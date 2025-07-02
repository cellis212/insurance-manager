"""Market impact modeling for asset liquidations.

This module calculates how forced asset sales affect market prices
and the costs incurred by companies during liquidation events.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class MarketImpactModel:
    """Models market impact of asset liquidations.
    
    Key features:
    - Price impact increases with sale size
    - Market depth varies by asset class
    - Temporary vs permanent price effects
    - Contagion effects in stressed markets
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize market impact model.
        
        Args:
            config: Game configuration
        """
        self.config = config
        investment_params = config.get('investment_parameters', {})
        
        # Market impact parameters
        self.impact_params = investment_params.get('market_impact', {
            'temporary_impact_factor': 0.5,    # 50% of impact is temporary
            'permanent_impact_factor': 0.5,    # 50% is permanent
            'depth_recovery_rate': 0.2,        # Market depth recovers 20% per period
            'contagion_threshold': 0.1,        # 10% market drop triggers contagion
            'volatility_multiplier': 2.0       # Vol doubles during liquidation
        })
        
        # Market depth by asset class (% of market that can be absorbed)
        self.market_depth = {
            'cash': float('inf'),              # Unlimited depth
            'treasury_bonds': 0.20,            # Can absorb 20% without impact
            'investment_grade_bonds': 0.10,    # 10% depth
            'public_equity': 0.15,             # 15% depth
            'commodities': 0.08,               # 8% depth
            'high_yield_bonds': 0.05,          # 5% depth
            'real_estate': 0.03,               # 3% depth
            'private_equity': 0.01             # 1% depth (very illiquid)
        }
        
        # Price impact coefficients (Kyle lambda)
        self.price_impact_coefficients = {
            'treasury_bonds': 0.001,
            'investment_grade_bonds': 0.003,
            'public_equity': 0.005,
            'commodities': 0.008,
            'high_yield_bonds': 0.010,
            'real_estate': 0.020,
            'private_equity': 0.050
        }
    
    def calculate_price_impact(
        self,
        asset_class: str,
        sale_amount: float,
        market_size: float,
        market_conditions: str = 'normal',
        is_forced_sale: bool = True
    ) -> Dict[str, float]:
        """Calculate price impact of selling assets.
        
        Uses square-root market impact model:
        Impact = λ * sqrt(Volume/ADV) * σ
        
        Args:
            asset_class: Type of asset being sold
            sale_amount: Dollar amount being sold
            market_size: Total market size for asset class
            market_conditions: Current market state
            is_forced_sale: Whether sale is forced (higher impact)
            
        Returns:
            Price impact metrics
        """
        # Calculate size relative to market
        if market_size <= 0:
            relative_size = 1.0
        else:
            relative_size = sale_amount / market_size
        
        # Get market depth for asset
        depth = self.market_depth.get(asset_class, 0.05)
        
        # Calculate base impact using square-root model
        if relative_size <= depth:
            # Within normal market depth
            base_impact = self.price_impact_coefficients.get(asset_class, 0.01) * np.sqrt(relative_size)
        else:
            # Beyond market depth - accelerating impact
            excess = relative_size - depth
            base_impact = (
                self.price_impact_coefficients.get(asset_class, 0.01) * np.sqrt(depth) +
                self.price_impact_coefficients.get(asset_class, 0.01) * excess * 2
            )
        
        # Adjust for market conditions
        condition_multipliers = {
            'crisis': 3.0,
            'stressed': 2.0,
            'normal': 1.0,
            'boom': 0.7
        }
        condition_mult = condition_multipliers.get(market_conditions, 1.0)
        
        # Forced sales have higher impact
        if is_forced_sale:
            forced_mult = 1.5
        else:
            forced_mult = 1.0
        
        # Calculate total impact
        total_impact = base_impact * condition_mult * forced_mult
        
        # Split into temporary and permanent components
        temporary_impact = total_impact * self.impact_params['temporary_impact_factor']
        permanent_impact = total_impact * self.impact_params['permanent_impact_factor']
        
        # Cap total impact at reasonable level
        total_impact = min(total_impact, 0.3)  # Max 30% price impact
        
        return {
            'total_impact': total_impact,
            'temporary_impact': temporary_impact,
            'permanent_impact': permanent_impact,
            'relative_size': relative_size,
            'exceeded_depth': relative_size > depth,
            'depth_utilization': min(1.0, relative_size / depth) if depth > 0 else 1.0
        }
    
    def calculate_market_wide_impact(
        self,
        liquidations: List[Dict[str, Any]],
        market_sizes: Dict[str, float],
        market_conditions: str = 'normal'
    ) -> Dict[str, Any]:
        """Calculate aggregate market impact from multiple liquidations.
        
        Args:
            liquidations: List of liquidation events
            market_sizes: Market sizes by asset class
            market_conditions: Current market state
            
        Returns:
            Market-wide impact metrics
        """
        # Aggregate liquidations by asset class
        total_by_asset = defaultdict(float)
        for liquidation in liquidations:
            for asset, amount in liquidation.get('assets_sold', {}).items():
                total_by_asset[asset] += amount
        
        # Calculate impact by asset class
        asset_impacts = {}
        total_market_impact = 0
        
        for asset, total_amount in total_by_asset.items():
            if asset == 'cash':
                continue  # No impact for cash
            
            market_size = market_sizes.get(asset, 1e9)  # Default 1B market
            impact = self.calculate_price_impact(
                asset_class=asset,
                sale_amount=total_amount,
                market_size=market_size,
                market_conditions=market_conditions,
                is_forced_sale=True
            )
            
            asset_impacts[asset] = impact
            total_market_impact += impact['total_impact'] * (total_amount / sum(total_by_asset.values()))
        
        # Check for contagion effects
        contagion_triggered = total_market_impact > self.impact_params['contagion_threshold']
        
        if contagion_triggered:
            # Contagion amplifies impacts
            contagion_multiplier = 1.5
            total_market_impact *= contagion_multiplier
            
            for asset in asset_impacts:
                asset_impacts[asset]['total_impact'] *= contagion_multiplier
        
        # Calculate volatility spike
        volatility_increase = min(
            self.impact_params['volatility_multiplier'],
            1 + total_market_impact * 2
        )
        
        return {
            'total_market_impact': total_market_impact,
            'asset_impacts': asset_impacts,
            'total_liquidated': sum(total_by_asset.values()),
            'num_assets_affected': len(total_by_asset),
            'contagion_triggered': contagion_triggered,
            'volatility_multiplier': volatility_increase,
            'market_stress_level': self._classify_stress_level(total_market_impact)
        }
    
    def _classify_stress_level(self, total_impact: float) -> str:
        """Classify market stress level based on impact.
        
        Args:
            total_impact: Total market impact
            
        Returns:
            Stress level classification
        """
        if total_impact < 0.02:
            return 'minimal'
        elif total_impact < 0.05:
            return 'moderate'
        elif total_impact < 0.10:
            return 'significant'
        elif total_impact < 0.20:
            return 'severe'
        else:
            return 'crisis'
    
    def simulate_price_recovery(
        self,
        initial_impact: Dict[str, float],
        periods: int = 10
    ) -> List[Dict[str, float]]:
        """Simulate price recovery after liquidation.
        
        Args:
            initial_impact: Initial price impact
            periods: Number of periods to simulate
            
        Returns:
            List of price levels over time
        """
        price_path = []
        
        # Start with full impact
        current_temporary = initial_impact['temporary_impact']
        permanent_impact = initial_impact['permanent_impact']
        
        for period in range(periods):
            # Temporary impact decays exponentially
            decay_rate = self.impact_params['depth_recovery_rate']
            current_temporary *= (1 - decay_rate)
            
            # Total price impact
            total_impact = permanent_impact + current_temporary
            
            # Price level (1 = normal)
            price_level = 1 - total_impact
            
            price_path.append({
                'period': period,
                'price_level': price_level,
                'temporary_component': current_temporary,
                'permanent_component': permanent_impact,
                'total_impact': total_impact
            })
        
        return price_path
    
    def calculate_liquidation_cascade(
        self,
        initial_liquidation: Dict[str, Any],
        market_participants: List[Dict[str, Any]],
        market_sizes: Dict[str, float]
    ) -> Dict[str, Any]:
        """Model potential liquidation cascade from initial forced sale.
        
        Args:
            initial_liquidation: Initial liquidation event
            market_participants: Other market participants
            market_sizes: Market sizes by asset
            
        Returns:
            Cascade analysis results
        """
        # Track cascade rounds
        cascade_rounds = []
        current_liquidations = [initial_liquidation]
        total_liquidated = 0
        affected_participants = set()
        
        for round_num in range(5):  # Max 5 rounds of contagion
            if not current_liquidations:
                break
            
            # Calculate market impact of current round
            round_impact = self.calculate_market_wide_impact(
                current_liquidations,
                market_sizes,
                'stressed'  # Cascade implies stressed conditions
            )
            
            # Determine which participants are forced to liquidate
            next_liquidations = []
            
            for participant in market_participants:
                if participant['id'] in affected_participants:
                    continue
                
                # Check if price drops trigger margin calls
                portfolio_impact = 0
                for asset, weight in participant.get('portfolio', {}).items():
                    if asset in round_impact['asset_impacts']:
                        asset_impact = round_impact['asset_impacts'][asset]['total_impact']
                        portfolio_impact += weight * asset_impact
                
                # Margin call if portfolio drops too much
                if portfolio_impact > participant.get('margin_threshold', 0.15):
                    affected_participants.add(participant['id'])
                    
                    # Create liquidation event
                    liquidation_amount = participant.get('portfolio_value', 0) * portfolio_impact
                    next_liquidations.append({
                        'participant_id': participant['id'],
                        'amount': liquidation_amount,
                        'trigger': 'margin_call',
                        'round': round_num + 1
                    })
            
            # Record round
            cascade_rounds.append({
                'round': round_num,
                'liquidations': len(current_liquidations),
                'amount_liquidated': sum(l.get('amount', 0) for l in current_liquidations),
                'market_impact': round_impact['total_market_impact'],
                'new_margin_calls': len(next_liquidations)
            })
            
            total_liquidated += sum(l.get('amount', 0) for l in current_liquidations)
            current_liquidations = next_liquidations
        
        return {
            'cascade_rounds': cascade_rounds,
            'total_rounds': len(cascade_rounds),
            'total_liquidated': total_liquidated,
            'participants_affected': len(affected_participants),
            'cascade_severity': self._classify_cascade_severity(len(affected_participants), len(market_participants))
        }
    
    def _classify_cascade_severity(self, affected: int, total: int) -> str:
        """Classify cascade severity.
        
        Args:
            affected: Number affected
            total: Total participants
            
        Returns:
            Severity classification
        """
        if total == 0:
            return 'none'
        
        affected_pct = affected / total
        
        if affected_pct < 0.05:
            return 'minimal'
        elif affected_pct < 0.15:
            return 'moderate'
        elif affected_pct < 0.30:
            return 'significant'
        elif affected_pct < 0.50:
            return 'severe'
        else:
            return 'systemic'
