"""Crisis triggers for forced liquidation events.

This module identifies conditions that trigger forced asset sales,
such as capital requirement breaches, margin calls, and catastrophic losses.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CrisisTriggerDetector:
    """Detects and analyzes conditions that trigger liquidation crises.
    
    Monitors for:
    - Regulatory capital breaches
    - Catastrophic loss events
    - Operational losses
    - Market value declines
    - Liquidity shortfalls
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize crisis trigger detector.
        
        Args:
            config: Game configuration
        """
        self.config = config
        
        # Regulatory parameters
        regulatory_params = config.get('regulatory_parameters', {})
        self.capital_requirements = regulatory_params.get('capital_requirements', {
            'minimum_ratio': 2.0,      # 200% of required capital
            'target_ratio': 3.0,       # 300% target
            'warning_ratio': 2.5       # Warning level
        })
        
        # Crisis thresholds
        self.crisis_thresholds = {
            'catastrophic_loss_pct': 0.25,    # 25% capital loss
            'market_decline_trigger': 0.20,    # 20% portfolio decline
            'liquidity_coverage_min': 1.2,     # 120% of short-term needs
            'combined_ratio_max': 1.15,        # 115% combined ratio crisis
            'consecutive_losses': 3            # 3 turns of losses
        }
        
        # Time pressure levels
        self.time_pressure_levels = {
            'immediate': 0,      # Same day
            'urgent': 1,         # 1 week
            'normal': 2,         # 2 weeks
            'flexible': 4        # 4 weeks
        }
    
    def check_all_triggers(
        self,
        company_state: Dict[str, Any],
        market_conditions: Dict[str, Any],
        turn_number: int
    ) -> List[Dict[str, Any]]:
        """Check all potential crisis triggers for a company.
        
        Args:
            company_state: Current company financial state
            market_conditions: Current market conditions
            turn_number: Current game turn
            
        Returns:
            List of triggered crises with details
        """
        triggered_crises = []
        
        # Check regulatory capital
        capital_crisis = self._check_capital_requirements(company_state)
        if capital_crisis:
            triggered_crises.append(capital_crisis)
        
        # Check catastrophic losses
        cat_crisis = self._check_catastrophic_losses(company_state)
        if cat_crisis:
            triggered_crises.append(cat_crisis)
        
        # Check market value decline
        market_crisis = self._check_market_decline(company_state, market_conditions)
        if market_crisis:
            triggered_crises.append(market_crisis)
        
        # Check liquidity
        liquidity_crisis = self._check_liquidity_needs(company_state)
        if liquidity_crisis:
            triggered_crises.append(liquidity_crisis)
        
        # Check operational performance
        operational_crisis = self._check_operational_performance(company_state)
        if operational_crisis:
            triggered_crises.append(operational_crisis)
        
        # Sort by severity
        triggered_crises.sort(key=lambda x: x['severity'], reverse=True)
        
        return triggered_crises
    
    def _check_capital_requirements(
        self, 
        company_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Check if company breaches regulatory capital requirements.
        
        Args:
            company_state: Company financial state
            
        Returns:
            Crisis details if triggered, None otherwise
        """
        current_capital = company_state.get('current_capital', 0)
        required_capital = company_state.get('required_capital', 0)
        
        if required_capital <= 0:
            return None
        
        solvency_ratio = current_capital / required_capital
        min_ratio = self.capital_requirements['minimum_ratio']
        
        if solvency_ratio < min_ratio:
            # Calculate shortfall
            target_capital = required_capital * self.capital_requirements['target_ratio']
            shortfall = target_capital - current_capital
            
            # Determine urgency based on how far below minimum
            if solvency_ratio < 1.0:
                urgency = 'immediate'
                time_pressure = 'urgent'
            elif solvency_ratio < min_ratio * 0.8:
                urgency = 'critical'
                time_pressure = 'urgent'
            else:
                urgency = 'high'
                time_pressure = 'normal'
            
            return {
                'type': 'regulatory_capital_breach',
                'severity': 1.0 - (solvency_ratio / min_ratio),
                'urgency': urgency,
                'time_pressure': time_pressure,
                'liquidation_need': shortfall,
                'details': {
                    'current_ratio': solvency_ratio,
                    'minimum_ratio': min_ratio,
                    'current_capital': current_capital,
                    'required_capital': required_capital,
                    'regulatory_deadline': self.time_pressure_levels[time_pressure]
                }
            }
        
        return None
    
    def _check_catastrophic_losses(
        self,
        company_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Check for catastrophic loss events.
        
        Args:
            company_state: Company financial state
            
        Returns:
            Crisis details if triggered
        """
        recent_catastrophe = company_state.get('recent_catastrophe', {})
        if not recent_catastrophe:
            return None
        
        cat_losses = recent_catastrophe.get('total_losses', 0)
        current_capital = company_state.get('current_capital', 0)
        
        if current_capital <= 0:
            return None
        
        loss_percentage = cat_losses / current_capital
        
        if loss_percentage > self.crisis_thresholds['catastrophic_loss_pct']:
            # Need to restore capital position
            pre_loss_capital = current_capital + cat_losses
            target_capital = company_state.get('required_capital', 0) * \
                           self.capital_requirements['target_ratio']
            
            liquidation_need = max(0, target_capital - current_capital)
            
            return {
                'type': 'catastrophic_loss',
                'severity': min(1.0, loss_percentage),
                'urgency': 'critical',
                'time_pressure': 'urgent',
                'liquidation_need': liquidation_need,
                'details': {
                    'catastrophe_type': recent_catastrophe.get('type', 'unknown'),
                    'total_losses': cat_losses,
                    'loss_percentage': loss_percentage,
                    'affected_lines': recent_catastrophe.get('affected_lines', [])
                }
            }
        
        return None
    
    def _check_market_decline(
        self,
        company_state: Dict[str, Any],
        market_conditions: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Check for market value decline triggers.
        
        Args:
            company_state: Company financial state
            market_conditions: Market conditions
            
        Returns:
            Crisis details if triggered
        """
        portfolio_value = company_state.get('portfolio_value', 0)
        previous_value = company_state.get('previous_portfolio_value', portfolio_value)
        
        if previous_value <= 0:
            return None
        
        value_change = (portfolio_value - previous_value) / previous_value
        
        if value_change < -self.crisis_thresholds['market_decline_trigger']:
            # Market decline requires capital buffer restoration
            capital_impact = abs(value_change) * portfolio_value
            
            # Check if this pushes below capital requirements
            current_capital = company_state.get('current_capital', 0)
            post_decline_capital = current_capital - capital_impact
            required_capital = company_state.get('required_capital', 0)
            
            if post_decline_capital < required_capital * self.capital_requirements['minimum_ratio']:
                liquidation_need = (required_capital * self.capital_requirements['target_ratio'] - 
                                  post_decline_capital)
                
                return {
                    'type': 'market_decline',
                    'severity': abs(value_change),
                    'urgency': 'high',
                    'time_pressure': 'normal',
                    'liquidation_need': liquidation_need,
                    'details': {
                        'portfolio_decline': value_change,
                        'value_lost': portfolio_value - previous_value,
                        'market_condition': market_conditions.get('state', 'unknown'),
                        'capital_impact': capital_impact
                    }
                }
        
        return None
    
    def _check_liquidity_needs(
        self,
        company_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Check for liquidity shortfalls.
        
        Args:
            company_state: Company financial state
            
        Returns:
            Crisis details if triggered
        """
        # Get liquidity needs
        claim_payments_due = company_state.get('claim_payments_due', 0)
        operating_expenses = company_state.get('operating_expenses', 0)
        debt_service = company_state.get('debt_service', 0)
        
        total_liquidity_need = claim_payments_due + operating_expenses + debt_service
        
        # Get available liquidity
        cash_available = company_state.get('cash_available', 0)
        liquid_assets = company_state.get('liquid_assets_value', 0)
        
        total_liquidity = cash_available + liquid_assets
        
        if total_liquidity_need <= 0:
            return None
        
        liquidity_ratio = total_liquidity / total_liquidity_need
        
        if liquidity_ratio < self.crisis_thresholds['liquidity_coverage_min']:
            shortfall = total_liquidity_need * self.crisis_thresholds['liquidity_coverage_min'] - total_liquidity
            
            return {
                'type': 'liquidity_shortfall',
                'severity': 1.0 - liquidity_ratio,
                'urgency': 'immediate',
                'time_pressure': 'immediate',
                'liquidation_need': shortfall,
                'details': {
                    'liquidity_ratio': liquidity_ratio,
                    'total_needs': total_liquidity_need,
                    'available_liquidity': total_liquidity,
                    'claim_payments': claim_payments_due,
                    'time_to_default': max(0, int(total_liquidity / total_liquidity_need * 4))  # Weeks
                }
            }
        
        return None
    
    def _check_operational_performance(
        self,
        company_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Check for operational performance triggers.
        
        Args:
            company_state: Company financial state
            
        Returns:
            Crisis details if triggered
        """
        # Check combined ratio
        combined_ratio = company_state.get('combined_ratio', 0)
        
        # Check consecutive losses
        loss_history = company_state.get('profit_history', [])
        consecutive_losses = 0
        for profit in reversed(loss_history):
            if profit < 0:
                consecutive_losses += 1
            else:
                break
        
        # Trigger if combined ratio too high or too many losses
        if (combined_ratio > self.crisis_thresholds['combined_ratio_max'] or
            consecutive_losses >= self.crisis_thresholds['consecutive_losses']):
            
            # Operational issues may require capital injection
            burn_rate = abs(np.mean([p for p in loss_history[-3:] if p < 0])) if loss_history else 0
            months_to_insolvency = company_state.get('current_capital', 0) / burn_rate if burn_rate > 0 else float('inf')
            
            if months_to_insolvency < 12:  # Less than a year of runway
                # Need capital to survive 18 months
                liquidation_need = burn_rate * 18 - company_state.get('current_capital', 0)
                
                return {
                    'type': 'operational_distress',
                    'severity': min(1.0, combined_ratio - 1.0),
                    'urgency': 'medium',
                    'time_pressure': 'flexible',
                    'liquidation_need': max(0, liquidation_need),
                    'details': {
                        'combined_ratio': combined_ratio,
                        'consecutive_losses': consecutive_losses,
                        'monthly_burn': burn_rate,
                        'runway_months': months_to_insolvency
                    }
                }
        
        return None
    
    def calculate_aggregate_crisis_severity(
        self,
        triggered_crises: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate aggregate severity from multiple crises.
        
        Args:
            triggered_crises: List of crisis events
            
        Returns:
            Aggregate crisis metrics
        """
        if not triggered_crises:
            return {
                'aggregate_severity': 0,
                'total_liquidation_need': 0,
                'most_urgent_timeframe': 'flexible',
                'crisis_count': 0
            }
        
        # Aggregate metrics
        total_severity = sum(c['severity'] for c in triggered_crises)
        avg_severity = total_severity / len(triggered_crises)
        max_severity = max(c['severity'] for c in triggered_crises)
        
        # Total liquidation need (take maximum, not sum, to avoid double counting)
        total_liquidation = max(c['liquidation_need'] for c in triggered_crises)
        
        # Most urgent timeframe
        time_pressures = ['immediate', 'urgent', 'normal', 'flexible']
        most_urgent_idx = min(
            time_pressures.index(c['time_pressure']) 
            for c in triggered_crises
        )
        most_urgent = time_pressures[most_urgent_idx]
        
        # Compound severity (multiple crises are worse than one)
        compound_factor = 1 + 0.2 * (len(triggered_crises) - 1)
        aggregate_severity = min(1.0, avg_severity * compound_factor)
        
        return {
            'aggregate_severity': aggregate_severity,
            'max_severity': max_severity,
            'total_liquidation_need': total_liquidation,
            'most_urgent_timeframe': most_urgent,
            'crisis_count': len(triggered_crises),
            'crisis_types': [c['type'] for c in triggered_crises],
            'compound_factor': compound_factor
        }
    
    def recommend_crisis_response(
        self,
        triggered_crises: List[Dict[str, Any]],
        company_resources: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recommend response strategy for crisis.
        
        Args:
            triggered_crises: Active crises
            company_resources: Available resources
            
        Returns:
            Recommended response strategy
        """
        if not triggered_crises:
            return {'action': 'none', 'urgency': 'none'}
        
        aggregate = self.calculate_aggregate_crisis_severity(triggered_crises)
        
        # Determine primary response
        if aggregate['total_liquidation_need'] > 0:
            liquid_assets = company_resources.get('liquid_assets_value', 0)
            illiquid_assets = company_resources.get('illiquid_assets_value', 0)
            
            if liquid_assets >= aggregate['total_liquidation_need']:
                action = 'liquidate_liquid_only'
            elif liquid_assets + illiquid_assets >= aggregate['total_liquidation_need']:
                action = 'liquidate_mixed'
            else:
                action = 'liquidate_all_possible'
        else:
            action = 'monitor'
        
        return {
            'action': action,
            'urgency': aggregate['most_urgent_timeframe'],
            'liquidation_target': aggregate['total_liquidation_need'],
            'recommended_timeline': self.time_pressure_levels[aggregate['most_urgent_timeframe']],
            'risk_level': 'critical' if aggregate['aggregate_severity'] > 0.7 else 'high' if aggregate['aggregate_severity'] > 0.4 else 'moderate'
        }
