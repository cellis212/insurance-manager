"""Health check endpoints for the Insurance Manager API.

Provides comprehensive health status for the application and its dependencies.
"""

from typing import Dict, Any
import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis

from core.database import get_session, check_database_health
from core.config import settings

router = APIRouter(tags=["health"])


async def check_redis_health() -> Dict[str, Any]:
    """Check Redis connectivity and basic health.
    
    Returns:
        dict: Redis health status
    """
    health_status = {
        "healthy": False,
        "details": {},
        "error": None
    }
    
    start_time = asyncio.get_event_loop().time()
    
    try:
        # Connect to Redis
        r = redis.from_url(settings.redis_url, decode_responses=True)
        
        # Test basic operations
        await r.ping()
        info = await r.info()
        
        health_status.update({
            "healthy": True,
            "details": {
                "response_time_ms": round((asyncio.get_event_loop().time() - start_time) * 1000, 2),
                "version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "uptime_in_days": info.get("uptime_in_days", 0),
            }
        })
        
        await r.close()
        
    except Exception as e:
        health_status["error"] = str(e)
        
    return health_status


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint.
    
    Returns:
        dict: Simple health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "insurance-manager-api",
        "version": settings.app_version
    }


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check including all dependencies.
    
    Returns:
        dict: Comprehensive health status for all components
    """
    # Run health checks concurrently
    db_health_task = asyncio.create_task(check_database_health())
    redis_health_task = asyncio.create_task(check_redis_health())
    
    # Wait for all checks to complete
    db_health = await db_health_task
    redis_health = await redis_health_task
    
    # Determine overall health
    all_healthy = all([
        db_health["healthy"],
        redis_health["healthy"]
    ])
    
    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "insurance-manager-api",
        "version": settings.app_version,
        "components": {
            "database": db_health,
            "redis": redis_health
        }
    }


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    """Kubernetes readiness probe endpoint.
    
    Checks if the service is ready to handle requests.
    
    Returns:
        dict: Readiness status
    """
    try:
        # Quick database query to ensure we can handle requests
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        
        return {
            "ready": True,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "ready": False,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/health/live")
async def liveness_check() -> Dict[str, Any]:
    """Kubernetes liveness probe endpoint.
    
    Simple check to see if the service is alive.
    
    Returns:
        dict: Liveness status
    """
    return {
        "alive": True,
        "timestamp": datetime.utcnow().isoformat()
    } 