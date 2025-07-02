"""Investment skill effects service.

Applies CFO skill-based perception noise to investment characteristics.
Integrates with existing CFOSkillEffects simulation module.
"""

from __future__ import annotations

from typing import Dict, Tuple, Any, Optional
from decimal import Decimal
import logging

from simulations.asset_purchase_simulation.cfo_skill_effects import CFOSkillEffects

logger = logging.getLogger(__name__)


class InvestmentSkillEffects:
    """Manages CFO skill effects on investment perception.
    
    Wraps the simulation module to provide a clean interface for
    the investment plugin.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize skill effects service.
        
        Args:
            config: Game configuration
        """
        self.config = config
        self.skill_effects = CFOSkillEffects(config)
    
    def apply_perception_noise(
        self,
        actual_characteristics: Dict[str, float],
        cfo_skill: int,
        market_conditions: Optional[str] = None
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """Apply CFO skill-based perception noise.
        
        Args:
            actual_characteristics: True portfolio characteristics (0-100 scale)
            cfo_skill: CFO skill level (0-100)
            market_conditions: Current market state
            
        Returns:
            Tuple of (perceived_characteristics, perception_details)
        """
        # Convert to 0-1 scale for simulation module
        actual_normalized = {
            char: value / 100 
            for char, value in actual_characteristics.items()
        }
        
        # Apply skill effects
        perceived_normalized, perception_details = self.skill_effects.apply_skill_noise(
            true_characteristics=actual_normalized,
            cfo_skill=cfo_skill,
            market_conditions=market_conditions
        )
        
        # Convert back to 0-100 scale
        perceived_characteristics = {
            char: value * 100 
            for char, value in perceived_normalized.items()
        }
        
        # Add summary metrics
        perception_details['perception_accuracy'] = self._calculate_accuracy(
            actual_characteristics, 
            perceived_characteristics
        )
        
        logger.debug(
            f"Applied CFO skill {cfo_skill} perception: "
            f"accuracy {perception_details['perception_accuracy']:.1%}"
        )
        
        return perceived_characteristics, perception_details
    
    def generate_investment_insights(
        self,
        portfolio_data: Dict[str, Any],
        cfo_skill: int,
        recent_performance: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate CFO insights based on skill level.
        
        Args:
            portfolio_data: Current portfolio information
            cfo_skill: CFO skill level
            recent_performance: Recent return data
            
        Returns:
            Investment insights appropriate to skill level
        """
        # Prepare data for report generation
        report_data = {
            'expected_return': portfolio_data.get('expected_return', 0),
            'risk_level': portfolio_data.get('portfolio_risk', 0.05) * 20,  # Convert to score
            'tail_risk': 'high' if portfolio_data.get('portfolio_risk', 0) > 0.15 else 'controlled'
        }
        
        # Generate base report
        report = self.skill_effects.generate_investment_report(report_data, cfo_skill)
        
        # Add performance-based insights if available
        if recent_performance:
            report['performance_assessment'] = self._assess_recent_performance(
                recent_performance, 
                cfo_skill
            )
        
        return report
    
    def calculate_decision_quality(
        self,
        cfo_skill: int,
        market_volatility: float = 0.15,
        time_pressure: bool = False
    ) -> Dict[str, float]:
        """Calculate expected decision quality metrics.
        
        Args:
            cfo_skill: CFO skill level
            market_volatility: Current market volatility
            time_pressure: Whether under liquidation pressure
            
        Returns:
            Decision quality metrics
        """
        # Convert volatility to complexity (0-1 scale)
        complexity = min(1.0, market_volatility * 3)
        
        return self.skill_effects.simulate_decision_quality(
            cfo_skill=cfo_skill,
            decision_complexity=complexity,
            time_pressure=time_pressure
        )
    
    def _calculate_accuracy(
        self, 
        actual: Dict[str, float], 
        perceived: Dict[str, float]
    ) -> float:
        """Calculate perception accuracy.
        
        Args:
            actual: Actual values
            perceived: Perceived values
            
        Returns:
            Accuracy score (0-1)
        """
        if not actual or not perceived:
            return 0.0
        
        total_error = 0
        count = 0
        
        for key in actual:
            if key in perceived:
                # Calculate percentage error
                if actual[key] > 0:
                    error = abs(actual[key] - perceived[key]) / actual[key]
                else:
                    error = 0 if perceived[key] == 0 else 1
                
                total_error += error
                count += 1
        
        if count == 0:
            return 0.0
        
        avg_error = total_error / count
        accuracy = 1 - min(1.0, avg_error)
        
        return accuracy
    
    def _assess_recent_performance(
        self,
        performance: Dict[str, Any],
        cfo_skill: int
    ) -> str:
        """Assess recent performance based on skill.
        
        Args:
            performance: Recent performance data
            cfo_skill: CFO skill level
            
        Returns:
            Performance assessment
        """
        actual_return = performance.get('actual_return_rate', 0)
        expected_return = performance.get('expected_return_rate', 0)
        
        # Calculate performance relative to expectations
        if expected_return > 0:
            performance_ratio = actual_return / expected_return
        else:
            performance_ratio = 1.0
        
        # Skill affects interpretation accuracy
        if cfo_skill < 30:
            # Novice: poor interpretation
            if performance_ratio > 1.5:
                return "excellent"
            else:
                return "satisfactory"
        elif cfo_skill < 70:
            # Competent: reasonable interpretation
            if performance_ratio > 1.2:
                return "excellent"
            elif performance_ratio > 0.8:
                return "good"
            else:
                return "poor"
        else:
            # Expert: nuanced interpretation
            if performance_ratio > 1.15:
                return "excellent"
            elif performance_ratio > 1.05:
                return "very good"
            elif performance_ratio > 0.95:
                return "good"
            elif performance_ratio > 0.85:
                return "below expectations"
            else:
                return "significantly underperforming" 