"""CEO model representing player character development.

The CEO is the player's avatar whose attributes multiply employee
effectiveness across the organization. Each attribute ranges from
1-100 and affects specific departments.
"""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Column, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.company import Company


class CEO(BaseModel):
    """Player's CEO character with 8 core attributes.
    
    CEO attributes serve as multipliers for employee performance,
    creating a progression system where player skill development
    directly impacts company operations.
    """
    
    __tablename__ = "ceos"
    
    # One-to-one relationship with company
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Company this CEO leads"
    )
    
    # Basic information
    name = Column(
        String(255),
        nullable=False,
        comment="CEO name"
    )
    
    age = Column(
        Numeric(3, 0),
        nullable=False,
        default=38,
        comment="CEO age (35-40 start, retires at 65)"
    )
    
    hired_date = Column(
        Date,
        nullable=False,
        default=date.today,
        comment="Date when CEO was hired"
    )
    
    # Core attributes (1-100 range)
    leadership = Column(
        Numeric(3, 0),
        nullable=False,
        default=30,
        comment="Universal 50% boost to all employees"
    )
    
    risk_intelligence = Column(
        Numeric(3, 0),
        nullable=False,
        default=30,
        comment="Boosts underwriting and actuarial staff"
    )
    
    market_acumen = Column(
        Numeric(3, 0),
        nullable=False,
        default=30,
        comment="Enhances marketing and sales teams"
    )
    
    regulatory_mastery = Column(
        Numeric(3, 0),
        nullable=False,
        default=30,
        comment="Improves compliance and legal efficiency"
    )
    
    innovation_capacity = Column(
        Numeric(3, 0),
        nullable=False,
        default=30,
        comment="Amplifies technology and R&D output"
    )
    
    deal_making = Column(
        Numeric(3, 0),
        nullable=False,
        default=30,
        comment="Helps with M&A and reinsurance negotiations"
    )
    
    financial_expertise = Column(
        Numeric(3, 0),
        nullable=False,
        default=30,
        comment="Boosts investment and financial analysis"
    )
    
    crisis_command = Column(
        Numeric(3, 0),
        nullable=False,
        default=30,
        comment="Activates during catastrophes for claims/PR boost"
    )
    
    # Progression tracking
    lifetime_profit = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Cumulative profit for milestone unlocks"
    )
    
    quarters_led = Column(
        Numeric(4, 0),
        nullable=False,
        default=0,
        comment="Number of quarters as CEO"
    )
    
    # Achievement tracking and special unlocks
    achievements = Column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="List of unlocked achievements and milestones"
    )
    
    special_bonuses = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Active bonuses from events or milestones"
    )
    
    # Schema versioning for data migration
    schema_version = Column(
        Numeric(3, 0),
        nullable=False,
        default=1,
        comment="Schema version for JSONB fields"
    )
    
    # Relationships
    company = relationship(
        "Company",
        back_populates="ceo",
        uselist=False
    )
    
    def __repr__(self) -> str:
        """String representation of the CEO."""
        return f"<CEO(name={self.name}, company_id={self.company_id})>"
    
    @property
    def years_until_retirement(self) -> int:
        """Calculate years until mandatory retirement at 65.
        
        Returns:
            Number of years until retirement
        """
        return max(0, 65 - int(self.age))
    
    @property
    def is_eligible_for_retirement(self) -> bool:
        """Check if CEO has reached retirement age.
        
        Returns:
            Whether CEO must retire
        """
        return self.age >= 65
    
    @property
    def total_stat_points(self) -> int:
        """Calculate total attribute points for progression tracking.
        
        Returns:
            Sum of all 8 attributes
        """
        return sum([
            int(self.leadership),
            int(self.risk_intelligence),
            int(self.market_acumen),
            int(self.regulatory_mastery),
            int(self.innovation_capacity),
            int(self.deal_making),
            int(self.financial_expertise),
            int(self.crisis_command)
        ])
    
    def get_employee_multiplier(self, position: str, is_crisis: bool = False) -> Decimal:
        """Calculate the multiplier this CEO provides to an employee.
        
        Args:
            position: The employee's position (e.g., 'CFO', 'CUO')
            is_crisis: Whether crisis command should be active
            
        Returns:
            Multiplier to apply to employee effectiveness
        """
        # Base leadership affects everyone at 50% strength
        base_multiplier = 1 + (self.leadership / 100) * 0.5
        
        # Position-specific multipliers at full strength
        position_multipliers = {
            "CUO": self.risk_intelligence,  # Chief Underwriting Officer
            "Chief Actuary": self.risk_intelligence,
            "CRO": self.risk_intelligence,  # Chief Risk Officer
            "CFO": self.financial_expertise,
            "CAO": self.financial_expertise,  # Chief Accounting Officer
            "CMO": self.market_acumen,
            "CCO": self.regulatory_mastery,  # Chief Compliance Officer
            "CTO": self.innovation_capacity
        }
        
        # Get position-specific boost
        if position in position_multipliers:
            specific_boost = position_multipliers[position] / 100
            base_multiplier += specific_boost
        
        # Crisis command applies during catastrophes
        if is_crisis:
            base_multiplier += self.crisis_command / 100
        
        return Decimal(str(base_multiplier))
    
    def check_milestone_unlocks(self) -> list[str]:
        """Check if any new milestones have been unlocked.
        
        Returns:
            List of newly unlocked milestone keys
        """
        unlocked = []
        milestones = {
            "advanced_analytics": Decimal("50000000"),    # $50M
            "fast_track_approvals": Decimal("100000000"), # $100M
            "premium_investments": Decimal("250000000"),  # $250M
            "national_advertising": Decimal("500000000"), # $500M
            "industry_influence": Decimal("1000000000")   # $1B
        }
        
        current_achievements = self.achievements or []
        
        for key, threshold in milestones.items():
            if key not in current_achievements and self.lifetime_profit >= threshold:
                unlocked.append(key)
        
        return unlocked 