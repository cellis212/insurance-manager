"""API endpoints for market events system.

Provides endpoints for:
- Current economic phase and predictions
- Active market events
- Competitor information
- Historical economic data
"""

from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.models import (
    Company, Semester, Turn, GameEvent,
    CEO, Employee
)
from core.config import settings

router = APIRouter(prefix="/api/v1/market-events", tags=["market-events"])


@router.get("/economic-phase/{company_id}")
async def get_economic_phase(
    company_id: UUID,
    session: AsyncSession = Depends(get_session)
) -> Dict:
    """Get current economic phase and CEO insights if applicable.
    
    Args:
        company_id: Company ID to get insights for
        session: Database session
        
    Returns:
        Current economic phase and predictions based on CEO market acumen
    """
    # Get company and verify it exists
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Get current semester
    semester = await session.get(Semester, company.semester_id)
    if not semester:
        raise HTTPException(status_code=404, detail="Semester not found")
    
    # Get economic cycle data from semester config
    cycle_data = semester.configuration.parameters.get("economic_cycle", {})
    if not cycle_data:
        return {
            "current_phase": "unknown",
            "phase_duration": 0,
            "ceo_insights": None
        }
    
    response = {
        "current_phase": cycle_data.get("current_phase", "unknown"),
        "phase_duration": cycle_data.get("phase_duration", 0),
        "ceo_insights": None
    }
    
    # Check CEO market acumen for insights
    ceo = await session.get(CEO, company_id)
    if ceo and ceo.market_acumen >= 60:
        # Calculate phase transition probabilities
        # This is simplified - in production would use the actual cycle manager
        phase_transitions = {
            "expansion": {"peak": 0.15, "expansion": 0.85},
            "peak": {"contraction": 0.80, "peak": 0.20},
            "contraction": {"trough": 0.20, "contraction": 0.80},
            "trough": {"recovery": 0.70, "trough": 0.30},
            "recovery": {"expansion": 0.25, "recovery": 0.75}
        }
        
        current = response["current_phase"]
        transitions = phase_transitions.get(current, {})
        
        # Higher acumen provides better insights
        accuracy = min(1.0, ceo.market_acumen / 100)
        
        response["ceo_insights"] = {
            "market_acumen": ceo.market_acumen,
            "phase_change_probabilities": transitions,
            "insight_accuracy": accuracy,
            "recommendation": _get_phase_recommendation(current, ceo.market_acumen)
        }
    
    return response


@router.get("/active-events/{semester_id}")
async def get_active_market_events(
    semester_id: UUID,
    session: AsyncSession = Depends(get_session)
) -> Dict:
    """Get all currently active market events.
    
    Args:
        semester_id: Semester ID
        session: Database session
        
    Returns:
        List of active market events and their impacts
    """
    # Get the most recent turn
    result = await session.execute(
        select(Turn).where(
            Turn.semester_id == semester_id,
            Turn.status == "completed"
        ).order_by(Turn.week_number.desc()).limit(1)
    )
    last_turn = result.scalar_one_or_none()
    
    if not last_turn:
        return {"active_events": [], "turn_number": 0}
    
    # Get active market events from game events
    result = await session.execute(
        select(GameEvent).where(
            GameEvent.semester_id == semester_id,
            GameEvent.turn_id == last_turn.id,
            GameEvent.event_type.in_(["market_event_start", "market_events.active"])
        ).order_by(GameEvent.created_at.desc()).limit(1)
    )
    event_record = result.scalar_one_or_none()
    
    if not event_record or not event_record.event_data:
        return {"active_events": [], "turn_number": last_turn.week_number}
    
    # Extract active events
    active_events = []
    if "events" in event_record.event_data:
        # From market_events.active event
        events = event_record.event_data.get("events", [])
        impacts = event_record.event_data.get("combined_impacts", {})
        
        # Reconstruct event details (simplified)
        for event_name in events:
            active_events.append({
                "name": event_name,
                "type": _infer_event_type(event_name),
                "severity": _infer_severity(event_name),
                "impacts": impacts
            })
    
    return {
        "active_events": active_events,
        "turn_number": last_turn.week_number,
        "combined_impacts": event_record.event_data.get("combined_impacts", {})
    }


