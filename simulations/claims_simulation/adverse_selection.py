"""Adverse selection modeling for insurance markets.

This module simulates how pricing decisions attract different risk profiles,
creating adverse selection effects where lower prices attract worse risks.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class AdverseSelectionModel:
    """Models adverse selection effects in insurance markets.
    
    Adverse selection occurs when:
    - Lower prices attract higher-risk customers
    - Higher prices drive away good risks
    - Information asymmetry between insurers and customers
    - Product tiers create risk segmentation
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize adverse selection model.
        
        Args:
            config: Game configuration
        """
        self.config = config
        claims_params = config.get('claims_parameters', {})
        self.selection_params = claims_params.get('adverse_selection_factors', {})
        
        # Default selection parameters
        self.base_selection_strength = self.selection_params.get('base_strength', 0.3)
        self.price_sensitivity = self.selection_params.get('price_sensitivity', 0.5)
        self.tier_segmentation = self.selection_params.get('tier_segmentation', True)
        
        # Risk distribution parameters
        self.risk_distribution = self.selection_params.get('risk_distribution', {
            'mean': 1.0,      # Average risk level
            'std': 0.3,       # Risk heterogeneity
            'min': 0.2,       # Minimum risk level
            'max': 3.0        # Maximum risk level
        })
    
    def calculate_selection_modifier(
        self,
        company_price: float,
        market_avg_price: float,
        product_tier: str = 'standard',
        line_of_business: str = 'auto'
    ) -> Tuple[float, Dict[str, Any]]:
        """Calculate risk selection modifier based on pricing.
        
        Lower prices relative to market attract worse risks.
        Higher prices attract better risks but lower volume.
        
        Args:
            company_price: Company's price
            market_avg_price: Market average price
            product_tier: Product quality tier
            line_of_business: Insurance line
            
        Returns:
            Tuple of (risk_modifier, selection_details)
        """
        # Calculate relative price position
        if market_avg_price > 0:
            relative_price = company_price / market_avg_price
        else:
            relative_price = 1.0
        
        # Base selection effect from price
        # relative_price < 1: cheaper than market (attracts worse risks)
        # relative_price > 1: expensive than market (attracts better risks)
        price_effect = self._calculate_price_selection(relative_price)
        
        # Tier-based selection
        tier_effect = self._calculate_tier_selection(product_tier)
        
        # Line-specific adjustments
        line_adjustment = self._get_line_adjustment(line_of_business)
        
        # Combine effects
        total_selection = price_effect * tier_effect * line_adjustment
        
        # Ensure reasonable bounds
        risk_modifier = np.clip(total_selection, 0.5, 2.0)
        
        selection_details = {
            'relative_price': relative_price,
            'price_effect': price_effect,
            'tier_effect': tier_effect,
            'line_adjustment': line_adjustment,
            'final_modifier': risk_modifier
        }
        
        logger.debug(
            f"Selection modifier: price={company_price:.0f} "
            f"(rel={relative_price:.2f}), tier={product_tier}, "
            f"modifier={risk_modifier:.2f}"
        )
        
        return risk_modifier, selection_details
    
    def _calculate_price_selection(self, relative_price: float) -> float:
        """Calculate selection effect from pricing.
        
        Args:
            relative_price: Price relative to market average
            
        Returns:
            Risk selection multiplier
        """
        # Logistic function for smooth transition
        # Center at 1.0 (market price)
        # Lower prices -> higher risk (modifier > 1)
        # Higher prices -> lower risk (modifier < 1)
        
        price_deviation = relative_price - 1.0
        
        # Asymmetric response
        if price_deviation < 0:
            # Underpricing attracts bad risks strongly
            selection = 1 + abs(price_deviation) * self.price_sensitivity * 1.5
        else:
            # Overpricing repels bad risks moderately
            selection = 1 - price_deviation * self.price_sensitivity * 0.7
        
        return selection
    
    def _calculate_tier_selection(self, product_tier: str) -> float:
        """Calculate selection effect from product tier.
        
        Args:
            product_tier: Product quality tier
            
        Returns:
            Tier-based selection multiplier
        """
        if not self.tier_segmentation:
            return 1.0
        
        tier_effects = {
            'basic': 1.3,      # Basic tier attracts 30% worse risks
            'standard': 1.0,   # Standard tier is baseline
            'premium': 0.9     # Premium tier attracts 10% better risks
        }
        
        return tier_effects.get(product_tier, 1.0)
    
    def _get_line_adjustment(self, line_of_business: str) -> float:
        """Get line-specific selection adjustment.
        
        Some lines have stronger selection effects.
        
        Args:
            line_of_business: Insurance line
            
        Returns:
            Line-specific adjustment factor
        """
        line_adjustments = {
            'auto': 1.2,              # Strong selection in auto
            'home': 0.9,              # Weaker selection in home
            'general_liability': 1.1,  # Moderate selection
            'workers_comp': 0.8,      # Weak (regulated)
            'commercial_property': 1.0 # Neutral
        }
        
        return line_adjustments.get(line_of_business.lower(), 1.0)
    
    def simulate_risk_distribution(
        self,
        num_customers: int,
        selection_modifier: float,
        random_seed: Optional[int] = None
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """Simulate risk levels for customer population.
        
        Args:
            num_customers: Number of customers to simulate
            selection_modifier: Risk selection modifier
            random_seed: Random seed for reproducibility
            
        Returns:
            Tuple of (risk_levels array, distribution_stats)
        """
        if random_seed is not None:
            np.random.seed(random_seed)
        
        # Adjust distribution parameters based on selection
        base_mean = self.risk_distribution['mean']
        base_std = self.risk_distribution['std']
        
        # Selection shifts the mean risk level
        adjusted_mean = base_mean * selection_modifier
        
        # Bad selection also increases variance (more extreme risks)
        if selection_modifier > 1:
            adjusted_std = base_std * (1 + (selection_modifier - 1) * 0.5)
        else:
            adjusted_std = base_std
        
        # Generate risk levels (truncated normal)
        a, b = (self.risk_distribution['min'] - adjusted_mean) / adjusted_std, \
               (self.risk_distribution['max'] - adjusted_mean) / adjusted_std
        
        risk_levels = stats.truncnorm.rvs(
            a, b,
            loc=adjusted_mean,
            scale=adjusted_std,
            size=num_customers
        )
        
        # Calculate statistics
        distribution_stats = {
            'mean_risk': np.mean(risk_levels),
            'std_risk': np.std(risk_levels),
            'median_risk': np.median(risk_levels),
            'pct_high_risk': np.mean(risk_levels > base_mean * 1.5),
            'pct_low_risk': np.mean(risk_levels < base_mean * 0.7),
            'skewness': stats.skew(risk_levels)
        }
        
        return risk_levels, distribution_stats
    
    def calculate_selection_impact(
        self,
        base_loss_ratio: float,
        selection_modifier: float,
        volume_impact: float = 1.0
    ) -> Dict[str, float]:
        """Calculate financial impact of adverse selection.
        
        Args:
            base_loss_ratio: Expected loss ratio without selection
            selection_modifier: Risk selection modifier
            volume_impact: Volume change from pricing
            
        Returns:
            Financial impact metrics
        """
        # Adjusted loss ratio from selection
        adjusted_loss_ratio = base_loss_ratio * selection_modifier
        
        # Profitability impact
        base_profit_margin = 1 - base_loss_ratio - 0.25  # Assume 25% expense ratio
        adjusted_profit_margin = 1 - adjusted_loss_ratio - 0.25
        
        # Volume-adjusted profit impact
        profit_impact = (adjusted_profit_margin * volume_impact) / base_profit_margin
        
        return {
            'base_loss_ratio': base_loss_ratio,
            'adjusted_loss_ratio': adjusted_loss_ratio,
            'loss_ratio_change': adjusted_loss_ratio - base_loss_ratio,
            'base_profit_margin': base_profit_margin,
            'adjusted_profit_margin': adjusted_profit_margin,
            'volume_impact': volume_impact,
            'total_profit_impact': profit_impact,
            'selection_penalty': 1 - profit_impact if profit_impact < 1 else 0
        }
    
    def model_death_spiral(
        self,
        initial_conditions: Dict[str, float],
        periods: int = 10
    ) -> List[Dict[str, float]]:
        """Model potential death spiral from adverse selection.
        
        Death spiral occurs when:
        1. Prices increase due to bad risks
        2. Good risks leave
        3. Risk pool worsens
        4. Prices increase further
        5. Repeat until collapse
        
        Args:
            initial_conditions: Starting market conditions
            periods: Number of periods to simulate
            
        Returns:
            List of period results showing spiral progression
        """
        results = []
        
        # Initial state
        price = initial_conditions.get('price', 1000)
        risk_level = initial_conditions.get('risk_level', 1.0)
        customer_base = initial_conditions.get('customers', 1000)
        market_price = initial_conditions.get('market_price', 1000)
        
        for period in range(periods):
            # Current relative price
            relative_price = price / market_price
            
            # Selection effect
            selection_modifier, _ = self.calculate_selection_modifier(
                price, market_price
            )
            
            # Customer attrition (good risks leave if price too high)
            if relative_price > 1.2:
                attrition_rate = min(0.5, (relative_price - 1.2) * 0.3)
                customers_lost = int(customer_base * attrition_rate)
                # Assume best risks leave first
                risk_level *= (1 + attrition_rate * 0.2)
                customer_base -= customers_lost
            else:
                customers_lost = 0
            
            # Update risk pool
            risk_level *= selection_modifier
            
            # Calculate required price increase
            loss_ratio = 0.7 * risk_level  # Base 70% loss ratio
            required_margin = 0.35  # 35% for expenses + profit
            breakeven_price = price * (loss_ratio + required_margin)
            
            # Price adjustment (with dampening)
            price = price * 0.7 + breakeven_price * 0.3
            
            # Record period results
            results.append({
                'period': period,
                'price': price,
                'relative_price': relative_price,
                'risk_level': risk_level,
                'customer_base': customer_base,
                'customers_lost': customers_lost,
                'loss_ratio': loss_ratio,
                'selection_modifier': selection_modifier
            })
            
            # Check for collapse
            if customer_base < initial_conditions.get('customers', 1000) * 0.1:
                logger.warning(f"Death spiral: 90% customer loss by period {period}")
                break
        
        return results
