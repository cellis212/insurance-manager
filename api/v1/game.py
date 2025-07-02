"""Core game flow API endpoints.

Handles the main game loop including:
- Company creation
- Turn decision submission
- Results retrieval
- Game status and dashboard
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth_utils import get_current_active_user, get_current_company
from core.database import get_async_db
from core.models import (
    User, Company, Semester, Turn, CompanyTurnDecision, 
    CompanyTurnResult, CEO, Employee, Product,
    CompanyStateAuthorization, CompanyLineOfBusiness
)
from features.ceo_system.services.ceo_creation import CEOCreationService

router = APIRouter(prefix="/api/v1/game", tags=["game"])


# Request/Response Models
class CreateCompanyRequest(BaseModel):
    """Request to create a new company."""
    company_name: str = Field(..., min_length=3, max_length=100)
    ceo_name: str = Field(..., min_length=2, max_length=100)
    academic_background: str = Field(..., description="Academic background code")
    alma_mater: str = Field(..., description="University name")


class CompanyResponse(BaseModel):
    """Response with company details."""
    id: UUID
    name: str
    home_state_code: str
    home_state_name: str
    current_capital: float
    solvency_ratio: float
    founded_date: str
    ceo_name: Optional[str]
    employee_count: int
    state_count: int
    product_count: int
    
    class Config:
        orm_mode = True


class TurnDecisionRequest(BaseModel):
    """Request to submit turn decisions."""
    # Expansion decisions
    expansion_requests: Optional[List[str]] = Field(default_factory=list, description="State codes to expand to")
    
    # Product decisions
    new_products: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    tier_switches: Optional[Dict[UUID, str]] = Field(default_factory=dict, description="Product ID -> new tier")
    
    # Pricing decisions
    pricing: Optional[Dict[UUID, float]] = Field(default_factory=dict, description="Product ID -> price multiplier")
    
    # Investment decisions
    portfolio_preferences: Optional[Dict[str, float]] = Field(default=None)
    
    # Employee decisions
    hire_employees: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    fire_employees: Optional[List[UUID]] = Field(default_factory=list)


class TurnStatusResponse(BaseModel):
    """Current turn status."""
    turn_number: int
    week_number: int
    status: str
    start_date: str
    end_date: str
    decisions_submitted: bool
    time_remaining_hours: float


class DashboardResponse(BaseModel):
    """Company dashboard data."""
    company: CompanyResponse
    current_turn: Optional[TurnStatusResponse]
    financial_summary: Dict[str, float]
    recent_events: List[Dict[str, Any]]
    compliance_score: Optional[float]
    market_position: Dict[str, Any]


class TurnResultsResponse(BaseModel):
    """Turn results data."""
    turn_id: UUID
    turn_number: int
    financial_results: Dict[str, float]
    market_results: Dict[str, Any]
    operational_results: Dict[str, Any]
    regulatory_results: Optional[Dict[str, Any]]
    special_events: List[Dict[str, Any]]


@router.post("/create-company", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    request: CreateCompanyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
) -> CompanyResponse:
    """Create a new company with CEO for the current semester.
    
    This initializes:
    - Company with starting capital
    - CEO with attributes based on academic background
    - Home state based on alma mater location
    - Initial state authorization
    """
    # Check if user already has a company this semester
    existing = await db.execute(
        select(Company).where(
            Company.user_id == current_user.id,
            Company.semester_id == current_user.semester_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a company for this semester"
        )
    
    # Get current semester
    semester = await db.get(Semester, current_user.semester_id)
    if not semester:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active semester found"
        )
    
    # Create CEO service
    ceo_service = CEOCreationService()
    await ceo_service.initialize(semester.configuration.parameters)
    
    # Create company
    company = Company(
        user_id=current_user.id,
        semester_id=current_user.semester_id,
        name=request.company_name,
        founded_date=datetime.utcnow().date(),
        current_capital=Decimal("5000000"),  # Starting capital from config
        solvency_ratio=Decimal("3.0"),
        market_position={},
        operational_data={}
    )
    db.add(company)
    await db.flush()  # Get company ID
    
    # Create CEO
    try:
        ceo = await ceo_service.create_ceo(
            session=db,
            company=company,
            name=request.ceo_name,
            academic_background=request.academic_background,
            alma_mater_name=request.alma_mater
        )
        
        # The service sets the home state, so refresh company
        await db.refresh(company)
        
        await db.commit()
        
        # Get state name
        from core.models.state import State
        state = await db.get(State, company.home_state_id)
        
        return CompanyResponse(
            id=company.id,
            name=company.name,
            home_state_code=state.code,
            home_state_name=state.name,
            current_capital=float(company.current_capital),
            solvency_ratio=float(company.solvency_ratio),
            founded_date=str(company.founded_date),
            ceo_name=ceo.name,
            employee_count=0,  # Just CEO initially
            state_count=1,  # Home state
            product_count=0
        )
        
    except ValueError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/company", response_model=CompanyResponse)
async def get_company_details(
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_async_db)
) -> CompanyResponse:
    """Get current company details."""
    # Get CEO name
    ceo = await db.get(CEO, company.id)
    ceo_name = ceo.name if ceo else None
    
    # Count employees
    employee_count_result = await db.execute(
        select(Employee).where(
            Employee.company_id == company.id,
            Employee.termination_date.is_(None)
        )
    )
    employee_count = len(employee_count_result.scalars().all())
    
    # Count authorized states
    state_count_result = await db.execute(
        select(CompanyStateAuthorization).where(
            CompanyStateAuthorization.company_id == company.id,
            CompanyStateAuthorization.status == "approved"
        )
    )
    state_count = len(state_count_result.scalars().all())
    
    # Count active products
    product_count_result = await db.execute(
        select(Product).where(
            Product.company_id == company.id,
            Product.is_active == True
        )
    )
    product_count = len(product_count_result.scalars().all())
    
    # Get home state
    from core.models.state import State
    state = await db.get(State, company.home_state_id)
    
    return CompanyResponse(
        id=company.id,
        name=company.name,
        home_state_code=state.code,
        home_state_name=state.name,
        current_capital=float(company.current_capital),
        solvency_ratio=float(company.solvency_ratio or 0),
        founded_date=str(company.founded_date),
        ceo_name=ceo_name,
        employee_count=employee_count + (1 if ceo else 0),  # Include CEO
        state_count=state_count,
        product_count=product_count
    )


@router.get("/current-turn", response_model=TurnStatusResponse)
async def get_current_turn_status(
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_async_db)
) -> TurnStatusResponse:
    """Get current turn status and timing information."""
    # Get active turn
    result = await db.execute(
        select(Turn).where(
            Turn.semester_id == company.semester_id,
            Turn.status == "active"
        ).order_by(Turn.turn_number.desc())
    )
    current_turn = result.scalar_one_or_none()
    
    if not current_turn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active turn found"
        )
    
    # Check if decisions submitted
    decision_result = await db.execute(
        select(CompanyTurnDecision).where(
            CompanyTurnDecision.company_id == company.id,
            CompanyTurnDecision.turn_id == current_turn.id
        )
    )
    decisions_submitted = decision_result.scalar_one_or_none() is not None
    
    # Calculate time remaining
    time_remaining = (current_turn.end_date - datetime.utcnow()).total_seconds() / 3600
    
    return TurnStatusResponse(
        turn_number=current_turn.turn_number,
        week_number=current_turn.week_number,
        status=current_turn.status,
        start_date=current_turn.start_date.isoformat(),
        end_date=current_turn.end_date.isoformat(),
        decisions_submitted=decisions_submitted,
        time_remaining_hours=max(0, time_remaining)
    )


@router.post("/decisions", status_code=status.HTTP_201_CREATED)
async def submit_turn_decisions(
    decisions: TurnDecisionRequest,
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Submit decisions for the current turn.
    
    All decisions are validated and stored together.
    You can submit multiple times before the deadline - latest submission wins.
    """
    # Get current turn
    result = await db.execute(
        select(Turn).where(
            Turn.semester_id == company.semester_id,
            Turn.status == "active"
        ).order_by(Turn.turn_number.desc())
    )
    current_turn = result.scalar_one_or_none()
    
    if not current_turn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active turn to submit decisions for"
        )
    
    # Check deadline
    if datetime.utcnow() > current_turn.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Turn deadline has passed"
        )
    
    # Build decision data
    decision_data = {
        "expansion": decisions.expansion_requests,
        "products": {
            "new": decisions.new_products,
            "tier_switches": {str(k): v for k, v in decisions.tier_switches.items()}
        },
        "pricing": {str(k): v for k, v in decisions.pricing.items()},
        "investments": decisions.portfolio_preferences,
        "employees": {
            "hire": decisions.hire_employees,
            "fire": [str(id) for id in decisions.fire_employees]
        }
    }
    
    # Check if decisions already exist
    existing_result = await db.execute(
        select(CompanyTurnDecision).where(
            CompanyTurnDecision.company_id == company.id,
            CompanyTurnDecision.turn_id == current_turn.id
        )
    )
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        # Update existing decisions
        existing.decisions = decision_data
        existing.validation_results = {"status": "pending_validation"}
        existing.features_used = []  # Track which features were used
    else:
        # Create new decision record
        turn_decision = CompanyTurnDecision(
            company_id=company.id,
            turn_id=current_turn.id,
            decisions=decision_data,
            validation_results={"status": "pending_validation"},
            features_used=[]
        )
        db.add(turn_decision)
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Decisions submitted successfully",
        "turn_number": current_turn.turn_number,
        "deadline": current_turn.end_date.isoformat()
    }


