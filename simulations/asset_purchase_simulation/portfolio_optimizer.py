"""Portfolio optimization for insurance company investments.

This module implements portfolio construction using characteristic-based
optimization with constraints typical for insurance companies.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from typing import Dict, List, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """Optimizes insurance investment portfolios based on characteristics.
    
    Insurance companies must balance:
    - Return objectives
    - Risk constraints
    - Liquidity needs
    - Regulatory requirements
    - Asset-liability matching
    
    Uses a characteristic-based approach where portfolios are defined
    by five key dimensions rather than individual securities.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize portfolio optimizer.
        
        Args:
            config: Game configuration with investment parameters
        """
        self.config = config
        investment_params = config.get('investment_parameters', {})
        
        # Portfolio characteristic bounds
        self.characteristic_bounds = investment_params.get('characteristic_bounds', {
            'risk': (0.0, 1.0),         # 0 = risk-free, 1 = high risk
            'duration': (0.0, 1.0),      # 0 = short, 1 = long duration
            'liquidity': (0.0, 1.0),     # 0 = illiquid, 1 = highly liquid
            'credit': (0.0, 1.0),        # 0 = AAA, 1 = high yield
            'diversification': (0.0, 1.0) # 0 = concentrated, 1 = diversified
        })
        
        # Return model parameters
        self.return_model = investment_params.get('return_model', {
            'base_rate': 0.03,           # Risk-free rate
            'risk_premium': 0.06,        # Max risk premium
            'duration_premium': 0.02,    # Term premium
            'illiquidity_premium': 0.03, # Liquidity premium
            'credit_premium': 0.04,      # Credit spread
            'diversification_benefit': 0.01
        })
        
        # Risk model parameters
        self.risk_model = investment_params.get('risk_model', {
            'base_volatility': 0.02,     # Risk-free volatility
            'risk_multiplier': 0.15,     # Additional vol per risk unit
            'concentration_penalty': 0.05 # Penalty for low diversification
        })
        
        # Regulatory constraints
        self.regulatory_constraints = investment_params.get('regulatory_constraints', {
            'max_risk': 0.7,             # Maximum average risk
            'min_liquidity': 0.3,        # Minimum liquidity
            'max_credit_risk': 0.5,      # Maximum credit risk
            'capital_charge_multiplier': 0.1
        })
    
    def optimize_portfolio(
        self,
        target_return: Optional[float] = None,
        risk_tolerance: float = 0.5,
        liquidity_need: float = 0.3,
        constraints: Optional[Dict[str, Any]] = None,
        current_portfolio: Optional[Dict[str, float]] = None
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """Optimize portfolio characteristics.
        
        Args:
            target_return: Target return (None for max Sharpe)
            risk_tolerance: Risk tolerance (0-1)
            liquidity_need: Minimum liquidity requirement
            constraints: Additional constraints
            current_portfolio: Current portfolio for rebalancing
            
        Returns:
            Tuple of (optimal_characteristics, optimization_details)
        """
        # Set up optimization problem
        initial_guess = self._get_initial_guess(current_portfolio)
        
        # Objective function (negative Sharpe ratio for maximization)
        def objective(x):
            characteristics = self._array_to_characteristics(x)
            expected_return = self._calculate_expected_return(characteristics)
            portfolio_risk = self._calculate_portfolio_risk(characteristics)
            
            if portfolio_risk > 0:
                sharpe_ratio = (expected_return - self.return_model['base_rate']) / portfolio_risk
                return -sharpe_ratio  # Negative for minimization
            else:
                return 1000  # Penalty for zero risk
        
        # Constraints
        constraints_list = []
        
        # Regulatory constraints
        constraints_list.append({
            'type': 'ineq',
            'fun': lambda x: self.regulatory_constraints['max_risk'] - x[0]  # risk <= max_risk
        })
        constraints_list.append({
            'type': 'ineq',
            'fun': lambda x: x[2] - self.regulatory_constraints['min_liquidity']  # liquidity >= min
        })
        constraints_list.append({
            'type': 'ineq',
            'fun': lambda x: self.regulatory_constraints['max_credit_risk'] - x[3]  # credit <= max
        })
        
        # Liquidity need constraint
        constraints_list.append({
            'type': 'ineq',
            'fun': lambda x: x[2] - liquidity_need  # liquidity >= need
        })
        
        # Target return constraint if specified
        if target_return is not None:
            constraints_list.append({
                'type': 'eq',
                'fun': lambda x: self._calculate_expected_return(
                    self._array_to_characteristics(x)
                ) - target_return
            })
        
        # Risk tolerance constraint
        constraints_list.append({
            'type': 'ineq',
            'fun': lambda x: risk_tolerance - x[0]  # risk <= tolerance
        })
        
        # Add any additional constraints
        if constraints:
            for name, value in constraints.items():
                if name in ['min_duration', 'max_duration', 'min_diversification']:
                    # Convert to constraint functions
                    if name == 'min_duration':
                        constraints_list.append({
                            'type': 'ineq',
                            'fun': lambda x: x[1] - value
                        })
                    elif name == 'max_duration':
                        constraints_list.append({
                            'type': 'ineq',
                            'fun': lambda x: value - x[1]
                        })
                    elif name == 'min_diversification':
                        constraints_list.append({
                            'type': 'ineq',
                            'fun': lambda x: x[4] - value
                        })
        
        # Bounds for each characteristic
        bounds = [
            self.characteristic_bounds['risk'],
            self.characteristic_bounds['duration'],
            self.characteristic_bounds['liquidity'],
            self.characteristic_bounds['credit'],
            self.characteristic_bounds['diversification']
        ]
        
        # Optimize
        result = minimize(
            objective,
            initial_guess,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints_list,
            options={'ftol': 1e-6, 'maxiter': 200}
        )
        
        # Extract results
        if result.success:
            optimal_characteristics = self._array_to_characteristics(result.x)
        else:
            logger.warning(f"Optimization failed: {result.message}")
            # Return conservative portfolio
            optimal_characteristics = {
                'risk': min(0.3, risk_tolerance),
                'duration': 0.5,
                'liquidity': max(0.5, liquidity_need),
                'credit': 0.2,
                'diversification': 0.7
            }
        
        # Calculate portfolio metrics
        expected_return = self._calculate_expected_return(optimal_characteristics)
        portfolio_risk = self._calculate_portfolio_risk(optimal_characteristics)
        sharpe_ratio = (expected_return - self.return_model['base_rate']) / portfolio_risk if portfolio_risk > 0 else 0
        
        optimization_details = {
            'success': result.success,
            'message': result.message if hasattr(result, 'message') else 'OK',
            'expected_return': expected_return,
            'portfolio_risk': portfolio_risk,
            'sharpe_ratio': sharpe_ratio,
            'capital_requirement': self._calculate_capital_requirement(optimal_characteristics),
            'iterations': result.nit if hasattr(result, 'nit') else 0
        }
        
        logger.info(
            f"Portfolio optimized: return={expected_return:.3%}, "
            f"risk={portfolio_risk:.3%}, Sharpe={sharpe_ratio:.2f}"
        )
        
        return optimal_characteristics, optimization_details
    
    def _get_initial_guess(
        self, 
        current_portfolio: Optional[Dict[str, float]] = None
    ) -> np.ndarray:
        """Get initial guess for optimization.
        
        Args:
            current_portfolio: Current portfolio characteristics
            
        Returns:
            Initial guess array
        """
        if current_portfolio:
            return np.array([
                current_portfolio.get('risk', 0.5),
                current_portfolio.get('duration', 0.5),
                current_portfolio.get('liquidity', 0.5),
                current_portfolio.get('credit', 0.3),
                current_portfolio.get('diversification', 0.7)
            ])
        else:
            # Conservative starting point
            return np.array([0.4, 0.5, 0.6, 0.3, 0.7])
    
    def _array_to_characteristics(self, x: np.ndarray) -> Dict[str, float]:
        """Convert optimization array to characteristics dict.
        
        Args:
            x: Optimization variables array
            
        Returns:
            Characteristics dictionary
        """
        return {
            'risk': x[0],
            'duration': x[1],
            'liquidity': x[2],
            'credit': x[3],
            'diversification': x[4]
        }
    
    def _calculate_expected_return(self, characteristics: Dict[str, float]) -> float:
        """Calculate expected return from portfolio characteristics.
        
        Args:
            characteristics: Portfolio characteristics
            
        Returns:
            Expected annual return
        """
        base_return = self.return_model['base_rate']
        
        # Add premiums for each characteristic
        risk_return = characteristics['risk'] * self.return_model['risk_premium']
        duration_return = characteristics['duration'] * self.return_model['duration_premium']
        illiquidity_return = (1 - characteristics['liquidity']) * self.return_model['illiquidity_premium']
        credit_return = characteristics['credit'] * self.return_model['credit_premium']
        diversification_return = characteristics['diversification'] * self.return_model['diversification_benefit']
        
        total_return = (
            base_return + 
            risk_return + 
            duration_return + 
            illiquidity_return + 
            credit_return + 
            diversification_return
        )
        
        return total_return
    
    def _calculate_portfolio_risk(self, characteristics: Dict[str, float]) -> float:
        """Calculate portfolio risk (volatility) from characteristics.
        
        Args:
            characteristics: Portfolio characteristics
            
        Returns:
            Portfolio volatility
        """
        base_vol = self.risk_model['base_volatility']
        
        # Risk increases volatility
        risk_vol = characteristics['risk'] * self.risk_model['risk_multiplier']
        
        # Duration adds volatility
        duration_vol = characteristics['duration'] * 0.05
        
        # Credit risk adds volatility
        credit_vol = characteristics['credit'] * 0.08
        
        # Low diversification increases volatility
        concentration_vol = (1 - characteristics['diversification']) * self.risk_model['concentration_penalty']
        
        # Combine volatilities (simplified - could use correlation matrix)
        total_vol = np.sqrt(
            base_vol**2 + 
            risk_vol**2 + 
            duration_vol**2 + 
            credit_vol**2 + 
            concentration_vol**2
        )
        
        return total_vol
    
    def _calculate_capital_requirement(self, characteristics: Dict[str, float]) -> float:
        """Calculate regulatory capital requirement.
        
        Args:
            characteristics: Portfolio characteristics
            
        Returns:
            Capital requirement as fraction of portfolio value
        """
        # Simplified risk-based capital calculation
        risk_charge = characteristics['risk'] * 0.08
        credit_charge = characteristics['credit'] * 0.06
        concentration_charge = (1 - characteristics['diversification']) * 0.02
        
        total_charge = (risk_charge + credit_charge + concentration_charge) * \
                      self.regulatory_constraints['capital_charge_multiplier']
        
        return total_charge
    
    def rebalance_portfolio(
        self,
        current_characteristics: Dict[str, float],
        target_characteristics: Dict[str, float],
        rebalancing_cost: float = 0.001,
        max_turnover: float = 0.3
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """Calculate optimal rebalancing trades.
        
        Args:
            current_characteristics: Current portfolio
            target_characteristics: Target portfolio
            rebalancing_cost: Transaction cost per unit change
            max_turnover: Maximum allowed turnover
            
        Returns:
            Tuple of (new_characteristics, rebalancing_details)
        """
        # Calculate required changes
        changes = {}
        total_change = 0
        
        for char in ['risk', 'duration', 'liquidity', 'credit', 'diversification']:
            change = target_characteristics[char] - current_characteristics[char]
            changes[char] = change
            total_change += abs(change)
        
        # Apply turnover constraint
        if total_change > max_turnover:
            # Scale down changes
            scaling_factor = max_turnover / total_change
            for char in changes:
                changes[char] *= scaling_factor
        
        # Calculate new portfolio
        new_characteristics = {}
        for char in current_characteristics:
            new_characteristics[char] = current_characteristics[char] + changes.get(char, 0)
            # Ensure bounds
            new_characteristics[char] = np.clip(
                new_characteristics[char],
                self.characteristic_bounds[char][0],
                self.characteristic_bounds[char][1]
            )
        
        # Calculate costs and benefits
        transaction_cost = total_change * rebalancing_cost
        current_return = self._calculate_expected_return(current_characteristics)
        new_return = self._calculate_expected_return(new_characteristics)
        return_improvement = new_return - current_return
        
        rebalancing_details = {
            'changes': changes,
            'total_turnover': min(total_change, max_turnover),
            'transaction_cost': transaction_cost,
            'return_improvement': return_improvement,
            'net_benefit': return_improvement - transaction_cost,
            'scaled': total_change > max_turnover
        }
        
        return new_characteristics, rebalancing_details
