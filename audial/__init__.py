"""
Audial SDK: A Python package for interacting with the Audial audio processing API.
"""

__version__ = "1.5.1"

# Pipelines: multi-step jobs (audial.pipelines.run/get/cancel/list).
# Imported before the functions below, which build on it.
from audial import pipelines

# Machine warm-up (audial.warmup, audial.status) and per-note lyrics
# (audial.lyrics). Imported before the functions, which use both.
from audial import lyrics
from audial import warmup
from audial.lyrics import text2vox_tokens
from audial.status import status

# Import and re-export public functions
from audial.functions.stem_split import stem_split
from audial.functions.analyze import analyze
from audial.functions.segment import segment
from audial.functions.master import master
from audial.functions.samples import generate_samples
from audial.functions.midi import generate_midi
from audial.functions.generate_music import generate_music
from audial.functions.sound2vital import sound2vital
from audial.functions.sound2serum import sound2serum
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
    AudialValidationError,
    SubscriptionRequiredError,
)

__all__ = [
    "pipelines",
    "lyrics",
    "warmup",
    "status",
    "text2vox_tokens",
    "stem_split",
    "analyze",
    "segment",
    "master",
    "generate_samples",
    "generate_midi",
    "generate_music",
    "sound2vital",
    "sound2serum",
    "text2vox",
    "config",
    "login",
    "logout",
    "AudialError",
    "AudialAuthError",
    "AudialAPIError",
    "AudialValidationError",
    "SubscriptionRequiredError",
]
