"""Insurance Manager simulation modules.

This package contains all simulation components used by the game engine
and plugins to model market dynamics, claims, and investment decisions.
"""

# Import all simulation modules for easy access
from . import demand_simulation
from . import claims_simulation
from . import asset_purchase_simulation
from . import asset_sale_simulation

__all__ = [
    'demand_simulation',
    'claims_simulation',
    'asset_purchase_simulation',
    'asset_sale_simulation'
]
