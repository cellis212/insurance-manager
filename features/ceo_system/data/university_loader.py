"""University data loader - Loads real US university data."""

import uuid
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state import State
from features.ceo_system.models.university import University
from features.ceo_system.data.university_data import UNIVERSITY_DATA


class UniversityDataLoader:
    """Loads real US university data into the database."""
    
    def __init__(self):
        """Initialize with university data."""
        self.UNIVERSITIES = UNIVERSITY_DATA
    
    async def load_universities(self, session: AsyncSession) -> int:
        """Load university data into the database.
        
        Args:
            session: Database session
            
        Returns:
            Number of universities loaded
        """
        # Get all states first
        result = await session.execute(select(State))
        states = {state.code: state for state in result.scalars().all()}
        
        loaded_count = 0
        
        for uni_data in self.UNIVERSITIES:
            # Check if university already exists
            result = await session.execute(
                select(University).where(University.name == uni_data["name"])
            )
            if result.scalar_one_or_none():
                continue  # Skip if already exists
            
            # Get state
            state = states.get(uni_data["state"])
            if not state:
                print(f"Warning: State {uni_data['state']} not found for {uni_data['name']}")
                continue
            
            # Create university
            university = University(
                id=uuid.uuid4(),
                name=uni_data["name"],
                state_id=state.id,
                city=uni_data["city"],
                institution_type="4-year",
                control=uni_data["control"],
                enrollment=uni_data.get("enrollment"),
                has_business_school=True,  # Assume all have business schools
                has_rmi_program=uni_data.get("has_rmi", False),
                aliases=uni_data.get("aliases")
            )
            
            session.add(university)
            loaded_count += 1
        
        await session.flush()
        return loaded_count
    
    async def load_academic_backgrounds(self, session: AsyncSession) -> int:
        """Load academic background configurations.
        
        Args:
            session: Database session
            
        Returns:
            Number of backgrounds loaded
        """
        from features.ceo_system.models.academic_background import AcademicBackground
        
        backgrounds = [
            {
                "code": "rmi_finance",
                "name": "Risk Management & Finance",
                "description": "Deep understanding of capital markets and risk pricing",
                "secondary_major": "Finance",
                "attribute_bonuses": {
                    "risk_intelligence": 10,
                    "financial_expertise": 10
                },
                "special_perks": ["investment_insight", "capital_markets_access"]
            },
            {
                "code": "rmi_accounting",
                "name": "Risk Management & Accounting",
                "description": "Expertise in regulatory compliance and financial reporting",
                "secondary_major": "Accounting",
                "attribute_bonuses": {
                    "regulatory_mastery": 10,
                    "financial_expertise": 10
                },
                "special_perks": ["audit_efficiency", "regulatory_relationships"]
            },
            {
                "code": "rmi_marketing",
                "name": "Risk Management & Marketing",
                "description": "Customer-focused approach to insurance products",
                "secondary_major": "Marketing",
                "attribute_bonuses": {
                    "market_acumen": 10,
                    "deal_making": 10
                },
                "special_perks": ["customer_insights", "brand_building"]
            },
            {
                "code": "rmi_analytics",
                "name": "Risk Management & Analytics",
                "description": "Data-driven decision making and technology innovation",
                "secondary_major": "Analytics",
                "attribute_bonuses": {
                    "risk_intelligence": 10,
                    "innovation_capacity": 10
                },
                "special_perks": ["predictive_modeling", "tech_integration"]
            }
        ]
        
        loaded_count = 0
        
        for bg_data in backgrounds:
            # Check if already exists
            result = await session.execute(
                select(AcademicBackground).where(AcademicBackground.code == bg_data["code"])
            )
            if result.scalar_one_or_none():
                continue
            
            background = AcademicBackground(
                id=uuid.uuid4(),
                code=bg_data["code"],
                name=bg_data["name"],
                description=bg_data["description"],
                primary_major="Risk Management & Insurance",
                secondary_major=bg_data["secondary_major"],
                attribute_bonuses=bg_data["attribute_bonuses"],
                special_perks=bg_data["special_perks"],
                is_active="true"
            )
            
            session.add(background)
            loaded_count += 1
        
        await session.flush()
        return loaded_count 