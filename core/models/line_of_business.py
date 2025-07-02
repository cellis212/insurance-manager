"""Line of business model for different insurance product types.

Represents different insurance lines like auto, home, commercial,
each with unique characteristics affecting claims and profitability.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Column, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.product import Product
    from core.models.company import CompanyLineOfBusiness


class LineOfBusiness(BaseModel):
    """Insurance line of business with unique risk characteristics.
    
    Each line has different claim frequencies, severities, and
    capital requirements that affect gameplay strategy.
    """
    
    __tablename__ = "lines_of_business"
    
    # Basic information
    code = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        comment="Short code for the line (e.g., 'AUTO', 'HOME')"
    )
    
    name = Column(
        String(100),
        nullable=False,
        comment="Full name of the line of business"
    )
    
    description = Column(
        String(500),
        nullable=True,
        comment="Description of what this line covers"
    )
    
    # Risk characteristics
    base_frequency = Column(
        Numeric(8, 4),
        nullable=False,
        default=Decimal("0.1000"),
        comment="Base claim frequency (claims per policy per year)"
    )
    
    base_severity = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("10000.00"),
        comment="Base claim severity (average claim amount)"
    )
    
    frequency_volatility = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.20"),
        comment="Volatility of claim frequency (coefficient of variation)"
    )
    
    severity_volatility = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.50"),
        comment="Volatility of claim severity (coefficient of variation)"
    )
    
    # Capital and regulatory
    capital_requirement_multiplier = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("1.00"),
        comment="Multiplier for capital requirements vs base"
    )
    
    regulatory_complexity = Column(
        String(20),
        nullable=False,
        default="medium",
        comment="Regulatory complexity: 'low', 'medium', or 'high'"
    )
    
    # Market characteristics
    market_characteristics = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Additional market data (competition, growth rate, etc.)"
    )
    
    # Catastrophe exposure
    catastrophe_exposed = Column(
        String(50),
        nullable=True,
        comment="Types of catastrophes this line is exposed to"
    )
    
    # Relationships
    products = relationship(
        "Product",
        back_populates="line_of_business",
        cascade="all, delete-orphan"
    )
    
    company_lines = relationship(
        "CompanyLineOfBusiness",
        back_populates="line_of_business",
        cascade="all, delete-orphan"
    )
    
    market_conditions = relationship(
        "MarketCondition",
        back_populates="line_of_business",
        cascade="all, delete-orphan"
    )
    
    price_decisions = relationship(
        "PriceDecision",
        back_populates="line_of_business",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        """String representation of the line of business."""
        return f"<LineOfBusiness(code={self.code}, name={self.name})>"
    
    @property
    def expected_loss_ratio(self) -> Decimal:
        """Calculate expected loss ratio based on frequency and severity.
        
        Returns:
            Expected loss ratio as a decimal
        """
        # Simplified calculation - would be more complex in reality
        expected_losses = self.base_frequency * self.base_severity
        # Assume average premium is 1.5x expected losses for profitability
        return Decimal("0.67")  # 67% loss ratio target
    
    @property
    def is_high_risk(self) -> bool:
        """Check if this is a high-risk line of business.
        
        Returns:
            Whether this line has high risk characteristics
        """
        return (
            self.base_frequency > Decimal("0.2000") or
            self.frequency_volatility > Decimal("0.30") or
            self.catastrophe_exposed is not None
        )
    
    @property
    def capital_intensity(self) -> str:
        """Get capital intensity level.
        
        Returns:
            Capital intensity: 'low', 'medium', or 'high'
        """
        if self.capital_requirement_multiplier >= Decimal("1.50"):
            return "high"
        elif self.capital_requirement_multiplier >= Decimal("1.00"):
            return "medium"
        else:
            return "low"
    
    def get_market_data(self, data_key: str, default: any = None) -> any:
        """Get specific market characteristic data.
        
        Args:
            data_key: The market data key to retrieve
            default: Default value if not set
            
        Returns:
            The market data value or default
        """
        return self.market_characteristics.get(data_key, default) 