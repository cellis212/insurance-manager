"""Competitor behavior simulation for market events.

Simulates AI-controlled insurance companies reacting to market conditions
"""

import random
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import (
    Company, CompanyStateAuthorization, CompanyLineOfBusiness,
    State, LineOfBusiness, Product, PriceDecision, Turn,
    CompanyTurnDecision, CEO, Employee
)
from features.market_events.services.economic_cycles import EconomicPhase


class CompetitorStrategy(Enum):
    """AI competitor strategic approaches."""
    AGGRESSIVE = "aggressive"      # Low prices, rapid expansion
    CONSERVATIVE = "conservative"  # High prices, slow growth
    BALANCED = "balanced"         # Middle ground
    OPPORTUNISTIC = "opportunistic"  # Reacts strongly to events
    NICHE = "niche"              # Focus on specific markets


class CompetitorProfile:
    """Profile for an AI competitor company."""
    
    def __init__(
        self,
        company_id: UUID,
        name: str,
        strategy: CompetitorStrategy,
        capital: Decimal,
        home_state_id: UUID,
        risk_tolerance: float = 0.5
    ):
        self.company_id = company_id
        self.name = name
        self.strategy = strategy
        self.capital = capital
        self.home_state_id = home_state_id
        self.risk_tolerance = risk_tolerance  # 0.0 = very conservative, 1.0 = very risky
        self.authorized_states: Set[UUID] = {home_state_id}
        self.active_lines: Set[UUID] = set()
        self.market_share_by_state: Dict[UUID, float] = {}


