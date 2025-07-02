"""Market share allocation and competitive dynamics.

This module handles the allocation of market share among competitors
based on their pricing decisions, product characteristics, and market conditions.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from collections import defaultdict
import logging

from .elasticity_models import DemandSimulator

logger = logging.getLogger(__name__)


class MarketShareAllocator:
    """Allocates market share among competing insurance companies.
    
    This class manages the competitive dynamics of the insurance market,
    determining how customers are distributed among companies based on:
    - Pricing strategies
    - Product quality tiers
    - Geographic presence
    - Market conditions
    - Historical performance (loyalty effects)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize market share allocator.
        
        Args:
            config: Game configuration
        """
        self.config = config
        self.demand_simulator = DemandSimulator(config)
        
        # Market parameters
        economic_params = config.get('economic_parameters', {})
        self.market_growth_rate = economic_params.get('market_growth_rate', 0.03)
        self.new_entrant_penalty = economic_params.get('new_entrant_penalty', 0.8)
        
        # Loyalty effects (future enhancement)
        self.enable_loyalty = economic_params.get('enable_loyalty', False)
        self.loyalty_factor = economic_params.get('loyalty_factor', 0.1)
    
    def allocate_market_shares(
        self,
        state_id: str,
        line_of_business: str,
        companies: List[Dict[str, Any]],
        market_condition: Optional[Dict[str, Any]] = None,
        previous_shares: Optional[Dict[str, float]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Allocate market shares among competing companies.
        
        Args:
            state_id: State where competition occurs
            line_of_business: Insurance line being competed for
            companies: List of companies with pricing/product data
            market_condition: Current market conditions
            previous_shares: Previous turn's market shares (for loyalty)
            
        Returns:
            Dictionary mapping company_id to allocation results
        """
        if not companies:
            return {}
        
        # Extract market condition multiplier
        market_multiplier = 1.0
        if market_condition:
            market_multiplier = market_condition.get('demand_multiplier', 1.0)
        
        # Calculate base market shares using demand simulator
        shares = self.demand_simulator.calculate_market_equilibrium(
            companies=companies,
            line_of_business=line_of_business,
            market_condition=market_condition.get('type') if market_condition else None
        )
        
        # Apply market growth
        total_market_size = self._calculate_market_size(
            state_id, 
            line_of_business,
            market_multiplier
        )
        
        # Apply loyalty effects if enabled and previous shares exist
        if self.enable_loyalty and previous_shares:
            shares = self._apply_loyalty_effects(shares, previous_shares)
        
        # Apply new entrant penalties
        shares = self._apply_new_entrant_effects(shares, companies)
        
        # Convert shares to absolute values and prepare results
        results = {}
        for company in companies:
            company_id = company['id']
            market_share = shares.get(company_id, 0.0)
            
            # Calculate absolute premium volume
            premium_volume = market_share * total_market_size
            
            # Calculate number of policies (rough estimate)
            avg_premium = company.get('price', 1000)
            policy_count = int(premium_volume / avg_premium) if avg_premium > 0 else 0
            
            results[company_id] = {
                'market_share': market_share,
                'premium_volume': premium_volume,
                'policy_count': policy_count,
                'effective_price': company.get('price', 0),
                'product_tier': company.get('tier', 'standard'),
                'is_new_entrant': company.get('is_new_entrant', False)
            }
        
        # Log market dynamics
        logger.info(
            f"Market share allocation for {line_of_business} in {state_id}: "
            f"{len(companies)} companies, total market ${total_market_size:,.0f}"
        )
        
        return results
    
    def _calculate_market_size(
        self, 
        state_id: str, 
        line_of_business: str,
        market_multiplier: float
    ) -> float:
        """Calculate total market size for a state/line combination.
        
        Args:
            state_id: State identifier
            line_of_business: Insurance line
            market_multiplier: Market condition effect
            
        Returns:
            Total market size in dollars
        """
        # Base market sizes (would come from state data in real implementation)
        base_market_sizes = {
            'auto': 100_000_000,        # $100M base market
            'home': 80_000_000,         # $80M base market
            'general_liability': 60_000_000,
            'workers_comp': 120_000_000,
            'commercial_property': 90_000_000
        }
        
        base_size = base_market_sizes.get(line_of_business.lower(), 50_000_000)
        
        # Apply growth and market conditions
        growth_factor = 1 + self.market_growth_rate
        total_size = base_size * growth_factor * market_multiplier
        
        return total_size
    
    def _apply_loyalty_effects(
        self,
        current_shares: Dict[str, float],
        previous_shares: Dict[str, float]
    ) -> Dict[str, float]:
        """Apply customer loyalty effects to market shares.
        
        Companies with existing market share have some customer stickiness.
        
        Args:
            current_shares: Newly calculated shares
            previous_shares: Previous turn's shares
            
        Returns:
            Adjusted market shares
        """
        adjusted_shares = {}
        
        for company_id, current_share in current_shares.items():
            previous_share = previous_shares.get(company_id, 0.0)
            
            # Blend current and previous shares based on loyalty factor
            # loyalty_factor = 0.1 means 10% of previous share is "sticky"
            adjusted_share = (
                (1 - self.loyalty_factor) * current_share +
                self.loyalty_factor * previous_share
            )
            
            adjusted_shares[company_id] = adjusted_share
        
        # Renormalize to ensure shares sum to 1
        total = sum(adjusted_shares.values())
        if total > 0:
            adjusted_shares = {
                cid: share / total
                for cid, share in adjusted_shares.items()
            }
        
        return adjusted_shares
    
    def _apply_new_entrant_effects(
        self,
        shares: Dict[str, float],
        companies: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Apply penalties for new market entrants.
        
        New companies face customer acquisition challenges.
        
        Args:
            shares: Current market shares
            companies: Company data including entrant status
            
        Returns:
            Adjusted market shares
        """
        # Identify new entrants
        new_entrants = {
            c['id'] for c in companies
            if c.get('is_new_entrant', False)
        }
        
        if not new_entrants:
            return shares
        
        # Apply penalty to new entrants
        adjusted_shares = {}
        released_share = 0.0
        
        for company_id, share in shares.items():
            if company_id in new_entrants:
                # New entrants get reduced share
                adjusted_share = share * self.new_entrant_penalty
                released_share += share - adjusted_share
                adjusted_shares[company_id] = adjusted_share
            else:
                adjusted_shares[company_id] = share
        
        # Redistribute released share to established companies
        established_companies = [
            cid for cid in shares.keys()
            if cid not in new_entrants
        ]
        
        if established_companies and released_share > 0:
            # Redistribute proportionally to current shares
            total_established_share = sum(
                shares[cid] for cid in established_companies
            )
            
            if total_established_share > 0:
                for company_id in established_companies:
                    redistribution = (
                        shares[company_id] / total_established_share * released_share
                    )
                    adjusted_shares[company_id] += redistribution
        
        return adjusted_shares
    
    def calculate_competitive_response(
        self,
        company_id: str,
        current_price: float,
        competitor_actions: List[Dict[str, Any]],
        line_of_business: str
    ) -> Dict[str, Any]:
        """Calculate optimal pricing response to competitor actions.
        
        This method helps companies understand how to respond to
        competitor price changes (for AI companies or suggestions).
        
        Args:
            company_id: Company making the decision
            current_price: Company's current price
            competitor_actions: List of competitor price changes
            line_of_business: Insurance line
            
        Returns:
            Suggested response with reasoning
        """
        # Analyze competitor moves
        avg_competitor_change = np.mean([
            action.get('price_change', 0.0)
            for action in competitor_actions
        ])
        
        # Get elasticity for this line
        elasticity = abs(self.demand_simulator.price_elasticity.get(
            line_of_business.lower(), 1.0
        ))
        
        # Simple response strategy
        suggested_change = 0.0
        reasoning = []
        
        if avg_competitor_change < -0.05:  # Competitors dropping prices
            # Consider matching if elasticity is high
            if elasticity > 1.0:
                suggested_change = avg_competitor_change * 0.8  # Don't fully match
                reasoning.append("High elasticity market - partially matching competitor price cuts")
            else:
                suggested_change = avg_competitor_change * 0.3  # Minimal response
                reasoning.append("Low elasticity market - maintaining price discipline")
        
        elif avg_competitor_change > 0.05:  # Competitors raising prices
            # Opportunity to increase prices
            suggested_change = avg_competitor_change * 0.6  # Conservative increase
            reasoning.append("Following market price increases conservatively")
        
        else:
            reasoning.append("Market prices stable - no change recommended")
        
        return {
            'suggested_price': current_price * (1 + suggested_change),
            'price_change_pct': suggested_change,
            'reasoning': reasoning,
            'market_elasticity': elasticity,
            'avg_competitor_change': avg_competitor_change
        }
    
    def analyze_market_concentration(
        self,
        market_shares: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate market concentration metrics.
        
        Args:
            market_shares: Company market shares
            
        Returns:
            Concentration metrics (HHI, CR4, etc.)
        """
        shares = list(market_shares.values())
        shares.sort(reverse=True)
        
        # Herfindahl-Hirschman Index (HHI)
        hhi = sum(s**2 for s in shares) * 10000  # Convert to standard scale
        
        # Concentration ratios
        cr1 = shares[0] if len(shares) >= 1 else 0
        cr4 = sum(shares[:4]) if len(shares) >= 4 else sum(shares)
        
        # Market competitiveness assessment
        if hhi < 1500:
            competition_level = "competitive"
        elif hhi < 2500:
            competition_level = "moderately_concentrated"
        else:
            competition_level = "highly_concentrated"
        
        return {
            'hhi': hhi,
            'cr1': cr1,
            'cr4': cr4,
            'num_competitors': len(shares),
            'competition_level': competition_level,
            'effective_competitors': sum(1 for s in shares if s > 0.05)  # >5% share
        }
