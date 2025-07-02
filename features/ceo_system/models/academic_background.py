"""Academic Background model for CEO education tracking."""

from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB

from core.models.base import BaseModel


class AcademicBackground(BaseModel):
    """Academic background configurations for CEO creation.
    
    This table stores the available academic background combinations
    and their associated bonuses for CEO attributes.
    """
    
    __tablename__ = "academic_backgrounds"
    
    # Unique identifier
    code = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique code for the background (e.g., 'rmi_finance')"
    )
    
    # Display information
    name = Column(
        String(100),
        nullable=False,
        comment="Display name (e.g., 'Risk Management & Finance')"
    )
    
    description = Column(
        String(500),
        nullable=False,
        comment="Description of the background's focus and benefits"
    )
    
    # Major components
    primary_major = Column(
        String(100),
        nullable=False,
        default="Risk Management & Insurance",
        comment="Primary major (always RMI for this game)"
    )
    
    secondary_major = Column(
        String(100),
        nullable=False,
        comment="Secondary major or concentration"
    )
    
    # Attribute bonuses
    attribute_bonuses = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="CEO attribute bonuses from this background"
    )
    
    # Special features
    special_perks = Column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Special perks or abilities from this background"
    )
    
    # Availability
    is_active = Column(
        String(5),
        nullable=False,
        default="true",
        comment="Whether this background is available for selection"
    )
    
    def __repr__(self) -> str:
        """String representation of the academic background."""
        return f"<AcademicBackground(code={self.code}, name={self.name})>"
    
    def get_bonus(self, attribute: str) -> int:
        """Get the bonus for a specific CEO attribute.
        
        Args:
            attribute: The CEO attribute name
            
        Returns:
            The bonus value (0 if no bonus)
        """
        return self.attribute_bonuses.get(attribute, 0)
    
    def has_perk(self, perk_code: str) -> bool:
        """Check if this background has a specific perk.
        
        Args:
            perk_code: The perk code to check
            
        Returns:
            Whether the background has this perk
        """
        return perk_code in self.special_perks 