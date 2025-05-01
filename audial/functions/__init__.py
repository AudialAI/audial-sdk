"""
Core functions for the Audial SDK.
"""

from audial.functions.stem_split import stem_split
from audial.functions.analyze import analyze
from audial.functions.segment import segment
from audial.functions.master import master
from audial.functions.samples import generate_samples
from audial.functions.midi import generate_midi

__all__ = [
    "stem_split",
    "analyze",
    "segment",
    "master",
    "generate_samples",
    "generate_midi",
]