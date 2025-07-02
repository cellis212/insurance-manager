"""Integration module for weekly simulation with turn processing.

This module provides utilities to integrate the weekly simulation engine
with the existing turn processing system in core/tasks/turn_processing.py.
"""

import logging
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Turn
from .simulation_engine import WeeklySimulationEngine

logger = logging.getLogger(__name__)


async def run_enhanced_weekly_simulation(
    session: AsyncSession,
    turn: Turn,
    game_state: Dict
) -> Dict:
    """Run enhanced weekly simulation using the new simulation engine.
    
    This function can be called from the existing turn processing system
    to replace or supplement the basic simulation functions.
    
    Args:
        session: Database session
        turn: Turn being processed
        game_state: Shared game state from turn processor
        
    Returns:
        Dictionary containing comprehensive simulation results
    """
    logger.info(f"Running enhanced weekly simulation for turn {turn.id}")
    
    # Initialize simulation engine
    simulation_engine = WeeklySimulationEngine()
    
    # Configure demand function (can be made configurable)
    simulation_engine.configure_demand_function(
        "placeholder",  # Use placeholder for now
        base_elasticity=-1.5,
        competition_factor=0.8
    )
    
    # Run the simulation
    results = await simulation_engine.process_weekly_turn(
        session, turn, game_state
    )
    
    logger.info(f"Enhanced simulation completed for turn {turn.id}")
    return results


def get_simulation_config() -> Dict:
    """Get default configuration for the weekly simulation.
    
    Returns:
        Dictionary with simulation configuration
    """
    return {
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
        },
        "operations_simulation": {
            "base_loss_ratio": 0.65,
            "expense_ratio": 0.20,
            "volatility_factor": 0.2
        },
        "investment_simulation": {
            "base_return_rate": 0.02,
            "volatility_range": [0.8, 1.2]
        }
    }


async def migrate_existing_simulation_functions(
    session: AsyncSession,
    turn: Turn,
    game_state: Dict
) -> Dict:
    """Migrate from existing simulation functions to new weekly simulation.
    
    This function can be used to gradually transition from the existing
    simulation functions in turn_processing.py to the new comprehensive
    weekly simulation system.
    
    Args:
        session: Database session
        turn: Turn being processed
        game_state: Shared game state
        
    Returns:
        Dictionary with migration results
    """
    logger.info("Migrating to new weekly simulation system")
    
    # Run both old and new simulations for comparison
    try:
        # Run new simulation
        new_results = await run_enhanced_weekly_simulation(session, turn, game_state)
        
        # TODO: Run existing simulation functions for comparison
        # This would call the existing functions from turn_processing.py
        # old_results = await run_legacy_simulation(session, turn, game_state)
        
        # For now, just return the new results
        migration_results = {
            "migration_status": "success",
            "new_simulation_results": new_results,
            "comparison_notes": "Legacy simulation comparison not yet implemented"
        }
        
        return migration_results
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}", exc_info=True)
        return {
            "migration_status": "failed",
            "error": str(e),
            "fallback_used": False
        }


# Example usage functions for testing and development

async def test_placeholder_demand_function():
    """Test the placeholder demand function with sample data.
    
    This function can be used to test and validate the demand function
    implementation during development.
    """
    from .demand_functions import PlaceholderDemandFunction, DemandInputs
    from decimal import Decimal
    
    # Create test demand function
    demand_func = PlaceholderDemandFunction(
        base_elasticity=-1.5,
        competition_factor=0.8
    )
    
    # Create test inputs
    test_inputs = DemandInputs(
        base_market_size=Decimal("1000000"),
        price=Decimal("1200"),
        competitor_prices=[Decimal("1000"), Decimal("1100"), Decimal("1300")],
        market_conditions={
            "cycle_phase": "normal",
            "growth_rate": 0.03,
            "competitive_intensity": 0.8
        },
        company_attributes={
            "capital": 5000000.0,
            "experience": 1.0
        },
        product_features={
            "coverage_level": 1.0,
            "service_quality": 1.0
        }
    )
    
    # Calculate demand
    result = demand_func.calculate_demand(test_inputs)
    
    logger.info(f"Test demand calculation:")
    logger.info(f"  Quantity demanded: {result.quantity_demanded}")
    logger.info(f"  Market share: {result.market_share:.2%}")
    logger.info(f"  Price elasticity: {result.price_elasticity}")
    logger.info(f"  Competitive position: {result.competitive_position}")
    
    return result


def create_development_simulation_engine() -> WeeklySimulationEngine:
    """Create a simulation engine configured for development and testing.
    
    Returns:
        Configured WeeklySimulationEngine for development use
    """
    engine = WeeklySimulationEngine()
    
    # Configure with development-friendly settings
    engine.configure_demand_function(
        "placeholder",
        base_elasticity=-1.2,  # Less elastic for testing
        competition_factor=0.6,  # Reduced competition effects
        random_variation=0.05  # Less randomness for predictable testing
    )
    
    logger.info("Created development simulation engine")
    return engine