"""API endpoints for geographic expansion functionality.

Provides endpoints for:
- Getting expansion opportunities
- Requesting expansion to new states
- Viewing pending and approved authorizations
- Calculating expansion costs
"""

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import Company, State, CompanyStateAuthorization
from features.expansion.services import ExpansionCalculator, ApprovalWorkflow

router = APIRouter(prefix="/expansion", tags=["expansion"])


# Response models
class ExpansionCostResponse(BaseModel):
    """Response model for expansion cost calculation."""
    state_code: str
    state_name: str
    total_cost: Decimal
    base_cost: Decimal
    market_adjusted_cost: Decimal
    distance_cost: Decimal
    discounts: dict[str, Decimal]
    discount_amount: Decimal
    is_home_state: bool
    is_adjacent: Optional[bool]
    approval_weeks: int
    regulatory_category: str
    distance_miles: float


class ExpansionOpportunityResponse(ExpansionCostResponse):
    """Response model for expansion opportunities."""
    state_id: UUID


class PendingExpansionResponse(BaseModel):
    """Response model for pending expansions."""
    authorization_id: UUID
    state_code: str
    state_name: str
    application_date: str
    expected_approval_date: str
    days_remaining: int
    weeks_remaining: int


class AuthorizedStateResponse(BaseModel):
    """Response model for authorized states."""
    state_id: UUID
    state_code: str
    state_name: str
    authorization_date: str
    compliance_score: str
    is_home_state: bool


class ExpansionRequestBody(BaseModel):
    """Request body for expansion requests."""
    state_codes: List[str] = Field(..., min_items=1, max_items=3)


class ExpansionRequestResponse(BaseModel):
    """Response model for expansion requests."""
    authorizations: List[dict]
    total_cost: Decimal
    remaining_capital: Decimal


# Import real authentication from API auth utils
from api.auth_utils import get_current_company


