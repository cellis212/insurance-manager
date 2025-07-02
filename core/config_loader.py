"""Semester configuration loader and validator.

Loads YAML configuration files for semesters, validates against schema,
and provides configuration data to the game engine.
"""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, date
from decimal import Decimal
import json
from functools import lru_cache

from pydantic import BaseModel, Field, ValidationError, validator
from pydantic.types import condate

from core.config import settings


class SemesterInfo(BaseModel):
    """Semester identification and timing information."""
    code: str = Field(..., pattern=r"^\d{4}_(SPRING|SUMMER|FALL|WINTER)$")
    name: str
    start_date: condate()
    end_date: condate()
    description: Optional[str] = None
    
    @validator('end_date')
    def end_after_start(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class BaseConfigurationRef(BaseModel):
    """Reference to a base GameConfiguration."""
    name: str
    version: int = Field(..., ge=1)


class PluginConfig(BaseModel):
    """Configuration for a single plugin."""
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)


class FeatureFlagConfig(BaseModel):
    """Feature flag configuration."""
    name: str
    enabled: bool
    scope: str = Field(..., pattern=r"^(global|semester|user|company)$")
    rollout_percentage: Optional[float] = Field(None, ge=0, le=100)


class ScheduledEvent(BaseModel):
    """Pre-scheduled game event."""
    turn: int = Field(..., ge=1)
    type: str
    config: Dict[str, Any] = Field(default_factory=dict)


class CustomRules(BaseModel):
    """Semester-specific custom rules."""
    scheduled_events: List[ScheduledEvent] = Field(default_factory=list)
    special_modifiers: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)


class ABTestGroup(BaseModel):
    """A/B test group configuration."""
    percentage: float = Field(..., ge=0, le=100)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ABTest(BaseModel):
    """A/B test configuration."""
    name: str
    description: Optional[str] = None
    groups: Dict[str, ABTestGroup]
    
    @validator('groups')
    def validate_percentages(cls, v):
        total = sum(group.percentage for group in v.values())
        if abs(total - 100.0) > 0.01:  # Allow small floating point errors
            raise ValueError(f'Group percentages must sum to 100, got {total}')
        return v


class DataCollectionConfig(BaseModel):
    """Data collection configuration."""
    enhanced_logging: bool = False
    decision_tracking: bool = False
    performance_metrics: List[str] = Field(default_factory=list)


class ExperimentConfig(BaseModel):
    """Research and experiment configuration."""
    ab_tests: List[ABTest] = Field(default_factory=list)
    data_collection: DataCollectionConfig = Field(default_factory=DataCollectionConfig)


class GradingComponent(BaseModel):
    """Grading component configuration."""
    name: str
    weight: float = Field(..., ge=0, le=1)
    metric: str


class GradingConfig(BaseModel):
    """Grading configuration."""
    enabled: bool = False
    components: List[GradingComponent] = Field(default_factory=list)
    
    @validator('components')
    def validate_weights(cls, v):
        if v:
            total = sum(comp.weight for comp in v)
            if abs(total - 1.0) > 0.01:  # Allow small floating point errors
                raise ValueError(f'Component weights must sum to 1.0, got {total}')
        return v


class ReminderConfig(BaseModel):
    """Notification reminder configuration."""
    timing: str  # e.g., "-3 hours" or "+1 hour"
    message: str


class NotificationConfig(BaseModel):
    """Notification configuration."""
    channels: List[str] = Field(default_factory=list)
    reminders: Dict[str, ReminderConfig] = Field(default_factory=dict)


class DevelopmentConfig(BaseModel):
    """Development/debug configuration."""
    fast_forward_enabled: bool = False
    debug_mode: bool = False
    bypass_deadlines: bool = False
    show_hidden_metrics: bool = False