@router.get("/decisions/current", response_model=Dict[str, Any])
async def get_current_decisions(
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Get decisions submitted for the current turn."""
    # Get current turn
    result = await db.execute(
        select(Turn).where(
            Turn.semester_id == company.semester_id,
            Turn.status == "active"
        ).order_by(Turn.turn_number.desc())
    )
    current_turn = result.scalar_one_or_none()
    
    if not current_turn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active turn found"
        )
    
    # Get decisions
    decision_result = await db.execute(
        select(CompanyTurnDecision).where(
            CompanyTurnDecision.company_id == company.id,
            CompanyTurnDecision.turn_id == current_turn.id
        )
    )
    decision = decision_result.scalar_one_or_none()
    
    if not decision:
        return {
            "turn_number": current_turn.turn_number,
            "submitted": False,
            "decisions": None
        }
    
    return {
        "turn_number": current_turn.turn_number,
        "submitted": True,
        "submitted_at": decision.created_at.isoformat(),
        "decisions": decision.decisions,
        "validation_status": decision.validation_results.get("status", "unknown")
    }


@router.get("/results/{turn_id}", response_model=TurnResultsResponse)
async def get_turn_results(
    turn_id: UUID,
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_async_db)
) -> TurnResultsResponse:
    """Get results for a specific turn."""
    # Get turn to verify it belongs to company's semester
    turn = await db.get(Turn, turn_id)
    if not turn or turn.semester_id != company.semester_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turn not found"
        )
    
    # Get results
    result = await db.execute(
        select(CompanyTurnResult).where(
            CompanyTurnResult.company_id == company.id,
            CompanyTurnResult.turn_id == turn_id
        )
    )
    turn_result = result.scalar_one_or_none()
    
    if not turn_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Results not available for this turn yet"
        )
    
    return TurnResultsResponse(
        turn_id=turn_result.turn_id,
        turn_number=turn.turn_number,
        financial_results=turn_result.financial_results,
        market_results=turn_result.market_results,
        operational_results=turn_result.operational_results,
        regulatory_results=turn_result.regulatory_results,
        special_events=turn_result.special_events or []
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def get_company_dashboard(
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_async_db)
) -> DashboardResponse:
    """Get comprehensive dashboard data for the company."""
    # Get company details
    company_response = await get_company_details(company, db)
    
    # Get current turn status
    try:
        turn_status = await get_current_turn_status(company, db)
    except HTTPException:
        # No active turn
        turn_status = None
    
    # Get latest financial results
    financial_summary = {
        "current_capital": float(company.current_capital),
        "solvency_ratio": float(company.solvency_ratio or 0),
        "total_premiums": 0.0,
        "total_claims": 0.0,
        "combined_ratio": 0.0
    }
    
    # Get most recent results if available
    if turn_status:
        result = await db.execute(
            select(CompanyTurnResult).where(
                CompanyTurnResult.company_id == company.id
            ).order_by(CompanyTurnResult.created_at.desc()).limit(1)
        )
        latest_result = result.scalar_one_or_none()
        
        if latest_result:
            financial_summary.update({
                "total_premiums": latest_result.financial_results.get("total_premiums", 0),
                "total_claims": latest_result.financial_results.get("total_claims", 0),
                "combined_ratio": latest_result.financial_results.get("combined_ratio", 0)
            })
    
    # Get recent events
    from core.models.game_event import GameEvent
    event_result = await db.execute(
        select(GameEvent).where(
            GameEvent.company_id == company.id
        ).order_by(GameEvent.created_at.desc()).limit(10)
    )
    events = event_result.scalars().all()
    
    recent_events = [
        {
            "type": event.event_type,
            "category": event.category,
            "description": event.description,
            "created_at": event.created_at.isoformat()
        }
        for event in events
    ]
    
    # Get compliance score if regulatory feature is enabled
    compliance_score = None
    if company.operational_data and "compliance_score" in company.operational_data:
        compliance_score = company.operational_data["compliance_score"]
    
    # Market position placeholder
    market_position = {
        "rank": "N/A",
        "market_share": 0.0,
        "growth_rate": 0.0
    }
    
    return DashboardResponse(
        company=company_response,
        current_turn=turn_status,
        financial_summary=financial_summary,
        recent_events=recent_events,
        compliance_score=compliance_score,
        market_position=market_position
    )


@router.get("/history/results", response_model=List[Dict[str, Any]])
async def get_results_history(
    limit: int = 10,
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_async_db)
) -> List[Dict[str, Any]]:
    """Get historical turn results."""
    result = await db.execute(
        select(CompanyTurnResult, Turn).join(Turn).where(
            CompanyTurnResult.company_id == company.id
        ).order_by(Turn.turn_number.desc()).limit(limit)
    )
    
    history = []
    for turn_result, turn in result:
        history.append({
            "turn_id": str(turn.id),
            "turn_number": turn.turn_number,
            "week_number": turn.week_number,
            "premiums": turn_result.total_premiums,
            "claims": turn_result.total_claims,
            "expenses": turn_result.total_expenses,
            "profit": turn_result.total_premiums - turn_result.total_claims - turn_result.total_expenses,
            "combined_ratio": turn_result.combined_ratio,
            "capital_after": turn_result.financial_results.get("capital_after", 0)
        })
    
    return history


@router.get("/lines-of-business", response_model=List[Dict[str, Any]])
async def get_lines_of_business(
    db: AsyncSession = Depends(get_async_db)
) -> List[Dict[str, Any]]:
    """Get all available lines of business."""
    from core.models.line_of_business import LineOfBusiness
    
    result = await db.execute(
        select(LineOfBusiness).order_by(LineOfBusiness.name)
    )
    lines = result.scalars().all()
    
    return [
        {
            "id": str(line.id),
            "code": line.code,
            "name": line.name,
            "base_frequency": float(line.base_frequency),
            "base_severity": float(line.base_severity),
            "capital_requirement_multiplier": float(line.capital_requirement_multiplier)
        }
        for line in lines
    ] 