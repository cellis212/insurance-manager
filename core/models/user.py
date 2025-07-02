"""User model for authentication and account management.

Handles user authentication, preferences, and semester association.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.session import Session
    from core.models.semester import Semester
    from core.models.company import Company
    from core.models.feature_flag import FeatureFlag
    from core.models.game_event import GameEvent
    from core.models.audit_log import AuditLog


class User(BaseModel):
    """User account for the Insurance Manager game.
    
    Stores authentication information, preferences, and feature flags.
    Users are associated with a specific semester for game participation.
    """
    
    __tablename__ = "users"
    
    # Authentication fields
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User's email address for login"
    )
    
    password_hash = Column(
        String(255),
        nullable=False,
        comment="Hashed password using bcrypt"
    )
    
    # Account status
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the user account is active"
    )
    
    is_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the user has verified their email"
    )
    
    # Tracking fields
    last_login = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of the user's last login"
    )
    
    # Preferences and configuration
    preferences = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="User preferences (theme, notifications, etc.)"
    )
    
    feature_flags = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Feature flags for progressive rollout"
    )
    
    # Semester association
    semester_id = Column(
        UUID(as_uuid=True),
        ForeignKey("semesters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Current semester the user is participating in"
    )
    
    # Relationships
    sessions = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    
    semester = relationship(
        "Semester",
        back_populates="users"
    )
    
    companies = relationship(
        "Company",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    feature_flag_records = relationship(
        "FeatureFlag",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    game_events = relationship(
        "GameEvent",
        back_populates="user"
    )
    
    audit_logs_created = relationship(
        "AuditLog",
        back_populates="changed_by_user"
    )
    
    def __repr__(self) -> str:
        """String representation of the user."""
        return f"<User(email={self.email}, id={self.id})>"
    
    @property
    def display_name(self) -> str:
        """Get display name from email."""
        return self.email.split("@")[0]
    
    def has_feature(self, feature_name: str) -> bool:
        """Check if a feature flag is enabled for this user.
        
        Args:
            feature_name: Name of the feature to check
            
        Returns:
            Whether the feature is enabled
        """
        return self.feature_flags.get(feature_name, False)
    
    def get_preference(self, preference_key: str, default: Optional[any] = None) -> any:
        """Get a user preference value.
        
        Args:
            preference_key: The preference key to retrieve
            default: Default value if preference not set
            
        Returns:
            The preference value or default
        """
        return self.preferences.get(preference_key, default) 