class CompetitorBehaviorEngine:
    """Manages AI competitor behavior in response to market conditions.
    
    Key principles:
    - Competitors react realistically to economic conditions
    - Different strategies create market diversity
    - Player actions influence competitor decisions
    - Competitors provide consistent challenge without being unfair
    """
    
    # Strategy behavior modifiers
    STRATEGY_MODIFIERS = {
        CompetitorStrategy.AGGRESSIVE: {
            "price_modifier": Decimal("0.85"),       # 15% below market
            "expansion_eagerness": 0.8,              # 80% chance to expand
            "product_tier_preference": "basic",      # Cost-focused
            "reaction_speed": 1.5,                   # Quick to react
            "capital_reserve_ratio": Decimal("0.1")  # Only 10% reserves
        },
        CompetitorStrategy.CONSERVATIVE: {
            "price_modifier": Decimal("1.15"),
            "expansion_eagerness": 0.2,
            "product_tier_preference": "premium",
            "reaction_speed": 0.5,
            "capital_reserve_ratio": Decimal("0.3")
        },
        CompetitorStrategy.BALANCED: {
            "price_modifier": Decimal("1.0"),
            "expansion_eagerness": 0.5,
            "product_tier_preference": "standard",
            "reaction_speed": 1.0,
            "capital_reserve_ratio": Decimal("0.2")
        },
        CompetitorStrategy.OPPORTUNISTIC: {
            "price_modifier": Decimal("0.95"),
            "expansion_eagerness": 0.6,
            "product_tier_preference": "adaptive",  # Changes based on market
            "reaction_speed": 2.0,
            "capital_reserve_ratio": Decimal("0.15")
        },
        CompetitorStrategy.NICHE: {
            "price_modifier": Decimal("1.1"),
            "expansion_eagerness": 0.3,
            "product_tier_preference": "premium",
            "reaction_speed": 0.8,
            "capital_reserve_ratio": Decimal("0.25")
        }
    }
    
    def __init__(self, session: AsyncSession):
        """Initialize the competitor behavior engine.
        
        Args:
            session: Database session
        """
        self.session = session
        self._competitors: Dict[UUID, CompetitorProfile] = {}
        self._market_intelligence: Dict[str, Any] = {}
    
    async def initialize_competitors(
        self,
        semester_id: UUID,
        num_competitors: int = 5
    ) -> List[CompetitorProfile]:
        """Initialize AI competitor companies for the semester.
        
        Args:
            semester_id: Current semester ID
            num_competitors: Number of AI competitors to create
            
        Returns:
            List of created competitor profiles
        """
        competitors = []
        
        # Get available states
        result = await self.session.execute(select(State))
        states = list(result.scalars().all())
        
        # Define competitor templates
        competitor_templates = [
            ("MegaSure Insurance", CompetitorStrategy.AGGRESSIVE, Decimal("10000000")),
            ("SafeGuard Mutual", CompetitorStrategy.CONSERVATIVE, Decimal("15000000")),
            ("National Protector", CompetitorStrategy.BALANCED, Decimal("12000000")),
            ("QuickClaim Corp", CompetitorStrategy.OPPORTUNISTIC, Decimal("8000000")),
            ("Regional Shield", CompetitorStrategy.NICHE, Decimal("6000000"))
        ]
        
        for i in range(min(num_competitors, len(competitor_templates))):
            name, strategy, capital = competitor_templates[i]
            home_state = random.choice(states)
            
            # Create AI company
            company = Company(
                user_id=None,  # No user for AI companies
                semester_id=semester_id,
                name=name,
                home_state_id=home_state.id,
                current_capital=capital,
                operational_data={
                    "is_ai_competitor": True,
                    "strategy": strategy.value
                }
            )
            self.session.add(company)
            await self.session.flush()
            
            # Create CEO for the company
            ceo = CEO(
                company_id=company.id,
                leadership=random.randint(50, 80),
                risk_intelligence=random.randint(50, 80),
                market_acumen=random.randint(50, 80),
                regulatory_mastery=random.randint(50, 80),
                innovation_capacity=random.randint(50, 80),
                deal_making=random.randint(50, 80),
                financial_expertise=random.randint(50, 80),
                crisis_command=random.randint(50, 80)
            )
            self.session.add(ceo)
            
            # Create initial employees
            await self._create_initial_employees(company.id, strategy)
            
            # Create competitor profile
            profile = CompetitorProfile(
                company_id=company.id,
                name=name,
                strategy=strategy,
                capital=capital,
                home_state_id=home_state.id,
                risk_tolerance=random.uniform(0.3, 0.7)
            )
            
            # Authorize home state
            auth = CompanyStateAuthorization(
                company_id=company.id,
                state_id=home_state.id,
                status="approved"
            )
            self.session.add(auth)
            
            competitors.append(profile)
            self._competitors[company.id] = profile
        
        await self.session.commit()
        return competitors
    
    async def generate_competitor_decisions(
        self,
        turn: Turn,
        economic_phase: EconomicPhase,
        market_events: List[Any],
        player_actions: Dict[str, Any]
    ) -> Dict[UUID, CompanyTurnDecision]:
        """Generate decisions for all AI competitors.
        
        Args:
            turn: Current turn
            economic_phase: Current economic phase
            market_events: Active market events
            player_actions: Recent player company actions
            
        Returns:
            Dictionary of company_id -> decisions
        """
        decisions = {}
        
        # Update market intelligence
        await self._update_market_intelligence(turn, player_actions)
        
        for company_id, profile in self._competitors.items():
            # Get company data
            company = await self.session.get(Company, company_id)
            if not company or company.current_capital <= 0:
                continue  # Skip bankrupt companies
            
            # Generate decisions based on strategy
            company_decisions = await self._generate_company_decisions(
                company, profile, economic_phase, market_events
            )
            
            # Create decision record
            decision = CompanyTurnDecision(
                company_id=company_id,
                turn_id=turn.id,
                decisions=company_decisions,
                submitted_at=turn.start_date  # AI submits immediately
            )
            
            decisions[company_id] = decision
            self.session.add(decision)
        
        await self.session.commit()
        return decisions
    
    async def _generate_company_decisions(
        self,
        company: Company,
        profile: CompetitorProfile,
        economic_phase: EconomicPhase,
        market_events: List[Any]
    ) -> Dict[str, Any]:
        """Generate specific decisions for a competitor company.
        
        Args:
            company: Company entity
            profile: Competitor profile
            economic_phase: Current economic phase
            market_events: Active market events
            
        Returns:
            Dictionary of decisions
        """
        decisions = {
            "expansions": [],
            "products": [],
            "pricing": [],
            "investments": {},
            "employees": []
        }
        
        modifiers = self.STRATEGY_MODIFIERS[profile.strategy]
        
        # Expansion decisions
        if await self._should_expand(company, profile, economic_phase):
            expansion = await self._select_expansion_target(company, profile)
            if expansion:
                decisions["expansions"].append(expansion)
        
        # Product decisions
        product_changes = await self._evaluate_product_changes(
            company, profile, economic_phase
        )
        decisions["products"].extend(product_changes)
        
        # Pricing decisions
        pricing = await self._generate_pricing_decisions(
            company, profile, economic_phase, market_events
        )
        decisions["pricing"] = pricing
        
        # Investment decisions
        decisions["investments"] = self._generate_investment_preferences(
            profile, economic_phase, market_events
        )
        
        # Employee decisions
        if await self._should_hire_employees(company, profile):
            hire_decisions = await self._select_employees_to_hire(company, profile)
            decisions["employees"].extend(hire_decisions)
        
        return decisions
    
    async def _should_expand(
        self,
        company: Company,
        profile: CompetitorProfile,
        economic_phase: EconomicPhase
    ) -> bool:
        """Determine if competitor should expand to new state.
        
        Args:
            company: Company entity
            profile: Competitor profile
            economic_phase: Current economic phase
            
        Returns:
            True if should expand
        """
        modifiers = self.STRATEGY_MODIFIERS[profile.strategy]
        base_eagerness = modifiers["expansion_eagerness"]
        
        # Adjust for economic phase
        phase_modifier = {
            EconomicPhase.EXPANSION: 1.2,
            EconomicPhase.PEAK: 1.1,
            EconomicPhase.CONTRACTION: 0.6,
            EconomicPhase.TROUGH: 0.4,
            EconomicPhase.RECOVERY: 0.9
        }.get(economic_phase, 1.0)
        
        # Check capital constraints
        min_capital = modifiers["capital_reserve_ratio"] * company.current_capital
        if company.current_capital < min_capital + Decimal("500000"):
            return False  # Not enough capital
        
        # Random decision based on modified eagerness
        return random.random() < (base_eagerness * phase_modifier)
    
    async def _select_expansion_target(
        self,
        company: Company,
        profile: CompetitorProfile
    ) -> Optional[Dict[str, Any]]:
        """Select state for expansion.
        
        Args:
            company: Company entity
            profile: Competitor profile
            
        Returns:
            Expansion decision or None
        """
        # Get unauthorized states
        result = await self.session.execute(
            select(State).where(
                ~State.id.in_(
                    select(CompanyStateAuthorization.state_id).where(
                        CompanyStateAuthorization.company_id == company.id
                    )
                )
            )
        )
        available_states = list(result.scalars().all())
        
        if not available_states:
            return None
        
        # Score states based on strategy
        if profile.strategy == CompetitorStrategy.AGGRESSIVE:
            # Target high population states
            target = max(available_states, key=lambda s: s.market_size_multiplier)
        elif profile.strategy == CompetitorStrategy.NICHE:
            # Target smaller, less competitive states
            target = min(available_states, key=lambda s: s.market_size_multiplier)
        else:
            # Random selection weighted by market size
            weights = [float(s.market_size_multiplier) for s in available_states]
            target = random.choices(available_states, weights=weights)[0]
        
        return {
            "state_id": str(target.id),
            "action": "expand"
        }
    
    async def _generate_pricing_decisions(
        self,
        company: Company,
        profile: CompetitorProfile,
        economic_phase: EconomicPhase,
        market_events: List[Any]
    ) -> List[Dict[str, Any]]:
        """Generate pricing decisions for all products.
        
        Args:
            company: Company entity
            profile: Competitor profile
            economic_phase: Current economic phase
            market_events: Active market events
            
        Returns:
            List of pricing decisions
        """
        pricing_decisions = []
        
        # Get all company products
        result = await self.session.execute(
            select(Product).where(Product.company_id == company.id)
        )
        products = result.scalars().all()
        
        base_modifier = self.STRATEGY_MODIFIERS[profile.strategy]["price_modifier"]
        
        # Adjust for economic phase
        phase_adjustment = {
            EconomicPhase.EXPANSION: Decimal("1.05"),     # Can charge more
            EconomicPhase.PEAK: Decimal("1.08"),
            EconomicPhase.CONTRACTION: Decimal("0.92"),   # Must reduce prices
            EconomicPhase.TROUGH: Decimal("0.88"),
            EconomicPhase.RECOVERY: Decimal("0.95")
        }.get(economic_phase, Decimal("1.0"))
        
        # Check for catastrophe events
        catastrophe_adjustment = Decimal("1.0")
        for event in market_events:
            if hasattr(event, 'event_type') and event.event_type == "catastrophe":
                if not event.affected_states or company.home_state_id in event.affected_states:
                    catastrophe_adjustment = Decimal("1.15")  # Increase prices during catastrophes
        
        for product in products:
            # Calculate price based on all factors
            price_multiplier = base_modifier * phase_adjustment * catastrophe_adjustment
            
            # Add some random variation
            variation = Decimal(random.uniform(0.95, 1.05))
            final_multiplier = price_multiplier * variation
            
            pricing_decisions.append({
                "product_id": str(product.id),
                "price_multiplier": float(final_multiplier)
            })
        
        return pricing_decisions
    
    def _generate_investment_preferences(
        self,
        profile: CompetitorProfile,
        economic_phase: EconomicPhase,
        market_events: List[Any]
    ) -> Dict[str, float]:
        """Generate investment portfolio preferences.
        
        Args:
            profile: Competitor profile
            economic_phase: Current economic phase
            market_events: Active market events
            
        Returns:
            Investment characteristic preferences
        """
        # Base preferences by strategy
        if profile.strategy == CompetitorStrategy.AGGRESSIVE:
            base_prefs = {
                "risk": 0.7,
                "duration": 0.4,
                "liquidity": 0.3,
                "credit": 0.5,
                "diversification": 0.4
            }
        elif profile.strategy == CompetitorStrategy.CONSERVATIVE:
            base_prefs = {
                "risk": 0.2,
                "duration": 0.6,
                "liquidity": 0.8,
                "credit": 0.8,
                "diversification": 0.9
            }
        else:
            base_prefs = {
                "risk": 0.5,
                "duration": 0.5,
                "liquidity": 0.5,
                "credit": 0.6,
                "diversification": 0.7
            }
        
        # Adjust for economic phase
        if economic_phase in [EconomicPhase.CONTRACTION, EconomicPhase.TROUGH]:
            # Become more conservative
            base_prefs["risk"] *= 0.7
            base_prefs["liquidity"] = min(1.0, base_prefs["liquidity"] * 1.3)
        elif economic_phase == EconomicPhase.EXPANSION:
            # Can take more risk
            base_prefs["risk"] = min(1.0, base_prefs["risk"] * 1.2)
        
        return base_prefs
    
    async def _create_initial_employees(
        self,
        company_id: UUID,
        strategy: CompetitorStrategy
    ) -> None:
        """Create initial C-suite for competitor company.
        
        Args:
            company_id: Company ID
            strategy: Company strategy
        """
        # Skill ranges based on strategy
        if strategy == CompetitorStrategy.AGGRESSIVE:
            skill_range = (40, 70)
        elif strategy == CompetitorStrategy.CONSERVATIVE:
            skill_range = (60, 85)
        else:
            skill_range = (50, 75)
        
        positions = ["CUO", "CFO", "CMO", "CCO", "CTO"]
        
        for position in positions:
            employee = Employee(
                company_id=company_id,
                position=position,
                first_name=f"AI_{position}",
                last_name=str(company_id)[:8],
                skill_level=random.randint(*skill_range),
                salary=Decimal(random.randint(150000, 300000)),
                hire_date=None  # Will be set when hired
            )
            self.session.add(employee)
    
    async def _update_market_intelligence(
        self,
        turn: Turn,
        player_actions: Dict[str, Any]
    ) -> None:
        """Update market intelligence based on player actions.
        
        Args:
            turn: Current turn
            player_actions: Recent player actions
        """
        # Track player pricing trends
        if "average_player_prices" in player_actions:
            self._market_intelligence["player_pricing_trend"] = player_actions["average_player_prices"]
        
        # Track player expansion patterns
        if "player_expansions" in player_actions:
            self._market_intelligence["player_expansion_rate"] = len(player_actions["player_expansions"])
        
        # Store for future decision-making
        self._market_intelligence["last_update_turn"] = turn.week_number
    
    async def _should_hire_employees(
        self,
        company: Company,
        profile: CompetitorProfile
    ) -> bool:
        """Determine if should hire new employees.
        
        Args:
            company: Company entity
            profile: Competitor profile
            
        Returns:
            True if should hire
        """
        # Check if missing key positions
        result = await self.session.execute(
            select(Employee).where(
                Employee.company_id == company.id,
                Employee.termination_date.is_(None)
            )
        )
        current_employees = result.scalars().all()
        
        filled_positions = {emp.position for emp in current_employees}
        key_positions = {"CUO", "CFO", "CMO", "CCO", "CTO"}
        
        # Always hire if missing key positions
        if key_positions - filled_positions:
            return True
        
        # Otherwise based on strategy and capital
        if company.current_capital > Decimal("2000000"):
            return random.random() < 0.3  # 30% chance if well-capitalized
        
        return False
    
    async def _select_employees_to_hire(
        self,
        company: Company,
        profile: CompetitorProfile
    ) -> List[Dict[str, Any]]:
        """Select which employees to hire.
        
        Args:
            company: Company entity
            profile: Competitor profile
            
        Returns:
            List of hire decisions
        """
        hire_decisions = []
        
        # Get current employees
        result = await self.session.execute(
            select(Employee).where(
                Employee.company_id == company.id,
                Employee.termination_date.is_(None)
            )
        )
        current_employees = result.scalars().all()
        filled_positions = {emp.position for emp in current_employees}
        
        # Prioritize missing key positions
        key_positions = ["CUO", "CFO", "CMO", "CCO", "CTO"]
        for position in key_positions:
            if position not in filled_positions:
                hire_decisions.append({
                    "position": position,
                    "action": "hire",
                    "target_skill": 60 if profile.strategy == CompetitorStrategy.AGGRESSIVE else 75
                })
        
        return hire_decisions
    
    async def _evaluate_product_changes(
        self,
        company: Company,
        profile: CompetitorProfile,
        economic_phase: EconomicPhase
    ) -> List[Dict[str, Any]]:
        """Evaluate potential product tier changes.
        
        Args:
            company: Company entity
            profile: Competitor profile
            economic_phase: Current economic phase
            
        Returns:
            List of product change decisions
        """
        product_changes = []
        
        # Get current products
        result = await self.session.execute(
            select(Product).where(Product.company_id == company.id)
        )
        products = result.scalars().all()
        
        tier_preference = self.STRATEGY_MODIFIERS[profile.strategy]["product_tier_preference"]
        
        # Adaptive strategy changes based on economic phase
        if tier_preference == "adaptive":
            if economic_phase in [EconomicPhase.CONTRACTION, EconomicPhase.TROUGH]:
                tier_preference = "basic"  # Focus on volume
            else:
                tier_preference = "premium"  # Focus on margins
        
        for product in products:
            if product.tier != tier_preference and random.random() < 0.2:  # 20% chance to switch
                product_changes.append({
                    "product_id": str(product.id),
                    "action": "change_tier",
                    "new_tier": tier_preference
                })
        
        return product_changes 