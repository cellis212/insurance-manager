"""Notification tasks for Insurance Manager.

This module handles all notification-related tasks including
turn reminders, deadline warnings, and result notifications.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List
from uuid import UUID

from celery import Task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.celery_app import celery_app
from core.database import get_session
from core.models import (
    Company, User, Turn, CompanyTurnDecision,
    CompanyTurnResult
)

logger = logging.getLogger(__name__)


@celery_app.task(name="core.tasks.notifications.send_deadline_reminder")
def send_deadline_reminder(semester_id: str) -> Dict:
    """Send reminder notifications 3 hours before turn deadline.
    
    This task runs Sunday at 9 PM EST to remind players to submit decisions.
    
    Args:
        semester_id: Current semester ID
        
    Returns:
        Dict with notification statistics
    """
    
    async def _send_reminders():
        async with get_session() as session:
            # Get current turn
            turn_result = await session.execute(
                select(Turn)
                .where(Turn.semester_id == UUID(semester_id))
                .where(Turn.status == "pending")
                .order_by(Turn.week_number.desc())
                .limit(1)
            )
            turn = turn_result.scalar_one_or_none()
            
            if not turn:
                logger.warning(f"No pending turn found for semester {semester_id}")
                return {"status": "no_turn", "notifications_sent": 0}
            
            # Get companies that haven't submitted
            submitted_result = await session.execute(
                select(CompanyTurnDecision.company_id)
                .where(CompanyTurnDecision.turn_id == turn.id)
            )
            submitted_ids = {row[0] for row in submitted_result.all()}
            
            # Get all active companies
            companies_result = await session.execute(
                select(Company)
                .where(Company.semester_id == turn.semester_id)
                .where(Company.status == "active")
            )
            companies = companies_result.scalars().all()
            
            notifications_sent = 0
            for company in companies:
                if company.id not in submitted_ids:
                    # Send reminder (placeholder - would integrate with email/SMS service)
                    logger.info(f"Sending deadline reminder to company {company.id}")
                    notifications_sent += 1
                    
                    # In a real implementation, would:
                    # - Look up user contact preferences
                    # - Send email/SMS/in-app notification
                    # - Track notification delivery status
            
            return {
                "status": "completed",
                "turn_id": str(turn.id),
                "notifications_sent": notifications_sent,
                "companies_pending": len(companies) - len(submitted_ids)
            }
    
    return asyncio.run(_send_reminders())


@celery_app.task(name="core.tasks.notifications.send_final_warning")
def send_final_warning(semester_id: str) -> Dict:
    """Send final warning 30 minutes before turn deadline.
    
    This task runs Sunday at 11:30 PM EST as last chance reminder.
    
    Args:
        semester_id: Current semester ID
        
    Returns:
        Dict with notification statistics
    """
    
    async def _send_warnings():
        async with get_session() as session:
            # Similar logic to deadline reminder but more urgent
            turn_result = await session.execute(
                select(Turn)
                .where(Turn.semester_id == UUID(semester_id))
                .where(Turn.status == "pending")
                .order_by(Turn.week_number.desc())
                .limit(1)
            )
            turn = turn_result.scalar_one_or_none()
            
            if not turn:
                return {"status": "no_turn", "warnings_sent": 0}
            
            # Get companies that still haven't submitted
            submitted_result = await session.execute(
                select(CompanyTurnDecision.company_id)
                .where(CompanyTurnDecision.turn_id == turn.id)
            )
            submitted_ids = {row[0] for row in submitted_result.all()}
            
            companies_result = await session.execute(
                select(Company)
                .where(Company.semester_id == turn.semester_id)
                .where(Company.status == "active")
            )
            companies = companies_result.scalars().all()
            
            warnings_sent = 0
            for company in companies:
                if company.id not in submitted_ids:
                    logger.warning(f"Sending FINAL warning to company {company.id}")
                    warnings_sent += 1
                    
                    # Would send urgent notification here
            
            return {
                "status": "completed",
                "turn_id": str(turn.id),
                "warnings_sent": warnings_sent,
                "deadline_minutes": 30
            }
    
    return asyncio.run(_send_warnings())


@celery_app.task(name="core.tasks.notifications.send_turn_completed")
def send_turn_completed(turn_id: str) -> Dict:
    """Send notifications when turn processing is complete.
    
    Args:
        turn_id: ID of the completed turn
        
    Returns:
        Dict with notification statistics
    """
    
    async def _send_completed():
        async with get_session() as session:
            # Get turn details
            turn_result = await session.execute(
                select(Turn).where(Turn.id == UUID(turn_id))
            )
            turn = turn_result.scalar_one()
            
            # Get all companies with results
            results = await session.execute(
                select(CompanyTurnResult)
                .where(CompanyTurnResult.turn_id == turn.id)
            )
            company_results = results.scalars().all()
            
            notifications_sent = 0
            for result in company_results:
                # Send result notification
                logger.info(
                    f"Notifying company {result.company_id} of turn {turn.week_number} results"
                )
                notifications_sent += 1
                
                # In a real implementation would:
                # - Format result summary
                # - Send via preferred channel
                # - Include key metrics and alerts
            
            return {
                "status": "completed",
                "turn_id": turn_id,
                "week_number": turn.week_number,
                "notifications_sent": notifications_sent
            }
    
    return asyncio.run(_send_completed())


@celery_app.task(name="core.tasks.notifications.send_bankruptcy_notice")
def send_bankruptcy_notice(company_id: str, turn_id: str) -> Dict:
    """Send bankruptcy notification to affected company.
    
    Args:
        company_id: ID of bankrupt company
        turn_id: Turn when bankruptcy occurred
        
    Returns:
        Dict with notification details
    """
    
    async def _send_bankruptcy():
        async with get_session() as session:
            # Get company and user details
            company_result = await session.execute(
                select(Company).where(Company.id == UUID(company_id))
            )
            company = company_result.scalar_one()
            
            # Get turn details
            turn_result = await session.execute(
                select(Turn).where(Turn.id == UUID(turn_id))
            )
            turn = turn_result.scalar_one()
            
            logger.critical(
                f"Company {company.name} declared bankrupt in week {turn.week_number}"
            )
            
            # Would send urgent notification to player
            # Would also notify instructors/administrators
            
            return {
                "status": "sent",
                "company_id": company_id,
                "company_name": company.name,
                "turn_week": turn.week_number,
                "notification_type": "bankruptcy"
            }
    
    return asyncio.run(_send_bankruptcy())


@celery_app.task(name="core.tasks.notifications.send_expansion_approved")
def send_expansion_approved(company_id: str, state_name: str) -> Dict:
    """Send notification when state expansion is approved.
    
    Args:
        company_id: Company that received approval
        state_name: State that approved expansion
        
    Returns:
        Dict with notification details
    """
    
    logger.info(f"Company {company_id} approved for expansion in {state_name}")
    
    # Placeholder for expansion approval notification
    # Would integrate with notification service
    
    return {
        "status": "sent",
        "company_id": company_id,
        "state": state_name,
        "notification_type": "expansion_approved"
    }


@celery_app.task(name="core.tasks.notifications.send_regulatory_action")
def send_regulatory_action(company_id: str, action_type: str, details: Dict) -> Dict:
    """Send notification of regulatory action against company.
    
    Args:
        company_id: Affected company
        action_type: Type of regulatory action
        details: Action details
        
    Returns:
        Dict with notification details
    """
    
    logger.warning(
        f"Regulatory action {action_type} against company {company_id}: {details}"
    )
    
    # Placeholder for regulatory action notification
    
    return {
        "status": "sent",
        "company_id": company_id,
        "action_type": action_type,
        "notification_type": "regulatory_action"
    } 