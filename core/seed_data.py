"""Seed data script for initializing the Insurance Manager database.

Populates the database with:
- All 51 US states with regulatory categories
- Standard lines of business
- Initial game configuration
- Sample semester setup
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import async_session_maker, init_db
from core.models import (
    State,
    LineOfBusiness,
    GameConfiguration,
    Semester,
    SemesterConfiguration,
)

logger = logging.getLogger(__name__)

# US States data with regulatory categories
US_STATES_DATA = [
    # Strict regulatory states (higher barriers, more requirements)
    {"code": "CA", "name": "California", "category": "strict", "base_cost": 500000, "multiplier": 1.4},
    {"code": "NY", "name": "New York", "category": "strict", "base_cost": 450000, "multiplier": 1.3},
    {"code": "FL", "name": "Florida", "category": "strict", "base_cost": 400000, "multiplier": 1.3},
    {"code": "TX", "name": "Texas", "category": "strict", "base_cost": 400000, "multiplier": 1.25},
    {"code": "IL", "name": "Illinois", "category": "strict", "base_cost": 350000, "multiplier": 1.2},
    
    # Moderate regulatory states
    {"code": "PA", "name": "Pennsylvania", "category": "moderate", "base_cost": 300000, "multiplier": 1.1},
    {"code": "OH", "name": "Ohio", "category": "moderate", "base_cost": 275000, "multiplier": 1.1},
    {"code": "GA", "name": "Georgia", "category": "moderate", "base_cost": 275000, "multiplier": 1.1},
    {"code": "NC", "name": "North Carolina", "category": "moderate", "base_cost": 250000, "multiplier": 1.1},
    {"code": "MI", "name": "Michigan", "category": "moderate", "base_cost": 275000, "multiplier": 1.05},
    {"code": "NJ", "name": "New Jersey", "category": "moderate", "base_cost": 325000, "multiplier": 1.15},
    {"code": "VA", "name": "Virginia", "category": "moderate", "base_cost": 250000, "multiplier": 1.05},
    {"code": "WA", "name": "Washington", "category": "moderate", "base_cost": 300000, "multiplier": 1.1},
    {"code": "AZ", "name": "Arizona", "category": "moderate", "base_cost": 225000, "multiplier": 1.05},
    {"code": "MA", "name": "Massachusetts", "category": "moderate", "base_cost": 325000, "multiplier": 1.15},
    {"code": "TN", "name": "Tennessee", "category": "moderate", "base_cost": 225000, "multiplier": 1.0},
    {"code": "IN", "name": "Indiana", "category": "moderate", "base_cost": 200000, "multiplier": 1.0},
    {"code": "MO", "name": "Missouri", "category": "moderate", "base_cost": 200000, "multiplier": 1.0},
    {"code": "MD", "name": "Maryland", "category": "moderate", "base_cost": 275000, "multiplier": 1.1},
    {"code": "WI", "name": "Wisconsin", "category": "moderate", "base_cost": 225000, "multiplier": 1.0},
    {"code": "CO", "name": "Colorado", "category": "moderate", "base_cost": 250000, "multiplier": 1.05},
    {"code": "MN", "name": "Minnesota", "category": "moderate", "base_cost": 225000, "multiplier": 1.0},
    {"code": "SC", "name": "South Carolina", "category": "moderate", "base_cost": 200000, "multiplier": 1.0},
    {"code": "AL", "name": "Alabama", "category": "moderate", "base_cost": 175000, "multiplier": 0.95},
    {"code": "LA", "name": "Louisiana", "category": "moderate", "base_cost": 200000, "multiplier": 1.0},
    {"code": "KY", "name": "Kentucky", "category": "moderate", "base_cost": 175000, "multiplier": 0.95},
    {"code": "OR", "name": "Oregon", "category": "moderate", "base_cost": 225000, "multiplier": 1.0},
    {"code": "OK", "name": "Oklahoma", "category": "moderate", "base_cost": 175000, "multiplier": 0.95},
    {"code": "CT", "name": "Connecticut", "category": "moderate", "base_cost": 300000, "multiplier": 1.1},
    {"code": "UT", "name": "Utah", "category": "moderate", "base_cost": 200000, "multiplier": 1.0},
    
    # Light regulatory states (easier entry, fewer requirements)
    {"code": "NV", "name": "Nevada", "category": "light", "base_cost": 150000, "multiplier": 0.9},
    {"code": "IA", "name": "Iowa", "category": "light", "base_cost": 150000, "multiplier": 0.9},
    {"code": "AR", "name": "Arkansas", "category": "light", "base_cost": 125000, "multiplier": 0.85},
    {"code": "MS", "name": "Mississippi", "category": "light", "base_cost": 125000, "multiplier": 0.85},
    {"code": "KS", "name": "Kansas", "category": "light", "base_cost": 150000, "multiplier": 0.9},
    {"code": "NM", "name": "New Mexico", "category": "light", "base_cost": 150000, "multiplier": 0.9},
    {"code": "NE", "name": "Nebraska", "category": "light", "base_cost": 125000, "multiplier": 0.85},
    {"code": "ID", "name": "Idaho", "category": "light", "base_cost": 125000, "multiplier": 0.85},
    {"code": "WV", "name": "West Virginia", "category": "light", "base_cost": 125000, "multiplier": 0.85},
    {"code": "HI", "name": "Hawaii", "category": "light", "base_cost": 175000, "multiplier": 0.95},
    {"code": "NH", "name": "New Hampshire", "category": "light", "base_cost": 150000, "multiplier": 0.9},
    {"code": "ME", "name": "Maine", "category": "light", "base_cost": 125000, "multiplier": 0.85},
    {"code": "RI", "name": "Rhode Island", "category": "light", "base_cost": 150000, "multiplier": 0.9},
    {"code": "MT", "name": "Montana", "category": "light", "base_cost": 100000, "multiplier": 0.8},
    {"code": "DE", "name": "Delaware", "category": "light", "base_cost": 150000, "multiplier": 0.9},
    {"code": "SD", "name": "South Dakota", "category": "light", "base_cost": 100000, "multiplier": 0.8},
    {"code": "ND", "name": "North Dakota", "category": "light", "base_cost": 100000, "multiplier": 0.8},
    {"code": "AK", "name": "Alaska", "category": "light", "base_cost": 150000, "multiplier": 0.9},
    {"code": "VT", "name": "Vermont", "category": "light", "base_cost": 125000, "multiplier": 0.85},
    {"code": "DC", "name": "District of Columbia", "category": "light", "base_cost": 200000, "multiplier": 1.0},
    {"code": "WY", "name": "Wyoming", "category": "light", "base_cost": 100000, "multiplier": 0.8},
]

# Standard lines of business
LINES_OF_BUSINESS_DATA = [
    {
        "code": "AUTO_PERSONAL",
        "name": "Personal Auto",
        "base_frequency": 0.15,  # 15% of policies have claims per year
        "base_severity": 8000,   # Average claim is $8,000
        "capital_multiplier": 1.0,
        "characteristics": {
            "risk_volatility": "medium",
            "regulatory_complexity": "high",
            "market_size": "very_large",
            "competition_level": "intense"
        }
    },
    {
        "code": "HOME_OWNERS", 
        "name": "Homeowners",
        "base_frequency": 0.05,  # 5% of policies have claims per year
        "base_severity": 25000,  # Average claim is $25,000
        "capital_multiplier": 1.2,
        "characteristics": {
            "risk_volatility": "high",  # Natural disasters
            "regulatory_complexity": "medium",
            "market_size": "large",
            "competition_level": "high"
        }
    },
    {
        "code": "GENERAL_LIABILITY",
        "name": "General Liability",
        "base_frequency": 0.02,  # 2% of policies have claims per year
        "base_severity": 50000,  # Average claim is $50,000
        "capital_multiplier": 1.5,
        "characteristics": {
            "risk_volatility": "high",
            "regulatory_complexity": "medium",
            "market_size": "medium",
            "competition_level": "moderate"
        }
    },
    {
        "code": "WORKERS_COMP",
        "name": "Workers' Compensation",
        "base_frequency": 0.03,  # 3% of policies have claims per year
        "base_severity": 35000,  # Average claim is $35,000
        "capital_multiplier": 2.0,
        "characteristics": {
            "risk_volatility": "medium",
            "regulatory_complexity": "very_high",
            "market_size": "large",
            "competition_level": "moderate"
        }
    },
    {
        "code": "COMMERCIAL_PROPERTY",
        "name": "Commercial Property", 
        "base_frequency": 0.04,  # 4% of policies have claims per year
        "base_severity": 75000,  # Average claim is $75,000
        "capital_multiplier": 1.8,
        "characteristics": {
            "risk_volatility": "high",
            "regulatory_complexity": "low",
            "market_size": "medium",
            "competition_level": "moderate"
        }
    }
]

# Initial game configuration
DEFAULT_GAME_CONFIG = {
    "name": "Default Game Configuration",
    "version": 1,
    "is_active": True,
    "economic_parameters": {
        "interest_rate": 0.05,
        "inflation_rate": 0.02,
        "market_growth_rate": 0.03,
        "recession_probability": 0.15,
        "boom_probability": 0.20
    },
    "turn_parameters": {
        "turns_per_semester": 16,
        "processing_day": "monday",
        "processing_hour": 0,
        "late_submission_penalty": 0.05,
        "no_decision_default": "maintain_previous"
    },
    "initial_values": {
        "starting_capital": 5000000,
        "minimum_capital": 1000000,
        "solvency_ratio_required": 1.25,
        "home_state_discount": 0.50,  # 50% discount on expansion
        "home_state_market_bonus": 0.10  # 10% market share advantage
    },
    "regulatory_parameters": {
        "authorization_wait_weeks": 4,
        "compliance_audit_frequency": 0.1,  # 10% chance per turn
        "penalty_rate_noncompliance": 0.05,
        "license_renewal_frequency_years": 2
    },
    "employee_parameters": {
        "c_suite_positions": ["CEO", "CUO", "CFO", "CMO", "CCO", "CTO", "CRO", "CAO", "Chief Actuary"],
        "base_salary_ranges": {
            "low": 100000,
            "medium": 150000,
            "high": 250000
        },
        "skill_impact_multiplier": 0.01,  # 1% per skill point
        "hiring_pool_size": 5
    },
    "product_parameters": {
        "tier_price_modifiers": {
            "basic": -0.20,
            "standard": 0.0,
            "premium": 0.30
        },
        "tier_risk_modifiers": {
            "basic": 0.30,  # 30% worse risks
            "standard": 0.0,
            "premium": -0.10  # 10% better risks
        },
        "switch_cost": 50000,
        "switch_time_weeks": 2
    },
    "expansion_parameters": {
        "base_expansion_weeks": 4,
        "distance_cost_per_mile": 100,
        "market_size_cost_multiplier": 1.0,
        "max_states_per_turn": 3
    },
    "investment_parameters": {
        "min_liquidity_ratio": 0.20,
        "rebalancing_cost_rate": 0.001,
        "skill_noise_range": {
            "novice": 0.30,    # 30% noise
            "intermediate": 0.15,  # 15% noise
            "expert": 0.05     # 5% noise
        }
    },
    "claims_parameters": {
        "catastrophe_frequency": 0.05,  # 5% chance per turn
        "catastrophe_severity_multiplier": 5.0,
        "seasonal_factors": {
            "winter": 1.2,
            "spring": 1.0,
            "summer": 0.8,
            "fall": 1.0
        }
    }
}


async def seed_states(session: AsyncSession) -> List[State]:
    """Seed all US states with regulatory data.
    
    Args:
        session: Database session
        
    Returns:
        List of created State objects
    """
    # Check if states already exist
    result = await session.execute(select(State))
    existing_states = result.scalars().all()
    
    if existing_states:
        logger.info(f"States already seeded: {len(existing_states)} states found")
        return existing_states
    
    states = []
    for state_data in US_STATES_DATA:
        state = State(
            code=state_data["code"],
            name=state_data["name"],
            regulatory_category=state_data["category"],
            base_expansion_cost=Decimal(str(state_data["base_cost"])),
            market_size_multiplier=Decimal(str(state_data["multiplier"])),
            additional_requirements={
                "filing_fee": state_data["base_cost"] * 0.01,  # 1% filing fee
                "annual_renewal_fee": state_data["base_cost"] * 0.005,  # 0.5% annual
                "minimum_capital_required": state_data["base_cost"] * 2,
                "special_requirements": []
            }
        )
        states.append(state)
        session.add(state)
    
    await session.commit()
    logger.info(f"Seeded {len(states)} US states")
    return states


async def seed_lines_of_business(session: AsyncSession) -> List[LineOfBusiness]:
    """Seed standard lines of business.
    
    Args:
        session: Database session
        
    Returns:
        List of created LineOfBusiness objects
    """
    # Check if lines already exist
    result = await session.execute(select(LineOfBusiness))
    existing_lines = result.scalars().all()
    
    if existing_lines:
        logger.info(f"Lines of business already seeded: {len(existing_lines)} lines found")
        return existing_lines
    
    lines = []
    for line_data in LINES_OF_BUSINESS_DATA:
        line = LineOfBusiness(
            code=line_data["code"],
            name=line_data["name"],
            base_frequency=Decimal(str(line_data["base_frequency"])),
            base_severity=Decimal(str(line_data["base_severity"])),
            capital_requirement_multiplier=Decimal(str(line_data["capital_multiplier"])),
            market_characteristics=line_data["characteristics"]
        )
        lines.append(line)
        session.add(line)
    
    await session.commit()
    logger.info(f"Seeded {len(lines)} lines of business")
    return lines


async def seed_game_configuration(session: AsyncSession) -> GameConfiguration:
    """Seed default game configuration.
    
    Args:
        session: Database session
        
    Returns:
        Created GameConfiguration object
    """
    # Check if configuration already exists
    result = await session.execute(
        select(GameConfiguration).where(GameConfiguration.is_active == True)
    )
    existing_config = result.scalar_one_or_none()
    
    if existing_config:
        logger.info("Game configuration already exists")
        return existing_config
    
    config = GameConfiguration(
        name=DEFAULT_GAME_CONFIG["name"],
        version=DEFAULT_GAME_CONFIG["version"],
        is_active=DEFAULT_GAME_CONFIG["is_active"],
        economic_parameters=DEFAULT_GAME_CONFIG["economic_parameters"],
        turn_parameters=DEFAULT_GAME_CONFIG["turn_parameters"],
        initial_values=DEFAULT_GAME_CONFIG["initial_values"],
        regulatory_parameters=DEFAULT_GAME_CONFIG["regulatory_parameters"],
        employee_parameters=DEFAULT_GAME_CONFIG["employee_parameters"],
        product_parameters=DEFAULT_GAME_CONFIG["product_parameters"],
        expansion_parameters=DEFAULT_GAME_CONFIG["expansion_parameters"],
        investment_parameters=DEFAULT_GAME_CONFIG["investment_parameters"],
        claims_parameters=DEFAULT_GAME_CONFIG["claims_parameters"]
    )
    
    session.add(config)
    await session.commit()
    logger.info("Seeded default game configuration")
    return config


async def create_sample_semester(
    session: AsyncSession,
    game_config: GameConfiguration,
    name: str = "Spring 2024",
    code: str = "S24"
) -> Semester:
    """Create a sample semester for testing.
    
    Args:
        session: Database session
        game_config: Game configuration to use
        name: Semester name
        code: Semester code
        
    Returns:
        Created Semester object
    """
    # Check if semester already exists
    result = await session.execute(
        select(Semester).where(Semester.code == code)
    )
    existing_semester = result.scalar_one_or_none()
    
    if existing_semester:
        logger.info(f"Semester {code} already exists")
        return existing_semester
    
    # Calculate dates
    today = date.today()
    semester_start = today
    semester_end = today + timedelta(weeks=16)
    game_start = today + timedelta(days=7)  # Game starts 1 week after semester
    game_end = semester_end - timedelta(days=7)  # Game ends 1 week before semester
    
    semester = Semester(
        name=name,
        code=code,
        start_date=semester_start,
        end_date=semester_end,
        game_start_date=game_start,
        game_end_date=game_end,
        is_active=True,
        is_registration_open=True,
        configuration={
            "max_companies_per_user": 1,
            "allow_late_registration": True,
            "enable_tutorials": True
        },
        game_version=str(game_config.version)
    )
    
    session.add(semester)
    await session.flush()  # Get the semester ID
    
    # Create semester-specific configuration
    semester_config = SemesterConfiguration(
        semester_id=semester.id,
        base_configuration_id=game_config.id,
        feature_overrides={
            "enable_advanced_investments": False,  # Disabled for MVP
            "enable_middle_management": False,     # Disabled for MVP
            "enable_custom_products": False,       # Disabled for MVP
            "catastrophe_frequency_multiplier": 1.0,
            "enable_ai_competitors": False
        },
        custom_rules={
            "scheduled_catastrophes": [],  # No scheduled events for now
            "market_conditions": "normal",
            "special_bonuses": {}
        },
        experiment_config={}  # No experiments for default semester
    )
    
    session.add(semester_config)
    await session.commit()
    
    logger.info(f"Created sample semester: {name} ({code})")
    return semester


async def seed_all():
    """Run all seed operations.
    
    This is the main entry point for seeding the database.
    """
    logger.info("Starting database seeding...")
    
    try:
        # Initialize database connection
        await init_db()
        
        async with async_session_maker() as session:
            # Seed in order of dependencies
            states = await seed_states(session)
            lines = await seed_lines_of_business(session)
            game_config = await seed_game_configuration(session)
            semester = await create_sample_semester(session, game_config)
            
            logger.info("Database seeding completed successfully!")
            logger.info(f"Summary:")
            logger.info(f"  - States: {len(states)}")
            logger.info(f"  - Lines of Business: {len(lines)}")
            logger.info(f"  - Game Configuration: {game_config.name}")
            logger.info(f"  - Sample Semester: {semester.name}")
            
    except Exception as e:
        logger.error(f"Error during database seeding: {str(e)}")
        raise


async def reset_and_seed():
    """Reset specific tables and reseed them.
    
    WARNING: This will delete all data in the affected tables!
    Use with caution, primarily for development.
    """
    logger.warning("Resetting and reseeding database...")
    
    async with async_session_maker() as session:
        # Delete in reverse order of dependencies
        await session.execute("DELETE FROM semester_configurations")
        await session.execute("DELETE FROM semesters")
        await session.execute("DELETE FROM game_configurations")
        await session.execute("DELETE FROM lines_of_business")
        await session.execute("DELETE FROM states")
        await session.commit()
        
    # Now reseed
    await seed_all()


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the seeding
    asyncio.run(seed_all()) 