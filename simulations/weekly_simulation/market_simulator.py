"""Market simulator for weekly simulation.

This module handles market dynamics simulation for individual market segments,
including demand calculation, pricing effects, and competitive dynamics.
"""

import logging
from decimal import Decimal
from typing import Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Company, Turn, PriceDecision, MarketCondition
from .demand_functions import DemandFunction, DemandInputs, DemandResult

logger = logging.getLogger(__name__)


class MarketSimulator:
    """Simulates market dynamics for market segments.
    
    This class handles the calculation of demand, market shares, and competitive
    effects for each market segment during the weekly simulation.
    """
    
    def __init__(self, demand_function: DemandFunction):
        """Initialize market simulator.
        
        Args:
            demand_function: Demand function to use for calculations
        """
        self.demand_function = demand_function
        logger.info(f"MarketSimulator initialized with {type(demand_function).__name__}")
    
    async def simulate_segment(
        self,
        session: AsyncSession,
        turn: Turn,
        state_id: UUID,
        line_id: UUID,
        companies: List[Company]
    ) -> Dict:
        """Simulate a single market segment.
        
        Args:
            session: Database session
            turn: Turn being processed
            state_id: State ID for the segment
            line_id: Line of business ID for the segment
            companies: Companies active in this segment
            
        Returns:
            Dictionary with segment simulation results
        """
        logger.info(f"Simulating market segment {state_id}_{line_id} with {len(companies)} companies")
        
        # Get or create market condition for this segment
        market_condition = await self._get_market_condition(
            session, turn, state_id, line_id
        )
        
        # Get pricing decisions for all companies
        company_prices = await self._get_company_prices(
            session, turn, state_id, line_id, companies
        )
        
        # Calculate demand for each company
        company_results = {}
        total_segment_demand = Decimal("0")
        
        for company in companies:
            price_decision = company_prices.get(company.id)
            if not price_decision:
                continue
            
            # Prepare demand inputs
            competitor_prices = [
                p.effective_price for c_id, p in company_prices.items() 
                if c_id != company.id
            ]
            
            demand_inputs = DemandInputs(
                base_market_size=market_condition.base_demand,
                price=price_decision.effective_price,
                competitor_prices=competitor_prices,
                market_conditions={
                    "cycle_phase": market_condition.market_data.get("cycle_phase", "normal"),
                    "growth_rate": market_condition.market_data.get("growth_rate", 0.03),
                    "competitive_intensity": float(market_condition.competitive_intensity)
                },
                company_attributes={
                    "capital": float(company.current_capital),
                    "experience": 1.0  # Placeholder
                },
                product_features={
                    "coverage_level": 1.0,  # Placeholder
                    "service_quality": 1.0  # Placeholder
                }
            )
            
            # Calculate demand for this company
            demand_result = self.demand_function.calculate_demand(demand_inputs)
            
            company_results[str(company.id)] = {
                "company_id": str(company.id),
                "price": price_decision.effective_price,
                "quantity_demanded": demand_result.quantity_demanded,
                "market_share": demand_result.market_share,
                "competitive_position": demand_result.competitive_position,
                "premium_volume": demand_result.quantity_demanded,
                "expected_loss_ratio": price_decision.expected_loss_ratio
            }
            
            total_segment_demand += demand_result.quantity_demanded
        
        # Calculate segment-level metrics
        segment_results = {
            "state_id": str(state_id),
            "line_id": str(line_id),
            "total_demand": total_segment_demand,
            "num_competitors": len(companies),
            "market_condition": {
                "base_demand": market_condition.base_demand,
                "price_elasticity": market_condition.price_elasticity,
                "competitive_intensity": market_condition.competitive_intensity
            },
            "company_results": company_results
        }
        
        logger.info(f"Segment simulation complete: {total_segment_demand} total demand")
        return segment_results
    
    async def _get_market_condition(
        self,
        session: AsyncSession,
        turn: Turn,
        state_id: UUID,
        line_id: UUID
    ) -> MarketCondition:
        """Get or create market condition for a segment.
        
        Args:
            session: Database session
            turn: Turn being processed
            state_id: State ID
            line_id: Line of business ID
            
        Returns:
            MarketCondition for the segment
        """
        # Try to get existing market condition
        result = await session.execute(
            select(MarketCondition)
            .where(MarketCondition.turn_id == turn.id)
            .where(MarketCondition.state_id == state_id)
            .where(MarketCondition.line_id == line_id)
        )
        condition = result.scalar_one_or_none()
        
        if not condition:
            # Create new market condition with default values
            condition = MarketCondition(
                semester_id=turn.semester_id,
                turn_id=turn.id,
                turn_number=turn.week_number,
                state_id=state_id,
                line_id=line_id,
                base_demand=Decimal("1000000"),  # $1M base premium volume
                price_elasticity=Decimal("-1.5"),  # Standard elasticity
                competitive_intensity=Decimal("0.8"),
                market_data={
                    "growth_rate": 0.03,
                    "cycle_phase": "normal",
                    "competitor_count": 0
                }
            )
            session.add(condition)
            await session.commit()
        
        return condition
    
    async def _get_company_prices(
        self,
        session: AsyncSession,
        turn: Turn,
        state_id: UUID,
        line_id: UUID,
        companies: List[Company]
    ) -> Dict[UUID, PriceDecision]:
        """Get pricing decisions for companies in a segment.
        
        Args:
            session: Database session
            turn: Turn being processed
            state_id: State ID
            line_id: Line of business ID
            companies: List of companies
            
        Returns:
            Dictionary mapping company ID to PriceDecision
        """
        company_prices = {}
        
        for company in companies:
            # Try to get price decision
            result = await session.execute(
                select(PriceDecision)
                .where(PriceDecision.company_id == company.id)
                .where(PriceDecision.turn_id == turn.id)
                .where(PriceDecision.state_id == state_id)
                .where(PriceDecision.line_id == line_id)
            )
            price_decision = result.scalar_one_or_none()
            
            if not price_decision:
                # Create default price decision
                price_decision = PriceDecision(
                    company_id=company.id,
                    turn_id=turn.id,
                    state_id=state_id,
                    line_id=line_id,
                    base_price=Decimal("1000"),
                    price_multiplier=Decimal("1.0"),
                    expected_loss_ratio=Decimal("0.65")
                )
                session.add(price_decision)
            
            company_prices[company.id] = price_decision
        
        await session.commit()
        return company_prices