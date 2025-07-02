"""Game engine for Insurance Manager.

This module contains the core game engine components including the
plugin manager and turn processing integration.
"""

from .plugin_manager import PluginManager, plugin_manager, PluginLoadError, PluginDependencyError

__all__ = [
    "PluginManager",
    "plugin_manager",
    "PluginLoadError",
    "PluginDependencyError"
] 