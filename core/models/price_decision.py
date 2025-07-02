"""Price decision model for tracking company pricing strategies.

Records pricing decisions made by companies for each state/line
combination per turn, used in demand simulation calculations.
"""

from __future__ import annotations
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as SQL_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.company import Company
    from core.models.turn import Turn
    from core.models.state import State
    from core.models.line_of_business import LineOfBusiness


class PriceDecision(BaseModel):
    """Company pricing decisions for market simulation.
    
    Tracks the pricing strategy for each company/state/line combination
    per turn. Used in conjunction with market conditions to calculate
    demand and market share.
    """
    
    __tablename__ = "price_decisions"
    
    # Foreign keys
    company_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Company making this pricing decision"
    )
    
    turn_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("turns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Turn this decision applies to"
    )
    
    state_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("states.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="State this pricing applies to"
    )
    
    line_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("lines_of_business.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Line of business this pricing applies to"
    )
    
    # Pricing parameters
    base_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Base premium price per policy"
    )
    
    price_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("1.00"),
        comment="Multiplier applied to base price (0.80 = 20% discount)"
    )
    
    expected_loss_ratio: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Expected loss ratio at this pricing level"
    )
    
    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="price_decisions"
    )
    
    turn: Mapped["Turn"] = relationship(
        "Turn",
        back_populates="price_decisions"
    )
    
    state: Mapped["State"] = relationship(
        "State",
        back_populates="price_decisions"
    )
    
    line_of_business: Mapped["LineOfBusiness"] = relationship(
        "LineOfBusiness",
        back_populates="price_decisions"
    )
    
    # Unique constraint - one price per company/turn/state/line
    __table_args__ = (
        UniqueConstraint(
            'company_id', 'turn_id', 'state_id', 'line_id',
            name='uix_price_decision_unique'
        ),
    )
    
    def __repr__(self) -> str:
        """String representation of the price decision."""
        return f"<PriceDecision(company={self.company_id}, turn={self.turn_id}, price={self.effective_price})>"
    
    @property
    def effective_price(self) -> Decimal:
        """Calculate the effective price after multiplier.
        
        Returns:
            Final price = base_price * price_multiplier
        """
        return self.base_price * self.price_multiplier
    
    @property
    def is_competitive(self) -> bool:
        """Check if pricing is below market average.
        
        Returns:
            Whether price multiplier indicates competitive pricing
        """
        return self.price_multiplier < Decimal("0.95")
    
    @property
    def is_premium(self) -> bool:
        """Check if pricing is above market average.
        
        Returns:
            Whether price multiplier indicates premium pricing
        """
        return self.price_multiplier > Decimal("1.05")
    
    def calculate_target_margin(self) -> Decimal:
        """Calculate target underwriting margin.
        
        Returns:
            Target margin = 1 - expected_loss_ratio - expense_ratio
        """
        # Assume standard expense ratio of 30%
        expense_ratio = Decimal("0.30")
        return Decimal("1.00") - self.expected_loss_ratio - expense_ratio 