# Audial SDK API Documentation

This document provides comprehensive documentation for the Audial SDK, including detailed information about all functions, parameters, return values, and examples for both the Python API and Command Line Interface (CLI).

## Table of Contents

- [Python API](#python-api)
  - [Configuration](#configuration)
  - [Stem Splitting](#stem-splitting)
  - [Audio Analysis](#audio-analysis)
  - [Audio Segmentation](#audio-segmentation)
  - [Audio Mastering](#audio-mastering)
  - [Sample Pack Generation](#sample-pack-generation)
  - [MIDI Generation](#midi-generation)
  - [Error Handling](#error-handling)
- [Command Line Interface](#command-line-interface)
  - [Configuration Commands](#configuration-commands)
  - [Stem Splitting Commands](#stem-splitting-commands)
  - [Audio Analysis Commands](#audio-analysis-commands)
  - [Audio Segmentation Commands](#audio-segmentation-commands)
  - [Audio Mastering Commands](#audio-mastering-commands)
  - [Sample Pack Generation Commands](#sample-pack-generation-commands)
  - [MIDI Generation Commands](#midi-generation-commands)
- [Result Data Structure](#result-data-structure)

## Python API

### Configuration

#### Setting API Key and User ID

```python
import audial

# Set API key
audial.config.set_api_key("your_api_key_here")

# Set User ID
audial.config.set_user_id("your_user_id_here")

# Get current API key and User ID
api_key = audial.config.get_api_key()
user_id = audial.config.get_user_id()
```

#### Setting Results Folder

```python
# Set custom results folder
audial.config.set_results_folder("path/to/custom/folder")

# Get current results folder
results_folder = audial.config.get_results_folder()
```

### Stem Splitting

Split an audio track into its component parts.

#### Function Signature

```python
audial.stem_split(
    file_path: str,
    stems: Optional[List[str]] = None,
    target_bpm: Optional[float] = None,
    target_key: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    algorithm: str = "primaudio"
) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | Yes | - | Path to the audio file to process |
| `stems` | List[str] | No | `["vocals", "drums", "bass", "other"]` | List of stems to extract |
| `target_bpm` | float | No | `None` | Target BPM for tempo adjustment |
| `target_key` | str | No | `None` | Target key for pitch adjustment (e.g., "Cmaj", "Dmin") |
| `results_folder` | str | No | `None` | Folder to save results (uses default if `None`) |
| `api_key` | str | No | `None` | API key to use (uses default if `None`) |
| `algorithm` | str | No | `"primaudio"` | Algorithm to use (`"primaudio"` or `"quintessound"`) |

#### Available Stem Options

- `vocals` - Vocal track
- `drums` - Drum track
- `bass` - Bass track
- `other` - All other instruments
- `full_song_without_vocals` - Full mix minus vocals
- `full_song_without_drums` - Full mix minus drums
- `full_song_without_bass` - Full mix minus bass
- `full_song_without_other` - Full mix minus other instruments

#### Returns

A dictionary containing:
- `execution`: API response data
- `files`: Information about downloaded files
  - `folder`: Path to the results folder
  - `files`: Dictionary mapping filenames to local file paths

#### Example

```python
import audial

# Basic stem splitting
result = audial.stem_split("path/to/audio.mp3")

# Access the paths to the downloaded files
stems_folder = result["files"]["folder"]
vocals_path = result["files"]["files"]["vocals.mp3"]
drums_path = result["files"]["files"]["drums.mp3"]
bass_path = result["files"]["files"]["bass.mp3"]
other_path = result["files"]["files"]["other.mp3"]

# Advanced stem splitting with options
result = audial.stem_split(
    "path/to/audio.mp3",
    stems=["vocals", "drums", "full_song_without_vocals"],
    target_bpm=120,
    target_key="Cmaj",
    algorithm="primaudio"
)
```

### Audio Analysis

Analyze an audio file to extract metadata like BPM, key, and other characteristics.

#### Function Signature

```python
audial.analyze(
    file_path: str,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | Yes | - | Path to the audio file to analyze |
| `results_folder` | str | No | `None` | Folder to save results (uses default if `None`) |
| `api_key` | str | No | `None` | API key to use (uses default if `None`) |

#### Returns

A dictionary containing:
- `execution`: API response data
- `analysis`: Analysis results including BPM, key, and other metadata
- `files`: Information about downloaded files
  - `folder`: Path to the results folder
  - `files`: Dictionary mapping filenames to local file paths

#### Example

```python
import audial

# Analyze an audio file
analysis = audial.analyze("path/to/audio.mp3")

# Access analysis results
bpm = analysis["analysis"]["bpm"]
key = analysis["analysis"]["key"]

print(f"BPM: {bpm}")
print(f"Key: {key}")
```

### Audio Segmentation

Segment an audio track into logical sections and analyze its components.

#### Function Signature

```python
audial.segment(
    file_path: str,
    components: Optional[List[str]] = None,
    analysis_type: Optional[str] = None,
    features: Optional[List[str]] = None,
    genre: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | Yes | - | Path to the audio file to segment |
| `components` | List[str] | No | `["bass", "beat", "melody", "vocal"]` | Components to segment |
| `analysis_type` | str | No | `"select_features"` | Type of analysis to perform |
| `features` | List[str] | No | `["mode", "energy", "loudness", "danceability", "tatum", "lyrics", "tags"]` | Features to extract |
| `genre` | str | No | `"Default"` | Genre of the track |
| `results_folder` | str | No | `None` | Folder to save results (uses default if `None`) |
| `api_key` | str | No | `None` | API key to use (uses default if `None`) |

#### Available Features

- `mode` - Musical mode
- `energy` - Energy level
- `loudness` - Loudness level
- `danceability` - Danceability rating
- `tatum` - Tatum features
- `lyrics` - Lyrics detection
- `key` - Musical key
- `tags` - Audio tags

#### Available Genres

`"Default"`, `"Afro House"`, `"Tech House"`, `"Bass House"`, `"Blues"`, `"Breakbeat"`, `"Classic Rock"`, `"Country"`, `"Deep House"`, `"Drum N Bass"`, `"Dubstep"`, `"Gospel"`, `"Grime140"`, `"House"`, `"Indie"`, `"Jazz"`, `"Latin"`, `"Metal"`, `"Minimal House"`, `"Pop"`, `"R&B"`, `"Rock"`, `"Techno"`, `"Trance"`, `"Trap"`, `"UK Garage"`

#### Returns

A dictionary containing:
- `execution`: API response data
- `segmentation`: Segmentation data (if available)
- `files`: Information about downloaded files
  - `folder`: Path to the results folder
  - `files`: Dictionary mapping filenames to local file paths

#### Example

```python
import audial

# Basic segmentation
segments = audial.segment("path/to/audio.mp3")

# Advanced segmentation with options
segments = audial.segment(
    "path/to/audio.mp3",
    components=["bass", "beat", "melody", "vocal"],
    analysis_type="select_features",
    features=["energy", "loudness", "danceability", "tatum"],
    genre="Tech House"
)

# Access segmentation files
json_file = segments["files"]["files"].get("audio_segmentation.json")
```

### Audio Mastering

Apply professional mastering to an audio file.

#### Function Signature

```python
audial.master(
    file_path: str,
    reference_file: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | Yes | - | Path to the audio file to master |
| `reference_file` | str | No | `None` | Path to a reference file to match sound characteristics |
| `results_folder` | str | No | `None` | Folder to save results (uses default if `None`) |
| `api_key` | str | No | `None` | API key to use (uses default if `None`) |

#### Returns

A dictionary containing:
- `execution`: API response data
- `files`: Information about downloaded files
  - `folder`: Path to the results folder
  - `files`: Dictionary mapping filenames to local file paths

#### Example

```python
import audial

# Basic mastering
mastered = audial.master("path/to/audio.mp3")

# Mastering with reference track
mastered = audial.master(
    "path/to/audio.mp3",
    reference_file="path/to/reference.mp3"
)

# Get the path to the mastered file
master_file = next(iter(mastered["files"]["files"].values()))
```

### Sample Pack Generation

Generate a sample pack from an audio file.

#### Function Signature

```python
audial.generate_samples(
    file_path: str,
    job_type: Optional[str] = None,
    components: Optional[List[str]] = None,
    genre: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | Yes | - | Path to the audio file |
| `job_type` | str | No | `"sample_pack"` | Type of sample pack job to run |
| `components` | List[str] | No | `["drums", "bass", "melody"]` | Components to include in the sample pack |
| `genre` | str | No | `"Default"` | Genre of the track |
| `results_folder` | str | No | `None` | Folder to save results (uses default if `None`) |
| `api_key` | str | No | `None` | API key to use (uses default if `None`) |

#### Available Components

- `drums` - Drum samples
- `bass` - Bass samples
- `melody` - Melodic samples

#### Available Genres

Same as [Audio Segmentation](#audio-segmentation).

#### Returns

A dictionary containing:
- `execution`: API response data
- `files`: Information about downloaded files
  - `folder`: Path to the results folder
  - `files`: Dictionary mapping filenames to local file paths

#### Example

```python
import audial

# Basic sample pack generation
samples = audial.generate_samples("path/to/audio.mp3")

# Advanced sample pack generation with options
samples = audial.generate_samples(
    "path/to/audio.mp3",
    job_type="sample_pack",
    components=["drums", "bass", "melody"],
    genre="Tech House"
)

# Access the sample pack folder
samples_folder = samples["files"]["folder"]

# List all downloaded samples
for sample_name, sample_path in samples["files"]["files"].items():
    print(f"{sample_name}: {sample_path}")
```

### MIDI Generation

Convert audio to MIDI data.

#### Function Signature

```python
audial.generate_midi(
    file_path: Union[str, List[str]],
    bpm: Optional[float] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str or List[str] | Yes | - | Path to one or more audio files |
| `bpm` | float | No | `None` | Override BPM for the MIDI generation |
| `results_folder` | str | No | `None` | Folder to save results (uses default if `None`) |
| `api_key` | str | No | `None` | API key to use (uses default if `None`) |

#### Returns

A dictionary containing:
- `execution`: API response data
- `files`: Information about downloaded files
  - `folder`: Path to the results folder
  - `files`: Dictionary mapping filenames to local file paths

#### Example

```python
import audial

# Generate MIDI from a single file
midi = audial.generate_midi("path/to/audio.mp3", bpm=120)

# Generate MIDI from multiple files
midi = audial.generate_midi(
    ["path/to/file1.mp3", "path/to/file2.mp3"],
    bpm=140
)

# Access the MIDI files
for midi_file, file_path in midi["files"]["files"].items():
    print(f"{midi_file}: {file_path}")
```

### Error Handling

The SDK provides custom exception classes for better error handling:

```python
from audial.api.exceptions import AudialError, AudialAuthError, AudialAPIError

try:
    result = audial.stem_split("path/to/audio.mp3")
except AudialAuthError as e:
    print(f"Authentication error: {e}")
    # Handle authentication issues
except AudialAPIError as e:
    print(f"API error: {e}")
    # Handle API-specific issues
except AudialError as e:
    print(f"General error: {e}")
    # Handle other errors
```

## Command Line Interface

The Audial SDK provides a command-line interface for all its functions.

### Configuration Commands

#### Show Current Configuration

```bash
audial config show
```

#### Set API Key

```bash
audial config --api-key your_api_key_here
```

#### Set User ID

```bash
audial config --user-id your_user_id_here
```

#### Set Results Folder

```bash
audial config --results-folder path/to/results/folder
```

### Stem Splitting Commands

#### Basic Stem Splitting

```bash
audial stem-split path/to/audio.mp3
```

#### Custom Stems

```bash
audial stem-split path/to/audio.mp3 --stems vocals,drums,bass,other
```

#### Full Song Without Specific Stems

```bash
audial stem-split path/to/audio.mp3 --stems full_song_without_vocals,full_song_without_drums
```

#### Tempo Adjustment

```bash
audial stem-split path/to/audio.mp3 --target-bpm 120
```

#### Key Adjustment

```bash
audial stem-split path/to/audio.mp3 --target-key Cmaj
```

#### Algorithm Selection

```bash
audial stem-split path/to/audio.mp3 --algorithm primaudio
```

```bash
audial stem-split path/to/audio.mp3 --algorithm quintessound
```

#### Custom Results Folder

```bash
audial stem-split path/to/audio.mp3 --results-folder path/to/custom/folder
```

#### Custom API Key

```bash
audial stem-split path/to/audio.mp3 --api-key your_custom_api_key
```

### Audio Analysis Commands

#### Basic Analysis

```bash
audial analyze path/to/audio.mp3
```

#### Custom Results Folder

```bash
audial analyze path/to/audio.mp3 --results-folder path/to/custom/folder
```

#### Custom API Key

```bash
audial analyze path/to/audio.mp3 --api-key your_custom_api_key
```

### Audio Segmentation Commands

#### Basic Segmentation

```bash
audial segment path/to/audio.mp3
```

#### Custom Features

```bash
audial segment path/to/audio.mp3 --features energy,loudness,danceability,tatum
```

#### Specific Genre

```bash
audial segment path/to/audio.mp3 --genre "Tech House"
```

#### Analysis Type

```bash
audial segment path/to/audio.mp3 --analysis-type select_features
```

#### Custom Results Folder

```bash
audial segment path/to/audio.mp3 --results-folder path/to/custom/folder
```

#### Custom API Key

```bash
audial segment path/to/audio.mp3 --api-key your_custom_api_key
```

### Audio Mastering Commands

#### Basic Mastering

```bash
audial master path/to/audio.mp3 --reference path/to/reference.mp3
```

Note: The reference file is required for the CLI interface.

#### Custom Results Folder

```bash
audial master path/to/audio.mp3 --reference path/to/reference.mp3 --results-folder path/to/custom/folder
```

#### Custom API Key

```bash
audial master path/to/audio.mp3 --reference path/to/reference.mp3 --api-key your_custom_api_key
```

### Sample Pack Generation Commands

#### Basic Sample Pack Generation

```bash
audial generate-samples path/to/audio.mp3
```

#### Custom Components

```bash
audial generate-samples path/to/audio.mp3 --components drums,bass,melody
```

#### Specific Genre

```bash
audial generate-samples path/to/audio.mp3 --genre "Tech House"
```

#### Job Type

```bash
audial generate-samples path/to/audio.mp3 --job-type sample_pack
```

#### Custom Results Folder

```bash
audial generate-samples path/to/audio.mp3 --results-folder path/to/custom/folder
```

#### Custom API Key

```bash
audial generate-samples path/to/audio.mp3 --api-key your_custom_api_key
```

### MIDI Generation Commands

#### Basic MIDI Generation

```bash
audial generate-midi path/to/audio.mp3
```

#### Multiple Files

```bash
audial generate-midi path/to/file1.mp3 path/to/file2.mp3 path/to/file3.mp3
```

#### Specific BPM

```bash
audial generate-midi path/to/audio.mp3 --bpm 120
```

#### Custom Results Folder

```bash
audial generate-midi path/to/audio.mp3 --results-folder path/to/custom/folder
```

#### Custom API Key

```bash
audial generate-midi path/to/audio.mp3 --api-key your_custom_api_key
```

## Result Data Structure

All functions return a consistent result structure:

```python
{
    "execution": {
        # Raw API response data
        "exeId": "execution-id",
        "state": "completed",
        "original": {
            "bpm": 120,
            "key": "Cmaj",
            "filename": "original.mp3",
            "url": "https://storage.url/path/to/file.mp3"
        },
        # Function-specific data (e.g., "stem", "midi", "master", etc.)
        "stem": {
            "vocalsmp3": {
                "bpm": 120,
                "key": "Cmaj",
                "filename": "vocals.mp3",
                "url": "https://storage.url/path/to/vocals.mp3"
            },
            # Other stems...
        },
        # Other execution data...
    },
    # For some functions, function-specific data may be included here
    "analysis": {
        "bpm": 120,
        "key": "Cmaj",
        "execution_id": "execution-id"
    },
    "segmentation": {
        # Segmentation data
    },
    "files": {
        "folder": "./audial_results/execution-id_function-type",
        "files": {
            "filename1.mp3": "./audial_results/execution-id_function-type/filename1.mp3",
            "filename2.mp3": "./audial_results/execution-id_function-type/filename2.mp3",
            # Other downloaded files...
        }
    }
}
```

The structure may vary slightly depending on the function, but will always include:
1. `execution`: The raw API response data
2. `files`: Information about the downloaded files
   - `folder`: Path to the results folder
   - `files`: Dictionary mapping filenames to local file paths

Some functions may include additional fields with function-specific data, such as `analysis` for the `analyze` function.