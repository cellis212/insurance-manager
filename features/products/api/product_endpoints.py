"""API endpoints for product management.

Provides REST endpoints for creating products, switching tiers, and viewing performance.
"""

import logging
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from features.products.services.product_manager import ProductManager
from features.products.services.tier_calculator import TierCalculator
from features.products.plugin import ProductSystemPlugin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])


# Pydantic models for API
class ProductCreateRequest(BaseModel):
    """Request model for creating a new product."""
    
    state_id: UUID = Field(description="State where product will be offered")
    line_of_business_id: UUID = Field(description="Line of business")
    tier: str = Field(description="Product tier: Basic, Standard, or Premium")
    base_premium: Decimal = Field(description="Base annual premium before tier adjustments", gt=0)
    deductible: Decimal = Field(description="Deductible amount", ge=0)
    coverage_limit: Decimal = Field(description="Maximum coverage per claim", gt=0)
    
    @validator('tier')
    def validate_tier(cls, v):
        """Validate tier is one of the allowed values."""
        if v not in ["Basic", "Standard", "Premium"]:
            raise ValueError("Tier must be Basic, Standard, or Premium")
        return v


class TierSwitchRequest(BaseModel):
    """Request model for switching product tier."""
    
    new_tier: str = Field(description="New tier: Basic, Standard, or Premium")
    
    @validator('new_tier')
    def validate_tier(cls, v):
        """Validate tier is one of the allowed values."""
        if v not in ["Basic", "Standard", "Premium"]:
            raise ValueError("Tier must be Basic, Standard, or Premium")
        return v


class ProductResponse(BaseModel):
    """Response model for product details."""
    
    id: UUID
    company_id: UUID
    state_code: str
    line_of_business_code: str
    tier: str
    base_premium: float
    deductible: float
    coverage_limit: float
    active_policies: int
    market_share: float
    effective_loss_ratio: float
    has_pending_switch: bool
    pending_tier: Optional[str] = None
    switch_effective_date: Optional[str] = None
    
    class Config:
        """Pydantic config."""
        orm_mode = True


class ProductPerformanceResponse(BaseModel):
    """Response model for product performance metrics."""
    
    product_id: UUID
    tier: str
    loss_ratio: float
    expected_loss_ratio: float
    performance_ratio: float
    performance_assessment: str


class TierModifiersResponse(BaseModel):
    """Response model for tier modifiers."""
    
    tier: str
    price_modifier: float
    risk_selection: float
    demand_elasticity: float
    retention_rate: float
    expense_ratio: float
    description: dict


# Import real authentication from API auth utils
from api.auth_utils import get_current_company
from core.models.company import Company

async def get_current_company_id(
    company: Company = Depends(get_current_company)
) -> UUID:
    """Get the current company ID from authentication."""
    return company.id


@router.get("/tiers", response_model=List[TierModifiersResponse])
async def get_tier_information(
    db: AsyncSession = Depends(get_db)
) -> List[TierModifiersResponse]:
    """Get information about all product tiers.
    
    Returns modifier values and descriptions for each tier.
    """
    tier_calculator = TierCalculator(db)
    
    responses = []
    for tier in ["Basic", "Standard", "Premium"]:
        modifiers = await tier_calculator.get_tier_modifiers(tier)
        description = tier_calculator.get_tier_description(tier)
        
        responses.append(TierModifiersResponse(
            tier=tier,
            price_modifier=float(modifiers["price_modifier"]),
            risk_selection=float(modifiers["risk_selection"]),
            demand_elasticity=float(modifiers["demand_elasticity"]),
            retention_rate=float(modifiers["retention_rate"]),
            expense_ratio=float(modifiers["expense_ratio"]),
            description=description
        ))
    
    return responses


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    request: ProductCreateRequest,
    company_id: UUID = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db)
) -> ProductResponse:
    """Create a new product offering.
    
    Company must be authorized in the state before creating products.
    Only one product per company/state/line combination is allowed.
    """
    product_manager = ProductManager(db)
    
    try:
        product = await product_manager.create_product(
            company_id=company_id,
            state_id=request.state_id,
            line_of_business_id=request.line_of_business_id,
            tier=request.tier,
            base_premium=request.base_premium,
            deductible=request.deductible,
            coverage_limit=request.coverage_limit
        )
        
        await db.commit()
        
        # Build response
        return ProductResponse(
            id=product.id,
            company_id=product.company_id,
            state_code=product.state.code,
            line_of_business_code=product.line_of_business.code,
            tier=product.tier,
            base_premium=float(product.base_premium),
            deductible=float(product.deductible),
            coverage_limit=float(product.coverage_limit),
            active_policies=int(product.active_policies or 0),
            market_share=float(product.market_share or 0),
            effective_loss_ratio=float(product.effective_loss_ratio),
            has_pending_switch=False,
            pending_tier=None,
            switch_effective_date=None
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create product"
        )


