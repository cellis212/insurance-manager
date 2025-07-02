"""Economic cycle management for market events.

Manages boom/bust cycles with realistic transitions and momentum.
Economic cycles affect:
- Base demand levels
- Investment returns
- Consumer confidence
- Price elasticity
- Claim frequency
"""

import random
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import MarketCondition, Semester, Turn, GameEvent


class EconomicPhase(Enum):
    """Economic cycle phases with natural progression."""
    EXPANSION = "expansion"      # Growing economy, increasing demand
    PEAK = "peak"               # Top of cycle, high demand but slowing
    CONTRACTION = "contraction"  # Declining economy, falling demand
    TROUGH = "trough"           # Bottom of cycle, low demand but stabilizing
    RECOVERY = "recovery"       # Early growth, improving conditions


class EconomicCycleManager:
    """Manages economic cycles with realistic transitions and momentum.
    
    Key principles:
    - Cycles have momentum - phases don't change instantly
    - Each phase has a minimum duration (except peak/trough which are transition points)
    - Random variations within phases create realistic fluctuations
    - Industry-wide effects impact all companies equally
    """
    
    # Phase transition probabilities (per turn)
    PHASE_TRANSITIONS = {
        EconomicPhase.EXPANSION: {
            EconomicPhase.PEAK: 0.15,  # 15% chance to peak each turn
            EconomicPhase.EXPANSION: 0.85  # 85% chance to continue
        },
        EconomicPhase.PEAK: {
            EconomicPhase.CONTRACTION: 0.80,  # Peak is usually brief
            EconomicPhase.PEAK: 0.20
        },
        EconomicPhase.CONTRACTION: {
            EconomicPhase.TROUGH: 0.20,
            EconomicPhase.CONTRACTION: 0.80
        },
        EconomicPhase.TROUGH: {
            EconomicPhase.RECOVERY: 0.70,  # Trough is also brief
            EconomicPhase.TROUGH: 0.30
        },
        EconomicPhase.RECOVERY: {
            EconomicPhase.EXPANSION: 0.25,
            EconomicPhase.RECOVERY: 0.75
        }
    }
    
    # Economic impacts by phase
    PHASE_IMPACTS = {
        EconomicPhase.EXPANSION: {
            "demand_multiplier": Decimal("1.15"),      # +15% base demand
            "investment_return_bonus": Decimal("0.02"), # +2% returns
            "price_elasticity_modifier": Decimal("0.9"), # Less price sensitive
            "consumer_confidence": Decimal("1.1"),
            "claim_frequency_modifier": Decimal("0.95")  # Fewer claims in good times
        },
        EconomicPhase.PEAK: {
            "demand_multiplier": Decimal("1.20"),
            "investment_return_bonus": Decimal("0.01"),
            "price_elasticity_modifier": Decimal("0.95"),
            "consumer_confidence": Decimal("1.05"),
            "claim_frequency_modifier": Decimal("1.0")
        },
        EconomicPhase.CONTRACTION: {
            "demand_multiplier": Decimal("0.85"),
            "investment_return_bonus": Decimal("-0.03"),
            "price_elasticity_modifier": Decimal("1.2"),  # More price sensitive
            "consumer_confidence": Decimal("0.8"),
            "claim_frequency_modifier": Decimal("1.1")
        },
        EconomicPhase.TROUGH: {
            "demand_multiplier": Decimal("0.80"),
            "investment_return_bonus": Decimal("-0.02"),
            "price_elasticity_modifier": Decimal("1.3"),
            "consumer_confidence": Decimal("0.75"),
            "claim_frequency_modifier": Decimal("1.15")
        },
        EconomicPhase.RECOVERY: {
            "demand_multiplier": Decimal("0.95"),
            "investment_return_bonus": Decimal("0.0"),
            "price_elasticity_modifier": Decimal("1.05"),
            "consumer_confidence": Decimal("0.9"),
            "claim_frequency_modifier": Decimal("1.05")
        }
    }
    
    def __init__(self, session: AsyncSession):
        """Initialize the economic cycle manager.
        
        Args:
            session: Database session
        """
        self.session = session
        self._current_phase: Optional[EconomicPhase] = None
        self._phase_duration: int = 0
        self._minimum_phase_duration = {
            EconomicPhase.EXPANSION: 8,     # At least 8 weeks
            EconomicPhase.PEAK: 1,          # Can be brief
            EconomicPhase.CONTRACTION: 6,   # At least 6 weeks
            EconomicPhase.TROUGH: 1,        # Can be brief
            EconomicPhase.RECOVERY: 4      # At least 4 weeks
        }
    
    async def initialize_cycle(self, semester: Semester) -> EconomicPhase:
        """Initialize economic cycle for a new semester.
        
        Args:
            semester: Semester to initialize cycle for
            
        Returns:
            Starting economic phase
        """
        # Start in a random non-extreme phase
        start_phases = [
            EconomicPhase.EXPANSION,
            EconomicPhase.RECOVERY,
            EconomicPhase.CONTRACTION
        ]
        self._current_phase = random.choice(start_phases)
        self._phase_duration = 0
        
        # Store initial state in semester config
        config = semester.configuration.parameters
        config["economic_cycle"] = {
            "current_phase": self._current_phase.value,
            "phase_duration": 0,
            "history": []
        }
        
        await self.session.commit()
        
        return self._current_phase
    
    async def advance_cycle(self, turn: Turn) -> Tuple[EconomicPhase, Dict[str, Decimal]]:
        """Advance the economic cycle for the current turn.
        
        Args:
            turn: Current turn
            
        Returns:
            Tuple of (new phase, phase impacts)
        """
        # Load current state from semester config
        semester = await self.session.get(Semester, turn.semester_id)
        cycle_state = semester.configuration.parameters.get("economic_cycle", {})
        
        if not cycle_state:
            # Initialize if not set
            self._current_phase = await self.initialize_cycle(semester)
        else:
            self._current_phase = EconomicPhase(cycle_state["current_phase"])
            self._phase_duration = cycle_state["phase_duration"]
        
        # Increment phase duration
        self._phase_duration += 1
        
        # Check for phase transition
        min_duration = self._minimum_phase_duration[self._current_phase]
        if self._phase_duration >= min_duration:
            # Can potentially transition
            transitions = self.PHASE_TRANSITIONS[self._current_phase]
            roll = random.random()
            
            cumulative_prob = 0.0
            for next_phase, prob in transitions.items():
                cumulative_prob += prob
                if roll < cumulative_prob:
                    if next_phase != self._current_phase:
                        # Phase change!
                        await self._record_phase_change(
                            turn, self._current_phase, next_phase
                        )
                        self._current_phase = next_phase
                        self._phase_duration = 0
                    break
        
        # Get impacts with some random variation
        base_impacts = self.PHASE_IMPACTS[self._current_phase].copy()
        impacts = {}
        for key, value in base_impacts.items():
            # Add ±5% random variation
            variation = Decimal(random.uniform(0.95, 1.05))
            impacts[key] = value * variation
        
        # Update semester config
        cycle_state["current_phase"] = self._current_phase.value
        cycle_state["phase_duration"] = self._phase_duration
        cycle_state["history"].append({
            "turn": turn.week_number,
            "phase": self._current_phase.value,
            "impacts": {k: str(v) for k, v in impacts.items()}
        })
        semester.configuration.parameters["economic_cycle"] = cycle_state
        
        await self.session.commit()
        
        return self._current_phase, impacts
    
    async def apply_cycle_to_market_conditions(
        self,
        turn: Turn,
        impacts: Dict[str, Decimal]
    ) -> None:
        """Apply economic cycle impacts to all market conditions.
        
        Args:
            turn: Current turn
            impacts: Economic impacts to apply
        """
        # Get all market conditions for this turn
        result = await self.session.execute(
            select(MarketCondition).where(
                MarketCondition.semester_id == turn.semester_id,
                MarketCondition.turn_number == turn.week_number
            )
        )
        conditions = result.scalars().all()
        
        for condition in conditions:
            # Apply demand multiplier
            condition.base_demand *= impacts["demand_multiplier"]
            
            # Adjust price elasticity (more negative = more elastic)
            condition.price_elasticity *= impacts["price_elasticity_modifier"]
            
            # Store additional impacts in market_data
            condition.market_data.update({
                "economic_phase": self._current_phase.value,
                "consumer_confidence": float(impacts["consumer_confidence"]),
                "investment_return_bonus": float(impacts["investment_return_bonus"]),
                "claim_frequency_modifier": float(impacts["claim_frequency_modifier"])
            })
        
        await self.session.commit()
    
    async def _record_phase_change(
        self,
        turn: Turn,
        old_phase: EconomicPhase,
        new_phase: EconomicPhase
    ) -> None:
        """Record economic phase change as a game event.
        
        Args:
            turn: Current turn
            old_phase: Previous economic phase
            new_phase: New economic phase
        """
        event = GameEvent(
            semester_id=turn.semester_id,
            turn_id=turn.id,
            event_type="economic_cycle_change",
            category="market",
            severity="info",
            description=f"Economic cycle shifted from {old_phase.value} to {new_phase.value}",
            event_data={
                "old_phase": old_phase.value,
                "new_phase": new_phase.value,
                "turn_number": turn.week_number,
                "phase_duration": self._phase_duration
            }
        )
        self.session.add(event)
    
    def get_ceo_insight_multiplier(self, ceo_market_acumen: int) -> Decimal:
        """Get multiplier for CEO's ability to predict economic changes.
        
        CEOs with high market acumen can better anticipate economic shifts.
        
        Args:
            ceo_market_acumen: CEO's market acumen attribute (0-100)
            
        Returns:
            Multiplier for advance warning (1.0 = no advantage)
        """
        # Expert CEOs (80+) get up to 2 turns advance warning
        if ceo_market_acumen >= 80:
            return Decimal("2.0")
        elif ceo_market_acumen >= 60:
            return Decimal("1.5")
        elif ceo_market_acumen >= 40:
            return Decimal("1.2")
        else:
            return Decimal("1.0")  # No advance insight
    
    def predict_next_phase(self, current_phase: EconomicPhase) -> Dict[EconomicPhase, float]:
        """Predict probability of next phase transitions.
        
        Used by CEOs with high market acumen to anticipate changes.
        
        Args:
            current_phase: Current economic phase
            
        Returns:
            Dictionary of phase -> probability
        """
        return self.PHASE_TRANSITIONS[current_phase].copy() 