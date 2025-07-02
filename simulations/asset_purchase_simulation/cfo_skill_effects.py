"""CFO skill effects on investment decision-making.

This module implements how CFO skill level affects the perception
of investment characteristics and the quality of investment decisions.
The key principle is that CFO skill affects information quality,
not actual returns.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class CFOSkillEffects:
    """Models how CFO skill affects investment perception and decisions.
    
    Key mechanisms:
    - Lower skill = more noise in perceiving true characteristics
    - Skill affects information quality, not actual returns
    - Poor information leads to suboptimal decisions
    - Skill improvement reduces perception errors
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize CFO skill effects model.
        
        Args:
            config: Game configuration
        """
        self.config = config
        investment_params = config.get('investment_parameters', {})
        
        # Skill effect parameters
        self.skill_params = investment_params.get('cfo_skill_effects', {
            'base_noise_level': 0.3,      # Maximum noise at skill 0
            'noise_reduction_rate': 0.9,   # How much skill reduces noise
            'min_noise_level': 0.02,       # Minimum noise even at skill 100
            'perception_bias': 0.1,        # Systematic optimism/pessimism
            'learning_rate': 0.05          # How fast CFOs learn from experience
        })
        
        # Skill thresholds for qualitative effects
        self.skill_thresholds = {
            'novice': 30,      # Below this: major errors
            'competent': 50,   # Basic understanding
            'skilled': 70,     # Good decision making
            'expert': 85       # Excellent perception
        }
    
    def apply_skill_noise(
        self,
        true_characteristics: Dict[str, float],
        cfo_skill: int,
        market_conditions: Optional[str] = None
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """Apply CFO skill-based noise to portfolio characteristics.
        
        Args:
            true_characteristics: Actual portfolio characteristics
            cfo_skill: CFO skill level (0-100)
            market_conditions: Current market state (affects difficulty)
            
        Returns:
            Tuple of (perceived_characteristics, perception_details)
        """
        # Calculate noise level based on skill
        noise_level = self._calculate_noise_level(cfo_skill)
        
        # Adjust for market conditions
        if market_conditions == 'crisis':
            noise_level *= 1.5  # Harder to perceive in crisis
        elif market_conditions == 'boom':
            noise_level *= 0.8  # Easier in good times
        
        perceived_characteristics = {}
        noise_applied = {}
        
        for char, true_value in true_characteristics.items():
            # Generate noise
            if char == 'risk':
                # CFOs tend to underestimate risk (optimism bias)
                bias = -self.skill_params['perception_bias'] * (1 - cfo_skill/100)
                noise = np.random.normal(bias, noise_level)
            elif char == 'liquidity':
                # Liquidity often overestimated
                bias = self.skill_params['perception_bias'] * (1 - cfo_skill/100)
                noise = np.random.normal(bias, noise_level)
            else:
                # Other characteristics: unbiased noise
                noise = np.random.normal(0, noise_level)
            
            # Apply noise with bounds
            perceived_value = true_value + noise
            perceived_value = np.clip(perceived_value, 0, 1)
            
            perceived_characteristics[char] = perceived_value
            noise_applied[char] = perceived_value - true_value
        
        # Calculate information quality metrics
        total_error = sum(abs(n) for n in noise_applied.values())
        avg_error = total_error / len(noise_applied)
        max_error = max(abs(n) for n in noise_applied.values())
        
        # Determine qualitative skill assessment
        skill_category = self._get_skill_category(cfo_skill)
        
        perception_details = {
            'cfo_skill': cfo_skill,
            'skill_category': skill_category,
            'noise_level': noise_level,
            'noise_applied': noise_applied,
            'total_absolute_error': total_error,
            'average_absolute_error': avg_error,
            'max_absolute_error': max_error,
            'information_quality': 1 - avg_error  # 0-1 scale
        }
        
        logger.debug(
            f"CFO skill {cfo_skill} ({skill_category}): "
            f"avg error {avg_error:.3f}, info quality {perception_details['information_quality']:.3f}"
        )
        
        return perceived_characteristics, perception_details
    
    def _calculate_noise_level(self, cfo_skill: int) -> float:
        """Calculate noise level based on CFO skill.
        
        Args:
            cfo_skill: CFO skill level (0-100)
            
        Returns:
            Standard deviation of perception noise
        """
        # Exponential decay of noise with skill
        skill_factor = cfo_skill / 100
        noise_reduction = self.skill_params['noise_reduction_rate'] ** skill_factor
        
        noise_level = (
            self.skill_params['min_noise_level'] + 
            (self.skill_params['base_noise_level'] - self.skill_params['min_noise_level']) * 
            (1 - skill_factor) * noise_reduction
        )
        
        return noise_level
    
    def _get_skill_category(self, cfo_skill: int) -> str:
        """Determine qualitative skill category.
        
        Args:
            cfo_skill: CFO skill level
            
        Returns:
            Skill category name
        """
        if cfo_skill < self.skill_thresholds['novice']:
            return 'novice'
        elif cfo_skill < self.skill_thresholds['competent']:
            return 'competent'
        elif cfo_skill < self.skill_thresholds['skilled']:
            return 'skilled'
        elif cfo_skill < self.skill_thresholds['expert']:
            return 'expert'
        else:
            return 'master'
    
    def simulate_decision_quality(
        self,
        cfo_skill: int,
        decision_complexity: float = 0.5,
        time_pressure: bool = False
    ) -> Dict[str, float]:
        """Simulate quality of investment decisions based on skill.
        
        Args:
            cfo_skill: CFO skill level
            decision_complexity: Complexity of decision (0-1)
            time_pressure: Whether under time pressure
            
        Returns:
            Decision quality metrics
        """
        # Base decision quality from skill
        base_quality = cfo_skill / 100
        
        # Complexity penalty
        complexity_penalty = decision_complexity * (1 - base_quality) * 0.3
        
        # Time pressure penalty
        time_penalty = 0.15 if time_pressure else 0
        
        # Calculate final quality
        decision_quality = max(0, base_quality - complexity_penalty - time_penalty)
        
        # Probability of major errors
        error_prob = 0.3 * (1 - base_quality) * (1 + decision_complexity)
        if time_pressure:
            error_prob *= 1.5
        
        # Expected suboptimality
        expected_loss = (1 - decision_quality) * 0.05  # 5% return loss at worst
        
        return {
            'decision_quality': decision_quality,
            'error_probability': min(1.0, error_prob),
            'expected_return_loss': expected_loss,
            'complexity_handled': base_quality > decision_complexity,
            'confidence_level': min(0.95, base_quality + 0.2)  # Overconfidence
        }
    
    def apply_experience_learning(
        self,
        current_skill: int,
        outcomes: List[Dict[str, Any]],
        max_skill: int = 100
    ) -> Tuple[int, Dict[str, Any]]:
        """Calculate skill improvement from experience.
        
        Args:
            current_skill: Current CFO skill
            outcomes: Recent investment outcomes
            max_skill: Maximum achievable skill
            
        Returns:
            Tuple of (new_skill, learning_details)
        """
        if not outcomes:
            return current_skill, {'skill_change': 0, 'learning_events': 0}
        
        # Calculate learning from each outcome
        total_learning = 0
        learning_events = 0
        
        for outcome in outcomes:
            # Learn more from mistakes
            prediction_error = abs(outcome.get('prediction_error', 0))
            if prediction_error > 0.1:  # Significant error
                learning = prediction_error * self.skill_params['learning_rate']
                total_learning += learning
                learning_events += 1
            
            # Learn from extreme events
            if outcome.get('extreme_event', False):
                total_learning += self.skill_params['learning_rate'] * 2
                learning_events += 1
        
        # Apply diminishing returns at high skill
        skill_factor = 1 - (current_skill / max_skill)
        effective_learning = total_learning * skill_factor
        
        # Calculate new skill
        new_skill = min(max_skill, current_skill + effective_learning)
        skill_change = new_skill - current_skill
        
        learning_details = {
            'skill_change': skill_change,
            'learning_events': learning_events,
            'total_learning_potential': total_learning,
            'effective_learning': effective_learning,
            'diminishing_returns_factor': skill_factor
        }
        
        if skill_change > 0:
            logger.info(
                f"CFO skill improved from {current_skill} to {new_skill:.1f} "
                f"({learning_events} learning events)"
            )
        
        return int(new_skill), learning_details
    
    def calculate_perception_correlation(
        self,
        true_values: Dict[str, float],
        perceived_values: Dict[str, float]
    ) -> float:
        """Calculate correlation between true and perceived values.
        
        Useful for measuring information quality.
        
        Args:
            true_values: True characteristic values
            perceived_values: Perceived values
            
        Returns:
            Correlation coefficient
        """
        if len(true_values) < 2:
            return 1.0
        
        true_array = np.array([true_values[k] for k in sorted(true_values.keys())])
        perceived_array = np.array([perceived_values[k] for k in sorted(true_values.keys())])
        
        correlation = np.corrcoef(true_array, perceived_array)[0, 1]
        
        return float(correlation) if not np.isnan(correlation) else 0.0
    
    def generate_investment_report(
        self,
        portfolio_data: Dict[str, Any],
        cfo_skill: int
    ) -> Dict[str, Any]:
        """Generate investment report with skill-based insights.
        
        Higher skill CFOs provide better analysis and insights.
        
        Args:
            portfolio_data: True portfolio data
            cfo_skill: CFO skill level
            
        Returns:
            Investment report with skill-appropriate content
        """
        skill_category = self._get_skill_category(cfo_skill)
        
        report = {
            'skill_category': skill_category,
            'confidence_level': 'high' if cfo_skill > 70 else 'medium' if cfo_skill > 40 else 'low'
        }
        
        # Analysis depth based on skill
        if skill_category == 'novice':
            report['analysis'] = 'basic'
            report['insights'] = [
                'Portfolio appears diversified',
                'Returns seem reasonable'
            ]
            report['risks_identified'] = ['Market risk']
            
        elif skill_category in ['competent', 'skilled']:
            report['analysis'] = 'intermediate'
            report['insights'] = [
                f"Expected return: {portfolio_data.get('expected_return', 0):.1%}",
                f"Risk level: {portfolio_data.get('risk_level', 'moderate')}",
                'Correlation analysis performed'
            ]
            report['risks_identified'] = [
                'Market risk',
                'Credit risk',
                'Liquidity concerns in crisis'
            ]
            
        else:  # Expert or master
            report['analysis'] = 'comprehensive'
            report['insights'] = [
                f"Risk-adjusted return optimization achieved",
                f"Tail risk exposure: {portfolio_data.get('tail_risk', 'controlled')}",
                'Factor decomposition completed',
                'Stress test scenarios analyzed'
            ]
            report['risks_identified'] = [
                'Market risk (beta exposure)',
                'Credit risk (spread duration)',
                'Liquidity risk (redemption modeling)',
                'Operational risk',
                'Model risk in optimization'
            ]
            report['recommendations'] = self._generate_recommendations(portfolio_data, cfo_skill)
        
        return report
    
    def _generate_recommendations(
        self, 
        portfolio_data: Dict[str, Any],
        cfo_skill: int
    ) -> List[str]:
        """Generate investment recommendations based on skill.
        
        Args:
            portfolio_data: Portfolio information
            cfo_skill: CFO skill level
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if cfo_skill > 70:
            # Skilled CFOs can make nuanced recommendations
            if portfolio_data.get('risk_level', 0) > 0.7:
                recommendations.append('Consider reducing equity allocation by 10%')
            if portfolio_data.get('liquidity', 1) < 0.3:
                recommendations.append('Increase liquid assets for potential redemptions')
            if portfolio_data.get('duration', 0) > 0.7:
                recommendations.append('Monitor interest rate risk given high duration')
        
        return recommendations
