"""Game configuration model for global game parameters.

Stores versioned configurations that define game mechanics, economic parameters,
and other settings that apply across all semesters unless overridden.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    DateTime,
    CheckConstraint,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models import SemesterConfiguration


class GameConfiguration(BaseModel):
    """Global game configuration settings.
    
    Stores all configurable game parameters including economic formulas,
    turn timing, initial values, and game mechanics. Configurations are
    versioned to support changes over time.
    
    Attributes:
        name: Human-readable name for this configuration
        version: Sequential version number
        is_active: Whether this is the currently active configuration
        valid_from: When this configuration becomes valid
        valid_until: When this configuration expires
        
        # Core game parameters (stored in JSONB)
        economic_parameters: Market dynamics, elasticities, etc.
        turn_parameters: Timing, deadlines, processing windows
        initial_values: Starting capital, default values
        regulatory_parameters: State categories, requirements
        employee_parameters: Skill ranges, salary formulas
        product_parameters: Tier definitions, effects
        expansion_parameters: Cost formulas, timing
        investment_parameters: Asset classes, return models
        claims_parameters: Frequency/severity distributions
        
        schema_version: Version of the configuration schema
    """
    
    __tablename__ = "game_configurations"
    
    # Configuration identification
    name = Column(
        String(255),
        nullable=False,
        comment="Human-readable name for this configuration"
    )
    
    version = Column(
        Integer,
        nullable=False,
        comment="Sequential version number"
    )
    
    is_active = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is the currently active configuration"
    )
    
    # Validity period
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="NOW()",
        comment="When this configuration becomes valid"
    )
    
    valid_until = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this configuration expires (null for permanent)"
    )
    
    # Game parameters organized by category
    economic_parameters = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="""Economic and market parameters:
        {
            "base_demand_multiplier": 1.0,
            "price_elasticity": {"auto": -1.2, "home": -0.8, ...},
            "cross_price_elasticity": 0.3,
            "market_growth_rate": 0.03,
            "inflation_rate": 0.02,
            "interest_rates": {"risk_free": 0.03, "corporate": 0.05},
            ...
        }"""
    )
    
    turn_parameters = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="""Turn timing and processing parameters:
        {
            "turn_duration_days": 7,
            "decision_deadline": "Sunday 23:59:59 EST",
            "processing_start": "Monday 00:00:00 EST",
            "max_processing_minutes": 900,
            "late_submission_penalty": 0.05,
            ...
        }"""
    )
    
    initial_values = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="""Starting values for new companies:
        {
            "starting_capital": 5000000,
            "home_state_discount": 0.5,
            "initial_solvency_ratio": 3.0,
            "base_expense_ratio": 0.25,
            ...
        }"""
    )
    
    regulatory_parameters = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="""Regulatory system parameters:
        {
            "categories": {
                "strict": {"capital_multiplier": 1.5, "approval_weeks": 6},
                "moderate": {"capital_multiplier": 1.2, "approval_weeks": 4},
                "light": {"capital_multiplier": 1.0, "approval_weeks": 2}
            },
            "base_compliance_cost": 50000,
            "audit_probability": 0.1,
            ...
        }"""
    )
    
    employee_parameters = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="""Employee system parameters:
        {
            "skill_ranges": {"min": 10, "max": 100},
            "salary_formula": {"base": 100000, "skill_multiplier": 2000},
            "productivity_curve": "logarithmic",
            "hiring_pool_size": 5,
            ...
        }"""
    )
    
    product_parameters = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="""Product tier parameters:
        {
            "tiers": {
                "basic": {"price_modifier": 0.8, "risk_selection": 1.3},
                "standard": {"price_modifier": 1.0, "risk_selection": 1.0},
                "premium": {"price_modifier": 1.3, "risk_selection": 0.9}
            },
            "switching_cost": 100000,
            "switching_weeks": 2,
            ...
        }"""
    )
    
    expansion_parameters = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="""Geographic expansion parameters:
        {
            "base_expansion_cost": 500000,
            "distance_multiplier_formula": "1 + (distance / 1000)",
            "market_size_multiplier": true,
            "approval_weeks_base": 4,
            ...
        }"""
    )
    
    investment_parameters = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="""Investment system parameters:
        {
            "asset_classes": ["stocks", "bonds", "real_estate", "alternatives"],
            "return_models": {...},
            "risk_correlation_matrix": [...],
            "liquidity_premiums": {...},
            "cfo_skill_noise_formula": "1 - (skill / 100)",
            ...
        }"""
    )
    
    claims_parameters = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="""Claims generation parameters:
        {
            "frequency_distributions": {...},
            "severity_distributions": {...},
            "catastrophe_probabilities": {...},
            "adverse_selection_factors": {...},
            ...
        }"""
    )
    
    # Misc game settings
    miscellaneous_parameters = Column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Additional parameters not covered by other categories"
    )
    
    # Schema versioning
    schema_version = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Version of the configuration schema"
    )
    
    # Relationships
    semester_configurations = relationship(
        "SemesterConfiguration",
        back_populates="base_configuration",
        cascade="all, delete-orphan"
    )
    
    # Constraints
    __table_args__ = (
        # Only one configuration can be active at a time
        Index(
            'uq_game_configuration_active',
            'is_active',
            unique=True,
            postgresql_where='is_active = true'
        ),
        # Version numbers must be unique
        UniqueConstraint('version', name='uq_game_configuration_version'),
        # Indexes for lookups
        Index('ix_game_configuration_active', 'is_active', 'valid_from'),
        Index('ix_game_configuration_validity', 'valid_from', 'valid_until'),
    )
    
    def get_parameter(self, category: str, key: str, default: Any = None) -> Any:
        """Get a specific parameter value.
        
        Args:
            category: Parameter category (e.g., 'economic_parameters')
            key: Parameter key within the category
            default: Default value if not found
            
        Returns:
            The parameter value or default
        """
        category_data = getattr(self, category, {})
        if isinstance(category_data, dict):
            return category_data.get(key, default)
        return default
    
    def is_valid_at(self, check_time: Optional[datetime] = None) -> bool:
        """Check if this configuration is valid at a given time.
        
        Args:
            check_time: Time to check (defaults to now)
            
        Returns:
            True if the configuration is valid at the given time
        """
        check_time = check_time or datetime.utcnow()
        
        if check_time < self.valid_from:
            return False
            
        if self.valid_until and check_time > self.valid_until:
            return False
            
        return True
    
    def __repr__(self) -> str:
        return (
            f"<GameConfiguration(name='{self.name}', version={self.version}, "
            f"is_active={self.is_active})>"
        ) 