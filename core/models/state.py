"""State model representing US states with insurance regulatory information.

Stores state-specific regulatory categories, expansion costs, and
market characteristics for the insurance game.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, Column, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.company import Company
    from core.models.product import Product


class State(BaseModel):
    """US state with insurance regulatory and market information.
    
    Each state has different regulatory requirements, market sizes,
    and expansion costs that affect gameplay.
    """
    
    __tablename__ = "states"
    
    # Basic information
    code = Column(
        CHAR(2),
        unique=True,
        nullable=False,
        index=True,
        comment="Two-letter state code (e.g., 'NY', 'CA')"
    )
    
    name = Column(
        String(100),
        nullable=False,
        comment="Full state name (e.g., 'New York', 'California')"
    )
    
    # Regulatory information
    regulatory_category = Column(
        String(20),
        nullable=False,
        comment="Regulatory strictness: 'strict', 'moderate', or 'light'"
    )
    
    # Market characteristics
    base_expansion_cost = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("1000000.00"),
        comment="Base cost to expand into this state"
    )
    
    market_size_multiplier = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("1.00"),
        comment="Multiplier for market size relative to baseline"
    )
    
    population = Column(
        Numeric(12, 0),
        nullable=True,
        comment="State population for market sizing"
    )
    
    # Additional requirements and data
    additional_requirements = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="State-specific requirements and regulations"
    )
    
    market_data = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Additional market characteristics and statistics"
    )
    
    # Geographic information
    region = Column(
        String(50),
        nullable=True,
        comment="Geographic region (e.g., 'Northeast', 'Southwest')"
    )
    
    timezone = Column(
        String(50),
        nullable=True,
        default="America/New_York",
        comment="Primary timezone for the state"
    )
    
    # Relationships
    companies_home_state = relationship(
        "Company",
        foreign_keys="Company.home_state_id",
        back_populates="home_state"
    )
    
    company_authorizations = relationship(
        "CompanyStateAuthorization",
        back_populates="state",
        cascade="all, delete-orphan"
    )
    
    products = relationship(
        "Product",
        back_populates="state",
        cascade="all, delete-orphan"
    )
    
    market_conditions = relationship(
        "MarketCondition",
        back_populates="state",
        cascade="all, delete-orphan"
    )
    
    price_decisions = relationship(
        "PriceDecision",
        back_populates="state",
        cascade="all, delete-orphan"
    )
    
    universities = relationship(
        "University",
        back_populates="state",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        """String representation of the state."""
        return f"<State(code={self.code}, name={self.name})>"
    
    @property
    def is_strict_regulatory(self) -> bool:
        """Check if this is a strict regulatory state.
        
        Returns:
            Whether the state has strict regulations
        """
        return self.regulatory_category == "strict"
    
    @property
    def expansion_difficulty(self) -> str:
        """Get expansion difficulty based on cost and regulations.
        
        Returns:
            Difficulty level: 'easy', 'medium', or 'hard'
        """
        if self.base_expansion_cost > Decimal("2000000") or self.is_strict_regulatory:
            return "hard"
        elif self.base_expansion_cost > Decimal("1000000"):
            return "medium"
        else:
            return "easy"
    
    def get_requirement(self, requirement_key: str, default: any = None) -> any:
        """Get a specific regulatory requirement.
        
        Args:
            requirement_key: The requirement to retrieve
            default: Default value if not set
            
        Returns:
            The requirement value or default
        """
        return self.additional_requirements.get(requirement_key, default) 