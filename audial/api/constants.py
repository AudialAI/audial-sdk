"""
Constants for the Audial API.
"""

import os

# Production API host. Override with the AUDIAL_API_BASE_URL environment
# variable to point the SDK at a different deployment (staging, a local mock
# server, a self-hosted instance) without code changes.
DEFAULT_API_BASE_URL = "https://api.audialmusic.ai/api"


def get_api_base_url() -> str:
    """
    Return the Audial API base URL, honoring the AUDIAL_API_BASE_URL
    environment variable override if it is set.

    This is a function (rather than a plain module constant) so callers can
    set the environment variable at any point before instantiating
    AudialProxy and have it take effect -- useful for tests and for
    switching deployments within a single process.
    """
    return os.environ.get("AUDIAL_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")


# Base API URL - using the auth server as proxy
# This endpoint will be responsible for routing to the actual API endpoints
# Resolved once at import time for backward-compatible module-level access;
# code that must honor a post-import env var change should call
# get_api_base_url() directly (AudialProxy does this in __init__).
API_BASE_URL = get_api_base_url()
AUTH_SERVER_URL = f"{API_BASE_URL}/proxy"

# Function names as defined in the API
FUNCTION_STEM_SPLITTER = "stem-splitter"
FUNCTION_PRIMARY_ANALYSIS = "primary-analysis"
FUNCTION_SEGMENTATION = "segmentation"
FUNCTION_MASTERING = "mastering"
FUNCTION_SAMPLE_PACK = "sample-pack"
FUNCTION_GENERATE_MIDI = "generate-midi"

# Execution types
EXECUTION_TYPE_STEM = "stem"
EXECUTION_TYPE_MODIFIED = "modified"
EXECUTION_TYPE_MASTER = "master"
EXECUTION_TYPE_MIDI = "midi"
EXECUTION_TYPE_SAMPLES = "samples"
EXECUTION_TYPE_SEGMENTATION = "segmentation"

# Execution states
EXECUTION_STATE_CREATED = "created"
EXECUTION_STATE_INITIALIZED = "initialized"
EXECUTION_STATE_PROCESSING = "processing"
EXECUTION_STATE_COMPLETED = "completed"
EXECUTION_STATE_FAILED = "failed"

# Default stem options
DEFAULT_STEM_OPTIONS = ["vocals", "drums", "bass", "other"]

# Available stem options
ALL_STEM_OPTIONS = [
    "vocals", 
    "drums", 
    "bass", 
    "other",
    "full_song_without_vocals",
    "full_song_without_drums",
    "full_song_without_bass",
    "full_song_without_other"
]

# Default polling interval for checking execution status (in seconds)
DEFAULT_POLLING_INTERVAL = 2

# Maximum number of retries for API requests
MAX_RETRIES = 3

# Timeout for API requests (in seconds)
REQUEST_TIMEOUT = 60

# Default values for segmentation
DEFAULT_SEGMENTATION_COMPONENTS = ["intro", "verse", "chorus", "outro"]
DEFAULT_SEGMENTATION_FEATURES = ["energy", "tempo", "loudness"]

# Music Generator
FUNCTION_MUSIC_GENERATOR = "music-generator"
EXECUTION_TYPE_MUSIC_GENERATOR = "generated"

# Music Generator task types
MUSIC_GENERATOR_TASK_TYPES = [
    "text2music",
    "cover",
    "remix",
    "extract",
    "lego",
    "complete",
    "understand",
]

# Music Generator defaults
DEFAULT_INFERENCE_STEPS = 50
DEFAULT_GUIDANCE_SCALE = 7.0
DEFAULT_BATCH_SIZE = 1
DEFAULT_AUDIO_FORMAT = "mp3"
DEFAULT_AUDIO_DURATION = 60
DEFAULT_VOCAL_LANGUAGE = "en"
DEFAULT_AUDIO_COVER_STRENGTH = 1.0

# Valid audio output formats
AUDIO_FORMATS = ["mp3", "flac", "wav", "opus", "aac"]

# sound2vital
FUNCTION_SOUND2VITAL = "sound2vital"
EXECUTION_TYPE_PRESET = "preset"
# Input audio must be at most this many seconds long.
SOUND2VITAL_MAX_INPUT_DURATION = 20
# Typical job runtime is 60-250s; leave headroom for polling.
SOUND2VITAL_DEFAULT_MAX_WAIT = 360
SOUND2VITAL_DEFAULT_POLL_INTERVAL = 5

# text2vox
FUNCTION_TEXT2VOX = "text2vox"
EXECUTION_TYPE_TEXT2VOX = "generated"
TEXT2VOX_LYRICS_MODES = ["auto", "per_note", "1to1"]
TEXT2VOX_DEFAULT_MAX_WAIT = 360
TEXT2VOX_DEFAULT_POLL_INTERVAL = 5

# Execution-scoped upload filetypes (PUT /files/{userId}/execution/{exeId}/{filetype}/{filename})
FILETYPE_REFERENCE = "reference"
FILETYPE_MIDI = "midi"
FILETYPE_MELODY = "melody"
FILETYPE_WORD_TS = "word_ts"