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

# Analysis add-ons: POST /functions/run/<name> with {userId, analysisExeId}.
FUNCTION_AUDIO_FEATURES = "audio-features"
FUNCTION_AUDIO_TAGS = "audio-tags"
FUNCTION_LYRICS = "lyrics"

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
# What the music worker accepts (its generator_request.VALID_TASK_TYPES). "extract" and
# "complete" were listed here until 1.4.3 but the engine never supported them: the API now
# refuses them with 400 INVALID_INPUT, and before that they failed on the worker.
MUSIC_GENERATOR_TASK_TYPES = [
    "text2music",
    "cover",
    "remix",
    "lego",
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

# sound2serum -- same contract as sound2vital, targeting Serum 2 instead of
# Vital. The execution stays exeType "preset" with synth="serum2"; the preset
# file lands under exe_data["preset"]["presetSerumPreset"].
FUNCTION_SOUND2SERUM = "sound2serum"
# Input audio must be at most this many seconds long.
SOUND2SERUM_MAX_INPUT_DURATION = 20
# Serum runs take ~2.5 min plus a ~2.5 min cold start; leave headroom.
SOUND2SERUM_DEFAULT_MAX_WAIT = 480
SOUND2SERUM_DEFAULT_POLL_INTERVAL = 5

# text2vox
FUNCTION_TEXT2VOX = "text2vox"
EXECUTION_TYPE_TEXT2VOX = "generated"
TEXT2VOX_LYRICS_MODES = ["auto", "per_note", "1to1"]
TEXT2VOX_DEFAULT_MAX_WAIT = 360
TEXT2VOX_DEFAULT_POLL_INTERVAL = 5

# ---------------------------------------------------------------------------
# Machine warm-up (GET /functions/status, and the `warmup` object the API
# writes onto executions and pipeline steps).
# ---------------------------------------------------------------------------

# SDK function name -> the `function` key GET /functions/status reports it
# under. `audial.status()` accepts either spelling and normalises with this.
STATUS_FUNCTIONS = {
    "stem_split": FUNCTION_STEM_SPLITTER,
    "analyze": FUNCTION_PRIMARY_ANALYSIS,
    "segment": FUNCTION_SEGMENTATION,
    "master": FUNCTION_MASTERING,
    "generate_samples": FUNCTION_SAMPLE_PACK,
    "generate_midi": FUNCTION_GENERATE_MIDI,
    "generate_music": FUNCTION_MUSIC_GENERATOR,
    "sound2vital": FUNCTION_SOUND2VITAL,
    "sound2serum": FUNCTION_SOUND2SERUM,
    "text2vox": FUNCTION_TEXT2VOX,
    "audio_features": FUNCTION_AUDIO_FEATURES,
    "tags": FUNCTION_AUDIO_TAGS,
    "lyrics": FUNCTION_LYRICS,
}

# Warm-up phases written onto an execution / pipeline step.
WARMUP_STATE_COLD = "cold"
WARMUP_STATE_INITIALIZING = "initializing"
WARMUP_STATE_WORKING = "working"
WARMUP_STATE_DONE = "done"

# Execution-scoped upload filetypes (PUT /files/{userId}/execution/{exeId}/{filetype}/{filename})
FILETYPE_REFERENCE = "reference"
FILETYPE_MIDI = "midi"
FILETYPE_MELODY = "melody"
FILETYPE_WORD_TS = "word_ts"

# ---------------------------------------------------------------------------
# Pipelines (POST /pipelines): multi-step jobs run as one API call.
# ---------------------------------------------------------------------------

PIPELINE_SAMPLE_PACK = "sample-pack"
PIPELINE_SEGMENTATION = "segmentation"

# Pipeline name -> ordered step names, mirroring the server's PIPELINES table.
# segmentation: the analysis, then the add-ons featuresToExtract asks for.
# sample-pack: the analysis and its stems together ("prepare"), then the pack.
# Pipelines started before 2026-11 report "stem-split" as their first step.
PIPELINES = {
    PIPELINE_SEGMENTATION: ["segmentation", "add-ons"],
    PIPELINE_SAMPLE_PACK: ["prepare", "sample-pack"],
}

# The function whose machine a pipeline waits on first, for the CLI's
# cold-start check before it submits.
PIPELINE_FIRST_FUNCTION = {
    PIPELINE_SEGMENTATION: FUNCTION_SEGMENTATION,
    PIPELINE_SAMPLE_PACK: FUNCTION_STEM_SPLITTER,
}

# Pipeline states
PIPELINE_STATE_QUEUED = "queued"
PIPELINE_STATE_RUNNING = "running"
PIPELINE_STATE_COMPLETED = "completed"
PIPELINE_STATE_FAILED = "failed"
PIPELINE_STATE_CANCELLED = "cancelled"

# A pipeline in one of these states will not change again.
PIPELINE_TERMINAL_STATES = (
    PIPELINE_STATE_COMPLETED,
    PIPELINE_STATE_FAILED,
    PIPELINE_STATE_CANCELLED,
)

# Step states
PIPELINE_STEP_PENDING = "pending"
PIPELINE_STEP_RUNNING = "running"
PIPELINE_STEP_COMPLETED = "completed"
PIPELINE_STEP_FAILED = "failed"
PIPELINE_STEP_SKIPPED = "skipped"
PIPELINE_STEP_CANCELLED = "cancelled"

# Seconds between GET /pipelines/{id} polls while waiting for a pipeline.
DEFAULT_PIPELINE_POLL_INTERVAL = 5

# Default page size for GET /pipelines.
DEFAULT_PIPELINE_LIST_LIMIT = 20


# ---------------------------------------------------------------------------
# The analysis and its add-ons (SDK 1.6).
# ---------------------------------------------------------------------------

# SDK name of an add-on -> the function that runs it, and its key on the
# analysis record (`addons.<key>`).
ADDON_FUNCTIONS = {
    "features": FUNCTION_AUDIO_FEATURES,
    "tags": FUNCTION_AUDIO_TAGS,
    "lyrics": FUNCTION_LYRICS,
    "samplePack": FUNCTION_SAMPLE_PACK,
}

# featuresToExtract values that each add-on answers.
FEATURE_ADDONS = {
    "mode": "features",
    "energy": "features",
    "loudness": "features",
    "danceability": "features",
    "tatum": "features",
    "key": "features",
    "tags": "tags",
    "lyrics": "lyrics",
}

# The add-on run states on an analysis record.
ADDON_STATE_QUEUED = "queued"
ADDON_STATE_RUNNING = "running"
ADDON_STATE_COMPLETED = "completed"
ADDON_STATE_FAILED = "failed"
ADDON_STATE_CANCELLED = "cancelled"
ADDON_TERMINAL_STATES = (ADDON_STATE_COMPLETED, ADDON_STATE_FAILED, ADDON_STATE_CANCELLED)

# HTTP 409 codes of an add-on run that cannot start yet (or at all).
ERROR_STEMS_NOT_READY = "STEMS_NOT_READY"
ERROR_ADDON_UNAVAILABLE = "ADDON_UNAVAILABLE"
ERROR_ANALYSIS_NOT_READY = "ANALYSIS_NOT_READY"

# The words customers read for them (the same on the website and in the MCP server).
STEMS_NOT_READY_TEXT = "This track is still being prepared. Try again in a minute."
ADDON_UNAVAILABLE_TEXT = "This result can't be added to this analysis."
STEMS_FAILED_TEXT = "We couldn't prepare this track."
PREPARING_TEXT = "Preparing the track…"
INSTRUMENTAL_TEXT = "No vocals in this track."
# A tags part's line instead of its tags: a silent stem, or one with nothing to tag (as the website's tiles).
SILENT_PART_TEXT = {
    "drums": "No drums in this track.",
    "bass": "No bass in this track.",
    "melody": "No melody in this track.",
    "vocals": INSTRUMENTAL_TEXT,
}
EMPTY_PART_TEXT = "Nothing to tag in this part."

# Execution states in which an analysis is still on its way.
ANALYSIS_IN_FLIGHT_STATES = (
    EXECUTION_STATE_CREATED,
    EXECUTION_STATE_INITIALIZED,
    EXECUTION_STATE_PROCESSING,
    "queued",
    "running",
)

# How long an add-on keeps retrying while the track is being prepared
# (409 STEMS_NOT_READY), and how long it then waits for its own run.
ADDON_DEFAULT_WAIT_S = 600
ADDON_DEFAULT_MAX_WAIT = 900
ADDON_DEFAULT_POLL_INTERVAL = 5

# How long segment() waits for the analysis itself (about half a minute warm;
# the first request after a quiet period also waits for a machine to start).
ANALYSIS_DEFAULT_MAX_WAIT = 900
ANALYSIS_DEFAULT_POLL_INTERVAL = 3
