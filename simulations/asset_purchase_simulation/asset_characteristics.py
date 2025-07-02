"""Asset characteristics mapping for portfolio construction.

This module translates between abstract portfolio characteristics
and specific asset allocations that achieve those characteristics.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)


class AssetCharacteristicsMapper:
    """Maps portfolio characteristics to asset allocations.
    
    Translates the five portfolio characteristics (risk, duration, 
    liquidity, credit, diversification) into specific asset class
    allocations that would achieve those characteristics.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize asset mapper.
        
        Args:
            config: Game configuration
        """
        self.config = config
        investment_params = config.get('investment_parameters', {})
        
        # Define asset classes and their characteristics
        self.asset_classes = investment_params.get('asset_classes', self._get_default_asset_classes())
        
        # Correlation matrix between asset classes
        self.correlation_matrix = investment_params.get(
            'risk_correlation_matrix',
            self._get_default_correlation_matrix()
        )
    
    def _get_default_asset_classes(self) -> Dict[str, Dict[str, float]]:
        """Get default asset class definitions.
        
        Returns:
            Dictionary of asset class characteristics
        """
        return {
            'treasury_bonds': {
                'risk': 0.1,
                'duration': 0.5,
                'liquidity': 1.0,
                'credit': 0.0,
                'expected_return': 0.03,
                'volatility': 0.02
            },
            'investment_grade_bonds': {
                'risk': 0.3,
                'duration': 0.6,
                'liquidity': 0.8,
                'credit': 0.3,
                'expected_return': 0.045,
                'volatility': 0.04
            },
            'high_yield_bonds': {
                'risk': 0.6,
                'duration': 0.4,
                'liquidity': 0.6,
                'credit': 0.8,
                'expected_return': 0.07,
                'volatility': 0.08
            },
            'public_equity': {
                'risk': 0.8,
                'duration': 0.7,
                'liquidity': 0.9,
                'credit': 0.0,
                'expected_return': 0.09,
                'volatility': 0.15
            },
            'real_estate': {
                'risk': 0.6,
                'duration': 0.8,
                'liquidity': 0.3,
                'credit': 0.2,
                'expected_return': 0.075,
                'volatility': 0.12
            },
            'private_equity': {
                'risk': 0.9,
                'duration': 0.9,
                'liquidity': 0.1,
                'credit': 0.1,
                'expected_return': 0.12,
                'volatility': 0.20
            },
            'commodities': {
                'risk': 0.7,
                'duration': 0.3,
                'liquidity': 0.7,
                'credit': 0.0,
                'expected_return': 0.06,
                'volatility': 0.18
            },
            'cash': {
                'risk': 0.0,
                'duration': 0.0,
                'liquidity': 1.0,
                'credit': 0.0,
                'expected_return': 0.02,
                'volatility': 0.001
            }
        }
    
    def _get_default_correlation_matrix(self) -> np.ndarray:
        """Get default correlation matrix for asset classes.
        
        Returns:
            Correlation matrix
        """
        # Order: treasury, IG bonds, HY bonds, equity, RE, PE, commodities, cash
        return np.array([
            [1.00, 0.80, 0.40, -0.10, 0.20, 0.10, -0.20, 0.10],  # Treasury
            [0.80, 1.00, 0.60, 0.20, 0.30, 0.25, -0.10, 0.15],   # IG Bonds
            [0.40, 0.60, 1.00, 0.65, 0.50, 0.60, 0.30, 0.10],    # HY Bonds
            [-0.10, 0.20, 0.65, 1.00, 0.70, 0.85, 0.40, -0.05],  # Equity
            [0.20, 0.30, 0.50, 0.70, 1.00, 0.75, 0.35, 0.05],    # Real Estate
            [0.10, 0.25, 0.60, 0.85, 0.75, 1.00, 0.30, 0.00],    # Private Equity
            [-0.20, -0.10, 0.30, 0.40, 0.35, 0.30, 1.00, 0.00],  # Commodities
            [0.10, 0.15, 0.10, -0.05, 0.05, 0.00, 0.00, 1.00]    # Cash
        ])
    
    def map_characteristics_to_allocation(
        self,
        target_characteristics: Dict[str, float],
        constraints: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """Map target characteristics to asset allocation.
        
        Args:
            target_characteristics: Target portfolio characteristics
            constraints: Allocation constraints (min/max per asset)
            
        Returns:
            Tuple of (asset_allocation, mapping_details)
        """
        # Use optimization to find allocation that matches characteristics
        from scipy.optimize import minimize
        
        asset_names = list(self.asset_classes.keys())
        n_assets = len(asset_names)
        
        # Initial guess (equal weight)
        initial_weights = np.ones(n_assets) / n_assets
        
        # Objective: minimize distance from target characteristics
        def objective(weights):
            portfolio_chars = self._calculate_portfolio_characteristics(weights)
            distance = 0
            for char in ['risk', 'duration', 'liquidity', 'credit']:
                if char in target_characteristics:
                    distance += (portfolio_chars[char] - target_characteristics[char])**2
            
            # Add diversification penalty
            # Herfindahl index for concentration
            concentration = np.sum(weights**2)
            diversification = 1 - concentration
            if 'diversification' in target_characteristics:
                distance += (diversification - target_characteristics['diversification'])**2 * 2
            
            return distance
        
        # Constraints
        constraints_list = []
        
        # Weights sum to 1
        constraints_list.append({
            'type': 'eq',
            'fun': lambda w: np.sum(w) - 1.0
        })
        
        # Non-negative weights
        bounds = [(0, 1) for _ in range(n_assets)]
        
        # Apply custom constraints if provided
        if constraints:
            for asset, limits in constraints.items():
                if asset in asset_names:
                    idx = asset_names.index(asset)
                    if 'min' in limits:
                        bounds[idx] = (limits['min'], bounds[idx][1])
                    if 'max' in limits:
                        bounds[idx] = (bounds[idx][0], limits['max'])
        
        # Optimize
        result = minimize(
            objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints_list,
            options={'ftol': 1e-8, 'maxiter': 300}
        )
        
        # Extract allocation
        if result.success:
            weights = result.x
        else:
            logger.warning(f"Asset mapping optimization failed: {result.message}")
            # Use heuristic allocation
            weights = self._heuristic_allocation(target_characteristics)
        
        # Create allocation dictionary
        allocation = {}
        for i, asset in enumerate(asset_names):
            if weights[i] > 0.001:  # Ignore very small weights
                allocation[asset] = float(weights[i])
        
        # Calculate achieved characteristics
        achieved_chars = self._calculate_portfolio_characteristics(weights)
        
        # Calculate tracking error
        tracking_error = {}
        for char in target_characteristics:
            if char in achieved_chars:
                tracking_error[char] = achieved_chars[char] - target_characteristics[char]
        
        mapping_details = {
            'achieved_characteristics': achieved_chars,
            'tracking_error': tracking_error,
            'optimization_success': result.success,
            'num_assets': len(allocation),
            'concentration': np.sum(weights**2),
            'expected_return': self._calculate_expected_return(weights),
            'expected_volatility': self._calculate_expected_volatility(weights)
        }
        
        return allocation, mapping_details
    
    def _calculate_portfolio_characteristics(self, weights: np.ndarray) -> Dict[str, float]:
        """Calculate portfolio characteristics from weights.
        
        Args:
            weights: Asset weights array
            
        Returns:
            Portfolio characteristics
        """
        characteristics = {
            'risk': 0,
            'duration': 0,
            'liquidity': 0,
            'credit': 0
        }
        
        asset_names = list(self.asset_classes.keys())
        
        # Weighted average characteristics
        for i, asset in enumerate(asset_names):
            asset_chars = self.asset_classes[asset]
            for char in characteristics:
                characteristics[char] += weights[i] * asset_chars.get(char, 0)
        
        # Diversification from concentration
        concentration = np.sum(weights**2)
        characteristics['diversification'] = 1 - concentration
        
        return characteristics
    
    def _calculate_expected_return(self, weights: np.ndarray) -> float:
        """Calculate expected portfolio return.
        
        Args:
            weights: Asset weights
            
        Returns:
            Expected return
        """
        expected_return = 0
        asset_names = list(self.asset_classes.keys())
        
        for i, asset in enumerate(asset_names):
            expected_return += weights[i] * self.asset_classes[asset]['expected_return']
        
        return expected_return
    
    def _calculate_expected_volatility(self, weights: np.ndarray) -> float:
        """Calculate expected portfolio volatility.
        
        Args:
            weights: Asset weights
            
        Returns:
            Expected volatility
        """
        # Get individual asset volatilities
        asset_names = list(self.asset_classes.keys())
        vols = np.array([self.asset_classes[asset]['volatility'] for asset in asset_names])
        
        # Portfolio variance = w' * Σ * w
        # where Σ = D * C * D (D is diagonal vol matrix, C is correlation)
        D = np.diag(vols)
        Sigma = D @ self.correlation_matrix @ D
        
        portfolio_variance = weights @ Sigma @ weights
        portfolio_vol = np.sqrt(portfolio_variance)
        
        return float(portfolio_vol)
    
    def _heuristic_allocation(self, target_characteristics: Dict[str, float]) -> np.ndarray:
        """Create heuristic allocation based on characteristics.
        
        Args:
            target_characteristics: Target characteristics
            
        Returns:
            Asset weights array
        """
        asset_names = list(self.asset_classes.keys())
        weights = np.zeros(len(asset_names))
        
        # Simple heuristic based on risk level
        risk_level = target_characteristics.get('risk', 0.5)
        liquidity_need = target_characteristics.get('liquidity', 0.5)
        
        if risk_level < 0.3:
            # Conservative
            weights[asset_names.index('treasury_bonds')] = 0.6
            weights[asset_names.index('investment_grade_bonds')] = 0.3
            weights[asset_names.index('cash')] = 0.1
        elif risk_level < 0.6:
            # Moderate
            weights[asset_names.index('treasury_bonds')] = 0.3
            weights[asset_names.index('investment_grade_bonds')] = 0.3
            weights[asset_names.index('public_equity')] = 0.3
            weights[asset_names.index('cash')] = 0.1
        else:
            # Aggressive
            weights[asset_names.index('public_equity')] = 0.5
            weights[asset_names.index('high_yield_bonds')] = 0.2
            weights[asset_names.index('real_estate')] = 0.15
            weights[asset_names.index('private_equity')] = 0.1
            weights[asset_names.index('cash')] = 0.05
        
        # Adjust for liquidity
        if liquidity_need > 0.7:
            # Increase liquid assets
            cash_idx = asset_names.index('cash')
            treasury_idx = asset_names.index('treasury_bonds')
            
            # Take from illiquid assets
            if 'private_equity' in asset_names:
                pe_idx = asset_names.index('private_equity')
                transfer = weights[pe_idx] * 0.5
                weights[pe_idx] -= transfer
                weights[cash_idx] += transfer * 0.5
                weights[treasury_idx] += transfer * 0.5
        
        # Normalize
        weights = weights / np.sum(weights)
        
        return weights
    
    def calculate_rebalancing_trades(
        self,
        current_allocation: Dict[str, float],
        target_allocation: Dict[str, float],
        portfolio_value: float
    ) -> Dict[str, Dict[str, float]]:
        """Calculate specific trades needed for rebalancing.
        
        Args:
            current_allocation: Current asset allocation (weights)
            target_allocation: Target asset allocation (weights)
            portfolio_value: Total portfolio value
            
        Returns:
            Dictionary of trades by asset
        """
        trades = {}
        
        all_assets = set(current_allocation.keys()) | set(target_allocation.keys())
        
        for asset in all_assets:
            current_weight = current_allocation.get(asset, 0)
            target_weight = target_allocation.get(asset, 0)
            
            weight_change = target_weight - current_weight
            
            if abs(weight_change) > 0.001:  # Ignore tiny changes
                trade_amount = weight_change * portfolio_value
                
                trades[asset] = {
                    'current_weight': current_weight,
                    'target_weight': target_weight,
                    'weight_change': weight_change,
                    'trade_amount': trade_amount,
                    'action': 'buy' if weight_change > 0 else 'sell'
                }
        
        return trades
