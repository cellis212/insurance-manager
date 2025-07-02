"""
Regulatory Audit System

Manages random audits based on compliance scores:
- Higher compliance scores = lower audit probability
- CCO skill significantly affects audit frequency
- State regulatory category affects audit severity
- Track audit history and outcomes
"""

import random
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import (
    Company, Employee, State, CompanyStateAuthorization,
    GameEvent, AuditLog
)


class AuditSystem:
    """Manages regulatory audits and investigations"""
    
    # Base audit probabilities by compliance score range
    AUDIT_PROBABILITIES = {
        (90, 100): 0.02,   # 2% chance for excellent compliance
        (80, 89): 0.05,    # 5% chance for good compliance
        (70, 79): 0.10,    # 10% chance for average compliance
        (60, 69): 0.20,    # 20% chance for below average
        (50, 59): 0.35,    # 35% chance for poor compliance
        (0, 49): 0.50      # 50% chance for very poor compliance
    }
    
    # CCO skill impact on audit probability
    CCO_SKILL_MULTIPLIERS = {
        (80, 100): 0.3,    # Expert CCO: 70% reduction
        (60, 79): 0.6,     # Good CCO: 40% reduction
        (40, 59): 0.8,     # Average CCO: 20% reduction
        (20, 39): 1.0,     # Below average: no reduction
        (0, 19): 1.5       # Poor CCO: 50% increase
    }
    
    # State category audit severity multipliers
    STATE_SEVERITY_MULTIPLIERS = {
        "strict": 1.5,     # 50% more severe
        "moderate": 1.0,   # baseline
        "light": 0.7       # 30% less severe
    }
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def check_for_audits(
        self,
        company: Company,
        compliance_score: float,
        turn_id: UUID,
        random_seed: Optional[int] = None
    ) -> List[Dict]:
        """
        Check if company should be audited this turn
        
        Returns list of audit events (empty if no audits)
        """
        if random_seed is not None:
            random.seed(random_seed)
            
        # Get CCO skill level
        cco_skill = await self._get_cco_skill(company)
        
        # Calculate audit probability
        base_prob = self._get_base_audit_probability(compliance_score)
        cco_multiplier = self._get_cco_multiplier(cco_skill)
        final_prob = base_prob * cco_multiplier
        
        # Check if audit triggered
        if random.random() > final_prob:
            return []  # No audit this turn
            
        # Determine audit scope and severity
        audits = await self._generate_audits(company, compliance_score, turn_id)
        
        # Log audit events
        for audit in audits:
            await self._log_audit_event(company, audit, turn_id)
            
        return audits
    
    async def _get_cco_skill(self, company: Company) -> int:
        """Get CCO skill level, return 0 if no CCO"""
        emp_stmt = select(Employee).where(
            Employee.company_id == company.id,
            Employee.position == "CCO",
            Employee.is_active == True
        )
        result = await self.session.execute(emp_stmt)
        cco = result.scalar_one_or_none()
        
        return cco.skill_level if cco else 0
    
    def _get_base_audit_probability(self, compliance_score: float) -> float:
        """Get base audit probability from compliance score"""
        for (min_score, max_score), prob in self.AUDIT_PROBABILITIES.items():
            if min_score <= compliance_score <= max_score:
                return prob
        return 0.5  # Default to high probability if score out of range
    
    def _get_cco_multiplier(self, cco_skill: int) -> float:
        """Get audit probability multiplier from CCO skill"""
        for (min_skill, max_skill), multiplier in self.CCO_SKILL_MULTIPLIERS.items():
            if min_skill <= cco_skill <= max_skill:
                return multiplier
        return 1.0  # Default to no modification
    
    async def _generate_audits(
        self,
        company: Company,
        compliance_score: float,
        turn_id: UUID
    ) -> List[Dict]:
        """Generate specific audit events based on compliance issues"""
        audits = []
        
        # Get states where company operates
        auth_stmt = select(CompanyStateAuthorization).where(
            CompanyStateAuthorization.company_id == company.id,
            CompanyStateAuthorization.is_approved == True
        )
        result = await self.session.execute(auth_stmt)
        authorizations = result.scalars().all()
        
        if not authorizations:
            return []
            
        # Focus on most problematic state (random selection weighted by strictness)
        state_weights = []
        for auth in authorizations:
            state = await self.session.get(State, auth.state_id)
            if state:
                weight = self.STATE_SEVERITY_MULTIPLIERS.get(
                    state.regulatory_category, 1.0
                )
                state_weights.append((state, weight))
                
        if not state_weights:
            return []
            
        # Select audit state
        states, weights = zip(*state_weights)
        audit_state = random.choices(states, weights=weights)[0]
        
        # Determine audit type based on compliance issues
        audit_types = self._determine_audit_types(compliance_score)
        
        for audit_type in audit_types:
            audit = {
                "type": audit_type,
                "state_id": audit_state.id,
                "state_code": audit_state.code,
                "severity": self._calculate_audit_severity(
                    audit_type,
                    audit_state.regulatory_category,
                    compliance_score
                ),
                "scope": self._determine_audit_scope(audit_type),
                "estimated_duration_weeks": self._estimate_duration(audit_type),
                "potential_penalties": self._estimate_penalties(
                    audit_type,
                    audit_state.regulatory_category,
                    company.current_capital
                )
            }
            audits.append(audit)
            
        return audits
    
    def _determine_audit_types(self, compliance_score: float) -> List[str]:
        """Determine which types of audits to conduct"""
        audit_types = []
        
        # More audit types for lower compliance scores
        if compliance_score < 50:
            # Comprehensive audit for very poor compliance
            audit_types.append("comprehensive")
        elif compliance_score < 70:
            # Targeted audits for specific issues
            if random.random() < 0.6:
                audit_types.append("financial")
            if random.random() < 0.4:
                audit_types.append("market_conduct")
        else:
            # Routine audits for good compliance
            if random.random() < 0.7:
                audit_types.append("routine")
            else:
                audit_types.append("targeted")
                
        return audit_types
    
    def _calculate_audit_severity(
        self,
        audit_type: str,
        state_category: str,
        compliance_score: float
    ) -> str:
        """Calculate audit severity level"""
        base_severity = {
            "comprehensive": 3,
            "financial": 2,
            "market_conduct": 2,
            "targeted": 1,
            "routine": 0
        }.get(audit_type, 1)
        
        # Adjust for state category
        multiplier = self.STATE_SEVERITY_MULTIPLIERS.get(state_category, 1.0)
        adjusted_severity = base_severity * multiplier
        
        # Adjust for compliance score
        if compliance_score < 50:
            adjusted_severity *= 1.2
        elif compliance_score > 80:
            adjusted_severity *= 0.8
            
        # Map to severity levels
        if adjusted_severity >= 3:
            return "critical"
        elif adjusted_severity >= 2:
            return "major"
        elif adjusted_severity >= 1:
            return "moderate"
        else:
            return "minor"
    
    def _determine_audit_scope(self, audit_type: str) -> List[str]:
        """Determine what areas the audit will cover"""
        scopes = {
            "comprehensive": [
                "financial_statements",
                "regulatory_filings",
                "market_conduct",
                "claims_handling",
                "underwriting_practices",
                "investment_compliance"
            ],
            "financial": [
                "financial_statements",
                "capital_adequacy",
                "investment_compliance"
            ],
            "market_conduct": [
                "claims_handling",
                "underwriting_practices",
                "consumer_complaints"
            ],
            "targeted": [
                "regulatory_filings"
            ],
            "routine": [
                "regulatory_filings",
                "financial_statements"
            ]
        }
        return scopes.get(audit_type, ["general_review"])
    
    def _estimate_duration(self, audit_type: str) -> int:
        """Estimate audit duration in weeks"""
        durations = {
            "comprehensive": 8,
            "financial": 4,
            "market_conduct": 4,
            "targeted": 2,
            "routine": 1
        }
        return durations.get(audit_type, 2)
    
    def _estimate_penalties(
        self,
        audit_type: str,
        state_category: str,
        current_capital: Decimal
    ) -> Dict[str, Decimal]:
        """Estimate potential penalties from audit"""
        # Base penalty as percentage of capital
        base_penalties = {
            "comprehensive": Decimal("0.05"),  # 5% of capital
            "financial": Decimal("0.03"),      # 3% of capital
            "market_conduct": Decimal("0.02"), # 2% of capital
            "targeted": Decimal("0.01"),       # 1% of capital
            "routine": Decimal("0.005")        # 0.5% of capital
        }
        
        base_pct = base_penalties.get(audit_type, Decimal("0.01"))
        
        # Adjust for state category
        multiplier = Decimal(str(self.STATE_SEVERITY_MULTIPLIERS.get(state_category, 1.0)))
        adjusted_pct = base_pct * multiplier
        
        # Calculate penalty ranges
        min_penalty = current_capital * adjusted_pct * Decimal("0.5")
        max_penalty = current_capital * adjusted_pct * Decimal("2.0")
        likely_penalty = current_capital * adjusted_pct
        
        return {
            "minimum": min_penalty.quantize(Decimal("0.01")),
            "likely": likely_penalty.quantize(Decimal("0.01")),
            "maximum": max_penalty.quantize(Decimal("0.01"))
        }
    
    async def _log_audit_event(
        self,
        company: Company,
        audit: Dict,
        turn_id: UUID
    ) -> None:
        """Log audit event to game events table"""
        event = GameEvent(
            event_type="regulatory_audit",
            category="regulatory",
            severity="warning" if audit["severity"] in ["minor", "moderate"] else "error",
            company_id=company.id,
            turn_id=turn_id,
            data={
                "audit_details": audit,
                "message": f"Regulatory audit initiated in {audit['state_code']}: {audit['type']} audit",
                "expected_completion": f"{audit['estimated_duration_weeks']} weeks"
            }
        )
        self.session.add(event)
        
        # Also create audit log entry
        audit_log = AuditLog(
            entity_type="company",
            entity_id=str(company.id),
            action="audit_initiated",
            changes={
                "audit_type": audit["type"],
                "state": audit["state_code"],
                "severity": audit["severity"]
            },
            user_id=None,  # System-initiated
            turn_id=turn_id,
            additional_data=audit
        )
        self.session.add(audit_log)
        
    async def get_recent_audits(
        self,
        company_id: UUID,
        weeks_back: int = 52
    ) -> List[GameEvent]:
        """Get recent audit history for a company"""
        cutoff_date = datetime.utcnow() - timedelta(weeks=weeks_back)
        
        stmt = select(GameEvent).where(
            and_(
                GameEvent.company_id == company_id,
                GameEvent.event_type == "regulatory_audit",
                GameEvent.created_at >= cutoff_date
            )
        ).order_by(GameEvent.created_at.desc())
        
        result = await self.session.execute(stmt)
        return result.scalars().all() 