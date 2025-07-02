"""
Regulatory Compliance Plugin

Integrates regulatory compliance tracking, audits, and penalties into the game.
Monitors company compliance and applies consequences based on behavior.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.interfaces import GameSystemPlugin
from core.models import Company, Turn, GameConfiguration, State
from core.events import on_event

from .services import ComplianceCalculator, AuditSystem, PenaltyEngine


class RegulatoryPlugin(GameSystemPlugin):
    """Regulatory compliance system plugin"""
    
    name = "regulatory_compliance"
    version = "1.0.0"
    
    def __init__(self):
        self.compliance_calculator = None
        self.audit_system = None
        self.penalty_engine = None
        
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the regulatory system"""
        self.config = config
        
        # Configuration for the regulatory system
        self.audit_base_seed = config.get("audit_base_seed", 42)
        self.enable_grace_periods = config.get("enable_grace_periods", True)
        self.strict_mode = config.get("strict_mode", False)
        
    async def on_turn_start(
        self,
        turn: Turn,
        companies: List[Company],
        session: AsyncSession,
        shared_state: Dict[str, Any]
    ) -> None:
        """Process regulatory compliance at turn start"""
        # Initialize services with session
        self.compliance_calculator = ComplianceCalculator(session)
        self.audit_system = AuditSystem(session)
        self.penalty_engine = PenaltyEngine(session)
        
        # Store compliance scores in shared state
        shared_state["compliance_scores"] = {}
        
        for company in companies:
            # Calculate compliance score
            compliance_result = await self.compliance_calculator.calculate_compliance_score(
                company
            )
            
            shared_state["compliance_scores"][company.id] = compliance_result
            
            # Check for audits
            # Use consistent seed based on turn and company for reproducibility
            random_seed = self.audit_base_seed + turn.turn_number + hash(str(company.id))
            
            audits = await self.audit_system.check_for_audits(
                company,
                compliance_result["overall_score"],
                turn.id,
                random_seed
            )
            
            # Store audit info for later processing
            if audits:
                if "company_audits" not in shared_state:
                    shared_state["company_audits"] = {}
                shared_state["company_audits"][company.id] = audits
                
            # Process any violations
            if compliance_result["violations"]:
                penalties_result = await self.penalty_engine.calculate_penalties(
                    company,
                    compliance_result["violations"],
                    compliance_result["overall_score"],
                    turn.id
                )
                
                # Apply financial penalties
                if penalties_result["total_penalty"] > 0:
                    company.current_capital -= penalties_result["total_penalty"]
                    
                    # Store penalty info for turn results
                    if "regulatory_penalties" not in shared_state:
                        shared_state["regulatory_penalties"] = {}
                    shared_state["regulatory_penalties"][company.id] = penalties_result
                    
                # Store warnings for turn results
                if penalties_result["warnings_issued"]:
                    if "regulatory_warnings" not in shared_state:
                        shared_state["regulatory_warnings"] = {}
                    shared_state["regulatory_warnings"][company.id] = penalties_result["warnings_issued"]
                    
        # Check for expired grace periods
        expired = await self.penalty_engine.process_grace_period_expirations(
            companies, turn.id
        )
        if expired:
            shared_state["expired_grace_periods"] = expired
            
        await session.flush()
    
    async def on_decision_submitted(
        self,
        company: Company,
        decisions: Dict[str, Any],
        session: AsyncSession,
        shared_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate decisions from a regulatory perspective"""
        validation_errors = []
        validation_warnings = []
        
        # Check if company can operate in requested states
        expansion_decisions = decisions.get("expansions", [])
        for expansion in expansion_decisions:
            state_id = expansion.get("state_id")
            
            # Check compliance score
            compliance_scores = shared_state.get("compliance_scores", {})
            company_compliance = compliance_scores.get(company.id, {})
            overall_score = company_compliance.get("overall_score", 100)
            
            if overall_score < 60:
                validation_warnings.append(
                    f"Low compliance score ({overall_score:.1f}) may delay expansion approval"
                )
                
        # Check if under audit
        company_audits = shared_state.get("company_audits", {})
        if company.id in company_audits:
            audits = company_audits[company.id]
            for audit in audits:
                if audit["severity"] in ["critical", "major"]:
                    validation_warnings.append(
                        f"Active {audit['severity']} audit in {audit['state_code']} may affect operations"
                    )
                    
        return {
            "valid": len(validation_errors) == 0,
            "errors": validation_errors,
            "warnings": validation_warnings
        }
    
    async def calculate_results(
        self,
        companies: List[Company],
        turn: Turn,
        session: AsyncSession,
        shared_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate regulatory impacts on turn results"""
        regulatory_results = {}
        
        for company in companies:
            company_results = {
                "compliance_score": None,
                "active_audits": [],
                "penalties_paid": 0,
                "warnings_received": []
            }
            
            # Get compliance score
            compliance_scores = shared_state.get("compliance_scores", {})
            if company.id in compliance_scores:
                company_results["compliance_score"] = compliance_scores[company.id]["overall_score"]
                
            # Get audit info
            company_audits = shared_state.get("company_audits", {})
            if company.id in company_audits:
                company_results["active_audits"] = company_audits[company.id]
                
            # Get penalties
            penalties = shared_state.get("regulatory_penalties", {})
            if company.id in penalties:
                company_results["penalties_paid"] = float(penalties[company.id]["total_penalty"])
                
            # Get warnings
            warnings = shared_state.get("regulatory_warnings", {})
            if company.id in warnings:
                company_results["warnings_received"] = warnings[company.id]
                
            regulatory_results[str(company.id)] = company_results
            
        return {
            "regulatory_compliance": regulatory_results
        }
    
    async def on_turn_complete(
        self,
        turn: Turn,
        results: Dict[str, Any],
        session: AsyncSession,
        shared_state: Dict[str, Any]
    ) -> None:
        """Update company data after turn completion"""
        # Update filing dates for companies that submitted decisions
        companies_stmt = select(Company).where(
            Company.semester_id == turn.semester_id
        )
        result = await session.execute(companies_stmt)
        companies = result.scalars().all()
        
        for company in companies:
            # Update last filing dates for states where company operates
            if company.id in results.get("decisions_submitted", []):
                # Get authorized states
                from core.models import CompanyStateAuthorization
                auth_stmt = select(CompanyStateAuthorization).where(
                    CompanyStateAuthorization.company_id == company.id,
                    CompanyStateAuthorization.is_approved == True
                )
                auth_result = await session.execute(auth_stmt)
                authorizations = auth_result.scalars().all()
                
                # Update filing dates
                if not company.operational_data:
                    company.operational_data = {}
                    
                if "last_filings" not in company.operational_data:
                    company.operational_data["last_filings"] = {}
                    
                for auth in authorizations:
                    state = await session.get(State, auth.state_id)
                    if state:
                        company.operational_data["last_filings"][state.code] = {
                            "date": datetime.utcnow().isoformat(),
                            "turn_number": turn.turn_number
                        }
                        
        await session.flush()
    
    async def on_bankruptcy(
        self,
        company: Company,
        turn: Turn,
        session: AsyncSession,
        shared_state: Dict[str, Any]
    ) -> None:
        """Handle regulatory implications of bankruptcy"""
        # Log regulatory failure
        from core.models import GameEvent
        
        event = GameEvent(
            event_type="regulatory_failure",
            category="regulatory",
            severity="critical",
            company_id=company.id,
            turn_id=turn.id,
            data={
                "reason": "bankruptcy",
                "compliance_score": shared_state.get("compliance_scores", {}).get(
                    company.id, {}
                ).get("overall_score"),
                "message": f"{company.name} regulatory licenses suspended due to bankruptcy"
            }
        )
        session.add(event)
        
    async def on_catastrophe(
        self,
        affected_companies: List[Company],
        catastrophe_data: Dict[str, Any],
        turn: Turn,
        session: AsyncSession,
        shared_state: Dict[str, Any]
    ) -> None:
        """Handle regulatory relief during catastrophes"""
        # Provide temporary regulatory relief
        affected_states = catastrophe_data.get("affected_states", [])
        
        for company in affected_companies:
            # Check if company operates in affected states
            from core.models import CompanyStateAuthorization
            auth_stmt = select(CompanyStateAuthorization).where(
                CompanyStateAuthorization.company_id == company.id,
                CompanyStateAuthorization.state_id.in_(affected_states),
                CompanyStateAuthorization.is_approved == True
            )
            result = await session.execute(auth_stmt)
            
            if result.scalar_one_or_none():
                # Grant temporary relief
                from core.models import GameEvent
                
                event = GameEvent(
                    event_type="regulatory_relief",
                    category="regulatory",
                    severity="info",
                    company_id=company.id,
                    turn_id=turn.id,
                    data={
                        "reason": "catastrophe",
                        "relief_weeks": 4,
                        "message": "Temporary regulatory relief granted due to catastrophe"
                    }
                )
                session.add(event)
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Return configuration schema for this plugin"""
        return {
            "type": "object",
            "properties": {
                "audit_base_seed": {
                    "type": "integer",
                    "description": "Base random seed for audit calculations"
                },
                "enable_grace_periods": {
                    "type": "boolean",
                    "description": "Whether to enable grace periods for violations"
                },
                "strict_mode": {
                    "type": "boolean",
                    "description": "Enable stricter compliance requirements"
                }
            }
        }
    
    def get_provided_events(self) -> List[str]:
        """Events this plugin emits"""
        return [
            "regulatory.audit_initiated",
            "regulatory.penalty_assessed",
            "regulatory.warning_issued",
            "regulatory.compliance_calculated"
        ]
    
    def get_required_events(self) -> List[str]:
        """Events this plugin listens for"""
        return []
    
    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate plugin configuration"""
        errors = []
        
        if "audit_base_seed" in config:
            if not isinstance(config["audit_base_seed"], int):
                errors.append("audit_base_seed must be an integer")
                
        return errors 