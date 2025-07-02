"""Semester configuration model for semester-specific settings.

Allows overriding global game configuration and feature flags for
specific semesters, enabling experimentation and gradual rollouts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict, Any

from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    UniqueConstraint,
    Index,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models import Semester, GameConfiguration


class SemesterConfiguration(BaseModel):
    """Semester-specific configuration overrides.
    
    Allows each semester to customize game parameters, enable/disable features,
    and run experiments without affecting the global configuration.
    
    Attributes:
        semester_id: The semester this configuration applies to
        base_configuration_id: Optional base GameConfiguration to inherit from
        
        # Override parameters (null means use base/default)
        economic_overrides: Overrides for economic parameters
        turn_overrides: Overrides for turn parameters
        initial_value_overrides: Overrides for starting values
        regulatory_overrides: Overrides for regulatory parameters
        employee_overrides: Overrides for employee system
        product_overrides: Overrides for product tiers
        expansion_overrides: Overrides for expansion costs/rules
        investment_overrides: Overrides for investment system
        claims_overrides: Overrides for claims generation
        
        feature_overrides: Feature flags specific to this semester
        custom_rules: Special rules/events for this semester
        experiment_config: A/B testing or research configurations
        
        schema_version: Version of the configuration schema
    """
    
    __tablename__ = "semester_configurations"
    
    # Semester linkage
    semester_id = Column(
        UUID(as_uuid=True),
        ForeignKey('semesters.id', ondelete='CASCADE'),
        nullable=False,
        comment="The semester this configuration applies to"
    )
    
    # Optional base configuration
    base_configuration_id = Column(
        UUID(as_uuid=True),
        ForeignKey('game_configurations.id', ondelete='SET NULL'),
        nullable=True,
        comment="Base GameConfiguration to inherit from"
    )
    
    # Parameter overrides - null means use base configuration
    economic_overrides = Column(
        JSONB,
        nullable=True,
        comment="Overrides for economic parameters"
    )
    
    turn_overrides = Column(
        JSONB,
        nullable=True,
        comment="Overrides for turn timing parameters"
    )
    
    initial_value_overrides = Column(
        JSONB,
        nullable=True,
        comment="Overrides for starting values"
    )
    
    regulatory_overrides = Column(
        JSONB,
        nullable=True,
        comment="Overrides for regulatory parameters"
    )
    
    employee_overrides = Column(
        JSONB,
        nullable=True,
        comment="Overrides for employee system parameters"
    )
    
    product_overrides = Column(
        JSONB,
        nullable=True,
        comment="Overrides for product tier parameters"
    )
    
    expansion_overrides = Column(
        JSONB,
        nullable=True,
        comment="Overrides for expansion parameters"
    )
    
    investment_overrides = Column(
        JSONB,
        nullable=True,
        comment="Overrides for investment system parameters"
    )
    
    claims_overrides = Column(
        JSONB,
        nullable=True,
        comment="Overrides for claims generation parameters"
    )
    
    miscellaneous_overrides = Column(
        JSONB,
        nullable=True,
        comment="Overrides for miscellaneous parameters"
    )
    
    # Semester-specific feature flags
    feature_overrides = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="""Feature flags specific to this semester:
        {
            "enable_advanced_investments": true,
            "enable_middle_management": false,
            "enable_custom_products": false,
            "catastrophe_frequency_multiplier": 1.5,
            ...
        }"""
    )
    
    # Custom rules for this semester
    custom_rules = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="""Special rules or events for this semester:
        {
            "scheduled_catastrophes": [
                {"turn": 5, "type": "hurricane", "states": ["FL", "TX"]},
                ...
            ],
            "market_conditions": "recession",
            "special_bonuses": {...},
            ...
        }"""
    )
    
    # Research/experiment configuration
    experiment_config = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="""A/B testing or research experiment settings:
        {
            "experiment_name": "demand_elasticity_study",
            "treatment_groups": [
                {"group": "A", "company_ids": [...], "parameters": {...}},
                {"group": "B", "company_ids": [...], "parameters": {...}}
            ],
            "metrics_to_track": ["profitability", "market_share", ...],
            ...
        }"""
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
        back_populates="semester_configuration",
        foreign_keys=[semester_id]
    )
    
    base_configuration = relationship(
        "GameConfiguration",
        back_populates="semester_configurations",
        foreign_keys=[base_configuration_id]
    )
    
    # Constraints
    __table_args__ = (
        # One configuration per semester
        UniqueConstraint('semester_id', name='uq_semester_configuration_semester'),
        # Indexes for lookups
        Index('ix_semester_configuration_semester', 'semester_id'),
    )
    
    def get_parameter(self, category: str, key: str, default: Any = None) -> Any:
        """Get a parameter value, checking overrides first then base config.
        
        Args:
            category: Parameter category (e.g., 'economic_parameters')
            key: Parameter key within the category
            default: Default value if not found
            
        Returns:
            The parameter value from overrides, base config, or default
        """
        # Check for override first
        override_category = f"{category.replace('_parameters', '')}_overrides"
        override_data = getattr(self, override_category, None)
        
        if override_data and isinstance(override_data, dict):
            if key in override_data:
                return override_data[key]
        
        # Fall back to base configuration
        if self.base_configuration:
            return self.base_configuration.get_parameter(category, key, default)
            
        return default
    
    def get_feature_flag(self, feature_key: str, default: bool = False) -> bool:
        """Get a feature flag value for this semester.
        
        Args:
            feature_key: The feature flag key
            default: Default value if not found
            
        Returns:
            The feature flag value
        """
        if isinstance(self.feature_overrides, dict):
            return self.feature_overrides.get(feature_key, default)
        return default
    
    def merge_parameters(self, category: str) -> Dict[str, Any]:
        """Get merged parameters from base config and overrides.
        
        Args:
            category: Parameter category to merge
            
        Returns:
            Merged parameter dictionary
        """
        # Start with base configuration if available
        if self.base_configuration:
            base_params = getattr(self.base_configuration, category, {})
            merged = dict(base_params) if isinstance(base_params, dict) else {}
        else:
            merged = {}
        
        # Apply overrides
        override_category = f"{category.replace('_parameters', '')}_overrides"
        override_data = getattr(self, override_category, None)
        
        if override_data and isinstance(override_data, dict):
            merged.update(override_data)
            
        return merged
    
    def __repr__(self) -> str:
        return f"<SemesterConfiguration(semester_id={self.semester_id})>" 