"""Company line of business model for product offerings.

Tracks which lines of business a company offers in each state,
including performance metrics and market share.
"""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Column, Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.company import Company
    from core.models.line_of_business import LineOfBusiness


class CompanyLineOfBusiness(BaseModel):
    """Company's offering of a specific line of business.
    
    Tracks performance metrics, premiums, and losses for each
    line of business a company operates.
    """
    
    __tablename__ = "company_lines_of_business"
    __table_args__ = (
        UniqueConstraint('company_id', 'line_of_business_id', name='uq_company_line'),
    )
    
    # Company and line
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Company offering this line"
    )
    
    line_of_business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lines_of_business.id"),
        nullable=False,
        index=True,
        comment="Line of business being offered"
    )
    
    # Status and dates
    start_date = Column(
        Date,
        nullable=False,
        default=date.today,
        comment="Date company started offering this line"
    )
    
    end_date = Column(
        Date,
        nullable=True,
        comment="Date company stopped offering this line (if applicable)"
    )
    
    # Financial metrics
    total_premium_written = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total premiums written in this line"
    )
    
    total_premium_earned = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total premiums earned in this line"
    )
    
    total_losses_paid = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total losses paid in this line"
    )
    
    loss_ratio = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Losses / Earned Premium ratio"
    )
    
    combined_ratio = Column(
        Numeric(5, 2),
        nullable=True,
        comment="(Losses + Expenses) / Earned Premium ratio"
    )
    
    # Policy metrics
    policies_in_force = Column(
        Numeric(10, 0),
        nullable=False,
        default=0,
        comment="Number of active policies"
    )
    
    average_premium = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Average premium per policy"
    )
    
    # Performance data
    performance_metrics = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Additional performance metrics and KPIs"
    )
    
    # Relationships
    company = relationship(
        "Company",
        back_populates="lines_of_business"
    )
    
    line_of_business = relationship(
        "LineOfBusiness",
        back_populates="company_lines"
    )
    
    def __repr__(self) -> str:
        """String representation of the company line."""
        return f"<CompanyLine(company_id={self.company_id}, line_id={self.line_of_business_id})>"
    
    @property
    def is_active(self) -> bool:
        """Check if this line is currently active.
        
        Returns:
            Whether the company still offers this line
        """
        return self.end_date is None or self.end_date > date.today()
    
    @property
    def is_profitable(self) -> bool:
        """Check if this line is profitable.
        
        Returns:
            Whether the combined ratio is below 100%
        """
        if not self.combined_ratio:
            return True  # Assume profitable if no data yet
        return self.combined_ratio < Decimal("100.00")
    
    @property
    def weeks_in_operation(self) -> int:
        """Calculate weeks this line has been offered.
        
        Returns:
            Number of weeks since start date
        """
        end = self.end_date or date.today()
        return (end - self.start_date).days // 7
    
    @property
    def underwriting_profit(self) -> Decimal:
        """Calculate underwriting profit/loss.
        
        Returns:
            Underwriting profit (negative if loss)
        """
        return self.total_premium_earned - self.total_losses_paid
    
    def get_metric(self, metric_key: str, default: any = None) -> any:
        """Get a performance metric value.
        
        Args:
            metric_key: The metric to retrieve
            default: Default value if not set
            
        Returns:
            The metric value or default
        """
        return self.performance_metrics.get(metric_key, default) 