"""Liquidation event model for tracking forced asset sales.

Records when companies must liquidate investments due to catastrophes,
operational losses, or other liquidity needs. CFO skill affects which
assets are liquidated and the resulting market impact.
"""

from __future__ import annotations
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as SQL_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.company import Company
    from core.models.turn import Turn


class LiquidationEvent(BaseModel):
    """Forced asset liquidation events.
    
    When companies face liquidity crises (catastrophe losses, large claims,
    regulatory fines), they must liquidate investments. The CFO's skill
    determines which assets are sold and at what discount.
    """
    
    __tablename__ = "liquidation_events"
    
    # Foreign keys
    company_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Company forced to liquidate assets"
    )
    
    turn_id: Mapped[UUID] = mapped_column(
        SQL_UUID(as_uuid=True),
        ForeignKey("turns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Turn when liquidation occurred"
    )
    
    # Liquidation details
    trigger_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="What triggered liquidation: catastrophe, operational_loss, regulatory_fine, capital_call"
    )
    
    required_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Amount of cash needed"
    )
    
    # Asset liquidation details
    assets_liquidated: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="List of assets sold: [{asset_class, amount, discount_applied, liquidity_score}]"
    )
    
    # Market impact
    market_impact: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Additional discount due to market conditions (0.05 = 5%)"
    )
    
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Total cost of liquidation including all discounts"
    )
    
    # CFO skill impact
    cfo_skill_at_time: Mapped[int] = mapped_column(
        Numeric(3, 0),
        nullable=True,
        comment="CFO skill level when liquidation occurred (0-100)"
    )
    
    # Additional context
    liquidation_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Additional details: {time_pressure, alternative_sources_tried, regulatory_involvement}"
    )
    
    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="liquidation_events"
    )
    
    turn: Mapped["Turn"] = relationship(
        "Turn",
        back_populates="liquidation_events"
    )
    
    def __repr__(self) -> str:
        """String representation of the liquidation event."""
        return f"<LiquidationEvent(company={self.company_id}, trigger={self.trigger_type}, amount={self.required_amount})>"
    
    @property
    def liquidation_efficiency(self) -> Decimal:
        """Calculate how efficiently assets were liquidated.
        
        Returns:
            Efficiency ratio (1.0 = no loss, 0.8 = 20% loss)
        """
        if self.required_amount <= 0:
            return Decimal("1.00")
            
        return self.required_amount / self.total_cost
    
    @property
    def average_discount(self) -> Decimal:
        """Calculate average discount across all liquidated assets.
        
        Returns:
            Average discount applied (0.10 = 10% haircut)
        """
        total_discount = Decimal("0.00")
        total_amount = Decimal("0.00")
        
        for asset in self.assets_liquidated:
            if isinstance(asset, dict):
                amount = Decimal(str(asset.get('amount', 0)))
                discount = Decimal(str(asset.get('discount_applied', 0)))
                total_discount += amount * discount
                total_amount += amount
        
        if total_amount <= 0:
            return Decimal("0.00")
            
        return total_discount / total_amount
    
    def was_catastrophe_driven(self) -> bool:
        """Check if liquidation was due to catastrophe.
        
        Returns:
            Whether trigger was catastrophe-related
        """
        return self.trigger_type == 'catastrophe'
    
    def get_liquidity_quality_score(self) -> int:
        """Calculate quality of liquidated assets.
        
        Higher score = more liquid assets were sold (better CFO)
        
        Returns:
            Average liquidity score of sold assets (0-100)
        """
        total_score = 0
        asset_count = 0
        
        for asset in self.assets_liquidated:
            if isinstance(asset, dict) and 'liquidity_score' in asset:
                total_score += asset['liquidity_score']
                asset_count += 1
        
        if asset_count == 0:
            return 50  # Default middle score
            
        return total_score // asset_count
    
    def calculate_skill_impact(self) -> Decimal:
        """Calculate how much CFO skill affected the outcome.
        
        Returns:
            Additional cost due to low skill (positive = extra cost)
        """
        if not self.cfo_skill_at_time:
            return Decimal("0.00")
            
        # Perfect skill (100) = no extra cost
        # Poor skill (0) = up to 20% extra cost
        skill_penalty = (100 - self.cfo_skill_at_time) / 500  # 0-20%
        
        return self.required_amount * Decimal(str(skill_penalty)) 