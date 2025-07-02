"""Operations simulator for weekly simulation.

This module handles the simulation of company operations including
claims generation, underwriting results, and operational expenses.
"""

import logging
from decimal import Decimal
from typing import Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Company, Turn
from simulations.claims_simulation import FrequencySeverityModel

logger = logging.getLogger(__name__)


class OperationsSimulator:
    """Simulates company operations for weekly turns.
    
    This class handles the calculation of operational results including
    premium income, claims expenses, and underwriting profits.
    """
    
    def __init__(self):
        """Initialize operations simulator."""
        self.claims_model = FrequencySeverityModel({
            "base_frequency": 0.1,
            "severity_mean": 10000,
            "severity_std": 5000
        })
        logger.info("OperationsSimulator initialized")
    
    async def simulate_company_operations(
        self,
        session: AsyncSession,
        turn: Turn,
        company: Company,
        market_results: Dict
    ) -> Dict:
        """Simulate operations for a single company.
        
        Args:
            session: Database session
            turn: Turn being processed
            company: Company to simulate
            market_results: Results from market simulation
            
        Returns:
            Dictionary with company operations results
        """
        logger.info(f"Simulating operations for company {company.id}")
        
        # Extract company's market results
        company_market_data = self._extract_company_market_data(
            company.id, market_results
        )
        
        # Calculate premium income
        premium_income = self._calculate_premium_income(company_market_data)
        
        # Simulate claims
        claims_results = await self._simulate_claims(
            session, company, premium_income
        )
        
        # Calculate expenses
        expenses = self._calculate_expenses(company, premium_income)
        
        # Calculate underwriting result
        underwriting_result = premium_income - claims_results["total_claims"] - expenses["total_expenses"]
        
        return {
            "company_id": str(company.id),
            "premium_income": premium_income,
            "claims": claims_results,
            "expenses": expenses,
            "underwriting_result": underwriting_result,
            "loss_ratio": float(claims_results["total_claims"] / premium_income) if premium_income > 0 else 0.0,
            "expense_ratio": float(expenses["total_expenses"] / premium_income) if premium_income > 0 else 0.0,
            "combined_ratio": float((claims_results["total_claims"] + expenses["total_expenses"]) / premium_income) if premium_income > 0 else 0.0
        }
    
    def _extract_company_market_data(
        self,
        company_id: UUID,
        market_results: Dict
    ) -> Dict:
        """Extract market data specific to a company.
        
        Args:
            company_id: Company ID
            market_results: Market simulation results
            
        Returns:
            Dictionary with company's market data
        """
        company_id_str = str(company_id)
        total_premium = Decimal("0")
        market_segments = []
        
        for segment_key, segment_data in market_results.items():
            company_results = segment_data.get("company_results", {})
            if company_id_str in company_results:
                company_segment_data = company_results[company_id_str]
                total_premium += company_segment_data.get("premium_volume", Decimal("0"))
                market_segments.append(company_segment_data)
        
        return {
            "total_premium": total_premium,
            "segments": market_segments,
            "num_segments": len(market_segments)
        }
    
    def _calculate_premium_income(self, market_data: Dict) -> Decimal:
        """Calculate total premium income for the company.
        
        Args:
            market_data: Company's market data
            
        Returns:
            Total premium income
        """
        return market_data.get("total_premium", Decimal("0"))
    
    async def _simulate_claims(
        self,
        session: AsyncSession,
        company: Company,
        premium_income: Decimal
    ) -> Dict:
        """Simulate claims for the company.
        
        Args:
            session: Database session
            company: Company object
            premium_income: Premium income for the period
            
        Returns:
            Dictionary with claims simulation results
        """
        # Use a simple claims simulation for now
        # In a real implementation, this would use the claims simulation models
        
        # Base claims as percentage of premium
        base_claims_ratio = Decimal("0.65")  # 65% loss ratio
        
        # Add some randomness
        import random
        volatility = Decimal(str(random.uniform(0.8, 1.2)))
        
        total_claims = premium_income * base_claims_ratio * volatility
        
        return {
            "total_claims": total_claims,
            "claims_count": int(premium_income / 10000),  # Rough estimate
            "average_claim_size": total_claims / max(int(premium_income / 10000), 1),
            "loss_ratio": float(total_claims / premium_income) if premium_income > 0 else 0.0
        }
    
    def _calculate_expenses(
        self,
        company: Company,
        premium_income: Decimal
    ) -> Dict:
        """Calculate operational expenses for the company.
        
        Args:
            company: Company object
            premium_income: Premium income for the period
            
        Returns:
            Dictionary with expense calculations
        """
        # Commission and acquisition costs (percentage of premium)
        commission_rate = Decimal("0.15")  # 15%
        commissions = premium_income * commission_rate
        
        # Fixed operational expenses
        base_expenses = Decimal("50000")  # Base monthly expenses
        
        # Variable expenses (percentage of premium)
        variable_rate = Decimal("0.05")  # 5%
        variable_expenses = premium_income * variable_rate
        
        total_expenses = commissions + base_expenses + variable_expenses
        
        return {
            "commissions": commissions,
            "base_expenses": base_expenses,
            "variable_expenses": variable_expenses,
            "total_expenses": total_expenses,
            "expense_ratio": float(total_expenses / premium_income) if premium_income > 0 else 0.0
        }