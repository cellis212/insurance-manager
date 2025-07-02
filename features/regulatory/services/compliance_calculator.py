"""
Compliance Score Calculation Service

Calculates compliance scores based on:
- Filing timeliness
- Capital adequacy
- Product compliance
- Employee certifications
- Operating authorization status
"""

from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import (
    Company, CompanyStateAuthorization, Employee, Product,
    CompanyTurnResult, State
)


class ComplianceCalculator:
    """Calculates regulatory compliance scores for companies"""
    
    # Score component weights
    WEIGHTS = {
        "filing_timeliness": 0.20,
        "capital_adequacy": 0.25,
        "product_compliance": 0.20,
        "employee_certifications": 0.15,
        "authorization_status": 0.20
    }
    
    # Filing requirements by state regulatory category
    FILING_REQUIREMENTS = {
        "strict": {
            "frequency_days": 30,  # Monthly filings
            "grace_period_days": 7,
            "late_penalty_per_day": 0.02  # 2% per day
        },
        "moderate": {
            "frequency_days": 90,  # Quarterly
            "grace_period_days": 14,
            "late_penalty_per_day": 0.01
        },
        "light": {
            "frequency_days": 180,  # Semi-annual
            "grace_period_days": 30,
            "late_penalty_per_day": 0.005
        }
    }
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate_compliance_score(
        self, 
        company: Company,
        as_of_date: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Calculate overall compliance score and component scores
        
        Returns dict with:
        - overall_score: 0-100
        - component_scores: dict of individual components
        - violations: list of current violations
        """
        if not as_of_date:
            as_of_date = datetime.utcnow()
            
        # Calculate each component
        filing_score = await self._calculate_filing_timeliness(company, as_of_date)
        capital_score = await self._calculate_capital_adequacy(company)
        product_score = await self._calculate_product_compliance(company)
        employee_score = await self._calculate_employee_certifications(company)
        auth_score = await self._calculate_authorization_compliance(company)
        
        # Weighted average
        component_scores = {
            "filing_timeliness": filing_score,
            "capital_adequacy": capital_score,
            "product_compliance": product_score,
            "employee_certifications": employee_score,
            "authorization_status": auth_score
        }
        
        overall_score = sum(
            score * self.WEIGHTS[component]
            for component, score in component_scores.items()
        )
        
        # Identify violations
        violations = []
        if filing_score < 50:
            violations.append("Late regulatory filings")
        if capital_score < 50:
            violations.append("Insufficient capital reserves")
        if product_score < 50:
            violations.append("Non-compliant products")
        if employee_score < 50:
            violations.append("Missing required certifications")
        if auth_score < 50:
            violations.append("Operating without authorization")
            
        return {
            "overall_score": overall_score,
            "component_scores": component_scores,
            "violations": violations,
            "calculated_at": as_of_date
        }
    
    async def _calculate_filing_timeliness(
        self, 
        company: Company,
        as_of_date: datetime
    ) -> float:
        """Calculate score based on regulatory filing timeliness"""
        # Get states where company operates
        auth_stmt = select(CompanyStateAuthorization).where(
            CompanyStateAuthorization.company_id == company.id,
            CompanyStateAuthorization.is_approved == True
        )
        result = await self.session.execute(auth_stmt)
        authorizations = result.scalars().all()
        
        if not authorizations:
            return 100.0  # No filing requirements if not operating anywhere
            
        # Check filing status for each state
        total_score = 0.0
        for auth in authorizations:
            state = await self.session.get(State, auth.state_id)
            if not state:
                continue
                
            requirements = self.FILING_REQUIREMENTS.get(
                state.regulatory_category, 
                self.FILING_REQUIREMENTS["moderate"]
            )
            
            # Check last filing (stored in operational_data JSONB)
            last_filing = company.operational_data.get("last_filings", {}).get(state.code)
            if not last_filing:
                # Never filed - worst score
                total_score += 0.0
                continue
                
            last_filing_date = datetime.fromisoformat(last_filing["date"])
            days_since_filing = (as_of_date - last_filing_date).days
            
            if days_since_filing <= requirements["frequency_days"]:
                # On time
                total_score += 100.0
            elif days_since_filing <= requirements["frequency_days"] + requirements["grace_period_days"]:
                # In grace period
                days_late = days_since_filing - requirements["frequency_days"]
                penalty = days_late * requirements["late_penalty_per_day"] * 100
                total_score += max(50.0, 100.0 - penalty)
            else:
                # Beyond grace period
                days_late = days_since_filing - requirements["frequency_days"]
                penalty = days_late * requirements["late_penalty_per_day"] * 100
                total_score += max(0.0, 100.0 - penalty)
                
        return total_score / len(authorizations)
    
    async def _calculate_capital_adequacy(self, company: Company) -> float:
        """Calculate score based on capital reserves vs requirements"""
        # Get latest solvency ratio
        if not company.solvency_ratio:
            return 0.0  # No data means non-compliant
            
        solvency = float(company.solvency_ratio)
        
        # Score based on solvency ratio
        # 2.0+ = 100, 1.5 = 80, 1.2 = 60, 1.0 = 40, <1.0 = scaled down
        if solvency >= 2.0:
            return 100.0
        elif solvency >= 1.5:
            return 80.0 + (solvency - 1.5) * 40.0  # 80-100 range
        elif solvency >= 1.2:
            return 60.0 + (solvency - 1.2) * 66.67  # 60-80 range
        elif solvency >= 1.0:
            return 40.0 + (solvency - 1.0) * 100.0  # 40-60 range
        else:
            return max(0.0, solvency * 40.0)  # 0-40 range
    
    async def _calculate_product_compliance(self, company: Company) -> float:
        """Calculate score based on product regulatory compliance"""
        # Get all active products
        prod_stmt = select(Product).where(
            Product.company_id == company.id,
            Product.is_active == True
        )
        result = await self.session.execute(prod_stmt)
        products = result.scalars().all()
        
        if not products:
            return 100.0  # No products means no violations
            
        # Check each product for compliance issues
        total_score = 0.0
        for product in products:
            product_score = 100.0
            
            # Check if product is approved in its state
            auth_stmt = select(CompanyStateAuthorization).where(
                CompanyStateAuthorization.company_id == company.id,
                CompanyStateAuthorization.state_id == product.state_id,
                CompanyStateAuthorization.is_approved == True
            )
            result = await self.session.execute(auth_stmt)
            auth = result.scalar_one_or_none()
            
            if not auth:
                # Product in unauthorized state - major violation
                product_score = 0.0
            else:
                # Check product-specific compliance (rates, forms, etc)
                compliance_data = product.custom_config.get("compliance", {})
                
                # Rate filing status
                if not compliance_data.get("rates_approved", False):
                    product_score -= 30.0
                    
                # Form filing status
                if not compliance_data.get("forms_approved", False):
                    product_score -= 20.0
                    
                # Last review date
                last_review = compliance_data.get("last_review_date")
                if last_review:
                    days_since_review = (datetime.utcnow() - datetime.fromisoformat(last_review)).days
                    if days_since_review > 365:  # Annual review required
                        product_score -= 10.0
                        
            total_score += max(0.0, product_score)
            
        return total_score / len(products)
    
    async def _calculate_employee_certifications(self, company: Company) -> float:
        """Calculate score based on required employee certifications"""
        # Get all employees
        emp_stmt = select(Employee).where(
            Employee.company_id == company.id,
            Employee.is_active == True
        )
        result = await self.session.execute(emp_stmt)
        employees = result.scalars().all()
        
        # Check CCO specifically (most important for compliance)
        cco = next((e for e in employees if e.position == "CCO"), None)
        
        if not cco:
            # No CCO is a major compliance issue
            return 20.0
            
        # Base score on CCO skill level
        # Skill 80+ = 100, 60-79 = 80, 40-59 = 60, 20-39 = 40, <20 = 20
        cco_skill = cco.skill_level
        if cco_skill >= 80:
            base_score = 100.0
        elif cco_skill >= 60:
            base_score = 80.0
        elif cco_skill >= 40:
            base_score = 60.0
        elif cco_skill >= 20:
            base_score = 40.0
        else:
            base_score = 20.0
            
        # Additional penalties for missing other key positions
        key_positions = ["CEO", "CUO", "CFO", "Chief Actuary"]
        filled_positions = {e.position for e in employees}
        missing_positions = set(key_positions) - filled_positions
        
        # Deduct 5 points per missing key position
        penalty = len(missing_positions) * 5.0
        
        return max(0.0, base_score - penalty)
    
    async def _calculate_authorization_compliance(self, company: Company) -> float:
        """Calculate score based on operating with proper authorizations"""
        # Check if company has any products in unauthorized states
        prod_stmt = select(Product).where(
            Product.company_id == company.id,
            Product.is_active == True
        )
        result = await self.session.execute(prod_stmt)
        products = result.scalars().all()
        
        if not products:
            return 100.0  # Not operating anywhere
            
        # Get all authorized states
        auth_stmt = select(CompanyStateAuthorization.state_id).where(
            CompanyStateAuthorization.company_id == company.id,
            CompanyStateAuthorization.is_approved == True
        )
        result = await self.session.execute(auth_stmt)
        authorized_states = set(result.scalars().all())
        
        # Check each product
        violations = 0
        for product in products:
            if product.state_id not in authorized_states:
                violations += 1
                
        # Score decreases with violations
        if violations == 0:
            return 100.0
        elif violations == 1:
            return 50.0  # One violation is serious
        else:
            # Multiple violations - severe penalty
            return max(0.0, 50.0 - (violations - 1) * 25.0) 