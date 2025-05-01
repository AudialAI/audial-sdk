"""
Constants for the Audial API.
"""

# Base API URL - using the auth server as proxy
# This endpoint will be responsible for routing to the actual API endpoints
API_BASE_URL = "https://starfish-app-2x28e.ondigitalocean.app/api"
AUTH_SERVER_URL = "https://starfish-app-2x28e.ondigitalocean.app/api/proxy"

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