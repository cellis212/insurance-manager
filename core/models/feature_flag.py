"""Feature flag model for progressive feature rollout.

Supports multiple scopes (global, semester, user, company) to enable
A/B testing and gradual feature deployment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict, Any
from uuid import UUID as PyUUID
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Enum,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
    DateTime,
    Integer,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models import Semester, User, Company


class FeatureFlag(BaseModel):
    """Feature flag for controlling feature availability.
    
    Features can be enabled/disabled at different scopes:
    - global: Affects all users/companies
    - semester: Specific to a semester
    - user: Specific to individual users
    - company: Specific to individual companies
    
    Attributes:
        feature_key: Unique identifier for the feature (e.g., 'advanced_investments')
        scope: Level at which the flag applies
        scope_id: ID of the specific scope entity (null for global)
        enabled: Whether the feature is enabled
        description: Human-readable description of the feature
        configuration: Additional feature-specific configuration
        rollout_percentage: For gradual rollouts (0-100)
        valid_from: When the flag becomes active
        valid_until: When the flag expires (null for permanent)
        schema_version: Version of the configuration schema
    """
    
    __tablename__ = "feature_flags"
    
    # Feature identification
    feature_key = Column(
        String(100),
        nullable=False,
        comment="Unique key identifying the feature"
    )
    
    # Scope definition
    scope = Column(
        Enum('global', 'semester', 'user', 'company', name='feature_scope'),
        nullable=False,
        default='global',
        comment="Level at which this flag applies"
    )
    
    # Scope-specific ID (nullable for global flags)
    semester_id = Column(
        UUID(as_uuid=True),
        ForeignKey('semesters.id', ondelete='CASCADE'),
        nullable=True,
        comment="Semester ID when scope is 'semester'"
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=True,
        comment="User ID when scope is 'user'"
    )
    
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=True,
        comment="Company ID when scope is 'company'"
    )
    
    # Flag status
    enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this feature is enabled"
    )
    
    # Metadata
    description = Column(
        String(500),
        nullable=True,
        comment="Human-readable description of what this feature enables"
    )
    
    # Configuration for the feature
    configuration = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Feature-specific configuration parameters"
    )
    
    # Gradual rollout support
    rollout_percentage = Column(
        Integer,
        nullable=False,
        default=100,
        comment="Percentage of entities that should see this feature (0-100)"
    )
    
    # Time-based activation
    valid_from = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this flag becomes active"
    )
    
    valid_until = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this flag expires (null for permanent)"
    )
    
    # Schema versioning
    schema_version = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Version of the configuration schema"
    )
    
    # Relationships
    semester = relationship(
        "Semester",
        back_populates="feature_flags",
        foreign_keys=[semester_id]
    )
    
    user = relationship(
        "User",
        back_populates="feature_flag_records",
        foreign_keys=[user_id]
    )
    
    company = relationship(
        "Company",
        back_populates="feature_flags",
        foreign_keys=[company_id]
    )
    
    # Constraints
    __table_args__ = (
        # Ensure only one flag per feature per scope entity
        UniqueConstraint(
            'feature_key', 'scope', 'semester_id', 'user_id', 'company_id',
            name='uq_feature_flag_scope'
        ),
        # Ensure scope matches the populated ID
        CheckConstraint(
            """
            (scope = 'global' AND semester_id IS NULL AND user_id IS NULL AND company_id IS NULL) OR
            (scope = 'semester' AND semester_id IS NOT NULL AND user_id IS NULL AND company_id IS NULL) OR
            (scope = 'user' AND semester_id IS NULL AND user_id IS NOT NULL AND company_id IS NULL) OR
            (scope = 'company' AND semester_id IS NULL AND user_id IS NULL AND company_id IS NOT NULL)
            """,
            name='ck_feature_flag_scope_consistency'
        ),
        # Ensure rollout percentage is valid
        CheckConstraint(
            'rollout_percentage >= 0 AND rollout_percentage <= 100',
            name='ck_feature_flag_rollout_percentage'
        ),
        # Index for quick lookups
        Index('ix_feature_flag_lookup', 'feature_key', 'scope', 'enabled'),
        Index('ix_feature_flag_validity', 'valid_from', 'valid_until'),
    )
    
    def is_active(self, check_time: Optional[datetime] = None) -> bool:
        """Check if the feature flag is currently active.
        
        Args:
            check_time: Time to check validity (defaults to now)
            
        Returns:
            True if the flag is enabled and within its validity period
        """
        if not self.enabled:
            return False
            
        check_time = check_time or datetime.utcnow()
        
        if self.valid_from and check_time < self.valid_from:
            return False
            
        if self.valid_until and check_time > self.valid_until:
            return False
            
        return True
    
    def should_show_to_entity(self, entity_id: PyUUID) -> bool:
        """Determine if an entity should see this feature based on rollout percentage.
        
        Uses consistent hashing to ensure the same entity always gets the same result.
        
        Args:
            entity_id: ID of the entity to check
            
        Returns:
            True if the entity should see this feature
        """
        if self.rollout_percentage >= 100:
            return True
        if self.rollout_percentage <= 0:
            return False
            
        # Use consistent hashing based on feature key and entity ID
        hash_input = f"{self.feature_key}:{entity_id}"
        hash_value = hash(hash_input)
        
        # Convert to percentage (0-100)
        entity_percentage = abs(hash_value) % 100
        
        return entity_percentage < self.rollout_percentage
    
    def __repr__(self) -> str:
        return (
            f"<FeatureFlag(feature_key='{self.feature_key}', "
            f"scope='{self.scope}', enabled={self.enabled})>"
        ) 