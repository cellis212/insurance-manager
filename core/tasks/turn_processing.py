"""Turn processing tasks for Insurance Manager.

This module contains the main turn processing logic that runs weekly
to simulate the insurance market and calculate results for all companies.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from celery import Task, group, chord
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.celery_app import celery_app
from core.database import get_session, init_db
from core.engine import plugin_manager
from core.events import event_bus
from core.models import (
    Turn, Company, CompanyTurnDecision, CompanyTurnResult,
    MarketCondition, PriceDecision, LineOfBusiness, State,
    InvestmentPortfolio, LiquidationEvent, Product,
    CompanyLineOfBusiness, CompanyStateAuthorization
)

logger = logging.getLogger(__name__)


class TurnProcessingError(Exception):
    """Raised when turn processing encounters a critical error."""
    pass


@celery_app.task(bind=True, name="core.tasks.turn_processing.process_turn")
def process_turn(self: Task, semester_id: str, turn_id: Optional[str] = None) -> Dict:
    """Main turn processing task that orchestrates all simulation stages.
    
    This task runs every Monday at midnight EST to process the weekly turn.
    It coordinates all sub-tasks and ensures data consistency.
    
    Args:
        semester_id: UUID of the current semester
        turn_id: Optional UUID of specific turn to process (for reruns)
        
    Returns:
        Dict with processing results and statistics
    """
    try:
        # Run the async processing function
        result = asyncio.run(_process_turn_async(semester_id, turn_id))
        return result
    except Exception as e:
        logger.error(f"Turn processing failed: {str(e)}", exc_info=True)
        raise TurnProcessingError(f"Turn processing failed: {str(e)}")


async def _process_turn_async(semester_id: str, turn_id: Optional[str] = None) -> Dict:
    """Async implementation of turn processing."""
    
    async with get_session() as session:
        # Initialize plugin manager if needed
        if not plugin_manager._initialized:
            await plugin_manager.initialize(session, semester_id)
        
        # Get or create the current turn
        turn = await _get_or_create_turn(session, semester_id, turn_id)
        
        if turn.status != "pending":
            logger.warning(f"Turn {turn.id} is not pending (status: {turn.status})")
            return {"status": "skipped", "reason": f"Turn status is {turn.status}"}
        
        # Update turn status to processing
        turn.status = "processing"
        turn.processing_started_at = datetime.now(timezone.utc)
        await session.commit()
        
        # Create shared game state for plugins
        game_state = {
            "semester_id": semester_id,
            "turn_id": str(turn.id),
            "turn_number": turn.week_number,
            "market_results": {},
            "operations_results": {},
            "investment_results": {}
        }
        
        try:
            # Emit turn start event
            await event_bus.emit(
                "turn.started",
                {"turn_id": str(turn.id), "turn_number": turn.week_number},
                source="TurnProcessor"
            )
            
            # Let plugins prepare for turn
            await plugin_manager.on_turn_start(turn, game_state)
            
            # Stage 1: Pre-processing validation
            logger.info(f"Starting pre-processing validation for turn {turn.id}")
            validation_results = await _pre_process_validation(session, turn)
            
            # Stage 2: Market simulation
            logger.info(f"Starting market simulation for turn {turn.id}")
            market_results = await _simulate_markets(session, turn)
            game_state["market_results"] = market_results
            
            # Stage 3: Operations simulation
            logger.info(f"Starting operations simulation for turn {turn.id}")
            operations_results = await _simulate_operations(session, turn, market_results)
            game_state["operations_results"] = operations_results
            
            # Stage 4: Investment simulation
            logger.info(f"Starting investment simulation for turn {turn.id}")
            investment_results = await _simulate_investments(session, turn, operations_results)
            game_state["investment_results"] = investment_results
            
            # Stage 5: Plugin calculations
            logger.info(f"Running plugin calculations for turn {turn.id}")
            companies = await session.execute(
                select(Company).where(Company.semester_id == turn.semester_id)
            )
            plugin_results = await plugin_manager.calculate_results(
                turn, companies.scalars().all(), game_state
            )
            
            # Stage 6: Post-processing
            logger.info(f"Starting post-processing for turn {turn.id}")
            final_results = await _post_process_results(
                session, turn, operations_results, investment_results, plugin_results
            )
            
            # Mark turn as completed
            turn.status = "completed"
            turn.processing_completed_at = datetime.now(timezone.utc)
            await session.commit()
            
            # Let plugins handle turn completion
            await plugin_manager.on_turn_complete(turn, final_results, game_state)
            
            # Emit turn completed event
            await event_bus.emit(
                "turn.completed",
                {
                    "turn_id": str(turn.id),
                    "turn_number": turn.week_number,
                    "companies_processed": len(final_results)
                },
                source="TurnProcessor"
            )
            
            # Trigger notifications
            celery_app.send_task(
                "core.tasks.notifications.send_turn_completed",
                kwargs={"turn_id": str(turn.id)},
                queue="notifications"
            )
            
            return {
                "status": "completed",
                "turn_id": str(turn.id),
                "companies_processed": len(final_results),
                "processing_time": (
                    turn.processing_completed_at - turn.processing_started_at
                ).total_seconds(),
                "plugin_results": {k: len(v) if isinstance(v, dict) else v 
                                 for k, v in plugin_results.items()}
            }
            
        except Exception as e:
            # Mark turn as failed
            turn.status = "failed"
            turn.processing_completed_at = datetime.now(timezone.utc)
            await session.commit()
            
            # Emit turn failed event
            await event_bus.emit(
                "turn.failed",
                {
                    "turn_id": str(turn.id),
                    "turn_number": turn.week_number,
                    "error": str(e)
                },
                source="TurnProcessor"
            )
            
            logger.error(f"Turn processing failed: {str(e)}", exc_info=True)
            raise


async def _get_or_create_turn(
    session: AsyncSession, 
    semester_id: str, 
    turn_id: Optional[str] = None
) -> Turn:
    """Get existing turn or create new one for the current week."""
    
    if turn_id:
        # Specific turn requested
        result = await session.execute(
            select(Turn).where(Turn.id == UUID(turn_id))
        )
        turn = result.scalar_one_or_none()
        if not turn:
            raise ValueError(f"Turn {turn_id} not found")
        return turn
    
    # Get the current week's turn
    result = await session.execute(
        select(Turn)
        .where(Turn.semester_id == UUID(semester_id))
        .where(Turn.status == "pending")
        .order_by(Turn.week_number.desc())
        .limit(1)
    )
    turn = result.scalar_one_or_none()
    
    if not turn:
        # Create new turn
        # Get the last turn number
        last_turn_result = await session.execute(
            select(Turn.week_number)
            .where(Turn.semester_id == UUID(semester_id))
            .order_by(Turn.week_number.desc())
            .limit(1)
        )
        last_week = last_turn_result.scalar_one_or_none() or 0
        
        turn = Turn(
            semester_id=UUID(semester_id),
            week_number=last_week + 1,
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),  # Will be updated
            status="pending",
            version=1
        )
        session.add(turn)
        await session.commit()
    
    return turn


async def _pre_process_validation(session: AsyncSession, turn: Turn) -> Dict:
    """Stage 1: Validate all company states and decisions."""
    
    validation_results = {
        "companies_validated": 0,
        "companies_with_errors": 0,
        "decisions_processed": 0,
        "default_decisions_applied": 0
    }
    
    # Get all active companies
    result = await session.execute(
        select(Company).where(Company.semester_id == turn.semester_id)
    )
    companies = result.scalars().all()
    
    for company in companies:
        # Check if company submitted decisions
        decision_result = await session.execute(
            select(CompanyTurnDecision)
            .where(CompanyTurnDecision.company_id == company.id)
            .where(CompanyTurnDecision.turn_id == turn.id)
        )
        decision = decision_result.scalar_one_or_none()
        
        if not decision:
            # Apply "no change" defaults
            decision = CompanyTurnDecision(
                company_id=company.id,
                turn_id=turn.id,
                decisions={
                    "type": "no_change",
                    "reason": "no_submission",
                    "applied_at": datetime.now(timezone.utc).isoformat()
                },
                submitted_at=turn.end_date,  # Use deadline as submission time
                is_late=True
            )
            session.add(decision)
            validation_results["default_decisions_applied"] += 1
        else:
            # Validate submitted decisions
            validation_errors = await _validate_company_decisions(
                session, company, decision
            )
            
            # Let plugins validate decisions too
            plugin_errors = await plugin_manager.on_decision_submitted(
                company, decision, {"turn_id": str(turn.id)}
            )
            
            # Combine all validation errors
            all_errors = validation_errors.copy()
            for plugin_name, errors in plugin_errors.items():
                all_errors.extend([f"[{plugin_name}] {error}" for error in errors])
            
            if all_errors:
                decision.validation_result = {
                    "valid": False,
                    "errors": all_errors
                }
                validation_results["companies_with_errors"] += 1
            else:
                decision.validation_result = {"valid": True}
                validation_results["decisions_processed"] += 1
        
        validation_results["companies_validated"] += 1
    
    await session.commit()
    return validation_results


async def _validate_company_decisions(
    session: AsyncSession,
    company: Company,
    decision: CompanyTurnDecision
) -> List[str]:
    """Validate a company's submitted decisions."""
    
    errors = []
    decisions = decision.decisions or {}
    
    # Check capital requirements for expansions
    if "expansions" in decisions:
        for expansion in decisions["expansions"]:
            state_id = expansion.get("state_id")
            if state_id:
                # Check if already authorized
                auth_result = await session.execute(
                    select(CompanyStateAuthorization)
                    .where(CompanyStateAuthorization.company_id == company.id)
                    .where(CompanyStateAuthorization.state_id == UUID(state_id))
                )
                if auth_result.scalar_one_or_none():
                    errors.append(f"Already authorized in state {state_id}")
                
                # Check capital requirements
                state_result = await session.execute(
                    select(State).where(State.id == UUID(state_id))
                )
                state = state_result.scalar_one_or_none()
                if state and company.current_capital < state.base_expansion_cost:
                    errors.append(
                        f"Insufficient capital for {state.name} expansion "
                        f"(need ${state.base_expansion_cost:,.2f})"
                    )
    
    # Validate pricing decisions
    if "pricing" in decisions:
        for price_decision in decisions["pricing"]:
            if price_decision.get("price_multiplier", 1.0) < 0.5:
                errors.append("Price multiplier cannot be below 0.5")
            if price_decision.get("price_multiplier", 1.0) > 2.0:
                errors.append("Price multiplier cannot exceed 2.0")
    
    return errors


