# Audial SDK API Documentation

This document provides comprehensive documentation for the Audial SDK, including detailed information about all functions, parameters, return values, and examples for both the Python API and Command Line Interface (CLI).

## Table of Contents

- [Python API](#python-api)
  - [Configuration](#configuration)
  - [Pipelines](#pipelines)
  - [Stem Splitting](#stem-splitting)
  - [Audio Analysis](#audio-analysis)
  - [Audio Segmentation](#audio-segmentation)
  - [Audio Mastering](#audio-mastering)
  - [Sample Pack Generation](#sample-pack-generation)
  - [MIDI Generation](#midi-generation)
  - [Sound-to-Vital Resynthesis (sound2vital)](#sound-to-vital-resynthesis-sound2vital)
  - [Text-to-Vocal Synthesis (text2vox)](#text-to-vocal-synthesis-text2vox)
  - [Error Handling](#error-handling)
- [Command Line Interface](#command-line-interface)
  - [Configuration Commands](#configuration-commands)
  - [Pipeline Commands](#pipeline-commands)
  - [Stem Splitting Commands](#stem-splitting-commands)
  - [Audio Analysis Commands](#audio-analysis-commands)
  - [Audio Segmentation Commands](#audio-segmentation-commands)
  - [Audio Mastering Commands](#audio-mastering-commands)
  - [Sample Pack Generation Commands](#sample-pack-generation-commands)
  - [MIDI Generation Commands](#midi-generation-commands)
  - [sound2vital Commands](#sound2vital-commands)
  - [text2vox Commands](#text2vox-commands)
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

### Pipelines

A pipeline runs several Audial functions as one job: the file is uploaded once
and the API feeds each step's output into the next. Both pipelines start by
separating stems, because their second step needs stems to work on.

| Pipeline | Steps | Outputs |
|---|---|---|
| `sample-pack` | `stem-split` -> `sample-pack` | `outputs.stems`, `outputs.samples` |
| `segmentation` | `stem-split` -> `segmentation` | `outputs.stems`, `outputs.segmentation` |

#### Function Signatures

```python
audial.pipelines.run(
    name: str,
    file_path: str,
    options: Optional[Dict[str, Any]] = None,
    wait: bool = True,
    poll_interval: float = 5,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]

audial.pipelines.get(pipeline_id: str, api_key: Optional[str] = None) -> Dict[str, Any]
audial.pipelines.cancel(pipeline_id: str, api_key: Optional[str] = None) -> Dict[str, Any]
audial.pipelines.list(limit: int = 20, cursor: Optional[str] = None,
                      api_key: Optional[str] = None) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | str | Yes | - | `"sample-pack"` or `"segmentation"` |
| `file_path` | str | Yes | - | Path to the local audio file; it is uploaded with the request |
| `options` | Dict | No | `None` | See the options table below |
| `wait` | bool | No | `True` | Poll until the pipeline finishes; `False` returns the queued status at once |
| `poll_interval` | float | No | `5` | Seconds between status polls |
| `on_progress` | Callable | No | `None` | Called with the status dict for the first response and after every poll |
| `api_key` | str | No | `None` | API key to use (uses default if `None`) |

#### Options

| Option | Type | Applies to | Description |
|--------|------|-----------|-------------|
| `components` | List[str] | both | `["drums", "bass", "melody"]` for `sample-pack`; `["bass", "beat", "melody", "vocal"]` for `segmentation` |
| `genre` | str | both | Genre hint; same list as [Audio Segmentation](#audio-segmentation) |
| `bpm` | float | both | Overrides the detected tempo |
| `keyString` | str | both | Overrides the detected key, e.g. `"A minor"` |
| `featuresToExtract` | List[str] | `segmentation` | Features to extract per section |

Anything you omit gets the API's default, and tempo and key are detected from
the file when you do not send them.

#### Returns

The API's pipeline status dictionary:

```python
{
  "pipelineId": "...",
  "pipeline": "sample-pack",
  "state": "queued" | "running" | "completed" | "failed" | "cancelled",
  "currentStep": "sample-pack",
  "createdAt": ..., "updatedAt": ..., "startedAt": ..., "endedAt": ..., "durationMs": ...,
  "steps": [
    {"name": "stem-split", "state": "completed", "exeId": "...", "durationMs": 41000},
    {"name": "sample-pack", "state": "running", "exeId": "...", "subStage": "rendering"}
  ],
  "outputs": {
    "stems": {"drumsmp3": {"filename": "...", "url": "..."}, ...},
    "samples": ["https://...", ...],
    "segmentation": ["https://...", ...]
  },
  "original": {"filename": "...", "url": "..."},
  "options": {...},
  "error": {"step": "...", "code": "...", "message": "..."}
}
```

`pipelines.list()` returns the page envelope: `{"items": [status, ...],
"nextCursor": "..."}`.

A pipeline that ends `failed` or `cancelled` raises `AudialError`, with the
failing step's name and the worker's message in the text. An account whose free
allowance is used up raises `SubscriptionRequiredError` (HTTP 402).

#### Example

```python
import audial

status = audial.pipelines.run(
    "sample-pack",
    "path/to/audio.mp3",
    options={"components": ["drums", "bass"], "genre": "Tech House"},
    on_progress=lambda s: print(s["state"], s.get("currentStep")),
)

for url in status["outputs"]["samples"]:
    print(url)

# Start one and come back to it later
queued = audial.pipelines.run("segmentation", "path/to/audio.mp3", wait=False)
later = audial.pipelines.get(queued["pipelineId"])
audial.pipelines.cancel(queued["pipelineId"])

# Your recent pipelines, newest first
for item in audial.pipelines.list(limit=10)["items"]:
    print(item["pipeline"], item["state"])
```

`audial.generate_samples()` and `audial.segment()` run these pipelines for you
and download the results; call `pipelines.run()` directly when you want the
output URLs, the per-step timings, or control over polling.

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

Segmentation runs on separated stems, so this function runs the `segmentation`
[pipeline](#pipelines): the track is split into stems first and then segmented,
in a single API call. Tempo and key are detected automatically. `execution` in
the result is the pipeline status, so every step and its timing is visible
there; `audial.pipelines.run("segmentation", ...)` is the same job without the
downloads.

#### Function Signature

```python
audial.segment(
    file_path: str,
    components: Optional[List[str]] = None,
    analysis_type: Optional[str] = None,
    features: Optional[List[str]] = None,
    genre: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None,
    poll_interval: float = 5
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
| `on_progress` | Callable | No | `None` | Called with the pipeline status after every poll |
| `poll_interval` | float | No | `5` | Seconds between pipeline status polls |

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
- `execution`: The final pipeline status (steps, outputs, timings)
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

A sample pack is built from separated stems, so this function runs the
`sample-pack` [pipeline](#pipelines): the track is split into stems first and
the pack is built from them, in a single API call. Tempo and key are detected
automatically. `execution` in the result is the pipeline status, so every step
and its timing is visible there; `audial.pipelines.run("sample-pack", ...)` is
the same job without the downloads.

#### Function Signature

```python
audial.generate_samples(
    file_path: str,
    job_type: Optional[str] = None,
    components: Optional[List[str]] = None,
    genre: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None,
    poll_interval: float = 5
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
| `on_progress` | Callable | No | `None` | Called with the pipeline status after every poll |
| `poll_interval` | float | No | `5` | Seconds between pipeline status polls |

#### Available Components

- `drums` - Drum samples
- `bass` - Bass samples
- `melody` - Melodic samples

#### Available Genres

Same as [Audio Segmentation](#audio-segmentation).

#### Returns

A dictionary containing:
- `execution`: The final pipeline status (steps, outputs, timings)
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

### Sound-to-Vital Resynthesis (sound2vital)

Synthesize a [Vital](https://vital.audio/) synth preset that reproduces the timbre of a
short audio clip. This is a paid function -- it requires an active Audial subscription in
addition to a valid API key (see [Error Handling](#error-handling)).

#### Function Signature

```python
audial.sound2vital(
    file_path: str,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    max_wait: float = 360,
    poll_interval: float = 5
) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | Yes | - | Path to the input audio file. Must be 20 seconds or shorter |
| `results_folder` | str | No | `None` | Folder to save results (uses default if `None`) |
| `api_key` | str | No | `None` | API key to use (uses default if `None`) |
| `max_wait` | float | No | `360` | Maximum seconds to wait for completion (jobs typically take 60-250s) |
| `poll_interval` | float | No | `5` | Seconds between execution status polls |

#### Returns

A dictionary containing:
- `execution`: API response data
- `files`: Information about downloaded files
  - `folder`: Path to the results folder
  - `files`: Dictionary mapping filenames to local file paths (the `.vital` preset plus
    any generated render/keyboard/report files)
- `preset`: Local path to the downloaded `.vital` preset, if the job produced one
- `scores`: `generation_metadata.scores` -- `huang_similarity`, `at_threshold`,
  `threshold`, `model` -- if present
- `report`: `generation_metadata.report`, if present
- `warnings`: `generation_metadata.warnings` list, if present

#### Example

```python
import audial

result = audial.sound2vital("path/to/clip.wav")

print(f"Preset: {result['preset']}")
print(f"Similarity score: {result['scores']['huang_similarity']}")
```

### Text-to-Vocal Synthesis (text2vox)

Synthesize a sung vocal in the timbre of a short reference voice clip, following a melody
(MIDI or audio) and lyrics. This is a paid function -- it requires an active Audial
subscription in addition to a valid API key (see [Error Handling](#error-handling)).

Exactly one of `midi_file` / `melody_audio_file` must be given -- the underlying worker
needs one of the two to drive the melody.

#### Function Signature

```python
audial.text2vox(
    reference_file: str,
    lyrics: str,
    midi_file: Optional[str] = None,
    melody_audio_file: Optional[str] = None,
    word_timestamps_file: Optional[str] = None,
    lyrics_mode: str = "auto",
    reference_text: Optional[str] = None,
    cfg_strength: Optional[float] = None,
    nfe_steps: Optional[int] = None,
    pitch_shift: Optional[float] = None,
    strict_pitch: Optional[bool] = None,
    bend_smoothing_ms: Optional[float] = None,
    no_pitch_bends: Optional[bool] = None,
    leading_silence_s: Optional[float] = None,
    seed: Optional[int] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    max_wait: float = 360,
    poll_interval: float = 5
) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `reference_file` | str | Yes | - | Path to a short (5-10s) reference voice clip -- the voice to sing in |
| `lyrics` | str | Yes | - | The lyrics to sing |
| `midi_file` | str | One of midi_file/melody_audio_file | `None` | Path to a MIDI file driving the melody |
| `melody_audio_file` | str | One of midi_file/melody_audio_file | `None` | Path to override melody audio (skips strict-pitch synthesis) |
| `word_timestamps_file` | str | No | `None` | Path to a Whisper word-timestamps JSON, used by auto-align |
| `lyrics_mode` | str | No | `"auto"` | `"auto"` (word count matches MIDI notes, auto-aligns via word_timestamps), `"per_note"` (pipe-delimited, one token per note), or `"1to1"` (passed straight through) |
| `reference_text` | str | No | `None` | What is said in the reference clip |
| `cfg_strength` | float | No | `None` | Worker synthesis option |
| `nfe_steps` | int | No | `None` | Worker synthesis option |
| `pitch_shift` | float | No | `None` | Worker synthesis option |
| `strict_pitch` | bool | No | `None` | Worker synthesis option |
| `bend_smoothing_ms` | float | No | `None` | Worker synthesis option |
| `no_pitch_bends` | bool | No | `None` | Worker synthesis option |
| `leading_silence_s` | float | No | `None` | Worker synthesis option |
| `seed` | int | No | `None` | Random seed for reproducibility |
| `results_folder` | str | No | `None` | Folder to save results (uses default if `None`) |
| `api_key` | str | No | `None` | API key to use (uses default if `None`) |
| `max_wait` | float | No | `360` | Maximum seconds to wait for completion |
| `poll_interval` | float | No | `5` | Seconds between execution status polls |

#### Returns

A dictionary containing:
- `execution`: API response data
- `files`: Information about downloaded files
  - `folder`: Path to the results folder
  - `files`: Dictionary mapping filenames to local file paths (the rendered wav plus any
    MIDI actually used, if the worker returned one)
- `metadata`: `generation_metadata` dict (`duration_s`, `sample_rate`), if present
- `warnings`: `generation_metadata.warnings` list, if present

#### Example

```python
import audial

# Driven by a MIDI file
result = audial.text2vox(
    reference_file="path/to/voice_clip.wav",
    lyrics="la la la la",
    midi_file="path/to/melody.mid",
)

# Driven by melody audio instead
result = audial.text2vox(
    reference_file="path/to/voice_clip.wav",
    lyrics="la la la la",
    melody_audio_file="path/to/melody.wav",
    lyrics_mode="per_note",
)

for name, path in result["files"]["files"].items():
    print(f"{name}: {path}")
```

### Error Handling

The SDK provides custom exception classes for better error handling:

```python
from audial.api.exceptions import (
    AudialError,
    AudialAuthError,
    AudialAPIError,
    SubscriptionRequiredError,
)

try:
    result = audial.stem_split("path/to/audio.mp3")
except SubscriptionRequiredError as e:
    print(f"Subscription required: {e}")
    # sound2vital and text2vox require an active Audial subscription
    # (HTTP 402, code SUBSCRIPTION_REQUIRED) in addition to a valid API key
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

Note: `SubscriptionRequiredError` is a subclass of `AudialAPIError`, so an `except
AudialAPIError` clause also catches it -- catch `SubscriptionRequiredError` first if you
need to handle it differently (e.g. prompting the user to subscribe).

## Command Line Interface

The Audial SDK provides a command-line interface for all its functions.

### Configuration Commands

#### Show Current Configuration

```bash
audial config --show
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

### Pipeline Commands

Run a whole pipeline (stem split, then the sample pack or segmentation step)
in one call, printing a line per step change.

#### Sample Pack Pipeline

```bash
audial pipeline sample-pack path/to/audio.mp3
```

#### Segmentation Pipeline

```bash
audial pipeline segmentation path/to/audio.mp3
```

#### Options

```bash
audial pipeline sample-pack path/to/audio.mp3 \
  --genre "Tech House" \
  --components drums bass melody \
  --bpm 128 \
  --key "A minor"
```

| Flag | Description |
|------|-------------|
| `--genre` | Genre hint |
| `--components` | Components to process, space separated |
| `--bpm` | Override the detected tempo |
| `--key` | Override the detected key |
| `--no-wait` | Start the pipeline and print its id without waiting |
| `--poll-interval` | Seconds between status polls (default 5) |
| `--json` | Print the pipeline status as JSON instead of a summary |
| `--api-key` | API key to use |

#### JSON Output

```bash
audial pipeline segmentation path/to/audio.mp3 --json
```

Prints only the pipeline status document, for piping into other tools.

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

### sound2vital Commands

Requires an active Audial subscription.

#### Basic Usage

```bash
audial sound2vital path/to/clip.wav
```

#### Custom Results Folder

```bash
audial sound2vital path/to/clip.wav --results-folder path/to/custom/folder
```

#### Custom API Key

```bash
audial sound2vital path/to/clip.wav --api-key your_custom_api_key
```

### text2vox Commands

Requires an active Audial subscription. Exactly one of `--midi` / `--melody-audio` must be
given.

#### Driven by a MIDI File

```bash
audial text2vox path/to/voice_clip.wav "la la la la" --midi path/to/melody.mid
```

#### Driven by Melody Audio

```bash
audial text2vox path/to/voice_clip.wav "la la la la" --melody-audio path/to/melody.wav
```

#### Lyrics Mode

```bash
audial text2vox path/to/voice_clip.wav "la|la|la|la" --midi path/to/melody.mid --lyrics-mode per_note
```

#### Custom Results Folder

```bash
audial text2vox path/to/voice_clip.wav "la la la la" --midi path/to/melody.mid --results-folder path/to/custom/folder
```

#### Custom API Key

```bash
audial text2vox path/to/voice_clip.wav "la la la la" --midi path/to/melody.mid --api-key your_custom_api_key
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