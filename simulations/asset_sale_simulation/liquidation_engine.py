"""Liquidation engine for forced asset sales during crises.

This module implements the logic for determining which assets to sell
when a company needs to raise cash quickly, with CFO skill affecting
the quality of liquidation decisions.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class LiquidationEngine:
    """Manages forced asset liquidations during financial stress.
    
    Key features:
    - Determines optimal liquidation order based on multiple factors
    - CFO skill affects which assets are chosen for sale
    - Market impact increases with liquidation size
    - Time pressure affects decision quality
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize liquidation engine.
        
        Args:
            config: Game configuration
        """
        self.config = config
        investment_params = config.get('investment_parameters', {})
        
        # Liquidation parameters
        self.liquidation_params = investment_params.get('liquidation_parameters', {
            'base_discount': 0.02,           # 2% minimum liquidation cost
            'size_impact_factor': 0.1,       # Impact increases with size
            'time_pressure_multiplier': 1.5, # Urgent sales cost more
            'skill_discount_reduction': 0.5, # High skill reduces costs by 50%
            'market_depth_factor': 0.05      # Market can absorb 5% without impact
        })
        
        # Asset liquidation preferences (optimal order)
        self.optimal_liquidation_order = [
            'cash',                    # No cost to "liquidate" cash
            'treasury_bonds',          # Most liquid
            'investment_grade_bonds',  # Liquid
            'public_equity',           # Fairly liquid
            'commodities',             # Moderate liquidity
            'high_yield_bonds',        # Less liquid
            'real_estate',            # Illiquid
            'private_equity'          # Most illiquid
        ]
    
    def calculate_liquidation_need(
        self,
        current_capital: float,
        required_capital: float,
        buffer_multiplier: float = 1.1
    ) -> float:
        """Calculate amount needed from liquidation.
        
        Args:
            current_capital: Current available capital
            required_capital: Minimum required capital
            buffer_multiplier: Safety buffer above minimum
            
        Returns:
            Amount to liquidate (0 if sufficient capital)
        """
        target_capital = required_capital * buffer_multiplier
        liquidation_need = max(0, target_capital - current_capital)
        
        if liquidation_need > 0:
            logger.info(
                f"Liquidation needed: ${liquidation_need:,.0f} "
                f"(current: ${current_capital:,.0f}, required: ${required_capital:,.0f})"
            )
        
        return liquidation_need
    
    def select_assets_for_liquidation(
        self,
        portfolio: Dict[str, float],
        portfolio_value: float,
        liquidation_need: float,
        cfo_skill: int,
        time_pressure: str = 'normal',
        market_conditions: Optional[str] = None
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """Select which assets to liquidate based on CFO skill.
        
        Args:
            portfolio: Current asset allocation (weights)
            portfolio_value: Total portfolio value
            liquidation_need: Amount needed from liquidation
            cfo_skill: CFO skill level (affects selection quality)
            time_pressure: 'urgent', 'normal', or 'flexible'
            market_conditions: Current market state
            
        Returns:
            Tuple of (assets_to_sell, liquidation_details)
        """
        # Convert weights to dollar amounts
        asset_values = {
            asset: weight * portfolio_value
            for asset, weight in portfolio.items()
        }
        
        # Determine liquidation order based on skill
        if cfo_skill >= 70:
            # Skilled CFO uses optimal order
            liquidation_order = self.optimal_liquidation_order.copy()
        elif cfo_skill >= 40:
            # Moderate skill: some mistakes
            liquidation_order = self._shuffle_order_by_skill(
                self.optimal_liquidation_order.copy(), 
                cfo_skill
            )
        else:
            # Low skill: poor choices (might sell illiquid first)
            liquidation_order = list(asset_values.keys())
            np.random.shuffle(liquidation_order)
        
        # Select assets to meet liquidation need
        assets_to_sell = {}
        amount_raised = 0
        liquidation_costs = {}
        
        for asset in liquidation_order:
            if asset not in asset_values or asset_values[asset] <= 0:
                continue
            
            if amount_raised >= liquidation_need:
                break
            
            # Calculate how much to sell from this asset
            remaining_need = liquidation_need - amount_raised
            available_amount = asset_values[asset]
            
            # Skill affects whether CFO sells entire positions
            if cfo_skill < 50:
                # Low skill: tend to liquidate entire positions
                amount_to_sell = available_amount
            else:
                # Higher skill: sell only what's needed
                amount_to_sell = min(available_amount, remaining_need * 1.1)
            
            # Calculate liquidation discount
            discount = self._calculate_liquidation_discount(
                asset=asset,
                amount=amount_to_sell,
                portfolio_value=portfolio_value,
                time_pressure=time_pressure,
                market_conditions=market_conditions,
                cfo_skill=cfo_skill
            )
            
            # Record sale
            assets_to_sell[asset] = amount_to_sell
            liquidation_costs[asset] = discount
            amount_raised += amount_to_sell * (1 - discount)
        
        # Calculate total metrics
        total_sold = sum(assets_to_sell.values())
        total_costs = sum(
            amount * liquidation_costs[asset]
            for asset, amount in assets_to_sell.items()
        )
        avg_discount = total_costs / total_sold if total_sold > 0 else 0
        
        # Determine if liquidation was sufficient
        shortfall = max(0, liquidation_need - amount_raised)
        
        liquidation_details = {
            'liquidation_need': liquidation_need,
            'amount_raised': amount_raised,
            'shortfall': shortfall,
            'total_sold': total_sold,
            'total_costs': total_costs,
            'average_discount': avg_discount,
            'liquidation_costs': liquidation_costs,
            'num_assets_sold': len(assets_to_sell),
            'cfo_skill_category': self._get_skill_category(cfo_skill),
            'liquidation_quality': self._assess_liquidation_quality(
                assets_to_sell, liquidation_costs, cfo_skill
            )
        }
        
        if shortfall > 0:
            logger.warning(
                f"Liquidation shortfall: ${shortfall:,.0f} "
                f"(raised ${amount_raised:,.0f} of ${liquidation_need:,.0f})"
            )
        
        return assets_to_sell, liquidation_details
    
    def _shuffle_order_by_skill(
        self, 
        optimal_order: List[str], 
        cfo_skill: int
    ) -> List[str]:
        """Partially shuffle liquidation order based on skill.
        
        Args:
            optimal_order: Optimal liquidation sequence
            cfo_skill: CFO skill level
            
        Returns:
            Shuffled order (more shuffled = lower skill)
        """
        # Calculate number of swaps based on skill
        max_swaps = len(optimal_order) - 1
        skill_factor = (100 - cfo_skill) / 100
        num_swaps = int(max_swaps * skill_factor * 0.5)
        
        order = optimal_order.copy()
        
        # Perform random swaps
        for _ in range(num_swaps):
            i, j = np.random.choice(len(order), 2, replace=False)
            order[i], order[j] = order[j], order[i]
        
        return order
    
    def _calculate_liquidation_discount(
        self,
        asset: str,
        amount: float,
        portfolio_value: float,
        time_pressure: str,
        market_conditions: Optional[str],
        cfo_skill: int
    ) -> float:
        """Calculate discount (haircut) for liquidating an asset.
        
        Args:
            asset: Asset type being sold
            amount: Dollar amount being sold
            portfolio_value: Total portfolio value
            time_pressure: Urgency of sale
            market_conditions: Current market state
            cfo_skill: CFO skill level
            
        Returns:
            Discount rate (0-1, where 0.1 = 10% discount)
        """
        # Base discount by asset type
        asset_discounts = {
            'cash': 0.0,
            'treasury_bonds': 0.005,
            'investment_grade_bonds': 0.01,
            'public_equity': 0.02,
            'commodities': 0.03,
            'high_yield_bonds': 0.04,
            'real_estate': 0.08,
            'private_equity': 0.15
        }
        
        base_discount = asset_discounts.get(asset, 0.05)
        
        # Size impact (larger sales have bigger impact)
        size_ratio = amount / portfolio_value
        market_depth = self.liquidation_params['market_depth_factor']
        
        if size_ratio > market_depth:
            size_impact = (size_ratio - market_depth) * self.liquidation_params['size_impact_factor']
        else:
            size_impact = 0
        
        # Time pressure impact
        time_multipliers = {
            'urgent': self.liquidation_params['time_pressure_multiplier'],
            'normal': 1.0,
            'flexible': 0.8
        }
        time_multiplier = time_multipliers.get(time_pressure, 1.0)
        
        # Market conditions impact
        market_multipliers = {
            'crisis': 2.0,
            'stressed': 1.5,
            'normal': 1.0,
            'boom': 0.8
        }
        market_multiplier = market_multipliers.get(market_conditions, 1.0)
        
        # Calculate total discount before skill adjustment
        total_discount = (base_discount + size_impact) * time_multiplier * market_multiplier
        
        # CFO skill reduces discount
        skill_factor = cfo_skill / 100
        skill_reduction = skill_factor * self.liquidation_params['skill_discount_reduction']
        final_discount = total_discount * (1 - skill_reduction)
        
        # Cap at reasonable maximum
        final_discount = min(final_discount, 0.5)  # Max 50% discount
        
        return final_discount
    
    def _get_skill_category(self, cfo_skill: int) -> str:
        """Get skill category name.
        
        Args:
            cfo_skill: CFO skill level
            
        Returns:
            Skill category
        """
        if cfo_skill < 30:
            return 'novice'
        elif cfo_skill < 50:
            return 'competent'
        elif cfo_skill < 70:
            return 'skilled'
        elif cfo_skill < 85:
            return 'expert'
        else:
            return 'master'
    
    def _assess_liquidation_quality(
        self,
        assets_sold: Dict[str, float],
        liquidation_costs: Dict[str, float],
        cfo_skill: int
    ) -> str:
        """Assess quality of liquidation decisions.
        
        Args:
            assets_sold: Assets and amounts sold
            liquidation_costs: Discount rates by asset
            cfo_skill: CFO skill level
            
        Returns:
            Quality assessment
        """
        if not assets_sold:
            return 'none'
        
        # Calculate weighted average liquidity of assets sold
        total_sold = sum(assets_sold.values())
        
        # Check if liquid assets were prioritized
        liquid_assets = ['cash', 'treasury_bonds', 'investment_grade_bonds', 'public_equity']
        liquid_portion = sum(
            amount for asset, amount in assets_sold.items()
            if asset in liquid_assets
        ) / total_sold
        
        # Calculate average discount
        avg_discount = sum(
            amount * liquidation_costs[asset]
            for asset, amount in assets_sold.items()
        ) / total_sold
        
        # Assess quality
        if liquid_portion > 0.8 and avg_discount < 0.03:
            return 'excellent'
        elif liquid_portion > 0.6 and avg_discount < 0.05:
            return 'good'
        elif liquid_portion > 0.4 and avg_discount < 0.08:
            return 'fair'
        else:
            return 'poor'
    
    def calculate_post_liquidation_portfolio(
        self,
        original_portfolio: Dict[str, float],
        portfolio_value: float,
        assets_sold: Dict[str, float],
        liquidation_costs: Dict[str, float]
    ) -> Tuple[Dict[str, float], float]:
        """Calculate portfolio after liquidation.
        
        Args:
            original_portfolio: Original allocation (weights)
            portfolio_value: Original portfolio value
            assets_sold: Assets and amounts sold
            liquidation_costs: Discounts applied
            
        Returns:
            Tuple of (new_portfolio_weights, new_portfolio_value)
        """
        # Calculate remaining values after sales
        remaining_values = {}
        total_remaining = 0
        
        for asset, weight in original_portfolio.items():
            original_value = weight * portfolio_value
            sold_amount = assets_sold.get(asset, 0)
            remaining_value = original_value - sold_amount
            
            if remaining_value > 0:
                remaining_values[asset] = remaining_value
                total_remaining += remaining_value
        
        # Add cash raised from liquidation
        cash_raised = sum(
            amount * (1 - liquidation_costs.get(asset, 0))
            for asset, amount in assets_sold.items()
        )
        
        if 'cash' in remaining_values:
            remaining_values['cash'] += cash_raised
        else:
            remaining_values['cash'] = cash_raised
        
        total_remaining += cash_raised
        
        # Convert to weights
        new_portfolio = {}
        if total_remaining > 0:
            for asset, value in remaining_values.items():
                new_portfolio[asset] = value / total_remaining
        
        return new_portfolio, total_remaining
