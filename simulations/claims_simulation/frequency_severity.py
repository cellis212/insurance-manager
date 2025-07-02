"""Frequency and severity models for insurance claims generation.

This module implements statistical models for generating realistic
claim frequencies (how many claims) and severities (claim amounts).
"""

from __future__ import annotations

import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Optional, Any
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class FrequencySeverityModel:
    """Generates insurance claims using frequency/severity approach.
    
    This model simulates claims by:
    1. Determining claim count (frequency) using count distributions
    2. Generating claim amounts (severity) using continuous distributions
    3. Applying modifiers for product tiers, selection effects, etc.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize frequency/severity model.
        
        Args:
            config: Game configuration with claims parameters
        """
        self.config = config
        claims_params = config.get('claims_parameters', {})
        
        # Frequency parameters by line of business
        self.frequency_params = claims_params.get('frequency_distributions', {
            'auto': {'distribution': 'poisson', 'base_rate': 0.15},  # 15% annual
            'home': {'distribution': 'poisson', 'base_rate': 0.08},  # 8% annual
            'general_liability': {'distribution': 'negative_binomial', 'base_rate': 0.12, 'dispersion': 2},
            'workers_comp': {'distribution': 'poisson', 'base_rate': 0.05},
            'commercial_property': {'distribution': 'poisson', 'base_rate': 0.10}
        })
        
        # Severity parameters by line of business
        self.severity_params = claims_params.get('severity_distributions', {
            'auto': {'distribution': 'lognormal', 'mean_log': 8.5, 'std_log': 1.2},  # ~$4,900 median
            'home': {'distribution': 'lognormal', 'mean_log': 9.2, 'std_log': 1.5},  # ~$10,000 median
            'general_liability': {'distribution': 'pareto', 'scale': 5000, 'shape': 1.5},
            'workers_comp': {'distribution': 'lognormal', 'mean_log': 9.0, 'std_log': 1.8},
            'commercial_property': {'distribution': 'lognormal', 'mean_log': 9.5, 'std_log': 1.6}
        })
        
        # Product tier effects
        product_params = config.get('product_parameters', {})
        self.tier_effects = product_params.get('tiers', {})
        
        # Inflation rate for severity
        economic_params = config.get('economic_parameters', {})
        self.inflation_rate = economic_params.get('inflation_rate', 0.02)
    
    def generate_claims(
        self,
        exposure_units: float,
        line_of_business: str,
        product_tier: str = 'standard',
        selection_modifier: float = 1.0,
        time_period: float = 1.0,
        random_seed: Optional[int] = None
    ) -> Tuple[List[float], Dict[str, Any]]:
        """Generate claims for a given exposure.
        
        Args:
            exposure_units: Number of exposure units (policies, vehicles, etc.)
            line_of_business: Insurance line
            product_tier: Product quality tier affecting selection
            selection_modifier: Additional selection effect modifier
            time_period: Time period in years (default 1.0)
            random_seed: Random seed for reproducibility
            
        Returns:
            Tuple of (list of claim amounts, statistics dict)
        """
        if random_seed is not None:
            np.random.seed(random_seed)
        
        # Get line-specific parameters
        freq_params = self.frequency_params.get(
            line_of_business.lower(),
            self.frequency_params['auto']  # Default
        )
        sev_params = self.severity_params.get(
            line_of_business.lower(),
            self.severity_params['auto']  # Default
        )
        
        # Calculate adjusted frequency
        base_frequency = freq_params['base_rate'] * time_period
        
        # Apply tier selection effect
        tier_info = self.tier_effects.get(product_tier, {})
        risk_selection = tier_info.get('risk_selection', 1.0)
        adjusted_frequency = base_frequency * risk_selection * selection_modifier
        
        # Generate claim count
        claim_count = self._generate_frequency(
            exposure_units=exposure_units,
            adjusted_rate=adjusted_frequency,
            distribution_params=freq_params
        )
        
        # Generate claim severities
        claims = []
        if claim_count > 0:
            claims = self._generate_severities(
                count=claim_count,
                distribution_params=sev_params,
                tier_modifier=risk_selection
            )
        
        # Calculate statistics
        statistics = {
            'claim_count': claim_count,
            'frequency_rate': claim_count / exposure_units if exposure_units > 0 else 0,
            'total_claims': sum(claims),
            'average_severity': np.mean(claims) if claims else 0,
            'max_claim': max(claims) if claims else 0,
            'exposure_units': exposure_units,
            'adjusted_frequency': adjusted_frequency
        }
        
        logger.debug(
            f"Generated {claim_count} claims for {exposure_units} units "
            f"in {line_of_business} ({product_tier} tier)"
        )
        
        return claims, statistics
    
    def _generate_frequency(
        self,
        exposure_units: float,
        adjusted_rate: float,
        distribution_params: Dict[str, Any]
    ) -> int:
        """Generate claim count using appropriate distribution.
        
        Args:
            exposure_units: Number of exposure units
            adjusted_rate: Adjusted claim rate per unit
            distribution_params: Distribution specification
            
        Returns:
            Number of claims
        """
        dist_type = distribution_params.get('distribution', 'poisson')
        expected_claims = exposure_units * adjusted_rate
        
        if dist_type == 'poisson':
            # Poisson distribution for claim counts
            claim_count = np.random.poisson(expected_claims)
            
        elif dist_type == 'negative_binomial':
            # Negative binomial for overdispersed counts
            dispersion = distribution_params.get('dispersion', 2)
            # Convert to scipy parameterization
            n = expected_claims / (dispersion - 1) if dispersion > 1 else expected_claims
            p = 1 / dispersion if dispersion > 0 else 0.5
            claim_count = np.random.negative_binomial(n, p)
            
        else:
            # Default to Poisson
            claim_count = np.random.poisson(expected_claims)
        
        return max(0, int(claim_count))
    
    def _generate_severities(
        self,
        count: int,
        distribution_params: Dict[str, Any],
        tier_modifier: float = 1.0
    ) -> List[float]:
        """Generate claim amounts using appropriate distribution.
        
        Args:
            count: Number of claims to generate
            distribution_params: Severity distribution specification
            tier_modifier: Product tier effect on severity
            
        Returns:
            List of claim amounts
        """
        dist_type = distribution_params.get('distribution', 'lognormal')
        severities = []
        
        if dist_type == 'lognormal':
            # Lognormal distribution (common for insurance)
            mean_log = distribution_params.get('mean_log', 8.0)
            std_log = distribution_params.get('std_log', 1.0)
            
            # Adjust mean for tier effect and inflation
            adjusted_mean = mean_log + np.log(tier_modifier) + np.log(1 + self.inflation_rate)
            
            severities = np.random.lognormal(adjusted_mean, std_log, count).tolist()
            
        elif dist_type == 'pareto':
            # Pareto distribution for heavy-tailed risks
            scale = distribution_params.get('scale', 1000)
            shape = distribution_params.get('shape', 1.5)
            
            # Adjust scale for tier effect
            adjusted_scale = scale * tier_modifier * (1 + self.inflation_rate)
            
            # Generate using (scale * (U^(-1/shape) - 1))
            uniform_samples = np.random.uniform(0, 1, count)
            severities = (adjusted_scale * (uniform_samples**(-1/shape) - 1)).tolist()
            
        elif dist_type == 'gamma':
            # Gamma distribution
            shape = distribution_params.get('shape', 2.0)
            scale = distribution_params.get('scale', 5000)
            
            # Adjust scale for modifiers
            adjusted_scale = scale * tier_modifier * (1 + self.inflation_rate)
            
            severities = np.random.gamma(shape, adjusted_scale, count).tolist()
            
        else:
            # Default to lognormal
            severities = np.random.lognormal(8.0, 1.0, count).tolist()
        
        # Ensure all severities are positive and apply minimum
        min_claim = 100  # Minimum claim amount
        severities = [max(min_claim, sev) for sev in severities]
        
        return severities
    
    def calculate_pure_premium(
        self,
        line_of_business: str,
        product_tier: str = 'standard',
        selection_modifier: float = 1.0,
        simulations: int = 1000
    ) -> Dict[str, float]:
        """Calculate pure premium using Monte Carlo simulation.
        
        Pure premium = Expected frequency × Expected severity
        
        Args:
            line_of_business: Insurance line
            product_tier: Product quality tier
            selection_modifier: Additional risk selection
            simulations: Number of Monte Carlo simulations
            
        Returns:
            Pure premium statistics
        """
        total_claims = []
        frequencies = []
        severities = []
        
        for _ in range(simulations):
            # Generate claims for one exposure unit
            claims, stats = self.generate_claims(
                exposure_units=1.0,
                line_of_business=line_of_business,
                product_tier=product_tier,
                selection_modifier=selection_modifier
            )
            
            total_claims.append(stats['total_claims'])
            frequencies.append(stats['claim_count'])
            if claims:
                severities.extend(claims)
        
        # Calculate statistics
        pure_premium = np.mean(total_claims)
        pure_premium_std = np.std(total_claims)
        
        return {
            'pure_premium': pure_premium,
            'pure_premium_std': pure_premium_std,
            'pure_premium_cv': pure_premium_std / pure_premium if pure_premium > 0 else 0,
            'expected_frequency': np.mean(frequencies),
            'expected_severity': np.mean(severities) if severities else 0,
            'percentile_90': np.percentile(total_claims, 90),
            'percentile_95': np.percentile(total_claims, 95),
            'percentile_99': np.percentile(total_claims, 99)
        }
    
    def calculate_loss_ratio(
        self,
        claims: List[float],
        earned_premium: float,
        expenses: Optional[float] = None
    ) -> Dict[str, float]:
        """Calculate loss ratio and related metrics.
        
        Args:
            claims: List of claim amounts
            earned_premium: Premium earned in period
            expenses: Optional expense amount
            
        Returns:
            Loss ratio metrics
        """
        total_claims = sum(claims)
        claim_count = len(claims)
        
        # Basic loss ratio
        loss_ratio = total_claims / earned_premium if earned_premium > 0 else 0
        
        # Combined ratio if expenses provided
        if expenses is not None:
            expense_ratio = expenses / earned_premium if earned_premium > 0 else 0
            combined_ratio = loss_ratio + expense_ratio
        else:
            expense_ratio = 0
            combined_ratio = loss_ratio
        
        return {
            'loss_ratio': loss_ratio,
            'expense_ratio': expense_ratio,
            'combined_ratio': combined_ratio,
            'total_claims': total_claims,
            'claim_count': claim_count,
            'average_claim': total_claims / claim_count if claim_count > 0 else 0,
            'earned_premium': earned_premium
        }
