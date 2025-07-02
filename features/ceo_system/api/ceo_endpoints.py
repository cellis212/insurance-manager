"""CEO System API endpoints for character creation and management."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models.company import Company
from core.models.user import User
from features.ceo_system.services.ceo_creation import CEOCreationService
from features.ceo_system.services.employee_hiring import EmployeeHiringService


router = APIRouter(prefix="/api/v1/ceo", tags=["CEO System"])


# Request/Response models
class AcademicBackgroundResponse(BaseModel):
    """Academic background option for CEO creation."""
    code: str
    name: str
    description: str
    bonuses: Dict[str, int]


class UniversitySearchResponse(BaseModel):
    """University search result."""
    name: str
    city: str
    state: str
    has_rmi_program: bool
    enrollment: int | None
    aliases: List[str] | None = Field(default_factory=list)


class CreateCEORequest(BaseModel):
    """Request to create a new CEO."""
    name: str = Field(..., min_length=1, max_length=255)
    academic_background: str = Field(..., description="Academic background code")
    alma_mater: str = Field(..., description="University name")


class CEOAttributesResponse(BaseModel):
    """CEO attributes and stats."""
    id: str
    name: str
    age: float
    company_id: str
    attributes: Dict[str, int]
    achievements: List[Dict[str, Any]]
    lifetime_profit: float
    quarters_led: int
    years_until_retirement: int


class EmployeeCandidateResponse(BaseModel):
    """Available employee candidate."""
    name: str
    position: str
    skill_level: int
    base_salary: float
    special_bonus: str | None
    personality: Dict[str, str]
    background: Dict[str, Any]
    availability_expires: int


class HireEmployeeRequest(BaseModel):
    """Request to hire an employee."""
    candidate_name: str
    position: str


@router.get("/academic-backgrounds", response_model=List[AcademicBackgroundResponse])
async def get_academic_backgrounds():
    """Get available academic backgrounds for CEO creation."""
    service = CEOCreationService()
    
    backgrounds = []
    for code, data in service.ACADEMIC_BACKGROUNDS.items():
        backgrounds.append(AcademicBackgroundResponse(
            code=code,
            name=data["name"],
            description=data["description"],
            bonuses=data["bonuses"]
        ))
    
    return backgrounds


@router.get("/universities/search", response_model=List[UniversitySearchResponse])
async def search_universities(
    query: str,
    state: str | None = None,
    has_rmi: bool | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Search for universities by name, state, or RMI program availability.
    
    Args:
        query: Search string (partial match on name or aliases)
        state: Filter by state code (e.g., 'GA')
        has_rmi: Filter by RMI program availability
        limit: Maximum results to return
    """
    from features.ceo_system.models.university import University
    from core.models.state import State
    
    # Build query
    stmt = select(University).join(State)
    
    # Apply filters
    if query:
        # Search in name and aliases
        search_pattern = f"%{query}%"
        stmt = stmt.where(
            (University.name.ilike(search_pattern)) |
            (University.aliases.ilike(search_pattern))
        )
    
    if state:
        stmt = stmt.where(State.code == state.upper())
    
    if has_rmi is not None:
        stmt = stmt.where(University.has_rmi_program == has_rmi)
    
    # Order by enrollment (larger universities first) and limit
    stmt = stmt.order_by(University.enrollment.desc().nullslast()).limit(limit)
    
    # Execute query
    result = await db.execute(stmt)
    universities = result.scalars().all()
    
    # Format response
    response = []
    for uni in universities:
        # Get state code through relationship
        state_result = await db.execute(
            select(State.code).where(State.id == uni.state_id)
        )
        state_code = state_result.scalar_one()
        
        response.append(UniversitySearchResponse(
            name=uni.name,
            city=uni.city,
            state=state_code,
            has_rmi_program=uni.has_rmi_program,
            enrollment=int(uni.enrollment) if uni.enrollment else None,
            aliases=uni.aliases.split(";") if uni.aliases else []
        ))
    
    return response


