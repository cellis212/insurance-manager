"""Audit logging for critical entity changes.

Tracks modifications to important game entities like companies, financials,
and employees. Captures before/after states for debugging and compliance.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
import enum

from sqlalchemy import (
    String, 
    ForeignKey, 
    CheckConstraint,
    Enum,
    Integer,
    TIMESTAMP,
    Index,
    text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import BaseModel

if TYPE_CHECKING:
    from .semester import Semester
    from .company import Company
    from .user import User
    from .employee import Employee


class AuditedEntity(enum.Enum):
    """Entities that are tracked for audit purposes."""
    COMPANY = "company"
    COMPANY_FINANCIALS = "company_financials"
    EMPLOYEE = "employee"
    PRODUCT = "product"
    COMPANY_STATE_AUTH = "company_state_auth"
    COMPANY_LINE_OF_BUSINESS = "company_line_of_business"
    TURN_DECISION = "turn_decision"
    TURN_RESULT = "turn_result"
    CEO_ATTRIBUTES = "ceo_attributes"
    INVESTMENT_PORTFOLIO = "investment_portfolio"


class ChangeType(enum.Enum):
    """Type of change being audited."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    BULK_UPDATE = "bulk_update"


class AuditLog(BaseModel):
    """Tracks changes to critical game entities.
    
    This table captures before/after snapshots of entity changes for debugging,
    compliance, and game state reconstruction. Designed for moderate write volume
    with rich querying capabilities.
    
    Attributes:
        entity_type: The type of entity being audited
        entity_id: UUID of the specific entity instance
        change_type: Type of change (create, update, delete)
        semester_id: Semester this change belongs to (for partitioning)
        
        changed_by_user_id: User who initiated the change (null for system)
        changed_by_system: System component that made the change
        change_reason: Human-readable reason for the change
        
        old_values: JSONB snapshot of entity state before change
            - For CREATE: null
            - For UPDATE: previous field values (only changed fields)
            - For DELETE: full entity snapshot
            
        new_values: JSONB snapshot of entity state after change
            - For CREATE: full entity snapshot
            - For UPDATE: new field values (only changed fields)
            - For DELETE: null
            
        changed_fields: List of field names that were modified
        
        context_metadata: JSONB containing additional context:
            - request_id: HTTP request ID for tracing
            - turn_id: Turn when change occurred
            - correlation_id: Links related changes
            - validation_errors: Any validation issues
            - business_rules_applied: Which rules triggered
            - cascade_from: Parent entity that triggered this change
        
        company_id: Optional reference to affected company for filtering
        
    Relationships:
        semester: The semester this audit log belongs to
        company: Optional reference to the affected company
        changed_by_user: User who made the change
    """
    
    __tablename__ = "audit_logs"
    __table_args__ = (
        # Indexes for common query patterns
        Index('idx_audit_logs_entity_lookup', 'entity_type', 'entity_id', 'created_at'),
        Index('idx_audit_logs_semester_entity', 'semester_id', 'entity_type', 'created_at'),
        Index('idx_audit_logs_company_created', 'company_id', 'created_at'),
        Index('idx_audit_logs_user_changes', 'changed_by_user_id', 'created_at'),
        # GIN indexes for JSONB queries
        Index('idx_audit_logs_changed_fields', 'changed_fields', postgresql_using='gin'),
        Index('idx_audit_logs_context_metadata', 'context_metadata', postgresql_using='gin'),
        # Ensure entity_id is a valid UUID
        CheckConstraint(
            "entity_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'",
            name="check_audit_logs_entity_id_uuid"
        ),
    )
    
    # Entity identification
    entity_type: Mapped[AuditedEntity] = mapped_column(
        Enum(AuditedEntity, native_enum=False),
        nullable=False
    )
    entity_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False
    )
    change_type: Mapped[ChangeType] = mapped_column(
        Enum(ChangeType, native_enum=False),
        nullable=False
    )
    
    # Relationships
    semester_id: Mapped[UUID] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"),
        nullable=False
    )
    changed_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    company_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True
    )
    
    # Change tracking
    changed_by_system: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        server_default="api"
    )
    change_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    
    # State snapshots
    old_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True
    )
    new_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True
    )
    changed_fields: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb")
    )
    
    # Additional context
    context_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb")
    )
    
    # Relationships
    semester: Mapped["Semester"] = relationship(
        back_populates="audit_logs"
    )
    company: Mapped[Optional["Company"]] = relationship(
        back_populates="audit_logs"
    )
    changed_by_user: Mapped[Optional["User"]] = relationship(
        back_populates="audit_logs_created"
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog({self.entity_type.value}:{self.entity_id}, {self.change_type.value})>"
    
    @property
    def is_financial_change(self) -> bool:
        """Whether this audit log represents a financial change."""
        return self.entity_type in [
            AuditedEntity.COMPANY_FINANCIALS,
            AuditedEntity.TURN_RESULT,
            AuditedEntity.INVESTMENT_PORTFOLIO
        ]
    
    def get_changed_field_value(self, field_name: str) -> tuple[Any, Any]:
        """Get the old and new values for a specific field.
        
        Args:
            field_name: The name of the field to check
            
        Returns:
            Tuple of (old_value, new_value), either may be None
        """
        old_val = self.old_values.get(field_name) if self.old_values else None
        new_val = self.new_values.get(field_name) if self.new_values else None
        return (old_val, new_val) 