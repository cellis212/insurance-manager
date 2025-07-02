"""Turn model for tracking weekly game cycles.

Each turn represents one week of game time, processing decisions
and calculating results for all companies in a semester.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.semester import Semester
    from core.models.turn_decision import CompanyTurnDecision
    from core.models.turn_result import CompanyTurnResult
    from core.models.game_event import GameEvent


class Turn(BaseModel):
    """Weekly game turn for processing company decisions.
    
    Turns process every Monday at midnight EST, calculating results
    based on all company decisions submitted before the deadline.
    """
    
    __tablename__ = "turns"
    
    # Semester association
    semester_id = Column(
        UUID(as_uuid=True),
        ForeignKey("semesters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Semester this turn belongs to"
    )
    
    # Turn identification
    turn_number = Column(
        Integer,
        nullable=False,
        comment="Sequential turn number within the semester (1-16)"
    )
    
    # Timing
    start_time = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="When this turn period begins"
    )
    
    end_time = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Deadline for submitting decisions (Sunday midnight EST)"
    )
    
    processing_started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When turn processing began"
    )
    
    processing_completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When turn processing finished"
    )
    
    # Status tracking
    status = Column(
        String(20),
        nullable=False,
        default="upcoming",
        comment="Status: 'upcoming', 'active', 'processing', 'completed', 'failed'"
    )
    
    # Version and configuration
    game_version = Column(
        String(20),
        nullable=False,
        comment="Game version for this turn's calculations"
    )
    
    # Special turn configuration
    special_rules = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Special events or rules for this turn (catastrophes, etc.)"
    )
    
    # Processing metadata
    processing_metadata = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Statistics about turn processing (duration, errors, etc.)"
    )
    
    # Schema versioning for data migration
    schema_version = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Schema version for JSONB fields"
    )
    
    # Relationships
    semester = relationship(
        "Semester",
        back_populates="turns"
    )
    
    company_decisions = relationship(
        "CompanyTurnDecision",
        back_populates="turn",
        cascade="all, delete-orphan"
    )
    
    company_results = relationship(
        "CompanyTurnResult",
        back_populates="turn",
        cascade="all, delete-orphan"
    )
    
    game_events = relationship(
        "GameEvent",
        back_populates="turn",
        cascade="all, delete-orphan"
    )
    
    price_decisions = relationship(
        "PriceDecision",
        back_populates="turn",
        cascade="all, delete-orphan"
    )
    
    investment_portfolios = relationship(
        "InvestmentPortfolio",
        back_populates="turn",
        cascade="all, delete-orphan"
    )
    
    liquidation_events = relationship(
        "LiquidationEvent",
        back_populates="turn",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        """String representation of the turn."""
        return f"<Turn(semester={self.semester_id}, number={self.turn_number}, status={self.status})>"
    
    @property
    def is_accepting_decisions(self) -> bool:
        """Check if turn is still accepting player decisions.
        
        Returns:
            Whether decisions can still be submitted
        """
        if self.status != "active":
            return False
        
        return datetime.now(tz=datetime.now().tzinfo) < self.end_time
    
    @property
    def processing_duration_seconds(self) -> int:
        """Calculate how long turn processing took.
        
        Returns:
            Processing duration in seconds, or 0 if not completed
        """
        if not self.processing_started_at or not self.processing_completed_at:
            return 0
        
        duration = self.processing_completed_at - self.processing_started_at
        return int(duration.total_seconds())
    
    def has_special_event(self, event_type: str) -> bool:
        """Check if this turn has a specific special event.
        
        Args:
            event_type: Type of event to check for
            
        Returns:
            Whether the event is active this turn
        """
        events = self.special_rules.get("events", [])
        return event_type in events
    
    def get_catastrophe_info(self) -> dict:
        """Get catastrophe information if this is a catastrophe turn.
        
        Returns:
            Catastrophe details or empty dict
        """
        if not self.has_special_event("catastrophe"):
            return {}
        
        return self.special_rules.get("catastrophe_details", {}) 