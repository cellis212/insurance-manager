"""Weekly simulation engine for comprehensive market simulation.

This module provides the main simulation engine that coordinates all
aspects of the weekly simulation including market dynamics, operations,
and financial results.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import (
    Turn, Company, CompanyTurnDecision, CompanyTurnResult,
    PriceDecision, MarketCondition, State, LineOfBusiness
)
from core.events import event_bus
from core.engine import plugin_manager

from simulations.demand_simulation import DemandSimulator, MarketShareAllocator
from simulations.claims_simulation import FrequencySeverityModel, CatastropheSimulator
from simulations.asset_purchase_simulation import AssetPurchaseSimulator
from simulations.asset_sale_simulation import AssetSaleSimulator

from .demand_functions import DemandFunctionFactory, DemandInputs
from .market_simulator import MarketSimulator
from .operations_simulator import OperationsSimulator
from .results_aggregator import ResultsAggregator

logger = logging.getLogger(__name__)


class WeeklySimulationEngine:
    """Main engine for weekly simulation processing.
    
    This engine coordinates all simulation components to process a complete
    weekly turn for all companies in a semester. It follows the established
    architecture with plugin support and event-driven processing.
    """
    
    def __init__(self):
        """Initialize the simulation engine."""
        self.demand_function = DemandFunctionFactory.create_demand_function("placeholder")
        self.market_simulator = MarketSimulator(self.demand_function)
        self.operations_simulator = OperationsSimulator()
        self.results_aggregator = ResultsAggregator()
        
        # Legacy simulation components
        self.demand_simulator = DemandSimulator()
        self.market_share_allocator = MarketShareAllocator()
        self.frequency_severity_model = FrequencySeverityModel()
        self.catastrophe_simulator = CatastropheSimulator()
        
        logger.info("WeeklySimulationEngine initialized")
    
    async def process_weekly_turn(
        self,
        session: AsyncSession,
        turn: Turn,
        game_state: Dict
    ) -> Dict:
        """Process a complete weekly turn simulation.
        
        This is the main entry point for weekly simulation processing.
        It coordinates all simulation stages and returns comprehensive results.
        
        Args:
            session: Database session
            turn: Turn object being processed
            game_state: Shared game state from turn processor
            
        Returns:
            Dictionary containing all simulation results
        """
        logger.info(f"Starting weekly simulation for turn {turn.id}")
        
        # Emit simulation start event
        await event_bus.emit(
            "simulation.started",
            {
                "turn_id": str(turn.id),
                "turn_number": turn.week_number,
                "semester_id": str(turn.semester_id)
            },
            source="WeeklySimulationEngine"
        )
        
        try:
            # Stage 1: Market simulation
            logger.info("Running market simulation")
            market_results = await self._simulate_markets(session, turn, game_state)
            
            # Stage 2: Operations simulation
            logger.info("Running operations simulation")
            operations_results = await self._simulate_operations(
                session, turn, market_results, game_state
            )
            
            # Stage 3: Investment simulation
            logger.info("Running investment simulation")
            investment_results = await self._simulate_investments(
                session, turn, operations_results, game_state
            )
            
            # Stage 4: Aggregate results
            logger.info("Aggregating final results")
            final_results = await self._aggregate_results(
                session, turn, market_results, operations_results, investment_results
            )
            
            # Stage 5: Plugin processing
            logger.info("Running plugin calculations")
            plugin_results = await self._run_plugin_calculations(
                session, turn, final_results, game_state
            )
            
            # Combine all results
            simulation_results = {
                "market_results": market_results,
                "operations_results": operations_results,
                "investment_results": investment_results,
                "final_results": final_results,
                "plugin_results": plugin_results,
                "processing_metadata": {
                    "turn_id": str(turn.id),
                    "companies_processed": len(final_results.get("company_results", {})),
                    "simulation_completed_at": datetime.now(timezone.utc).isoformat()
                }
            }
            
            # Update game state
            game_state.update(simulation_results)
            
            # Emit simulation completion event
            await event_bus.emit(
                "simulation.completed",
                {
                    "turn_id": str(turn.id),
                    "companies_processed": len(final_results.get("company_results", {})),
                    "simulation_results": simulation_results["processing_metadata"]
                },
                source="WeeklySimulationEngine"
            )
            
            logger.info(f"Weekly simulation completed for turn {turn.id}")
            return simulation_results
            
        except Exception as e:
            logger.error(f"Weekly simulation failed: {str(e)}", exc_info=True)
            
            # Emit simulation failure event
            await event_bus.emit(
                "simulation.failed",
                {
                    "turn_id": str(turn.id),
                    "error": str(e)
                },
                source="WeeklySimulationEngine"
            )
            
            raise
    
    async def _simulate_markets(
        self,
        session: AsyncSession,
        turn: Turn,
        game_state: Dict
    ) -> Dict:
        """Simulate market dynamics for all market segments.
        
        Args:
            session: Database session
            turn: Turn being processed
            game_state: Shared game state
            
        Returns:
            Dictionary with market simulation results
        """
        market_results = {}
        
        # Get all active companies
        companies_result = await session.execute(
            select(Company).where(Company.semester_id == turn.semester_id)
        )
        companies = companies_result.scalars().all()
        
        # Get all market segments (state/line combinations)
        market_segments = await self._get_market_segments(session, turn)
        
        for segment in market_segments:
            state_id, line_id = segment
            
            # Get companies active in this segment
            segment_companies = await self._get_segment_companies(
                session, state_id, line_id, companies
            )
            
            if not segment_companies:
                continue
            
            # Run market simulation for this segment
            segment_results = await self.market_simulator.simulate_segment(
                session, turn, state_id, line_id, segment_companies
            )
            
            market_results[f"{state_id}_{line_id}"] = segment_results
        
        return market_results
    
    async def _simulate_operations(
        self,
        session: AsyncSession,
        turn: Turn,
        market_results: Dict,
        game_state: Dict
    ) -> Dict:
        """Simulate operational results for all companies.
        
        Args:
            session: Database session
            turn: Turn being processed
            market_results: Results from market simulation
            game_state: Shared game state
            
        Returns:
            Dictionary with operations simulation results
        """
        operations_results = {}
        
        # Get all companies
        companies_result = await session.execute(
            select(Company).where(Company.semester_id == turn.semester_id)
        )
        companies = companies_result.scalars().all()
        
        for company in companies:
            # Simulate operations for this company
            company_results = await self.operations_simulator.simulate_company_operations(
                session, turn, company, market_results
            )
            
            operations_results[str(company.id)] = company_results
        
        return operations_results
    
    async def _simulate_investments(
        self,
        session: AsyncSession,
        turn: Turn,
        operations_results: Dict,
        game_state: Dict
    ) -> Dict:
        """Simulate investment portfolio changes and returns.
        
        Args:
            session: Database session
            turn: Turn being processed
            operations_results: Results from operations simulation
            game_state: Shared game state
            
        Returns:
            Dictionary with investment simulation results
        """
        investment_results = {}
        
        # Get all companies
        companies_result = await session.execute(
            select(Company).where(Company.semester_id == turn.semester_id)
        )
        companies = companies_result.scalars().all()
        
        for company in companies:
            # Get company's operations results
            company_ops_results = operations_results.get(str(company.id), {})
            
            # Simulate investment portfolio for this company
            company_investment_results = await self._simulate_company_investments(
                session, turn, company, company_ops_results
            )
            
            investment_results[str(company.id)] = company_investment_results
        
        return investment_results
    
    async def _simulate_company_investments(
        self,
        session: AsyncSession,
        turn: Turn,
        company: Company,
        operations_results: Dict
    ) -> Dict:
        """Simulate investment portfolio for a single company.
        
        Args:
            session: Database session
            turn: Turn being processed
            company: Company to simulate
            operations_results: Company's operations results
            
        Returns:
            Dictionary with company investment results
        """
        # This is a placeholder implementation
        # In the future, this would integrate with the investment plugins
        
        # Calculate basic investment income
        base_investment_income = company.current_capital * Decimal("0.02")  # 2% quarterly return
        
        # Apply some randomness
        import random
        volatility_factor = Decimal(str(random.uniform(0.8, 1.2)))
        investment_income = base_investment_income * volatility_factor
        
        return {
            "investment_income": investment_income,
            "portfolio_value": company.current_capital + investment_income,
            "return_rate": float(investment_income / company.current_capital) if company.current_capital > 0 else 0.0
        }
    
    async def _aggregate_results(
        self,
        session: AsyncSession,
        turn: Turn,
        market_results: Dict,
        operations_results: Dict,
        investment_results: Dict
    ) -> Dict:
        """Aggregate all simulation results into final company results.
        
        Args:
            session: Database session
            turn: Turn being processed
            market_results: Market simulation results
            operations_results: Operations simulation results
            investment_results: Investment simulation results
            
        Returns:
            Dictionary with aggregated final results
        """
        return await self.results_aggregator.aggregate_results(
            session, turn, market_results, operations_results, investment_results
        )
    
    async def _run_plugin_calculations(
        self,
        session: AsyncSession,
        turn: Turn,
        final_results: Dict,
        game_state: Dict
    ) -> Dict:
        """Run plugin calculations for additional features.
        
        Args:
            session: Database session
            turn: Turn being processed
            final_results: Aggregated simulation results
            game_state: Shared game state
            
        Returns:
            Dictionary with plugin calculation results
        """
        # Get all companies
        companies_result = await session.execute(
            select(Company).where(Company.semester_id == turn.semester_id)
        )
        companies = companies_result.scalars().all()
        
        # Run plugin calculations
        plugin_results = await plugin_manager.calculate_results(
            turn, companies, game_state
        )
        
        return plugin_results
    
    async def _get_market_segments(
        self,
        session: AsyncSession,
        turn: Turn
    ) -> List[Tuple[UUID, UUID]]:
        """Get all active market segments for the turn.
        
        Args:
            session: Database session
            turn: Turn being processed
            
        Returns:
            List of (state_id, line_id) tuples representing market segments
        """
        # For now, return a placeholder segment
        # In a real implementation, this would query the database for active segments
        
        # Get a sample state and line of business
        state_result = await session.execute(
            select(State).limit(1)
        )
        state = state_result.scalar_one_or_none()
        
        line_result = await session.execute(
            select(LineOfBusiness).limit(1)
        )
        line = line_result.scalar_one_or_none()
        
        if state and line:
            return [(state.id, line.id)]
        else:
            return []
    
    async def _get_segment_companies(
        self,
        session: AsyncSession,
        state_id: UUID,
        line_id: UUID,
        all_companies: List[Company]
    ) -> List[Company]:
        """Get companies active in a specific market segment.
        
        Args:
            session: Database session
            state_id: State ID for the segment
            line_id: Line of business ID for the segment
            all_companies: List of all companies to filter
            
        Returns:
            List of companies active in the segment
        """
        # For now, return all companies as a placeholder
        # In a real implementation, this would filter based on authorizations
        return all_companies
    
    def configure_demand_function(self, function_type: str, **kwargs) -> None:
        """Configure the demand function used by the simulation.
        
        Args:
            function_type: Type of demand function to use
            **kwargs: Additional configuration parameters
        """
        self.demand_function = DemandFunctionFactory.create_demand_function(
            function_type, **kwargs
        )
        self.market_simulator.demand_function = self.demand_function
        
        logger.info(f"Configured demand function: {function_type}")
    
    def get_simulation_status(self) -> Dict:
        """Get current simulation engine status.
        
        Returns:
            Dictionary with simulation engine status information
        """
        return {
            "demand_function_type": type(self.demand_function).__name__,
            "components_initialized": {
                "market_simulator": self.market_simulator is not None,
                "operations_simulator": self.operations_simulator is not None,
                "results_aggregator": self.results_aggregator is not None
            },
            "engine_ready": True
        }