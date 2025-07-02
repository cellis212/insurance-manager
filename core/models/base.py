"""Base model classes for Insurance Manager.

Provides base classes with common fields and functionality
that all database models inherit from.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamp fields."""
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the record was created"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when the record was last updated"
    )


class BaseModel(Base, TimestampMixin):
    """Abstract base model with common fields for all models.
    
    Provides:
    - UUID primary key
    - created_at/updated_at timestamps
    - Common utility methods
    """
    
    __abstract__ = True
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Unique identifier for the record"
    )
    
    def __repr__(self) -> str:
        """String representation of the model."""
        return f"<{self.__class__.__name__}(id={self.id})>"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert model instance to dictionary.
        
        Returns:
            Dictionary representation of the model
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name for this model.
        
        Returns:
            The table name
        """
        return cls.__tablename__ 