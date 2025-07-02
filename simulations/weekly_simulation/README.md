# Weekly Simulation Framework

This directory contains a comprehensive weekly simulation framework for the Insurance Manager game. The framework provides placeholder demand functions and orchestrates all simulation components for the weekly turn processing.

## Architecture Overview

The weekly simulation framework consists of several interconnected components:

### Core Components

1. **WeeklySimulationEngine** (`simulation_engine.py`)
   - Main orchestration engine for weekly simulations
   - Coordinates all simulation stages (market, operations, investments)
   - Integrates with the existing plugin system
   - Emits events for monitoring and logging

2. **Demand Functions** (`demand_functions.py`)
   - **PlaceholderDemandFunction**: Simple, predictable demand calculations for rapid development
   - **LinearDemandFunction**: Basic linear demand curve implementation
   - **DemandFunctionFactory**: Factory pattern for creating different demand functions
   - Extensible architecture for adding more sophisticated models (BLP, etc.)

3. **MarketSimulator** (`market_simulator.py`)
   - Simulates market dynamics for individual market segments
   - Calculates demand, market shares, and competitive effects
   - Uses configurable demand functions
   - Handles pricing decisions and market conditions

4. **OperationsSimulator** (`operations_simulator.py`)
   - Simulates company operations including claims, expenses, and underwriting
   - Integrates with existing claims simulation models
   - Calculates loss ratios, expense ratios, and combined ratios
   - Provides placeholder implementations with hooks for more complex models

5. **ResultsAggregator** (`results_aggregator.py`)
   - Combines results from all simulation components
   - Calculates final company financial positions
   - Updates database with turn results
   - Generates turn-level summary statistics

6. **Integration Module** (`integration.py`)
   - Provides integration utilities for the existing turn processing system
   - Migration functions for transitioning from legacy simulation code
   - Development and testing utilities
   - Configuration management

## Key Features

### Placeholder Demand Functions

The framework includes two placeholder demand functions designed for rapid development:

- **PlaceholderDemandFunction**: Uses simple price elasticity and competition effects
- **LinearDemandFunction**: Implements Q = a - b*P + c*X relationships

Both functions provide:
- Predictable, deterministic results for testing
- Configurable parameters for different market conditions
- Proper handling of edge cases (zero demand, no competition)
- Integration with the broader market simulation

### Plugin Architecture Integration

The framework integrates seamlessly with the existing plugin architecture:
- Uses the plugin manager for extensibility
- Emits events for monitoring and debugging
- Supports feature flags for gradual rollout
- Maintains backward compatibility with existing systems

### Database Integration

- Automatic creation of market conditions and price decisions
- Comprehensive result storage in `CompanyTurnResult`
- JSONB fields for detailed performance metrics
- Proper transaction handling and error recovery

## Usage Examples

### Basic Usage

```python
from simulations.weekly_simulation import WeeklySimulationEngine

# Initialize engine
engine = WeeklySimulationEngine()

# Configure demand function
engine.configure_demand_function(
    "placeholder",
    base_elasticity=-1.5,
    competition_factor=0.8
)

# Run simulation
results = await engine.process_weekly_turn(session, turn, game_state)
```

### Integration with Turn Processing

```python
from simulations.weekly_simulation.integration import run_enhanced_weekly_simulation

# Replace existing simulation in turn_processing.py
async def _simulate_markets(session, turn, game_state):
    results = await run_enhanced_weekly_simulation(session, turn, game_state)
    return results["market_results"]
```

### Testing Demand Functions

```python
from simulations.weekly_simulation.integration import test_placeholder_demand_function

# Test demand function with sample data
result = await test_placeholder_demand_function()
print(f"Market share: {result.market_share:.2%}")
```

## Configuration

The framework supports flexible configuration through:

- **Demand Function Parameters**: Elasticity, competition effects, randomness
- **Market Conditions**: Base demand, price elasticity, competitive intensity  
- **Operations Parameters**: Loss ratios, expense ratios, volatility
- **Investment Settings**: Return rates, risk profiles

Example configuration:

```python
config = {
    "demand_function": {
        "type": "placeholder",
        "parameters": {
            "base_elasticity": -1.5,
            "competition_factor": 0.8,
            "random_variation": 0.1
        }
    },
    "market_simulation": {
        "base_market_size": 1000000,
        "price_elasticity": -1.5,
        "competitive_intensity": 0.8
    }
}
```

## Extension Points

The framework is designed for easy extension:

1. **New Demand Functions**: Implement the `DemandFunction` interface
2. **Market Dynamics**: Extend `MarketSimulator` for complex market effects
3. **Claims Models**: Integrate with sophisticated actuarial models
4. **Investment Strategies**: Add portfolio optimization algorithms
5. **Plugin Integration**: Create specialized plugins for advanced features

## Development Guidelines

### Adding New Demand Functions

1. Inherit from `DemandFunction` abstract base class
2. Implement `calculate_demand()` and `get_price_elasticity()` methods
3. Add to `DemandFunctionFactory`
4. Create unit tests with known inputs/outputs
5. Document parameters and use cases

### Testing Strategy

- Use placeholder functions for predictable test results
- Test with various market conditions and company states
- Validate financial calculations and ratios
- Ensure database transactions work correctly
- Test error handling and recovery scenarios

### Performance Considerations

- Simulation runs for all companies every Monday at midnight
- Target: Complete processing within 15 minutes for 1000+ players
- Use async/await for database operations
- Cache market conditions and reuse calculations where possible
- Monitor memory usage with large datasets

## Integration with Turn Processing

The weekly simulation integrates with the existing turn processing system in `core/tasks/turn_processing.py`:

1. **Market Simulation Stage**: Replace `_simulate_markets()` with enhanced market simulation
2. **Operations Stage**: Use `OperationsSimulator` for comprehensive operations modeling
3. **Investment Stage**: Integrate investment portfolio simulation
4. **Results Processing**: Use `ResultsAggregator` for final result compilation

The integration preserves all existing interfaces while providing enhanced functionality through the new simulation components.

## Future Enhancements

The framework provides hooks for future enhancements:

- **BLP Demand Models**: Integration with existing BLP implementation
- **Advanced Claims Models**: Catastrophe modeling, adverse selection
- **Investment Optimization**: Portfolio optimization with risk constraints
- **Regulatory Simulation**: State-specific regulatory effects
- **CEO Skill Effects**: Skill-based modifiers for simulation outcomes
- **Real-Time Updates**: WebSocket integration for live simulation monitoring

## Development Status

- ✅ Basic framework implemented with placeholder demand functions
- ✅ Integration utilities for existing turn processing system  
- ✅ Comprehensive result aggregation and database storage
- ✅ Plugin system integration and event handling
- ⚠️ Some import errors need resolution (SQLAlchemy, asset simulation modules)
- 🔄 Testing and validation with real game data needed
- 🔄 Performance optimization for large-scale deployment

The framework is ready for development and testing, with clear paths for extending functionality as the game evolves.