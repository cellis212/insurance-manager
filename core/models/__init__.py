"""Core models package for Insurance Manager.

This module imports all database models to ensure they are registered
with SQLAlchemy's metadata for Alembic auto-generation.
"""

# Import base model utilities
from core.models.base import BaseModel, TimestampMixin

# Import all models for Alembic auto-detection
from core.models.audit_log import AuditLog
from core.models.ceo import CEO
from core.models.company import Company
from core.models.company_line_of_business import CompanyLineOfBusiness
from core.models.company_state_authorization import CompanyStateAuthorization
from core.models.employee import Employee
from core.models.feature_flag import FeatureFlag
from core.models.game_configuration import GameConfiguration
from core.models.game_event import GameEvent
from core.models.investment_portfolio import InvestmentPortfolio
from core.models.line_of_business import LineOfBusiness
from core.models.liquidation_event import LiquidationEvent
from core.models.market_condition import MarketCondition
from core.models.price_decision import PriceDecision
from core.models.product import Product
from core.models.semester import Semester
from core.models.semester_configuration import SemesterConfiguration
from core.models.session import Session
from core.models.state import State
from core.models.turn import Turn
from core.models.turn_decision import CompanyTurnDecision
from core.models.turn_result import CompanyTurnResult
from core.models.user import User

__all__ = [
    "AuditLog",
    "BaseModel", 
    "TimestampMixin",
    "CEO",
    "Company",
    "CompanyLineOfBusiness",
    "CompanyStateAuthorization",
    "CompanyTurnDecision",
    "CompanyTurnResult",
    "Employee",
    "FeatureFlag",
    "GameConfiguration",
    "GameEvent",
    "InvestmentPortfolio",
    "LineOfBusiness",
    "LiquidationEvent",
    "MarketCondition",
    "PriceDecision",
    "Product",
    "Semester",
    "SemesterConfiguration",
    "Session",
    "State", 
    "Turn",
    "User",
] 