@router.post("/create", response_model=CEOAttributesResponse)
async def create_ceo(
    request: CreateCEORequest,
    current_user: User = Depends(get_current_user),  # You'll need to implement this
    db: AsyncSession = Depends(get_db)
):
    """Create a new CEO for the user's company.
    
    This can only be done once per company per semester.
    """
    # Get user's company
    result = await db.execute(
        select(Company).where(
            Company.user_id == current_user.id,
            Company.semester_id == current_user.semester_id
        )
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No company found for current semester"
        )
    
    # Check if CEO already exists
    if company.ceo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company already has a CEO"
        )
    
    # Create CEO
    service = CEOCreationService()
    await service.initialize({})  # Load from config in real implementation
    
    try:
        ceo = await service.create_ceo(
            session=db,
            company=company,
            name=request.name,
            academic_background=request.academic_background,
            alma_mater_name=request.alma_mater
        )
        
        await db.commit()
        
        # Format response
        return CEOAttributesResponse(
            id=str(ceo.id),
            name=ceo.name,
            age=float(ceo.age),
            company_id=str(ceo.company_id),
            attributes={
                "leadership": int(ceo.leadership),
                "risk_intelligence": int(ceo.risk_intelligence),
                "market_acumen": int(ceo.market_acumen),
                "regulatory_mastery": int(ceo.regulatory_mastery),
                "innovation_capacity": int(ceo.innovation_capacity),
                "deal_making": int(ceo.deal_making),
                "financial_expertise": int(ceo.financial_expertise),
                "crisis_command": int(ceo.crisis_command)
            },
            achievements=ceo.achievements,
            lifetime_profit=float(ceo.lifetime_profit),
            quarters_led=int(ceo.quarters_led),
            years_until_retirement=ceo.years_until_retirement
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/me", response_model=CEOAttributesResponse)
async def get_my_ceo(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the current user's CEO details."""
    # Get user's company with CEO
    result = await db.execute(
        select(Company).where(
            Company.user_id == current_user.id,
            Company.semester_id == current_user.semester_id
        )
    )
    company = result.scalar_one_or_none()
    
    if not company or not company.ceo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No CEO found for current company"
        )
    
    ceo = company.ceo
    
    return CEOAttributesResponse(
        id=str(ceo.id),
        name=ceo.name,
        age=float(ceo.age),
        company_id=str(ceo.company_id),
        attributes={
            "leadership": int(ceo.leadership),
            "risk_intelligence": int(ceo.risk_intelligence),
            "market_acumen": int(ceo.market_acumen),
            "regulatory_mastery": int(ceo.regulatory_mastery),
            "innovation_capacity": int(ceo.innovation_capacity),
            "deal_making": int(ceo.deal_making),
            "financial_expertise": int(ceo.financial_expertise),
            "crisis_command": int(ceo.crisis_command)
        },
        achievements=ceo.achievements,
        lifetime_profit=float(ceo.lifetime_profit),
        quarters_led=int(ceo.quarters_led),
        years_until_retirement=ceo.years_until_retirement
    )


@router.get("/employees", response_model=List[Dict[str, Any]])
async def get_current_employees(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get all current employees for the user's company."""
    # Get user's company
    result = await db.execute(
        select(Company).where(
            Company.user_id == current_user.id,
            Company.semester_id == current_user.semester_id
        )
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No company found for current semester"
        )
    
    # Get all employees
    from core.models.employee import Employee
    
    employees_result = await db.execute(
        select(Employee).where(
            Employee.company_id == company.id
        ).order_by(Employee.position)
    )
    employees = employees_result.scalars().all()
    
    # Format response
    return [
        {
            "id": str(emp.id),
            "name": emp.name,
            "position": emp.position,
            "skill_level": int(emp.skill_level),
            "base_salary": float(emp.base_salary),
            "bonus_paid_ytd": float(emp.bonus_paid_ytd),
            "special_bonus": emp.special_bonus,
            "hire_date": emp.hire_date,
            "quarters_employed": int(emp.quarters_employed),
            "annual_cost": float(emp.annual_cost)
        }
        for emp in employees
    ]


@router.delete("/employees/{employee_id}")
async def fire_employee(
    employee_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Fire an employee immediately.
    
    Note: This is different from submitting a fire decision for turn processing.
    This endpoint immediately removes the employee.
    """
    # Get user's company
    result = await db.execute(
        select(Company).where(
            Company.user_id == current_user.id,
            Company.semester_id == current_user.semester_id
        )
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No company found for current semester"
        )
    
    # Get the employee
    from core.models.employee import Employee
    from uuid import UUID
    
    try:
        emp_uuid = UUID(employee_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid employee ID"
        )
    
    employee = await db.get(Employee, emp_uuid)
    
    if not employee or employee.company_id != company.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    # Delete the employee
    await db.delete(employee)
    await db.commit()
    
    return {
        "success": True,
        "message": f"Employee {employee.name} ({employee.position}) has been terminated"
    }


@router.get("/hiring-pool", response_model=Dict[str, List[EmployeeCandidateResponse]])
async def get_hiring_pool(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the current week's available employee candidates."""
    # Get current turn number (simplified - in real implementation, get from Turn table)
    current_turn = 1  # TODO: Get actual turn number
    
    # Generate hiring pool
    service = EmployeeHiringService()
    await service.initialize({})  # Load from config
    
    hiring_pool = await service.generate_weekly_hiring_pool(
        session=db,
        semester_id=str(current_user.semester_id),
        turn_number=current_turn
    )
    
    # Format response
    response = {}
    for position, candidates in hiring_pool.items():
        response[position] = [
            EmployeeCandidateResponse(
                name=c["name"],
                position=c["position"],
                skill_level=c["skill_level"],
                base_salary=c["base_salary"],
                special_bonus=c["special_bonus"],
                personality=c["personality"],
                background=c["background"],
                availability_expires=c["availability_expires"]
            )
            for c in candidates
        ]
    
    return response


@router.post("/hire-employee")
async def hire_employee(
    request: HireEmployeeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Hire an employee from the current hiring pool."""
    # Get user's company
    result = await db.execute(
        select(Company).where(
            Company.user_id == current_user.id,
            Company.semester_id == current_user.semester_id
        )
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No company found for current semester"
        )
    
    # Check if position is already filled
    from core.models.employee import Employee
    
    existing = await db.execute(
        select(Employee).where(
            Employee.company_id == company.id,
            Employee.position == request.position
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Position {request.position} is already filled"
        )
    
    # Get current hiring pool (in real implementation, cache this)
    service = EmployeeHiringService()
    await service.initialize({})
    
    current_turn = 1  # TODO: Get actual turn
    hiring_pool = await service.generate_weekly_hiring_pool(
        session=db,
        semester_id=str(current_user.semester_id),
        turn_number=current_turn
    )
    
    # Find the candidate
    candidates = hiring_pool.get(request.position, [])
    candidate = next(
        (c for c in candidates if c["name"] == request.candidate_name),
        None
    )
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found in current hiring pool"
        )
    
    # Check if company can afford the salary
    if company.current_capital < candidate["base_salary"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient capital to hire this employee"
        )
    
    # Hire the employee
    employee = await service.hire_employee(
        session=db,
        company=company,
        candidate_data=candidate
    )
    
    await db.commit()
    
    return {
        "success": True,
        "employee": {
            "id": str(employee.id),
            "name": employee.name,
            "position": employee.position,
            "skill_level": int(employee.skill_level),
            "base_salary": float(employee.base_salary)
        }
    }


# Import real authentication from API auth utils
from api.auth_utils import get_current_active_user as get_current_user 