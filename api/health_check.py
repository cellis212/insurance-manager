"""Health check module for verifying service dependencies."""

import os
import sys
import time
from sqlalchemy import create_engine, text
import redis


def check_postgres(max_retries: int = 30, retry_delay: int = 2) -> bool:
    """Check if PostgreSQL is available and ready."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return False
    
    for attempt in range(max_retries):
        try:
            engine = create_engine(database_url)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            print("PostgreSQL is ready!")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"PostgreSQL not ready (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay)
            else:
                print(f"PostgreSQL failed to become ready: {e}")
                return False
    
    return False


def check_redis(max_retries: int = 30, retry_delay: int = 2) -> bool:
    """Check if Redis is available and ready."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    for attempt in range(max_retries):
        try:
            r = redis.from_url(redis_url)
            r.ping()
            print("Redis is ready!")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Redis not ready (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay)
            else:
                print(f"Redis failed to become ready: {e}")
                return False
    
    return False


def main():
    """Run health checks for all required services."""
    print("Running health checks...")
    
    # Check all services
    postgres_ready = check_postgres()
    redis_ready = check_redis()
    
    if not postgres_ready or not redis_ready:
        print("Health checks failed!")
        sys.exit(1)
    
    print("All services are ready!")
    sys.exit(0)


if __name__ == "__main__":
    main() 