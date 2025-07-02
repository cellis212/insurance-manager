"""Semester model for managing game instances.

Each semester represents a separate game instance with its own
configuration and data. All game data resets between semesters.
"""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, Date, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.user import User
    from core.models.company import Company
    from core.models.turn import Turn
    from core.models.feature_flag import FeatureFlag
    from core.models.semester_configuration import SemesterConfiguration
    from core.models.game_event import GameEvent
    from core.models.audit_log import AuditLog


class Semester(BaseModel):
    """Represents an academic semester game instance.
    
    Each semester is a completely separate game with its own configuration,
    allowing for feature changes and experimentation between terms.
    """
    
    __tablename__ = "semesters"
    
    # Basic information
    name = Column(
        String(100),
        nullable=False,
        unique=True,
        comment="Human-readable semester name (e.g., 'Fall 2024')"
    )
    
    code = Column(
        String(20),
        nullable=False,
        unique=True,
        index=True,
        comment="Semester code (e.g., 'F24')"
    )
    
    # Semester dates
    start_date = Column(
        Date,
        nullable=False,
        comment="First day of the semester"
    )
    
    end_date = Column(
        Date,
        nullable=False,
        comment="Last day of the semester"
    )
    
    # Game configuration
    game_start_date = Column(
        Date,
        nullable=False,
        comment="When the game actually starts (may be after semester start)"
    )
    
    game_end_date = Column(
        Date,
        nullable=False,
        comment="When the game ends (may be before semester end)"
    )
    
    # Status flags
    is_active = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether this is the currently active semester"
    )
    
    is_registration_open = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether new users can register for this semester"
    )
    
    # Configuration
    configuration = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Semester-specific game configuration and feature flags"
    )
    
    # Version tracking
    game_version = Column(
        String(20),
        nullable=False,
        default="1.0.0",
        comment="Game version running for this semester"
    )
    
    # Relationships
    users = relationship(
        "User",
        back_populates="semester"
    )
    
    companies = relationship(
        "Company",
        back_populates="semester",
        cascade="all, delete-orphan"
    )
    
    turns = relationship(
        "Turn",
        back_populates="semester",
        cascade="all, delete-orphan"
    )
    
    feature_flags = relationship(
        "FeatureFlag",
        back_populates="semester",
        cascade="all, delete-orphan"
    )
    
    semester_configuration = relationship(
        "SemesterConfiguration",
        back_populates="semester",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    game_events = relationship(
        "GameEvent",
        back_populates="semester",
        cascade="all, delete-orphan"
    )
    
    audit_logs = relationship(
        "AuditLog",
        back_populates="semester",
        cascade="all, delete-orphan"
    )
    
    market_conditions = relationship(
        "MarketCondition",
        back_populates="semester",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        """String representation of the semester."""
        return f"<Semester(name={self.name}, code={self.code})>"
    
    @property
    def is_in_progress(self) -> bool:
        """Check if the game is currently in progress.
        
        Returns:
            Whether we're between game start and end dates
        """
        today = date.today()
        return self.game_start_date <= today <= self.game_end_date
    
    @property
    def weeks_remaining(self) -> int:
        """Calculate weeks remaining in the semester.
        
        Returns:
            Number of weeks until game end
        """
        if not self.is_in_progress:
            return 0
        
        days_remaining = (self.game_end_date - date.today()).days
        return max(0, days_remaining // 7)
    
    def get_config(self, key: str, default: any = None) -> any:
        """Get a configuration value for this semester.
        
        Args:
            key: Configuration key to retrieve
            default: Default value if not set
            
        Returns:
            The configuration value or default
        """
        return self.configuration.get(key, default) 