async def _simulate_markets(session: AsyncSession, turn: Turn) -> Dict:
    """Stage 2: Simulate market demand and competition."""
    
    market_results = {}
    
    # Get all state/line combinations with active companies
    result = await session.execute(
        select(
            CompanyStateAuthorization.state_id,
            CompanyLineOfBusiness.line_of_business_id
        )
        .join(CompanyLineOfBusiness,
              CompanyLineOfBusiness.company_id == CompanyStateAuthorization.company_id)
        .distinct()
    )
    market_segments = result.all()
    
    for state_id, line_id in market_segments:
        # Calculate base demand
        market_condition = await _get_or_create_market_condition(
            session, turn, state_id, line_id
        )
        
        # Get all companies competing in this segment
        companies_result = await session.execute(
            select(Company)
            .join(CompanyStateAuthorization)
            .join(CompanyLineOfBusiness)
            .where(CompanyStateAuthorization.state_id == state_id)
            .where(CompanyLineOfBusiness.line_of_business_id == line_id)
        )
        competing_companies = companies_result.scalars().all()
        
        # Calculate market shares based on pricing
        segment_results = await _calculate_market_shares(
            session, turn, market_condition, competing_companies
        )
        
        market_results[f"{state_id}_{line_id}"] = segment_results
    
    await session.commit()
    return market_results


