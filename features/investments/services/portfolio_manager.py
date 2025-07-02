"""Portfolio management service for investment decisions.

Handles portfolio characteristic preferences, optimization, and tracking.
Integrates with existing simulation modules for actual calculations.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Optional, Tuple, Any, List
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.models.investment_portfolio import InvestmentPortfolio
from core.models.liquidation_event import LiquidationEvent
from core.models.company import Company
from core.models.employee import Employee
from core.models.turn import Turn
from simulations.asset_purchase_simulation.portfolio_optimizer import PortfolioOptimizer
from simulations.asset_purchase_simulation.asset_characteristics import AssetCharacteristicsMapper
from simulations.asset_sale_simulation.liquidation_engine import LiquidationEngine

logger = logging.getLogger(__name__)


class PortfolioManager:
    """Manages investment portfolios for insurance companies.
    
    Provides interface for:
    - Setting portfolio characteristic preferences (5 sliders)
    - Optimizing portfolios based on constraints
    - Tracking portfolio performance
    - Handling forced liquidations
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize portfolio manager.
        
        Args:
            config: Game configuration
        """
        self.config = config
        self.optimizer = PortfolioOptimizer(config)
        self.asset_mapper = AssetCharacteristicsMapper(config)
        self.liquidation_engine = LiquidationEngine(config)
        
        # Investment parameters
        investment_params = config.get('investment_parameters', {})
        self.min_investment_amount = Decimal(str(investment_params.get('min_investment_amount', 1000000)))
        self.characteristic_names = ['risk', 'duration', 'liquidity', 'credit', 'diversification']
    
    async def create_portfolio_decision(
        self,
        session: AsyncSession,
        company_id: UUID,
        turn_id: UUID,
        characteristic_preferences: Dict[str, float]
    ) -> Dict[str, Any]:
        """Create investment portfolio decision for a turn.
        
        Args:
            session: Database session
            company_id: Company making decision
            turn_id: Current turn ID
            characteristic_preferences: Desired portfolio characteristics (0-100 scale)
            
        Returns:
            Portfolio decision details
            
        Raises:
            ValueError: If preferences are invalid or company has insufficient capital
        """
        # Validate preferences
        self._validate_preferences(characteristic_preferences)
        
        # Get company and check capital
        company = await session.get(Company, company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")
        
        if company.current_capital < self.min_investment_amount:
            raise ValueError(
                f"Insufficient capital for investment. "
                f"Need at least ${self.min_investment_amount:,.0f}, "
                f"have ${company.current_capital:,.0f}"
            )
        
        # Convert preferences to optimizer scale (0-1)
        optimizer_preferences = {
            char: value / 100 
            for char, value in characteristic_preferences.items()
        }
        
        # Determine constraints based on company state
        constraints = await self._get_investment_constraints(session, company)
        
        # Optimize portfolio
        optimal_characteristics, optimization_details = self.optimizer.optimize_portfolio(
            risk_tolerance=optimizer_preferences.get('risk', 0.5),
            liquidity_need=optimizer_preferences.get('liquidity', 0.3),
            constraints=constraints
        )
        
        # Map to asset allocation
        asset_allocation, mapping_details = self.asset_mapper.map_characteristics_to_allocation(optimal_characteristics)
        
        # Convert back to 0-100 scale for storage
        stored_characteristics = {
            char: value * 100 
            for char, value in optimal_characteristics.items()
        }
        
        decision = {
            'company_id': company_id,
            'turn_id': turn_id,
            'requested_characteristics': characteristic_preferences,
            'optimized_characteristics': stored_characteristics,
            'asset_allocation': asset_allocation,
            'expected_return': optimization_details['expected_return'],
            'portfolio_risk': optimization_details['portfolio_risk'],
            'sharpe_ratio': optimization_details['sharpe_ratio'],
            'optimization_success': optimization_details['success']
        }
        
        logger.info(
            f"Portfolio decision created for company {company_id}: "
            f"Expected return {optimization_details['expected_return']:.1%}, "
            f"Risk {optimization_details['portfolio_risk']:.1%}"
        )
        
        return decision
    
    async def process_portfolio_returns(
        self,
        session: AsyncSession,
        portfolio: InvestmentPortfolio,
        market_conditions: str = 'normal'
    ) -> Tuple[Decimal, Dict[str, Any]]:
        """Calculate portfolio returns for a turn.
        
        Args:
            session: Database session
            portfolio: Investment portfolio to process
            market_conditions: Current market state
            
        Returns:
            Tuple of (actual_returns, return_details)
        """
        # Get actual characteristics (stored as 0-100, convert to 0-1)
        characteristics = {
            char: portfolio.characteristics.get(char, 50) / 100
            for char in self.characteristic_names
        }
        
        # Calculate expected returns based on characteristics
        expected_return = self.optimizer._calculate_expected_return(characteristics)
        portfolio_risk = self.optimizer._calculate_portfolio_risk(characteristics)
        
        # Add market condition effects
        market_multipliers = {
            'boom': 1.5,
            'normal': 1.0,
            'recession': 0.5,
            'crisis': -0.5
        }
        market_effect = market_multipliers.get(market_conditions, 1.0)
        
        # Generate random return based on expected return and risk
        import numpy as np
        random_shock = np.random.normal(0, portfolio_risk)
        actual_return_rate = expected_return * market_effect + random_shock
        
        # Calculate dollar returns
        actual_returns = portfolio.total_value * Decimal(str(actual_return_rate))
        
        return_details = {
            'expected_return_rate': expected_return,
            'portfolio_risk': portfolio_risk,
            'market_effect': market_effect,
            'random_shock': random_shock,
            'actual_return_rate': actual_return_rate,
            'dollar_returns': float(actual_returns)
        }
        
        return actual_returns, return_details
    
    async def handle_liquidation_need(
        self,
        session: AsyncSession,
        company_id: UUID,
        turn_id: UUID,
        liquidation_amount: Decimal,
        trigger_type: str,
        portfolio: InvestmentPortfolio,
        cfo_skill: Optional[int] = None
    ) -> LiquidationEvent:
        """Handle forced portfolio liquidation.
        
        Args:
            session: Database session
            company_id: Company needing liquidation
            turn_id: Current turn
            liquidation_amount: Amount needed
            trigger_type: What triggered the need
            portfolio: Current portfolio
            cfo_skill: CFO skill level (if None, will look up)
            
        Returns:
            Created liquidation event
        """
        # Get CFO skill if not provided
        if cfo_skill is None:
            cfo = await self._get_company_cfo(session, company_id)
            cfo_skill = int(cfo.skill_level) if cfo else 50
        
        # Convert characteristics to asset allocation for liquidation
        characteristics = {
            char: portfolio.characteristics.get(char, 50) / 100
            for char in self.characteristic_names
        }
        asset_allocation, _ = self.asset_mapper.map_characteristics_to_allocation(characteristics)
        
        # Determine which assets to liquidate
        assets_to_sell, liquidation_details = self.liquidation_engine.select_assets_for_liquidation(
            portfolio=asset_allocation,
            portfolio_value=float(portfolio.total_value),
            liquidation_need=float(liquidation_amount),
            cfo_skill=cfo_skill,
            time_pressure='urgent' if trigger_type == 'catastrophe' else 'normal'
        )
        
        # Create liquidation event
        liquidation_event = LiquidationEvent(
            company_id=company_id,
            turn_id=turn_id,
            trigger_type=trigger_type,
            required_amount=liquidation_amount,
            assets_liquidated=assets_to_sell,
            market_impact=Decimal(str(liquidation_details['average_discount'])),
            total_cost=Decimal(str(liquidation_details['total_costs'])),
            cfo_skill_at_time=cfo_skill,
            liquidation_metadata={
                'liquidation_quality': liquidation_details['liquidation_quality'],
                'num_assets_sold': liquidation_details['num_assets_sold'],
                'shortfall': liquidation_details['shortfall']
            }
        )
        
        session.add(liquidation_event)
        
        # Update portfolio value
        portfolio.total_value -= Decimal(str(liquidation_details['total_sold']))
        
        logger.info(
            f"Liquidation processed for company {company_id}: "
            f"Needed ${liquidation_amount:,.0f}, "
            f"raised ${liquidation_details['amount_raised']:,.0f}, "
            f"cost ${liquidation_details['total_costs']:,.0f}"
        )
        
        return liquidation_event
    
    async def get_portfolio_summary(
        self,
        session: AsyncSession,
        company_id: UUID,
        turn_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get summary of company's current portfolio.
        
        Args:
            session: Database session
            company_id: Company ID
            turn_id: Turn ID
            
        Returns:
            Portfolio summary or None if no portfolio
        """
        # Get latest portfolio
        stmt = select(InvestmentPortfolio).where(
            InvestmentPortfolio.company_id == company_id,
            InvestmentPortfolio.turn_id == turn_id
        )
        result = await session.execute(stmt)
        portfolio = result.scalar_one_or_none()
        
        if not portfolio:
            return None
        
        # Get CFO for skill assessment
        cfo = await self._get_company_cfo(session, company_id)
        
        summary = {
            'total_value': float(portfolio.total_value),
            'actual_characteristics': portfolio.characteristics,
            'perceived_characteristics': portfolio.perceived_characteristics,
            'actual_returns': float(portfolio.actual_returns),
            'perceived_returns': float(portfolio.perceived_returns),
            'cfo_skill': int(cfo.skill_level) if cfo else None,
            'information_quality': self._calculate_information_quality(
                portfolio.characteristics,
                portfolio.perceived_characteristics
            )
        }
        
        return summary
    
    def _validate_preferences(self, preferences: Dict[str, float]) -> None:
        """Validate portfolio characteristic preferences.
        
        Args:
            preferences: Characteristic preferences to validate
            
        Raises:
            ValueError: If preferences are invalid
        """
        required_chars = set(self.characteristic_names)
        provided_chars = set(preferences.keys())
        
        if provided_chars != required_chars:
            missing = required_chars - provided_chars
            extra = provided_chars - required_chars
            raise ValueError(
                f"Invalid characteristics. Missing: {missing}, Extra: {extra}"
            )
        
        for char, value in preferences.items():
            if not 0 <= value <= 100:
                raise ValueError(
                    f"Characteristic '{char}' must be between 0 and 100, got {value}"
                )
    
    async def _get_investment_constraints(
        self, 
        session: AsyncSession, 
        company: Company
    ) -> Dict[str, Any]:
        """Get investment constraints based on company state.
        
        Args:
            session: Database session
            company: Company entity
            
        Returns:
            Constraint dictionary
        """
        constraints = {}
        
        # Solvency constraints
        if company.solvency_ratio and company.solvency_ratio < Decimal("1.5"):
            # Low solvency requires more liquidity
            constraints['min_liquidity'] = 0.5
            constraints['max_risk'] = 0.6
        
        # Get number of states for diversification
        auth_count = len(company.state_authorizations)
        if auth_count < 5:
            # Small companies need less complexity
            constraints['max_duration'] = 0.7
            constraints['min_diversification'] = 0.3
        
        return constraints
    
    async def _get_company_cfo(
        self, 
        session: AsyncSession, 
        company_id: UUID
    ) -> Optional[Employee]:
        """Get company's CFO.
        
        Args:
            session: Database session
            company_id: Company ID
            
        Returns:
            CFO employee or None
        """
        stmt = select(Employee).where(
            Employee.company_id == company_id,
            Employee.position == "CFO"
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    def _calculate_information_quality(
        self, 
        actual: Dict[str, Any], 
        perceived: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate information quality score.
        
        Args:
            actual: Actual characteristics
            perceived: Perceived characteristics
            
        Returns:
            Quality score (0-1)
        """
        if not perceived:
            return 0.0
        
        total_error = 0
        count = 0
        
        for char in self.characteristic_names:
            if char in actual and char in perceived:
                error = abs(actual[char] - perceived[char])
                total_error += error
                count += 1
        
        if count == 0:
            return 0.0
        
        avg_error = total_error / count
        # Convert error to quality (0-100 scale, so divide by 100)
        quality = 1 - (avg_error / 100)
        
        return max(0.0, quality) 