"""Results aggregator for weekly simulation.

This module handles the aggregation of all simulation results into
final company results and turn summaries.
"""

import logging
from decimal import Decimal
from typing import Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Company, Turn, CompanyTurnResult

logger = logging.getLogger(__name__)


class ResultsAggregator:
    """Aggregates simulation results into final company results.
    
    This class combines market, operations, and investment results
    into comprehensive company performance metrics.
    """
    
    def __init__(self):
        """Initialize results aggregator."""
        logger.info("ResultsAggregator initialized")
    
    async def aggregate_results(
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
        logger.info(f"Aggregating results for turn {turn.id}")
        
        # Get all companies
        companies_result = await session.execute(
            select(Company).where(Company.semester_id == turn.semester_id)
        )
        companies = companies_result.scalars().all()
        
        company_results = {}
        turn_summary = {
            "total_premium": Decimal("0"),
            "total_claims": Decimal("0"),
            "total_expenses": Decimal("0"),
            "total_investment_income": Decimal("0"),
            "companies_processed": 0
        }
        
        for company in companies:
            company_id_str = str(company.id)
            
            # Get results for this company
            ops_results = operations_results.get(company_id_str, {})
            inv_results = investment_results.get(company_id_str, {})
            
            # Calculate final financial position
            final_results = await self._calculate_company_final_results(
                company, ops_results, inv_results
            )
            
            # Store results
            company_results[company_id_str] = final_results
            
            # Update turn summary
            turn_summary["total_premium"] += final_results.get("premium_income", Decimal("0"))
            turn_summary["total_claims"] += final_results.get("total_claims", Decimal("0"))
            turn_summary["total_expenses"] += final_results.get("total_expenses", Decimal("0"))
            turn_summary["total_investment_income"] += final_results.get("investment_income", Decimal("0"))
            turn_summary["companies_processed"] += 1
            
            # Save to database
            await self._save_company_results(session, turn, company, final_results, inv_results)
        
        # Calculate turn-level metrics
        turn_summary["average_loss_ratio"] = (
            float(turn_summary["total_claims"] / turn_summary["total_premium"])
            if turn_summary["total_premium"] > 0 else 0.0
        )
        
        turn_summary["average_expense_ratio"] = (
            float(turn_summary["total_expenses"] / turn_summary["total_premium"])
            if turn_summary["total_premium"] > 0 else 0.0
        )
        
        turn_summary["average_combined_ratio"] = (
            turn_summary["average_loss_ratio"] + turn_summary["average_expense_ratio"]
        )
        
        await session.commit()
        
        return {
            "company_results": company_results,
            "turn_summary": turn_summary
        }
    
    async def _calculate_company_final_results(
        self,
        company: Company,
        operations_results: Dict,
        investment_results: Dict
    ) -> Dict:
        """Calculate final results for a single company.
        
        Args:
            company: Company object
            operations_results: Operations simulation results
            investment_results: Investment simulation results
            
        Returns:
            Dictionary with final company results
        """
        # Extract key metrics
        premium_income = operations_results.get("premium_income", Decimal("0"))
        total_claims = operations_results.get("claims", {}).get("total_claims", Decimal("0"))
        total_expenses = operations_results.get("expenses", {}).get("total_expenses", Decimal("0"))
        underwriting_result = operations_results.get("underwriting_result", Decimal("0"))
        investment_income = investment_results.get("investment_income", Decimal("0"))
        
        # Calculate net income
        net_income = underwriting_result + investment_income
        
        # Calculate new capital position
        new_capital = company.current_capital + net_income
        
        # Calculate key ratios
        loss_ratio = float(total_claims / premium_income) if premium_income > 0 else 0.0
        expense_ratio = float(total_expenses / premium_income) if premium_income > 0 else 0.0
        combined_ratio = loss_ratio + expense_ratio
        
        return {
            "company_id": str(company.id),
            "company_name": company.name,
            
            # Income statement
            "premium_income": premium_income,
            "total_claims": total_claims,
            "total_expenses": total_expenses,
            "underwriting_result": underwriting_result,
            "investment_income": investment_income,
            "net_income": net_income,
            
            # Balance sheet
            "starting_capital": company.current_capital,
            "ending_capital": new_capital,
            "capital_change": net_income,
            
            # Key ratios
            "loss_ratio": loss_ratio,
            "expense_ratio": expense_ratio,
            "combined_ratio": combined_ratio,
            "return_on_capital": float(net_income / company.current_capital) if company.current_capital > 0 else 0.0,
            
            # Additional metrics
            "market_segments": len(operations_results.get("segments", [])),
            "portfolio_value": investment_results.get("portfolio_value", company.current_capital)
        }
    
    async def _save_company_results(
        self,
        session: AsyncSession,
        turn: Turn,
        company: Company,
        results: Dict,
        inv_results: Dict
    ) -> None:
        """Save company results to the database.
        
        Args:
            session: Database session
            turn: Turn object
            company: Company object
            results: Final company results
        """
        # Check if results already exist
        existing_result = await session.execute(
            select(CompanyTurnResult)
            .where(CompanyTurnResult.company_id == company.id)
            .where(CompanyTurnResult.turn_id == turn.id)
        )
        company_result = existing_result.scalar_one_or_none()
        
        if not company_result:
            # Create new result record
            company_result = CompanyTurnResult(
                company_id=company.id,
                turn_id=turn.id,
                semester_id=turn.semester_id
            )
            session.add(company_result)
        
        # Update financial results
        company_result.premium_income = results["premium_income"]
        company_result.claims_paid = results["total_claims"]
        company_result.operating_expenses = results["total_expenses"]
        company_result.underwriting_result = results["underwriting_result"]
        company_result.investment_income = results["investment_income"]
        company_result.net_income = results["net_income"]
        company_result.ending_capital = results["ending_capital"]
        
        # Update key metrics
        company_result.loss_ratio = Decimal(str(results["loss_ratio"]))
        company_result.expense_ratio = Decimal(str(results["expense_ratio"]))
        company_result.combined_ratio = Decimal(str(results["combined_ratio"]))
        
        # Store detailed results in JSONB field
        company_result.detailed_results = {
            "market_performance": {
                "segments_active": results["market_segments"],
                "premium_by_segment": {}  # TODO: Add segment-level details
            },
            "operations_performance": {
                "claims_count": results.get("claims_count", 0),
                "average_claim_size": float(results.get("average_claim_size", 0))
            },
                         "investment_performance": {
                 "portfolio_value": float(results["portfolio_value"]),
                 "return_rate": inv_results.get("return_rate", 0.0)
             },
            "ratios": {
                "loss_ratio": results["loss_ratio"],
                "expense_ratio": results["expense_ratio"],
                "combined_ratio": results["combined_ratio"],
                "return_on_capital": results["return_on_capital"]
            }
        }
        
        # Update company's capital
        company.current_capital = results["ending_capital"]