async def _get_or_create_market_condition(
    session: AsyncSession,
    turn: Turn,
    state_id: UUID,
    line_id: UUID
) -> MarketCondition:
    """Get or create market condition for a state/line/turn."""
    
    result = await session.execute(
        select(MarketCondition)
        .where(MarketCondition.turn_id == turn.id)
        .where(MarketCondition.state_id == state_id)
        .where(MarketCondition.line_id == line_id)
    )
    condition = result.scalar_one_or_none()
    
    if not condition:
        # Create new market condition with base parameters
        # In a real implementation, these would vary by market cycle
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
                "competitor_count": 0  # Will be updated
            }
        )
        session.add(condition)
    
    return condition


async def _calculate_market_shares(
    session: AsyncSession,
    turn: Turn,
    market_condition: MarketCondition,
    companies: List[Company]
) -> Dict:
    """Calculate market shares based on pricing decisions."""
    
    segment_results = {
        "total_premium": 0,
        "company_results": {}
    }
    
    if not companies:
        return segment_results
    
    # Get pricing decisions for all companies
    company_prices = {}
    for company in companies:
        price_result = await session.execute(
            select(PriceDecision)
            .where(PriceDecision.company_id == company.id)
            .where(PriceDecision.turn_id == turn.id)
            .where(PriceDecision.state_id == market_condition.state_id)
            .where(PriceDecision.line_id == market_condition.line_id)
        )
        price_decision = price_result.scalar_one_or_none()
        
        if price_decision:
            company_prices[company.id] = price_decision
        else:
            # Use default pricing if no decision
            company_prices[company.id] = PriceDecision(
                company_id=company.id,
                turn_id=turn.id,
                state_id=market_condition.state_id,
                line_id=market_condition.line_id,
                base_price=Decimal("1000"),
                price_multiplier=Decimal("1.0"),
                expected_loss_ratio=Decimal("0.65")
            )
    
    # Simple market share calculation based on relative pricing
    # Lower prices get higher market share (with elasticity)
    avg_price = sum(p.effective_price for p in company_prices.values()) / len(company_prices)
    
    for company_id, price_decision in company_prices.items():
        price_ratio = float(price_decision.effective_price / avg_price)
        # Market share inversely proportional to price with elasticity
        base_share = 1.0 / len(companies)
        price_effect = (1.0 - price_ratio) * float(market_condition.price_elasticity)
        market_share = base_share * (1.0 + price_effect)
        
        # Ensure market share is between 0 and 1
        market_share = max(0.01, min(0.9, market_share))
        
        premium_volume = float(market_condition.base_demand) * market_share
        
        segment_results["company_results"][str(company_id)] = {
            "market_share": market_share,
            "premium_volume": premium_volume,
            "effective_price": float(price_decision.effective_price)
        }
        segment_results["total_premium"] += premium_volume
    
    return segment_results


