"""Database configuration and connection management for Insurance Manager.

This module provides async SQLAlchemy setup with connection pooling,
base model definitions, and session management.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import MetaData, text, pool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings

logger = logging.getLogger(__name__)

# Database URL for async PostgreSQL connection
DATABASE_URL = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

# Connection pool configuration for production use
POOL_SIZE = 20  # Number of persistent connections
MAX_OVERFLOW = 10  # Maximum overflow connections
POOL_TIMEOUT = 30  # Seconds to wait for a connection
POOL_RECYCLE = 3600  # Recycle connections after 1 hour

# Create async engine with appropriate pooling for async operations
# For async applications, NullPool is recommended to avoid connection sharing issues
# Each coroutine gets its own connection which is properly closed after use
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_pre_ping=True,
    poolclass=NullPool,  # Use NullPool for all environments to avoid async conflicts
    # Connection arguments for PostgreSQL
    connect_args={
        "server_settings": {
            "application_name": "insurance_manager",
            "jit": "off"
        },
        "command_timeout": 60,
        "timeout": 30,
    }
)

# Async session factory
async_session_maker = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Naming convention for constraints to ensure consistent migration names
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# Create metadata with naming convention
metadata = MetaData(naming_convention=naming_convention)


# Base class for all models using SQLAlchemy 2.0 style
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    metadata = metadata


# Dependency to get database session
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional scope for database operations.
    
    This is the primary way to get a database session in the application.
    It automatically handles commits and rollbacks.
    
    Yields:
        AsyncSession: Database session for the request
        
    Example:
        async with get_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error occurred: {str(e)}")
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error in database session: {str(e)}")
            raise
        finally:
            await session.close()


# Health check functionality
async def check_database_health() -> dict:
    """Check database connectivity and basic health metrics.
    
    Returns:
        dict: Health status including connectivity, pool stats, and response time
    """
    health_status = {
        "healthy": False,
        "details": {},
        "error": None
    }
    
    start_time = asyncio.get_event_loop().time()
    
    try:
        # Test basic connectivity
        async with async_session_maker() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
            
        # Get pool statistics
        pool_status = engine.pool.status() if hasattr(engine.pool, 'status') else "Pool status unavailable"
        
        health_status.update({
            "healthy": True,
            "details": {
                "response_time_ms": round((asyncio.get_event_loop().time() - start_time) * 1000, 2),
                "pool_status": pool_status,
                "pool_size": getattr(engine.pool, 'size', POOL_SIZE),
                "pool_checked_out": getattr(engine.pool, 'checked_out_connections', 0),
            }
        })
        
    except Exception as e:
        health_status["error"] = str(e)
        logger.error(f"Database health check failed: {str(e)}")
        
    return health_status


@asynccontextmanager
async def get_db_transaction():
    """Provide a database transaction context manager.
    
    This is useful when you need explicit transaction control across
    multiple operations.
    
    Example:
        async with get_db_transaction() as session:
            user = User(email="test@example.com")
            session.add(user)
            # Transaction commits on exit, rolls back on exception
    """
    async with async_session_maker() as session:
        async with session.begin():
            try:
                yield session
            except Exception:
                await session.rollback()
                raise


async def init_db():
    """Initialize database connections and verify connectivity.
    
    This should be called during application startup.
    """
    try:
        # Test the connection
        health = await check_database_health()
        if health["healthy"]:
            logger.info("Database connection established successfully")
            logger.info(f"Pool configuration: size={POOL_SIZE}, max_overflow={MAX_OVERFLOW}")
        else:
            raise RuntimeError(f"Database unhealthy: {health.get('error')}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


async def close_db():
    """Close database connections gracefully.
    
    This should be called during application shutdown.
    """
    try:
        await engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {str(e)}")
        raise 