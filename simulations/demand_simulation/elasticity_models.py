"""Demand elasticity models for market share calculation.

This module implements price elasticity calculations that determine how
pricing decisions affect market share. Starting with simple linear elasticity
for MVP, with hooks for future BLP-style discrete choice models.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class DemandSimulator:
    """Simulates market demand based on price elasticity and product characteristics.
    
    This simulator calculates market share based on:
    - Own-price elasticity (how price affects own demand)
    - Cross-price elasticity (how competitor prices affect demand)
    - Product tier effects (quality perception)
    - Market conditions (boom/recession)
    
    Future enhancements will include:
    - Consumer heterogeneity (BLP random coefficients)
    - Brand loyalty effects
    - Distribution channel impacts
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize demand simulator with game configuration.
        
        Args:
            config: Game configuration containing economic parameters
        """
        # Extract economic parameters
        economic_params = config.get('economic_parameters', {})
        
        # Price elasticity by line of business
        self.price_elasticity = economic_params.get('price_elasticity', {
            'auto': -1.2,        # More elastic (price sensitive)
            'home': -0.8,        # Less elastic (necessity)
            'general_liability': -1.0,
            'workers_comp': -0.6,  # Least elastic (required)
            'commercial_property': -0.9
        })
        
        # Cross-price elasticity (how competitor prices affect our demand)
        self.cross_price_elasticity = economic_params.get('cross_price_elasticity', 0.3)
        
        # Base demand multiplier for market conditions
        self.base_demand_multiplier = economic_params.get('base_demand_multiplier', 1.0)
        
        # Product tier effects from configuration
        product_params = config.get('product_parameters', {})
        self.tier_effects = product_params.get('tiers', {
            'basic': {'price_modifier': 0.8, 'quality_perception': 0.8},
            'standard': {'price_modifier': 1.0, 'quality_perception': 1.0},
            'premium': {'price_modifier': 1.3, 'quality_perception': 1.2}
        })
        
        # Market size normalization to ensure shares sum to 1
        self.normalize_shares = True
    
    def calculate_market_share(
        self,
        company_price: float,
        competitor_prices: List[float],
        line_of_business: str,
        product_tier: str = 'standard',
        market_condition: Optional[str] = None,
        market_multiplier: float = 1.0
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate market share based on prices and product characteristics.
        
        Uses a simplified logit model for MVP:
        utility = α - β*price + γ*quality + ε
        
        Where:
        - α is base utility (normalized to 0)
        - β is price sensitivity (elasticity)
        - γ is quality perception from tier
        - ε is unobserved factors (set to 0 for now)
        
        Args:
            company_price: Our company's price
            competitor_prices: List of competitor prices
            line_of_business: Insurance line (affects elasticity)
            product_tier: Product quality tier
            market_condition: Optional market state (boom/recession)
            market_multiplier: External market effect multiplier
            
        Returns:
            Tuple of (market_share, debug_info)
        """
        # Get line-specific elasticity
        own_elasticity = self.price_elasticity.get(
            line_of_business.lower(), 
            -1.0  # Default elasticity if line not found
        )
        
        # Get tier effects
        tier_info = self.tier_effects.get(product_tier, self.tier_effects['standard'])
        quality_perception = tier_info.get('quality_perception', 1.0)
        
        # Apply market condition multiplier
        demand_multiplier = self.base_demand_multiplier * market_multiplier
        
        # Calculate utilities using logit model
        # Own utility
        own_utility = self._calculate_utility(
            price=company_price,
            quality=quality_perception,
            elasticity=own_elasticity,
            is_own=True
        )
        
        # Competitor utilities (assume standard tier for competitors in MVP)
        competitor_utilities = []
        for comp_price in competitor_prices:
            comp_utility = self._calculate_utility(
                price=comp_price,
                quality=1.0,  # Standard tier assumed
                elasticity=own_elasticity,
                is_own=False
            )
            competitor_utilities.append(comp_utility)
        
        # Calculate market shares using softmax (logit probabilities)
        all_utilities = [own_utility] + competitor_utilities
        exp_utilities = np.exp(all_utilities)
        total_exp = np.sum(exp_utilities)
        
        # Our market share
        market_share = float(exp_utilities[0] / total_exp)
        
        # Apply demand multiplier to absolute share
        market_share *= demand_multiplier
        
        # Ensure share is between 0 and 1
        market_share = max(0.0, min(1.0, market_share))
        
        # Debug information
        debug_info = {
            'own_utility': own_utility,
            'avg_competitor_utility': np.mean(competitor_utilities) if competitor_utilities else 0,
            'price_elasticity': own_elasticity,
            'quality_perception': quality_perception,
            'num_competitors': len(competitor_prices),
            'demand_multiplier': demand_multiplier
        }
        
        logger.debug(
            f"Market share calculation: price={company_price}, "
            f"tier={product_tier}, share={market_share:.3f}"
        )
        
        return market_share, debug_info
    
    def _calculate_utility(
        self, 
        price: float, 
        quality: float, 
        elasticity: float,
        is_own: bool
    ) -> float:
        """Calculate utility for a product offering.
        
        Args:
            price: Product price
            quality: Quality perception multiplier
            elasticity: Price elasticity parameter
            is_own: Whether this is our own product
            
        Returns:
            Utility value
        """
        # Base utility (normalized to 0)
        utility = 0.0
        
        # Price effect (negative elasticity means higher price reduces utility)
        # Using log price for realistic elasticity behavior
        if price > 0:
            utility += elasticity * np.log(price)
        
        # Quality effect (positive)
        utility += 2.0 * np.log(quality)  # Quality coefficient
        
        # Cross-price effects if not own product
        if not is_own:
            utility *= (1 - self.cross_price_elasticity)
        
        return utility
    
    def calculate_market_equilibrium(
        self,
        companies: List[Dict[str, Any]],
        line_of_business: str,
        market_condition: Optional[str] = None,
        iterations: int = 10
    ) -> Dict[str, float]:
        """Calculate market equilibrium with competitive responses.
        
        Iteratively adjusts market shares based on competitive dynamics
        until equilibrium is reached or iteration limit hit.
        
        Args:
            companies: List of company data with prices and tiers
            line_of_business: Insurance line
            market_condition: Market state
            iterations: Maximum iterations for convergence
            
        Returns:
            Dictionary of company_id -> market_share
        """
        shares = {}
        
        for iteration in range(iterations):
            new_shares = {}
            
            for company in companies:
                company_id = company['id']
                company_price = company['price']
                company_tier = company.get('tier', 'standard')
                
                # Get competitor prices
                competitor_prices = [
                    c['price'] for c in companies 
                    if c['id'] != company_id
                ]
                
                # Calculate this company's share
                share, _ = self.calculate_market_share(
                    company_price=company_price,
                    competitor_prices=competitor_prices,
                    line_of_business=line_of_business,
                    product_tier=company_tier,
                    market_condition=market_condition
                )
                
                new_shares[company_id] = share
            
            # Normalize shares to sum to 1
            if self.normalize_shares:
                total_share = sum(new_shares.values())
                if total_share > 0:
                    new_shares = {
                        cid: share / total_share 
                        for cid, share in new_shares.items()
                    }
            
            # Check for convergence
            if iteration > 0:
                max_change = max(
                    abs(new_shares.get(cid, 0) - shares.get(cid, 0))
                    for cid in set(new_shares.keys()) | set(shares.keys())
                )
                if max_change < 0.001:  # Convergence threshold
                    logger.debug(f"Market equilibrium reached in {iteration} iterations")
                    break
            
            shares = new_shares
        
        return shares
    
    def calculate_demand_curve(
        self,
        base_price: float,
        price_range: Tuple[float, float],
        line_of_business: str,
        product_tier: str = 'standard',
        competitor_prices: Optional[List[float]] = None,
        num_points: int = 20
    ) -> List[Tuple[float, float]]:
        """Generate demand curve showing price-quantity relationship.
        
        Useful for optimization and visualization.
        
        Args:
            base_price: Reference price point
            price_range: (min_price, max_price) to evaluate
            line_of_business: Insurance line
            product_tier: Product quality tier
            competitor_prices: Fixed competitor prices
            num_points: Number of points on curve
            
        Returns:
            List of (price, market_share) tuples
        """
        if competitor_prices is None:
            # Use base price as competitor benchmark
            competitor_prices = [base_price] * 3  # Assume 3 competitors
        
        min_price, max_price = price_range
        prices = np.linspace(min_price, max_price, num_points)
        
        demand_curve = []
        for price in prices:
            share, _ = self.calculate_market_share(
                company_price=float(price),
                competitor_prices=competitor_prices,
                line_of_business=line_of_business,
                product_tier=product_tier
            )
            demand_curve.append((float(price), share))
        
        return demand_curve