async def _simulate_operations(
    session: AsyncSession,
    turn: Turn,
    market_results: Dict
) -> Dict:
    """Stage 3: Simulate insurance operations including claims."""
    
    operations_results = {}
    
    # Get all companies
    result = await session.execute(
        select(Company).where(Company.semester_id == turn.semester_id)
    )
    companies = result.scalars().all()
    
    for company in companies:
        company_operations = {
            "premiums_written": Decimal("0"),
            "premiums_earned": Decimal("0"),
            "claims_incurred": Decimal("0"),
            "expenses": Decimal("0"),
            "underwriting_result": Decimal("0"),
            "loss_ratio": Decimal("0"),
            "expense_ratio": Decimal("0"),
            "combined_ratio": Decimal("0"),
            "lines_detail": {}
        }
        
        # Process each line of business
        lines_result = await session.execute(
            select(CompanyLineOfBusiness)
            .where(CompanyLineOfBusiness.company_id == company.id)
        )
        company_lines = lines_result.scalars().all()
        
        for company_line in company_lines:
            # Get states where company operates this line
            states_result = await session.execute(
                select(CompanyStateAuthorization)
                .where(CompanyStateAuthorization.company_id == company.id)
            )
            company_states = states_result.scalars().all()
            
            line_premiums = Decimal("0")
            line_claims = Decimal("0")
            
            for company_state in company_states:
                # Get market results for this segment
                segment_key = f"{company_state.state_id}_{company_line.line_of_business_id}"
                if segment_key in market_results:
                    segment = market_results[segment_key]
                    company_result = segment["company_results"].get(str(company.id), {})
                    
                    if company_result:
                        premium = Decimal(str(company_result["premium_volume"]))
                        line_premiums += premium
                        
                        # Simulate claims based on product tier and selection effects
                        claims = await _simulate_claims(
                            session, company, company_state.state_id,
                            company_line.line_of_business_id, premium
                        )
                        line_claims += claims
            
            company_operations["lines_detail"][str(company_line.line_of_business_id)] = {
                "premiums": float(line_premiums),
                "claims": float(line_claims),
                "loss_ratio": float(line_claims / line_premiums) if line_premiums > 0 else 0
            }
            
            company_operations["premiums_written"] += line_premiums
            company_operations["claims_incurred"] += line_claims
        
        # Calculate expenses (simplified - 25% of premium)
        company_operations["expenses"] = company_operations["premiums_written"] * Decimal("0.25")
        
        # Calculate ratios
        if company_operations["premiums_written"] > 0:
            company_operations["loss_ratio"] = (
                company_operations["claims_incurred"] / company_operations["premiums_written"]
            )
            company_operations["expense_ratio"] = (
                company_operations["expenses"] / company_operations["premiums_written"]
            )
            company_operations["combined_ratio"] = (
                company_operations["loss_ratio"] + company_operations["expense_ratio"]
            )
        
        company_operations["underwriting_result"] = (
            company_operations["premiums_written"] - 
            company_operations["claims_incurred"] - 
            company_operations["expenses"]
        )
        
        operations_results[company.id] = company_operations
    
    return operations_results


