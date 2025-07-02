"""Company model representing player-managed insurance companies.

The core entity that players control, managing capital, employees,
products, and geographic expansion throughout the game.
"""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from core.models.base import BaseModel

if TYPE_CHECKING:
    from core.models.user import User
    from core.models.semester import Semester
    from core.models.state import State
    from core.models.ceo import CEO
    from core.models.employee import Employee
    from core.models.product import Product
    from core.models.turn import CompanyTurnDecision, CompanyTurnResult
    from core.models.feature_flag import FeatureFlag
    from core.models.game_event import GameEvent
    from core.models.audit_log import AuditLog


class Company(BaseModel):
    """Player-managed insurance company.
    
    The main entity players control, starting with $5M capital
    in their home state and expanding from there.
    """
    
    __tablename__ = "companies"
    
    # Ownership and semester
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Player who owns this company"
    )
    
    semester_id = Column(
        UUID(as_uuid=True),
        ForeignKey("semesters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Semester this company belongs to"
    )
    
    # Basic information
    name = Column(
        String(255),
        nullable=False,
        comment="Company name chosen by player"
    )
    
    home_state_id = Column(
        UUID(as_uuid=True),
        ForeignKey("states.id"),
        nullable=False,
        comment="Home state based on player's alma mater"
    )
    
    founded_date = Column(
        Date,
        nullable=False,
        default=date.today,
        comment="In-game date when company was founded"
    )
    
    # Financial status
    current_capital = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("5000000.00"),
        comment="Current available capital"
    )
    
    total_assets = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("5000000.00"),
        comment="Total assets including investments"
    )
    
    total_liabilities = Column(
        Numeric(15, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total liabilities including reserves"
    )
    
    solvency_ratio = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Assets / Liabilities ratio"
    )
    
    # Game status
    is_active = Column(
        String(20),
        nullable=False,
        default="active",
        comment="Status: 'active', 'bankrupt', 'liquidating'"
    )
    
    turn_number = Column(
        Numeric(3, 0),
        nullable=False,
        default=0,
        comment="Current turn number for this company"
    )
    
    # Performance tracking
    market_position = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Market share and ranking by state/line"
    )
    
    operational_data = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Operational metrics and KPIs"
    )
    
    # Schema versioning for data migration
    schema_version = Column(
        Numeric(3, 0),
        nullable=False,
        default=1,
        comment="Schema version for JSONB fields"
    )
    
    # Relationships
    user = relationship(
        "User",
        back_populates="companies"
    )
    
    semester = relationship(
        "Semester",
        back_populates="companies"
    )
    
    home_state = relationship(
        "State",
        foreign_keys=[home_state_id],
        back_populates="companies_home_state"
    )
    
    ceo = relationship(
        "CEO",
        back_populates="company",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    employees = relationship(
        "Employee",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    products = relationship(
        "Product",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    state_authorizations = relationship(
        "CompanyStateAuthorization",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    lines_of_business = relationship(
        "CompanyLineOfBusiness",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    turn_decisions = relationship(
        "CompanyTurnDecision",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    turn_results = relationship(
        "CompanyTurnResult",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    feature_flags = relationship(
        "FeatureFlag",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    game_events = relationship(
        "GameEvent",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    audit_logs = relationship(
        "AuditLog",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    price_decisions = relationship(
        "PriceDecision",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    investment_portfolios = relationship(
        "InvestmentPortfolio",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    liquidation_events = relationship(
        "LiquidationEvent",
        back_populates="company",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        """String representation of the company."""
        return f"<Company(name={self.name}, capital={self.current_capital})>"
    
    @property
    def is_solvent(self) -> bool:
        """Check if company meets solvency requirements.
        
        Returns:
            Whether the company is solvent
        """
        if self.total_liabilities == 0:
            return True
        return self.solvency_ratio >= Decimal("1.25")  # 125% minimum
    
    @property
    def available_capital_for_expansion(self) -> Decimal:
        """Calculate capital available for expansion.
        
        Returns:
            Amount of capital available for new ventures
        """
        # Reserve 20% for operations and regulatory requirements
        return self.current_capital * Decimal("0.80")
    
    @property
    def weeks_in_business(self) -> int:
        """Calculate how many weeks the company has been operating.
        
        Returns:
            Number of weeks since founding
        """
        if not self.founded_date:
            return 0
        return (date.today() - self.founded_date).days // 7
    
    def get_market_share(self, state_code: str, line_code: str) -> Optional[Decimal]:
        """Get market share for a specific state and line.
        
        Args:
            state_code: Two-letter state code
            line_code: Line of business code
            
        Returns:
            Market share as decimal (0.15 = 15%) or None
        """
        key = f"{state_code}_{line_code}"
        return self.market_position.get(key, {}).get("market_share")
    
    def get_operational_metric(self, metric_key: str, default: any = None) -> any:
        """Get an operational metric value.
        
        Args:
            metric_key: The metric to retrieve
            default: Default value if not set
            
        Returns:
            The metric value or default
        """
        return self.operational_data.get(metric_key, default) 