@router.get("/competitors/{semester_id}")
async def get_competitor_info(
    semester_id: UUID,
    include_details: bool = Query(False, description="Include detailed competitor information"),
    session: AsyncSession = Depends(get_session)
) -> Dict:
    """Get information about AI competitor companies.
    
    Args:
        semester_id: Semester ID
        include_details: Whether to include detailed information
        session: Database session
        
    Returns:
        List of competitor companies and their strategies
    """
    # Get AI competitor companies
    result = await session.execute(
        select(Company).where(
            Company.semester_id == semester_id,
            Company.user_id.is_(None),  # AI companies have no user
            Company.operational_data["is_ai_competitor"].astext == "true"
        )
    )
    competitors = result.scalars().all()
    
    competitor_list = []
    for comp in competitors:
        comp_info = {
            "id": str(comp.id),
            "name": comp.name,
            "strategy": comp.operational_data.get("strategy", "unknown"),
            "home_state": str(comp.home_state_id),
            "capital": float(comp.current_capital),
            "is_active": comp.current_capital > 0
        }
        
        if include_details:
            # Get CEO attributes
            ceo = await session.get(CEO, comp.id)
            if ceo:
                comp_info["ceo_attributes"] = {
                    "leadership": ceo.leadership,
                    "risk_intelligence": ceo.risk_intelligence,
                    "market_acumen": ceo.market_acumen,
                    "regulatory_mastery": ceo.regulatory_mastery
                }
            
            # Get employee count
            result = await session.execute(
                select(Employee).where(
                    Employee.company_id == comp.id,
                    Employee.termination_date.is_(None)
                )
            )
            employees = result.scalars().all()
            comp_info["employee_count"] = len(employees)
            comp_info["key_positions_filled"] = [emp.position for emp in employees]
        
        competitor_list.append(comp_info)
    
    # Sort by strategy for consistent ordering
    competitor_list.sort(key=lambda x: (x["strategy"], x["name"]))
    
    return {
        "competitors": competitor_list,
        "total_count": len(competitor_list),
        "active_count": sum(1 for c in competitor_list if c["is_active"])
    }


@router.get("/economic-history/{semester_id}")
async def get_economic_history(
    semester_id: UUID,
    limit: int = Query(52, ge=1, le=104, description="Number of weeks to retrieve"),
    session: AsyncSession = Depends(get_session)
) -> Dict:
    """Get historical economic phase data for the semester.
    
    Args:
        semester_id: Semester ID
        limit: Maximum number of weeks to retrieve
        session: Database session
        
    Returns:
        Historical economic phase transitions and impacts
    """
    # Get semester configuration
    semester = await session.get(Semester, semester_id)
    if not semester:
        raise HTTPException(status_code=404, detail="Semester not found")
    
    # Extract economic history
    cycle_data = semester.configuration.parameters.get("economic_cycle", {})
    history = cycle_data.get("history", [])
    
    # Limit history to requested number of entries
    history = history[-limit:] if len(history) > limit else history
    
    # Calculate phase statistics
    phase_counts = {}
    phase_durations = {}
    current_phase = None
    phase_start = 0
    
    for i, entry in enumerate(history):
        phase = entry["phase"]
        
        # Count phases
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
        
        # Track phase durations
        if phase != current_phase:
            if current_phase:
                duration = i - phase_start
                if current_phase not in phase_durations:
                    phase_durations[current_phase] = []
                phase_durations[current_phase].append(duration)
            current_phase = phase
            phase_start = i
    
    # Calculate average durations
    avg_durations = {
        phase: sum(durations) / len(durations) if durations else 0
        for phase, durations in phase_durations.items()
    }
    
    return {
        "history": history,
        "statistics": {
            "phase_counts": phase_counts,
            "average_durations": avg_durations,
            "total_weeks": len(history)
        },
        "current_phase": cycle_data.get("current_phase", "unknown"),
        "phase_duration": cycle_data.get("phase_duration", 0)
    }