async def _simulate_claims(
    session: AsyncSession,
    company: Company,
    state_id: UUID,
    line_id: UUID,
    premium: Decimal
) -> Decimal:
    """Simulate claims for a specific company/state/line combination."""
    
    # Get product tier to determine selection effects
    product_result = await session.execute(
        select(Product)
        .where(Product.company_id == company.id)
        .where(Product.state_id == state_id)
        .where(Product.line_of_business_id == line_id)
    )
    product = product_result.scalar_one_or_none()
    
    # Base loss ratio by line (simplified)
    base_loss_ratios = {
        "personal_auto": Decimal("0.65"),
        "homeowners": Decimal("0.60"),
        "general_liability": Decimal("0.55"),
        "workers_comp": Decimal("0.70"),
        "commercial_property": Decimal("0.50")
    }
    
    # Get line of business details
    line_result = await session.execute(
        select(LineOfBusiness).where(LineOfBusiness.id == line_id)
    )
    line = line_result.scalar_one_or_none()
    
    base_loss_ratio = base_loss_ratios.get(line.code, Decimal("0.60"))
    
    # Apply product tier effects
    if product:
        if product.tier == "basic":
            # Basic products attract worse risks
            loss_ratio = base_loss_ratio * Decimal("1.3")
        elif product.tier == "premium":
            # Premium products attract better risks
            loss_ratio = base_loss_ratio * Decimal("0.9")
        else:
            # Standard products
            loss_ratio = base_loss_ratio
    else:
        loss_ratio = base_loss_ratio
    
    # Add some randomness (±10%)
    import random
    random_factor = Decimal(str(0.9 + random.random() * 0.2))
    loss_ratio = loss_ratio * random_factor
    
    # Calculate claims
    claims = premium * loss_ratio
    
    return claims


