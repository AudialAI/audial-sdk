"""
Audial SDK: A Python package for interacting with the Audial audio processing API.
"""

__version__ = "1.0.0"

# Import and re-export public functions
from audial.functions.stem_split import stem_split
from audial.functions.analyze import analyze
from audial.functions.segment import segment
from audial.functions.master import master
from audial.functions.samples import generate_samples
from audial.functions.midi import generate_midi

# Import config module
from audial.utils import config

# Import exceptions
from audial.api.exceptions import AudialError, AudialAuthError, AudialAPIError

__all__ = [
    "stem_split",
    "analyze",
    "segment",
    "master",
    "generate_samples",
    "generate_midi",
    "config",
    "AudialError",
    "AudialAuthError",
    "AudialAPIError",
]