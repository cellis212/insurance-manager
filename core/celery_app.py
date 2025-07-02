"""Celery application configuration for Insurance Manager.

This module sets up Celery for asynchronous task processing including
turn processing, notifications, and other background jobs.
"""

import logging
from celery import Celery, Task
from celery.schedules import crontab
from celery.signals import worker_ready, worker_shutdown
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)

# Create Celery application
celery_app = Celery(
    "insurance_manager",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["core.tasks.turn_processing", "core.tasks.notifications"]
)

# Configure Celery
celery_app.conf.update(
    # Task execution settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,  # Results expire after 1 hour
    timezone=settings.turn_processing_timezone,
    enable_utc=True,
    
    # Task routing
    task_default_queue="default",
    task_queues={
        "default": {
            "exchange": "default",
            "exchange_type": "direct",
            "routing_key": "default",
        },
        "turn_processing": {
            "exchange": "turn_processing",
            "exchange_type": "direct", 
            "routing_key": "turn_processing",
        },
        "notifications": {
            "exchange": "notifications",
            "exchange_type": "direct",
            "routing_key": "notifications",
        }
    },
    
    # Task time limits
    task_soft_time_limit=3600,  # 1 hour soft limit
    task_time_limit=3900,  # 1 hour 5 min hard limit
    
    # Task execution pools
    worker_pool="prefork",
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Beat scheduler settings
    beat_scheduler="celery.beat:PersistentScheduler",
    beat_schedule_filename="celerybeat-schedule",
)


class DatabaseTask(Task):
    """Base task that ensures database connections are properly handled."""
    
    _db = None
    
    @property
    def db(self):
        """Lazy database connection property."""
        if self._db is None:
            from core.database import init_db
            import asyncio
            asyncio.run(init_db())
        return self._db


# Set the base task for all tasks
celery_app.Task = DatabaseTask


# Semester-aware beat schedule
def get_beat_schedule():
    """Generate beat schedule based on current semester configuration.
    
    This function checks if a semester is active and returns the appropriate
    schedule. The schedule can be dynamically updated when semesters change.
    """
    schedule = {}
    
    # Only schedule turn processing if a semester is active
    if settings.semester_id:
        # Weekly turn processing - Monday at midnight EST/EDT
        schedule["process-weekly-turn"] = {
            "task": "core.tasks.turn_processing.process_turn",
            "schedule": crontab(
                hour=settings.turn_processing_hour,
                minute=0,
                day_of_week=1,  # Monday
            ),
            "kwargs": {"semester_id": settings.semester_id},
            "options": {
                "queue": "turn_processing",
                "priority": 10,
            }
        }
        
        # Turn submission deadline reminder - Sunday 9 PM EST/EDT
        schedule["turn-deadline-reminder"] = {
            "task": "core.tasks.notifications.send_deadline_reminder",
            "schedule": crontab(
                hour=21,
                minute=0,
                day_of_week=0,  # Sunday
            ),
            "kwargs": {"semester_id": settings.semester_id},
            "options": {
                "queue": "notifications",
                "priority": 5,
            }
        }
        
        # Grace period final warning - Sunday 11:30 PM EST/EDT
        schedule["turn-final-warning"] = {
            "task": "core.tasks.notifications.send_final_warning",
            "schedule": crontab(
                hour=23,
                minute=30,
                day_of_week=0,  # Sunday
            ),
            "kwargs": {"semester_id": settings.semester_id},
            "options": {
                "queue": "notifications",
                "priority": 8,
            }
        }
    
    # Always-active maintenance tasks
    schedule["cleanup-old-sessions"] = {
        "task": "core.tasks.maintenance.cleanup_sessions",
        "schedule": crontab(hour=3, minute=0),  # 3 AM daily
        "options": {"queue": "default"}
    }
    
    return schedule


# Apply the beat schedule
celery_app.conf.beat_schedule = get_beat_schedule()


@worker_ready.connect
def on_worker_ready(**kwargs):
    """Initialize worker when it's ready."""
    logger.info("Celery worker is ready")
    logger.info(f"Active queues: {list(celery_app.conf.task_queues.keys())}")
    logger.info(f"Timezone: {celery_app.conf.timezone}")
    
    # Log active beat schedule if this is a beat worker
    if celery_app.conf.beat_schedule:
        logger.info(f"Active scheduled tasks: {list(celery_app.conf.beat_schedule.keys())}")


@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    """Cleanup when worker shuts down."""
    logger.info("Celery worker shutting down")
    # Any cleanup code here


def update_semester_schedule(semester_id: str = None):
    """Update the beat schedule when semester changes.
    
    This function should be called when:
    - A new semester is started
    - A semester ends
    - Semester configuration changes
    
    Args:
        semester_id: The new semester ID, or None to disable semester tasks
    """
    settings.semester_id = semester_id
    celery_app.conf.beat_schedule = get_beat_schedule()
    logger.info(f"Updated beat schedule for semester: {semester_id}") 