async def _simulate_investments(
    session: AsyncSession,
    turn: Turn,
    operations_results: Dict
) -> Dict:
    """Stage 4: Simulate investment returns and forced liquidations."""
    
    investment_results = {}
    
    for company_id, ops_result in operations_results.items():
        # Get company's investment portfolio
        portfolio_result = await session.execute(
            select(InvestmentPortfolio)
            .where(InvestmentPortfolio.company_id == company_id)
            .order_by(InvestmentPortfolio.created_at.desc())
            .limit(1)
        )
        portfolio = portfolio_result.scalar_one_or_none()
        
        if not portfolio:
            # Create default portfolio if none exists
            company_result = await session.execute(
                select(Company).where(Company.id == company_id)
            )
            company = company_result.scalar_one()
            
            portfolio = InvestmentPortfolio(
                company_id=company_id,
                turn_id=turn.id,
                total_value=company.current_capital * Decimal("0.8"),  # 80% invested
                characteristics={
                    "risk": 0.5,
                    "duration": 0.5,
                    "liquidity": 0.7,
                    "credit_quality": 0.8,
                    "diversification": 0.6
                },
                perceived_characteristics={
                    "risk": 0.5,
                    "duration": 0.5,
                    "liquidity": 0.7,
                    "credit_quality": 0.8,
                    "diversification": 0.6
                }
            )
            session.add(portfolio)
        
        # Calculate investment returns (simplified)
        base_return = Decimal("0.04")  # 4% annual, scaled to weekly
        weekly_return = base_return / 52
        
        # Adjust for risk level
        risk_adjustment = Decimal(str(portfolio.characteristics.get("risk", 0.5) - 0.5)) * Decimal("0.02")
        actual_return = weekly_return + risk_adjustment
        
        # Add market volatility
        import random
        volatility = Decimal(str(random.gauss(0, 0.01)))
        actual_return += volatility
        
        investment_income = portfolio.total_value * actual_return
        
        # Check if liquidation needed
        underwriting_result = ops_result["underwriting_result"]
        cash_need = -underwriting_result if underwriting_result < 0 else Decimal("0")
        
        liquidation_event = None
        if cash_need > 0:
            # Need to liquidate assets
            liquidation_event = await _process_liquidation(
                session, company_id, turn.id, cash_need, portfolio
            )
            session.add(liquidation_event)
        
        investment_results[company_id] = {
            "portfolio_value": float(portfolio.total_value),
            "investment_income": float(investment_income),
            "liquidation_needed": cash_need > 0,
            "liquidation_amount": float(liquidation_event.required_amount) if liquidation_event else 0,
            "liquidation_cost": float(liquidation_event.total_cost) if liquidation_event else 0
        }
    
    await session.commit()
    return investment_results


async def _process_liquidation(
    session: AsyncSession,
    company_id: UUID,
    turn_id: UUID,
    required_amount: Decimal,
    portfolio: InvestmentPortfolio
) -> LiquidationEvent:
    """Process forced asset liquidation when cash is needed."""
    
    # Get CFO skill level to determine liquidation quality
    # For MVP, use a default skill level
    cfo_skill = 50  # Medium skill
    
    # Higher skill means better liquidation (lower costs)
    skill_factor = cfo_skill / 100
    base_liquidation_cost = Decimal("0.05")  # 5% haircut
    
    # Adjust cost based on skill
    liquidation_discount = base_liquidation_cost * (2 - Decimal(str(skill_factor)))
    
    # Liquidate least liquid assets first (poor decision)
    # Better CFOs would liquidate most liquid first
    liquidity_score = portfolio.characteristics.get("liquidity", 0.5)
    if skill_factor < 0.5:
        # Poor CFO liquidates illiquid assets
        liquidation_discount *= Decimal(str(2 - liquidity_score))
    
    total_cost = required_amount * liquidation_discount
    
    liquidation_event = LiquidationEvent(
        company_id=company_id,
        turn_id=turn_id,
        trigger_type="operational_loss",
        required_amount=required_amount,
        assets_liquidated={
            "bonds": float(required_amount * Decimal("0.6")),
            "stocks": float(required_amount * Decimal("0.3")),
            "alternatives": float(required_amount * Decimal("0.1"))
        },
        market_impact=float(liquidation_discount),
        total_cost=required_amount + total_cost,
        liquidation_quality=skill_factor,
        skill_metrics={
            "cfo_skill": cfo_skill,
            "decision_quality": skill_factor,
            "suboptimal_cost": float(total_cost)
        }
    )
    
    # Update portfolio value
    portfolio.total_value -= (required_amount + total_cost)
    
    return liquidation_event


