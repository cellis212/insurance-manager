"""Product model for insurance products offered by companies.

Implements the three-tier product system (Basic/Standard/Premium)
where each tier affects pricing and risk selection differently.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.company import Company
    from core.models.state import State
    from core.models.line_of_business import LineOfBusiness


class Product(BaseModel):
    """Insurance product with tier-based pricing and risk selection.
    
    Companies can offer one tier per line of business per state.
    Each tier has different premium levels and attracts different
    risk pools through adverse selection.
    """
    
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "state_id", "line_of_business_id",
            name="uq_one_product_per_company_state_line"
        ),
    )
    
    # Foreign keys
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Company offering this product"
    )
    
    state_id = Column(
        UUID(as_uuid=True),
        ForeignKey("states.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="State where product is offered"
    )
    
    line_of_business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lines_of_business.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Line of business for this product"
    )
    
    # Product configuration
    tier = Column(
        String(20),
        nullable=False,
        default="Standard",
        comment="Product tier: 'Basic', 'Standard', or 'Premium'"
    )
    
    # Pricing characteristics
    base_premium = Column(
        Numeric(12, 2),
        nullable=False,
        comment="Base annual premium before tier adjustments"
    )
    
    deductible = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Deductible amount for claims"
    )
    
    coverage_limit = Column(
        Numeric(12, 2),
        nullable=False,
        comment="Maximum coverage amount per claim"
    )
    
    # Market performance
    active_policies = Column(
        Numeric(10, 0),
        nullable=False,
        default=0,
        comment="Number of active policies for this product"
    )
    
    market_share = Column(
        Numeric(5, 4),
        nullable=True,
        comment="Market share in this state/line (0.1234 = 12.34%)"
    )
    
    # Risk selection effects
    selection_effect = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Risk selection multiplier from tier choice"
    )
    
    # Custom configuration for future features
    custom_config = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Extensible configuration for future product features"
    )
    
    # Schema versioning for JSONB migration
    schema_version = Column(
        Numeric(3, 0),
        nullable=False,
        default=1,
        comment="Schema version for custom_config field"
    )
    
    # Relationships
    company = relationship(
        "Company",
        back_populates="products"
    )
    
    state = relationship(
        "State",
        back_populates="products"
    )
    
    line_of_business = relationship(
        "LineOfBusiness",
        back_populates="products"
    )
    
    def __repr__(self) -> str:
        """String representation of the product."""
        return f"<Product(tier={self.tier}, company_id={self.company_id})>"
    
    def __init__(self, **kwargs):
        """Initialize product with tier-specific characteristics."""
        super().__init__(**kwargs)
        self._apply_tier_effects()
    
    def _apply_tier_effects(self) -> None:
        """Apply tier-specific pricing and selection effects."""
        if self.tier == "Basic":
            # 20% cheaper, attracts 30% worse risks
            self.selection_effect = Decimal("0.30")
            if self.base_premium:
                self.base_premium *= Decimal("0.80")
        elif self.tier == "Premium":
            # 30% more expensive, attracts 10% better risks
            self.selection_effect = Decimal("-0.10")
            if self.base_premium:
                self.base_premium *= Decimal("1.30")
        else:
            # Standard tier - baseline
            self.selection_effect = Decimal("0.00")
    
    @property
    def effective_loss_ratio(self) -> Decimal:
        """Calculate effective loss ratio including selection effects.
        
        Returns:
            Expected loss ratio adjusted for tier selection
        """
        base_loss_ratio = Decimal("0.67")  # Standard baseline
        return base_loss_ratio * (Decimal("1") + self.selection_effect)
    
    @property
    def price_elasticity_factor(self) -> Decimal:
        """Get demand elasticity factor based on tier.
        
        Returns:
            Price elasticity multiplier for demand calculations
        """
        elasticity_map = {
            "Basic": Decimal("1.5"),    # High price sensitivity
            "Standard": Decimal("1.0"),  # Normal elasticity
            "Premium": Decimal("0.6")    # Low price sensitivity
        }
        return elasticity_map.get(self.tier, Decimal("1.0"))
    
    @property
    def tier_display_name(self) -> str:
        """Get display name for the product tier.
        
        Returns:
            Human-friendly tier name
        """
        return f"{self.tier} Tier"
    
    @property
    def requires_tier_change_notice(self) -> bool:
        """Check if changing this product tier requires customer notice.
        
        Returns:
            Whether 4-week notice is required
        """
        # Always require notice if product has active policies
        return self.active_policies > 0
    
    def get_custom_feature(self, feature_key: str, default: any = None) -> any:
        """Get a custom configuration value.
        
        Args:
            feature_key: The configuration key to retrieve
            default: Default value if not set
            
        Returns:
            The configuration value or default
        """
        return self.custom_config.get(feature_key, default)
    
    def set_custom_feature(self, feature_key: str, value: any) -> None:
        """Set a custom configuration value.
        
        Args:
            feature_key: The configuration key to set
            value: The value to store
        """
        if self.custom_config is None:
            self.custom_config = {}
        self.custom_config[feature_key] = value 