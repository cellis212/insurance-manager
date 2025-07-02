"""Market events plugin implementation.

Comprehensive market events system that includes:
- Economic boom/bust cycles with realistic transitions
- Various market-wide events (regulatory, technology, catastrophes)
- AI competitor behavior that reacts to market conditions
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select

from core.interfaces import GameSystemPlugin
from core.events import event_bus, EventPriority
from core.models import Turn, Company, CompanyTurnDecision, MarketCondition, CEO, PriceDecision
from features.market_events.services import (
    EconomicCycleManager,
    MarketEventGenerator,
    CompetitorBehaviorEngine
)


class MarketEventsPlugin(GameSystemPlugin):
    """Plugin that manages economic cycles, market events, and competitor behavior.
    
    This plugin:
    - Generates economic boom/bust cycles with momentum
    - Creates various market-wide events (regulatory changes, catastrophes, etc.)
    - Simulates AI competitor companies that react to market conditions
    - Provides CEO market acumen benefits for anticipating changes
    """
    
    VERSION = "2.0.0"
    DEPENDENCIES = ["ceo_system"]  # Need CEO attributes for market acumen
    
    def __init__(self):
        """Initialize the market events plugin."""
        super().__init__()
        self.economic_cycle_manager = None
        self.market_event_generator = None
        self.competitor_behavior_engine = None
        self._config = {}
        self._active_events = []
        self._current_economic_phase = None
    
    async def initialize(self, game_config: Dict[str, Any]) -> None:
        """Initialize the plugin with game configuration.
        
        Args:
            game_config: Game configuration from database
        """
        # Store configuration
        self._config = game_config.get("market_events", {
            "enable_economic_cycles": True,
            "enable_market_events": True,
            "enable_competitors": True,
            "num_competitors": 5,
            "event_probability_multiplier": 1.0
        })
        
        # Register event handlers
        event_bus.register(
            "turn.started",
            self._handle_turn_start,
            priority=EventPriority.HIGH,
            plugin_name=self.name
        )
        
        event_bus.register(
            "company.bankrupt",
            self._handle_bankruptcy,
            priority=EventPriority.NORMAL,
            plugin_name=self.name
        )
        
        event_bus.register(
            "semester.started",
            self._handle_semester_start,
            priority=EventPriority.HIGH,
            plugin_name=self.name
        )
    
    async def on_turn_start(self, turn: Turn, game_state: Dict[str, Any]) -> None:
        """Process economic cycles and check for new market events at turn start.
        
        Args:
            turn: Current turn being processed
            game_state: Shared game state
        """
        # Get database session from game state
        session = game_state.get("session")
        if not session:
            return
        
        # Initialize managers if needed
        if not self.economic_cycle_manager:
            self.economic_cycle_manager = EconomicCycleManager(session)
            self.market_event_generator = MarketEventGenerator(session)
            self.competitor_behavior_engine = CompetitorBehaviorEngine(session)
        
        # Process economic cycles
        if self._config.get("enable_economic_cycles", True):
            phase, impacts = await self.economic_cycle_manager.advance_cycle(turn)
            self._current_economic_phase = phase
            
            # Apply economic impacts to market conditions
            await self.economic_cycle_manager.apply_cycle_to_market_conditions(
                turn, impacts
            )
            
            # Store in game state for other systems
            game_state["economic_phase"] = phase.value
            game_state["economic_impacts"] = impacts
        
        # Check for new market events
        if self._config.get("enable_market_events", True):
            # Get company actions from previous turn
            company_actions = await self._get_company_actions(session, turn)
            
            # Generate new events
            new_events = await self.market_event_generator.check_for_events(
                turn,
                self._current_economic_phase.value if self._current_economic_phase else "expansion",
                company_actions
            )
            
            # Update active events
            self._active_events = await self.market_event_generator.update_active_events(turn)
            
            # Store combined impacts
            combined_impacts = self.market_event_generator.get_combined_impacts()
            game_state["market_event_impacts"] = combined_impacts
            game_state["active_market_events"] = [
                {
                    "name": e.name,
                    "type": e.event_type.value,
                    "severity": e.severity,
                    "weeks_remaining": e.duration_weeks
                }
                for e in self._active_events
            ]
        
        # Generate competitor decisions
        if self._config.get("enable_competitors", True):
            player_actions = await self._get_player_actions(session, turn)
            
            competitor_decisions = await self.competitor_behavior_engine.generate_competitor_decisions(
                turn,
                self._current_economic_phase or "expansion",
                self._active_events,
                player_actions
            )
            
            # Store competitor count for market simulation
            game_state["num_competitors"] = len(competitor_decisions)
    
    async def on_decision_submitted(
        self, 
        company: Company, 
        decision: CompanyTurnDecision,
        game_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Validate decisions in context of market events.
        
        Args:
            company: Company submitting decisions
            decision: Submitted decisions
            game_state: Shared game state
            
        Returns:
            Validation result or None if valid
        """
        # Check if severe market events restrict certain actions
        for event in self._active_events:
            if event.severity >= 2.5:  # Severe events
                decisions = decision.decisions or {}
                
                # During catastrophes, limit expansions
                if event.event_type.value == "catastrophe":
                    if event.affected_states and company.home_state_id in event.affected_states:
                        if "expansions" in decisions and decisions["expansions"]:
                            return {
                                "valid": False,
                                "errors": [
                                    f"Cannot expand during severe {event.name} affecting your home state"
                                ]
                            }
                
                # During regulatory changes, increase compliance requirements
                elif event.event_type.value == "regulatory_change":
                    # This would integrate with regulatory plugin
                    pass
        
        return None  # No validation errors
    
    async def calculate_results(
        self, 
        turn: Turn,
        companies: List[Company],
        game_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate market event and economic impacts on companies.
        
        Args:
            turn: Current turn
            companies: All companies in the game
            game_state: Shared game state with results from other stages
            
        Returns:
            Market event results to merge into turn results
        """
        results = {
            "economic_phase": self._current_economic_phase.value if self._current_economic_phase else None,
            "economic_impacts": game_state.get("economic_impacts", {}),
            "active_events": game_state.get("active_market_events", []),
            "company_impacts": {}
        }
        
        # Get session for CEO lookups
        session = game_state.get("session")
        
        # Calculate impacts on each company
        for company in companies:
            company_impact = {
                "economic_phase_effects": {},
                "market_event_effects": {},
                "ceo_market_insights": {}
            }
            
            # Apply economic phase impacts (already in market conditions)
            if self._current_economic_phase:
                impacts = game_state.get("economic_impacts", {})
                company_impact["economic_phase_effects"] = {
                    "investment_return_modifier": float(impacts.get("investment_return_bonus", 0)),
                    "claim_frequency_modifier": float(impacts.get("claim_frequency_modifier", 1.0))
                }
            
            # Apply market event impacts
            if self._active_events:
                combined_impacts = self.market_event_generator.get_combined_impacts()
                
                # Check catastrophe impacts for specific states
                for event in self._active_events:
                    if event.event_type.value == "catastrophe":
                        if event.affected_states and company.home_state_id in event.affected_states:
                            # Company is directly affected
                            company_impact["market_event_effects"]["catastrophe_claims_multiplier"] = float(
                                combined_impacts.get("claims_surge_multiplier", 1.0)
                            )
                
                # Apply general market event impacts
                for impact_type, value in combined_impacts.items():
                    if impact_type not in ["claims_surge_multiplier"]:  # Already handled above
                        company_impact["market_event_effects"][impact_type] = float(value)
            
            # CEO market acumen provides insights
            if session and company.ceo:
                ceo = await session.get(CEO, company.id)
                if ceo and ceo.market_acumen >= 60:
                    # High market acumen provides economic predictions
                    insight_multiplier = self.economic_cycle_manager.get_ceo_insight_multiplier(
                        ceo.market_acumen
                    )
                    
                    if self._current_economic_phase:
                        next_phase_probs = self.economic_cycle_manager.predict_next_phase(
                            self._current_economic_phase
                        )
                        company_impact["ceo_market_insights"] = {
                            "current_phase": self._current_economic_phase.value,
                            "phase_change_probability": next_phase_probs,
                            "insight_accuracy": float(insight_multiplier)
                        }
            
            results["company_impacts"][str(company.id)] = company_impact
        
        return results
    
    async def on_turn_complete(
        self, 
        turn: Turn,
        results: Dict[str, Any],
        game_state: Dict[str, Any]
    ) -> None:
        """Handle cleanup after turn processing.
        
        Args:
            turn: Completed turn
            results: Final turn results
            game_state: Shared game state
        """
        # Emit events for analysis
        if self._current_economic_phase:
            await event_bus.emit(
                "economic_phase.recorded",
                {
                    "turn_id": str(turn.id),
                    "phase": self._current_economic_phase.value,
                    "impacts": game_state.get("economic_impacts", {})
                },
                source=self.name
            )
        
        # Record active market events
        if self._active_events:
            await event_bus.emit(
                "market_events.active",
                {
                    "turn_id": str(turn.id),
                    "events": [e.name for e in self._active_events],
                    "combined_impacts": self.market_event_generator.get_combined_impacts()
                },
                source=self.name
            )
    
    async def _handle_bankruptcy(self, event: Any) -> None:
        """Handle bankruptcy events that might trigger market events.
        
        Args:
            event: Bankruptcy event data
        """
        # Track bankruptcies for potential industry scandal
        turn_id = event.data.get("turn_id")
        if turn_id and self.market_event_generator:
            # This will be picked up in next turn's company_actions
            await event_bus.emit(
                "market.competitor_bankrupt",
                {"company_id": event.data.get("company_id")},
                source=self.name
            )
    
    async def _handle_semester_start(self, event: Any) -> None:
        """Initialize competitors when semester starts.
        
        Args:
            event: Semester start event
        """
        semester_id = event.data.get("semester_id")
        session = event.data.get("session")
        
        if semester_id and session and self._config.get("enable_competitors", True):
            # Initialize competitor behavior engine
            if not self.competitor_behavior_engine:
                self.competitor_behavior_engine = CompetitorBehaviorEngine(session)
            
            # Create competitor companies
            num_competitors = self._config.get("num_competitors", 5)
            await self.competitor_behavior_engine.initialize_competitors(
                semester_id, num_competitors
            )
    
    async def _handle_turn_start(self, event: Any) -> None:
        """Handle turn start event from event bus.
        
        Args:
            event: Turn start event
        """
        # This ensures economic cycles are processed early in turn
        turn = event.data.get("turn")
        game_state = event.data.get("game_state", {})
        
        if turn and self._config.get("enable_economic_cycles", True):
            # Process will happen in on_turn_start
            pass
    
    async def _get_company_actions(
        self,
        session: Any,
        turn: Turn
    ) -> Dict[str, Any]:
        """Get company actions from previous turn for event generation.
        
        Args:
            session: Database session
            turn: Current turn
            
        Returns:
            Dictionary of relevant company actions
        """
        # Count bankruptcies in last turn
        if turn.week_number > 1:
            # Query for companies that went bankrupt
            result = await session.execute(
                select(Company).where(
                    Company.semester_id == turn.semester_id,
                    Company.operational_data["bankruptcy_turn"].astext == str(turn.week_number - 1)
                )
            )
            bankruptcies = len(result.scalars().all())
        else:
            bankruptcies = 0
        
        return {
            "bankruptcies_this_turn": bankruptcies
        }
    
    async def _get_player_actions(
        self,
        session: Any,
        turn: Turn
    ) -> Dict[str, Any]:
        """Get player actions for competitor intelligence.
        
        Args:
            session: Database session
            turn: Current turn
            
        Returns:
            Dictionary of player actions
        """
        # Get average player pricing
        result = await session.execute(
            select(PriceDecision).where(
                PriceDecision.turn_id == turn.id
            )
        )
        price_decisions = result.scalars().all()
        
        if price_decisions:
            avg_multiplier = sum(p.price_multiplier for p in price_decisions) / len(price_decisions)
        else:
            avg_multiplier = 1.0
        
        return {
            "average_player_prices": float(avg_multiplier),
            "num_player_companies": len([c for c in await session.execute(
                select(Company).where(
                    Company.semester_id == turn.semester_id,
                    Company.user_id.isnot(None)
                )
            ).scalars().all()])
        }
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Get configuration schema for this plugin.
        
        Returns:
            JSON schema for plugin configuration
        """
        return {
            "type": "object",
            "properties": {
                "market_events": {
                    "type": "object",
                    "properties": {
                        "enable_economic_cycles": {
                            "type": "boolean",
                            "default": True,
                            "description": "Enable economic boom/bust cycles"
                        },
                        "enable_market_events": {
                            "type": "boolean",
                            "default": True,
                            "description": "Enable random market events"
                        },
                        "enable_competitors": {
                            "type": "boolean",
                            "default": True,
                            "description": "Enable AI competitor companies"
                        },
                        "num_competitors": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 10,
                            "default": 5,
                            "description": "Number of AI competitors"
                        },
                        "event_probability_multiplier": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 3.0,
                            "default": 1.0,
                            "description": "Multiplier for event probability"
                        }
                    }
                }
            }
        }
    
    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate plugin configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        market_config = config.get("market_events", {})
        
        num_competitors = market_config.get("num_competitors", 5)
        if not 0 <= num_competitors <= 10:
            errors.append("num_competitors must be between 0 and 10")
        
        multiplier = market_config.get("event_probability_multiplier", 1.0)
        if not 0.0 <= multiplier <= 3.0:
            errors.append("event_probability_multiplier must be between 0.0 and 3.0")
        
        return errors 