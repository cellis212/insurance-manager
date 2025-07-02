#!/usr/bin/env python3
"""
Test database connection for Insurance Manager.

This script verifies that:
1. Environment variables are set correctly
2. Database connection can be established
3. Basic queries work

Usage:
    python scripts/test_db_connection.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import async_session_maker, init_db, check_database_health
from core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_connection():
    """Test database connection and basic operations."""
    logger.info("Testing Insurance Manager database connection...")
    
    # Check environment variables
    logger.info("\n1. Checking environment variables:")
    
    required_settings = {
        "DATABASE_URL": settings.database_url,
        "REDIS_URL": settings.redis_url,
        "SECRET_KEY": settings.secret_key
    }
    missing_vars = []
    
    for var_name, value in required_settings.items():
        if value and value != "your-secret-key-here-change-in-production":
            # Mask sensitive parts
            if "://" in value:
                parts = value.split("://")
                if len(parts) > 1 and "@" in parts[1]:
                    user_pass, rest = parts[1].split("@", 1)
                    masked = f"{parts[0]}://***@{rest}"
                else:
                    masked = value
            else:
                masked = "***" if var_name == "SECRET_KEY" else value
            logger.info(f"  ✓ {var_name}: {masked}")
        else:
            logger.error(f"  ✗ {var_name}: NOT SET or using default")
            if var_name == "SECRET_KEY":
                missing_vars.append(var_name)
    
    if missing_vars:
        logger.error(f"\n❌ Missing environment variables: {', '.join(missing_vars)}")
        logger.error("Please update the SECRET_KEY in your .env file.")
        return False
    
    # Test database connection
    logger.info("\n2. Testing database connection:")
    
    try:
        await init_db()
        logger.info("  ✓ Database initialization successful")
    except Exception as e:
        logger.error(f"  ✗ Database initialization failed: {str(e)}")
        return False
    
    # Test basic query
    logger.info("\n3. Testing basic database query:")
    
    try:
        async with async_session_maker() as session:
            result = await session.execute(text("SELECT 1"))
            value = result.scalar()
            if value == 1:
                logger.info("  ✓ Basic query successful")
            else:
                logger.error(f"  ✗ Unexpected query result: {value}")
                return False
    except Exception as e:
        logger.error(f"  ✗ Query failed: {str(e)}")
        return False
    
    # Test table existence
    logger.info("\n4. Checking for existing tables:")
    
    try:
        async with async_session_maker() as session:
            # Check if migrations have been run
            result = await session.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
            )
            tables = [row[0] for row in result.fetchall()]
            
            if tables:
                logger.info(f"  ✓ Found {len(tables)} tables:")
                for table in tables[:10]:  # Show first 10
                    logger.info(f"    - {table}")
                if len(tables) > 10:
                    logger.info(f"    ... and {len(tables) - 10} more")
            else:
                logger.warning("  ⚠ No tables found - migrations may need to be run")
    except Exception as e:
        logger.error(f"  ✗ Failed to check tables: {str(e)}")
        return False
    
    # Test health check
    logger.info("\n5. Running health check:")
    
    try:
        health = await check_database_health()
        logger.info(f"  ✓ Database is healthy: {health}")
    except Exception as e:
        logger.error(f"  ✗ Health check failed: {str(e)}")
        return False
    
    logger.info("\n✅ All database connection tests passed!")
    logger.info("\nYou can now run: python scripts/load_initial_data.py")
    return True


async def main():
    """Main entry point."""
    success = await test_connection()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main()) 