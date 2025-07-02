"""Geographic expansion plugin for the Insurance Manager game.

Integrates expansion functionality with the game engine,
handling turn lifecycle events and approval processing.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.events import on_event
from core.interfaces import GameSystemPlugin
from core.models import Company, CompanyStateAuthorization, State
from features.expansion.services import ExpansionCalculator, ApprovalWorkflow

logger = logging.getLogger(__name__)


class ExpansionPlugin(GameSystemPlugin):
    """Plugin for managing geographic expansion mechanics."""
    
    def __init__(self):
        """Initialize the expansion plugin."""
        super().__init__()
        self.calculator: Optional[ExpansionCalculator] = None
        self.workflow: Optional[ApprovalWorkflow] = None
    
    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "Geographic Expansion System"
    
    @property
    def version(self) -> str:
        """Return the plugin version."""
        return "1.0.0"
    
    @property
    def dependencies(self) -> list[str]:
        """Return plugin dependencies."""
        return []  # No dependencies on other plugins
    
    async def initialize(self, game_config: Dict[str, Any]) -> None:
        """Initialize the plugin with game configuration.
        
        Args:
            game_config: Game configuration dictionary
        """
        # Extract expansion configuration
        expansion_config = {
            **game_config.get("expansion_parameters", {}),
            "home_state_discount": game_config.get("initial_values", {}).get("home_state_discount", 0.5),
            "adjacent_state_discount": 0.2,  # Default value
            "same_region_discount": 0.1,     # Default value
        }
        
        # Initialize services
        self.calculator = ExpansionCalculator(expansion_config)
        self.workflow = ApprovalWorkflow(self.calculator)
        
        # Register event handlers
        self._register_event_handlers()
        
        logger.info(f"Initialized {self.name} v{self.version}")
    
    def _register_event_handlers(self) -> None:
        """Register event handlers for the expansion system."""
        @on_event("company.created")
        async def handle_company_created(event_data: Dict[str, Any]) -> None:
            """Automatically authorize home state when company is created."""
            company_id = event_data.get("company_id")
            session = event_data.get("session")
            
            if not company_id or not session:
                return
            
            company = await session.get(Company, company_id)
            if not company or not company.home_state_id:
                return
            
            # Check if home state authorization already exists
            existing = await session.execute(
                select(CompanyStateAuthorization)
                .where(
                    CompanyStateAuthorization.company_id == company.id,
                    CompanyStateAuthorization.state_id == company.home_state_id
                )
            )
            if existing.scalar_one_or_none():
                return
            
            # Create home state authorization
            home_auth = CompanyStateAuthorization(
                company_id=company.id,
                state_id=company.home_state_id,
                status="approved",
                application_date=company.founded_date,
                approval_date=company.founded_date,
                is_compliant=True,
                compliance_score="excellent",
                is_home_state=True
            )
            session.add(home_auth)
            
            logger.info(f"Auto-approved home state for company {company.id}")
    
    async def on_turn_start(
        self,
        session: AsyncSession,
        turn_data: Dict[str, Any],
        game_state: Dict[str, Any]
    ) -> None:
        """Process pending expansion approvals at turn start.
        
        Args:
            session: Database session
            turn_data: Current turn information
            game_state: Shared game state
        """
        turn_id = turn_data.get("turn_id")
        current_date = turn_data.get("current_date")
        
        if not turn_id:
            logger.warning("No turn_id provided to expansion plugin")
            return
        
        # Process pending approvals
        approved = await self.workflow.process_pending_approvals(
            session, turn_id, current_date
        )
        
        if approved:
            logger.info(f"Processed {len(approved)} expansion approvals")
            
            # Emit events for each approval
            for auth in approved:
                await self._emit_event("expansion.approved", {
                    "authorization_id": auth.id,
                    "company_id": auth.company_id,
                    "state_id": auth.state_id
                })
    
    async def on_decision_submitted(
        self,
        session: AsyncSession,
        company: Company,
        decisions: Dict[str, Any],
        game_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate expansion decisions when submitted.
        
        Args:
            session: Database session
            company: Company submitting decisions
            decisions: Decision data
            game_state: Shared game state
            
        Returns:
            Validation results
        """
        expansion_decisions = decisions.get("expansions", [])
        
        if not expansion_decisions:
            return {"valid": True}
        
        # Validate expansion requests
        errors = []
        total_cost = 0
        
        for state_code in expansion_decisions:
            # Get state
            result = await session.execute(
                select(State).where(State.code == state_code)
            )
            state = result.scalar_one_or_none()
            
            if not state:
                errors.append(f"Invalid state code: {state_code}")
                continue
            
            # Check if already authorized
            existing = await session.execute(
                select(CompanyStateAuthorization)
                .where(
                    CompanyStateAuthorization.company_id == company.id,
                    CompanyStateAuthorization.state_id == state.id
                )
            )
            if existing.scalar_one_or_none():
                errors.append(f"Already authorized in {state.name}")
                continue
            
            # Calculate cost
            cost_details = await self.calculator.calculate_expansion_cost(
                session, company, state
            )
            total_cost += cost_details["total_cost"]
        
        # Check capital
        if total_cost > company.current_capital:
            errors.append(f"Insufficient capital: need ${total_cost:,.0f}")
        
        # Check expansion limit
        pending_result = await session.execute(
            select(CompanyStateAuthorization)
            .where(
                CompanyStateAuthorization.company_id == company.id,
                CompanyStateAuthorization.status == "pending"
            )
        )
        pending_count = len(pending_result.scalars().all())
        
        if len(expansion_decisions) + pending_count > self.calculator.max_states_per_turn:
            errors.append(f"Cannot expand to more than {self.calculator.max_states_per_turn} states per turn")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "total_cost": total_cost
        }
    
    async def calculate_results(
        self,
        session: AsyncSession,
        company: Company,
        turn_data: Dict[str, Any],
        game_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate expansion-related results for the turn.
        
        Args:
            session: Database session
            company: Company to calculate for
            turn_data: Current turn information
            game_state: Shared game state
            
        Returns:
            Expansion results
        """
        # Check compliance for all authorizations
        auth_result = await session.execute(
            select(CompanyStateAuthorization)
            .where(
                CompanyStateAuthorization.company_id == company.id,
                CompanyStateAuthorization.status == "approved"
            )
        )
        authorizations = auth_result.scalars().all()
        
        compliance_violations = []
        for auth in authorizations:
            is_compliant = await self.workflow.check_compliance(
                session, auth, turn_data["turn_id"]
            )
            if not is_compliant:
                state = await session.get(State, auth.state_id)
                compliance_violations.append({
                    "state_code": state.code,
                    "state_name": state.name,
                    "compliance_score": auth.compliance_score
                })
        
        # Calculate expansion bonuses
        home_state_bonus = 0
        if any(auth.is_home_state for auth in authorizations):
            # Home state market share bonus from config
            home_state_bonus = game_state.get("config", {}).get(
                "initial_values", {}
            ).get("home_state_market_bonus", 0.1)
        
        return {
            "authorized_states": len(authorizations),
            "compliance_violations": compliance_violations,
            "home_state_bonus": home_state_bonus
        }
    
    async def on_turn_complete(
        self,
        session: AsyncSession,
        turn_data: Dict[str, Any],
        results: Dict[str, Any],
        game_state: Dict[str, Any]
    ) -> None:
        """Handle turn completion for expansion system.
        
        Args:
            session: Database session
            turn_data: Current turn information
            results: Turn processing results
            game_state: Shared game state
        """
        # Check for companies that should have authorizations revoked
        for company_id, company_results in results.items():
            if company_results.get("is_bankrupt"):
                # Revoke all non-home state authorizations for bankrupt companies
                auth_result = await session.execute(
                    select(CompanyStateAuthorization)
                    .where(
                        CompanyStateAuthorization.company_id == company_id,
                        CompanyStateAuthorization.is_home_state == False,
                        CompanyStateAuthorization.status == "approved"
                    )
                )
                for auth in auth_result.scalars().all():
                    await self.workflow.revoke_authorization(
                        session, auth, "Company bankruptcy", turn_data["turn_id"]
                    )
    
    async def on_catastrophe(
        self,
        session: AsyncSession,
        event_data: Dict[str, Any],
        game_state: Dict[str, Any]
    ) -> None:
        """Handle catastrophe events affecting expansions.
        
        Args:
            session: Database session
            event_data: Catastrophe event information
            game_state: Shared game state
        """
        # Catastrophes might affect compliance in affected states
        affected_states = event_data.get("affected_states", [])
        
        if not affected_states:
            return
        
        # Log the catastrophe impact
        logger.info(
            f"Catastrophe affecting expansions in states: {affected_states}"
        ) 