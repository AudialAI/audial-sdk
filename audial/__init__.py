"""
Audial SDK: A Python package for interacting with the Audial audio processing API.
"""

__version__ = "1.3.0"

# Import and re-export public functions
from audial.functions.stem_split import stem_split
from audial.functions.analyze import analyze
from audial.functions.segment import segment
from audial.functions.master import master
from audial.functions.samples import generate_samples
from audial.functions.midi import generate_midi
from audial.functions.generate_music import generate_music
from audial.functions.sound2vital import sound2vital
from audial.functions.text2vox import text2vox

# Import config module
from audial.utils import config

# Signing in through the browser (no API key to copy)
from audial.api.device_login import login, logout

# Import exceptions
from audial.api.exceptions import (
    AudialError,
    AudialAuthError,
    AudialAPIError,
    SubscriptionRequiredError,
)

__all__ = [
    "stem_split",
    "analyze",
    "segment",
    "master",
    "generate_samples",
    "generate_midi",
    "generate_music",
    "sound2vital",
    "text2vox",
    "config",
    "login",
    "logout",
    "AudialError",
    "AudialAuthError",
    "AudialAPIError",
    "SubscriptionRequiredError",
]