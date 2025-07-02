"""Company turn result model for storing calculated outcomes.

Stores all calculated results for a company after turn processing,
including financial results, market changes, and performance metrics.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.company import Company
    from core.models.turn import Turn


class CompanyTurnResult(BaseModel):
    """Stores calculated results for a company after turn processing.
    
    Contains all financial outcomes, market changes, and performance
    metrics calculated during turn processing. Uses JSONB for extensibility
    as new calculation types are added.
    """
    
    __tablename__ = "company_turn_results"
    
    # Foreign keys
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Company these results belong to"
    )
    
    turn_id = Column(
        UUID(as_uuid=True),
        ForeignKey("turns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Turn these results are for"
    )
    
    # Core financial results
    premiums_written = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total premiums written this turn"
    )
    
    premiums_earned = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Premiums earned (pro-rata portion)"
    )
    
    claims_incurred = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total claims incurred this turn"
    )
    
    claims_paid = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Claims actually paid out this turn"
    )
    
    operating_expenses = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total operating expenses including salaries"
    )
    
    investment_income = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Income from investment portfolio"
    )
    
    net_income = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Net income for the turn"
    )
    
    ending_capital = Column(
        Numeric(15, 2),
        nullable=False,
        comment="Capital balance at turn end"
    )
    
    # Key ratios
    loss_ratio = Column(
        Numeric(5, 4),
        nullable=True,
        comment="Claims incurred / premiums earned"
    )
    
    expense_ratio = Column(
        Numeric(5, 4),
        nullable=True,
        comment="Operating expenses / premiums written"
    )
    
    combined_ratio = Column(
        Numeric(5, 4),
        nullable=True,
        comment="Loss ratio + expense ratio"
    )
    
    # Detailed results storage
    financial_details = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Detailed financial breakdown by line/state"
    )
    
    market_results = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Market share changes, competitor analysis"
    )
    
    operational_results = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Employee performance, efficiency metrics"
    )
    
    regulatory_results = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Compliance status, regulatory actions"
    )
    
    special_events = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Catastrophe impacts, market events"
    )
    
    # Schema versioning for data migration
    result_schema_version = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Schema version for JSONB result fields"
    )
    
    # Relationships
    company = relationship(
        "Company",
        back_populates="turn_results"
    )
    
    turn = relationship(
        "Turn",
        back_populates="company_results"
    )
    
    # Unique constraint - one result set per company per turn
    __table_args__ = (
        UniqueConstraint('company_id', 'turn_id', name='uix_company_turn_result'),
    )
    
    def __repr__(self) -> str:
        """String representation of the result."""
        return f"<CompanyTurnResult(company={self.company_id}, turn={self.turn_id}, net_income={self.net_income})>"
    
    @property
    def is_profitable(self) -> bool:
        """Check if the company was profitable this turn.
        
        Returns:
            Whether net income is positive
        """
        return self.net_income > 0
    
    @property
    def is_underwriting_profitable(self) -> bool:
        """Check if underwriting operations were profitable.
        
        Returns:
            Whether combined ratio is below 100%
        """
        if not self.combined_ratio:
            return False
        return self.combined_ratio < 1.0
    
    def get_line_results(self, line_code: str) -> dict:
        """Get detailed results for a specific line of business.
        
        Args:
            line_code: Line of business code
            
        Returns:
            Results for that line or empty dict
        """
        return self.financial_details.get('by_line', {}).get(line_code, {})
    
    def get_state_results(self, state_code: str) -> dict:
        """Get detailed results for a specific state.
        
        Args:
            state_code: Two-letter state code
            
        Returns:
            Results for that state or empty dict
        """
        return self.financial_details.get('by_state', {}).get(state_code, {})
    
    def get_market_share(self, state_code: str, line_code: str) -> float:
        """Get market share for a state/line combination.
        
        Args:
            state_code: Two-letter state code
            line_code: Line of business code
            
        Returns:
            Market share as decimal (0.15 = 15%)
        """
        key = f"{state_code}_{line_code}"
        return self.market_results.get('market_shares', {}).get(key, 0.0)
    
    def get_catastrophe_loss(self) -> Decimal:
        """Get total catastrophe losses if any occurred this turn.
        
        Returns:
            Total catastrophe losses
        """
        cat_events = self.special_events.get('catastrophes', [])
        total_loss = Decimal("0.00")
        
        for event in cat_events:
            if isinstance(event, dict) and 'loss_amount' in event:
                total_loss += Decimal(str(event['loss_amount']))
        
        return total_loss
    
    def calculate_ratios(self) -> None:
        """Calculate and update key performance ratios."""
        # Loss ratio
        if self.premiums_earned > 0:
            self.loss_ratio = self.claims_incurred / self.premiums_earned
        else:
            self.loss_ratio = None
        
        # Expense ratio
        if self.premiums_written > 0:
            self.expense_ratio = self.operating_expenses / self.premiums_written
        else:
            self.expense_ratio = None
        
        # Combined ratio
        if self.loss_ratio is not None and self.expense_ratio is not None:
            self.combined_ratio = self.loss_ratio + self.expense_ratio
        else:
            self.combined_ratio = None 