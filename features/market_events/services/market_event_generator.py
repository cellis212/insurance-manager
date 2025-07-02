"""Market event generation for industry-wide impacts.

Generates various market events that affect all companies:
- Regulatory changes
- Technology disruptions  
- Demographic shifts
- Geopolitical events
- Industry scandals
"""

import random
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import GameEvent, State, LineOfBusiness, Turn


class MarketEventType(Enum):
    """Types of market-wide events."""
    REGULATORY_CHANGE = "regulatory_change"
    TECHNOLOGY_DISRUPTION = "technology_disruption"
    DEMOGRAPHIC_SHIFT = "demographic_shift"
    GEOPOLITICAL_EVENT = "geopolitical_event"
    INDUSTRY_SCANDAL = "industry_scandal"
    CATASTROPHE = "catastrophe"
    PANDEMIC = "pandemic"
    CYBER_ATTACK = "cyber_attack"


@dataclass
class MarketEvent:
    """Represents a market event with its impacts."""
    event_type: MarketEventType
    name: str
    description: str
    duration_weeks: int
    severity: float  # 1.0 = normal, 3.0 = severe
    affected_states: Optional[Set[UUID]] = None  # None = all states
    affected_lines: Optional[Set[UUID]] = None   # None = all lines
    impacts: Dict[str, Decimal] = None
    
    def __post_init__(self):
        if self.impacts is None:
            self.impacts = {}


