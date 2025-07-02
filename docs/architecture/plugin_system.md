# Plugin Architecture Documentation

## Overview

The Insurance Manager uses a plugin-based architecture that allows game features to be added without modifying the core engine. This enables rapid development, easy testing, and semester-based feature rollouts.

## Architecture Components

### 1. GameSystemPlugin Interface

All plugins must inherit from `core.interfaces.GameSystemPlugin` and implement the required methods:

```python
from core.interfaces import GameSystemPlugin

class MyPlugin(GameSystemPlugin):
    VERSION = "1.0.0"
    DEPENDENCIES = ["OtherPlugin"]  # Optional
    
    async def initialize(self, game_config: Dict[str, Any]) -> None:
        """Initialize plugin with game configuration."""
        pass
    
    async def on_turn_start(self, turn: Turn, game_state: Dict[str, Any]) -> None:
        """Called at the beginning of each turn."""
        pass
    
    async def on_decision_submitted(
        self, 
        company: Company, 
        decision: CompanyTurnDecision,
        game_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Validate company decisions. Return None if valid."""
        pass
    
    async def calculate_results(
        self, 
        turn: Turn,
        companies: List[Company],
        game_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate plugin-specific results."""
        pass
    
    async def on_turn_complete(
        self, 
        turn: Turn,
        results: Dict[str, Any],
        game_state: Dict[str, Any]
    ) -> None:
        """Called after turn processing completes."""
        pass
```

### 2. Event Bus

Plugins communicate through an asynchronous event bus:

```python
from core.events import event_bus, on_event, EventPriority

# Emit an event
await event_bus.emit(
    "company.expanded",
    {"company_id": str(company.id), "state": "NY"},
    source="ExpansionPlugin"
)

# Listen for events (method 1: decorator)
@on_event("company.expanded", priority=EventPriority.HIGH)
async def handle_expansion(event: Event):
    company_id = event.data["company_id"]
    # React to expansion

# Listen for events (method 2: manual registration)
event_bus.register(
    "turn.started",
    my_handler_function,
    priority=EventPriority.NORMAL,
    plugin_name="MyPlugin"
)
```

### 3. Plugin Manager

The plugin manager handles:
- Plugin discovery from the `features/` directory
- Dependency resolution
- Initialization in correct order
- Feature flag integration

## Creating a Plugin

### Step 1: Create Plugin Structure

```
features/
└── my_feature/
    ├── __init__.py
    ├── plugin.py         # Required: Contains plugin class
    ├── models.py         # Optional: Feature-specific models
    ├── calculations.py   # Optional: Business logic
    └── tests/           # Optional: Plugin tests
```

### Step 2: Implement Plugin Class

```python
# features/my_feature/plugin.py
from core.interfaces import GameSystemPlugin
from core.events import event_bus

class MyFeaturePlugin(GameSystemPlugin):
    VERSION = "1.0.0"
    DEPENDENCIES = []  # List other plugins this depends on
    
    async def initialize(self, game_config: Dict[str, Any]) -> None:
        """Initialize plugin."""
        # Load configuration
        self.config = game_config.get("my_feature", {})
        
        # Register event handlers
        event_bus.register(
            "turn.started",
            self._handle_turn_start,
            plugin_name=self.name
        )
    
    async def on_turn_start(self, turn: Turn, game_state: Dict[str, Any]) -> None:
        """Prepare for turn processing."""
        # Initialize turn-specific data
        game_state["my_feature_data"] = {}
    
    async def calculate_results(
        self, 
        turn: Turn,
        companies: List[Company],
        game_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate feature-specific results."""
        results = {}
        
        # Access shared game state
        market_results = game_state.get("market_results", {})
        
        # Perform calculations
        for company in companies:
            results[str(company.id)] = self._calculate_for_company(
                company, market_results
            )
        
        return results
```

### Step 3: Enable Plugin

Plugins are enabled via feature flags in the database:

```sql
INSERT INTO feature_flags (
    flag_name,
    is_enabled,
    scope,
    description
) VALUES (
    'plugin.MyFeaturePlugin',
    true,
    'global',
    'Enables the my_feature plugin'
);
```

## Plugin Communication Patterns

### 1. Shared Game State

