"""API endpoints for investment management.

Provides REST API for portfolio management, including:
- Setting portfolio preferences
- Viewing current portfolio
- Getting CFO insights
- Viewing liquidation history
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Any, Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from core.database import get_db
from core.models.company import Company
from core.models.investment_portfolio import InvestmentPortfolio
from core.models.liquidation_event import LiquidationEvent
from core.models.turn import Turn
from features.investments.services.portfolio_manager import PortfolioManager
from features.investments.services.skill_effects import InvestmentSkillEffects

# Import real authentication from API auth utils
from api.auth_utils import get_current_company


router = APIRouter(prefix="/api/v1/investments", tags=["investments"])


class PortfolioPreferences(BaseModel):
    """Portfolio characteristic preferences."""
    risk: float = Field(..., ge=0, le=100, description="Risk tolerance (0=conservative, 100=aggressive)")
    duration: float = Field(..., ge=0, le=100, description="Duration preference (0=short, 100=long)")
    liquidity: float = Field(..., ge=0, le=100, description="Liquidity need (0=illiquid OK, 100=highly liquid)")
    credit: float = Field(..., ge=0, le=100, description="Credit quality (0=AAA only, 100=high yield OK)")
    diversification: float = Field(..., ge=0, le=100, description="Diversification (0=concentrated, 100=highly diversified)")
    
    @validator('*')
    def round_to_integer(cls, v):
        """Round all values to integers."""
        return round(v)


class PortfolioResponse(BaseModel):
    """Portfolio information response."""
    total_value: float
    actual_characteristics: Dict[str, float]
    perceived_characteristics: Optional[Dict[str, float]]
    actual_returns: float
    perceived_returns: float
    information_quality: float
    cfo_skill: Optional[int]
    asset_allocation: Optional[Dict[str, float]]


class InvestmentDecisionResponse(BaseModel):
    """Response after submitting investment decision."""
    success: bool
    message: str
    expected_return: Optional[float]
    portfolio_risk: Optional[float]
    sharpe_ratio: Optional[float]
    optimization_notes: Optional[str]


class LiquidationEventResponse(BaseModel):
    """Liquidation event details."""
    id: UUID
    trigger_type: str
    required_amount: float
    total_cost: float
    liquidation_efficiency: float
    cfo_skill_at_time: Optional[int]
    assets_sold: List[Dict[str, Any]]
    created_at: str


class CFOInsightResponse(BaseModel):
    """CFO investment insights."""
    skill_category: str
    confidence_level: str
    analysis_depth: str
    insights: List[str]
    risks_identified: List[str]
    recommendations: Optional[List[str]]
    performance_assessment: Optional[str]


@router.post("/preferences", response_model=InvestmentDecisionResponse)
async def set_portfolio_preferences(
    preferences: PortfolioPreferences,
    session: AsyncSession = Depends(get_db),
    company: Company = Depends(get_current_company)
) -> InvestmentDecisionResponse:
    """Set portfolio characteristic preferences.
    
    Submit your desired portfolio characteristics using five sliders:
    - Risk: How much volatility you're willing to accept
    - Duration: Average time horizon of investments
    - Liquidity: How quickly you need to access funds
    - Credit: Quality of credit investments
    - Diversification: How spread out investments should be
    """
    # Get current turn
    stmt = select(Turn).where(
        Turn.semester_id == company.semester_id,
        Turn.status == 'active'
    ).order_by(Turn.turn_number.desc()).limit(1)
    result = await session.execute(stmt)
    current_turn = result.scalar_one_or_none()
    
    if not current_turn:
        raise HTTPException(
            status_code=400,
            detail="No active turn found"
        )
    
    # Initialize portfolio manager
    # TODO: Get config from proper source
    config = {
        'investment_parameters': {
            'min_investment_amount': 1000000
        }
    }
    portfolio_manager = PortfolioManager(config)
    
    try:
        # Create portfolio decision
        decision = await portfolio_manager.create_portfolio_decision(
            session,
            company.id,
            current_turn.id,
            preferences.dict()
        )
        
        await session.commit()
        
        return InvestmentDecisionResponse(
            success=True,
            message="Portfolio preferences set successfully",
            expected_return=decision['expected_return'],
            portfolio_risk=decision['portfolio_risk'],
            sharpe_ratio=decision['sharpe_ratio'],
            optimization_notes="Optimized within regulatory constraints" if decision['optimization_success'] else "Used fallback allocation"
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.get("/portfolio", response_model=Optional[PortfolioResponse])
async def get_current_portfolio(
    session: AsyncSession = Depends(get_db),
    company: Company = Depends(get_current_company)
) -> Optional[PortfolioResponse]:
    """Get current portfolio status.
    
    Returns both actual and perceived characteristics based on CFO skill.
    """
    # Get latest portfolio
    stmt = select(InvestmentPortfolio).where(
        InvestmentPortfolio.company_id == company.id
    ).order_by(InvestmentPortfolio.created_at.desc()).limit(1)
    
    result = await session.execute(stmt)
    portfolio = result.scalar_one_or_none()
    
    if not portfolio:
        return None
    
    # Get CFO skill
    from core.models.employee import Employee
    cfo_stmt = select(Employee).where(
        Employee.company_id == company.id,
        Employee.position == "CFO"
    )
    cfo_result = await session.execute(cfo_stmt)
    cfo = cfo_result.scalar_one_or_none()
    
    # Calculate information quality
    info_quality = 0.0
    if portfolio.perceived_characteristics:
        errors = []
        for char in ['risk', 'duration', 'liquidity', 'credit', 'diversification']:
            if char in portfolio.characteristics and char in portfolio.perceived_characteristics:
                error = abs(portfolio.characteristics[char] - portfolio.perceived_characteristics[char])
                errors.append(error)
        if errors:
            info_quality = 1 - (sum(errors) / len(errors) / 100)
    
    return PortfolioResponse(
        total_value=float(portfolio.total_value),
        actual_characteristics=portfolio.characteristics,
        perceived_characteristics=portfolio.perceived_characteristics,
        actual_returns=float(portfolio.actual_returns),
        perceived_returns=float(portfolio.perceived_returns),
        information_quality=info_quality,
        cfo_skill=int(cfo.skill_level) if cfo else None,
        asset_allocation=None  # TODO: Add if needed
    )


@router.get("/insights", response_model=CFOInsightResponse)
async def get_cfo_insights(
    session: AsyncSession = Depends(get_db),
    company: Company = Depends(get_current_company)
) -> CFOInsightResponse:
    """Get CFO insights on current portfolio.
    
    Quality of insights depends on CFO skill level.
    """
    # Get CFO
    from core.models.employee import Employee
    cfo_stmt = select(Employee).where(
        Employee.company_id == company.id,
        Employee.position == "CFO"
    )
    cfo_result = await session.execute(cfo_stmt)
    cfo = cfo_result.scalar_one_or_none()
    
    if not cfo:
        raise HTTPException(
            status_code=400,
            detail="No CFO hired"
        )
    
    # Get latest portfolio
    portfolio = await _get_latest_portfolio(session, company.id)
    
    if not portfolio:
        # Default insights without portfolio
        return CFOInsightResponse(
            skill_category="unknown",
            confidence_level="low",
            analysis_depth="basic",
            insights=["No investment portfolio established"],
            risks_identified=["No portfolio to analyze"],
            recommendations=["Consider establishing an investment portfolio"],
            performance_assessment=None
        )
    
    # Initialize skill effects service
    config = {}  # TODO: Get proper config
    skill_effects = InvestmentSkillEffects(config)
    
    # Prepare portfolio data
    portfolio_data = {
        'expected_return': 0.05,  # TODO: Calculate from characteristics
        'portfolio_risk': 0.1,
    }
    
    # Generate insights
    insights = skill_effects.generate_investment_insights(
        portfolio_data,
        int(cfo.skill_level)
    )
    
    return CFOInsightResponse(
        skill_category=insights['skill_category'],
        confidence_level=insights['confidence_level'],
        analysis_depth=insights.get('analysis', 'basic'),
        insights=insights.get('insights', []),
        risks_identified=insights.get('risks_identified', []),
        recommendations=insights.get('recommendations'),
        performance_assessment=insights.get('performance_assessment')
    )


@router.get("/liquidations", response_model=List[LiquidationEventResponse])
async def get_liquidation_history(
    limit: int = 10,
    session: AsyncSession = Depends(get_db),
    company: Company = Depends(get_current_company)
) -> List[LiquidationEventResponse]:
    """Get history of forced liquidations.
    
    Shows when and why assets were liquidated, and the cost.
    """
    stmt = select(LiquidationEvent).where(
        LiquidationEvent.company_id == company.id
    ).order_by(LiquidationEvent.created_at.desc()).limit(limit)
    
    result = await session.execute(stmt)
    events = result.scalars().all()
    
    return [
        LiquidationEventResponse(
            id=event.id,
            trigger_type=event.trigger_type,
            required_amount=float(event.required_amount),
            total_cost=float(event.total_cost),
            liquidation_efficiency=float(event.liquidation_efficiency),
            cfo_skill_at_time=event.cfo_skill_at_time,
            assets_sold=event.assets_liquidated if isinstance(event.assets_liquidated, list) else [],
            created_at=event.created_at.isoformat()
        )
        for event in events
    ]


@router.get("/constraints", response_model=Dict[str, Any])
async def get_investment_constraints(
    session: AsyncSession = Depends(get_db),
    company: Company = Depends(get_current_company)
) -> Dict[str, Any]:
    """Get current investment constraints based on company state.
    
    Returns regulatory and solvency-based constraints.
    """
    constraints = {
        'min_investment_amount': 1000000,
        'max_investment_percentage': 0.8,  # Max 80% of capital
        'regulatory_constraints': {
            'max_risk': 70,
            'min_liquidity': 30,
            'max_credit_risk': 50
        }
    }
    
    # Adjust for low solvency
    if company.solvency_ratio and company.solvency_ratio < Decimal("1.5"):
        constraints['solvency_adjustments'] = {
            'min_liquidity': 50,
            'max_risk': 60,
            'reason': 'Low solvency ratio requires higher liquidity'
        }
    
    # Adjust for small companies
    auth_count = len(company.state_authorizations)
    if auth_count < 5:
        constraints['size_adjustments'] = {
            'max_duration': 70,
            'min_diversification': 30,
            'reason': f'Small company ({auth_count} states) should avoid complexity'
        }
    
    return constraints


async def _get_latest_portfolio(
    session: AsyncSession,
    company_id: UUID
) -> Optional[InvestmentPortfolio]:
    """Get company's latest portfolio.
    
    Args:
        session: Database session
        company_id: Company ID
        
    Returns:
        Latest portfolio or None
    """
    stmt = select(InvestmentPortfolio).where(
        InvestmentPortfolio.company_id == company_id
    ).order_by(InvestmentPortfolio.created_at.desc()).limit(1)
    
    result = await session.execute(stmt)
    return result.scalar_one_or_none() 