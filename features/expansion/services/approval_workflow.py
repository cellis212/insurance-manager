"""Approval workflow service for state expansions.

Manages the approval process including payment processing,
waiting periods, and authorization tracking.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import (
    Company,
    State,
    CompanyStateAuthorization,
    CompanyTurnDecision,
    AuditLog,
    GameEvent
)
from features.expansion.services.expansion_calculator import ExpansionCalculator

logger = logging.getLogger(__name__)


class ApprovalWorkflow:
    """Manages the approval workflow for state expansions."""
    
    def __init__(self, calculator: ExpansionCalculator):
        """Initialize workflow with calculator.
        
        Args:
            calculator: Expansion calculator for cost calculations
        """
        self.calculator = calculator
    
    async def request_expansion(
        self,
        session: AsyncSession,
        company: Company,
        target_state: State,
        turn_id: UUID
    ) -> Tuple[CompanyStateAuthorization, Dict[str, any]]:
        """Request expansion into a new state.
        
        Creates authorization record and processes payment.
        
        Args:
            session: Database session
            company: Company requesting expansion
            target_state: State to expand into
            turn_id: Current turn ID
            
        Returns:
            Tuple of (authorization, cost_details)
            
        Raises:
            ValueError: If expansion request is invalid
            RuntimeError: If insufficient funds
        """
        # Check if already authorized
        existing = await session.execute(
            select(CompanyStateAuthorization)
            .where(
                and_(
                    CompanyStateAuthorization.company_id == company.id,
                    CompanyStateAuthorization.state_id == target_state.id
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Company already has authorization for {target_state.name}")
        
        # Calculate expansion cost
        cost_details = await self.calculator.calculate_expansion_cost(
            session, company, target_state
        )
        
        # Validate sufficient capital
        if company.current_capital < cost_details["total_cost"]:
            raise RuntimeError(
                f"Insufficient capital: need {cost_details['total_cost']}, "
                f"have {company.current_capital}"
            )
        
        # Get pending expansions count
        pending_result = await session.execute(
            select(CompanyStateAuthorization)
            .where(
                and_(
                    CompanyStateAuthorization.company_id == company.id,
                    CompanyStateAuthorization.status == "pending"
                )
            )
        )
        pending_count = len(pending_result.scalars().all())
        
        # Validate expansion request
        is_valid, error_msg = self.calculator.validate_expansion_request(
            company, [target_state], pending_count
        )
        if not is_valid:
            raise ValueError(error_msg)
        
        # Process payment
        company.current_capital -= cost_details["total_cost"]
        
        # Create authorization record
        is_home_state = target_state.id == company.home_state_id
        expected_approval = date.today() + timedelta(weeks=cost_details["approval_weeks"])
        
        authorization = CompanyStateAuthorization(
            company_id=company.id,
            state_id=target_state.id,
            status="approved" if is_home_state else "pending",
            application_date=date.today(),
            approval_date=date.today() if is_home_state else None,
            expected_approval_date=None if is_home_state else expected_approval,
            is_compliant=True,
            compliance_score="excellent",
            is_home_state=is_home_state
        )
        
        session.add(authorization)
        
        # Create audit log
        audit = AuditLog(
            entity_type="company_state_authorization",
            entity_id=authorization.id,
            action="create",
            user_id=company.user_id,
            company_id=company.id,
            semester_id=company.semester_id,
            turn_number=company.turn_number,
            before_state={},
            after_state={
                "state": target_state.name,
                "status": authorization.status,
                "cost": str(cost_details["total_cost"])
            },
            financial_impact=-cost_details["total_cost"],
            details={
                "expansion_type": "home_state" if is_home_state else "new_state",
                "cost_breakdown": {
                    "base_cost": str(cost_details["base_cost"]),
                    "distance_cost": str(cost_details["distance_cost"]),
                    "discounts": {k: str(v) for k, v in cost_details["discounts"].items()}
                }
            }
        )
        session.add(audit)
        
        # Create game event
        event = GameEvent(
            semester_id=company.semester_id,
            company_id=company.id,
            turn_id=turn_id,
            event_type="expansion_requested",
            category="expansion",
            severity="info",
            title=f"Expansion to {target_state.name} Requested",
            description=(
                f"{company.name} has requested expansion to {target_state.name}. "
                f"{'Approved immediately (home state)' if is_home_state else f'Approval expected in {cost_details['approval_weeks']} weeks'}."
            ),
            event_data={
                "state_code": target_state.code,
                "state_name": target_state.name,
                "cost": str(cost_details["total_cost"]),
                "approval_weeks": cost_details["approval_weeks"],
                "is_home_state": is_home_state
            }
        )
        session.add(event)
        
        logger.info(
            f"Company {company.id} requested expansion to {target_state.code} "
            f"for ${cost_details['total_cost']}"
        )
        
        return authorization, cost_details
    
    async def process_pending_approvals(
        self,
        session: AsyncSession,
        turn_id: UUID,
        current_date: Optional[date] = None
    ) -> List[CompanyStateAuthorization]:
        """Process all pending expansion approvals.
        
        Checks for authorizations that have reached their approval date.
        
        Args:
            session: Database session
            turn_id: Current turn ID
            current_date: Current date (defaults to today)
            
        Returns:
            List of newly approved authorizations
        """
        if current_date is None:
            current_date = date.today()
        
        # Find pending authorizations ready for approval
        result = await session.execute(
            select(CompanyStateAuthorization)
            .where(
                and_(
                    CompanyStateAuthorization.status == "pending",
                    CompanyStateAuthorization.expected_approval_date <= current_date
                )
            )
        )
        pending_authorizations = result.scalars().all()
        
        approved = []
        
        for auth in pending_authorizations:
            # Update status
            auth.status = "approved"
            auth.approval_date = current_date
            
            # Get company and state for event
            company = await session.get(Company, auth.company_id)
            state = await session.get(State, auth.state_id)
            
            # Create approval event
            event = GameEvent(
                semester_id=company.semester_id,
                company_id=company.id,
                turn_id=turn_id,
                event_type="expansion_approved",
                category="expansion",
                severity="success",
                title=f"Expansion to {state.name} Approved",
                description=f"{company.name} is now authorized to operate in {state.name}.",
                event_data={
                    "state_code": state.code,
                    "state_name": state.name,
                    "authorization_id": str(auth.id)
                }
            )
            session.add(event)
            
            approved.append(auth)
            
            logger.info(f"Approved expansion for company {company.id} to state {state.code}")
        
        return approved
    
    async def get_pending_expansions(
        self,
        session: AsyncSession,
        company_id: UUID
    ) -> List[Dict]:
        """Get all pending expansions for a company.
        
        Args:
            session: Database session
            company_id: Company ID
            
        Returns:
            List of pending expansion details
        """
        result = await session.execute(
            select(CompanyStateAuthorization)
            .where(
                and_(
                    CompanyStateAuthorization.company_id == company_id,
                    CompanyStateAuthorization.status == "pending"
                )
            )
        )
        pending = result.scalars().all()
        
        expansions = []
        for auth in pending:
            state = await session.get(State, auth.state_id)
            days_remaining = auth.days_until_approval
            
            expansions.append({
                "authorization_id": auth.id,
                "state_code": state.code,
                "state_name": state.name,
                "application_date": auth.application_date,
                "expected_approval_date": auth.expected_approval_date,
                "days_remaining": days_remaining,
                "weeks_remaining": (days_remaining + 6) // 7  # Round up
            })
        
        return expansions
    
    async def get_authorized_states(
        self,
        session: AsyncSession,
        company_id: UUID
    ) -> List[State]:
        """Get all states a company is authorized to operate in.
        
        Args:
            session: Database session
            company_id: Company ID
            
        Returns:
            List of authorized states
        """
        result = await session.execute(
            select(State)
            .join(CompanyStateAuthorization)
            .where(
                and_(
                    CompanyStateAuthorization.company_id == company_id,
                    CompanyStateAuthorization.status == "approved",
                    CompanyStateAuthorization.is_compliant == True
                )
            )
        )
        return result.scalars().all()
    
    async def check_compliance(
        self,
        session: AsyncSession,
        authorization: CompanyStateAuthorization,
        turn_id: UUID
    ) -> bool:
        """Check and update compliance status for an authorization.
        
        Args:
            session: Database session
            authorization: Authorization to check
            turn_id: Current turn ID
            
        Returns:
            Whether the company is compliant
        """
        # For MVP, compliance is based on having active products and meeting capital requirements
        company = await session.get(Company, authorization.company_id)
        state = await session.get(State, authorization.state_id)
        
        # Check minimum capital requirement
        min_capital = state.additional_requirements.get(
            "minimum_capital_required",
            state.base_expansion_cost * 2
        )
        
        if company.current_capital < min_capital:
            authorization.is_compliant = False
            authorization.compliance_score = "poor"
            
            # Create compliance event
            event = GameEvent(
                semester_id=company.semester_id,
                company_id=company.id,
                turn_id=turn_id,
                event_type="compliance_violation",
                category="regulatory",
                severity="warning",
                title=f"Compliance Violation in {state.name}",
                description=(
                    f"{company.name} does not meet minimum capital requirements "
                    f"in {state.name} (${min_capital:,.0f} required)"
                ),
                event_data={
                    "state_code": state.code,
                    "violation_type": "insufficient_capital",
                    "required_capital": str(min_capital),
                    "current_capital": str(company.current_capital)
                }
            )
            session.add(event)
            
            return False
        
        # Update compliance score based on capital ratio
        capital_ratio = company.current_capital / min_capital
        if capital_ratio >= 2.0:
            authorization.compliance_score = "excellent"
        elif capital_ratio >= 1.5:
            authorization.compliance_score = "good"
        elif capital_ratio >= 1.25:
            authorization.compliance_score = "fair"
        else:
            authorization.compliance_score = "poor"
        
        authorization.is_compliant = True
        return True
    
    async def revoke_authorization(
        self,
        session: AsyncSession,
        authorization: CompanyStateAuthorization,
        reason: str,
        turn_id: UUID
    ) -> None:
        """Revoke a state authorization.
        
        Args:
            session: Database session
            authorization: Authorization to revoke
            reason: Reason for revocation
            turn_id: Current turn ID
        """
        authorization.status = "revoked"
        authorization.is_compliant = False
        
        company = await session.get(Company, authorization.company_id)
        state = await session.get(State, authorization.state_id)
        
        # Create revocation event
        event = GameEvent(
            semester_id=company.semester_id,
            company_id=company.id,
            turn_id=turn_id,
            event_type="authorization_revoked",
            category="regulatory",
            severity="error",
            title=f"Authorization Revoked in {state.name}",
            description=f"{company.name}'s authorization to operate in {state.name} has been revoked: {reason}",
            event_data={
                "state_code": state.code,
                "state_name": state.name,
                "reason": reason,
                "authorization_id": str(authorization.id)
            }
        )
        session.add(event)
        
        logger.warning(
            f"Revoked authorization for company {company.id} in state {state.code}: {reason}"
        ) 