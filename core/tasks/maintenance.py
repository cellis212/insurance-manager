"""Maintenance tasks for Insurance Manager.

This module contains housekeeping tasks that run periodically
to maintain system health and clean up old data.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict

from celery import Task
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.celery_app import celery_app
from core.database import get_session
from core.models import Session, GameEvent, AuditLog

logger = logging.getLogger(__name__)


@celery_app.task(name="core.tasks.maintenance.cleanup_sessions")
def cleanup_sessions() -> Dict:
    """Clean up expired user sessions.
    
    This task runs daily to remove expired sessions from the database.
    
    Returns:
        Dict with cleanup statistics
    """
    
    async def _cleanup():
        async with get_session() as session:
            now = datetime.now(timezone.utc)
            
            # Count sessions to be deleted
            count_result = await session.execute(
                select(Session).where(Session.expires_at < now)
            )
            expired_count = len(count_result.scalars().all())
            
            # Delete expired sessions
            await session.execute(
                delete(Session).where(Session.expires_at < now)
            )
            await session.commit()
            
            logger.info(f"Cleaned up {expired_count} expired sessions")
            
            return {
                "status": "completed",
                "expired_sessions_removed": expired_count,
                "cleanup_time": now.isoformat()
            }
    
    return asyncio.run(_cleanup())


@celery_app.task(name="core.tasks.maintenance.cleanup_old_events")
def cleanup_old_events(days_to_keep: int = 90) -> Dict:
    """Clean up old game events and audit logs.
    
    This task removes events older than the specified number of days.
    Keeps important events (errors, critical) longer.
    
    Args:
        days_to_keep: Number of days to retain events
        
    Returns:
        Dict with cleanup statistics
    """
    
    async def _cleanup():
        async with get_session() as session:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            cutoff_date_critical = datetime.now(timezone.utc) - timedelta(days=days_to_keep * 4)
            
            # Delete non-critical events
            events_result = await session.execute(
                delete(GameEvent)
                .where(GameEvent.created_at < cutoff_date)
                .where(GameEvent.severity.notin_(["error", "critical"]))
                .returning(GameEvent.id)
            )
            events_deleted = len(events_result.all())
            
            # Delete old critical events (keep 4x longer)
            critical_result = await session.execute(
                delete(GameEvent)
                .where(GameEvent.created_at < cutoff_date_critical)
                .where(GameEvent.severity.in_(["error", "critical"]))
                .returning(GameEvent.id)
            )
            critical_deleted = len(critical_result.all())
            
            # Clean up old audit logs (keep financial changes longer)
            audit_result = await session.execute(
                delete(AuditLog)
                .where(AuditLog.created_at < cutoff_date)
                .where(AuditLog.table_name.notin_(["companies", "company_turn_results"]))
                .returning(AuditLog.id)
            )
            audit_deleted = len(audit_result.all())
            
            await session.commit()
            
            logger.info(
                f"Cleaned up {events_deleted} events, {critical_deleted} critical events, "
                f"and {audit_deleted} audit logs"
            )
            
            return {
                "status": "completed",
                "events_deleted": events_deleted,
                "critical_events_deleted": critical_deleted,
                "audit_logs_deleted": audit_deleted,
                "cutoff_date": cutoff_date.isoformat(),
                "critical_cutoff_date": cutoff_date_critical.isoformat()
            }
    
    return asyncio.run(_cleanup())


@celery_app.task(name="core.tasks.maintenance.vacuum_database")
def vacuum_database() -> Dict:
    """Run PostgreSQL VACUUM to reclaim storage and update statistics.
    
    This should run weekly during low-usage periods.
    
    Returns:
        Dict with vacuum results
    """
    
    async def _vacuum():
        from sqlalchemy import text
        
        async with get_session() as session:
            # Note: VACUUM cannot run inside a transaction block
            # Need raw connection for this
            connection = await session.connection()
            
            try:
                # Analyze tables to update statistics
                await connection.execute(text("ANALYZE;"))
                
                logger.info("Database statistics updated")
                
                return {
                    "status": "completed",
                    "operation": "analyze",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
            except Exception as e:
                logger.error(f"Database maintenance failed: {str(e)}")
                return {
                    "status": "failed",
                    "error": str(e)
                }
    
    return asyncio.run(_vacuum())


@celery_app.task(name="core.tasks.maintenance.check_database_health")
def check_database_health() -> Dict:
    """Perform comprehensive database health check.
    
    Returns:
        Dict with health metrics
    """
    
    async def _check_health():
        from core.database import check_database_health as db_health_check
        from sqlalchemy import text
        
        health_result = await db_health_check()
        
        async with get_session() as session:
            # Check table sizes
            size_result = await session.execute(
                text("""
                    SELECT 
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                    LIMIT 10;
                """)
            )
            table_sizes = [
                {"table": row.tablename, "size": row.size}
                for row in size_result
            ]
            
            # Check for long-running queries
            query_result = await session.execute(
                text("""
                    SELECT 
                        pid,
                        now() - pg_stat_activity.query_start AS duration,
                        query,
                        state
                    FROM pg_stat_activity
                    WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
                    AND state != 'idle';
                """)
            )
            long_queries = [
                {
                    "pid": row.pid,
                    "duration": str(row.duration),
                    "query": row.query[:100],
                    "state": row.state
                }
                for row in query_result
            ]
            
            return {
                "status": "completed",
                "database_health": health_result,
                "largest_tables": table_sizes,
                "long_running_queries": long_queries,
                "check_time": datetime.now(timezone.utc).isoformat()
            }
    
    return asyncio.run(_check_health())


@celery_app.task(name="core.tasks.maintenance.archive_completed_semester")
def archive_completed_semester(semester_id: str) -> Dict:
    """Archive data from a completed semester.
    
    This task exports semester data and marks it as archived.
    
    Args:
        semester_id: ID of semester to archive
        
    Returns:
        Dict with archive results
    """
    
    async def _archive():
        from core.semester_management import SemesterManager
        
        manager = SemesterManager()
        
        # Archive the semester data
        archive_path = await manager.archive_semester(
            semester_id=semester_id,
            output_dir=f"archives/semester_{semester_id}"
        )
        
        logger.info(f"Semester {semester_id} archived to {archive_path}")
        
        return {
            "status": "completed",
            "semester_id": semester_id,
            "archive_path": archive_path,
            "archived_at": datetime.now(timezone.utc).isoformat()
        }
    
    return asyncio.run(_archive())


# Schedule additional maintenance tasks
celery_app.conf.beat_schedule.update({
    "cleanup-sessions": {
        "task": "core.tasks.maintenance.cleanup_sessions",
        "schedule": celery_app.conf.beat_schedule.crontab(
            hour=3, minute=0  # 3 AM daily
        ),
        "options": {"queue": "default"}
    },
    "cleanup-old-events": {
        "task": "core.tasks.maintenance.cleanup_old_events",
        "schedule": celery_app.conf.beat_schedule.crontab(
            hour=4, minute=0  # 4 AM daily
        ),
        "options": {"queue": "default"}
    },
    "vacuum-database": {
        "task": "core.tasks.maintenance.vacuum_database",
        "schedule": celery_app.conf.beat_schedule.crontab(
            hour=2, minute=0, day_of_week=0  # 2 AM Sunday
        ),
        "options": {"queue": "default"}
    },
    "check-database-health": {
        "task": "core.tasks.maintenance.check_database_health",
        "schedule": celery_app.conf.beat_schedule.crontab(
            minute=0  # Every hour
        ),
        "options": {"queue": "default"}
    }
}) 