async def _post_process_results(
    session: AsyncSession,
    turn: Turn,
    operations_results: Dict,
    investment_results: Dict,
    plugin_results: Optional[Dict] = None
) -> Dict:
    """Stage 5: Calculate final results and update company states."""
    
    final_results = {}
    
    for company_id, ops_result in operations_results.items():
        inv_result = investment_results.get(company_id, {})
        
        # Calculate total income
        underwriting_income = ops_result["underwriting_result"]
        investment_income = Decimal(str(inv_result.get("investment_income", 0)))
        liquidation_cost = Decimal(str(inv_result.get("liquidation_cost", 0)))
        
        net_income = underwriting_income + investment_income - liquidation_cost
        
        # Update company capital
        company_result = await session.execute(
            select(Company).where(Company.id == company_id)
        )
        company = company_result.scalar_one()
        
        new_capital = company.current_capital + net_income
        company.current_capital = new_capital
        
        # Calculate solvency ratio (simplified)
        required_capital = ops_result["premiums_written"] * Decimal("0.3")
        solvency_ratio = new_capital / required_capital if required_capital > 0 else Decimal("999")
        company.solvency_ratio = solvency_ratio
        
        # Create turn result record
        turn_result = CompanyTurnResult(
            company_id=company_id,
            turn_id=turn.id,
            premiums_written=ops_result["premiums_written"],
            premiums_earned=ops_result["premiums_written"],  # Simplified
            claims_incurred=ops_result["claims_incurred"],
            expenses=ops_result["expenses"],
            investment_income=investment_income,
            net_income=net_income,
            ending_capital=new_capital,
            loss_ratio=ops_result["loss_ratio"],
            expense_ratio=ops_result["expense_ratio"],
            combined_ratio=ops_result["combined_ratio"],
            financial_data={
                "underwriting_result": float(underwriting_income),
                "lines_detail": ops_result["lines_detail"],
                "liquidation_events": inv_result.get("liquidation_amount", 0) > 0
            },
            market_data={
                "market_shares": {},  # Would be populated from market_results
                "competitive_position": "stable"
            },
            operational_data={
                "employee_count": 5,  # MVP - fixed C-suite
                "efficiency_score": 0.8
            }
        )
        session.add(turn_result)
        
        # Check for bankruptcy
        if new_capital <= 0 or solvency_ratio < Decimal("1.0"):
            company.status = "bankrupt"
            logger.warning(f"Company {company.id} is bankrupt!")
            
            # Trigger bankruptcy notification
            celery_app.send_task(
                "core.tasks.notifications.send_bankruptcy_notice",
                kwargs={
                    "company_id": str(company_id),
                    "turn_id": str(turn.id)
                },
                queue="notifications"
            )
        
        final_results[company_id] = {
            "net_income": float(net_income),
            "ending_capital": float(new_capital),
            "solvency_ratio": float(solvency_ratio),
            "status": company.status
        }
    
    await session.commit()
    return final_results


# Additional utility tasks

@celery_app.task(name="core.tasks.turn_processing.validate_turn_integrity")
def validate_turn_integrity(turn_id: str) -> Dict:
    """Validate that all turn data is consistent and complete."""
    
    async def _validate():
        async with get_session() as session:
            # Check all companies have results
            turn_result = await session.execute(
                select(Turn).where(Turn.id == UUID(turn_id))
            )
            turn = turn_result.scalar_one()
            
            # Get company count
            company_result = await session.execute(
                select(Company).where(Company.semester_id == turn.semester_id)
            )
            companies = company_result.scalars().all()
            
            # Get result count
            result_count = await session.execute(
                select(CompanyTurnResult).where(CompanyTurnResult.turn_id == turn.id)
            )
            results = result_count.scalars().all()
            
            return {
                "turn_id": turn_id,
                "companies": len(companies),
                "results": len(results),
                "complete": len(companies) == len(results),
                "missing": len(companies) - len(results)
            }
    
    return asyncio.run(_validate())


@celery_app.task(name="core.tasks.turn_processing.reprocess_turn")
def reprocess_turn(turn_id: str, stage: Optional[str] = None) -> Dict:
    """Reprocess a specific turn or stage for debugging/recovery."""
    
    logger.info(f"Reprocessing turn {turn_id}, stage: {stage or 'all'}")
    
    # For now, just run the full process
    # In future, could restart from specific stage
    return process_turn(turn_id=turn_id)