class MarketEventGenerator:
    """Generates and manages market-wide events.
    
    Events can be:
    - Scheduled (known in advance, like regulatory changes)
    - Random (catastrophes, scandals)
    - Triggered (by economic conditions or company actions)
    """
    
    # Event templates with realistic impacts
    EVENT_TEMPLATES = {
        MarketEventType.REGULATORY_CHANGE: [
            {
                "name": "Federal Privacy Regulations",
                "description": "New federal data privacy laws require significant compliance investment",
                "duration_weeks": 12,
                "severity": 2.0,
                "impacts": {
                    "compliance_cost_multiplier": Decimal("1.3"),
                    "operational_expense_increase": Decimal("0.05"),
                    "barrier_to_entry": Decimal("1.2")
                }
            },
            {
                "name": "State Deregulation Wave",
                "description": "Multiple states ease insurance regulations to attract business",
                "duration_weeks": 24,
                "severity": 1.5,
                "impacts": {
                    "price_competition_increase": Decimal("1.2"),
                    "compliance_cost_multiplier": Decimal("0.8"),
                    "new_entrant_probability": Decimal("1.5")
                }
            }
        ],
        MarketEventType.TECHNOLOGY_DISRUPTION: [
            {
                "name": "AI Underwriting Revolution",
                "description": "New AI tools dramatically improve risk assessment accuracy",
                "duration_weeks": 52,
                "severity": 2.5,
                "impacts": {
                    "underwriting_accuracy_bonus": Decimal("0.2"),
                    "tech_investment_requirement": Decimal("500000"),
                    "early_adopter_advantage": Decimal("1.3")
                }
            },
            {
                "name": "Blockchain Claims Processing",
                "description": "Industry adopts blockchain for faster, cheaper claims",
                "duration_weeks": 36,
                "severity": 2.0,
                "impacts": {
                    "claims_processing_cost": Decimal("0.7"),
                    "customer_satisfaction_bonus": Decimal("1.1"),
                    "implementation_cost": Decimal("300000")
                }
            }
        ],
        MarketEventType.DEMOGRAPHIC_SHIFT: [
            {
                "name": "Millennial Insurance Boom",
                "description": "Millennials entering prime insurance-buying years",
                "duration_weeks": 104,  # 2 years
                "severity": 1.5,
                "impacts": {
                    "demand_growth_rate": Decimal("0.03"),
                    "digital_channel_importance": Decimal("1.5"),
                    "price_sensitivity_increase": Decimal("1.2")
                }
            },
            {
                "name": "Rural Population Decline",
                "description": "Accelerating rural depopulation affects market dynamics",
                "duration_weeks": 156,  # 3 years
                "severity": 1.8,
                "impacts": {
                    "rural_demand_decrease": Decimal("0.95"),
                    "urban_competition_increase": Decimal("1.1"),
                    "distribution_cost_rural": Decimal("1.3")
                }
            }
        ],
        MarketEventType.CATASTROPHE: [
            {
                "name": "Major Hurricane",
                "description": "Category 5 hurricane hits multiple coastal states",
                "duration_weeks": 4,
                "severity": 3.0,
                "impacts": {
                    "claims_surge_multiplier": Decimal("5.0"),
                    "reinsurance_cost_increase": Decimal("1.4"),
                    "capital_strain": Decimal("0.2")
                }
            },
            {
                "name": "Midwest Tornado Outbreak",
                "description": "Historic tornado outbreak across multiple states",
                "duration_weeks": 2,
                "severity": 2.5,
                "impacts": {
                    "claims_surge_multiplier": Decimal("3.0"),
                    "operational_strain": Decimal("1.3"),
                    "competitor_capacity_reduction": Decimal("0.9")
                }
            }
        ],
        MarketEventType.PANDEMIC: [
            {
                "name": "Global Health Crisis",
                "description": "Pandemic affects mortality and business interruption claims",
                "duration_weeks": 52,
                "severity": 3.0,
                "impacts": {
                    "life_claims_increase": Decimal("2.0"),
                    "business_interruption_claims": Decimal("3.0"),
                    "operational_disruption": Decimal("0.8"),
                    "investment_volatility": Decimal("1.5")
                }
            }
        ]
    }
    
    def __init__(self, session: AsyncSession):
        """Initialize the market event generator.
        
        Args:
            session: Database session
        """
        self.session = session
        self._active_events: List[MarketEvent] = []
        self._event_history: List[Dict] = []
    
    async def check_for_events(
        self,
        turn: Turn,
        economic_phase: str,
        company_actions: Dict[str, Any]
    ) -> List[MarketEvent]:
        """Check if any new market events should occur this turn.
        
        Args:
            turn: Current turn
            economic_phase: Current economic cycle phase
            company_actions: Recent company actions that might trigger events
            
        Returns:
            List of new events starting this turn
        """
        new_events = []
        
        # Random event probability varies by economic phase
        base_probability = {
            "expansion": 0.05,      # 5% in good times
            "peak": 0.08,          # 8% at peak (instability)
            "contraction": 0.12,   # 12% in bad times
            "trough": 0.10,        # 10% at bottom
            "recovery": 0.06       # 6% during recovery
        }.get(economic_phase, 0.08)
        
        # Check for random events
        if random.random() < base_probability:
            event_type = self._select_event_type(economic_phase)
            event = await self._generate_event(event_type, turn)
            if event:
                new_events.append(event)
        
        # Check for triggered events (e.g., multiple bankruptcies trigger scandal)
        triggered = await self._check_triggered_events(company_actions)
        new_events.extend(triggered)
        
        # Add to active events
        self._active_events.extend(new_events)
        
        # Record events in database
        for event in new_events:
            await self._record_event(event, turn)
        
        return new_events
    
    async def update_active_events(self, turn: Turn) -> List[MarketEvent]:
        """Update active events, removing expired ones.
        
        Args:
            turn: Current turn
            
        Returns:
            List of currently active events
        """
        # Decrement duration and remove expired events
        still_active = []
        for event in self._active_events:
            event.duration_weeks -= 1
            if event.duration_weeks > 0:
                still_active.append(event)
            else:
                # Event ended
                await self._record_event_end(event, turn)
        
        self._active_events = still_active
        return self._active_events
    
    def get_combined_impacts(self) -> Dict[str, Decimal]:
        """Get combined impacts from all active events.
        
        Returns:
            Dictionary of combined impact multipliers
        """
        combined = {}
        
        for event in self._active_events:
            for impact_type, value in event.impacts.items():
                if impact_type in combined:
                    # Multiply impacts (compound effects)
                    combined[impact_type] *= value
                else:
                    combined[impact_type] = value
        
        return combined
    
    def _select_event_type(self, economic_phase: str) -> MarketEventType:
        """Select event type based on current conditions.
        
        Args:
            economic_phase: Current economic phase
            
        Returns:
            Selected event type
        """
        # Weight event types by economic phase
        weights = {
            "expansion": {
                MarketEventType.REGULATORY_CHANGE: 0.3,
                MarketEventType.TECHNOLOGY_DISRUPTION: 0.3,
                MarketEventType.DEMOGRAPHIC_SHIFT: 0.2,
                MarketEventType.CATASTROPHE: 0.15,
                MarketEventType.INDUSTRY_SCANDAL: 0.05
            },
            "contraction": {
                MarketEventType.REGULATORY_CHANGE: 0.2,
                MarketEventType.TECHNOLOGY_DISRUPTION: 0.1,
                MarketEventType.DEMOGRAPHIC_SHIFT: 0.1,
                MarketEventType.CATASTROPHE: 0.3,
                MarketEventType.INDUSTRY_SCANDAL: 0.3
            }
        }
        
        phase_weights = weights.get(
            economic_phase,
            {t: 1.0 / len(MarketEventType) for t in MarketEventType}
        )
        
        # Exclude pandemic unless very rare conditions
        if random.random() > 0.02:  # 2% chance
            phase_weights.pop(MarketEventType.PANDEMIC, None)
        
        # Random weighted selection
        event_types = list(phase_weights.keys())
        probabilities = list(phase_weights.values())
        
        return random.choices(event_types, weights=probabilities)[0]
    
    async def _generate_event(
        self,
        event_type: MarketEventType,
        turn: Turn
    ) -> Optional[MarketEvent]:
        """Generate a specific type of event.
        
        Args:
            event_type: Type of event to generate
            turn: Current turn
            
        Returns:
            Generated event or None
        """
        templates = self.EVENT_TEMPLATES.get(event_type, [])
        if not templates:
            return None
        
        # Select random template
        template = random.choice(templates)
        
        # Create event from template
        event = MarketEvent(
            event_type=event_type,
            name=template["name"],
            description=template["description"],
            duration_weeks=template["duration_weeks"],
            severity=template["severity"],
            impacts=template["impacts"].copy()
        )
        
        # For catastrophes, select affected states
        if event_type == MarketEventType.CATASTROPHE:
            event.affected_states = await self._select_affected_states(
                event.name, turn.semester_id
            )
        
        return event
    
    async def _select_affected_states(
        self,
        event_name: str,
        semester_id: UUID
    ) -> Set[UUID]:
        """Select states affected by a catastrophe.
        
        Args:
            event_name: Name of the event
            semester_id: Current semester
            
        Returns:
            Set of affected state IDs
        """
        # Get all states
        result = await self.session.execute(select(State))
        all_states = {s.id: s for s in result.scalars().all()}
        
        # Select based on event type and geography
        if "hurricane" in event_name.lower():
            # Coastal states
            coastal_codes = ["FL", "TX", "LA", "MS", "AL", "GA", "SC", "NC", "VA"]
            affected = {
                state_id for state_id, state in all_states.items()
                if state.code in coastal_codes
            }
        elif "tornado" in event_name.lower():
            # Midwest states
            midwest_codes = ["OK", "KS", "NE", "IA", "MO", "IL", "IN", "OH"]
            affected = {
                state_id for state_id, state in all_states.items()
                if state.code in midwest_codes
            }
        else:
            # Random selection
            num_affected = random.randint(3, 8)
            affected = set(random.sample(list(all_states.keys()), num_affected))
        
        return affected
    
    async def _check_triggered_events(
        self,
        company_actions: Dict[str, Any]
    ) -> List[MarketEvent]:
        """Check if company actions trigger any events.
        
        Args:
            company_actions: Recent company actions
            
        Returns:
            List of triggered events
        """
        triggered = []
        
        # Example: Multiple bankruptcies trigger industry scandal
        bankruptcies = company_actions.get("bankruptcies_this_turn", 0)
        if bankruptcies >= 3 and random.random() < 0.5:
            scandal = MarketEvent(
                event_type=MarketEventType.INDUSTRY_SCANDAL,
                name="Insurance Industry Crisis",
                description=f"{bankruptcies} companies failed, triggering regulatory scrutiny",
                duration_weeks=8,
                severity=2.5,
                impacts={
                    "regulatory_scrutiny": Decimal("2.0"),
                    "consumer_confidence_loss": Decimal("0.8"),
                    "audit_probability_increase": Decimal("1.5")
                }
            )
            triggered.append(scandal)
        
        return triggered
    
    async def _record_event(self, event: MarketEvent, turn: Turn) -> None:
        """Record market event in database.
        
        Args:
            event: Event to record
            turn: Current turn
        """
        game_event = GameEvent(
            semester_id=turn.semester_id,
            turn_id=turn.id,
            event_type="market_event_start",
            category="market",
            severity="warning" if event.severity >= 2.0 else "info",
            description=f"{event.name}: {event.description}",
            event_data={
                "event_type": event.event_type.value,
                "name": event.name,
                "duration_weeks": event.duration_weeks,
                "severity": float(event.severity),
                "impacts": {k: str(v) for k, v in event.impacts.items()},
                "affected_states": [str(s) for s in event.affected_states] if event.affected_states else None
            }
        )
        self.session.add(game_event)
        await self.session.commit()
    
    async def _record_event_end(self, event: MarketEvent, turn: Turn) -> None:
        """Record end of market event.
        
        Args:
            event: Event that ended
            turn: Current turn
        """
        game_event = GameEvent(
            semester_id=turn.semester_id,
            turn_id=turn.id,
            event_type="market_event_end",
            category="market",
            severity="info",
            description=f"{event.name} has ended",
            event_data={
                "event_type": event.event_type.value,
                "name": event.name
            }
        )
        self.session.add(game_event)
        await self.session.commit() 