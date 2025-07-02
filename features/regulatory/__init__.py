"""
Regulatory Compliance System

Manages state regulatory requirements, compliance tracking, audits, and penalties.
Key features:
- Compliance score calculation based on company behavior
- Random audits with CCO skill influence
- State-specific requirements based on regulatory category
- Grace periods and escalating penalties
"""

from .plugin import RegulatoryPlugin

__all__ = ["RegulatoryPlugin"] 