@router.get("/", response_model=List[ProductResponse])
async def list_company_products(
    state_id: Optional[UUID] = None,
    line_of_business_id: Optional[UUID] = None,
    company_id: UUID = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db)
) -> List[ProductResponse]:
    """List all products for the current company.
    
    Can filter by state and/or line of business.
    """
    product_manager = ProductManager(db)
    
    products = await product_manager.get_company_products(
        company_id=company_id,
        state_id=state_id,
        line_of_business_id=line_of_business_id
    )
    
    responses = []
    for product in products:
        # Check for pending switch
        has_pending = bool(product.custom_config and "pending_tier" in product.custom_config)
        
        responses.append(ProductResponse(
            id=product.id,
            company_id=product.company_id,
            state_code=product.state.code,
            line_of_business_code=product.line_of_business.code,
            tier=product.tier,
            base_premium=float(product.base_premium),
            deductible=float(product.deductible),
            coverage_limit=float(product.coverage_limit),
            active_policies=int(product.active_policies or 0),
            market_share=float(product.market_share or 0),
            effective_loss_ratio=float(product.effective_loss_ratio),
            has_pending_switch=has_pending,
            pending_tier=product.custom_config.get("pending_tier") if has_pending else None,
            switch_effective_date=product.custom_config.get("switch_effective_date") if has_pending else None
        ))
    
    return responses


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    company_id: UUID = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db)
) -> ProductResponse:
    """Get details for a specific product.
    
    Product must belong to the current company.
    """
    product_manager = ProductManager(db)
    
    products = await product_manager.get_company_products(company_id)
    product = next((p for p in products if p.id == product_id), None)
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check for pending switch
    has_pending = bool(product.custom_config and "pending_tier" in product.custom_config)
    
    return ProductResponse(
        id=product.id,
        company_id=product.company_id,
        state_code=product.state.code,
        line_of_business_code=product.line_of_business.code,
        tier=product.tier,
        base_premium=float(product.base_premium),
        deductible=float(product.deductible),
        coverage_limit=float(product.coverage_limit),
        active_policies=int(product.active_policies or 0),
        market_share=float(product.market_share or 0),
        effective_loss_ratio=float(product.effective_loss_ratio),
        has_pending_switch=has_pending,
        pending_tier=product.custom_config.get("pending_tier") if has_pending else None,
        switch_effective_date=product.custom_config.get("switch_effective_date") if has_pending else None
    )


@router.post("/{product_id}/switch-tier")
async def switch_product_tier(
    product_id: UUID,
    request: TierSwitchRequest,
    company_id: UUID = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Initiate a product tier switch.
    
    Switching tiers costs $50,000 and takes 2 weeks to complete.
    If the product has active policies, customer notification is required.
    """
    product_manager = ProductManager(db)
    
    # Verify product belongs to company
    products = await product_manager.get_company_products(company_id)
    if not any(p.id == product_id for p in products):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    try:
        result = await product_manager.switch_product_tier(
            product_id=product_id,
            new_tier=request.new_tier
        )
        
        await db.commit()
        
        return {
            "message": "Tier switch initiated successfully",
            "details": result
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error switching tier: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to switch product tier"
        )


@router.get("/{product_id}/performance", response_model=List[ProductPerformanceResponse])
async def get_product_performance(
    product_id: UUID,
    weeks: int = 4,
    company_id: UUID = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db)
) -> List[ProductPerformanceResponse]:
    """Get performance history for a product.
    
    Returns loss ratio and performance metrics for the specified number of weeks.
    """
    product_manager = ProductManager(db)
    
    # Verify product belongs to company
    products = await product_manager.get_company_products(company_id)
    product = next((p for p in products if p.id == product_id), None)
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Get performance history from custom config
    performance_history = product.custom_config.get("performance_history", [])
    
    # Limit to requested weeks
    recent_history = performance_history[-weeks:] if len(performance_history) > weeks else performance_history
    
    # Convert to response format
    responses = []
    for record in recent_history:
        responses.append(ProductPerformanceResponse(
            product_id=product.id,
            tier=record.get("tier", product.tier),
            loss_ratio=float(record.get("loss_ratio", 0)),
            expected_loss_ratio=float(record.get("expected_loss_ratio", 0.67)),
            performance_ratio=float(record.get("performance_ratio", 1.0)),
            performance_assessment=product_manager._assess_performance(
                Decimal(record.get("performance_ratio", "1.0"))
            )
        ))
    
    return responses


@router.get("/summary", response_model=dict)
async def get_product_summary(
    company_id: UUID = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get comprehensive product summary for the company.
    
    Includes counts by tier/state/line, pending switches, and performance metrics.
    """
    plugin = ProductSystemPlugin()
    await plugin.initialize(db, {})
    
    summary = await plugin.get_company_product_summary(company_id)
    
    return summary 