"""University model for CEO alma mater tracking."""

from sqlalchemy import Column, ForeignKey, String, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.models.base import BaseModel


class University(BaseModel):
    """University entity for tracking CEO alma maters.
    
    This table stores real US universities to provide accurate
    home state advantages based on where the CEO studied.
    """
    
    __tablename__ = "universities"
    
    # Basic information
    name = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Official university name"
    )
    
    # Location
    state_id = Column(
        UUID(as_uuid=True),
        ForeignKey("states.id"),
        nullable=False,
        index=True,
        comment="State where university is located"
    )
    
    city = Column(
        String(100),
        nullable=False,
        comment="City where main campus is located"
    )
    
    # Classification
    institution_type = Column(
        String(50),
        nullable=False,
        default="4-year",
        comment="Type: 4-year, 2-year, graduate-only"
    )
    
    control = Column(
        String(50),
        nullable=False,
        default="private",
        comment="Control: public, private, for-profit"
    )
    
    # Size and prestige indicators
    enrollment = Column(
        Numeric(8, 0),
        nullable=True,
        comment="Total student enrollment"
    )
    
    has_business_school = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether university has a business school"
    )
    
    has_rmi_program = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether university has Risk Management & Insurance program"
    )
    
    # Common nicknames or abbreviations
    aliases = Column(
        String(500),
        nullable=True,
        comment="Common aliases separated by semicolons (e.g., 'UGA;Georgia')"
    )
    
    # Relationships
    state = relationship("State", back_populates="universities")
    
    def __repr__(self) -> str:
        """String representation of the university."""
        return f"<University(name={self.name}, state={self.state_id})>"
    
    @property
    def is_major_rmi_school(self) -> bool:
        """Check if this is a major RMI program school.
        
        Returns:
            Whether this university has a notable RMI program
        """
        # Major RMI programs (can be expanded)
        major_rmi_schools = [
            "University of Georgia",
            "Temple University", 
            "University of Wisconsin-Madison",
            "Georgia State University",
            "Florida State University",
            "University of Pennsylvania",
            "St. John's University",
            "Illinois State University",
            "University of South Carolina",
            "Appalachian State University"
        ]
        
        return self.name in major_rmi_schools or self.has_rmi_program
    
    def matches_name(self, query: str) -> bool:
        """Check if a query string matches this university.
        
        Args:
            query: Search query (can be full name or alias)
            
        Returns:
            Whether the query matches this university
        """
        query_lower = query.lower().strip()
        
        # Check main name
        if query_lower == self.name.lower():
            return True
        
        # Check aliases
        if self.aliases:
            aliases = [a.strip().lower() for a in self.aliases.split(";")]
            if query_lower in aliases:
                return True
        
        # Partial match on main name
        if query_lower in self.name.lower():
            return True
        
        return False 