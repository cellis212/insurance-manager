"""Asset sale simulation package for crisis liquidation management.

This package provides tools for managing forced asset sales during
financial crises, including CFO skill effects on liquidation quality.
"""

from .liquidation_engine import LiquidationEngine
from .market_impact import MarketImpactModel
from .crisis_triggers import CrisisTriggerDetector

__all__ = [
    'LiquidationEngine',
    'MarketImpactModel',
    'CrisisTriggerDetector'
]
