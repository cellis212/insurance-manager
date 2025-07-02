"""
API endpoints for regulatory compliance system

Provides access to:
- Compliance scores
- Audit history
- Penalty information
- Regulatory requirements by state
"""

from typing import List, Optional
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from core.database import get_db
from core.models import Company, State, GameEvent
from features.regulatory.services import ComplianceCalculator, AuditSystem


router = APIRouter(prefix="/api/v1/regulatory", tags=["regulatory"])


# Response models
class ComplianceScoreResponse(BaseModel):
    """Compliance score details"""
    overall_score: float = Field(..., description="Overall compliance score 0-100")
    component_scores: dict = Field(..., description="Individual component scores")
    violations: List[str] = Field(..., description="Current violations")
    calculated_at: datetime = Field(..., description="When score was calculated")


class AuditResponse(BaseModel):
    """Audit information"""
    audit_type: str
    state_code: str
    severity: str
    scope: List[str]
    estimated_duration_weeks: int
    potential_penalties: dict
    initiated_at: datetime


class StateRequirementsResponse(BaseModel):
    """Regulatory requirements for a state"""
    state_code: str
    state_name: str
    regulatory_category: str
    filing_frequency_days: int
    grace_period_days: int
    typical_audit_frequency: str
    expansion_requirements: dict


class CompanyRegulatoryStatusResponse(BaseModel):
    """Complete regulatory status for a company"""
    company_id: UUID
    compliance_score: Optional[ComplianceScoreResponse]
    active_audits: List[AuditResponse]
    recent_penalties: List[dict]
    grace_periods: List[dict]
    last_filings: dict


# Import real authentication from API auth utils
from api.auth_utils import get_current_company


@router.get("/compliance/score", response_model=ComplianceScoreResponse)
async def get_compliance_score(
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db)
) -> ComplianceScoreResponse:
    """Get current compliance score for the company"""
    calculator = ComplianceCalculator(db)
    
    result = await calculator.calculate_compliance_score(company)
    
    return ComplianceScoreResponse(
        overall_score=result["overall_score"],
        component_scores=result["component_scores"],
        violations=result["violations"],
        calculated_at=result["calculated_at"]
    )


@router.get("/compliance/history")
async def get_compliance_history(
    weeks: int = Query(52, description="Number of weeks to look back"),
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db)
) -> List[dict]:
    """Get compliance score history"""
    # This would need to be enhanced to store historical scores
    # For now, return current score as single data point
    calculator = ComplianceCalculator(db)
    current = await calculator.calculate_compliance_score(company)
    
    return [{
        "date": current["calculated_at"],
        "overall_score": current["overall_score"],
        "violations": current["violations"]
    }]


@router.get("/audits/current", response_model=List[AuditResponse])
async def get_current_audits(
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db)
) -> List[AuditResponse]:
    """Get currently active audits"""
    audit_system = AuditSystem(db)
    
    # Get recent audit events
    recent_audits = await audit_system.get_recent_audits(
        company.id,
        weeks_back=12  # Audits from last 3 months
    )
    
    # Transform to response format
    audits = []
    for event in recent_audits:
        audit_data = event.data.get("audit_details", {})
        audits.append(AuditResponse(
            audit_type=audit_data.get("type", "unknown"),
            state_code=audit_data.get("state_code", ""),
            severity=audit_data.get("severity", "unknown"),
            scope=audit_data.get("scope", []),
            estimated_duration_weeks=audit_data.get("estimated_duration_weeks", 0),
            potential_penalties=audit_data.get("potential_penalties", {}),
            initiated_at=event.created_at
        ))
        
    return audits


@router.get("/audits/history")
async def get_audit_history(
    weeks: int = Query(52, description="Number of weeks to look back"),
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db)
) -> List[dict]:
    """Get audit history"""
    audit_system = AuditSystem(db)
    
    audits = await audit_system.get_recent_audits(company.id, weeks_back=weeks)
    
    return [
        {
            "date": audit.created_at,
            "type": audit.data.get("audit_details", {}).get("type"),
            "state": audit.data.get("audit_details", {}).get("state_code"),
            "severity": audit.data.get("audit_details", {}).get("severity"),
            "outcome": audit.data.get("outcome", "pending")
        }
        for audit in audits
    ]


@router.get("/states/{state_code}/requirements", response_model=StateRequirementsResponse)
async def get_state_requirements(
    state_code: str,
    db: AsyncSession = Depends(get_db)
) -> StateRequirementsResponse:
    """Get regulatory requirements for a specific state"""
    # Get state info
    from sqlalchemy import select
    
    stmt = select(State).where(State.code == state_code.upper())
    result = await db.execute(stmt)
    state = result.scalar_one_or_none()
    
    if not state:
        raise HTTPException(status_code=404, detail="State not found")
        
    # Get filing requirements based on category
    filing_reqs = ComplianceCalculator.FILING_REQUIREMENTS.get(
        state.regulatory_category,
        ComplianceCalculator.FILING_REQUIREMENTS["moderate"]
    )
    
    # Determine typical audit frequency
    if state.regulatory_category == "strict":
        audit_freq = "Quarterly"
    elif state.regulatory_category == "light":
        audit_freq = "Annually"
    else:
        audit_freq = "Semi-annually"
        
    # Build expansion requirements
    expansion_reqs = {
        "base_cost": float(state.base_expansion_cost) if state.base_expansion_cost else 1000000,
        "approval_weeks": 4 if state.regulatory_category != "strict" else 6,
        "minimum_capital": 5000000 if state.regulatory_category == "strict" else 3000000,
        "required_positions": ["CEO", "CFO", "CCO", "Chief Actuary"]
    }
    
    if state.regulatory_category == "strict":
        expansion_reqs["additional_requirements"] = [
            "Detailed business plan",
            "5-year financial projections",
            "Local office requirement"
        ]
        
    return StateRequirementsResponse(
        state_code=state.code,
        state_name=state.name,
        regulatory_category=state.regulatory_category,
        filing_frequency_days=filing_reqs["frequency_days"],
        grace_period_days=filing_reqs["grace_period_days"],
        typical_audit_frequency=audit_freq,
        expansion_requirements=expansion_reqs
    )


