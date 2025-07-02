"""Company state authorization model for expansion tracking.

Tracks which states a company is authorized to operate in,
including approval dates and compliance status.
"""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.company import Company
    from core.models.state import State


class CompanyStateAuthorization(BaseModel):
    """Authorization for a company to operate in a specific state.
    
    Tracks the approval process, compliance status, and any
    state-specific requirements for operations.
    """
    
    __tablename__ = "company_state_authorizations"
    __table_args__ = (
        UniqueConstraint('company_id', 'state_id', name='uq_company_state'),
    )
    
    # Company and state
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Company seeking authorization"
    )
    
    state_id = Column(
        UUID(as_uuid=True),
        ForeignKey("states.id"),
        nullable=False,
        index=True,
        comment="State for authorization"
    )
    
    # Authorization status
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="Status: 'pending', 'approved', 'suspended', 'revoked'"
    )
    
    # Important dates
    application_date = Column(
        Date,
        nullable=False,
        default=date.today,
        comment="Date authorization was requested"
    )
    
    approval_date = Column(
        Date,
        nullable=True,
        comment="Date authorization was approved"
    )
    
    expected_approval_date = Column(
        Date,
        nullable=True,
        comment="Expected approval date (4 weeks from application)"
    )
    
    # Compliance tracking
    is_compliant = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether company is meeting state requirements"
    )
    
    compliance_score = Column(
        String(20),
        nullable=True,
        comment="Compliance rating: 'excellent', 'good', 'fair', 'poor'"
    )
    
    last_audit_date = Column(
        Date,
        nullable=True,
        comment="Date of last regulatory audit"
    )
    
    # Home state advantage
    is_home_state = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is the company's home state"
    )
    
    # Relationships
    company = relationship(
        "Company",
        back_populates="state_authorizations"
    )
    
    state = relationship(
        "State",
        back_populates="company_authorizations"
    )
    
    def __repr__(self) -> str:
        """String representation of the authorization."""
        return f"<CompanyStateAuth(company_id={self.company_id}, state_id={self.state_id}, status={self.status})>"
    
    @property
    def is_approved(self) -> bool:
        """Check if authorization is approved.
        
        Returns:
            Whether the company can operate in this state
        """
        return self.status == "approved" and self.is_compliant
    
    @property
    def days_until_approval(self) -> int:
        """Calculate days until expected approval.
        
        Returns:
            Days remaining or 0 if already approved
        """
        if self.status == "approved" or not self.expected_approval_date:
            return 0
        
        days = (self.expected_approval_date - date.today()).days
        return max(0, days)
    
    @property
    def needs_compliance_review(self) -> bool:
        """Check if compliance review is needed.
        
        Returns:
            Whether a compliance review should be scheduled
        """
        if not self.is_approved:
            return False
            
        # Review needed if poor compliance or no recent audit
        if self.compliance_score == "poor":
            return True
            
        if not self.last_audit_date:
            return True
            
        # Audit every 12 weeks
        days_since_audit = (date.today() - self.last_audit_date).days
        return days_since_audit > 84 