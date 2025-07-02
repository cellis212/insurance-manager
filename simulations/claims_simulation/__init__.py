"""Claims simulation package for insurance loss generation.

This package provides tools for simulating insurance claims including:
- Frequency/severity modeling
- Catastrophe events
- Adverse selection effects
"""

from .frequency_severity import FrequencySeverityModel
from .catastrophe_events import CatastropheSimulator
from .adverse_selection import AdverseSelectionModel

__all__ = [
    'FrequencySeverityModel',
    'CatastropheSimulator',
    'AdverseSelectionModel'
]
