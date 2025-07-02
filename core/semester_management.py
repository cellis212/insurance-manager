"""Semester management utilities for Insurance Manager.

Provides functionality for:
- Creating new semesters
- Resetting semesters between terms
- Archiving semester data for research
- Verifying clean initialization
"""

import asyncio
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import csv

from sqlalchemy import select, text, and_
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd

from core.database import async_session_maker, init_db, engine
from core.models import (
    Semester,
    SemesterConfiguration,
    GameConfiguration,
    Company,
    User,
    Turn,
    CompanyTurnDecision,
    CompanyTurnResult,
    GameEvent,
    AuditLog,
)

logger = logging.getLogger(__name__)


class SemesterManager:
    """Manages semester lifecycle operations."""
    
    def __init__(self, archive_path: str = "data/archives"):
        """Initialize the semester manager.
        
        Args:
            archive_path: Base path for archived semester data
        """
        self.archive_path = Path(archive_path)
        self.archive_path.mkdir(parents=True, exist_ok=True)
    
    async def create_semester(
        self,
        name: str,
        code: str,
        start_date: date,
        duration_weeks: int = 16,
        game_config_id: Optional[str] = None,
        feature_overrides: Optional[Dict[str, Any]] = None,
        custom_rules: Optional[Dict[str, Any]] = None
    ) -> Semester:
        """Create a new semester with configuration.
        
        Args:
            name: Human-readable semester name (e.g., "Fall 2024")
            code: Short semester code (e.g., "F24")
            start_date: Semester start date
            duration_weeks: Length of semester in weeks
            game_config_id: ID of game configuration to use
            feature_overrides: Feature flags for this semester
            custom_rules: Custom rules/events for this semester
            
        Returns:
            Created Semester object
        """
        async with async_session_maker() as session:
            # Check if semester already exists
            existing = await session.execute(
                select(Semester).where(Semester.code == code)
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Semester with code {code} already exists")
            
            # Get game configuration
            if not game_config_id:
                # Use active configuration
                result = await session.execute(
                    select(GameConfiguration).where(GameConfiguration.is_active == True)
                )
                game_config = result.scalar_one_or_none()
                if not game_config:
                    raise ValueError("No active game configuration found")
                game_config_id = game_config.id
            
            # Calculate dates
            end_date = start_date + timedelta(weeks=duration_weeks)
            game_start = start_date + timedelta(days=7)  # Game starts 1 week in
            game_end = end_date - timedelta(days=7)  # Game ends 1 week early
            
            # Create semester
            semester = Semester(
                name=name,
                code=code,
                start_date=start_date,
                end_date=end_date,
                game_start_date=game_start,
                game_end_date=game_end,
                is_active=False,  # Not active until explicitly activated
                is_registration_open=True,
                configuration={
                    "max_companies_per_user": 1,
                    "allow_late_registration": True,
                    "enable_tutorials": True,
                    "created_at": datetime.utcnow().isoformat()
                },
                game_version="1.0.0"
            )
            
            session.add(semester)
            await session.flush()
            
            # Create semester configuration
            semester_config = SemesterConfiguration(
                semester_id=semester.id,
                base_configuration_id=game_config_id,
                feature_overrides=feature_overrides or {
                    "enable_advanced_investments": False,
                    "enable_middle_management": False,
                    "enable_custom_products": False,
                    "catastrophe_frequency_multiplier": 1.0,
                    "enable_ai_competitors": False
                },
                custom_rules=custom_rules or {
                    "scheduled_catastrophes": [],
                    "market_conditions": "normal",
                    "special_bonuses": {}
                },
                experiment_config={}
            )
            
            session.add(semester_config)
            await session.commit()
            
            logger.info(f"Created new semester: {name} ({code})")
            return semester
    
    async def activate_semester(self, semester_code: str) -> None:
        """Activate a semester and deactivate all others.
        
        Args:
            semester_code: Code of semester to activate
        """
        async with async_session_maker() as session:
            # Deactivate all semesters
            await session.execute(
                text("UPDATE semesters SET is_active = FALSE")
            )
            
            # Activate the specified semester
            result = await session.execute(
                select(Semester).where(Semester.code == semester_code)
            )
            semester = result.scalar_one_or_none()
            
            if not semester:
                raise ValueError(f"Semester {semester_code} not found")
            
            semester.is_active = True
            await session.commit()
            
            logger.info(f"Activated semester: {semester_code}")
    
    async def verify_clean_state(self, semester_id: str) -> Dict[str, Any]:
        """Verify a semester is in a clean initial state.
        
        Args:
            semester_id: ID of semester to verify
            
        Returns:
            Verification results including any issues found
        """
        issues = []
        stats = {}
        
        async with async_session_maker() as session:
            # Check semester exists
            result = await session.execute(
                select(Semester).where(Semester.id == semester_id)
            )
            semester = result.scalar_one_or_none()
            
            if not semester:
                return {"valid": False, "error": "Semester not found"}
            
            # Count entities
            company_count = await session.scalar(
                select(Company).where(Company.semester_id == semester_id).count()
            )
            turn_count = await session.scalar(
                select(Turn).where(Turn.semester_id == semester_id).count()
            )
            
            stats["companies"] = company_count
            stats["turns"] = turn_count
            
            # Check for issues
            if company_count > 0:
                issues.append(f"Found {company_count} existing companies")
            
            if turn_count > 0:
                issues.append(f"Found {turn_count} existing turns")
            
            # Check dates
            today = date.today()
            if semester.game_start_date <= today:
                issues.append("Game has already started")
            
            if not semester.is_registration_open:
                issues.append("Registration is closed")
        
        return {
            "valid": len(issues) == 0,
            "semester": {
                "name": semester.name,
                "code": semester.code,
                "is_active": semester.is_active
            },
            "stats": stats,
            "issues": issues
        }
    
    async def archive_semester_data(self, semester_code: str) -> Path:
        """Archive all data for a semester to files.
        
        Args:
            semester_code: Code of semester to archive
            
        Returns:
            Path to archive directory
        """
        logger.info(f"Starting archive for semester {semester_code}")
        
        # Create archive directory
        archive_dir = self.archive_path / semester_code / datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        async with async_session_maker() as session:
            # Get semester
            result = await session.execute(
                select(Semester).where(Semester.code == semester_code)
            )
            semester = result.scalar_one_or_none()
            
            if not semester:
                raise ValueError(f"Semester {semester_code} not found")
            
            # Archive metadata
            metadata = {
                "semester_id": str(semester.id),
                "semester_name": semester.name,
                "semester_code": semester.code,
                "archived_at": datetime.utcnow().isoformat(),
                "game_version": semester.game_version,
                "start_date": semester.start_date.isoformat(),
                "end_date": semester.end_date.isoformat()
            }
            
            with open(archive_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)
            
            # Archive companies
            await self._archive_companies(session, semester.id, archive_dir)
            
            # Archive turns and results
            await self._archive_turns(session, semester.id, archive_dir)
            
            # Archive events
            await self._archive_events(session, semester.id, archive_dir)
            
            # Archive audit logs
            await self._archive_audit_logs(session, semester.id, archive_dir)
        
        logger.info(f"Archive completed: {archive_dir}")
        return archive_dir
    
    async def _archive_companies(self, session: AsyncSession, semester_id: str, archive_dir: Path):
        """Archive company data to CSV."""
        query = """
            SELECT 
                c.id,
                c.name,
                u.email as owner_email,
                s.code as home_state,
                c.founded_date,
                c.current_capital,
                c.total_assets,
                c.total_liabilities,
                c.solvency_ratio,
                c.is_active,
                c.turn_number,
                c.created_at,
                c.updated_at
            FROM companies c
            JOIN users u ON c.user_id = u.id
            JOIN states s ON c.home_state_id = s.id
            WHERE c.semester_id = :semester_id
        """
        
        result = await session.execute(text(query), {"semester_id": semester_id})
        rows = result.fetchall()
        
        if rows:
            df = pd.DataFrame(rows, columns=result.keys())
            df.to_csv(archive_dir / "companies.csv", index=False)
            logger.info(f"Archived {len(df)} companies")
    
    async def _archive_turns(self, session: AsyncSession, semester_id: str, archive_dir: Path):
        """Archive turn results to CSV and JSON."""
        # Get all turns
        result = await session.execute(
            select(Turn).where(Turn.semester_id == semester_id).order_by(Turn.turn_number)
        )
        turns = result.scalars().all()
        
        turn_data = []
        results_dir = archive_dir / "turn_results"
        results_dir.mkdir(exist_ok=True)
        
        for turn in turns:
            turn_data.append({
                "turn_number": turn.turn_number,
                "start_time": turn.start_time.isoformat(),
                "end_time": turn.end_time.isoformat(),
                "processing_completed_at": turn.processing_completed_at.isoformat() if turn.processing_completed_at else None,
                "status": turn.status,
                "special_rules": turn.special_rules
            })
            
            # Get turn results
            result = await session.execute(
                select(CompanyTurnResult).where(CompanyTurnResult.turn_id == turn.id)
            )
            turn_results = result.scalars().all()
            
            if turn_results:
                # Save detailed results as JSON
                results_data = []
                for tr in turn_results:
                    results_data.append({
                        "company_id": str(tr.company_id),
                        "premiums_written": float(tr.premiums_written),
                        "premiums_earned": float(tr.premiums_earned),
                        "claims_incurred": float(tr.claims_incurred),
                        "operating_expenses": float(tr.operating_expenses),
                        "investment_income": float(tr.investment_income),
                        "net_income": float(tr.net_income),
                        "loss_ratio": float(tr.loss_ratio) if tr.loss_ratio else None,
                        "expense_ratio": float(tr.expense_ratio) if tr.expense_ratio else None,
                        "combined_ratio": float(tr.combined_ratio) if tr.combined_ratio else None,
                        "ending_capital": float(tr.ending_capital),
                        "financial_details": tr.financial_details,
                        "market_results": tr.market_results,
                        "operational_metrics": tr.operational_metrics
                    })
                
                with open(results_dir / f"turn_{turn.turn_number:02d}_results.json", "w") as f:
                    json.dump(results_data, f, indent=2)
        
        # Save turn summary
        if turn_data:
            df = pd.DataFrame(turn_data)
            df.to_csv(archive_dir / "turns.csv", index=False)
            logger.info(f"Archived {len(turn_data)} turns")
    
    async def _archive_events(self, session: AsyncSession, semester_id: str, archive_dir: Path):
        """Archive game events to CSV."""
        query = """
            SELECT 
                event_type,
                category,
                severity,
                company_id,
                turn_id,
                event_data,
                triggered_by,
                created_at
            FROM game_events
            WHERE semester_id = :semester_id
            ORDER BY created_at
        """
        
        result = await session.execute(text(query), {"semester_id": semester_id})
        rows = result.fetchall()
        
        if rows:
            # Save summary to CSV
            summary_data = []
            for row in rows:
                summary_data.append({
                    "created_at": row.created_at,
                    "event_type": row.event_type,
                    "category": row.category,
                    "severity": row.severity,
                    "triggered_by": row.triggered_by
                })
            
            df = pd.DataFrame(summary_data)
            df.to_csv(archive_dir / "events_summary.csv", index=False)
            
            # Save full events as JSON
            events_data = [dict(row._mapping) for row in rows]
            with open(archive_dir / "events_full.json", "w") as f:
                json.dump(events_data, f, indent=2, default=str)
            
            logger.info(f"Archived {len(rows)} events")
    
    async def _archive_audit_logs(self, session: AsyncSession, semester_id: str, archive_dir: Path):
        """Archive audit logs to CSV."""
        query = """
            SELECT 
                entity_type,
                entity_id,
                change_type,
                changed_by_user_id,
                changed_by_system,
                change_reason,
                changed_fields,
                created_at
            FROM audit_logs
            WHERE semester_id = :semester_id
            ORDER BY created_at
        """
        
        result = await session.execute(text(query), {"semester_id": semester_id})
        rows = result.fetchall()
        
        if rows:
            df = pd.DataFrame(rows, columns=result.keys())
            df.to_csv(archive_dir / "audit_logs.csv", index=False)
            logger.info(f"Archived {len(rows)} audit logs")
    
    async def reset_semester(self, semester_code: str, archive_first: bool = True) -> None:
        """Reset a semester by removing all game data.
        
        Args:
            semester_code: Code of semester to reset
            archive_first: Whether to archive data before deleting
        """
        logger.warning(f"Resetting semester {semester_code}")
        
        if archive_first:
            await self.archive_semester_data(semester_code)
        
        async with async_session_maker() as session:
            # Get semester
            result = await session.execute(
                select(Semester).where(Semester.code == semester_code)
            )
            semester = result.scalar_one_or_none()
            
            if not semester:
                raise ValueError(f"Semester {semester_code} not found")
            
            semester_id = semester.id
            
            # Delete in order of dependencies
            # Note: Most have CASCADE delete, but being explicit
            await session.execute(
                text("DELETE FROM company_turn_results WHERE turn_id IN (SELECT id FROM turns WHERE semester_id = :sid)"),
                {"sid": semester_id}
            )
            await session.execute(
                text("DELETE FROM company_turn_decisions WHERE turn_id IN (SELECT id FROM turns WHERE semester_id = :sid)"),
                {"sid": semester_id}
            )
            await session.execute(
                text("DELETE FROM audit_logs WHERE semester_id = :sid"),
                {"sid": semester_id}
            )
            await session.execute(
                text("DELETE FROM game_events WHERE semester_id = :sid"),
                {"sid": semester_id}
            )
            await session.execute(
                text("DELETE FROM turns WHERE semester_id = :sid"),
                {"sid": semester_id}
            )
            await session.execute(
                text("DELETE FROM companies WHERE semester_id = :sid"),
                {"sid": semester_id}
            )
            
            # Reset semester state
            semester.is_active = False
            semester.is_registration_open = True
            
            await session.commit()
            
        logger.info(f"Semester {semester_code} reset complete")
    
    async def get_semester_statistics(self, semester_code: str) -> Dict[str, Any]:
        """Get detailed statistics for a semester.
        
        Args:
            semester_code: Code of semester to analyze
            
        Returns:
            Dictionary of statistics
        """
        async with async_session_maker() as session:
            # Get semester
            result = await session.execute(
                select(Semester).where(Semester.code == semester_code)
            )
            semester = result.scalar_one_or_none()
            
            if not semester:
                raise ValueError(f"Semester {semester_code} not found")
            
            stats = {
                "semester": {
                    "name": semester.name,
                    "code": semester.code,
                    "is_active": semester.is_active,
                    "weeks_completed": (date.today() - semester.game_start_date).days // 7
                }
            }
            
            # Company statistics
            company_stats = await session.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_companies,
                        COUNT(CASE WHEN is_active = 'active' THEN 1 END) as active_companies,
                        COUNT(CASE WHEN is_active = 'bankrupt' THEN 1 END) as bankrupt_companies,
                        AVG(current_capital) as avg_capital,
                        MAX(current_capital) as max_capital,
                        MIN(current_capital) as min_capital
                    FROM companies
                    WHERE semester_id = :sid
                """),
                {"sid": semester.id}
            )
            stats["companies"] = dict(company_stats.fetchone()._mapping)
            
            # Turn statistics
            turn_stats = await session.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_turns,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_turns,
                        AVG(EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at))) as avg_processing_seconds
                    FROM turns
                    WHERE semester_id = :sid
                """),
                {"sid": semester.id}
            )
            stats["turns"] = dict(turn_stats.fetchone()._mapping)
            
            # Event statistics
            event_stats = await session.execute(
                text("""
                    SELECT 
                        category,
                        COUNT(*) as count
                    FROM game_events
                    WHERE semester_id = :sid
                    GROUP BY category
                """),
                {"sid": semester.id}
            )
            stats["events_by_category"] = {
                row.category: row.count for row in event_stats
            }
            
            return stats