# Dependency to get game configuration
async def get_expansion_config(
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get expansion configuration for the current semester."""
    from core.models import Semester, SemesterConfiguration, GameConfiguration
    
    # Get current semester
    semester = await db.get(Semester, company.semester_id)
    if not semester:
        # Fall back to default configuration
        return {
            "base_expansion_weeks": 4,
            "distance_cost_per_mile": 100,
            "market_size_cost_multiplier": 1.0,
            "max_states_per_turn": 3,
            "home_state_discount": 0.5,
            "adjacent_state_discount": 0.2,
            "same_region_discount": 0.1
        }
    
    # Get semester configuration
    result = await db.execute(
        select(SemesterConfiguration)
        .where(SemesterConfiguration.semester_id == semester.id)
    )
    semester_config = result.scalar_one_or_none()
    
    # Get base game configuration
    base_config_result = await db.execute(
        select(GameConfiguration)
        .where(GameConfiguration.is_active == True)
        .order_by(GameConfiguration.version.desc())
    )
    base_config = base_config_result.scalar_one_or_none()
    
    if not base_config:
        # Fall back to default if no configuration found
        return {
            "base_expansion_weeks": 4,
            "distance_cost_per_mile": 100,
            "market_size_cost_multiplier": 1.0,
            "max_states_per_turn": 3,
            "home_state_discount": 0.5,
            "adjacent_state_discount": 0.2,
            "same_region_discount": 0.1
        }
    
    # Start with base expansion parameters
    expansion_config = base_config.expansion_parameters.copy()
    
    # Apply semester overrides if they exist
    if semester_config and semester_config.feature_overrides:
        expansion_overrides = semester_config.feature_overrides.get("expansion_parameters", {})
        expansion_config.update(expansion_overrides)
    
    # Ensure required keys exist with defaults
    expansion_config.setdefault("base_expansion_weeks", 4)
    expansion_config.setdefault("distance_cost_per_mile", 100)
    expansion_config.setdefault("market_size_cost_multiplier", 1.0)
    expansion_config.setdefault("max_states_per_turn", 3)
    expansion_config.setdefault("home_state_discount", 0.5)
    expansion_config.setdefault("adjacent_state_discount", 0.2)
    expansion_config.setdefault("same_region_discount", 0.1)
    
    return expansion_config


@router.get("/opportunities", response_model=List[ExpansionOpportunityResponse])
async def get_expansion_opportunities(
    budget: Optional[Decimal] = Query(None, description="Maximum budget for expansion"),
    company: Company = Depends(get_current_company),
    config: dict = Depends(get_expansion_config),
    db: AsyncSession = Depends(get_db)
) -> List[ExpansionOpportunityResponse]:
    """Get available expansion opportunities for the company.
    
    Returns a list of states the company can expand to, sorted by cost.
    Optionally filtered by budget constraint.
    """
    calculator = ExpansionCalculator(config)
    opportunities = await calculator.get_expansion_opportunities(db, company, budget)
    
    return [
        ExpansionOpportunityResponse(
            state_id=opp["state"].id,
            state_code=opp["state_code"],
            state_name=opp["state_name"],
            total_cost=opp["total_cost"],
            base_cost=opp["base_cost"],
            market_adjusted_cost=opp["market_adjusted_cost"],
            distance_cost=opp["distance_cost"],
            discounts=opp["discounts"],
            discount_amount=opp["discount_amount"],
            is_home_state=opp["is_home_state"],
            is_adjacent=opp["is_adjacent"],
            approval_weeks=opp["approval_weeks"],
            regulatory_category=opp["regulatory_category"],
            distance_miles=opp["distance_miles"]
        )
        for opp in opportunities
    ]


@router.get("/cost/{state_code}", response_model=ExpansionCostResponse)
async def calculate_expansion_cost(
    state_code: str,
    company: Company = Depends(get_current_company),
    config: dict = Depends(get_expansion_config),
    db: AsyncSession = Depends(get_db)
) -> ExpansionCostResponse:
    """Calculate the cost to expand into a specific state.
    
    Returns detailed cost breakdown including discounts and approval time.
    """
    # Get target state
    result = await db.execute(
        select(State).where(State.code == state_code.upper())
    )
    target_state = result.scalar_one_or_none()
    
    if not target_state:
        raise HTTPException(status_code=404, detail=f"State '{state_code}' not found")
    
    calculator = ExpansionCalculator(config)
    cost_details = await calculator.calculate_expansion_cost(db, company, target_state)
    
    return ExpansionCostResponse(
        state_code=target_state.code,
        state_name=target_state.name,
        **cost_details
    )


@router.post("/request", response_model=ExpansionRequestResponse)
async def request_expansion(
    request: ExpansionRequestBody,
    company: Company = Depends(get_current_company),
    config: dict = Depends(get_expansion_config),
    db: AsyncSession = Depends(get_db)
) -> ExpansionRequestResponse:
    """Request expansion to one or more states.
    
    Processes payment and creates authorization records.
    Home state expansions are approved immediately.
    """
    # Get current turn from database
    from core.models.turn import Turn
    result = await db.execute(
        select(Turn).where(
            Turn.semester_id == company.semester_id,
            Turn.status == "active"
        ).order_by(Turn.turn_number.desc())
    )
    current_turn = result.scalar_one_or_none()
    
    if not current_turn:
        raise HTTPException(
            status_code=400,
            detail="No active turn found. Please wait for turn processing."
        )
    
    turn_id = current_turn.id
    
    # Get target states
    states = []
    for code in request.state_codes:
        result = await db.execute(
            select(State).where(State.code == code.upper())
        )
        state = result.scalar_one_or_none()
        if not state:
            raise HTTPException(status_code=404, detail=f"State '{code}' not found")
        states.append(state)
    
    # Initialize services
    calculator = ExpansionCalculator(config)
    workflow = ApprovalWorkflow(calculator)
    
    # Process each expansion request
    authorizations = []
    total_cost = Decimal("0")
    
    try:
        for state in states:
            auth, cost_details = await workflow.request_expansion(
                db, company, state, turn_id
            )
            authorizations.append({
                "state_code": state.code,
                "state_name": state.name,
                "status": auth.status,
                "cost": cost_details["total_cost"],
                "approval_weeks": cost_details["approval_weeks"],
                "is_home_state": cost_details["is_home_state"]
            })
            total_cost += cost_details["total_cost"]
        
        await db.commit()
        
        return ExpansionRequestResponse(
            authorizations=authorizations,
            total_cost=total_cost,
            remaining_capital=company.current_capital
        )
        
    except (ValueError, RuntimeError) as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pending", response_model=List[PendingExpansionResponse])
async def get_pending_expansions(
    company: Company = Depends(get_current_company),
    config: dict = Depends(get_expansion_config),
    db: AsyncSession = Depends(get_db)
) -> List[PendingExpansionResponse]:
    """Get all pending expansion requests for the company."""
    calculator = ExpansionCalculator(config)
    workflow = ApprovalWorkflow(calculator)
    
    pending = await workflow.get_pending_expansions(db, company.id)
    
    return [
        PendingExpansionResponse(**exp)
        for exp in pending
    ]


@router.get("/authorized", response_model=List[AuthorizedStateResponse])
async def get_authorized_states(
    company: Company = Depends(get_current_company),
    config: dict = Depends(get_expansion_config),
    db: AsyncSession = Depends(get_db)
) -> List[AuthorizedStateResponse]:
    """Get all states the company is authorized to operate in."""
    calculator = ExpansionCalculator(config)
    workflow = ApprovalWorkflow(calculator)
    
    states = await workflow.get_authorized_states(db, company.id)
    
    # Get authorization details
    responses = []
    for state in states:
        # Get authorization record
        result = await db.execute(
            select(CompanyStateAuthorization)
            .where(
                CompanyStateAuthorization.company_id == company.id,
                CompanyStateAuthorization.state_id == state.id,
                CompanyStateAuthorization.status == "approved"
            )
        )
        auth = result.scalar_one()
        
        responses.append(AuthorizedStateResponse(
            state_id=state.id,
            state_code=state.code,
            state_name=state.name,
            authorization_date=str(auth.approval_date),
            compliance_score=auth.compliance_score or "excellent",
            is_home_state=auth.is_home_state
        ))
    
    return responses


@router.get("/distance/{state1}/{state2}")
async def calculate_distance(
    state1: str,
    state2: str
) -> dict:
    """Calculate distance between two states.
    
    Returns distance in miles between state geographic centers.
    """
    try:
        distance = ExpansionCalculator.calculate_distance(
            state1.upper(), 
            state2.upper()
        )
        return {
            "state1": state1.upper(),
            "state2": state2.upper(),
            "distance_miles": round(distance, 2)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) 