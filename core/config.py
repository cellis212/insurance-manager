"""Application configuration using Pydantic settings management.

Loads configuration from environment variables with validation
and type conversion.
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "Insurance Manager"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, description="Debug mode")
    testing: bool = Field(default=False, description="Testing mode")
    
    # Database
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/insurance_manager",
        description="PostgreSQL connection URL"
    )
    
    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    
    # Security
    secret_key: str = Field(
        default="your-secret-key-here-change-in-production",
        description="Secret key for JWT encoding"
    )
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=30, 
        description="Access token expiration in minutes"
    )
    
    # Celery
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        description="Celery broker URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2", 
        description="Celery result backend URL"
    )
    
    # Game Configuration
    turn_processing_day: str = Field(
        default="monday",
        description="Day of week for turn processing"
    )
    turn_processing_hour: int = Field(
        default=0,
        description="Hour for turn processing (0-23)"
    )
    turn_processing_timezone: str = Field(
        default="America/New_York",
        description="Timezone for turn processing"
    )
    
    # Semester Configuration
    semester_id: Optional[str] = Field(
        default=None,
        description="Current semester ID"
    )
    semester_config_path: str = Field(
        default="config/semester_configs/current.yaml",
        description="Path to current semester configuration"
    )
    
    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL is properly formatted."""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("Database URL must be a PostgreSQL connection string")
        return v
    
    @field_validator("turn_processing_hour")
    @classmethod
    def validate_hour(cls, v: int) -> int:
        """Ensure hour is in valid range."""
        if not 0 <= v <= 23:
            raise ValueError("Hour must be between 0 and 23")
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings() 