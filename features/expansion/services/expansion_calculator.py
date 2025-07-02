"""Expansion cost calculator service.

Calculates the cost and requirements for expanding into new states,
factoring in distance, market size, regulatory categories, and home state advantages.
"""

import math
from decimal import Decimal
from typing import Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Company, State, CompanyStateAuthorization
from features.expansion.data.state_coordinates import (
    STATE_COORDINATES,
    STATE_REGIONS,
    STATE_ADJACENCIES
)


class ExpansionCalculator:
    """Calculates expansion costs and requirements for companies."""
    
    def __init__(self, config: Dict):
        """Initialize calculator with game configuration.
        
        Args:
            config: Expansion parameters from game configuration
        """
        self.base_expansion_weeks = config.get("base_expansion_weeks", 4)
        self.distance_cost_per_mile = Decimal(str(config.get("distance_cost_per_mile", 100)))
        self.market_size_cost_multiplier = Decimal(str(config.get("market_size_cost_multiplier", 1.0)))
        self.max_states_per_turn = config.get("max_states_per_turn", 3)
        self.home_state_discount = Decimal(str(config.get("home_state_discount", 0.5)))  # From initial_values
        self.adjacent_state_discount = Decimal(str(config.get("adjacent_state_discount", 0.2)))
        self.same_region_discount = Decimal(str(config.get("same_region_discount", 0.1)))
    
    @staticmethod
    def calculate_distance(state1_code: str, state2_code: str) -> float:
        """Calculate distance between two states using their geographic centers.
        
        Uses the Haversine formula to calculate great-circle distance.
        
        Args:
            state1_code: Two-letter code for first state
            state2_code: Two-letter code for second state
            
        Returns:
            Distance in miles
        """
        if state1_code not in STATE_COORDINATES or state2_code not in STATE_COORDINATES:
            raise ValueError(f"Invalid state code: {state1_code} or {state2_code}")
        
        lat1, lon1 = STATE_COORDINATES[state1_code]
        lat2, lon2 = STATE_COORDINATES[state2_code]
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in miles
        r = 3959
        
        return c * r
    
    async def calculate_expansion_cost(
        self,
        session: AsyncSession,
        company: Company,
        target_state: State,
        existing_authorizations: Optional[list[CompanyStateAuthorization]] = None
    ) -> Dict[str, any]:
        """Calculate the cost to expand into a target state.
        
        Args:
            session: Database session
            company: Company requesting expansion
            target_state: State to expand into
            existing_authorizations: Optional list of existing authorizations to avoid requery
            
        Returns:
            Dictionary with:
                - total_cost: Total expansion cost
                - base_cost: Base state expansion cost
                - distance_cost: Additional cost based on distance
                - discounts: Dictionary of applied discounts
                - is_home_state: Whether this is the home state
                - is_adjacent: Whether this is adjacent to an authorized state
                - approval_weeks: Weeks until approval
        """
        # Check if this is the home state
        home_state = await session.get(State, company.home_state_id)
        is_home_state = target_state.id == company.home_state_id
        
        # Get existing authorizations if not provided
        if existing_authorizations is None:
            result = await session.execute(
                select(CompanyStateAuthorization)
                .where(CompanyStateAuthorization.company_id == company.id)
                .where(CompanyStateAuthorization.status == "approved")
            )
            existing_authorizations = result.scalars().all()
        
        # Start with base cost
        base_cost = target_state.base_expansion_cost
        
        # Apply market size multiplier
        market_adjusted_cost = base_cost * target_state.market_size_multiplier * self.market_size_cost_multiplier
        
        # Calculate distance-based cost
        distance_cost = Decimal("0")
        min_distance = float('inf')
        
        if not is_home_state and existing_authorizations:
            # Find minimum distance from any authorized state
            for auth in existing_authorizations:
                auth_state = await session.get(State, auth.state_id)
                distance = self.calculate_distance(auth_state.code, target_state.code)
                min_distance = min(min_distance, distance)
            
            if min_distance < float('inf'):
                distance_cost = self.distance_cost_per_mile * Decimal(str(min_distance))
        elif not is_home_state:
            # If no existing authorizations, calculate from home state
            distance = self.calculate_distance(home_state.code, target_state.code)
            distance_cost = self.distance_cost_per_mile * Decimal(str(distance))
            min_distance = distance
        
        # Calculate total before discounts
        total_cost = market_adjusted_cost + distance_cost
        
        # Apply discounts
        discounts = {}
        discount_multiplier = Decimal("1.0")
        
        if is_home_state:
            discounts["home_state"] = self.home_state_discount
            discount_multiplier *= (Decimal("1.0") - self.home_state_discount)
        else:
            # Check for adjacent state discount
            is_adjacent = False
            for auth in existing_authorizations:
                auth_state = await session.get(State, auth.state_id)
                if target_state.code in STATE_ADJACENCIES.get(auth_state.code, set()):
                    is_adjacent = True
                    break
            
            if is_adjacent:
                discounts["adjacent_state"] = self.adjacent_state_discount
                discount_multiplier *= (Decimal("1.0") - self.adjacent_state_discount)
            
            # Check for same region discount
            if home_state.code in STATE_REGIONS and target_state.code in STATE_REGIONS:
                if STATE_REGIONS[home_state.code] == STATE_REGIONS[target_state.code]:
                    discounts["same_region"] = self.same_region_discount
                    discount_multiplier *= (Decimal("1.0") - self.same_region_discount)
        
        # Apply final discount
        total_cost *= discount_multiplier
        
        # Determine approval time (faster for home state)
        approval_weeks = 1 if is_home_state else self.base_expansion_weeks
        
        # Regulatory category affects approval time
        if target_state.regulatory_category == "strict" and not is_home_state:
            approval_weeks += 2
        elif target_state.regulatory_category == "light" and not is_home_state:
            approval_weeks -= 1
        
        approval_weeks = max(1, approval_weeks)  # Minimum 1 week
        
        return {
            "total_cost": total_cost,
            "base_cost": base_cost,
            "market_adjusted_cost": market_adjusted_cost,
            "distance_cost": distance_cost,
            "discounts": discounts,
            "discount_amount": (market_adjusted_cost + distance_cost) - total_cost,
            "is_home_state": is_home_state,
            "is_adjacent": is_adjacent if not is_home_state else None,
            "approval_weeks": approval_weeks,
            "regulatory_category": target_state.regulatory_category,
            "distance_miles": min_distance if min_distance < float('inf') else 0
        }
    
    async def get_expansion_opportunities(
        self,
        session: AsyncSession,
        company: Company,
        budget: Optional[Decimal] = None
    ) -> list[Dict]:
        """Get all available expansion opportunities for a company.
        
        Args:
            session: Database session
            company: Company looking for expansion
            budget: Optional budget constraint
            
        Returns:
            List of expansion opportunities sorted by cost
        """
        # Get all states
        result = await session.execute(select(State))
        all_states = result.scalars().all()
        
        # Get existing authorizations
        auth_result = await session.execute(
            select(CompanyStateAuthorization)
            .where(CompanyStateAuthorization.company_id == company.id)
        )
        authorizations = auth_result.scalars().all()
        
        # Create set of already authorized states
        authorized_state_ids = {auth.state_id for auth in authorizations}
        approved_auths = [auth for auth in authorizations if auth.status == "approved"]
        
        opportunities = []
        
        for state in all_states:
            # Skip if already authorized or pending
            if state.id in authorized_state_ids:
                continue
            
            # Calculate expansion cost
            cost_info = await self.calculate_expansion_cost(
                session, company, state, approved_auths
            )
            
            # Skip if over budget
            if budget and cost_info["total_cost"] > budget:
                continue
            
            opportunities.append({
                "state": state,
                "state_code": state.code,
                "state_name": state.name,
                **cost_info
            })
        
        # Sort by total cost
        opportunities.sort(key=lambda x: x["total_cost"])
        
        return opportunities
    
    def validate_expansion_request(
        self,
        company: Company,
        target_states: list[State],
        pending_expansions: int = 0
    ) -> Tuple[bool, Optional[str]]:
        """Validate an expansion request.
        
        Args:
            company: Company requesting expansion
            target_states: List of states to expand into
            pending_expansions: Number of currently pending expansions
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check company is active
        if company.is_active != "active":
            return False, "Company must be active to expand"
        
        # Check expansion limit
        total_expansions = len(target_states) + pending_expansions
        if total_expansions > self.max_states_per_turn:
            return False, f"Cannot expand to more than {self.max_states_per_turn} states per turn"
        
        # Check for duplicates
        state_ids = [state.id for state in target_states]
        if len(state_ids) != len(set(state_ids)):
            return False, "Cannot expand to the same state multiple times"
        
        return True, None 