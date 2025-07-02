"""Catastrophe event simulation for insurance claims.

This module generates major catastrophic events (hurricanes, earthquakes, etc.)
that affect multiple companies and create correlated losses across regions.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Set
from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class CatastropheSimulator:
    """Simulates catastrophic events affecting insurance markets.
    
    Catastrophes create:
    - Correlated losses across geographic regions
    - Sudden spikes in claim frequency and severity
    - Market-wide impacts on capital and pricing
    - Potential solvency crises requiring liquidations
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize catastrophe simulator.
        
        Args:
            config: Game configuration with catastrophe parameters
        """
        self.config = config
        claims_params = config.get('claims_parameters', {})
        self.cat_params = claims_params.get('catastrophe_probabilities', {})
        
        # Define catastrophe types and their characteristics
        self.catastrophe_types = {
            'hurricane': {
                'annual_probability': 0.15,
                'affected_states': ['FL', 'TX', 'LA', 'NC', 'SC', 'GA', 'AL', 'MS'],
                'severity_range': (0.5, 5.0),  # Multiplier on normal claims
                'lines_affected': ['home', 'auto', 'commercial_property'],
                'correlation_radius': 3,  # Affects neighboring states
                'duration_weeks': 2
            },
            'earthquake': {
                'annual_probability': 0.05,
                'affected_states': ['CA', 'AK', 'WA', 'OR', 'NV', 'UT'],
                'severity_range': (1.0, 10.0),
                'lines_affected': ['home', 'commercial_property'],
                'correlation_radius': 2,
                'duration_weeks': 1
            },
            'flood': {
                'annual_probability': 0.10,
                'affected_states': 'all',  # Can happen anywhere
                'severity_range': (0.3, 3.0),
                'lines_affected': ['home', 'auto', 'commercial_property'],
                'correlation_radius': 1,
                'duration_weeks': 2
            },
            'wildfire': {
                'annual_probability': 0.08,
                'affected_states': ['CA', 'OR', 'WA', 'CO', 'AZ', 'NM', 'MT', 'ID'],
                'severity_range': (0.5, 4.0),
                'lines_affected': ['home', 'commercial_property'],
                'correlation_radius': 2,
                'duration_weeks': 3
            },
            'winter_storm': {
                'annual_probability': 0.12,
                'affected_states': ['NY', 'MA', 'CT', 'NH', 'VT', 'ME', 'PA', 'NJ'],
                'severity_range': (0.2, 2.0),
                'lines_affected': ['auto', 'home', 'commercial_property'],
                'correlation_radius': 3,
                'duration_weeks': 1
            }
        }
        
        # Override with config if provided
        if self.cat_params:
            for cat_type, params in self.cat_params.items():
                if cat_type in self.catastrophe_types:
                    self.catastrophe_types[cat_type].update(params)
    
    def generate_catastrophe(
        self,
        turn_number: int,
        force_type: Optional[str] = None,
        force_states: Optional[List[str]] = None,
        random_seed: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate a catastrophe event for the current turn.
        
        Args:
            turn_number: Current game turn
            force_type: Force a specific catastrophe type (for scenarios)
            force_states: Force specific affected states
            random_seed: Random seed for reproducibility
            
        Returns:
            Catastrophe event details or None if no event
        """
        if random_seed is not None:
            np.random.seed(random_seed)
        
        # Check if catastrophe occurs this turn
        if force_type:
            cat_type = force_type
        else:
            # Random selection based on probabilities
            cat_occurs = False
            cat_type = None
            
            for event_type, params in self.catastrophe_types.items():
                # Convert annual probability to weekly
                weekly_prob = 1 - (1 - params['annual_probability']) ** (1/52)
                if np.random.random() < weekly_prob:
                    cat_occurs = True
                    cat_type = event_type
                    break
            
            if not cat_occurs:
                return None
        
        # Generate catastrophe details
        cat_params = self.catastrophe_types[cat_type]
        
        # Determine affected states
        if force_states:
            epicenter_states = force_states
        else:
            epicenter_states = self._select_affected_states(cat_type, cat_params)
        
        # Generate severity
        severity_range = cat_params['severity_range']
        base_severity = np.random.uniform(severity_range[0], severity_range[1])
        
        # Create catastrophe event
        catastrophe = {
            'type': cat_type,
            'turn_number': turn_number,
            'epicenter_states': epicenter_states,
            'all_affected_states': self._expand_affected_region(
                epicenter_states, 
                cat_params['correlation_radius']
            ),
            'base_severity': base_severity,
            'lines_affected': cat_params['lines_affected'],
            'duration_weeks': cat_params['duration_weeks'],
            'state_severities': self._calculate_state_severities(
                epicenter_states,
                base_severity,
                cat_params['correlation_radius']
            )
        }
        
        logger.info(
            f"Generated {cat_type} catastrophe affecting {len(catastrophe['all_affected_states'])} states "
            f"with base severity {base_severity:.2f}"
        )
        
        return catastrophe
    
    def calculate_catastrophe_claims(
        self,
        catastrophe: Dict[str, Any],
        exposure_by_state: Dict[str, float],
        line_of_business: str,
        base_frequency: float,
        base_severity: float
    ) -> Tuple[List[float], Dict[str, Any]]:
        """Calculate catastrophe-induced claims for a company.
        
        Args:
            catastrophe: Catastrophe event details
            exposure_by_state: Company's exposure units by state
            line_of_business: Insurance line
            base_frequency: Normal claim frequency
            base_severity: Normal claim severity
            
        Returns:
            Tuple of (catastrophe claims list, statistics)
        """
        # Check if this line is affected by the catastrophe
        if line_of_business not in catastrophe['lines_affected']:
            return [], {'catastrophe_claims': 0, 'cat_claim_count': 0}
        
        cat_claims = []
        state_details = {}
        
        for state, exposure in exposure_by_state.items():
            if state not in catastrophe['all_affected_states']:
                continue
            
            # Get state-specific severity multiplier
            state_severity = catastrophe['state_severities'].get(state, 0.1)
            
            # Calculate catastrophe claim frequency
            # Catastrophes dramatically increase frequency
            cat_frequency = base_frequency * state_severity * 5  # 5x multiplier
            expected_claims = exposure * cat_frequency
            
            # Generate claim count (Poisson)
            claim_count = np.random.poisson(expected_claims)
            
            # Generate catastrophe severities
            # Higher severity and more variable
            cat_severity_multiplier = state_severity * 2  # Double severity impact
            
            state_claims = []
            for _ in range(claim_count):
                # Lognormal with increased parameters
                severity = np.random.lognormal(
                    np.log(base_severity * cat_severity_multiplier),
                    0.8  # Higher variance for catastrophes
                )
                state_claims.append(severity)
                cat_claims.append(severity)
            
            state_details[state] = {
                'exposure': exposure,
                'severity_multiplier': state_severity,
                'claim_count': claim_count,
                'total_claims': sum(state_claims)
            }
        
        # Calculate statistics
        statistics = {
            'catastrophe_claims': sum(cat_claims),
            'cat_claim_count': len(cat_claims),
            'avg_cat_severity': np.mean(cat_claims) if cat_claims else 0,
            'max_cat_claim': max(cat_claims) if cat_claims else 0,
            'affected_states': len(state_details),
            'state_details': state_details
        }
        
        return cat_claims, statistics
    
    def _select_affected_states(
        self, 
        cat_type: str, 
        cat_params: Dict[str, Any]
    ) -> List[str]:
        """Select which states are affected by the catastrophe.
        
        Args:
            cat_type: Type of catastrophe
            cat_params: Catastrophe parameters
            
        Returns:
            List of epicenter state codes
        """
        potential_states = cat_params['affected_states']
        
        if potential_states == 'all':
            # For floods, randomly select from all states
            # In real implementation, would use state list from database
            all_states = ['FL', 'TX', 'CA', 'NY', 'PA', 'IL', 'OH', 'GA', 'NC', 'MI']
            num_states = np.random.randint(1, 4)  # 1-3 epicenter states
            return list(np.random.choice(all_states, num_states, replace=False))
        else:
            # Select from predefined vulnerable states
            num_states = np.random.randint(1, min(3, len(potential_states)))
            return list(np.random.choice(potential_states, num_states, replace=False))
    
    def _expand_affected_region(
        self,
        epicenter_states: List[str],
        correlation_radius: int
    ) -> Set[str]:
        """Expand affected region based on correlation radius.
        
        Args:
            epicenter_states: Epicenter state codes
            correlation_radius: How many neighboring states affected
            
        Returns:
            Set of all affected states
        """
        # Simplified geographic adjacency
        # In real implementation, would use actual state adjacency data
        adjacency = {
            'FL': ['GA', 'AL'],
            'TX': ['OK', 'AR', 'LA', 'NM'],
            'CA': ['OR', 'NV', 'AZ'],
            'NY': ['PA', 'NJ', 'CT', 'MA', 'VT'],
            'GA': ['FL', 'AL', 'SC', 'NC', 'TN'],
            # ... more adjacencies
        }
        
        affected = set(epicenter_states)
        
        # Expand based on radius
        for _ in range(correlation_radius):
            new_states = set()
            for state in affected:
                neighbors = adjacency.get(state, [])
                new_states.update(neighbors)
            affected.update(new_states)
        
        return affected
    
    def _calculate_state_severities(
        self,
        epicenter_states: List[str],
        base_severity: float,
        correlation_radius: int
    ) -> Dict[str, float]:
        """Calculate severity multipliers for each affected state.
        
        Args:
            epicenter_states: Epicenter states (full severity)
            base_severity: Base severity multiplier
            correlation_radius: Correlation distance
            
        Returns:
            Dict of state -> severity multiplier
        """
        severities = {}
        
        # Epicenter states get full severity
        for state in epicenter_states:
            severities[state] = base_severity
        
        # Get all affected states
        all_affected = self._expand_affected_region(epicenter_states, correlation_radius)
        
        # Calculate diminishing severity for distant states
        # Simplified - in reality would use actual distances
        for state in all_affected:
            if state not in severities:
                # Random decay factor
                distance_factor = np.random.uniform(0.3, 0.7)
                severities[state] = base_severity * distance_factor
        
        return severities
    
    def estimate_market_impact(
        self,
        catastrophe: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """Estimate market-wide impact of catastrophe.
        
        Args:
            catastrophe: Catastrophe event
            market_data: Current market conditions
            
        Returns:
            Market impact metrics
        """
        # Calculate estimated industry losses
        base_severity = catastrophe['base_severity']
        num_affected_states = len(catastrophe['all_affected_states'])
        
        # Rough estimation of industry losses
        industry_loss_billions = base_severity * num_affected_states * np.random.uniform(5, 20)
        
        # Capital market impact
        capital_impact = min(0.3, industry_loss_billions / 1000)  # Max 30% impact
        
        # Reinsurance cost increase
        reinsurance_increase = 1 + (base_severity * 0.2)  # 20% per severity point
        
        return {
            'estimated_industry_loss': industry_loss_billions * 1_000_000_000,
            'capital_market_impact': capital_impact,
            'reinsurance_cost_multiplier': reinsurance_increase,
            'expected_market_hardening': base_severity * 0.1,  # 10% price increase per severity
            'expected_capacity_reduction': capital_impact * 0.5
        }
