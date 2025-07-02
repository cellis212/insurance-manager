#!/usr/bin/env python3
"""
Initial data loading script for Insurance Manager.

This script sets up a fresh database with all necessary data:
1. Runs database migrations
2. Loads base game data (states, lines of business, game config)
3. Loads universities and academic backgrounds
4. Creates an initial semester
5. Verifies data loaded correctly

Usage:
    python scripts/load_initial_data.py
    
Options:
    --semester-code: Code for the semester (default: S24)
    --semester-name: Name for the semester (default: Spring 2024)
    --start-date: Start date in YYYY-MM-DD format (default: today)
"""

import asyncio
import logging
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
import argparse
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import async_session_maker, init_db
from core.seed_data import seed_all
from core.semester_management import SemesterManager
from core.config_loader import ConfigurationLoader
from core.models import (
    State,
    LineOfBusiness,
    GameConfiguration,
    Semester,
    Company,
    Turn,
    FeatureFlag,
)
from features.ceo_system.data.university_loader import UniversityDataLoader
from features.ceo_system.models.university import University
from features.ceo_system.models.academic_background import AcademicBackground

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataLoader:
    """Handles initial data loading for the Insurance Manager."""
    
    def __init__(self):
        """Initialize the data loader."""
        self.semester_manager = SemesterManager()
        self.university_loader = UniversityDataLoader()
        self.verification_results = {}
    
    async def run_migrations(self) -> bool:
        """Run database migrations using Alembic.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Running database migrations...")
        
        try:
            # Run alembic upgrade head
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info("Migrations completed successfully")
            logger.debug(f"Migration output: {result.stdout}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Migration failed: {e.stderr}")
            return False
    
    async def load_base_data(self) -> bool:
        """Load base game data (states, lines, config).
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Loading base game data...")
        
        try:
            # This will load states, lines of business, and game configuration
            await seed_all()
            return True
            
        except Exception as e:
            logger.error(f"Failed to load base data: {str(e)}")
            return False
    
    async def load_university_data(self) -> bool:
        """Load university and academic background data.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Loading university data...")
        
        try:
            async with async_session_maker() as session:
                # Load universities
                uni_count = await self.university_loader.load_universities(session)
                logger.info(f"Loaded {uni_count} universities")
                
                # Load academic backgrounds
                bg_count = await self.university_loader.load_academic_backgrounds(session)
                logger.info(f"Loaded {bg_count} academic backgrounds")
                
                await session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to load university data: {str(e)}")
            return False
    
    async def create_semester(
        self,
        code: str = "S24",
        name: str = "Spring 2024",
        start_date: date = None,
        config_file: str = None
    ) -> bool:
        """Create an initial semester.
        
        Args:
            code: Semester code
            name: Semester name
            start_date: Start date (defaults to today)
            config_file: Path to semester config YAML (optional)
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Creating semester: {name} ({code})")
        
        try:
            if start_date is None:
                start_date = date.today()
            
            # Load semester configuration if provided
            feature_overrides = None
            custom_rules = None
            
            if config_file:
                config_path = Path(config_file)
                if config_path.exists():
                    loader = ConfigurationLoader()
                    config = loader.load_config(config_path)
                    # Convert to database format
                    db_config = loader.export_to_database_format(config)
                    feature_overrides = db_config.get('feature_overrides', {})
                    custom_rules = db_config.get('custom_rules', {})
                else:
                    logger.warning(f"Config file not found: {config_file}")
            
            # Create the semester
            semester = await self.semester_manager.create_semester(
                name=name,
                code=code,
                start_date=start_date,
                duration_weeks=16,
                feature_overrides=feature_overrides,
                custom_rules=custom_rules
            )
            
            # Activate the semester
            await self.semester_manager.activate_semester(code)
            
            logger.info(f"Semester created and activated: {semester.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create semester: {str(e)}")
            return False
    
    async def create_feature_flags(self) -> bool:
        """Create default feature flags for plugins.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Creating feature flags...")
        
        try:
            async with async_session_maker() as session:
                # Get active semester
                result = await session.execute(
                    select(Semester).where(Semester.is_active == True)
                )
                semester = result.scalar_one_or_none()
                
                if not semester:
                    logger.error("No active semester found")
                    return False
                
                # Define default plugin flags
                plugin_flags = [
                    {
                        "feature_key": "plugin.CEOSystemPlugin",
                        "description": "CEO character system with universities and attributes",
                        "enabled": True,
                        "scope": "global"
                    },
                    {
                        "feature_key": "plugin.ExpansionSystemPlugin", 
                        "description": "Geographic expansion system",
                        "enabled": True,
                        "scope": "global"
                    },
                    {
                        "feature_key": "plugin.ProductSystemPlugin",
                        "description": "Three-tier product system",
                        "enabled": True,
                        "scope": "global"
                    },
                    {
                        "feature_key": "plugin.InvestmentManagerPlugin",
                        "description": "Investment portfolio management",
                        "enabled": True,
                        "scope": "global"
                    },
                    {
                        "feature_key": "plugin.RegulatoryCompliancePlugin",
                        "description": "Regulatory compliance tracking",
                        "enabled": True,
                        "scope": "global"
                    },
                    {
                        "feature_key": "plugin.MarketEventsPlugin",
                        "description": "Market events and economic cycles",
                        "enabled": True,
                        "scope": "global"
                    }
                ]
                
                # Create flags
                for flag_data in plugin_flags:
                    # Check if already exists
                    result = await session.execute(
                        select(FeatureFlag).where(FeatureFlag.feature_key == flag_data["feature_key"])
                    )
                    if result.scalar_one_or_none():
                        continue
                    
                    flag = FeatureFlag(**flag_data)
                    session.add(flag)
                
                await session.commit()
                logger.info(f"Created {len(plugin_flags)} feature flags")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create feature flags: {str(e)}")
            return False
    
    async def verify_data(self) -> Dict[str, Any]:
        """Verify all data loaded correctly.
        
        Returns:
            Dictionary with verification results
        """
        logger.info("Verifying loaded data...")
        
        results = {
            "success": True,
            "checks": {}
        }
        
        async with async_session_maker() as session:
            # Check states
            state_count = await session.scalar(select(func.count(State.id)))
            results["checks"]["states"] = {
                "expected": 51,
                "actual": state_count,
                "passed": state_count == 51
            }
            if not results["checks"]["states"]["passed"]:
                results["success"] = False
            
            # Check lines of business
            line_count = await session.scalar(select(func.count(LineOfBusiness.id)))
            results["checks"]["lines_of_business"] = {
                "expected": 5,
                "actual": line_count,
                "passed": line_count == 5
            }
            if not results["checks"]["lines_of_business"]["passed"]:
                results["success"] = False
            
            # Check game configuration
            config_count = await session.scalar(
                select(func.count(GameConfiguration.id)).where(
                    GameConfiguration.is_active == True
                )
            )
            results["checks"]["game_configuration"] = {
                "expected": 1,
                "actual": config_count,
                "passed": config_count == 1
            }
            if not results["checks"]["game_configuration"]["passed"]:
                results["success"] = False
            
            # Check universities
            uni_count = await session.scalar(select(func.count(University.id)))
            results["checks"]["universities"] = {
                "expected_min": 70,
                "actual": uni_count,
                "passed": uni_count >= 70
            }
            if not results["checks"]["universities"]["passed"]:
                results["success"] = False
            
            # Check academic backgrounds
            bg_count = await session.scalar(select(func.count(AcademicBackground.id)))
            results["checks"]["academic_backgrounds"] = {
                "expected": 4,
                "actual": bg_count,
                "passed": bg_count == 4
            }
            if not results["checks"]["academic_backgrounds"]["passed"]:
                results["success"] = False
            
            # Check active semester
            semester_count = await session.scalar(
                select(func.count(Semester.id)).where(Semester.is_active == True)
            )
            results["checks"]["active_semester"] = {
                "expected": 1,
                "actual": semester_count,
                "passed": semester_count == 1
            }
            if not results["checks"]["active_semester"]["passed"]:
                results["success"] = False
            
            # Check feature flags
            flag_count = await session.scalar(select(func.count(FeatureFlag.id)))
            results["checks"]["feature_flags"] = {
                "expected_min": 6,
                "actual": flag_count,
                "passed": flag_count >= 6
            }
            if not results["checks"]["feature_flags"]["passed"]:
                results["success"] = False
        
        self.verification_results = results
        return results
    
    async def run(
        self,
        semester_code: str = "S24",
        semester_name: str = "Spring 2024",
        start_date: date = None,
        config_file: str = None
    ) -> bool:
        """Run the complete data loading process.
        
        Args:
            semester_code: Code for the semester
            semester_name: Name for the semester
            start_date: Start date for the semester
            config_file: Path to semester config YAML
            
        Returns:
            True if all steps successful, False otherwise
        """
        logger.info("Starting initial data loading process...")
        
        steps = [
            ("Database migrations", self.run_migrations),
            ("Base game data", self.load_base_data),
            ("University data", self.load_university_data),
            ("Feature flags", self.create_feature_flags),
            ("Semester creation", lambda: self.create_semester(
                semester_code, semester_name, start_date, config_file
            )),
        ]
        
        for step_name, step_func in steps:
            logger.info(f"\n{'='*60}")
            logger.info(f"Step: {step_name}")
            logger.info(f"{'='*60}")
            
            success = await step_func()
            if not success:
                logger.error(f"Failed at step: {step_name}")
                return False
        
        # Verify everything loaded
        logger.info(f"\n{'='*60}")
        logger.info("Verification")
        logger.info(f"{'='*60}")
        
        verification = await self.verify_data()
        
        # Print verification results
        for check_name, check_result in verification["checks"].items():
            status = "✓" if check_result["passed"] else "✗"
            logger.info(f"{status} {check_name}: {check_result}")
        
        if verification["success"]:
            logger.info("\n✅ All data loaded successfully!")
            logger.info("\nYou can now:")
            logger.info("1. Start the backend: docker-compose up")
            logger.info("2. Access the API at: http://localhost:8000")
            logger.info("3. View API docs at: http://localhost:8000/docs")
        else:
            logger.error("\n❌ Some verification checks failed!")
            logger.error("Please review the errors above and try again.")
        
        return verification["success"]


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Load initial data for Insurance Manager")
    parser.add_argument(
        "--semester-code",
        default="S24",
        help="Semester code (default: S24)"
    )
    parser.add_argument(
        "--semester-name",
        default="Spring 2024",
        help="Semester name (default: Spring 2024)"
    )
    parser.add_argument(
        "--start-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
        help="Start date in YYYY-MM-DD format (default: today)"
    )
    parser.add_argument(
        "--config-file",
        default="config/semester_configs/example_semester.yaml",
        help="Path to semester config YAML file"
    )
    
    args = parser.parse_args()
    
    # Initialize database connection
    await init_db()
    
    # Run data loader
    loader = DataLoader()
    success = await loader.run(
        semester_code=args.semester_code,
        semester_name=args.semester_name,
        start_date=args.start_date,
        config_file=args.config_file
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main()) 