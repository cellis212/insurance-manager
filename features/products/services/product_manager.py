"""Product manager service for handling product operations.

Manages product creation, tier switching, and validation.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models import (
    Product,
    Company,
    CompanyStateAuthorization,
    CompanyTurnDecision,
    Turn,
    GameConfiguration,
    GameEvent,
    AuditLog,
)
from core.models.line_of_business import LineOfBusiness
from core.models.state import State

logger = logging.getLogger(__name__)


class ProductManager:
    """Manages product lifecycle and operations."""
    
    def __init__(self, db_session: AsyncSession):
        """Initialize product manager.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
        self._config: Optional[Dict] = None
    
    async def _get_config(self) -> Dict:
        """Get product configuration parameters.
        
        Returns:
            Product parameters from game configuration
        """
        if self._config is None:
            result = await self.db.execute(
                select(GameConfiguration).where(GameConfiguration.is_active == True)
            )
            config = result.scalar_one_or_none()
            if not config:
                raise ValueError("No active game configuration found")
            self._config = config.get_parameter("product_parameters", {})
        return self._config
    
    async def create_product(
        self,
        company_id: UUID,
        state_id: UUID,
        line_of_business_id: UUID,
        tier: str,
        base_premium: Decimal,
        deductible: Decimal,
        coverage_limit: Decimal
    ) -> Product:
        """Create a new product offering.
        
        Args:
            company_id: Company offering the product
            state_id: State where product is offered
            line_of_business_id: Line of business
            tier: Product tier (Basic/Standard/Premium)
            base_premium: Base annual premium before tier adjustments
            deductible: Deductible amount
            coverage_limit: Maximum coverage per claim
            
        Returns:
            Created product
            
        Raises:
            ValueError: If validation fails
        """
        # Validate tier
        if tier not in ["Basic", "Standard", "Premium"]:
            raise ValueError(f"Invalid tier: {tier}. Must be Basic, Standard, or Premium")
        
        # Check if company is authorized in state
        auth_result = await self.db.execute(
            select(CompanyStateAuthorization).where(
                and_(
                    CompanyStateAuthorization.company_id == company_id,
                    CompanyStateAuthorization.state_id == state_id,
                    CompanyStateAuthorization.is_active == True
                )
            )
        )
        auth = auth_result.scalar_one_or_none()
        if not auth:
            raise ValueError("Company is not authorized to operate in this state")
        
        # Check if product already exists (unique constraint)
        existing_result = await self.db.execute(
            select(Product).where(
                and_(
                    Product.company_id == company_id,
                    Product.state_id == state_id,
                    Product.line_of_business_id == line_of_business_id
                )
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            raise ValueError(
                "Product already exists for this company/state/line combination. "
                "Use switch_product_tier instead."
            )
        
        # Create product
        product = Product(
            company_id=company_id,
            state_id=state_id,
            line_of_business_id=line_of_business_id,
            tier=tier,
            base_premium=base_premium,
            deductible=deductible,
            coverage_limit=coverage_limit,
            active_policies=0,
            market_share=Decimal("0.0")
        )
        
        self.db.add(product)
        await self.db.flush()
        
        # Create audit log
        audit_log = AuditLog(
            entity_type="Product",
            entity_id=product.id,
            action="created",
            changes={
                "tier": tier,
                "base_premium": str(base_premium),
                "state_id": str(state_id),
                "line_of_business_id": str(line_of_business_id)
            },
            user_id=None,  # System action
            company_id=company_id
        )
        self.db.add(audit_log)
        
        # Create game event
        event = GameEvent(
            event_type="product_created",
            category="product",
            severity="info",
            data={
                "company_id": str(company_id),
                "product_id": str(product.id),
                "tier": tier,
                "state_id": str(state_id),
                "line_of_business_id": str(line_of_business_id)
            },
            message=f"Created {tier} tier product"
        )
        self.db.add(event)
        
        logger.info(f"Created {tier} product for company {company_id}")
        return product
    
    async def get_company_products(
        self,
        company_id: UUID,
        state_id: Optional[UUID] = None,
        line_of_business_id: Optional[UUID] = None
    ) -> List[Product]:
        """Get all products for a company.
        
        Args:
            company_id: Company ID
            state_id: Filter by state (optional)
            line_of_business_id: Filter by line (optional)
            
        Returns:
            List of products
        """
        query = select(Product).where(Product.company_id == company_id)
        
        if state_id:
            query = query.where(Product.state_id == state_id)
        if line_of_business_id:
            query = query.where(Product.line_of_business_id == line_of_business_id)
        
        query = query.options(
            selectinload(Product.state),
            selectinload(Product.line_of_business)
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def switch_product_tier(
        self,
        product_id: UUID,
        new_tier: str,
        effective_turn_id: Optional[UUID] = None
    ) -> Dict:
        """Switch a product to a different tier.
        
        Implements the 2-week switching delay and cost.
        
        Args:
            product_id: Product to switch
            new_tier: New tier (Basic/Standard/Premium)
            effective_turn_id: Turn when switch takes effect (optional)
            
        Returns:
            Dict with switch details including effective date and cost
            
        Raises:
            ValueError: If validation fails
        """
        # Validate new tier
        if new_tier not in ["Basic", "Standard", "Premium"]:
            raise ValueError(f"Invalid tier: {new_tier}")
        
        # Get product with relationships
        result = await self.db.execute(
            select(Product)
            .where(Product.id == product_id)
            .options(selectinload(Product.company))
        )
        product = result.scalar_one_or_none()
        if not product:
            raise ValueError(f"Product {product_id} not found")
        
        # Check if already same tier
        if product.tier == new_tier:
            raise ValueError(f"Product is already {new_tier} tier")
        
        # Get configuration
        config = await self._get_config()
        switch_cost = Decimal(str(config.get("switch_cost", 50000)))
        switch_weeks = config.get("switch_time_weeks", 2)
        
        # Check if company has sufficient capital
        if product.company.current_capital < switch_cost:
            raise ValueError(
                f"Insufficient capital. Need {switch_cost}, have {product.company.current_capital}"
            )
        
        # Calculate effective date
        if not effective_turn_id:
            # Get current turn
            turn_result = await self.db.execute(
                select(Turn)
                .where(Turn.semester_id == product.company.semester_id)
                .order_by(Turn.turn_number.desc())
                .limit(1)
            )
            current_turn = turn_result.scalar_one_or_none()
            if not current_turn:
                raise ValueError("No active turn found")
            
            # Calculate future turn
            future_turn_number = current_turn.turn_number + switch_weeks
            effective_date = current_turn.end_date + timedelta(weeks=switch_weeks)
        else:
            # Validate provided turn
            turn_result = await self.db.execute(
                select(Turn).where(Turn.id == effective_turn_id)
            )
            effective_turn = turn_result.scalar_one_or_none()
            if not effective_turn:
                raise ValueError(f"Turn {effective_turn_id} not found")
            effective_date = effective_turn.start_date
        
        # Store switch details in custom_config
        switch_details = {
            "pending_tier": new_tier,
            "switch_initiated": datetime.utcnow().isoformat(),
            "switch_effective_date": effective_date.isoformat(),
            "switch_cost": str(switch_cost),
            "previous_tier": product.tier,
            "notification_sent": product.active_policies > 0
        }
        
        # Update product custom config
        if product.custom_config is None:
            product.custom_config = {}
        product.custom_config.update(switch_details)
        
        # Deduct switch cost from company capital
        product.company.current_capital -= switch_cost
        
        # Create audit log
        audit_log = AuditLog(
            entity_type="Product",
            entity_id=product.id,
            action="tier_switch_initiated",
            changes={
                "from_tier": product.tier,
                "to_tier": new_tier,
                "cost": str(switch_cost),
                "effective_date": effective_date.isoformat()
            },
            company_id=product.company_id
        )
        self.db.add(audit_log)
        
        # Create game event
        event = GameEvent(
            event_type="product_tier_switch",
            category="product",
            severity="info",
            data={
                "company_id": str(product.company_id),
                "product_id": str(product_id),
                "from_tier": product.tier,
                "to_tier": new_tier,
                "switch_cost": str(switch_cost),
                "effective_date": effective_date.isoformat()
            },
            message=f"Initiated tier switch from {product.tier} to {new_tier}"
        )
        self.db.add(event)
        
        await self.db.flush()
        
        logger.info(
            f"Initiated tier switch for product {product_id}: "
            f"{product.tier} -> {new_tier}, effective {effective_date}"
        )
        
        return {
            "product_id": str(product_id),
            "current_tier": product.tier,
            "new_tier": new_tier,
            "switch_cost": switch_cost,
            "effective_date": effective_date,
            "notification_required": product.active_policies > 0
        }
    
    async def process_pending_switches(self, turn_id: UUID) -> List[Dict]:
        """Process any product tier switches that become effective this turn.
        
        Args:
            turn_id: Current turn ID
            
        Returns:
            List of processed switches
        """
        # Get current turn
        turn_result = await self.db.execute(
            select(Turn).where(Turn.id == turn_id)
        )
        current_turn = turn_result.scalar_one_or_none()
        if not current_turn:
            raise ValueError(f"Turn {turn_id} not found")
        
        # Find products with pending switches
        result = await self.db.execute(
            select(Product).where(
                Product.custom_config.op("?")("pending_tier")
            )
        )
        products_with_switches = list(result.scalars().all())
        
        processed = []
        for product in products_with_switches:
            switch_date_str = product.custom_config.get("switch_effective_date")
            if not switch_date_str:
                continue
            
            switch_date = datetime.fromisoformat(switch_date_str).date()
            if switch_date <= current_turn.start_date:
                # Process the switch
                old_tier = product.tier
                new_tier = product.custom_config["pending_tier"]
                product.tier = new_tier
                
                # Apply new tier effects
                product._apply_tier_effects()
                
                # Create completion record
                completion_details = {
                    "switch_completed": datetime.utcnow().isoformat(),
                    "previous_tier": old_tier,
                    "completed_tier": new_tier
                }
                
                # Move pending details to history
                if "switch_history" not in product.custom_config:
                    product.custom_config["switch_history"] = []
                product.custom_config["switch_history"].append({
                    **product.custom_config.get("pending_tier", {}),
                    **completion_details
                })
                
                # Remove pending switch
                product.custom_config.pop("pending_tier", None)
                product.custom_config.pop("switch_initiated", None)
                product.custom_config.pop("switch_effective_date", None)
                product.custom_config.pop("switch_cost", None)
                product.custom_config.pop("previous_tier", None)
                product.custom_config.pop("notification_sent", None)
                
                # Create audit log
                audit_log = AuditLog(
                    entity_type="Product",
                    entity_id=product.id,
                    action="tier_switch_completed",
                    changes={
                        "from_tier": old_tier,
                        "to_tier": new_tier,
                        "turn_id": str(turn_id)
                    },
                    company_id=product.company_id
                )
                self.db.add(audit_log)
                
                processed.append({
                    "product_id": str(product.id),
                    "company_id": str(product.company_id),
                    "from_tier": old_tier,
                    "to_tier": new_tier
                })
                
                logger.info(
                    f"Completed tier switch for product {product.id}: "
                    f"{old_tier} -> {new_tier}"
                )
        
        await self.db.flush()
        return processed
    
    async def calculate_product_performance(
        self,
        product_id: UUID,
        claims_count: int,
        claims_amount: Decimal,
        premiums_collected: Decimal
    ) -> Dict:
        """Calculate product performance metrics.
        
        Args:
            product_id: Product ID
            claims_count: Number of claims
            claims_amount: Total claim amount
            premiums_collected: Total premiums
            
        Returns:
            Performance metrics
        """
        # Get product
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise ValueError(f"Product {product_id} not found")
        
        # Calculate metrics
        loss_ratio = (
            claims_amount / premiums_collected 
            if premiums_collected > 0 
            else Decimal("0")
        )
        
        # Expected vs actual comparison
        expected_loss_ratio = product.effective_loss_ratio
        performance_ratio = loss_ratio / expected_loss_ratio if expected_loss_ratio > 0 else Decimal("1")
        
        # Store in custom config
        if product.custom_config is None:
            product.custom_config = {}
        
        if "performance_history" not in product.custom_config:
            product.custom_config["performance_history"] = []
        
        performance_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "claims_count": claims_count,
            "claims_amount": str(claims_amount),
            "premiums_collected": str(premiums_collected),
            "loss_ratio": str(loss_ratio),
            "expected_loss_ratio": str(expected_loss_ratio),
            "performance_ratio": str(performance_ratio),
            "tier": product.tier
        }
        
        product.custom_config["performance_history"].append(performance_data)
        
        # Keep only last 52 weeks of history
        if len(product.custom_config["performance_history"]) > 52:
            product.custom_config["performance_history"] = (
                product.custom_config["performance_history"][-52:]
            )
        
        await self.db.flush()
        
        return {
            "product_id": str(product_id),
            "tier": product.tier,
            "loss_ratio": loss_ratio,
            "expected_loss_ratio": expected_loss_ratio,
            "performance_ratio": performance_ratio,
            "performance_assessment": self._assess_performance(performance_ratio)
        }
    
    def _assess_performance(self, performance_ratio: Decimal) -> str:
        """Assess product performance based on ratio.
        
        Args:
            performance_ratio: Actual vs expected loss ratio
            
        Returns:
            Performance assessment
        """
        if performance_ratio < Decimal("0.8"):
            return "excellent"
        elif performance_ratio < Decimal("0.95"):
            return "good"
        elif performance_ratio < Decimal("1.05"):
            return "expected"
        elif performance_ratio < Decimal("1.2"):
            return "poor"
        else:
            return "critical" 