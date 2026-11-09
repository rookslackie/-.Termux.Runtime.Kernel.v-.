"""Ξ.Emergence — the field that finds its own order.

A local, deterministic Kuramoto phase network. Nothing in this package is
decorative: every number the interface shows is integrated from the equations
in `field.py` and each committed transition is receipted by `store.py`.
"""

from .field import EmergenceField, GLYPH_OPERATORS, OPERATORS
from .engine import EmergenceEngine
from .store import EmergenceLedger

__all__ = [
    "EmergenceField",
    "EmergenceEngine",
    "EmergenceLedger",
    "GLYPH_OPERATORS",
    "OPERATORS",
]