class SemesterConfig(BaseModel):
    """Complete semester configuration."""
    version: str = Field(..., pattern=r"^\d+\.\d+$")
    schema_version: int = Field(..., ge=1)
    semester: SemesterInfo
    base_configuration: Optional[BaseConfigurationRef] = None
    game_parameters: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    plugins: Dict[str, PluginConfig] = Field(default_factory=dict)
    feature_flags: List[FeatureFlagConfig] = Field(default_factory=list)
    custom_rules: CustomRules = Field(default_factory=CustomRules)
    experiments: ExperimentConfig = Field(default_factory=ExperimentConfig)
    grading: GradingConfig = Field(default_factory=GradingConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    development: DevelopmentConfig = Field(default_factory=DevelopmentConfig)
    
    @validator('feature_flags')
    def unique_flag_names(cls, v):
        names = [flag.name for flag in v]
        if len(names) != len(set(names)):
            raise ValueError('Feature flag names must be unique')
        return v


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ConfigurationLoader:
    """Loads and validates semester configuration files."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the configuration loader.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = config_dir or Path("config/semester_configs")
        self.schema_path = self.config_dir / "schema.yaml"
        self._schema: Optional[Dict[str, Any]] = None
        
    @property
    @lru_cache(maxsize=1)
    def schema(self) -> Dict[str, Any]:
        """Load and cache the configuration schema."""
        if self.schema_path.exists():
            with open(self.schema_path, 'r') as f:
                return yaml.safe_load(f)
        return {}
    
    def load_config(self, config_path: Path) -> SemesterConfig:
        """Load and validate a semester configuration file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Validated semester configuration
            
        Raises:
            ConfigValidationError: If validation fails
            FileNotFoundError: If config file doesn't exist
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        # Load YAML file
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
        
        # Convert dates from strings
        self._convert_dates(raw_config)
        
        # Validate against Pydantic model
        try:
            config = SemesterConfig(**raw_config)
        except ValidationError as e:
            raise ConfigValidationError(f"Configuration validation failed: {e}")
        
        # Additional custom validation
        self._validate_custom_rules(config)
        
        # Environment-specific validation
        self._validate_environment(config)
        
        return config
    
    def _convert_dates(self, config: Dict[str, Any]) -> None:
        """Convert date strings to date objects in-place."""
        if 'semester' in config:
            semester = config['semester']
            if 'start_date' in semester and isinstance(semester['start_date'], str):
                semester['start_date'] = datetime.strptime(
                    semester['start_date'], '%Y-%m-%d'
                ).date()
            if 'end_date' in semester and isinstance(semester['end_date'], str):
                semester['end_date'] = datetime.strptime(
                    semester['end_date'], '%Y-%m-%d'
                ).date()
    
    def _validate_custom_rules(self, config: SemesterConfig) -> None:
        """Perform custom validation beyond Pydantic."""
        # Validate scheduled events are within semester duration
        if config.custom_rules.scheduled_events:
            # Calculate total turns in semester
            days = (config.semester.end_date - config.semester.start_date).days
            total_turns = days // 7  # Weekly turns
            
            for event in config.custom_rules.scheduled_events:
                if event.turn > total_turns:
                    raise ConfigValidationError(
                        f"Scheduled event at turn {event.turn} exceeds "
                        f"semester duration ({total_turns} turns)"
                    )
    
    def _validate_environment(self, config: SemesterConfig) -> None:
        """Apply environment-specific validation rules."""
        environment = os.getenv("ENVIRONMENT", "development")
        
        if environment == "production":
            # Require base configuration in production
            if not config.base_configuration:
                raise ConfigValidationError(
                    "base_configuration is required in production"
                )
            
            # Disallow development settings
            if config.development.debug_mode or config.development.bypass_deadlines:
                raise ConfigValidationError(
                    "Development settings not allowed in production"
                )
    
    def list_configs(self) -> List[Tuple[str, Path]]:
        """List all available configuration files.
        
        Returns:
            List of (semester_code, file_path) tuples
        """
        configs = []
        
        for file_path in self.config_dir.glob("*.yaml"):
            if file_path.name in ["schema.yaml", "example_semester.yaml"]:
                continue
                
            try:
                # Quick parse to get semester code
                with open(file_path, 'r') as f:
                    data = yaml.safe_load(f)
                    
                if 'semester' in data and 'code' in data['semester']:
                    configs.append((data['semester']['code'], file_path))
            except Exception:
                # Skip invalid files
                continue
        
        return sorted(configs)
    
    def load_config_by_code(self, semester_code: str) -> SemesterConfig:
        """Load configuration by semester code.
        
        Args:
            semester_code: Semester code (e.g., "2024_SPRING")
            
        Returns:
            Semester configuration
            
        Raises:
            ConfigValidationError: If no config found for code
        """
        for code, path in self.list_configs():
            if code == semester_code:
                return self.load_config(path)
        
        raise ConfigValidationError(
            f"No configuration found for semester: {semester_code}"
        )
    
    def validate_plugin_config(
        self, 
        plugin_name: str, 
        plugin_config: Dict[str, Any],
        available_plugins: Set[str]
    ) -> List[str]:
        """Validate plugin-specific configuration.
        
        Args:
            plugin_name: Name of the plugin
            plugin_config: Plugin configuration
            available_plugins: Set of discovered plugin names
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check if plugin exists
        if plugin_name not in available_plugins:
            errors.append(f"Unknown plugin: {plugin_name}")
        
        # Plugin-specific validation would go here
        # This would typically call the plugin's validate_config method
        
        return errors
    
    def merge_with_base(
        self, 
        semester_config: SemesterConfig,
        base_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge semester overrides with base configuration.
        
        Args:
            semester_config: Semester configuration
            base_params: Base game parameters
            
        Returns:
            Merged configuration
        """
        merged = base_params.copy()
        
        # Deep merge game parameters
        for category, overrides in semester_config.game_parameters.items():
            if category in merged:
                if isinstance(merged[category], dict) and isinstance(overrides, dict):
                    merged[category].update(overrides)
                else:
                    merged[category] = overrides
            else:
                merged[category] = overrides
        
        return merged
    
    def export_to_database_format(self, config: SemesterConfig) -> Dict[str, Any]:
        """Convert configuration to database storage format.
        
        Args:
            config: Semester configuration
            
        Returns:
            Dictionary ready for database storage
        """
        # Convert Pydantic models to dictionaries
        config_dict = config.dict()
        
        # Convert dates to ISO format strings
        config_dict['semester']['start_date'] = config.semester.start_date.isoformat()
        config_dict['semester']['end_date'] = config.semester.end_date.isoformat()
        
        # Separate different parameter categories for database fields
        game_params = config_dict.pop('game_parameters', {})
        
        return {
            'economic_overrides': game_params.get('economic', {}),
            'turn_overrides': game_params.get('turn', {}),
            'initial_value_overrides': game_params.get('initial_values', {}),
            'regulatory_overrides': game_params.get('regulatory', {}),
            'employee_overrides': game_params.get('employee', {}),
            'product_overrides': game_params.get('product', {}),
            'expansion_overrides': game_params.get('expansion', {}),
            'investment_overrides': game_params.get('investment', {}),
            'claims_overrides': game_params.get('claims', {}),
            'miscellaneous_overrides': game_params.get('miscellaneous', {}),
            'feature_overrides': {
                flag.name: flag.enabled 
                for flag in config.feature_flags
            },
            'custom_rules': config_dict['custom_rules'],
            'experiment_config': config_dict['experiments'],
            'schema_version': config.schema_version
        }


# Global configuration loader instance
config_loader = ConfigurationLoader() 