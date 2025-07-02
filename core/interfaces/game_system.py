"""Game system plugin interface for Insurance Manager.

This module defines the abstract base class that all game system plugins
must implement to integrate with the core game engine.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from core.models import Turn, Company, CompanyTurnDecision


class GameSystemPlugin(ABC):
    """Abstract base class for game system plugins.
    
    All game features (CEO skills, employees, products, etc.) should be
    implemented as plugins that inherit from this interface. This allows
    features to be added without modifying the core engine.
    
    Plugins communicate through the event bus and should not directly
    import or depend on other plugins.
    """
    
    def __init__(self):
        """Initialize the plugin with its metadata."""
        self._name = self.__class__.__name__
        self._version = getattr(self, "VERSION", "1.0.0")
        self._dependencies: List[str] = getattr(self, "DEPENDENCIES", [])
        self._enabled = True
    
    @property
    def name(self) -> str:
        """Get the plugin name."""
        return self._name
    
    @property
    def version(self) -> str:
        """Get the plugin version."""
        return self._version
    
    @property
    def dependencies(self) -> List[str]:
        """Get list of plugin names this plugin depends on."""
        return self._dependencies
    
    @property
    def enabled(self) -> bool:
        """Check if the plugin is enabled."""
        return self._enabled
    
    def enable(self) -> None:
        """Enable the plugin."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable the plugin."""
        self._enabled = False
    
    @abstractmethod
    async def initialize(self, game_config: Dict[str, Any]) -> None:
        """Initialize the plugin with game configuration.
        
        Called once when the plugin is loaded. Use this to set up any
        required resources or validate configuration.
        
        Args:
            game_config: The current game configuration dictionary
        """
        pass
    
    @abstractmethod
    async def on_turn_start(self, turn: "Turn", game_state: Dict[str, Any]) -> None:
        """Called at the beginning of turn processing.
        
        Use this to set up any turn-specific state or perform pre-processing
        tasks like generating market conditions or updating employee states.
        
        Args:
            turn: The current turn being processed
            game_state: Shared game state dictionary that plugins can read/write
        """
        pass
    
    @abstractmethod
    async def on_decision_submitted(
        self, 
        company: "Company", 
        decision: "CompanyTurnDecision",
        game_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Called when a company submits decisions.
        
        Use this to validate decisions specific to your plugin's domain
        and potentially modify or enrich the decisions.
        
        Args:
            company: The company submitting decisions
            decision: The submitted turn decision
            game_state: Shared game state dictionary
            
        Returns:
            Optional validation result with 'valid' and 'errors' keys
        """
        pass
    
    @abstractmethod
    async def calculate_results(
        self, 
        turn: "Turn",
        companies: List["Company"],
        game_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate results for this plugin's game system.
        
        This is where the main simulation logic happens. Each plugin
        calculates its portion of the turn results.
        
        Args:
            turn: The current turn being processed
            companies: List of all companies in the game
            game_state: Shared game state dictionary
            
        Returns:
            Dictionary of results that will be merged into turn results
        """
        pass
    
    @abstractmethod
    async def on_turn_complete(
        self, 
        turn: "Turn",
        results: Dict[str, Any],
        game_state: Dict[str, Any]
    ) -> None:
        """Called after all turn processing is complete.
        
        Use this for cleanup, notifications, or preparing for the next turn.
        
        Args:
            turn: The completed turn
            results: The complete turn results
            game_state: Shared game state dictionary
        """
        pass
    
    async def on_company_bankrupt(
        self, 
        company: "Company",
        game_state: Dict[str, Any]
    ) -> None:
        """Called when a company goes bankrupt.
        
        Override this to handle bankruptcy-specific logic for your plugin.
        Default implementation does nothing.
        
        Args:
            company: The bankrupt company
            game_state: Shared game state dictionary
        """
        pass
    
    async def on_catastrophe(
        self, 
        event_type: str,
        affected_states: List[UUID],
        severity: float,
        game_state: Dict[str, Any]
    ) -> None:
        """Called when a catastrophe event occurs.
        
        Override this to handle catastrophe-specific logic for your plugin.
        Default implementation does nothing.
        
        Args:
            event_type: Type of catastrophe (hurricane, earthquake, etc.)
            affected_states: List of affected state IDs
            severity: Severity multiplier (1.0 = normal, higher = worse)
            game_state: Shared game state dictionary
        """
        pass
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Get the configuration schema for this plugin.
        
        Override this to define configuration options for your plugin.
        Should return a JSON schema dictionary.
        
        Returns:
            JSON schema for plugin configuration
        """
        return {}
    
    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate plugin configuration.
        
        Override this to implement custom configuration validation.
        
        Args:
            config: Plugin configuration to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        return [] 