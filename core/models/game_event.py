"""Game event tracking for debugging and analysis.

Captures all significant events during game execution including turn processing,
decision submissions, state changes, and system events. Designed for high-volume
writes with semester-based partitioning.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
import enum

from sqlalchemy import (
    String, 
    ForeignKey, 
    UniqueConstraint, 
    CheckConstraint,
    Enum,
    Integer,
    TIMESTAMP,
    Boolean,
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
    from .turn import Turn


class EventCategory(enum.Enum):
    """High-level categorization of events for filtering."""
    TURN_PROCESSING = "turn_processing"
    DECISION = "decision"
    FINANCIAL = "financial"
    REGULATORY = "regulatory"
    EMPLOYEE = "employee"
    PRODUCT = "product"
    EXPANSION = "expansion"
    INVESTMENT = "investment"
    CATASTROPHE = "catastrophe"
    SYSTEM = "system"
    USER_ACTION = "user_action"
    ERROR = "error"


class EventSeverity(enum.Enum):
    """Event severity levels for monitoring and alerting."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class GameEvent(BaseModel):
    """Captures all significant events during game execution.
    
    This table is designed for high-volume writes and will be partitioned
    by semester_id for efficient querying and cleanup. Events are immutable
    once created.
    
    Attributes:
        event_type: Specific event identifier (e.g., 'turn.started', 'company.bankrupt')
        category: High-level event category for filtering
        severity: Event severity level for monitoring
        semester_id: Semester this event belongs to (for partitioning)
        turn_id: Optional turn reference for turn-related events
        company_id: Optional company reference for company-specific events
        user_id: Optional user reference for user actions
        
        event_data: JSONB containing event-specific data. Structure varies by event_type:
            - turn.started: {turn_number, company_count, processing_start_time}
            - decision.submitted: {decision_type, values, validation_result}
            - company.bankrupt: {final_capital, debt, trigger_reason}
            - catastrophe.occurred: {type, severity, affected_states, total_damage}
        
        context_data: JSONB containing debugging context:
            - request_id: HTTP request ID for tracing
            - session_id: User session for tracking flows
            - ip_address: Client IP for security analysis
            - user_agent: Browser/client information
            - stack_trace: For error events
            - performance_metrics: {duration_ms, memory_used, queries_executed}
        
        triggered_by: What initiated this event ('system', 'user', 'scheduled', 'cascade')
        correlation_id: UUID to link related events together
        is_processed: Whether any follow-up actions have been completed
        
    Relationships:
        semester: The semester this event occurred in
        turn: Optional reference to the turn
        company: Optional reference to the company
        user: Optional reference to the user
    """
    
    __tablename__ = "game_events"
    __table_args__ = (
        # Partition by semester_id for efficient cleanup
        # Actual partitioning SQL will be in migration
        Index('idx_game_events_semester_created', 'semester_id', 'created_at'),
        Index('idx_game_events_type_severity', 'event_type', 'severity'),
        Index('idx_game_events_company_turn', 'company_id', 'turn_id'),
        Index('idx_game_events_correlation', 'correlation_id'),
        # GIN index for JSONB queries
        Index('idx_game_events_event_data', 'event_data', postgresql_using='gin'),
    )
    
    # Event identification
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[EventCategory] = mapped_column(
        Enum(EventCategory, native_enum=False), 
        nullable=False
    )
    severity: Mapped[EventSeverity] = mapped_column(
        Enum(EventSeverity, native_enum=False),
        nullable=False,
        server_default=EventSeverity.INFO.value
    )
    
    # Relationships
    semester_id: Mapped[UUID] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"),
        nullable=False
    )
    turn_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("turns.id", ondelete="CASCADE"),
        nullable=True
    )
    company_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Event data
    event_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb")
    )
    context_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb")
    )
    
    # Event metadata
    triggered_by: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="system"
    )
    correlation_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True
    )
    is_processed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false")
    )
    
    # Relationships
    semester: Mapped["Semester"] = relationship(
        back_populates="game_events"
    )
    turn: Mapped[Optional["Turn"]] = relationship(
        back_populates="game_events"
    )
    company: Mapped[Optional["Company"]] = relationship(
        back_populates="game_events"
    )
    user: Mapped[Optional["User"]] = relationship(
        back_populates="game_events"
    )
    
    def __repr__(self) -> str:
        return f"<GameEvent({self.event_type}, {self.severity.value}, {self.created_at})>" 