# Convenience functions for common operations
async def create_new_semester(
    name: str,
    code: str,
    start_date: date,
    **kwargs
) -> Semester:
    """Create a new semester using the default manager.
    
    Args:
        name: Semester name
        code: Semester code
        start_date: Start date
        **kwargs: Additional arguments for create_semester
        
    Returns:
        Created semester
    """
    manager = SemesterManager()
    return await manager.create_semester(name, code, start_date, **kwargs)


async def reset_current_semester(archive_first: bool = True) -> None:
    """Reset the currently active semester.
    
    Args:
        archive_first: Whether to archive before reset
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(Semester).where(Semester.is_active == True)
        )
        active_semester = result.scalar_one_or_none()
        
        if not active_semester:
            raise ValueError("No active semester found")
        
        manager = SemesterManager()
        await manager.reset_semester(active_semester.code, archive_first)


if __name__ == "__main__":
    # Example usage
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def main():
        if len(sys.argv) < 2:
            print("Usage: python semester_management.py [create|reset|archive|stats] [args...]")
            return
        
        await init_db()
        manager = SemesterManager()
        
        command = sys.argv[1]
        
        if command == "create":
            if len(sys.argv) < 4:
                print("Usage: python semester_management.py create <name> <code>")
                return
            
            semester = await manager.create_semester(
                name=sys.argv[2],
                code=sys.argv[3],
                start_date=date.today()
            )
            print(f"Created semester: {semester.name}")
            
        elif command == "reset":
            if len(sys.argv) < 3:
                print("Usage: python semester_management.py reset <code>")
                return
            
            await manager.reset_semester(sys.argv[2])
            print(f"Reset semester: {sys.argv[2]}")
            
        elif command == "archive":
            if len(sys.argv) < 3:
                print("Usage: python semester_management.py archive <code>")
                return
            
            path = await manager.archive_semester_data(sys.argv[2])
            print(f"Archived to: {path}")
            
        elif command == "stats":
            if len(sys.argv) < 3:
                print("Usage: python semester_management.py stats <code>")
                return
            
            stats = await manager.get_semester_statistics(sys.argv[2])
            print(json.dumps(stats, indent=2, default=str))
    
    asyncio.run(main()) 