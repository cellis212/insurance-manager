"""Session model for user authentication sessions.

Manages authentication tokens and session expiration.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.user import User


class Session(BaseModel):
    """Authentication session for logged-in users.
    
    Stores session tokens with expiration times for secure authentication.
    Sessions are automatically cleaned up when expired.
    """
    
    __tablename__ = "sessions"
    
    # User association
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User this session belongs to"
    )
    
    # Token information
    token_hash = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Hashed session token for security"
    )
    
    # Session metadata
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When this session expires"
    )
    
    ip_address = Column(
        String(45),  # Supports IPv6
        nullable=True,
        comment="IP address of the session creation"
    )
    
    user_agent = Column(
        String(500),
        nullable=True,
        comment="User agent string from the browser"
    )
    
    # Relationships
    user = relationship(
        "User",
        back_populates="sessions"
    )
    
    def __repr__(self) -> str:
        """String representation of the session."""
        return f"<Session(user_id={self.user_id}, expires_at={self.expires_at})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if the session has expired.
        
        Returns:
            Whether the session is expired
        """
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)
    
    @property
    def time_until_expiry(self) -> float:
        """Get seconds until session expires.
        
        Returns:
            Seconds until expiration (negative if expired)
        """
        delta = self.expires_at.replace(tzinfo=None) - datetime.utcnow()
        return delta.total_seconds() 