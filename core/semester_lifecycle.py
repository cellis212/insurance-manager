"""Semester lifecycle management for configuration-driven semesters.

This module handles the complete lifecycle of a semester including:
- Initialization from configuration files
- Mid-semester updates and feature toggles
- End-of-semester archival and reset
- Configuration hot-reloading for development
"""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from core.models import (
    Semester, SemesterConfiguration, GameConfiguration,
    FeatureFlag, Company, Turn
)
from core.config_loader import config_loader, SemesterConfig, ConfigValidationError
from core.semester_management import SemesterManager
from core.engine.plugin_manager import plugin_manager
from core.events import event_bus
from core.database import get_session

logger = logging.getLogger(__name__)


class SemesterLifecycleManager:
    """Manages the complete lifecycle of semesters using configuration files."""
    
    def __init__(self):
        """Initialize the lifecycle manager."""
        self.semester_manager = SemesterManager()
        self._active_semester: Optional[Semester] = None
        self._active_config: Optional[SemesterConfig] = None
        self._config_watchers: Dict[str, float] = {}  # Path -> last modified time
        
    async def initialize_from_config(
        self, 
        config_path: Path,
        session: AsyncSession
    ) -> Semester:
        """Initialize a new semester from a configuration file.
        
        Args:
            config_path: Path to the semester configuration YAML
            session: Database session
            
        Returns:
            Created semester instance
            
        Raises:
            ConfigValidationError: If configuration is invalid
            ValueError: If semester already exists
        """
        # Load and validate configuration
        config = config_loader.load_config(config_path)
        self._active_config = config
        
        # Check if semester already exists
        result = await session.execute(
            select(Semester).where(Semester.code == config.semester.code)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise ValueError(f"Semester {config.semester.code} already exists")
        
        # Get or create base game configuration
        base_config = None
        if config.base_configuration:
            result = await session.execute(
                select(GameConfiguration)
                .where(GameConfiguration.name == config.base_configuration.name)
                .where(GameConfiguration.version == config.base_configuration.version)
            )
            base_config = result.scalar_one_or_none()
            
            if not base_config:
                logger.warning(
                    f"Base configuration {config.base_configuration.name} "
                    f"v{config.base_configuration.version} not found"
                )
        
        # Create semester
        semester = await self.semester_manager.create_semester(
            code=config.semester.code,
            name=config.semester.name,
            start_date=config.semester.start_date,
            end_date=config.semester.end_date,
            configuration={
                "description": config.semester.description,
                "grading": config.grading.dict() if config.grading else {},
                "notifications": config.notifications.dict() if config.notifications else {},
                "development": config.development.dict() if config.development else {}
            }
        )
        
        # Create semester configuration
        db_config_data = config_loader.export_to_database_format(config)
        semester_config = SemesterConfiguration(
            semester_id=semester.id,
            base_configuration_id=base_config.id if base_config else None,
            **db_config_data
        )
        session.add(semester_config)
        
        # Create feature flags from configuration
        await self._create_feature_flags(config, semester.id, session)
        
        # Initialize plugins
        await plugin_manager.initialize(session, str(semester.id))
        
        # Schedule custom events if any
        await self._schedule_custom_events(config, semester.id, session)
        
        await session.commit()
        
        self._active_semester = semester
        
        # Emit initialization event
        await event_bus.emit(
            "semester.initialized",
            {
                "semester_id": str(semester.id),
                "code": semester.code,
                "config_path": str(config_path)
            },
            source="SemesterLifecycleManager"
        )
        
        logger.info(f"Initialized semester {semester.code} from {config_path}")
        
        return semester
    
    async def _create_feature_flags(
        self, 
        config: SemesterConfig,
        semester_id: str,
        session: AsyncSession
    ) -> None:
        """Create feature flags from configuration.
        
        Args:
            config: Semester configuration
            semester_id: Semester ID
            session: Database session
        """
        for flag_config in config.feature_flags:
            # Check if flag already exists
            result = await session.execute(
                select(FeatureFlag)
                .where(FeatureFlag.flag_name == flag_config.name)
                .where(FeatureFlag.scope == flag_config.scope)
                .where(FeatureFlag.semester_id == semester_id if flag_config.scope == "semester" else True)
            )
            existing = result.scalar_one_or_none()
            
            if not existing:
                flag = FeatureFlag(
                    flag_name=flag_config.name,
                    is_enabled=flag_config.enabled,
                    scope=flag_config.scope,
                    semester_id=semester_id if flag_config.scope == "semester" else None,
                    rollout_percentage=flag_config.rollout_percentage,
                    metadata={
                        "source": "semester_config",
                        "created_from": config.semester.code
                    }
                )
                session.add(flag)
    
    async def _schedule_custom_events(
        self,
        config: SemesterConfig,
        semester_id: str,
        session: AsyncSession
    ) -> None:
        """Schedule custom events from configuration.
        
        Args:
            config: Semester configuration
            semester_id: Semester ID
            session: Database session
        """
        # Custom events would be scheduled through the event system
        # This is a placeholder for future implementation
        for event in config.custom_rules.scheduled_events:
            await event_bus.emit(
                "semester.event_scheduled",
                {
                    "semester_id": semester_id,
                    "turn": event.turn,
                    "event_type": event.type,
                    "config": event.config
                },
                source="SemesterLifecycleManager"
            )
    
    async def update_feature_toggle(
        self,
        flag_name: str,
        enabled: bool,
        session: AsyncSession
    ) -> None:
        """Update a feature flag mid-semester.
        
        Args:
            flag_name: Name of the feature flag
            enabled: New enabled state
            session: Database session
        """
        if not self._active_semester:
            raise ValueError("No active semester")
        
        # Update database flag
        await session.execute(
            update(FeatureFlag)
            .where(FeatureFlag.flag_name == flag_name)
            .where(FeatureFlag.semester_id == self._active_semester.id)
            .values(is_enabled=enabled, updated_at=datetime.utcnow())
        )
        
        await session.commit()
        
        # Update plugin state if it's a plugin flag
        if flag_name.startswith("plugin."):
            plugin_name = flag_name.replace("plugin.", "")
            if enabled:
                await plugin_manager.enable_plugin(plugin_name)
            else:
                await plugin_manager.disable_plugin(plugin_name)
        
        # Emit update event
        await event_bus.emit(
            "semester.feature_toggled",
            {
                "semester_id": str(self._active_semester.id),
                "flag_name": flag_name,
                "enabled": enabled
            },
            source="SemesterLifecycleManager"
        )
        
        logger.info(f"Toggled feature {flag_name} to {enabled}")
    
    async def reload_configuration(
        self,
        config_path: Path,
        session: AsyncSession
    ) -> None:
        """Reload configuration from file (development only).
        
        Args:
            config_path: Path to the configuration file
            session: Database session
        """
        if not self._active_semester:
            raise ValueError("No active semester")
        
        # Check if in development mode
        if self._active_config and not self._active_config.development.debug_mode:
            raise ValueError("Configuration reload only available in development mode")
        
        # Load new configuration
        new_config = config_loader.load_config(config_path)
        
        # Validate semester code matches
        if new_config.semester.code != self._active_semester.code:
            raise ValueError(
                f"Semester code mismatch: {new_config.semester.code} != "
                f"{self._active_semester.code}"
            )
        
        # Update database configuration
        result = await session.execute(
            select(SemesterConfiguration)
            .where(SemesterConfiguration.semester_id == self._active_semester.id)
        )
        semester_config = result.scalar_one()
        
        # Update configuration fields
        db_config_data = config_loader.export_to_database_format(new_config)
        for key, value in db_config_data.items():
            setattr(semester_config, key, value)
        
        semester_config.updated_at = datetime.utcnow()
        
        # Update feature flags
        await self._update_feature_flags(new_config, session)
        
        # Reload plugins with new configuration
        await plugin_manager.initialize(session, str(self._active_semester.id))
        
        await session.commit()
        
        self._active_config = new_config
        
        # Emit reload event
        await event_bus.emit(
            "semester.config_reloaded",
            {
                "semester_id": str(self._active_semester.id),
                "config_path": str(config_path)
            },
            source="SemesterLifecycleManager"
        )
        
        logger.info(f"Reloaded configuration from {config_path}")
    
    async def _update_feature_flags(
        self,
        config: SemesterConfig,
        session: AsyncSession
    ) -> None:
        """Update feature flags from new configuration.
        
        Args:
            config: New semester configuration
            session: Database session
        """
        # Get existing flags
        result = await session.execute(
            select(FeatureFlag)
            .where(FeatureFlag.semester_id == self._active_semester.id)
        )
        existing_flags = {flag.flag_name: flag for flag in result.scalars()}
        
        # Update or create flags from config
        config_flags = {flag.name for flag in config.feature_flags}
        
        for flag_config in config.feature_flags:
            if flag_config.name in existing_flags:
                # Update existing flag
                flag = existing_flags[flag_config.name]
                flag.is_enabled = flag_config.enabled
                flag.rollout_percentage = flag_config.rollout_percentage
                flag.updated_at = datetime.utcnow()
            else:
                # Create new flag
                await self._create_feature_flags(config, str(self._active_semester.id), session)
        
        # Disable flags not in new config
        for flag_name, flag in existing_flags.items():
            if flag_name not in config_flags:
                flag.is_enabled = False
                flag.updated_at = datetime.utcnow()
    
    async def watch_config_changes(
        self,
        config_path: Path,
        interval: float = 1.0
    ) -> None:
        """Watch configuration file for changes (development only).
        
        Args:
            config_path: Path to watch
            interval: Check interval in seconds
        """
        if not self._active_config or not self._active_config.development.debug_mode:
            raise ValueError("Config watching only available in development mode")
        
        logger.info(f"Watching {config_path} for changes...")
        
        last_modified = config_path.stat().st_mtime
        self._config_watchers[str(config_path)] = last_modified
        
        while str(config_path) in self._config_watchers:
            await asyncio.sleep(interval)
            
            try:
                current_modified = config_path.stat().st_mtime
                if current_modified > last_modified:
                    logger.info(f"Configuration change detected in {config_path}")
                    
                    async with get_session() as session:
                        await self.reload_configuration(config_path, session)
                    
                    last_modified = current_modified
                    self._config_watchers[str(config_path)] = last_modified
                    
            except Exception as e:
                logger.error(f"Error checking configuration changes: {e}")
    
    def stop_watching(self, config_path: Optional[Path] = None) -> None:
        """Stop watching configuration file(s).
        
        Args:
            config_path: Specific path to stop watching, or None for all
        """
        if config_path:
            self._config_watchers.pop(str(config_path), None)
        else:
            self._config_watchers.clear()
    
    async def archive_semester(
        self,
        output_dir: Path,
        session: AsyncSession
    ) -> Path:
        """Archive semester data and configuration.
        
        Args:
            output_dir: Directory to save archive
            session: Database session
            
        Returns:
            Path to archive directory
        """
        if not self._active_semester:
            raise ValueError("No active semester")
        
        # Create archive directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = output_dir / f"{self._active_semester.code}_{timestamp}"
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Save configuration
        if self._active_config:
            config_file = archive_dir / "semester_config.yaml"
            shutil.copy2(
                config_loader.config_dir / f"{self._active_semester.code.lower()}.yaml",
                config_file
            )
        
        # Archive database data
        archive_path = await self.semester_manager.archive_semester(
            semester_id=str(self._active_semester.id),
            output_directory=archive_dir
        )
        
        # Save additional metadata
        metadata = {
            "semester_id": str(self._active_semester.id),
            "code": self._active_semester.code,
            "archived_at": datetime.utcnow().isoformat(),
            "total_companies": await self._count_companies(session),
            "total_turns": await self._count_turns(session),
            "configuration": self._active_config.dict() if self._active_config else None
        }
        
        with open(archive_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logger.info(f"Archived semester to {archive_dir}")
        
        return archive_dir
    
    async def _count_companies(self, session: AsyncSession) -> int:
        """Count companies in active semester."""
        from sqlalchemy import func
        result = await session.execute(
            select(func.count(Company.id))
            .where(Company.semester_id == self._active_semester.id)
        )
        return result.scalar() or 0
    
    async def _count_turns(self, session: AsyncSession) -> int:
        """Count turns in active semester."""
        from sqlalchemy import func
        result = await session.execute(
            select(func.count(Turn.id))
            .where(Turn.semester_id == self._active_semester.id)
        )
        return result.scalar() or 0
    
    async def reset_for_new_semester(
        self,
        new_config_path: Path,
        archive: bool = True,
        session: AsyncSession = None
    ) -> Semester:
        """Reset and prepare for a new semester.
        
        Args:
            new_config_path: Configuration for new semester
            archive: Whether to archive current semester
            session: Database session
            
        Returns:
            New semester instance
        """
        if self._active_semester and archive:
            # Archive current semester
            output_dir = Path("archives")
            output_dir.mkdir(exist_ok=True)
            await self.archive_semester(output_dir, session)
        
        # Clear active state
        self._active_semester = None
        self._active_config = None
        self.stop_watching()
        
        # Initialize new semester
        return await self.initialize_from_config(new_config_path, session)
    
    def get_active_config(self) -> Optional[SemesterConfig]:
        """Get the active semester configuration.
        
        Returns:
            Active configuration or None
        """
        return self._active_config
    
    def get_active_semester(self) -> Optional[Semester]:
        """Get the active semester.
        
        Returns:
            Active semester or None
        """
        return self._active_semester


# Global lifecycle manager instance
lifecycle_manager = SemesterLifecycleManager() 