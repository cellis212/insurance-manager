"""Demand functions for market simulation.

This module provides various demand function implementations including
placeholder functions for rapid development and testing.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union, Any
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DemandInputs:
    """Input parameters for demand calculation."""
    base_market_size: Decimal
    price: Decimal
    competitor_prices: List[Decimal]
    market_conditions: Dict[str, Any]
    company_attributes: Dict[str, float]
    product_features: Dict[str, float]


@dataclass
class DemandResult:
    """Result of demand calculation."""
    quantity_demanded: Decimal
    market_share: float
    price_elasticity: float
    competitive_position: float
    consumer_surplus: Optional[Decimal] = None


class DemandFunction(ABC):
    """Abstract base class for demand functions."""
    
    @abstractmethod
    def calculate_demand(self, inputs: DemandInputs) -> DemandResult:
        """Calculate demand based on input parameters.
        
        Args:
            inputs: DemandInputs containing all relevant parameters
            
        Returns:
            DemandResult with calculated demand and related metrics
        """
        pass
    
    @abstractmethod
    def get_price_elasticity(self, price: Decimal, inputs: DemandInputs) -> float:
        """Calculate price elasticity at given price point.
        
        Args:
            price: Price point to evaluate elasticity
            inputs: Other demand inputs
            
        Returns:
            Price elasticity (negative value)
        """
        pass


class PlaceholderDemandFunction(DemandFunction):
    """Placeholder demand function for rapid prototyping and testing.
    
    This function provides simple, predictable demand calculations that
    can be used during development before more sophisticated models are
    implemented. It uses basic linear relationships with random variation.
    """
    
    def __init__(
        self, 
        base_elasticity: float = -1.5,
        competition_factor: float = 0.8,
        random_variation: float = 0.1
    ):
        """Initialize placeholder demand function.
        
        Args:
            base_elasticity: Base price elasticity (should be negative)
            competition_factor: How much competition affects demand (0-1)
            random_variation: Random variation factor (0-1)
        """
        self.base_elasticity = base_elasticity
        self.competition_factor = competition_factor
        self.random_variation = random_variation
        
        logger.info(
            f"Initialized PlaceholderDemandFunction with elasticity={base_elasticity}, "
            f"competition_factor={competition_factor}"
        )
    
    def calculate_demand(self, inputs: DemandInputs) -> DemandResult:
        """Calculate demand using simple placeholder logic.
        
        This implementation:
        1. Calculates relative price position vs competitors
        2. Applies price elasticity to base market size
        3. Adjusts for competitive effects
        4. Adds small random variation for realism
        
        Args:
            inputs: DemandInputs containing market parameters
            
        Returns:
            DemandResult with calculated demand metrics
        """
        # Calculate average competitor price
        if inputs.competitor_prices:
            avg_competitor_price = sum(inputs.competitor_prices) / len(inputs.competitor_prices)
        else:
            avg_competitor_price = inputs.price  # No competition
        
        # Calculate relative price position (1.0 = at average, <1.0 = below average)
        if avg_competitor_price > 0:
            relative_price = float(inputs.price) / float(avg_competitor_price)
        else:
            relative_price = 1.0
        
        # Apply price elasticity to base demand
        # Lower relative prices increase demand
        price_effect = (relative_price - 1.0) * self.base_elasticity
        
        # Calculate base quantity with price effect
        base_quantity = inputs.base_market_size * Decimal(1.0 + price_effect)
        
        # Apply competitive effects
        num_competitors = len(inputs.competitor_prices)
        if num_competitors > 0:
            # More competitors reduce individual market share
            competition_effect = 1.0 / (1.0 + num_competitors * self.competition_factor)
        else:
            competition_effect = 1.0  # Monopoly
        
        # Calculate final quantity demanded
        quantity_demanded = base_quantity * Decimal(competition_effect)
        
        # Ensure non-negative demand
        quantity_demanded = max(quantity_demanded, Decimal("0"))
        
        # Calculate market share (simplified)
        total_market = inputs.base_market_size
        if total_market > 0:
            market_share = min(float(quantity_demanded / total_market), 1.0)
        else:
            market_share = 0.0
        
        # Calculate competitive position (0-1, higher is better)
        if inputs.competitor_prices:
            # Better position if price is lower than average
            competitive_position = max(0.0, min(1.0, 2.0 - relative_price))
        else:
            competitive_position = 1.0  # No competition
        
        return DemandResult(
            quantity_demanded=quantity_demanded,
            market_share=market_share,
            price_elasticity=self.base_elasticity,
            competitive_position=competitive_position
        )
    
    def get_price_elasticity(self, price: Decimal, inputs: DemandInputs) -> float:
        """Return base price elasticity (constant for placeholder function).
        
        Args:
            price: Price point (ignored in placeholder)
            inputs: Other inputs (ignored in placeholder)
            
        Returns:
            Base price elasticity
        """
        return self.base_elasticity


class LinearDemandFunction(DemandFunction):
    """Simple linear demand function implementation.
    
    Implements a basic linear demand curve: Q = a - b*P + c*X
    where Q is quantity, P is price, and X represents other factors.
    """
    
    def __init__(
        self,
        intercept: float = 10000.0,
        price_coefficient: float = -100.0,
        competition_coefficient: float = -50.0
    ):
        """Initialize linear demand function.
        
        Args:
            intercept: Base demand when price = 0
            price_coefficient: How much demand changes per unit price (negative)
            competition_coefficient: How competition affects demand (negative)
        """
        self.intercept = intercept
        self.price_coefficient = price_coefficient
        self.competition_coefficient = competition_coefficient
        
        logger.info(
            f"Initialized LinearDemandFunction: Q = {intercept} + {price_coefficient}*P + "
            f"{competition_coefficient}*C"
        )
    
    def calculate_demand(self, inputs: DemandInputs) -> DemandResult:
        """Calculate demand using linear function.
        
        Args:
            inputs: DemandInputs containing market parameters
            
        Returns:
            DemandResult with calculated demand metrics
        """
        # Calculate competition intensity (number of competitors)
        competition_intensity = len(inputs.competitor_prices)
        
        # Linear demand calculation: Q = a - b*P + c*Competition
        quantity_demanded = Decimal(
            self.intercept +
            self.price_coefficient * float(inputs.price) +
            self.competition_coefficient * competition_intensity
        )
        
        # Ensure non-negative demand
        quantity_demanded = max(quantity_demanded, Decimal("0"))
        
        # Calculate market share
        total_market = inputs.base_market_size
        if total_market > 0:
            market_share = min(float(quantity_demanded / total_market), 1.0)
        else:
            market_share = 0.0
        
        # Calculate competitive position
        if inputs.competitor_prices:
            avg_price = sum(inputs.competitor_prices) / len(inputs.competitor_prices)
            # Better position if below average price
            competitive_position = max(0.0, min(1.0, float(avg_price) / float(inputs.price)))
        else:
            competitive_position = 1.0
        
        return DemandResult(
            quantity_demanded=quantity_demanded,
            market_share=market_share,
            price_elasticity=self.price_coefficient / max(float(inputs.price), 1.0),
            competitive_position=competitive_position
        )
    
    def get_price_elasticity(self, price: Decimal, inputs: DemandInputs) -> float:
        """Calculate price elasticity for linear demand.
        
        For linear demand Q = a - b*P, elasticity = -b * (P/Q)
        
        Args:
            price: Current price
            inputs: Market inputs for calculating current quantity
            
        Returns:
            Price elasticity at given price point
        """
        # Calculate current quantity at this price
        result = self.calculate_demand(inputs)
        
        if result.quantity_demanded > 0:
            # Elasticity = (dQ/dP) * (P/Q)
            elasticity = self.price_coefficient * (float(price) / float(result.quantity_demanded))
        else:
            # Default elasticity when quantity is zero
            elasticity = self.price_coefficient
        
        return elasticity


class DemandFunctionFactory:
    """Factory for creating demand functions based on configuration."""
    
    @staticmethod
    def create_demand_function(
        function_type: str = "placeholder",
        **kwargs
    ) -> DemandFunction:
        """Create demand function of specified type.
        
        Args:
            function_type: Type of demand function ('placeholder', 'linear')
            **kwargs: Additional parameters for the demand function
            
        Returns:
            Configured demand function instance
            
        Raises:
            ValueError: If function_type is not supported
        """
        if function_type == "placeholder":
            return PlaceholderDemandFunction(**kwargs)
        elif function_type == "linear":
            return LinearDemandFunction(**kwargs)
        else:
            raise ValueError(f"Unsupported demand function type: {function_type}")
    
    @staticmethod
    def get_available_functions() -> List[str]:
        """Get list of available demand function types.
        
        Returns:
            List of supported function type names
        """
        return ["placeholder", "linear"]