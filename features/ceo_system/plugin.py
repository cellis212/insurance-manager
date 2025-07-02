"""CEO System Plugin - Main plugin implementation."""

from decimal import Decimal
from typing import Any

from core.interfaces.game_system import GameSystemPlugin
from features.ceo_system.services.ceo_creation import CEOCreationService
from features.ceo_system.services.employee_hiring import EmployeeHiringService


class CEOSystemPlugin(GameSystemPlugin):
    """Plugin that manages CEO creation, progression, and employee hiring."""
    
    def __init__(self):
        """Initialize the CEO system plugin."""
        super().__init__()
        self.ceo_service = CEOCreationService()
        self.hiring_service = EmployeeHiringService()
    
    @property
    def plugin_id(self) -> str:
        """Unique identifier for this plugin."""
        return "ceo_system"
    
    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"
    
    @property
    def dependencies(self) -> list[str]:
        """Other plugins this depends on."""
        return []  # CEO system is foundational, no dependencies
    
    async def initialize(self, game_config: dict[str, Any]) -> None:
        """Initialize the CEO system with game configuration.
        
        Args:
            game_config: Global game configuration
        """
        # Load CEO-specific configuration
        self.config = game_config.get("ceo_parameters", {})
        self.employee_config = game_config.get("employee_parameters", {})
        
        # Initialize services with configuration
        await self.ceo_service.initialize(self.config)
        await self.hiring_service.initialize(self.employee_config)
    
    async def on_turn_start(self, turn_number: int, game_state: dict[str, Any]) -> dict[str, Any]:
        """Handle turn start events for CEO system.
        
        Args:
            turn_number: Current turn number
            game_state: Shared game state
            
        Returns:
            Updated game state
        """
        # Generate new employee candidates for hiring
        semester_id = game_state.get("semester_id")
        if semester_id:
            hiring_pool = await self.hiring_service.generate_weekly_hiring_pool(
                semester_id=semester_id,
                turn_number=turn_number
            )
            game_state["hiring_pool"] = hiring_pool
        
        # Check for CEO progression events
        for company in game_state.get("companies", []):
            if company.ceo:
                # Age CEOs by 1 week (52 weeks = 1 year)
                company.ceo.age += Decimal("0.019")  # 1/52
                
                # Check for milestone unlocks
                unlocked = company.ceo.check_milestone_unlocks()
                if unlocked:
                    self._emit_event("ceo.milestones_unlocked", {
                        "company_id": str(company.id),
                        "ceo_id": str(company.ceo.id),
                        "milestones": unlocked
                    })
                
                # Check for retirement
                if company.ceo.is_eligible_for_retirement:
                    self._emit_event("ceo.retirement_eligible", {
                        "company_id": str(company.id),
                        "ceo_id": str(company.ceo.id),
                        "age": int(company.ceo.age)
                    })
        
        return game_state
    
    async def calculate_results(
        self,
        company_id: str,
        decisions: dict[str, Any],
        market_conditions: dict[str, Any],
        game_state: dict[str, Any]
    ) -> dict[str, Any]:
        """Calculate CEO/employee impacts on turn results.
        
        Args:
            company_id: Company making decisions
            decisions: Company's turn decisions
            market_conditions: Current market conditions
            game_state: Shared game state
            
        Returns:
            CEO/employee impacts on results
        """
        results = {}
        
        # Find the company
        company = next(
            (c for c in game_state.get("companies", []) if str(c.id) == company_id),
            None
        )
        
        if not company or not company.ceo:
            return results
        
        # Calculate employee effectiveness with CEO multipliers
        employee_impacts = {}
        for employee in company.employees:
            # Get CEO multiplier for this position
            is_crisis = market_conditions.get("catastrophe_active", False)
            ceo_multiplier = company.ceo.get_employee_multiplier(
                position=employee.position,
                is_crisis=is_crisis
            )
            
            # Calculate effective skill
            effective_skill = employee.calculate_effective_skill(ceo_multiplier)
            
            # Get department impacts
            impacts = employee.get_department_impact()
            impacts["effective_skill"] = float(effective_skill)
            impacts["ceo_multiplier"] = float(ceo_multiplier)
            
            employee_impacts[employee.position] = impacts
        
        results["employee_impacts"] = employee_impacts
        
        # CEO direct impacts
        ceo_impacts = {
            "leadership_morale_boost": float(company.ceo.leadership) / 100,
            "crisis_active": market_conditions.get("catastrophe_active", False),
            "total_stat_points": company.ceo.total_stat_points
        }
        
        if market_conditions.get("catastrophe_active"):
            ceo_impacts["crisis_command_bonus"] = float(company.ceo.crisis_command) / 100
        
        results["ceo_impacts"] = ceo_impacts
        
        return results
    
    async def on_turn_complete(
        self,
        turn_number: int,
        turn_results: dict[str, Any],
        game_state: dict[str, Any]
    ) -> None:
        """Handle CEO progression after turn completion.
        
        Args:
            turn_number: Completed turn number
            turn_results: Results of the turn
            game_state: Shared game state
        """
        # Update CEO progression based on results
        for company_result in turn_results.get("company_results", []):
            company_id = company_result.get("company_id")
            company = next(
                (c for c in game_state.get("companies", []) if str(c.id) == company_id),
                None
            )
            
            if company and company.ceo:
                # Update lifetime profit
                net_income = company_result.get("net_income", Decimal("0"))
                company.ceo.lifetime_profit += max(Decimal("0"), net_income)
                
                # Increment quarters if turn is divisible by 13 (quarterly)
                if turn_number % 13 == 0:
                    company.ceo.quarters_led += 1
                    
                    # Update employee tenure
                    for employee in company.employees:
                        employee.quarters_employed += 1
                
                # Experience-based progression (simplified for MVP)
                # Every $10M profit = 1 point to distribute
                profit_points = int(company.ceo.lifetime_profit / Decimal("10000000"))
                if profit_points > company.ceo.total_stat_points - 240:  # 8 attrs * 30 start
                    self._emit_event("ceo.skill_points_available", {
                        "company_id": str(company.id),
                        "ceo_id": str(company.ceo.id),
                        "points": profit_points - (company.ceo.total_stat_points - 240)
                    })
    
    def validate_configuration(self, config: dict[str, Any]) -> list[str]:
        """Validate plugin-specific configuration.
        
        Args:
            config: Plugin configuration to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check for required CEO parameters
        if "starting_age_range" not in config:
            errors.append("Missing required config: starting_age_range")
        
        if "attribute_ranges" not in config:
            errors.append("Missing required config: attribute_ranges")
        
        # Validate attribute ranges
        if "attribute_ranges" in config:
            required_attrs = [
                "leadership", "risk_intelligence", "market_acumen",
                "regulatory_mastery", "innovation_capacity", "deal_making",
                "financial_expertise", "crisis_command"
            ]
            for attr in required_attrs:
                if attr not in config["attribute_ranges"]:
                    errors.append(f"Missing attribute range for: {attr}")
        
        return errors 