@router.get("/event-history/{semester_id}")
async def get_event_history(
    semester_id: UUID,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(20, ge=1, le=100, description="Number of events to retrieve"),
    session: AsyncSession = Depends(get_session)
) -> Dict:
    """Get historical market events for the semester.
    
    Args:
        semester_id: Semester ID
        event_type: Optional filter by event type
        limit: Maximum number of events to retrieve
        session: Database session
        
    Returns:
        List of historical market events
    """
    # Build query
    query = select(GameEvent).where(
        GameEvent.semester_id == semester_id,
        GameEvent.category == "market"
    )
    
    if event_type:
        query = query.where(GameEvent.event_type == event_type)
    
    query = query.order_by(GameEvent.created_at.desc()).limit(limit)
    
    # Execute query
    result = await session.execute(query)
    events = result.scalars().all()
    
    # Format events
    event_list = []
    for event in events:
        event_data = {
            "id": str(event.id),
            "turn_id": str(event.turn_id) if event.turn_id else None,
            "event_type": event.event_type,
            "severity": event.severity,
            "description": event.description,
            "created_at": event.created_at.isoformat(),
            "data": event.event_data
        }
        event_list.append(event_data)
    
    return {
        "events": event_list,
        "total_count": len(event_list),
        "filter": {"event_type": event_type} if event_type else None
    }


def _get_phase_recommendation(phase: str, market_acumen: int) -> str:
    """Get strategic recommendation based on economic phase and CEO skill.
    
    Args:
        phase: Current economic phase
        market_acumen: CEO market acumen score
        
    Returns:
        Strategic recommendation text
    """
    recommendations = {
        "expansion": "Consider expansion opportunities and aggressive pricing while market conditions are favorable.",
        "peak": "Exercise caution - market peak suggests upcoming contraction. Build reserves.",
        "contraction": "Focus on efficiency and cost control. Avoid major expansions.",
        "trough": "Prepare for recovery. Consider strategic acquisitions at low valuations.",
        "recovery": "Begin moderate expansion. Market conditions improving but remain cautious."
    }
    
    base_rec = recommendations.get(phase, "Monitor market conditions closely.")
    
    if market_acumen >= 80:
        return f"Expert Insight: {base_rec} Your exceptional market acumen provides 1-2 turn advance warning."
    elif market_acumen >= 60:
        return f"Skilled Analysis: {base_rec}"
    else:
        return base_rec


def _infer_event_type(event_name: str) -> str:
    """Infer event type from event name.
    
    Args:
        event_name: Name of the event
        
    Returns:
        Inferred event type
    """
    name_lower = event_name.lower()
    
    if any(word in name_lower for word in ["hurricane", "tornado", "flood", "earthquake"]):
        return "catastrophe"
    elif any(word in name_lower for word in ["regulation", "compliance", "federal", "state"]):
        return "regulatory_change"
    elif any(word in name_lower for word in ["technology", "ai", "blockchain", "digital"]):
        return "technology_disruption"
    elif any(word in name_lower for word in ["scandal", "crisis", "fraud"]):
        return "industry_scandal"
    else:
        return "other"


def _infer_severity(event_name: str) -> float:
    """Infer event severity from event name.
    
    Args:
        event_name: Name of the event
        
    Returns:
        Inferred severity (1.0-3.0)
    """
    name_lower = event_name.lower()
    
    if any(word in name_lower for word in ["major", "severe", "catastrophic", "crisis"]):
        return 3.0
    elif any(word in name_lower for word in ["significant", "substantial"]):
        return 2.0
    else:
        return 1.5 