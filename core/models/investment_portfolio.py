"""Investment portfolio model for asset management simulation.

Tracks investment portfolio characteristics and performance, including
the critical distinction between actual and perceived characteristics
based on CFO skill level.
"""

from __future__ import annotations
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID as SQL_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.company import Company
    from core.models.turn import Turn


class InvestmentPortfolio(BaseModel):
    """Company investment portfolio tracking.
    
    Stores both actual and perceived portfolio characteristics to model
    information asymmetry based on CFO skill. The five key characteristics
    are risk, duration, liquidity, credit quality, and diversification.
    """
    
    __tablename__ = "investment_portfolios"
    
    # Foreign keys
    company_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Company owning this portfolio"
    )
    
    turn_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("turns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Turn this portfolio snapshot is from"
    )
    
    # Portfolio value
    total_value: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Total portfolio value at turn end"
    )
    
    # Actual portfolio characteristics
    characteristics: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Actual portfolio characteristics: {risk: 0-100, duration: 0-20, liquidity: 0-100, credit: 0-100, diversification: 0-100}"
    )
    
    # Perceived characteristics (affected by CFO skill)
    perceived_characteristics: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="What the CFO perceives: noise added based on skill level"
    )
    
    # Returns
    actual_returns: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Actual investment returns this turn"
    )
    
    perceived_returns: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="What the CFO reports as returns"
    )
    
    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="investment_portfolios"
    )
    
    turn: Mapped["Turn"] = relationship(
        "Turn",
        back_populates="investment_portfolios"
    )
    
    def __repr__(self) -> str:
        """String representation of the portfolio."""
        return f"<InvestmentPortfolio(company={self.company_id}, turn={self.turn_id}, value={self.total_value})>"
    
    @property
    def risk_level(self) -> int:
        """Get actual portfolio risk level.
        
        Returns:
            Risk level 0-100
        """
        return self.characteristics.get('risk', 50)
    
    @property
    def perceived_risk_level(self) -> int:
        """Get perceived portfolio risk level.
        
        Returns:
            Perceived risk level 0-100
        """
        if not self.perceived_characteristics:
            return self.risk_level
        return self.perceived_characteristics.get('risk', self.risk_level)
    
    @property
    def liquidity_score(self) -> int:
        """Get actual portfolio liquidity.
        
        Returns:
            Liquidity score 0-100 (100 = most liquid)
        """
        return self.characteristics.get('liquidity', 50)
    
    @property
    def duration_years(self) -> float:
        """Get portfolio duration in years.
        
        Returns:
            Average duration of portfolio assets
        """
        return self.characteristics.get('duration', 5.0)
    
    def calculate_liquidation_discount(self, amount_needed: Decimal) -> Decimal:
        """Calculate discount for forced liquidation.
        
        Higher liquidity = lower discount
        Larger liquidation relative to portfolio = higher discount
        
        Args:
            amount_needed: Amount that needs to be liquidated
            
        Returns:
            Discount factor (0.95 = 5% haircut)
        """
        if self.total_value <= 0:
            return Decimal("0.00")
            
        # Base discount based on liquidity
        liquidity_discount = (100 - self.liquidity_score) / 1000  # 0-10% based on liquidity
        
        # Additional discount for large liquidations
        liquidation_percentage = amount_needed / self.total_value
        size_discount = min(liquidation_percentage * Decimal("0.05"), Decimal("0.10"))  # Up to 10% for full liquidation
        
        total_discount = Decimal(str(liquidity_discount)) + size_discount
        
        return Decimal("1.00") - total_discount
    
    def get_stress_test_impact(self, scenario: str) -> Decimal:
        """Calculate portfolio impact under stress scenario.
        
        Args:
            scenario: Type of stress test ('market_crash', 'interest_spike', 'credit_crisis')
            
        Returns:
            Expected portfolio value change (negative for losses)
        """
        risk = self.risk_level / 100
        duration = self.duration_years / 20
        credit = self.characteristics.get('credit', 50) / 100
        
        if scenario == 'market_crash':
            # Higher risk = larger losses
            return self.total_value * Decimal(str(-0.30 * risk))
        elif scenario == 'interest_spike':
            # Longer duration = larger losses
            return self.total_value * Decimal(str(-0.15 * duration))
        elif scenario == 'credit_crisis':
            # Lower credit quality = larger losses
            return self.total_value * Decimal(str(-0.20 * (1 - credit)))
        else:
            return Decimal("0.00") 