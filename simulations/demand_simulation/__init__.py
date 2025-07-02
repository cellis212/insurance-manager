"""Demand simulation package for market dynamics.

This package provides tools for simulating customer demand,
market share allocation, and competitive dynamics in insurance markets.
"""

from .elasticity_models import DemandSimulator
from .market_share import MarketShareAllocator
from .blp_integration import BLPDemandModel, ConsumerTypeGenerator

__all__ = [
    'DemandSimulator',
    'MarketShareAllocator', 
    'BLPDemandModel',
    'ConsumerTypeGenerator'
]
