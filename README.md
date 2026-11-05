# Audial SDK

![Audial Logo](./assets/Rectangle110447.png)

[audialmusic.ai](https://audialmusic.ai?utm_source=github&utm_medium=readme&utm_campaign=sdk) · [API reference](https://audialmusic.ai/resources/api-reference?utm_source=github&utm_medium=readme&utm_campaign=sdk)

A powerful Python SDK for audio analysis and manipulation through the Audial API.

## Overview

The Audial SDK provides a user-friendly interface to Audial's powerful audio processing capabilities. With just a few lines of code, you can perform professional-grade audio operations including:

- **Stem Splitting**: Separate tracks into individual components (vocals, drums, bass, other)
- **Audio Analysis**: Extract BPM, key signatures, and other audio metadata
- **Song Analysis**: Find a track's sections, tempo and bars in about half a minute, then add audio features, tags, timed lyrics or a sample pack, one call each
- **Audio Mastering**: Apply professional mastering to your tracks
- **Sample Pack Generation**: Create reusable samples from audio tracks
- **MIDI Generation**: Convert audio to MIDI data
- **Sound-to-Vital Resynthesis**: Turn one isolated sound (not a loop) into a Vital synth preset
- **Sound-to-Serum 2 Resynthesis**: Turn one isolated sound (not a loop) into a Serum 2 preset
- **Text-to-Vocal Synthesis**: Sing lyrics in the timbre of a reference voice clip

Every function requires an Audial account with an active subscription; without one the API answers HTTP 402 `SUBSCRIPTION_REQUIRED` and the SDK raises `SubscriptionRequiredError`. Files are always given as local paths — the SDK uploads them for you.

The SDK supports both a Python API for integration into your projects and a command-line interface for direct use.

> **What changed in 1.6**
>
> - Analysis is faster and needs only the mix: `audial.segment(path)` is one call that answers in
>   about half a minute and returns an `analysis_id`.
> - Features, tags and lyrics are separate calls on an analysis: `audial.audio_features(id)`,
>   `audial.tags(id)`, `audial.lyrics(id)`. `segment(path, features=[...])` still runs them all
>   in one go, as before.
> - Lyrics now come with word timings.
> - Analysis files describe beats with a tempo map (`grid`); the SDK still returns `beat_times`
>   and `bar_times` (2.0 makes that opt-in; see `audial.grid`).
> - Energy and danceability were rebuilt and now differ between tracks and sections. Loudness now
>   follows the broadcast standard over both channels and reads 3–6 LU higher than before.
>
> Everything is listed in the [changelog](CHANGELOG.md).

## Installation

### Prerequisites

Before installing the Audial SDK, ensure you have the following:

- Python 3.7 or higher
- pip package manager (typically included with Python)
- An Audial API key and User ID (obtain from the [Audial website](https://audialmusic.ai?utm_source=github&utm_medium=readme&utm_campaign=sdk))

### Installation Methods

#### 1. Install from PyPI (Recommended)

The simplest way to install the Audial SDK is via pip:

```bash
pip install audial-sdk
```

#### 2. Install from Source

If you want the latest development version, you can install directly from the GitHub repository:

```bash
# Clone the repository
git clone https://github.com/AudialAI/audial-sdk.git

# Navigate to the project directory
cd audial-sdk

# Install the package
pip install -e .
```

## Configuration

### Sign in (recommended)

```bash
audial login
```

This opens a page in your browser. Approve it and you are signed in: there is no API key or
user ID to copy. The sign-in is saved on your computer (`~/.audial/credentials.json`, readable
only by you) and is used by the `audial` command, by Python scripts that `import audial`, and
by the Audial MCP server. `audial whoami` shows the account in use, `audial logout` signs out,
and each connected computer can be disconnected under Apps & API Keys in your profile at
audialmusic.ai. On a machine without a browser, `audial login --no-browser` prints the link
to open elsewhere. From Python, `audial.login()` does the same.

### API keys (servers and CI)

Where nobody is there to sign in, create an API key under Apps & API Keys in your profile and
give it to the SDK in one of the ways below. A key that starts with `aud_` is all you need;
`AUDIAL_USER_ID` is only required with an older key that does not. A key set in the
environment takes priority over a saved sign-in.

### Option 1: Environment Variables

Set the `AUDIAL_API_KEY` environment variable (and `AUDIAL_USER_ID` with an older key):

**Linux/macOS:**
```bash
export AUDIAL_API_KEY=your_api_key_here
export AUDIAL_USER_ID=your_user_id_here
```

**Windows (Command Prompt):**
```cmd
set AUDIAL_API_KEY=your_api_key_here
set AUDIAL_USER_ID=your_user_id_here
```

**Windows (PowerShell):**
```powershell
$env:AUDIAL_API_KEY = "your_api_key_here"
$env:AUDIAL_USER_ID = "your_user_id_here"
```

To point the SDK at a different Audial API host (for example a staging deployment), set `AUDIAL_API_BASE_URL` to that host's `/api` base:

```bash
export AUDIAL_API_BASE_URL=https://your-host.example.com/api
```

When it is unset the SDK talks to `https://api.audialmusic.ai/api`.

### Option 2: .env File

Create a file named `.env` in your project directory:

```
AUDIAL_API_KEY=your_api_key_here
AUDIAL_USER_ID=your_user_id_here
```

### Option 3: Configuration Command

Use the built-in configuration command:

```bash
# Set API key via CLI
audial config --api-key your_api_key_here

# Set User ID via CLI
audial config --user-id your_user_id_here

# Set results folder
audial config --results-folder path/to/results/folder

# Show current configuration
audial config --show
```

### Option 4: Python Code

Set the API key and User ID programmatically in your Python code:

```python
import audial
audial.config.set_api_key("your_api_key_here")
audial.config.set_user_id("your_user_id_here")
```

### Setting Results Folder

By default, all results are saved to `./audial_results/`. You can change this:

```python
# In Python
audial.config.set_results_folder("path/to/custom/folder")

# Or via command line
audial config --results-folder path/to/custom/folder
```

### Verifying Installation

You can verify that the SDK is correctly installed and configured:

```bash
# Check the version
python -c "import audial; print(audial.__version__)"

# Check configuration
audial config --show
```

## Troubleshooting Installation

If you encounter issues during installation:

### Dependency Issues

If you have dependency conflicts, try installing in a virtual environment:

```bash
# Create and activate a virtual environment
python -m venv audial-env
source audial-env/bin/activate  # Linux/macOS
# or
audial-env\Scripts\activate  # Windows

# Install the SDK
pip install audial-sdk
```

### Permission Issues

If you encounter permission errors during installation:

```bash
# Install for the current user only
pip install --user audial-sdk
```

### API Key or User ID Issues

If you get authentication errors:

1. Verify your API key and User ID are correct
2. Check that they are being properly set/loaded
3. Ensure your account has the necessary permissions

## Quick Start

```python
import audial

# Configure your API key and User ID
audial.config.set_api_key("your_api_key_here")
audial.config.set_user_id("your_user_id_here")

# Stem splitting
result = audial.stem_split("path/to/audio.mp3")
print(f"Vocals saved to: {result['files']['files']['vocals.mp3']}")
print(f"Drums saved to: {result['files']['files']['drums.mp3']}")

# Audio analysis
analysis = audial.analyze("path/to/audio.mp3")
print(f"BPM: {analysis['analysis']['bpm']}")
print(f"Key: {analysis['analysis']['key']}")

# Song analysis: sections, tempo and bars in about half a minute...
song = audial.segment("path/to/audio.mp3", genre="Tech House")
for section in song["audio_segmentation"]["sections"]:
    print(section["label"], section["start"])

# ...then audio features, tags and timed lyrics, one call each
features = audial.audio_features(song["analysis_id"])
lyrics = audial.lyrics(song["analysis_id"])
```

## Core Functions

### Stem Splitting

Split an audio track into its component parts:

```python
# Basic stem splitting
result = audial.stem_split("path/to/audio.mp3")

# Advanced options
result = audial.stem_split(
    "path/to/audio.mp3",
    stems=["vocals", "drums", "full_song_without_vocals"],
    target_bpm=120,
    target_key="Cmaj",
    algorithm="primaudio"  # or "quintessound"
)
```

Available stems:
- `vocals` - Vocal track
- `drums` - Drum track
- `bass` - Bass track
- `other` - All other instruments
- `full_song_without_vocals` - Full mix minus vocals
- `full_song_without_drums` - Full mix minus drums
- `full_song_without_bass` - Full mix minus bass
- `full_song_without_other` - Full mix minus other instruments

### Audio Analysis

Extract metadata from an audio track:

```python
analysis = audial.analyze("path/to/audio.mp3")
print(f"BPM: {analysis['analysis']['bpm']}")
print(f"Key: {analysis['analysis']['key']}")
```

### Song Analysis (Segmentation)

Analysis finds your track's sections, tempo and bars in about half a minute. Send the mix: no
stems are needed. Add audio features, tags, lyrics or a sample pack afterwards, one call each,
whenever you like.

```python
song = audial.segment("path/to/audio.mp3", genre="Tech House")

analysis_id = song["analysis_id"]
data = song["audio_segmentation"]
print(data["bpm"], data["time_signature"])
for section in data["sections"]:
    print(f"{section['start']:7.2f}  {section['label']}  ({section['bars']} bars)")
```

`genre` picks dance section names (INTRO, UP, CHORUS, DOWN, OUTRO) or song section names
(INTRO, VERSE, UP, CHORUS, OUTRO); `edm=True` or `edm=False` chooses directly.

#### Add-ons

Each add-on is its own call on the analysis id, any time later. It waits for its result and
returns it:

```python
features = audial.audio_features(analysis_id)  # energy, danceability, loudness, mode, key
tags = audial.tags(analysis_id)                # genre, moods, instruments, artist tags
lyrics = audial.lyrics(analysis_id)            # text, timed lines, word timings
pack = audial.generate_samples(analysis_id=analysis_id)   # drums, bass and melody loops

print(features["song"]["energy"], [s["energy"] for s in features["sections"]])
for line in lyrics["lines"]:
    print(line["start"], [word for word, start, end in line["words"]])
```

Energy and danceability are 0–100%. Energy reflects loudness, rhythmic activity and low end.
Danceability reflects how strong and regular the beat is. Both are measured per section, so a
drop reads higher than its breakdown.

Tags, lyrics and the sample pack read the analysis's stems, which are made automatically in the
background as soon as the analysis starts. Until they are ready the API answers
`409 STEMS_NOT_READY` ("This track is still being prepared. Try again in a minute."); the SDK
keeps trying for up to `wait_s` seconds (default 600). Audio features need only the mix.

An analysis counts as one run. Everything you add to it (features, tags, lyrics, a sample pack)
is included. Calling those on their own, without an analysis, counts as a run each. Calling an add-on
again returns the same result (`rerun=True` makes a new one).

#### The merged result

`segment()` returns the analysis with every add-on generated so far:

```python
{
  "analysis_id": "-Pq0...",
  "audio_segmentation": {
    "format_version": 4, "duration": 391.2, "bpm": 129.0, "time_signature": "4/4",
    "grid": {...},                  # the tempo map (below)
    "sections": [{"label": "INTRO", "start": 0.2, "end": 30.0, "start_bar": -2, "bars": 16, ...}, ...],
    "phrases": [...],
    "song_analysis": {...},         # audio features, genre, song_tags, lyrics, lyrics_lines
    "segment_analysis": [{...}, ...],   # one object per section
    "beat_times": [...], "bar_times": [...]   # with expand_beats=True (the 1.6 default)
  },
  "segmentation": {...},            # the same object, under its 1.5 name
  "execution": {...},               # the analysis execution
  "files": {"folder": "...", "files": {"analysis.json": "..."}}
}
```

`segment(path, features=[...])` still works as it did in 1.5: it runs the `segmentation`
pipeline, which makes the analysis and then the add-ons those features need, and the result
already holds them. It takes longer, because tags and lyrics wait for the stems.

#### The tempo map

Beats and bars aren't listed one by one. `grid` describes them: where each constant-tempo piece
starts, its BPM, and its bar and beat. Every beat time is `start + k × 60 / bpm`. Most tracks
have one piece.

```python
grid = data["grid"]
grid["beat_count"], grid["bar_count"]       # totals, no expansion needed
audial.grid.expand(grid)        # [(time, bar, beat), ...]; bars 0 and below are the lead-in
audial.grid.beat_times(grid)    # every beat time
audial.grid.bar_times(grid)     # the start of every bar from bar 1
audial.grid.beats_of(data)      # (beat times, bar times) of an analysis of any format
```

In 1.6 `segment()` also adds `beat_times` and `bar_times` for you (`expand_beats=True`), so
scripts written for older results keep working. 2.0 makes this opt-in; pass `expand_beats=False`
and use `audial.grid` to be ready for it.

### Audio Mastering

Apply professional mastering to your tracks:

```python
# Basic mastering
mastered = audial.master("path/to/audio.mp3")

# With reference track
mastered = audial.master(
    "path/to/audio.mp3",
    reference_file="path/to/reference.mp3"
)
```

### Sample Pack Generation

Generate a sample pack from an audio track. From a file, this runs the `sample-pack`
**pipeline**: the analysis and the stems start together, then the pack is built from them, in a
single API call. Tempo and key are detected automatically.

```python
samples = audial.generate_samples(
    "path/to/audio.mp3",
    job_type="sample_pack",
    components=["drums", "bass", "melody"],
    genre="Tech House"
)
```

From an analysis you already have, the pack reuses its stems and sections, and is included
with the analysis:

```python
pack = audial.generate_samples(analysis_id=song["analysis_id"], components=["drums", "bass"])
print(pack["components"])   # {"drums": {"status": "ok"}, "bass": {"status": "ok"}}
```

`samples["execution"]` is the pipeline status, so you can see what each step
did. The same job can be run directly:

```python
status = audial.pipelines.run("sample-pack", "path/to/audio.mp3",
                              options={"components": ["drums", "bass"],
                                       "genre": "Tech House"})
print(status["outputs"]["samples"])   # sample URLs
```

### MIDI Generation

Convert audio to MIDI:

```python
# Single file
midi = audial.generate_midi("path/to/audio.mp3", bpm=120)

# Multiple files
midi = audial.generate_midi(
    ["path/to/file1.mp3", "path/to/file2.mp3"],
    bpm=140
)
```

### Pipelines

A pipeline is several Audial functions run as one job: you send the file once
and the API feeds each step's output into the next.

| Pipeline | Steps |
|---|---|
| `sample-pack` | `prepare` (the analysis and its stems, together) -> `sample-pack` |
| `segmentation` | `segmentation` (the analysis) -> `add-ons` (the features, tags and lyrics asked for) |

```python
status = audial.pipelines.run(
    "sample-pack",
    "path/to/audio.mp3",
    options={"components": ["drums", "bass", "melody"], "genre": "Tech House"},
    on_progress=lambda s: print(s["state"], s.get("currentStep")),
)

print(status["state"])               # "completed"
print(status["outputs"]["samples"])  # sample URLs
```

`run()` uploads the file, polls until the pipeline finishes, and raises
`AudialError` naming the step that failed if one does. Other calls:

```python
audial.pipelines.run(name, file_path, options=None, wait=True,
                     poll_interval=5, on_progress=None, api_key=None)
audial.pipelines.get(pipeline_id)       # current status
audial.pipelines.cancel(pipeline_id)    # stop it
audial.pipelines.list(limit=20)         # {"items": [...], "nextCursor": ...}
```

Options are `components`, `genre`, `bpm`, `keyString` and `featuresToExtract`;
everything omitted gets the API's default, and BPM and key are detected from
the file when you do not send them. A segmentation pipeline reports the
analysis with every add-on as `outputs.analysis`, and any add-on that could
not be made in `outputs.warnings`.

`generate_samples(file)` and `segment(file, features=[...])` run these
pipelines for you and download the results, so use `pipelines.run()` directly
when you want the URLs, the per-step timings, or control over polling.

### Sound-to-Vital Resynthesis

Turn a short (<=20s) audio clip into a Vital synth preset:

```python
result = audial.sound2vital("path/to/clip.wav")
print(f"Preset: {result['preset']}")
```

### Sound-to-Serum 2 Resynthesis

Turn a short (<=20s) audio clip into a Serum 2 preset. No Audial plugin is needed --
open the downloaded `.SerumPreset` file directly in Xfer's Serum 2. Serum runs take
about 2.5 minutes, plus up to another 2.5 minutes if a worker has to cold-start:

```python
result = audial.sound2serum("path/to/clip.wav")
print(f"Preset: {result['preset']}")
```

### Text-to-Vocal Synthesis

Sing lyrics in the timbre of a reference voice clip, following a melody:

```python
result = audial.text2vox(
    reference_file="path/to/voice_clip.wav",
    lyrics="la la la la",
    midi_file="path/to/melody.mid",
)
```

#### Per-note lyrics

`lyrics_mode="per_note"` gives you a syllable per MIDI note: the lyrics are pipe-delimited,
one token per note, and a **hold** keeps the previous syllable going through the next note.

| Token | Meaning |
|-------|---------|
| `grace` | Sung on this note |
| `-` | Hold: continue the previous syllable through this note (the documented form) |
| `+` | Hold as well (a Synthesizer V habit) |
| *empty* | Hold as well -- what a double pipe produces |

So a word can span notes:

```python
result = audial.text2vox(
    reference_file="voice_clip.wav",
    midi_file="melody.mid",                              # 9 notes
    lyrics="amazing|-|-|grace|-|how|sweet|the|sound",    # 9 tokens
    lyrics_mode="per_note",
)
```

"amazing" is sung across notes 1-3 and "grace" across notes 4-5. There is no rest token: a
note that should be silent should not be in the MIDI. The token count must equal the note
count, and the first token must be a syllable -- which the SDK checks before it uploads
anything:

```python
from audial.api.exceptions import AudialValidationError

try:
    audial.text2vox(..., lyrics="-|grace", lyrics_mode="per_note")
except AudialValidationError as e:
    print(e)           # note 1 has no syllable; the first note needs one
    print(e.position)  # 1 -- the note the message is about

audial.text2vox_tokens("amazing|-|-|grace")  # the tokens that will be sent
```

See [Per-note lyrics](API_DOCUMENTATION.md#per-note-lyrics) for the full reference.

### Cold Starts

Audial's GPU workers scale to zero, so the first job after an idle period waits a few
minutes for a worker to start and load the model; every run after it is fast. The API
reports that phase on the execution it already returns, so the SDK can explain the wait
instead of looking hung.

Every function that polls takes an optional `on_progress` callback, and `audial.status()`
answers the same question *before* a job is submitted:

```python
tracker = audial.warmup.WarmupTracker()
audial.sound2vital("kick.wav", on_progress=lambda status: [
    print(line) for line in tracker.changes(status)
])
# Warming up the machine - the first request takes a few minutes longer than
# usual (about 3 min); every run after this is faster
# Working on your job...

audial.status("text2vox")
# {'items': [{'function': 'text2vox', 'warm': False, 'queued': 0,
#             'expectedColdStartMs': 180000, 'expectedRunMs': 42000}]}
```

The add-ons (`audio_features`, `tags`, `lyrics`) run on their own machines, so the first one
after a quiet period can wait for a start too ("Starting up — this can take a minute");
their `on_progress` reports it the same way, and `audial.status("tags")` asks ahead.

The CLI does both for you: it checks before it submits and prints each phase as it
changes. `audial status` shows every function at once. See [Cold Starts and Service
Status](API_DOCUMENTATION.md#cold-starts-and-service-status).

## Command Line Interface

The SDK provides a powerful command-line interface:

```bash
# Stem splitting
audial stem-split audio.mp3 --stems vocals,drums,bass,other

# Audio analysis
audial analyze audio.mp3

# Song analysis, then its add-ons (an analysis id, or a file: it is analysed first)
audial segment audio.mp3 --genre "Tech House"
audial features <analysis_id>
audial tags <analysis_id>
audial lyrics audio.mp3

# Mastering
audial master audio.mp3 --reference reference.mp3

# Sample pack generation
audial generate-samples audio.mp3 --components drums bass melody
audial generate-samples --analysis-id <analysis_id>

# Pipelines: several steps in one call
audial pipeline sample-pack audio.mp3 --genre "Tech House" --components drums bass
audial pipeline segmentation audio.mp3 --json

# MIDI generation
audial generate-midi audio.mp3 --bpm 120

# Sound-to-Vital resynthesis
audial sound2vital clip.wav

# Sound-to-Serum 2 resynthesis
audial sound2serum clip.wav

# Text-to-vocal synthesis
audial text2vox voice_clip.wav "la la la la" --midi melody.mid
audial text2vox voice_clip.wav "amazing|-|-|grace|-|how|sweet|the|sound" \
  --midi melody.mid --lyrics-mode per_note

# Which services have a worker awake right now
audial status

# Configuration
audial config --api-key your_api_key_here
audial config --user-id your_user_id_here
audial config --results-folder path/to/results
audial config --show
```

## Result Format

Functions that make files return a consistent result structure (`segment()` adds
`analysis_id` and `audio_segmentation`; the add-ons `audio_features`, `tags` and `lyrics`
return their result itself and save it as `<analysis_id>_analysis/<name>.json`):

```python
{
    "execution": {
        # API response data
        "exeId": "execution-id",
        "state": "completed",
        # Other execution data...
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

## Error Handling

```python
from audial.api.exceptions import (
    AudialError,
    AudialAuthError,
    AudialAPIError,
    AudialValidationError,
    SubscriptionRequiredError,
)

try:
    result = audial.stem_split("path/to/audio.mp3")
except AudialValidationError as e:
    print(f"Unusable input: {e} (position {e.position})")
except SubscriptionRequiredError as e:
    print(f"Subscription required: {e}")
except AudialAuthError as e:
    print(f"Authentication error: {e}")
except AudialAPIError as e:
    print(f"API error: {e}")
except AudialError as e:
    print(f"General error: {e}")
```

The add-ons raise `AudialAPIError` with `e.code` set when the API refuses them (HTTP 409):

- `STEMS_NOT_READY`: "This track is still being prepared. Try again in a minute." The stems were
  still being made after `wait_s` seconds, or could not be made ("We couldn't prepare this
  track.").
- `ADDON_UNAVAILABLE`: "This result can't be added to this analysis." For example an older
  analysis that kept no stems.

## Advanced Usage

See the [API Documentation](API_DOCUMENTATION.md) for detailed information about all functions and their parameters.

## Examples

The SDK includes example scripts in the [examples directory](examples/):

- [Stem Splitting](examples/stem_splitting.py)
- [Audio Analysis](examples/analysis.py)
- [Song Analysis with Audio Features and Tags](examples/segmentation.py)
- [Lyrics with Word Timings](examples/lyrics_lines.py)
- [Audio Mastering](examples/mastering.py)
- [Sample Pack Generation](examples/sample_generation.py)
- [MIDI Generation](examples/midi_generation.py)
- [Music Generation](examples/music_generation.py)
- [Sound-to-Vital Resynthesis](examples/sound2vital.py)
- [Sound-to-Serum 2 Resynthesis](examples/sound2serum.py)
- [Text-to-Vocal Synthesis](examples/text2vox.py)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or feedback, please [create an issue](https://github.com/AudialAI/audial-sdk/issues) on our GitHub repository or contact contact@audialmusic.ai.

---

Powered by [Audial](https://audialmusic.ai?utm_source=github&utm_medium=readme&utm_campaign=sdk).
