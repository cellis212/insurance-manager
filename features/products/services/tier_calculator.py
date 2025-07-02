"""Tier calculator service for product tier effects.

Calculates tier-based modifiers for pricing, risk selection, and demand.
"""

import logging
from decimal import Decimal
from typing import Dict, Tuple

from core.models import Product, GameConfiguration
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class TierCalculator:
    """Calculates tier-based effects on product performance."""
    
    # Default tier modifiers
    DEFAULT_TIER_MODIFIERS = {
        "Basic": {
            "price_modifier": Decimal("0.8"),      # 20% cheaper
            "risk_selection": Decimal("1.3"),       # 30% worse risks
            "demand_elasticity": Decimal("1.5"),    # High price sensitivity
            "retention_rate": Decimal("0.85"),      # 85% retention
            "expense_ratio": Decimal("0.35")        # Higher expense ratio
        },
        "Standard": {
            "price_modifier": Decimal("1.0"),       # Baseline
            "risk_selection": Decimal("1.0"),       # Normal risks
            "demand_elasticity": Decimal("1.0"),    # Normal elasticity
            "retention_rate": Decimal("0.90"),      # 90% retention
            "expense_ratio": Decimal("0.30")        # Standard expense ratio
        },
        "Premium": {
            "price_modifier": Decimal("1.3"),       # 30% more expensive
            "risk_selection": Decimal("0.9"),       # 10% better risks
            "demand_elasticity": Decimal("0.6"),    # Low price sensitivity
            "retention_rate": Decimal("0.95"),      # 95% retention
            "expense_ratio": Decimal("0.25")        # Lower expense ratio
        }
    }
    
    def __init__(self, db_session: AsyncSession):
        """Initialize tier calculator.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
        self._config: Dict = None
    
    async def _get_config(self) -> Dict:
        """Get tier configuration from game config.
        
        Returns:
            Tier configuration parameters
        """
        if self._config is None:
            result = await self.db.execute(
                select(GameConfiguration).where(GameConfiguration.is_active == True)
            )
            config = result.scalar_one_or_none()
            if not config:
                raise ValueError("No active game configuration found")
            
            product_params = config.get_parameter("product_parameters", {})
            self._config = {
                "price_modifiers": product_params.get("tier_price_modifiers", {}),
                "risk_modifiers": product_params.get("tier_risk_modifiers", {})
            }
        return self._config
    
    async def get_tier_modifiers(self, tier: str) -> Dict[str, Decimal]:
        """Get all modifiers for a product tier.
        
        Args:
            tier: Product tier (Basic/Standard/Premium)
            
        Returns:
            Dict of modifier name to value
        """
        if tier not in self.DEFAULT_TIER_MODIFIERS:
            raise ValueError(f"Invalid tier: {tier}")
        
        # Start with defaults
        modifiers = self.DEFAULT_TIER_MODIFIERS[tier].copy()
        
        # Override with config if available
        config = await self._get_config()
        
        # Map tier names to lowercase for config lookup
        tier_key = tier.lower()
        
        if tier_key in config.get("price_modifiers", {}):
            # Config stores as percentage change, convert to multiplier
            price_change = Decimal(str(config["price_modifiers"][tier_key]))
            modifiers["price_modifier"] = Decimal("1") + price_change
        
        if tier_key in config.get("risk_modifiers", {}):
            # Config stores as percentage worse/better, convert to multiplier
            risk_change = Decimal(str(config["risk_modifiers"][tier_key]))
            modifiers["risk_selection"] = Decimal("1") + risk_change
        
        return modifiers
    
    def calculate_premium(
        self,
        base_premium: Decimal,
        tier: str
    ) -> Decimal:
        """Calculate tier-adjusted premium.
        
        Args:
            base_premium: Base premium amount
            tier: Product tier
            
        Returns:
            Adjusted premium
        """
        if tier not in self.DEFAULT_TIER_MODIFIERS:
            raise ValueError(f"Invalid tier: {tier}")
        
        modifier = self.DEFAULT_TIER_MODIFIERS[tier]["price_modifier"]
        return base_premium * modifier
    
    def calculate_expected_loss_ratio(
        self,
        base_loss_ratio: Decimal,
        tier: str
    ) -> Decimal:
        """Calculate expected loss ratio for a tier.
        
        Args:
            base_loss_ratio: Base loss ratio (Standard tier)
            tier: Product tier
            
        Returns:
            Expected loss ratio adjusted for tier
        """
        if tier not in self.DEFAULT_TIER_MODIFIERS:
            raise ValueError(f"Invalid tier: {tier}")
        
        risk_selection = self.DEFAULT_TIER_MODIFIERS[tier]["risk_selection"]
        return base_loss_ratio * risk_selection
    
    def calculate_demand_impact(
        self,
        base_demand: Decimal,
        tier: str,
        price_change_percent: Decimal
    ) -> Decimal:
        """Calculate demand impact from price changes.
        
        Uses tier-specific price elasticity.
        
        Args:
            base_demand: Base demand quantity
            tier: Product tier
            price_change_percent: Percentage price change (0.1 = 10% increase)
            
        Returns:
            Adjusted demand quantity
        """
        if tier not in self.DEFAULT_TIER_MODIFIERS:
            raise ValueError(f"Invalid tier: {tier}")
        
        elasticity = self.DEFAULT_TIER_MODIFIERS[tier]["demand_elasticity"]
        
        # Price elasticity formula: % change in quantity = elasticity * % change in price
        # Negative relationship: higher price = lower demand
        demand_change = -elasticity * price_change_percent
        
        # Apply change to base demand
        return base_demand * (Decimal("1") + demand_change)
    
    def calculate_retention_impact(
        self,
        current_policies: int,
        tier: str
    ) -> int:
        """Calculate expected policy retention.
        
        Args:
            current_policies: Current number of policies
            tier: Product tier
            
        Returns:
            Expected retained policies
        """
        if tier not in self.DEFAULT_TIER_MODIFIERS:
            raise ValueError(f"Invalid tier: {tier}")
        
        retention_rate = self.DEFAULT_TIER_MODIFIERS[tier]["retention_rate"]
        retained = int(current_policies * retention_rate)
        
        return retained
    
    def calculate_expense_ratio(
        self,
        tier: str,
        premiums: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """Calculate operating expenses based on tier.
        
        Different tiers have different expense structures.
        
        Args:
            tier: Product tier
            premiums: Premium volume
            
        Returns:
            Tuple of (expense_ratio, expense_amount)
        """
        if tier not in self.DEFAULT_TIER_MODIFIERS:
            raise ValueError(f"Invalid tier: {tier}")
        
        expense_ratio = self.DEFAULT_TIER_MODIFIERS[tier]["expense_ratio"]
        expense_amount = premiums * expense_ratio
        
        return expense_ratio, expense_amount
    
    def get_tier_description(self, tier: str) -> Dict[str, str]:
        """Get human-readable description of tier characteristics.
        
        Args:
            tier: Product tier
            
        Returns:
            Dict with tier characteristics
        """
        descriptions = {
            "Basic": {
                "target_market": "Price-sensitive customers",
                "coverage": "Essential coverage with higher deductibles",
                "service_level": "Standard service, digital-first",
                "risk_profile": "Higher frequency, lower severity claims",
                "competitive_position": "Volume-focused, commodity product"
            },
            "Standard": {
                "target_market": "Mainstream customers",
                "coverage": "Comprehensive coverage with moderate deductibles",
                "service_level": "Full service with multiple channels",
                "risk_profile": "Average frequency and severity",
                "competitive_position": "Balanced price and features"
            },
            "Premium": {
                "target_market": "Quality-focused customers",
                "coverage": "Enhanced coverage with low deductibles",
                "service_level": "White-glove service, dedicated support",
                "risk_profile": "Lower frequency, responsible customers",
                "competitive_position": "Differentiated, relationship-focused"
            }
        }
        
        return descriptions.get(tier, {})
    
    def calculate_market_share_impact(
        self,
        company_tier: str,
        competitor_tiers: Dict[str, int]
    ) -> Decimal:
        """Calculate market share impact based on tier mix.
        
        Args:
            company_tier: Company's product tier
            competitor_tiers: Dict of tier -> count of competitors
            
        Returns:
            Market share multiplier
        """
        # Base attractiveness scores
        tier_scores = {
            "Basic": Decimal("1.5"),    # High volume appeal
            "Standard": Decimal("1.0"),  # Baseline
            "Premium": Decimal("0.7")    # Niche appeal
        }
        
        company_score = tier_scores.get(company_tier, Decimal("1.0"))
        
        # Calculate competitive landscape
        total_competitor_score = Decimal("0")
        total_competitors = 0
        
        for tier, count in competitor_tiers.items():
            if count > 0:
                total_competitor_score += tier_scores.get(tier, Decimal("1.0")) * count
                total_competitors += count
        
        if total_competitors == 0:
            # No competition, full market potential
            return Decimal("1.0")
        
        avg_competitor_score = total_competitor_score / total_competitors
        
        # Market share impact based on relative attractiveness
        market_share_multiplier = company_score / (company_score + avg_competitor_score)
        
        return market_share_multiplier
    
    def should_grandfather_policies(
        self,
        tier_change: Tuple[str, str],
        policy_count: int
    ) -> bool:
        """Determine if existing policies should be grandfathered.
        
        Args:
            tier_change: Tuple of (from_tier, to_tier)
            policy_count: Number of existing policies
            
        Returns:
            Whether to grandfather existing policies
        """
        from_tier, to_tier = tier_change
        
        # Always grandfather if moving from Premium to lower tier
        if from_tier == "Premium" and to_tier in ["Standard", "Basic"]:
            return True
        
        # Grandfather if significant policy count
        if policy_count > 1000:
            return True
        
        # Don't grandfather for upgrades (customer benefit)
        if (from_tier == "Basic" and to_tier in ["Standard", "Premium"]) or \
           (from_tier == "Standard" and to_tier == "Premium"):
            return False
        
        # Default to grandfathering for downgrades
        return True 