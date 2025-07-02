"""Market condition model for demand simulation.

Stores market conditions by state/line/turn to calculate demand
based on price elasticity and competitive intensity.
"""

from __future__ import annotations
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as SQL_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.semester import Semester
    from core.models.state import State
    from core.models.line_of_business import LineOfBusiness


class MarketCondition(BaseModel):
    """Market conditions for demand simulation.
    
    Tracks base demand, price elasticity, and competitive intensity
    for each state/line combination per turn. Used in market simulation
    to calculate demand curves and market shares.
    """
    
    __tablename__ = "market_conditions"
    
    # Foreign keys
    semester_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("semesters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Semester these conditions belong to"
    )
    
    turn_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Turn number within the semester"
    )
    
    state_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("states.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="State these conditions apply to"
    )
    
    line_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("lines_of_business.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Line of business these conditions apply to"
    )
    
    # Market parameters
    base_demand: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Base market demand in premium dollars"
    )
    
    price_elasticity: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("-1.5"),
        comment="Price elasticity of demand (typically negative)"
    )
    
    competitive_intensity: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("1.0"),
        comment="Competition level affecting price sensitivity"
    )
    
    # Additional market data
    market_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Additional market factors: {growth_rate, seasonality, regulatory_changes, consumer_confidence}"
    )
    
    # Relationships
    semester: Mapped["Semester"] = relationship(
        "Semester",
        back_populates="market_conditions"
    )
    
    state: Mapped["State"] = relationship(
        "State",
        back_populates="market_conditions"
    )
    
    line_of_business: Mapped["LineOfBusiness"] = relationship(
        "LineOfBusiness",
        back_populates="market_conditions"
    )
    
    # Unique constraint - one condition set per state/line/turn
    __table_args__ = (
        UniqueConstraint(
            'semester_id', 'turn_number', 'state_id', 'line_id',
            name='uix_market_condition_unique'
        ),
    )
    
    def __repr__(self) -> str:
        """String representation of the market condition."""
        return f"<MarketCondition(turn={self.turn_number}, state={self.state_id}, line={self.line_id})>"
    
    def calculate_demand_at_price(self, price: Decimal) -> Decimal:
        """Calculate demand at a given price point.
        
        Uses constant elasticity demand function:
        Q = base_demand * (P/P_base)^elasticity
        
        Args:
            price: Price point to calculate demand for
            
        Returns:
            Expected demand at that price
        """
        if price <= 0:
            return Decimal("0")
            
        # Assume base price is normalized to 1.0
        price_ratio = price / Decimal("1.0")
        
        # Apply elasticity with competitive intensity modifier
        elasticity_adjusted = self.price_elasticity * self.competitive_intensity
        demand_multiplier = price_ratio ** elasticity_adjusted
        
        return self.base_demand * demand_multiplier
    
    def get_growth_rate(self) -> Decimal:
        """Get market growth rate from market data.
        
        Returns:
            Growth rate as decimal (0.05 = 5%)
        """
        return Decimal(str(self.market_data.get('growth_rate', 0.0)))
    
    def get_seasonality_factor(self) -> Decimal:
        """Get seasonality adjustment factor.
        
        Returns:
            Seasonality multiplier (1.0 = no effect)
        """
        return Decimal(str(self.market_data.get('seasonality', 1.0))) 