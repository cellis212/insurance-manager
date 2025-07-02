"""Company turn decision model for storing player decisions.

Stores all decisions made by a company for a specific turn,
using JSONB for extensibility as new features are added.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.company import Company
    from core.models.turn import Turn


class CompanyTurnDecision(BaseModel):
    """Stores all decisions made by a company for a turn.
    
    Uses JSONB to store decision data, allowing new decision types
    to be added without schema changes. Decisions default to "no change"
    if not submitted by the deadline.
    """
    
    __tablename__ = "company_turn_decisions"
    
    # Foreign keys
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Company making the decisions"
    )
    
    turn_id = Column(
        UUID(as_uuid=True),
        ForeignKey("turns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Turn these decisions apply to"
    )
    
    # Submission tracking
    submitted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When decisions were submitted (null = defaults applied)"
    )
    
    is_default = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether these are system-generated 'no change' defaults"
    )
    
    # Decision storage
    decisions = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="All decisions for this turn (products, hiring, expansion, etc.)"
    )
    
    # Feature tracking
    features_used = Column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="List of features used in this decision set"
    )
    
    # Validation results
    validation_results = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Results of decision validation (warnings, errors)"
    )
    
    # Schema versioning for data migration
    schema_version = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Schema version for JSONB fields"
    )
    
    # Relationships
    company = relationship(
        "Company",
        back_populates="turn_decisions"
    )
    
    turn = relationship(
        "Turn",
        back_populates="company_decisions"
    )
    
    # Unique constraint - one decision set per company per turn
    __table_args__ = (
        UniqueConstraint('company_id', 'turn_id', name='uix_company_turn_decision'),
    )
    
    def __repr__(self) -> str:
        """String representation of the decision."""
        return f"<CompanyTurnDecision(company={self.company_id}, turn={self.turn_id}, default={self.is_default})>"
    
    def get_decision(self, category: str, key: str, default: any = None) -> any:
        """Get a specific decision value.
        
        Args:
            category: Decision category (e.g., 'products', 'hiring')
            key: Specific decision key within category
            default: Default value if not set
            
        Returns:
            The decision value or default
        """
        category_decisions = self.decisions.get(category, {})
        return category_decisions.get(key, default)
    
    def set_decision(self, category: str, key: str, value: any) -> None:
        """Set a specific decision value.
        
        Args:
            category: Decision category
            key: Specific decision key
            value: Decision value to set
        """
        if category not in self.decisions:
            self.decisions[category] = {}
        
        self.decisions[category][key] = value
        
        # Track feature usage
        if category not in self.features_used:
            self.features_used.append(category)
    
    @property
    def has_expansion_decisions(self) -> bool:
        """Check if this decision includes expansion plans.
        
        Returns:
            Whether expansion decisions are present
        """
        return 'expansion' in self.decisions and bool(self.decisions['expansion'])
    
    @property
    def has_product_changes(self) -> bool:
        """Check if this decision includes product changes.
        
        Returns:
            Whether product decisions are present
        """
        return 'products' in self.decisions and bool(self.decisions['products'])
    
    @property
    def total_hiring_cost(self) -> float:
        """Calculate total cost of hiring decisions.
        
        Returns:
            Total salary cost from hiring decisions
        """
        hiring = self.decisions.get('hiring', {})
        total = 0
        
        for position, details in hiring.items():
            if isinstance(details, dict) and 'salary' in details:
                total += details['salary']
        
        return total
    
    def validate_capital_requirements(self, available_capital: float) -> dict:
        """Validate that decisions don't exceed available capital.
        
        Args:
            available_capital: Company's available capital
            
        Returns:
            Validation results with any warnings/errors
        """
        results = {
            'valid': True,
            'warnings': [],
            'errors': []
        }
        
        total_cost = 0
        
        # Add hiring costs
        total_cost += self.total_hiring_cost
        
        # Add expansion costs
        expansion_costs = self.decisions.get('expansion', {}).get('total_cost', 0)
        total_cost += expansion_costs
        
        # Check capital constraint
        if total_cost > available_capital:
            results['valid'] = False
            results['errors'].append(
                f"Total cost ${total_cost:,.2f} exceeds available capital ${available_capital:,.2f}"
            )
        elif total_cost > available_capital * 0.8:
            results['warnings'].append(
                f"Total cost ${total_cost:,.2f} uses >80% of available capital"
            )
        
        return results 