"""CEO Creation Service - Handles character creation workflow."""

import random
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.ceo import CEO
from core.models.company import Company
from core.models.state import State
from features.ceo_system.models.academic_background import AcademicBackground
from features.ceo_system.models.university import University


class CEOCreationService:
    """Service for creating new CEO characters with academic backgrounds."""
    
    # Academic background bonuses (RMI + second major)
    ACADEMIC_BACKGROUNDS = {
        "rmi_finance": {
            "name": "Risk Management & Finance",
            "description": "Deep understanding of capital markets and risk pricing",
            "bonuses": {
                "risk_intelligence": 10,
                "financial_expertise": 10
            }
        },
        "rmi_accounting": {
            "name": "Risk Management & Accounting", 
            "description": "Expertise in regulatory compliance and financial reporting",
            "bonuses": {
                "regulatory_mastery": 10,
                "financial_expertise": 10
            }
        },
        "rmi_marketing": {
            "name": "Risk Management & Marketing",
            "description": "Customer-focused approach to insurance products",
            "bonuses": {
                "market_acumen": 10,
                "deal_making": 10
            }
        },
        "rmi_analytics": {
            "name": "Risk Management & Analytics",
            "description": "Data-driven decision making and technology innovation",
            "bonuses": {
                "risk_intelligence": 10,
                "innovation_capacity": 10
            }
        }
    }
    
    def __init__(self):
        """Initialize the CEO creation service."""
        self.config = {}
        self._university_cache = {}
    
    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize service with configuration.
        
        Args:
            config: CEO system configuration
        """
        self.config = config
    
    async def create_ceo(
        self,
        session: AsyncSession,
        company: Company,
        name: str,
        academic_background: str,
        alma_mater_name: str,
        personality_seed: Optional[int] = None
    ) -> CEO:
        """Create a new CEO with academic background and initial attributes.
        
        Args:
            session: Database session
            company: Company the CEO will lead
            name: CEO's name
            academic_background: One of the ACADEMIC_BACKGROUNDS keys
            alma_mater_name: Name of the university attended
            personality_seed: Optional seed for consistent randomization
            
        Returns:
            Created CEO instance
            
        Raises:
            ValueError: If academic background or university is invalid
        """
        # Validate academic background
        if academic_background not in self.ACADEMIC_BACKGROUNDS:
            raise ValueError(
                f"Invalid academic background: {academic_background}. "
                f"Must be one of: {list(self.ACADEMIC_BACKGROUNDS.keys())}"
            )
        
        # Get university and home state
        university = await self._get_university(session, alma_mater_name)
        if not university:
            raise ValueError(f"University '{alma_mater_name}' not found in database")
        
        # Get home state from university
        home_state = await session.get(State, university.state_id)
        if not home_state:
            raise ValueError(f"State not found for university {alma_mater_name}")
        
        # Generate initial attributes with academic bonuses
        if personality_seed is not None:
            random.seed(personality_seed)
        
        background_data = self.ACADEMIC_BACKGROUNDS[academic_background]
        bonuses = background_data["bonuses"]
        
        # Get attribute ranges from config
        attr_ranges = self.config.get("attribute_ranges", {})
        age_range = self.config.get("starting_age_range", {"min": 35, "max": 40})
        
        # Generate base attributes (before bonuses)
        attributes = {}
        attribute_names = [
            "leadership", "risk_intelligence", "market_acumen",
            "regulatory_mastery", "innovation_capacity", "deal_making",
            "financial_expertise", "crisis_command"
        ]
        
        for attr in attribute_names:
            attr_config = attr_ranges.get(attr, {"min": 20, "max": 40})
            base_value = random.randint(attr_config["min"], attr_config["max"])
            
            # Apply academic bonus if applicable
            bonus = bonuses.get(attr, 0)
            final_value = min(100, base_value + bonus)  # Cap at 100
            
            attributes[attr] = final_value
        
        # Generate starting age
        starting_age = random.randint(age_range["min"], age_range["max"])
        
        # Create CEO instance
        ceo = CEO(
            company_id=company.id,
            name=name,
            age=Decimal(str(starting_age)),
            hired_date=date.today(),
            leadership=attributes["leadership"],
            risk_intelligence=attributes["risk_intelligence"],
            market_acumen=attributes["market_acumen"],
            regulatory_mastery=attributes["regulatory_mastery"],
            innovation_capacity=attributes["innovation_capacity"],
            deal_making=attributes["deal_making"],
            financial_expertise=attributes["financial_expertise"],
            crisis_command=attributes["crisis_command"],
            lifetime_profit=Decimal("0.00"),
            quarters_led=0,
            achievements=[],
            special_bonuses={
                "academic_background": academic_background,
                "alma_mater": alma_mater_name,
                "home_state": home_state.code,
                "personality_seed": personality_seed
            }
        )
        
        # Store academic background in achievements
        ceo.achievements.append({
            "type": "academic_background",
            "background": academic_background,
            "name": background_data["name"],
            "description": background_data["description"],
            "bonuses_applied": bonuses,
            "earned_date": date.today().isoformat()
        })
        
        # Add alma mater achievement
        ceo.achievements.append({
            "type": "alma_mater",
            "university": alma_mater_name,
            "state": home_state.code,
            "home_state_bonus": "Active",
            "earned_date": date.today().isoformat()
        })
        
        session.add(ceo)
        
        # Update company's home state if not set
        if not company.home_state_id:
            company.home_state_id = home_state.id
        
        return ceo
    
    async def _get_university(self, session: AsyncSession, name: str) -> Optional[University]:
        """Get university by name from database.
        
        Args:
            session: Database session
            name: University name
            
        Returns:
            University instance or None if not found
        """
        # Check cache first
        if name in self._university_cache:
            return self._university_cache[name]
        
        # Query database
        result = await session.execute(
            select(University).where(University.name == name)
        )
        university = result.scalar_one_or_none()
        
        if university:
            self._university_cache[name] = university
        
        return university
    
    def get_attribute_description(self, attribute: str) -> dict[str, Any]:
        """Get detailed description of a CEO attribute.
        
        Args:
            attribute: Attribute name
            
        Returns:
            Dictionary with attribute details
        """
        descriptions = {
            "leadership": {
                "name": "Leadership",
                "description": "Universal 50% boost to all employees",
                "affects": ["All employee effectiveness", "Company morale"],
                "progression": "Gained through successful quarters and company growth"
            },
            "risk_intelligence": {
                "name": "Risk Intelligence",
                "description": "Improves underwriting quality and risk selection",
                "affects": ["Chief Underwriting Officer", "Chief Actuary", "Chief Risk Officer"],
                "progression": "Improved by handling claims events and market volatility"
            },
            "market_acumen": {
                "name": "Market Acumen",
                "description": "Enhances marketing effectiveness and customer acquisition",
                "affects": ["Chief Marketing Officer", "Sales teams"],
                "progression": "Developed through market expansion and competition"
            },
            "regulatory_mastery": {
                "name": "Regulatory Mastery",
                "description": "Speeds up regulatory approvals and reduces penalties",
                "affects": ["Chief Compliance Officer", "Legal teams"],
                "progression": "Gained through regulatory interactions and state expansions"
            },
            "innovation_capacity": {
                "name": "Innovation Capacity",
                "description": "Drives technology adoption and operational efficiency",
                "affects": ["Chief Technology Officer", "R&D teams"],
                "progression": "Increased by implementing new systems and products"
            },
            "deal_making": {
                "name": "Deal Making",
                "description": "Improves M&A outcomes and partnership negotiations",
                "affects": ["Reinsurance negotiations", "Strategic partnerships"],
                "progression": "Enhanced through successful deals and negotiations"
            },
            "financial_expertise": {
                "name": "Financial Expertise",
                "description": "Boosts investment returns and capital efficiency",
                "affects": ["Chief Financial Officer", "Chief Accounting Officer"],
                "progression": "Developed through investment decisions and financial management"
            },
            "crisis_command": {
                "name": "Crisis Command",
                "description": "Activates during catastrophes for claims and PR boost",
                "affects": ["All departments during crisis", "Claims handling", "Public relations"],
                "progression": "Improved by successfully managing catastrophic events"
            }
        }
        
        return descriptions.get(attribute, {
            "name": attribute.replace("_", " ").title(),
            "description": "Unknown attribute",
            "affects": [],
            "progression": "Unknown"
        })
    
    def calculate_personality_traits(self, seed: int) -> dict[str, str]:
        """Generate personality traits based on seed for flavor text.
        
        Args:
            seed: Personality seed for consistent generation
            
        Returns:
            Dictionary of personality traits
        """
        random.seed(seed)
        
        traits = {
            "decision_style": random.choice([
                "Analytical", "Intuitive", "Collaborative", "Decisive"
            ]),
            "risk_appetite": random.choice([
                "Conservative", "Moderate", "Aggressive", "Calculated"
            ]),
            "communication": random.choice([
                "Direct", "Diplomatic", "Inspirational", "Data-driven"
            ]),
            "leadership_approach": random.choice([
                "Transformational", "Servant", "Democratic", "Visionary"
            ])
        }
        
        # Reset random seed
        random.seed()
        
        return traits 