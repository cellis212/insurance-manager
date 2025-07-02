"""Employee Hiring Service - Manages C-suite recruitment."""

import random
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.employee import Employee, VALID_POSITIONS, POSITION_SALARY_RANGES
from core.models.company import Company


class EmployeeHiringService:
    """Service for managing employee hiring and weekly candidate pools."""
    
    # First name pools by gender
    FIRST_NAMES = {
        "male": [
            "James", "Robert", "John", "Michael", "David", "William", "Richard",
            "Joseph", "Thomas", "Christopher", "Charles", "Daniel", "Matthew",
            "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Kenneth",
            "Joshua", "Kevin", "Brian", "George", "Edward", "Ronald", "Timothy",
            "Jason", "Jeffrey", "Ryan", "Jacob", "Gary", "Nicholas", "Eric"
        ],
        "female": [
            "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara",
            "Susan", "Jessica", "Sarah", "Karen", "Nancy", "Lisa", "Betty",
            "Margaret", "Sandra", "Ashley", "Kimberly", "Emily", "Donna",
            "Michelle", "Dorothy", "Carol", "Amanda", "Melissa", "Deborah",
            "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia", "Kathleen",
            "Amy", "Shirley", "Angela", "Helen", "Anna", "Brenda", "Pamela"
        ]
    }
    
    # Last names
    LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
        "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
        "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
        "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
        "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz"
    ]
    
    # Special bonus templates by position
    SPECIAL_BONUS_TEMPLATES = {
        "CUO": [
            "-5% loss ratios in {market_type} markets",
            "+15% better risk selection for {line_type} lines",
            "Catastrophe modeling expertise in {region}",
            "Predictive underwriting algorithm developer",
            "Former state insurance commissioner experience"
        ],
        "CFO": [
            "+10% investment returns in {asset_class}",
            "-20% capital costs through {financing_type}",
            "M&A valuation expertise - {deal_size} deals",
            "Former {big_four} audit partner",
            "Hedge fund background - {strategy} specialist"
        ],
        "CMO": [
            "-25% customer acquisition costs via {channel}",
            "+30% digital conversion rates",
            "Viral marketing campaigns - {platform} expert",
            "Former {tech_company} growth lead",
            "Behavioral economics PhD"
        ],
        "CCO": [
            "-2 weeks on all {filing_type} rate filings",
            "Regulatory relationship bonus - {region} states",
            "Multi-state filing expertise - {num} state specialist",
            "Former NAIC committee member",
            "Legislative drafting experience"
        ],
        "CTO": [
            "-15% IT operational costs through {tech_type}",
            "Instant digital product launches",
            "AI/ML implementation expertise - {ml_type}",
            "Cloud migration specialist - {cloud_provider}",
            "Cybersecurity expertise - former {agency}"
        ],
        "CRO": [
            "-20% reinsurance costs with {reinsurer_type}",
            "Early catastrophe warnings - {days} day advantage",
            "Portfolio optimization expertise",
            "Former {rating_agency} analyst",
            "Enterprise risk framework designer"
        ],
        "CAO": [
            "Perfect reserve accuracy for {line_type} lines",
            "-10% audit costs with {audit_firm}",
            "Real-time financial reporting systems",
            "IFRS 17 implementation expert",
            "Former state auditor general"
        ],
        "Chief Actuary": [
            "+20% pricing precision in {market_segment}",
            "Predictive modeling expertise - {model_type}",
            "Competitive intelligence insights - {competitor_type}",
            "Former {consulting_firm} principal",
            "Published researcher - {research_area}"
        ]
    }
    
    # Template variable options
    TEMPLATE_VARS = {
        "market_type": ["new", "competitive", "emerging", "mature"],
        "line_type": ["personal", "commercial", "specialty", "excess"],
        "region": ["Southeast", "Northeast", "Midwest", "Southwest", "West Coast"],
        "asset_class": ["equities", "fixed income", "alternatives", "real estate"],
        "financing_type": ["debt refinancing", "equity optimization", "hybrid instruments"],
        "deal_size": ["$100M+", "$500M+", "$1B+", "mega"],
        "big_four": ["PwC", "EY", "Deloitte", "KPMG"],
        "strategy": ["long/short equity", "merger arbitrage", "distressed debt", "macro"],
        "channel": ["digital", "social media", "affiliate", "direct"],
        "platform": ["TikTok", "Instagram", "LinkedIn", "YouTube"],
        "tech_company": ["Google", "Meta", "Amazon", "Apple"],
        "filing_type": ["rate", "form", "rule", "territory"],
        "num": ["10", "15", "20", "25"],
        "tech_type": ["automation", "cloud optimization", "containerization"],
        "ml_type": ["NLP", "computer vision", "deep learning", "reinforcement learning"],
        "cloud_provider": ["AWS", "Azure", "GCP", "hybrid cloud"],
        "agency": ["NSA", "FBI", "CIA", "military"],
        "reinsurer_type": ["traditional", "alternative capital", "ILS", "captive"],
        "days": ["7", "10", "14", "21"],
        "rating_agency": ["S&P", "Moody's", "AM Best", "Fitch"],
        "audit_firm": ["Big 4", "regional", "specialist", "boutique"],
        "market_segment": ["small commercial", "middle market", "large account", "personal lines"],
        "model_type": ["GLM", "GBM", "neural network", "ensemble"],
        "competitor_type": ["regional", "national", "mutual", "startup"],
        "consulting_firm": ["McKinsey", "BCG", "Bain", "Oliver Wyman"],
        "research_area": ["climate risk", "cyber risk", "pandemic modeling", "social inflation"]
    }
    
    def __init__(self):
        """Initialize the employee hiring service."""
        self.config = {}
        self._name_cache = set()  # Avoid duplicate names in same pool
    
    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize service with configuration.
        
        Args:
            config: Employee system configuration
        """
        self.config = config
    
    async def generate_weekly_hiring_pool(
        self,
        session: AsyncSession,
        semester_id: str,
        turn_number: int
    ) -> dict[str, list[dict[str, Any]]]:
        """Generate available candidates for each C-suite position.
        
        Args:
            session: Database session
            semester_id: Current semester ID
            turn_number: Current turn number
            
        Returns:
            Dictionary mapping positions to candidate lists
        """
        hiring_pool = {}
        self._name_cache.clear()  # Reset for new pool
        
        # Get configuration
        candidates_per_position = self.config.get("candidates_per_position", 3)
        skill_range = self.config.get("skill_range", {"min": 30, "max": 80})
        special_bonus_chance = self.config.get("special_bonus_chance", 0.15)
        
        # Generate candidates for each position
        for position in VALID_POSITIONS:
            candidates = []
            
            for i in range(candidates_per_position):
                # Generate unique name
                name = self._generate_unique_name()
                
                # Generate skill level with some variation by turn
                # Later turns have slightly higher average skills
                turn_bonus = min(10, turn_number // 10)  # +1 per 10 turns, max +10
                min_skill = skill_range["min"] + turn_bonus
                max_skill = min(100, skill_range["max"] + turn_bonus)
                skill_level = random.randint(min_skill, max_skill)
                
                # Calculate salary based on skill
                base_salary = Employee.calculate_salary_requirement(position, skill_level)
                
                # Determine if candidate has special bonus
                special_bonus = None
                special_bonus_details = {}
                
                if skill_level >= 70 and random.random() < special_bonus_chance:
                    special_bonus, special_bonus_details = self._generate_special_bonus(
                        position, skill_level
                    )
                
                # Create candidate data
                candidate = {
                    "name": name,
                    "position": position,
                    "skill_level": skill_level,
                    "base_salary": float(base_salary),
                    "special_bonus": special_bonus,
                    "special_bonus_details": special_bonus_details,
                    "availability_expires": turn_number + 2,  # Available for 2 turns
                    "personality": self._generate_personality(),
                    "background": self._generate_background(position)
                }
                
                candidates.append(candidate)
            
            # Sort by skill level (best first)
            candidates.sort(key=lambda x: x["skill_level"], reverse=True)
            hiring_pool[position] = candidates
        
        return hiring_pool
    
    async def hire_employee(
        self,
        session: AsyncSession,
        company: Company,
        candidate_data: dict[str, Any],
        hire_date: Optional[date] = None
    ) -> Employee:
        """Hire an employee from the candidate pool.
        
        Args:
            session: Database session
            company: Company hiring the employee
            candidate_data: Candidate information from hiring pool
            hire_date: Optional hire date (defaults to today)
            
        Returns:
            Created Employee instance
        """
        if hire_date is None:
            hire_date = date.today()
        
        # Create employee from candidate data
        employee = Employee(
            company_id=company.id,
            position=candidate_data["position"],
            name=candidate_data["name"],
            skill_level=candidate_data["skill_level"],
            base_salary=Decimal(str(candidate_data["base_salary"])),
            bonus_paid_ytd=Decimal("0.00"),
            special_bonus=candidate_data.get("special_bonus"),
            special_bonus_details=candidate_data.get("special_bonus_details", {}),
            hire_date=hire_date.isoformat(),
            quarters_employed=0,
            performance_history=[]
        )
        
        # Add hiring information to performance history
        employee.performance_history.append({
            "event": "hired",
            "date": hire_date.isoformat(),
            "details": {
                "from_turn": candidate_data.get("availability_expires", 0) - 2,
                "personality": candidate_data.get("personality", {}),
                "background": candidate_data.get("background", {})
            }
        })
        
        session.add(employee)
        
        return employee
    
    def _generate_unique_name(self) -> str:
        """Generate a unique candidate name.
        
        Returns:
            Full name as "First Last"
        """
        attempts = 0
        while attempts < 100:
            # Randomly choose gender for name generation
            gender = random.choice(["male", "female"])
            first_name = random.choice(self.FIRST_NAMES[gender])
            last_name = random.choice(self.LAST_NAMES)
            
            full_name = f"{first_name} {last_name}"
            
            if full_name not in self._name_cache:
                self._name_cache.add(full_name)
                return full_name
            
            attempts += 1
        
        # Fallback with middle initial if can't find unique
        middle_initial = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        return f"{first_name} {middle_initial}. {last_name}"
    
    def _generate_special_bonus(
        self,
        position: str,
        skill_level: int
    ) -> tuple[str, dict[str, Any]]:
        """Generate a special bonus for high-skill candidates.
        
        Args:
            position: C-suite position
            skill_level: Candidate's skill level
            
        Returns:
            Tuple of (bonus description, bonus details)
        """
        templates = self.SPECIAL_BONUS_TEMPLATES.get(position, [])
        if not templates:
            return None, {}
        
        # Select random template
        template = random.choice(templates)
        
        # Fill in template variables
        import re
        variables = re.findall(r'{(\w+)}', template)
        
        details = {}
        for var in variables:
            if var in self.TEMPLATE_VARS:
                value = random.choice(self.TEMPLATE_VARS[var])
                template = template.replace(f"{{{var}}}", value)
                details[var] = value
        
        # Add skill-based modifier
        if skill_level >= 90:
            details["effectiveness"] = 1.5  # 50% more effective
        elif skill_level >= 80:
            details["effectiveness"] = 1.25  # 25% more effective
        else:
            details["effectiveness"] = 1.0
        
        return template, details
    
    def _generate_personality(self) -> dict[str, str]:
        """Generate personality traits for a candidate.
        
        Returns:
            Dictionary of personality traits
        """
        return {
            "work_style": random.choice([
                "Collaborative", "Independent", "Detail-oriented", "Big picture"
            ]),
            "leadership": random.choice([
                "Mentor", "Delegator", "Hands-on", "Strategic"
            ]),
            "communication": random.choice([
                "Direct", "Diplomatic", "Analytical", "Persuasive"
            ]),
            "innovation": random.choice([
                "Early adopter", "Cautious", "Experimental", "Traditional"
            ])
        }
    
    def _generate_background(self, position: str) -> dict[str, Any]:
        """Generate professional background for a candidate.
        
        Args:
            position: C-suite position
            
        Returns:
            Dictionary of background information
        """
        backgrounds_by_position = {
            "CUO": [
                "Former underwriting manager at major carrier",
                "Actuarial background with pricing expertise",
                "Started in field underwriting",
                "Risk consulting experience"
            ],
            "CFO": [
                "Big 4 accounting firm partner",
                "Investment banking background",
                "Insurance company treasurer",
                "Private equity experience"
            ],
            "CMO": [
                "Digital marketing pioneer",
                "Brand management at Fortune 500",
                "Insurance industry veteran",
                "Tech startup growth expert"
            ],
            "CCO": [
                "Former state regulator",
                "Law firm insurance practice",
                "In-house compliance leader",
                "Government relations expert"
            ],
            "CTO": [
                "Silicon Valley veteran",
                "Insurance tech innovator",
                "Enterprise architecture leader",
                "Startup founder"
            ],
            "CRO": [
                "Reinsurance broker background",
                "Enterprise risk consultant",
                "Rating agency analyst",
                "Catastrophe modeler"
            ],
            "CAO": [
                "Public accounting partner",
                "Insurance CFO experience",
                "Financial reporting expert",
                "M&A integration specialist"
            ],
            "Chief Actuary": [
                "Consulting actuary",
                "Pricing actuary at major carrier",
                "Predictive modeling expert",
                "Academic researcher"
            ]
        }
        
        background_type = random.choice(backgrounds_by_position.get(position, ["Industry veteran"]))
        years_experience = random.randint(10, 25)
        
        return {
            "type": background_type,
            "years_experience": years_experience,
            "industries": random.sample(
                ["P&C Insurance", "Life Insurance", "Reinsurance", "Consulting", "Technology"],
                k=random.randint(1, 3)
            )
        } 