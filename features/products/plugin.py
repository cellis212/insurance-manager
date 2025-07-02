"""Product system plugin for the Insurance Manager game.

Manages the three-tier product system and integrates with turn processing.
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.interfaces.game_system import GameSystemPlugin
from core.models import (
    Company,
    Product,
    CompanyTurnDecision,
    CompanyTurnResult,
    GameEvent,
)
from features.products.services.product_manager import ProductManager
from features.products.services.tier_calculator import TierCalculator

logger = logging.getLogger(__name__)


class ProductSystemPlugin(GameSystemPlugin):
    """Plugin for managing the three-tier product system."""
    
    def __init__(self):
        """Initialize the product system plugin."""
        super().__init__()
        self.product_manager: Optional[ProductManager] = None
        self.tier_calculator: Optional[TierCalculator] = None
    
    @property
    def name(self) -> str:
        """Get plugin name."""
        return "ProductSystemPlugin"
    
    @property
    def version(self) -> str:
        """Get plugin version."""
        return "1.0.0"
    
    @property
    def dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []  # No dependencies on other plugins
    
    async def initialize(self, db_session: AsyncSession, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration.
        
        Args:
            db_session: Database session
            config: Plugin configuration
        """
        self.db = db_session
        self.config = config
        self.product_manager = ProductManager(db_session)
        self.tier_calculator = TierCalculator(db_session)
        logger.info("Product system plugin initialized")
    
    async def validate_configuration(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Whether configuration is valid
        """
        # No specific configuration required
        return True
    
    async def on_turn_start(self, turn_id: UUID, game_state: Dict[str, Any]) -> None:
        """Handle turn start events.
        
        Process any pending product tier switches.
        
        Args:
            turn_id: Current turn ID
            game_state: Shared game state
        """
        logger.info(f"Processing product tier switches for turn {turn_id}")
        
        # Process pending tier switches
        processed_switches = await self.product_manager.process_pending_switches(turn_id)
        
        if processed_switches:
            # Store in game state for other plugins
            game_state["product_switches"] = processed_switches
            
            # Create game event
            event = GameEvent(
                event_type="product_switches_processed",
                category="product",
                severity="info",
                data={
                    "turn_id": str(turn_id),
                    "switches_count": len(processed_switches),
                    "switches": processed_switches
                },
                message=f"Processed {len(processed_switches)} product tier switches"
            )
            self.db.add(event)
            
        logger.info(f"Processed {len(processed_switches)} tier switches")
    
    async def on_decision_submitted(
        self,
        company_id: UUID,
        turn_id: UUID,
        decisions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle decision submission.
        
        Process product-related decisions.
        
        Args:
            company_id: Company submitting decisions
            turn_id: Current turn ID
            decisions: Submitted decisions
            
        Returns:
            Validation results
        """
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "processed_products": []
        }
        
        # Check for product decisions
        product_decisions = decisions.get("products", {})
        
        if not product_decisions:
            return validation_results
        
        # Process new product offerings
        new_products = product_decisions.get("new_products", [])
        for product_data in new_products:
            try:
                product = await self.product_manager.create_product(
                    company_id=company_id,
                    state_id=UUID(product_data["state_id"]),
                    line_of_business_id=UUID(product_data["line_of_business_id"]),
                    tier=product_data["tier"],
                    base_premium=Decimal(str(product_data["base_premium"])),
                    deductible=Decimal(str(product_data["deductible"])),
                    coverage_limit=Decimal(str(product_data["coverage_limit"]))
                )
                validation_results["processed_products"].append({
                    "action": "created",
                    "product_id": str(product.id),
                    "tier": product.tier
                })
            except ValueError as e:
                validation_results["errors"].append(f"Product creation failed: {str(e)}")
                validation_results["valid"] = False
            except Exception as e:
                logger.error(f"Unexpected error creating product: {str(e)}")
                validation_results["errors"].append("Product creation failed due to system error")
                validation_results["valid"] = False
        
        # Process tier switches
        tier_switches = product_decisions.get("tier_switches", [])
        for switch_data in tier_switches:
            try:
                switch_result = await self.product_manager.switch_product_tier(
                    product_id=UUID(switch_data["product_id"]),
                    new_tier=switch_data["new_tier"]
                )
                validation_results["processed_products"].append({
                    "action": "tier_switch_initiated",
                    "product_id": switch_data["product_id"],
                    "switch_details": switch_result
                })
                if switch_result.get("notification_required"):
                    validation_results["warnings"].append(
                        f"Customer notification required for tier switch on product {switch_data['product_id']}"
                    )
            except ValueError as e:
                validation_results["errors"].append(f"Tier switch failed: {str(e)}")
                validation_results["valid"] = False
            except Exception as e:
                logger.error(f"Unexpected error switching tier: {str(e)}")
                validation_results["errors"].append("Tier switch failed due to system error")
                validation_results["valid"] = False
        
        return validation_results
    
    async def calculate_results(
        self,
        turn_id: UUID,
        game_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate product-related results.
        
        Updates product performance and market share.
        
        Args:
            turn_id: Current turn ID
            game_state: Shared game state
            
        Returns:
            Product calculation results
        """
        results = {
            "product_performance": {},
            "market_share_updates": {}
        }
        
        # Get turn results from game state
        turn_results = game_state.get("turn_results", {})
        
        for company_id, company_results in turn_results.items():
            company_uuid = UUID(company_id) if isinstance(company_id, str) else company_id
            
            # Get company products
            products = await self.product_manager.get_company_products(company_uuid)
            
            for product in products:
                # Extract product performance data from turn results
                product_key = f"{product.state.code}_{product.line_of_business.code}"
                product_data = company_results.get("products", {}).get(product_key, {})
                
                if product_data:
                    # Calculate performance metrics
                    performance = await self.product_manager.calculate_product_performance(
                        product_id=product.id,
                        claims_count=product_data.get("claims_count", 0),
                        claims_amount=Decimal(str(product_data.get("claims_amount", 0))),
                        premiums_collected=Decimal(str(product_data.get("premiums_collected", 0)))
                    )
                    
                    results["product_performance"][str(product.id)] = performance
                    
                    # Update market share if available
                    if "market_share" in product_data:
                        product.market_share = Decimal(str(product_data["market_share"]))
                        results["market_share_updates"][str(product.id)] = product_data["market_share"]
                    
                    # Update active policies
                    if "active_policies" in product_data:
                        product.active_policies = product_data["active_policies"]
        
        # Store results in game state for other plugins
        game_state["product_results"] = results
        
        await self.db.flush()
        return results
    
    async def on_turn_complete(self, turn_id: UUID, game_state: Dict[str, Any]) -> None:
        """Handle turn completion.
        
        Finalize product updates.
        
        Args:
            turn_id: Completed turn ID
            game_state: Shared game state
        """
        # Create summary event
        product_results = game_state.get("product_results", {})
        
        if product_results:
            event = GameEvent(
                event_type="product_turn_summary",
                category="product",
                severity="info",
                data={
                    "turn_id": str(turn_id),
                    "products_updated": len(product_results.get("product_performance", {})),
                    "market_shares_updated": len(product_results.get("market_share_updates", {}))
                },
                message=f"Product system processed turn {turn_id}"
            )
            self.db.add(event)
        
        logger.info(f"Product system completed processing for turn {turn_id}")
    
    async def get_company_product_summary(self, company_id: UUID) -> Dict[str, Any]:
        """Get comprehensive product summary for a company.
        
        Args:
            company_id: Company ID
            
        Returns:
            Product summary including all products and their performance
        """
        products = await self.product_manager.get_company_products(company_id)
        
        summary = {
            "total_products": len(products),
            "products_by_tier": {"Basic": 0, "Standard": 0, "Premium": 0},
            "products_by_state": {},
            "products_by_line": {},
            "total_active_policies": 0,
            "pending_switches": [],
            "products": []
        }
        
        for product in products:
            # Count by tier
            summary["products_by_tier"][product.tier] += 1
            
            # Count by state
            state_code = product.state.code
            if state_code not in summary["products_by_state"]:
                summary["products_by_state"][state_code] = 0
            summary["products_by_state"][state_code] += 1
            
            # Count by line
            line_code = product.line_of_business.code
            if line_code not in summary["products_by_line"]:
                summary["products_by_line"][line_code] = 0
            summary["products_by_line"][line_code] += 1
            
            # Total policies
            summary["total_active_policies"] += int(product.active_policies or 0)
            
            # Check for pending switches
            if product.custom_config and "pending_tier" in product.custom_config:
                summary["pending_switches"].append({
                    "product_id": str(product.id),
                    "current_tier": product.tier,
                    "new_tier": product.custom_config["pending_tier"],
                    "effective_date": product.custom_config.get("switch_effective_date")
                })
            
            # Add product details
            product_detail = {
                "id": str(product.id),
                "state": state_code,
                "line_of_business": line_code,
                "tier": product.tier,
                "base_premium": float(product.base_premium),
                "active_policies": int(product.active_policies or 0),
                "market_share": float(product.market_share or 0),
                "effective_loss_ratio": float(product.effective_loss_ratio),
                "performance_history": product.custom_config.get("performance_history", [])[-4:]  # Last 4 weeks
            }
            summary["products"].append(product_detail)
        
        return summary 