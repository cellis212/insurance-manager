"""Investment management plugin for the Insurance Manager game.

Provides portfolio management, CFO skill effects, and liquidation handling.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Any, List, Optional
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.interfaces.game_system import GameSystemPlugin
from core.events.event_bus import EventBus
from core.models.company import Company
from core.models.employee import Employee
from core.models.investment_portfolio import InvestmentPortfolio
from core.models.turn import Turn
from features.investments.services.portfolio_manager import PortfolioManager
from features.investments.services.skill_effects import InvestmentSkillEffects

logger = logging.getLogger(__name__)


class InvestmentSystemPlugin(GameSystemPlugin):
    """Investment management system plugin.
    
    Handles:
    - Portfolio characteristic preferences (5 sliders)
    - CFO skill effects on perception vs reality
    - Automated liquidation during crises
    - Investment return calculations
    """
    
    def __init__(self):
        """Initialize investment plugin."""
        super().__init__()
        self.portfolio_manager: Optional[PortfolioManager] = None
        self.skill_effects: Optional[InvestmentSkillEffects] = None
    
    @property
    def name(self) -> str:
        """Plugin name."""
        return "Investment Management System"
    
    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"
    
    @property
    def dependencies(self) -> List[str]:
        """Plugin dependencies."""
        return ["CEO System"]  # Need employees for CFO
    
    async def initialize(
        self, 
        event_bus: EventBus, 
        config: Dict[str, Any]
    ) -> None:
        """Initialize plugin with configuration.
        
        Args:
            event_bus: Game event bus
            config: Game configuration
        """
        await super().initialize(event_bus, config)
        
        # Initialize services
        self.portfolio_manager = PortfolioManager(config)
        self.skill_effects = InvestmentSkillEffects(config)
        
        # Register event handlers
        self.event_bus.on("company.capital_need")(self._handle_capital_need)
        self.event_bus.on("market.conditions_changed")(self._handle_market_change)
        
        logger.info(f"{self.name} v{self.version} initialized")
    
    async def on_turn_start(
        self, 
        session: AsyncSession, 
        turn: Turn, 
        companies: List[Company]
    ) -> None:
        """Process investment portfolios at turn start.
        
        Args:
            session: Database session
            turn: Current turn
            companies: Active companies
        """
        logger.info(f"Processing investments for {len(companies)} companies")
        
        for company in companies:
            try:
                # Skip if company has insufficient capital
                min_amount = self.portfolio_manager.min_investment_amount
                if company.current_capital < min_amount:
                    continue
                
                # Get latest portfolio
                portfolio = await self._get_latest_portfolio(session, company.id)
                
                if portfolio:
                    # Process returns
                    returns, details = await self.portfolio_manager.process_portfolio_returns(
                        session,
                        portfolio,
                        market_conditions='normal'  # TODO: Get from market system
                    )
                    
                    # Update company capital
                    company.current_capital += returns
                    
                    logger.debug(
                        f"Company {company.id} investment returns: ${returns:,.0f}"
                    )
            
            except Exception as e:
                logger.error(f"Error processing investments for company {company.id}: {e}")
    
    async def on_decision_submitted(
        self, 
        session: AsyncSession, 
        company: Company, 
        decisions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate and process investment decisions.
        
        Args:
            session: Database session
            company: Company submitting decisions
            decisions: Submitted decisions
            
        Returns:
            Validation results
        """
        validation_results = {}
        
        # Check for investment decisions
        investment_decisions = decisions.get('investments')
        if not investment_decisions:
            return validation_results
        
        # Validate characteristic preferences
        preferences = investment_decisions.get('characteristic_preferences')
        if preferences:
            try:
                # Create portfolio decision
                decision = await self.portfolio_manager.create_portfolio_decision(
                    session,
                    company.id,
                    decisions.get('turn_id'),
                    preferences
                )
                
                validation_results['investment_valid'] = True
                validation_results['investment_decision'] = decision
                
            except ValueError as e:
                validation_results['investment_valid'] = False
                validation_results['investment_error'] = str(e)
        
        return validation_results
    
    async def calculate_results(
        self, 
        session: AsyncSession, 
        company: Company, 
        turn: Turn,
        shared_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate investment results for a company.
        
        Args:
            session: Database session
            company: Company to process
            turn: Current turn
            shared_state: Shared state between plugins
            
        Returns:
            Investment calculation results
        """
        results = {}
        
        # Get investment decision from shared state
        investment_decision = shared_state.get('decisions', {}).get('investment_decision')
        
        if investment_decision:
            # Get CFO for skill effects
            cfo = await self._get_company_cfo(session, company.id)
            cfo_skill = int(cfo.skill_level) if cfo else 50
            
            # Apply skill effects to perception
            actual_chars = investment_decision['optimized_characteristics']
            perceived_chars, perception_details = self.skill_effects.apply_perception_noise(
                actual_chars,
                cfo_skill,
                market_conditions=shared_state.get('market_conditions')
            )
            
            # Create portfolio record
            portfolio_value = min(
                company.current_capital - self.config.get('capital_buffer', 1000000),
                company.current_capital * Decimal("0.8")  # Max 80% in investments
            )
            
            portfolio = InvestmentPortfolio(
                company_id=company.id,
                turn_id=turn.id,
                total_value=portfolio_value,
                characteristics=actual_chars,
                perceived_characteristics=perceived_chars,
                actual_returns=Decimal("0"),  # Calculated at next turn
                perceived_returns=Decimal("0")
            )
            
            session.add(portfolio)
            
            # Deduct from company capital
            company.current_capital -= portfolio_value
            
            results['portfolio_created'] = True
            results['portfolio_value'] = float(portfolio_value)
            results['information_quality'] = perception_details['information_quality']
            
            # Generate insights
            insights = self.skill_effects.generate_investment_insights(
                investment_decision,
                cfo_skill
            )
            results['cfo_insights'] = insights
        
        # Check for liquidation needs
        liquidation_need = shared_state.get('liquidation_need')
        if liquidation_need:
            portfolio = await self._get_latest_portfolio(session, company.id)
            if portfolio and portfolio.total_value > 0:
                # Handle forced liquidation
                liquidation = await self.portfolio_manager.handle_liquidation_need(
                    session,
                    company.id,
                    turn.id,
                    Decimal(str(liquidation_need['amount'])),
                    liquidation_need['trigger'],
                    portfolio
                )
                
                results['liquidation_occurred'] = True
                results['liquidation_cost'] = float(liquidation.total_cost)
                results['amount_raised'] = float(liquidation.required_amount)
        
        return results
    
    async def on_catastrophe(
        self, 
        session: AsyncSession, 
        affected_companies: List[Company],
        catastrophe_data: Dict[str, Any]
    ) -> None:
        """Handle catastrophe effects on investments.
        
        Args:
            session: Database session
            affected_companies: Companies affected by catastrophe
            catastrophe_data: Catastrophe details
        """
        for company in affected_companies:
            # Check if liquidation needed
            capital_need = catastrophe_data.get('capital_requirements', {}).get(company.id)
            
            if capital_need and capital_need > company.current_capital:
                # Emit liquidation event
                await self.event_bus.emit(
                    "company.capital_need",
                    {
                        'company_id': company.id,
                        'amount': capital_need - company.current_capital,
                        'trigger': 'catastrophe',
                        'urgency': 'high'
                    }
                )
    
    async def _handle_capital_need(self, event_data: Dict[str, Any]) -> None:
        """Handle capital need events.
        
        Args:
            event_data: Event data with capital need details
        """
        # This would trigger liquidation in the next turn processing
        logger.info(
            f"Capital need registered for company {event_data['company_id']}: "
            f"${event_data['amount']:,.0f}"
        )
    
    async def _handle_market_change(self, event_data: Dict[str, Any]) -> None:
        """Handle market condition changes.
        
        Args:
            event_data: Market change details
        """
        # Market conditions affect both returns and perception accuracy
        logger.info(f"Market conditions changed to: {event_data.get('new_condition')}")
    
    async def _get_latest_portfolio(
        self, 
        session: AsyncSession, 
        company_id: UUID
    ) -> Optional[InvestmentPortfolio]:
        """Get company's latest portfolio.
        
        Args:
            session: Database session
            company_id: Company ID
            
        Returns:
            Latest portfolio or None
        """
        stmt = select(InvestmentPortfolio).where(
            InvestmentPortfolio.company_id == company_id
        ).order_by(InvestmentPortfolio.created_at.desc()).limit(1)
        
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
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