@router.get("/status", response_model=CompanyRegulatoryStatusResponse)
async def get_regulatory_status(
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db)
) -> CompanyRegulatoryStatusResponse:
    """Get complete regulatory status for the company"""
    # Get compliance score
    calculator = ComplianceCalculator(db)
    compliance_result = await calculator.calculate_compliance_score(company)
    
    compliance_score = ComplianceScoreResponse(
        overall_score=compliance_result["overall_score"],
        component_scores=compliance_result["component_scores"],
        violations=compliance_result["violations"],
        calculated_at=compliance_result["calculated_at"]
    )
    
    # Get current audits
    audit_system = AuditSystem(db)
    recent_audits = await audit_system.get_recent_audits(company.id, weeks_back=12)
    
    active_audits = []
    for event in recent_audits:
        audit_data = event.data.get("audit_details", {})
        # Check if audit is still active (simple duration check)
        weeks_elapsed = (datetime.utcnow() - event.created_at).days / 7
        if weeks_elapsed < audit_data.get("estimated_duration_weeks", 0):
            active_audits.append(AuditResponse(
                audit_type=audit_data.get("type", "unknown"),
                state_code=audit_data.get("state_code", ""),
                severity=audit_data.get("severity", "unknown"),
                scope=audit_data.get("scope", []),
                estimated_duration_weeks=audit_data.get("estimated_duration_weeks", 0),
                potential_penalties=audit_data.get("potential_penalties", {}),
                initiated_at=event.created_at
            ))
    
    # Get recent penalties
    from sqlalchemy import select, and_
    from datetime import timedelta
    
    penalty_stmt = select(GameEvent).where(
        and_(
            GameEvent.company_id == company.id,
            GameEvent.event_type == "regulatory_penalty",
            GameEvent.created_at >= datetime.utcnow() - timedelta(weeks=52)
        )
    ).order_by(GameEvent.created_at.desc()).limit(10)
    
    penalty_result = await db.execute(penalty_stmt)
    penalty_events = penalty_result.scalars().all()
    
    recent_penalties = [
        {
            "date": event.created_at,
            "amount": event.data.get("total_penalty", 0),
            "violations": event.data.get("penalties", [])
        }
        for event in penalty_events
    ]
    
    # Get active grace periods
    warning_stmt = select(GameEvent).where(
        and_(
            GameEvent.company_id == company.id,
            GameEvent.event_type == "regulatory_warning",
            GameEvent.created_at >= datetime.utcnow() - timedelta(weeks=12)
        )
    )
    
    warning_result = await db.execute(warning_stmt)
    warning_events = warning_result.scalars().all()
    
    grace_periods = []
    for event in warning_events:
        grace_expires = event.data.get("grace_expires")
        if grace_expires:
            expires_date = datetime.fromisoformat(grace_expires)
            if expires_date > datetime.utcnow():
                grace_periods.append({
                    "violation": event.data.get("violation_type"),
                    "expires": expires_date,
                    "issued": event.created_at
                })
    
    # Get last filing dates
    last_filings = company.operational_data.get("last_filings", {}) if company.operational_data else {}
    
    return CompanyRegulatoryStatusResponse(
        company_id=company.id,
        compliance_score=compliance_score,
        active_audits=active_audits,
        recent_penalties=recent_penalties,
        grace_periods=grace_periods,
        last_filings=last_filings
    )


@router.get("/penalties/estimate")
async def estimate_penalties(
    violations: List[str] = Query(..., description="List of violations to estimate"),
    company: Company = Depends(get_current_company),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Estimate potential penalties for given violations"""
    from features.regulatory.services import PenaltyEngine
    
    # Get current compliance score
    calculator = ComplianceCalculator(db)
    compliance_result = await calculator.calculate_compliance_score(company)
    
    # Calculate estimated penalties
    penalty_engine = PenaltyEngine(db)
    
    estimates = []
    for violation in violations:
        base_pct = penalty_engine.BASE_PENALTIES.get(violation, 0.01)
        base_amount = float(company.current_capital) * float(base_pct)
        
        estimates.append({
            "violation": violation,
            "base_percentage": float(base_pct) * 100,
            "estimated_amount": base_amount,
            "note": "Actual penalty may vary based on offense history and CCO skill"
        })
        
    return {
        "current_capital": float(company.current_capital),
        "compliance_score": compliance_result["overall_score"],
        "estimates": estimates,
        "total_estimated": sum(e["estimated_amount"] for e in estimates)
    } 