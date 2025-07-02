"""Plugin manager for Insurance Manager game system.

This module handles the discovery, loading, and lifecycle management of
game system plugins. It ensures plugins are loaded in the correct order
based on dependencies and manages their initialization.
"""

import importlib
import inspect
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, Union
from collections import defaultdict
import pkgutil

from core.interfaces.game_system import GameSystemPlugin
from core.events.event_bus import event_bus, Event
from core.models import GameConfiguration, FeatureFlag, SemesterConfiguration, Semester
from core.config_loader import config_loader, SemesterConfig
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class PluginLoadError(Exception):
    """Raised when a plugin cannot be loaded."""
    pass


class PluginDependencyError(Exception):
    """Raised when plugin dependencies cannot be resolved."""
    pass


class PluginManager:
    """Manages the lifecycle of game system plugins.
    
    The plugin manager handles:
    - Plugin discovery from the features directory
    - Dependency resolution and load ordering
    - Plugin initialization and configuration
    - Feature flag integration
    - Plugin state management
    """
    
    def __init__(self):
        """Initialize the plugin manager."""
        self._plugins: Dict[str, GameSystemPlugin] = {}
        self._plugin_classes: Dict[str, Type[GameSystemPlugin]] = {}
        self._load_order: List[str] = []
        self._initialized = False
        self._game_config: Optional[Dict[str, Any]] = None
        self._semester_config: Optional[SemesterConfig] = None
        self._plugin_configs: Dict[str, Dict[str, Any]] = {}
        
    async def initialize(self, session: AsyncSession, semester_id: Optional[str] = None) -> None:
        """Initialize the plugin manager with game configuration.
        
        Args:
            session: Database session for loading configuration
            semester_id: Optional semester ID for semester-specific config
        """
        # Load game configuration
        self._game_config = await self._load_game_config(session, semester_id)
        
        # Discover available plugins
        self._discover_plugins()
        
        # Load enabled plugins
        await self._load_enabled_plugins(session, semester_id)
        
        # Initialize plugins in dependency order
        await self._initialize_plugins()
        
        self._initialized = True
        logger.info(f"Plugin manager initialized with {len(self._plugins)} plugins")
        
    async def _load_game_config(
        self, 
        session: AsyncSession, 
        semester_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load game configuration from database and merge with semester config.
        
        Args:
            session: Database session
            semester_id: Optional semester ID for specific config
            
        Returns:
            Game configuration dictionary
        """
        # Get active game configuration
        result = await session.execute(
            select(GameConfiguration)
            .where(GameConfiguration.is_active == True)
            .limit(1)
        )
        game_config = result.scalar_one_or_none()
        
        if not game_config:
            logger.warning("No active game configuration found, using defaults")
            base_config = {}
        else:
            # Build base configuration from all parameter fields
            base_config = {}
            param_fields = [
                'economic_parameters', 'turn_parameters', 'initial_values',
                'regulatory_parameters', 'employee_parameters', 'product_parameters',
                'expansion_parameters', 'investment_parameters', 'claims_parameters',
                'miscellaneous_parameters'
            ]
            
            for field in param_fields:
                params = getattr(game_config, field, {})
                if params and isinstance(params, dict):
                    # Remove '_parameters' suffix for config keys
                    key = field.replace('_parameters', '')
                    base_config[key] = params
        
        # Load semester-specific configuration if provided
        if semester_id:
            # Get semester to find its configuration
            semester_result = await session.execute(
                select(Semester).where(Semester.id == semester_id)
            )
            semester = semester_result.scalar_one_or_none()
            
            if semester:
                # Check for semester configuration in database
                config_result = await session.execute(
                    select(SemesterConfiguration)
                    .where(SemesterConfiguration.semester_id == semester_id)
                )
                semester_config = config_result.scalar_one_or_none()
                
                # Also check for YAML configuration file
                try:
                    yaml_config = config_loader.load_config_by_code(semester.code)
                    self._semester_config = yaml_config
                    
                    # Store plugin configurations
                    self._plugin_configs = {
                        name: plugin_cfg.config
                        for name, plugin_cfg in yaml_config.plugins.items()
                        if plugin_cfg.enabled
                    }
                    
                    # Merge with base configuration
                    base_config = config_loader.merge_with_base(yaml_config, base_config)
                    
                except Exception as e:
                    logger.info(f"No YAML config found for semester {semester.code}: {e}")
                
                # If database config exists, apply those overrides too
                if semester_config:
                    base_config = self._merge_db_config(base_config, semester_config)
        
        return base_config
    
    def _merge_db_config(
        self, 
        base_config: Dict[str, Any], 
        semester_config: SemesterConfiguration
    ) -> Dict[str, Any]:
        """Merge database semester configuration with base config.
        
        Args:
            base_config: Base configuration dictionary
            semester_config: Database semester configuration
            
        Returns:
            Merged configuration
        """
        merged = base_config.copy()
        
        # Map of config keys to database field names
        field_mapping = {
            'economic': 'economic_overrides',
            'turn': 'turn_overrides',
            'initial_values': 'initial_value_overrides',
            'regulatory': 'regulatory_overrides',
            'employee': 'employee_overrides',
            'product': 'product_overrides',
            'expansion': 'expansion_overrides',
            'investment': 'investment_overrides',
            'claims': 'claims_overrides',
            'miscellaneous': 'miscellaneous_overrides'
        }
        
        for key, field_name in field_mapping.items():
            overrides = getattr(semester_config, field_name, None)
            if overrides and isinstance(overrides, dict):
                if key in merged:
                    merged[key].update(overrides)
                else:
                    merged[key] = overrides
        
        return merged
    
    def _discover_plugins(self) -> None:
        """Discover all available plugins in the features directory."""
        features_path = Path(__file__).parent.parent.parent / "features"
        
        if not features_path.exists():
            logger.warning("Features directory not found")
            return
        
        # Iterate through feature packages
        for importer, modname, ispkg in pkgutil.iter_modules([str(features_path)]):
            if ispkg:
                feature_name = modname
                feature_module = f"features.{feature_name}"
                
                try:
                    # Try to import the plugin module
                    plugin_module_name = f"{feature_module}.plugin"
                    plugin_module = importlib.import_module(plugin_module_name)
                    
                    # Find GameSystemPlugin subclasses
                    for name, obj in inspect.getmembers(plugin_module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, GameSystemPlugin) and 
                            obj is not GameSystemPlugin):
                            
                            plugin_name = obj.__name__
                            self._plugin_classes[plugin_name] = obj
                            logger.debug(f"Discovered plugin: {plugin_name} in {feature_name}")
                            
                except ImportError as e:
                    # Plugin module doesn't exist, which is fine
                    logger.debug(f"No plugin module in {feature_name}: {str(e)}")
                except Exception as e:
                    logger.error(f"Error discovering plugin in {feature_name}: {str(e)}")
    
    async def _load_enabled_plugins(
        self, 
        session: AsyncSession, 
        semester_id: Optional[str] = None
    ) -> None:
        """Load plugins that are enabled via feature flags or semester config.
        
        Args:
            session: Database session
            semester_id: Optional semester ID for checking flags
        """
        # Determine which plugins to load
        plugins_to_load = set()
        
        # First check semester configuration if available
        if self._semester_config:
            # Load plugins enabled in semester config
            for plugin_name, plugin_cfg in self._semester_config.plugins.items():
                if plugin_cfg.enabled and plugin_name in self._plugin_classes:
                    plugins_to_load.add(plugin_name)
                    logger.info(f"Plugin {plugin_name} enabled via semester config")
        
        # Also check database feature flags
        result = await session.execute(
            select(FeatureFlag)
            .where(FeatureFlag.flag_name.like("plugin.%"))
            .where(FeatureFlag.is_enabled == True)
        )
        feature_flags = result.scalars().all()
        
        # Add plugins from feature flags
        for flag in feature_flags:
            plugin_name = flag.flag_name.replace("plugin.", "")
            if plugin_name in self._plugin_classes:
                # Check if flag applies to this context
                if await self._should_enable_plugin(flag, semester_id):
                    plugins_to_load.add(plugin_name)
                    logger.info(f"Plugin {plugin_name} enabled via feature flag")
        
        # If no plugins specified, load all discovered plugins (development mode)
        if not plugins_to_load and self._plugin_classes:
            logger.info("No plugins specified, loading all discovered plugins (dev mode)")
            plugins_to_load = set(self._plugin_classes.keys())
        
        # Instantiate plugins
        for plugin_name in plugins_to_load:
            try:
                plugin_class = self._plugin_classes[plugin_name]
                plugin_instance = plugin_class()
                self._plugins[plugin_name] = plugin_instance
                logger.info(f"Loaded plugin: {plugin_name}")
            except Exception as e:
                logger.error(f"Failed to instantiate plugin {plugin_name}: {str(e)}")
                raise PluginLoadError(f"Failed to load plugin {plugin_name}: {str(e)}")
    
    async def _should_enable_plugin(
        self, 
        flag: FeatureFlag, 
        semester_id: Optional[str] = None
    ) -> bool:
        """Check if a plugin should be enabled based on feature flag.
        
        Args:
            flag: Feature flag to check
            semester_id: Optional semester ID for context
            
        Returns:
            True if plugin should be enabled
        """
        # Check scope
        if flag.scope == "global":
            return True
        elif flag.scope == "semester" and semester_id:
            return str(flag.semester_id) == semester_id
        # TODO: Implement user/company scope checks
        
        return False
    
    async def _initialize_plugins(self) -> None:
        """Initialize plugins in dependency order."""
        # Resolve dependencies and determine load order
        self._load_order = self._resolve_dependencies()
        
        # Initialize plugins in order
        for plugin_name in self._load_order:
            plugin = self._plugins[plugin_name]
            try:
                # Merge game config with plugin-specific config
                plugin_config = self._game_config or {}
                if plugin_name in self._plugin_configs:
                    plugin_config = {
                        **plugin_config,
                        'plugin_config': self._plugin_configs[plugin_name]
                    }
                
                await plugin.initialize(plugin_config)
                logger.info(f"Initialized plugin: {plugin_name}")
                
                # Emit plugin initialized event
                await event_bus.emit(
                    "plugin.initialized",
                    {"plugin_name": plugin_name},
                    source="PluginManager"
                )
            except Exception as e:
                logger.error(f"Failed to initialize plugin {plugin_name}: {str(e)}")
                raise PluginLoadError(f"Failed to initialize plugin {plugin_name}: {str(e)}")
    
    def _resolve_dependencies(self) -> List[str]:
        """Resolve plugin dependencies and determine load order.
        
        Returns:
            List of plugin names in load order
            
        Raises:
            PluginDependencyError: If dependencies cannot be resolved
        """
        # Build dependency graph
        dependencies = {}
        for name, plugin in self._plugins.items():
            dependencies[name] = set(plugin.dependencies)
        
        # Topological sort
        load_order = []
        visited = set()
        temp_visited = set()
        
        def visit(name: str):
            if name in temp_visited:
                raise PluginDependencyError(f"Circular dependency detected: {name}")
            if name in visited:
                return
            
            temp_visited.add(name)
            
            # Visit dependencies first
            for dep in dependencies.get(name, set()):
                if dep not in self._plugins:
                    raise PluginDependencyError(
                        f"Plugin {name} depends on {dep}, which is not loaded"
                    )
                visit(dep)
            
            temp_visited.remove(name)
            visited.add(name)
            load_order.append(name)
        
        # Visit all plugins
        for name in self._plugins:
            visit(name)
        
        return load_order
    
    def get_plugin(self, name: str) -> Optional[GameSystemPlugin]:
        """Get a loaded plugin by name.
        
        Args:
            name: Plugin name
            
        Returns:
            Plugin instance or None if not loaded
        """
        return self._plugins.get(name)
    
    def get_all_plugins(self) -> Dict[str, GameSystemPlugin]:
        """Get all loaded plugins.
        
        Returns:
            Dictionary of plugin name to instance
        """
        return self._plugins.copy()
    
    def get_enabled_plugins(self) -> List[GameSystemPlugin]:
        """Get all enabled plugins in load order.
        
        Returns:
            List of enabled plugins
        """
        return [
            self._plugins[name] 
            for name in self._load_order 
            if self._plugins[name].enabled
        ]
    
    async def enable_plugin(self, name: str) -> None:
        """Enable a loaded plugin.
        
        Args:
            name: Plugin name
        """
        plugin = self._plugins.get(name)
        if plugin:
            plugin.enable()
            await event_bus.emit(
                "plugin.enabled",
                {"plugin_name": name},
                source="PluginManager"
            )
        else:
            raise ValueError(f"Plugin {name} not found")
    
    async def disable_plugin(self, name: str) -> None:
        """Disable a loaded plugin.
        
        Args:
            name: Plugin name
        """
        plugin = self._plugins.get(name)
        if plugin:
            plugin.disable()
            await event_bus.emit(
                "plugin.disabled",
                {"plugin_name": name},
                source="PluginManager"
            )
        else:
            raise ValueError(f"Plugin {name} not found")
    
    async def reload_plugin(self, name: str) -> None:
        """Reload a plugin (useful for development).
        
        Args:
            name: Plugin name to reload
        """
        if name not in self._plugin_classes:
            raise ValueError(f"Plugin class {name} not found")
        
        # Disable old instance if exists
        if name in self._plugins:
            await self.disable_plugin(name)
            del self._plugins[name]
        
        # Create new instance
        plugin_class = self._plugin_classes[name]
        plugin_instance = plugin_class()
        self._plugins[name] = plugin_instance
        
        # Re-initialize
        await plugin_instance.initialize(self._game_config or {})
        
        # Update load order
        self._load_order = self._resolve_dependencies()
        
        await event_bus.emit(
            "plugin.reloaded",
            {"plugin_name": name},
            source="PluginManager"
        )
    
    def validate_plugin_config(self, name: str, config: Dict[str, Any]) -> List[str]:
        """Validate configuration for a specific plugin.
        
        Args:
            name: Plugin name
            config: Configuration to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        plugin = self._plugins.get(name)
        if not plugin:
            return [f"Plugin {name} not found"]
        
        return plugin.validate_config(config)
    
    def get_plugin_statistics(self) -> Dict[str, Any]:
        """Get statistics about loaded plugins.
        
        Returns:
            Dictionary with plugin statistics
        """
        return {
            "total_discovered": len(self._plugin_classes),
            "total_loaded": len(self._plugins),
            "total_enabled": len([p for p in self._plugins.values() if p.enabled]),
            "load_order": self._load_order,
            "plugins": {
                name: {
                    "version": plugin.version,
                    "enabled": plugin.enabled,
                    "dependencies": plugin.dependencies
                }
                for name, plugin in self._plugins.items()
            }
        }
    
    # Turn processing integration methods
    
    async def on_turn_start(self, turn: Any, game_state: Dict[str, Any]) -> None:
        """Call all plugins' on_turn_start method.
        
        Args:
            turn: Current turn
            game_state: Shared game state
        """
        for plugin in self.get_enabled_plugins():
            try:
                await plugin.on_turn_start(turn, game_state)
            except Exception as e:
                logger.error(f"Plugin {plugin.name} failed in on_turn_start: {str(e)}")
                await event_bus.emit(
                    "plugin.error",
                    {
                        "plugin_name": plugin.name,
                        "method": "on_turn_start",
                        "error": str(e)
                    },
                    source="PluginManager"
                )
    
    async def on_decision_submitted(
        self, 
        company: Any, 
        decision: Any,
        game_state: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Call all plugins' on_decision_submitted method.
        
        Args:
            company: Company submitting decision
            decision: Decision submitted
            game_state: Shared game state
            
        Returns:
            Dictionary mapping plugin names to validation errors
        """
        all_errors = {}
        
        for plugin in self.get_enabled_plugins():
            try:
                result = await plugin.on_decision_submitted(company, decision, game_state)
                if result and not result.get("valid", True):
                    all_errors[plugin.name] = result.get("errors", [])
            except Exception as e:
                logger.error(f"Plugin {plugin.name} failed in on_decision_submitted: {str(e)}")
                all_errors[plugin.name] = [f"Plugin error: {str(e)}"]
        
        return all_errors
    
    async def calculate_results(
        self, 
        turn: Any,
        companies: List[Any],
        game_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call all plugins' calculate_results method.
        
        Args:
            turn: Current turn
            companies: List of companies
            game_state: Shared game state
            
        Returns:
            Merged results from all plugins
        """
        all_results = {}
        
        for plugin in self.get_enabled_plugins():
            try:
                plugin_results = await plugin.calculate_results(turn, companies, game_state)
                if plugin_results:
                    all_results[plugin.name] = plugin_results
            except Exception as e:
                logger.error(f"Plugin {plugin.name} failed in calculate_results: {str(e)}")
                await event_bus.emit(
                    "plugin.error",
                    {
                        "plugin_name": plugin.name,
                        "method": "calculate_results",
                        "error": str(e)
                    },
                    source="PluginManager"
                )
        
        return all_results
    
    async def on_turn_complete(
        self, 
        turn: Any,
        results: Dict[str, Any],
        game_state: Dict[str, Any]
    ) -> None:
        """Call all plugins' on_turn_complete method.
        
        Args:
            turn: Completed turn
            results: Turn results
            game_state: Shared game state
        """
        for plugin in self.get_enabled_plugins():
            try:
                await plugin.on_turn_complete(turn, results, game_state)
            except Exception as e:
                logger.error(f"Plugin {plugin.name} failed in on_turn_complete: {str(e)}")
                await event_bus.emit(
                    "plugin.error",
                    {
                        "plugin_name": plugin.name,
                        "method": "on_turn_complete",
                        "error": str(e)
                    },
                    source="PluginManager"
                )


# Global plugin manager instance
plugin_manager = PluginManager() 