"""
Penalty Engine for Regulatory Compliance

Manages:
- Grace period tracking per violation type
- Penalty calculations based on severity
- Escalating penalties for repeat offenders
- Financial impact calculations
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import (
    Company, Employee, State, GameEvent, AuditLog,
    CompanyTurnResult
)


class PenaltyEngine:
    """Calculates and applies regulatory penalties"""
    
    # Grace period settings by violation type
    GRACE_PERIODS = {
        "Late regulatory filings": {
            "first_offense_weeks": 4,
            "repeat_offense_weeks": 2,
            "max_offenses_with_grace": 2
        },
        "Insufficient capital reserves": {
            "first_offense_weeks": 2,  # Less time for critical issues
            "repeat_offense_weeks": 1,
            "max_offenses_with_grace": 1
        },
        "Non-compliant products": {
            "first_offense_weeks": 6,
            "repeat_offense_weeks": 3,
            "max_offenses_with_grace": 2
        },
        "Missing required certifications": {
            "first_offense_weeks": 8,
            "repeat_offense_weeks": 4,
            "max_offenses_with_grace": 3
        },
        "Operating without authorization": {
            "first_offense_weeks": 0,  # No grace period - immediate penalty
            "repeat_offense_weeks": 0,
            "max_offenses_with_grace": 0
        }
    }
    
    # Base penalty amounts by violation type (as % of capital)
    BASE_PENALTIES = {
        "Late regulatory filings": Decimal("0.005"),      # 0.5% per occurrence
        "Insufficient capital reserves": Decimal("0.02"), # 2% - serious issue
        "Non-compliant products": Decimal("0.01"),       # 1% per product
        "Missing required certifications": Decimal("0.008"), # 0.8%
        "Operating without authorization": Decimal("0.05")  # 5% - most severe
    }
    
    # Multipliers for repeat offenses
    REPEAT_MULTIPLIERS = [
        Decimal("1.0"),   # First offense
        Decimal("1.5"),   # Second offense
        Decimal("2.0"),   # Third offense
        Decimal("3.0"),   # Fourth+ offense
    ]
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def calculate_penalties(
        self,
        company: Company,
        violations: List[str],
        compliance_score: float,
        turn_id: UUID
    ) -> Dict[str, any]:
        """
        Calculate penalties for current violations
        
        Returns:
        - total_penalty: Decimal amount
        - penalty_details: List of individual penalties
        - grace_periods: Active grace periods
        - warnings_issued: New warnings
        """
        penalty_details = []
        warnings_issued = []
        grace_periods = []
        total_penalty = Decimal("0")
        
        # Get violation history
        violation_history = await self._get_violation_history(company.id)
        
        # Get CCO skill for mitigation
        cco_skill = await self._get_cco_skill(company)
        
        # Process each violation
        for violation in violations:
            # Check if in grace period
            grace_status = await self._check_grace_period(
                company.id, violation, violation_history
            )
            
            if grace_status["in_grace"]:
                grace_periods.append({
                    "violation": violation,
                    "expires": grace_status["expires"],
                    "offense_number": grace_status["offense_number"]
                })
                
                # Issue warning
                warnings_issued.append({
                    "violation": violation,
                    "message": f"Warning: {violation} - Grace period expires in {grace_status['weeks_remaining']} weeks",
                    "severity": "warning"
                })
            else:
                # Calculate penalty
                penalty = await self._calculate_violation_penalty(
                    company,
                    violation,
                    violation_history,
                    compliance_score,
                    cco_skill
                )
                
                penalty_details.append(penalty)
                total_penalty += penalty["amount"]
                
        # Apply overall caps
        total_penalty = self._apply_penalty_caps(
            total_penalty,
            company.current_capital,
            compliance_score
        )
        
        # Log penalties
        if total_penalty > 0:
            await self._log_penalties(
                company, penalty_details, total_penalty, turn_id
            )
            
        return {
            "total_penalty": total_penalty,
            "penalty_details": penalty_details,
            "grace_periods": grace_periods,
            "warnings_issued": warnings_issued
        }
    
    async def _get_violation_history(
        self, 
        company_id: UUID,
        lookback_weeks: int = 52
    ) -> Dict[str, List[GameEvent]]:
        """Get violation history by type"""
        cutoff_date = datetime.utcnow() - timedelta(weeks=lookback_weeks)
        
        stmt = select(GameEvent).where(
            and_(
                GameEvent.company_id == company_id,
                GameEvent.event_type.in_([
                    "regulatory_violation",
                    "regulatory_warning",
                    "regulatory_penalty"
                ]),
                GameEvent.created_at >= cutoff_date
            )
        ).order_by(GameEvent.created_at.desc())
        
        result = await self.session.execute(stmt)
        events = result.scalars().all()
        
        # Group by violation type
        history = {}
        for event in events:
            violation_type = event.data.get("violation_type")
            if violation_type:
                if violation_type not in history:
                    history[violation_type] = []
                history[violation_type].append(event)
                
        return history
    
    async def _get_cco_skill(self, company: Company) -> int:
        """Get CCO skill level for penalty mitigation"""
        emp_stmt = select(Employee).where(
            Employee.company_id == company.id,
            Employee.position == "CCO",
            Employee.is_active == True
        )
        result = await self.session.execute(emp_stmt)
        cco = result.scalar_one_or_none()
        
        return cco.skill_level if cco else 0
    
    async def _check_grace_period(
        self,
        company_id: UUID,
        violation: str,
        history: Dict[str, List[GameEvent]]
    ) -> Dict[str, any]:
        """Check if company is in grace period for this violation"""
        grace_config = self.GRACE_PERIODS.get(
            violation,
            self.GRACE_PERIODS["Late regulatory filings"]  # Default
        )
        
        # Get previous occurrences
        previous = history.get(violation, [])
        offense_number = len(previous) + 1
        
        # Check if eligible for grace period
        if offense_number > grace_config["max_offenses_with_grace"]:
            return {"in_grace": False, "offense_number": offense_number}
            
        # Determine grace period length
        if offense_number == 1:
            grace_weeks = grace_config["first_offense_weeks"]
        else:
            grace_weeks = grace_config["repeat_offense_weeks"]
            
        if grace_weeks == 0:
            return {"in_grace": False, "offense_number": offense_number}
            
        # Check if already warned
        recent_warnings = [
            e for e in previous
            if e.event_type == "regulatory_warning"
            and (datetime.utcnow() - e.created_at).days <= grace_weeks * 7
        ]
        
        if recent_warnings:
            # Already in grace period
            expires = recent_warnings[0].created_at + timedelta(weeks=grace_weeks)
            weeks_remaining = max(0, (expires - datetime.utcnow()).days // 7)
            return {
                "in_grace": True,
                "expires": expires,
                "weeks_remaining": weeks_remaining,
                "offense_number": offense_number
            }
        else:
            # New grace period
            expires = datetime.utcnow() + timedelta(weeks=grace_weeks)
            return {
                "in_grace": True,
                "expires": expires,
                "weeks_remaining": grace_weeks,
                "offense_number": offense_number
            }
    
    async def _calculate_violation_penalty(
        self,
        company: Company,
        violation: str,
        history: Dict[str, List[GameEvent]],
        compliance_score: float,
        cco_skill: int
    ) -> Dict[str, any]:
        """Calculate penalty for a specific violation"""
        # Base penalty
        base_pct = self.BASE_PENALTIES.get(
            violation,
            Decimal("0.01")  # Default 1%
        )
        
        # Get offense number
        previous = history.get(violation, [])
        offense_number = len([
            e for e in previous 
            if e.event_type == "regulatory_penalty"
        ]) + 1
        
        # Apply repeat multiplier
        multiplier_idx = min(offense_number - 1, len(self.REPEAT_MULTIPLIERS) - 1)
        repeat_multiplier = self.REPEAT_MULTIPLIERS[multiplier_idx]
        
        # CCO skill mitigation (up to 30% reduction for expert CCO)
        cco_mitigation = Decimal("1.0")
        if cco_skill >= 80:
            cco_mitigation = Decimal("0.7")
        elif cco_skill >= 60:
            cco_mitigation = Decimal("0.8")
        elif cco_skill >= 40:
            cco_mitigation = Decimal("0.9")
            
        # Compliance score adjustment
        compliance_multiplier = Decimal("1.0")
        if compliance_score >= 80:
            compliance_multiplier = Decimal("0.8")  # 20% reduction
        elif compliance_score <= 50:
            compliance_multiplier = Decimal("1.2")  # 20% increase
            
        # Calculate final penalty
        penalty_pct = (
            base_pct * 
            repeat_multiplier * 
            cco_mitigation * 
            compliance_multiplier
        )
        
        penalty_amount = (
            company.current_capital * penalty_pct
        ).quantize(Decimal("0.01"))
        
        return {
            "violation": violation,
            "base_percentage": float(base_pct),
            "offense_number": offense_number,
            "repeat_multiplier": float(repeat_multiplier),
            "cco_mitigation": float(cco_mitigation),
            "compliance_adjustment": float(compliance_multiplier),
            "final_percentage": float(penalty_pct),
            "amount": penalty_amount
        }
    
    def _apply_penalty_caps(
        self,
        total_penalty: Decimal,
        current_capital: Decimal,
        compliance_score: float
    ) -> Decimal:
        """Apply caps to prevent excessive penalties"""
        # Maximum penalty as % of capital
        if compliance_score >= 70:
            max_pct = Decimal("0.10")  # 10% cap for good compliance
        elif compliance_score >= 50:
            max_pct = Decimal("0.15")  # 15% cap for average
        else:
            max_pct = Decimal("0.20")  # 20% cap for poor compliance
            
        max_penalty = current_capital * max_pct
        
        return min(total_penalty, max_penalty).quantize(Decimal("0.01"))
    
    async def _log_penalties(
        self,
        company: Company,
        penalty_details: List[Dict],
        total_penalty: Decimal,
        turn_id: UUID
    ) -> None:
        """Log penalty events"""
        # Create penalty event
        event = GameEvent(
            event_type="regulatory_penalty",
            category="regulatory",
            severity="error",
            company_id=company.id,
            turn_id=turn_id,
            data={
                "total_penalty": str(total_penalty),
                "penalty_count": len(penalty_details),
                "penalties": penalty_details,
                "message": f"Regulatory penalties assessed: ${total_penalty:,.2f}"
            }
        )
        self.session.add(event)
        
        # Create audit log
        audit_log = AuditLog(
            entity_type="company",
            entity_id=str(company.id),
            action="penalties_assessed",
            changes={
                "capital_before": str(company.current_capital),
                "penalty_amount": str(total_penalty),
                "violations": [p["violation"] for p in penalty_details]
            },
            user_id=None,  # System-initiated
            turn_id=turn_id,
            additional_data={
                "penalty_details": penalty_details
            }
        )
        self.session.add(audit_log)
        
    async def process_grace_period_expirations(
        self,
        companies: List[Company],
        turn_id: UUID
    ) -> List[Dict]:
        """Check for expired grace periods and convert to penalties"""
        expired_penalties = []
        
        for company in companies:
            # Get active warnings
            stmt = select(GameEvent).where(
                and_(
                    GameEvent.company_id == company.id,
                    GameEvent.event_type == "regulatory_warning",
                    GameEvent.created_at >= datetime.utcnow() - timedelta(weeks=12)
                )
            )
            result = await self.session.execute(stmt)
            warnings = result.scalars().all()
            
            for warning in warnings:
                grace_expires = warning.data.get("grace_expires")
                if grace_expires:
                    expires_date = datetime.fromisoformat(grace_expires)
                    if expires_date <= datetime.utcnow():
                        # Grace period expired - check if violation still exists
                        violation = warning.data.get("violation_type")
                        
                        # This would need integration with compliance calculator
                        # to check if violation is resolved
                        # For now, we'll assume it needs to be checked
                        expired_penalties.append({
                            "company_id": company.id,
                            "violation": violation,
                            "warning_date": warning.created_at,
                            "expired_date": expires_date
                        })
                        
        return expired_penalties