The `game_state` dictionary is passed to all plugin methods and allows sharing data:

```python
# In one plugin
game_state["market_conditions"] = calculate_market_conditions()

# In another plugin
market_conditions = game_state.get("market_conditions", {})
```

### 2. Event-Driven Communication

Use events for decoupled communication:

```python
# Plugin A emits an event
await event_bus.emit(
    "price.changed",
    {
        "company_id": str(company.id),
        "old_price": 100,
        "new_price": 120
    },
    source=self.name
)

# Plugin B reacts to the event
@on_event("price.changed")
async def handle_price_change(event: Event):
    # React to price change
    pass
```

### 3. Plugin Dependencies

Declare dependencies to ensure correct initialization order:

```python
class AdvancedPricingPlugin(GameSystemPlugin):
    DEPENDENCIES = ["MarketEventsPlugin", "CompetitorAnalysisPlugin"]
```

## Best Practices

### 1. Plugin Isolation

- Plugins should not import from other plugins directly
- Use events and shared game state for communication
- Each plugin should be independently testable

### 2. Error Handling

- Plugins should handle their own errors gracefully
- Failed plugins should not crash the turn processing
- Use logging for debugging

```python
try:
    result = await risky_calculation()
except Exception as e:
    logger.error(f"Plugin {self.name} calculation failed: {e}")
    return {}  # Return empty results rather than crashing
```

### 3. Performance Considerations

- Avoid blocking operations in plugin methods
- Use async/await for I/O operations
- Cache expensive calculations in game_state

### 4. Configuration

- Use the game configuration system for plugin settings
- Provide sensible defaults
- Validate configuration in `validate_config()`

```python
def get_config_schema(self) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "my_feature": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "threshold": {"type": "number"}
                }
            }
        }
    }
```

## Testing Plugins

### Unit Testing

```python
import pytest
from features.my_feature.plugin import MyFeaturePlugin

@pytest.mark.asyncio
async def test_plugin_initialization():
    plugin = MyFeaturePlugin()
    await plugin.initialize({"my_feature": {"enabled": True}})
    assert plugin.enabled
```

### Integration Testing

```python
@pytest.mark.asyncio
async def test_plugin_in_turn_processing():
    # Initialize plugin manager
    await plugin_manager.initialize(session)
    
    # Create test data
    turn = create_test_turn()
    companies = create_test_companies()
    
    # Run plugin calculations
    game_state = {}
    await plugin_manager.on_turn_start(turn, game_state)
    results = await plugin_manager.calculate_results(turn, companies, game_state)
    
    assert "MyFeaturePlugin" in results
```

## Available Events

Common events emitted by the core system:

- `turn.started` - Turn processing begins
- `turn.completed` - Turn processing completes
- `turn.failed` - Turn processing fails
- `company.bankrupt` - Company goes bankrupt
- `plugin.initialized` - Plugin is initialized
- `plugin.error` - Plugin encounters an error

## Example: Market Events Plugin

See `features/market_events/plugin.py` for a complete example that demonstrates:

- Implementing all required methods
- Using the event bus
- Modifying game state
- Validating decisions based on plugin state
- Calculating plugin-specific results

## Debugging

### Enable Debug Logging

```python
import logging
logging.getLogger("core.engine.plugin_manager").setLevel(logging.DEBUG)
logging.getLogger("core.events.event_bus").setLevel(logging.DEBUG)
```

### View Plugin Statistics

```python
stats = plugin_manager.get_plugin_statistics()
print(f"Loaded plugins: {stats['plugins']}")
```

### View Event History

```python
events = event_bus.get_event_history(event_type="turn.started", limit=10)
for event in events:
    print(f"{event.timestamp}: {event.event_type} from {event.source}")
```

## Future Plugin Ideas

- **CEO System**: Implement CEO attributes and progression
- **Employee Management**: Hiring, skills, and productivity
- **Advanced Products**: Custom product design and pricing
- **Expansion Strategy**: Complex expansion requirements
- **Investment Strategies**: Sophisticated portfolio management
- **Competitor AI**: Intelligent competitor behavior
- **Regulatory Events**: Dynamic regulatory changes
- **Economic Cycles**: Boom/bust cycle simulation 