"""Employee model representing C-suite executives.

For MVP, only C-suite positions are implemented. Each executive
has a skill level (1-100) and salary requirement that scales
with their effectiveness.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.company import Company


# Valid C-suite positions for MVP
VALID_POSITIONS = [
    "CUO",           # Chief Underwriting Officer
    "CFO",           # Chief Financial Officer
    "CMO",           # Chief Marketing Officer
    "CCO",           # Chief Compliance Officer
    "CTO",           # Chief Technology Officer
    "CRO",           # Chief Risk Officer
    "CAO",           # Chief Accounting Officer
    "Chief Actuary"  # Chief Actuary
]

# Base salary ranges by position (skill 50 baseline)
POSITION_SALARY_RANGES = {
    "CUO": {"min": 200000, "max": 500000},
    "CFO": {"min": 250000, "max": 600000},
    "CMO": {"min": 150000, "max": 400000},
    "CCO": {"min": 150000, "max": 350000},
    "CTO": {"min": 200000, "max": 500000},
    "CRO": {"min": 200000, "max": 450000},
    "CAO": {"min": 180000, "max": 400000},
    "Chief Actuary": {"min": 220000, "max": 550000}
}


class Employee(BaseModel):
    """C-suite executive working for an insurance company.
    
    Each employee has a skill level that determines their
    effectiveness, modified by CEO attributes. Salary requirements
    scale with skill level.
    """
    
    __tablename__ = "employees"
    
    # Company relationship
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Company employing this executive"
    )
    
    # Position and skills
    position = Column(
        String(50),
        nullable=False,
        comment="C-suite position (CUO, CFO, CMO, etc.)"
    )
    
    name = Column(
        String(255),
        nullable=False,
        comment="Executive's name"
    )
    
    skill_level = Column(
        Numeric(3, 0),
        nullable=False,
        default=50,
        comment="Base skill level (1-100)"
    )
    
    # Compensation
    base_salary = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Annual salary requirement"
    )
    
    bonus_paid_ytd = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Bonuses paid year-to-date"
    )
    
    # Special abilities
    special_bonus = Column(
        String(255),
        nullable=True,
        comment="Special ability like '+10% investment returns'"
    )
    
    special_bonus_details = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Detailed parameters for special bonus"
    )
    
    # Employment tracking
    hire_date = Column(
        String(10),
        nullable=False,
        comment="Date hired (YYYY-MM-DD format)"
    )
    
    quarters_employed = Column(
        Numeric(3, 0),
        nullable=False,
        default=0,
        comment="Number of quarters with company"
    )
    
    performance_history = Column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Historical performance metrics"
    )
    
    # Schema versioning
    schema_version = Column(
        Numeric(3, 0),
        nullable=False,
        default=1,
        comment="Schema version for JSONB fields"
    )
    
    # Relationships
    company = relationship(
        "Company",
        back_populates="employees"
    )
    
    def __repr__(self) -> str:
        """String representation of the employee."""
        return f"<Employee(name={self.name}, position={self.position}, skill={self.skill_level})>"
    
    @property
    def annual_cost(self) -> Decimal:
        """Calculate total annual cost including salary and bonuses.
        
        Returns:
            Total compensation cost per year
        """
        return self.base_salary + self.bonus_paid_ytd
    
    @property
    def quarterly_salary(self) -> Decimal:
        """Calculate quarterly salary payment.
        
        Returns:
            Quarterly salary amount
        """
        return self.base_salary / 4
    
    def calculate_effective_skill(self, ceo_multiplier: Decimal) -> Decimal:
        """Calculate effective skill level after CEO multiplier.
        
        Args:
            ceo_multiplier: Multiplier from CEO attributes
            
        Returns:
            Effective skill level for performance calculations
        """
        return self.skill_level * ceo_multiplier
    
    def get_department_impact(self) -> dict[str, any]:
        """Calculate this executive's impact on their department.
        
        Returns:
            Dictionary of metric impacts based on position and skill
        """
        impacts = {}
        
        if self.position == "CUO":
            # Chief Underwriting Officer affects loss ratios
            skill_factor = self.skill_level / 100
            impacts["loss_ratio_modifier"] = 1 - (0.15 * skill_factor)  # Up to -15%
            impacts["risk_selection_quality"] = skill_factor
            
        elif self.position == "CFO":
            # Chief Financial Officer affects investments
            skill_factor = self.skill_level / 100
            impacts["investment_return_modifier"] = 1 + (0.10 * skill_factor)  # Up to +10%
            impacts["capital_efficiency"] = skill_factor
            
        elif self.position == "CMO":
            # Chief Marketing Officer affects growth
            skill_factor = self.skill_level / 100
            impacts["premium_growth_modifier"] = 1 + (0.20 * skill_factor)  # Up to +20%
            impacts["acquisition_cost_modifier"] = 1 - (0.10 * skill_factor)  # Up to -10%
            
        elif self.position == "CCO":
            # Chief Compliance Officer affects regulatory
            skill_factor = self.skill_level / 100
            impacts["filing_time_reduction_weeks"] = int(2 * skill_factor)  # Up to 2 weeks
            impacts["penalty_risk_modifier"] = 1 - (0.30 * skill_factor)  # Up to -30%
            
        elif self.position == "CTO":
            # Chief Technology Officer affects operations
            skill_factor = self.skill_level / 100
            impacts["operating_cost_modifier"] = 1 - (0.08 * skill_factor)  # Up to -8%
            impacts["digital_capability_score"] = skill_factor
            
        elif self.position == "CRO":
            # Chief Risk Officer affects risk management
            skill_factor = self.skill_level / 100
            impacts["catastrophe_loss_modifier"] = 1 - (0.10 * skill_factor)  # Up to -10%
            impacts["early_warning_days"] = int(14 * skill_factor)  # Up to 14 days
            
        elif self.position == "CAO":
            # Chief Accounting Officer affects reserves
            skill_factor = self.skill_level / 100
            impacts["reserve_accuracy"] = 0.90 + (0.10 * skill_factor)  # 90-100% accuracy
            impacts["expense_tracking_precision"] = skill_factor
            
        elif self.position == "Chief Actuary":
            # Chief Actuary affects pricing
            skill_factor = self.skill_level / 100
            impacts["pricing_accuracy"] = 0.85 + (0.15 * skill_factor)  # 85-100% accuracy
            impacts["rate_indication_quality"] = skill_factor
        
        # Apply special bonus if applicable
        if self.special_bonus:
            impacts["special_bonus"] = self.special_bonus
            impacts["special_bonus_active"] = True
        
        return impacts
    
    @staticmethod
    def calculate_salary_requirement(position: str, skill_level: int) -> Decimal:
        """Calculate salary requirement based on position and skill.
        
        Args:
            position: The C-suite position
            skill_level: Skill level (1-100)
            
        Returns:
            Annual salary requirement
        """
        if position not in POSITION_SALARY_RANGES:
            raise ValueError(f"Invalid position: {position}")
        
        salary_range = POSITION_SALARY_RANGES[position]
        min_salary = salary_range["min"]
        max_salary = salary_range["max"]
        
        # Linear scaling with skill level
        skill_factor = (skill_level - 1) / 99  # Normalize to 0-1
        salary = min_salary + (max_salary - min_salary) * skill_factor
        
        return Decimal(str(int(salary)))
    
    @staticmethod
    def generate_special_bonus(position: str, skill_level: int) -> Optional[str]:
        """Generate a special bonus for high-skill executives.
        
        Args:
            position: The C-suite position
            skill_level: Skill level (1-100)
            
        Returns:
            Special bonus description or None
        """
        # Only high-skill executives (80+) get special bonuses
        if skill_level < 80:
            return None
        
        bonuses_by_position = {
            "CUO": [
                "-5% loss ratios in new markets",
                "+15% better risk selection",
                "Catastrophe modeling expertise"
            ],
            "CFO": [
                "+10% investment returns",
                "-20% capital costs",
                "M&A valuation expertise"
            ],
            "CMO": [
                "-25% customer acquisition costs",
                "+30% digital conversion rates",
                "Viral marketing campaigns"
            ],
            "CCO": [
                "-2 weeks on all rate filings",
                "Regulatory relationship bonus",
                "Multi-state filing expertise"
            ],
            "CTO": [
                "-15% IT operational costs",
                "Instant digital product launches",
                "AI/ML implementation expertise"
            ],
            "CRO": [
                "-20% reinsurance costs",
                "Early catastrophe warnings",
                "Portfolio optimization expertise"
            ],
            "CAO": [
                "Perfect reserve accuracy",
                "-10% audit costs",
                "Real-time financial reporting"
            ],
            "Chief Actuary": [
                "+20% pricing precision",
                "Predictive modeling expertise",
                "Competitive intelligence insights"
            ]
        }
        
        import random
        position_bonuses = bonuses_by_position.get(position, [])
        if position_bonuses:
            return random.choice(position_bonuses)
        
        return None 