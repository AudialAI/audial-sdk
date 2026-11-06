# Audial SDK API Documentation

This document provides comprehensive documentation for the Audial SDK, including detailed information about all functions, parameters, return values, and examples for both the Python API and Command Line Interface (CLI).

## Table of Contents

- [Python API](#python-api)
  - [Configuration](#configuration)
  - [Pipelines](#pipelines)
  - [Stem Splitting](#stem-splitting)
  - [Audio Analysis](#audio-analysis)
  - [Audio Segmentation](#audio-segmentation)
    - [The tempo map](#the-tempo-map)
  - [Analysis Add-ons](#analysis-add-ons)
    - [Audio features](#audio-features)
    - [Tags](#tags)
    - [Lyrics](#lyrics)
  - [Audio Mastering](#audio-mastering)
  - [Sample Pack Generation](#sample-pack-generation)
  - [MIDI Generation](#midi-generation)
  - [Sound-to-Vital Resynthesis (sound2vital)](#sound-to-vital-resynthesis-sound2vital)
  - [Sound-to-Serum 2 Resynthesis (sound2serum)](#sound-to-serum-2-resynthesis-sound2serum)
  - [Text-to-Vocal Synthesis (text2vox)](#text-to-vocal-synthesis-text2vox)
    - [Per-note lyrics](#per-note-lyrics)
  - [Cold Starts and Service Status](#cold-starts-and-service-status)
  - [Error Handling](#error-handling)
- [Command Line Interface](#command-line-interface)
  - [Configuration Commands](#configuration-commands)
  - [Pipeline Commands](#pipeline-commands)
  - [Stem Splitting Commands](#stem-splitting-commands)
  - [Audio Analysis Commands](#audio-analysis-commands)
  - [Audio Segmentation Commands](#audio-segmentation-commands)
  - [Analysis Add-on Commands](#analysis-add-on-commands)
  - [Audio Mastering Commands](#audio-mastering-commands)
  - [Sample Pack Generation Commands](#sample-pack-generation-commands)
  - [MIDI Generation Commands](#midi-generation-commands)
  - [sound2vital Commands](#sound2vital-commands)
  - [sound2serum Commands](#sound2serum-commands)
  - [text2vox Commands](#text2vox-commands)
  - [Service Status Command](#service-status-command)
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
and the API feeds each step's output into the next. Both pipelines start with
one analysis run, and the analysis and its stems are started together.

| Pipeline | Steps | Outputs |
|---|---|---|
| `sample-pack` | `prepare` (the analysis and its stems) -> `sample-pack` | `outputs.samples` |
| `segmentation` | `segmentation` (the analysis) -> `add-ons` (the features, tags and lyrics that `featuresToExtract` asks for) | `outputs.analysis`, `outputs.segmentation`, `outputs.warnings` |

`outputs.analysis` is the URL of the analysis with every add-on result (the merged view, see
[Audio Segmentation](#audio-segmentation)); `outputs.segmentation` lists the stored analysis
file. An add-on the caller asked for that could not be made is listed in `outputs.warnings`,
and the pipeline still completes. Pipelines started before November 2026 report `stem-split`
as their first step.

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
| `components` | List[str] | `sample-pack` | `["drums", "bass", "melody"]` (the default) or a subset |
| `genre` | str | both | Genre hint; same list as [Audio Segmentation](#audio-segmentation) |
| `bpm` | float | both | Overrides the detected tempo (used for the stems) |
| `keyString` | str | both | Overrides the detected key, e.g. `"A minor"` |
| `featuresToExtract` | List[str] | `segmentation` | The add-ons to run after the analysis: `mode`, `energy`, `loudness`, `danceability`, `tatum` (audio features), `tags`, `lyrics`. Default: all |

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
    {"name": "prepare", "state": "completed", "exeId": "...", "durationMs": 41000},
    {"name": "sample-pack", "state": "running", "exeId": "...", "subStage": "rendering"}
  ],
  "outputs": {
    "samples": ["https://...", ...],                 # sample-pack
    "analysis": "https://.../analysis",              # segmentation: the merged view
    "segmentation": ["https://...", ...],            # segmentation: the stored file
    "warnings": ["Lyrics could not be made: ..."]    # segmentation, when some add-on failed
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

`audial.generate_samples(file)` and `audial.segment(file, features=[...])` run
these pipelines for you and download the results; call `pipelines.run()`
directly when you want the output URLs, the per-step timings, or control over
polling.

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

Analysis finds your track's sections, tempo and bars in about half a minute. Add audio
features, tags, lyrics or a sample pack afterwards, one call each.

Send the mix: you get the sections, phrases and a tempo map. No stems are needed, and nothing
has to be prepared. Without `features`, `segment()` is one call
(`POST /functions/run/segmentation`). It returns the analysis and its `analysis_id`, which the
[add-ons](#analysis-add-ons) take.

With `features`, `segment()` runs the `segmentation` [pipeline](#pipelines), as in 1.5: the API
runs the analysis, then the add-ons those features need, and the result holds them. It takes
longer, because tags and lyrics wait for the analysis's stems.

#### Function Signature

```python
audial.segment(
    file_path: str,
    genre: Optional[str] = None,
    edm: Optional[bool] = None,
    features: Optional[List[str]] = None,
    results_folder: Optional[str] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None,
    expand_beats: bool = True,
    *,
    api_key: Optional[str] = None,
    poll_interval: Optional[float] = None,
    max_wait: float = 900,
    components: Optional[List[str]] = None,      # deprecated, ignored
    analysis_type: Optional[str] = None,         # deprecated, ignored
) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | Yes | - | Path to the audio file (the mix) |
| `genre` | str | No | `None` | Genre of the track (see below). It picks dance or song section names when `edm` is not given |
| `edm` | bool | No | `None` | `True`: dance section names (INTRO, UP, CHORUS, DOWN, OUTRO). `False`: song section names (INTRO, VERSE, UP, CHORUS, OUTRO). Default: from the genre, else from the audio |
| `features` | List[str] | No | `None` | Add-ons to run with the analysis (see below). None: the fast analysis only |
| `results_folder` | str | No | `None` | Folder to save results (uses default if `None`) |
| `on_progress` | Callable | No | `None` | Called with the analysis execution after every status check (with `features`: the pipeline status). It carries `warmup` while a machine starts |
| `expand_beats` | bool | No | `True` | Add `beat_times` and `bar_times` computed from `grid`. 2.0 makes this opt-in |
| `api_key` | str | No | `None` | API key to use (uses default if `None`) |
| `poll_interval` | float | No | `3` (`5` with `features`) | Seconds between status checks |
| `max_wait` | float | No | `900` | Seconds to wait for the analysis |
| `components`, `analysis_type` | | No | | No longer used. Accepted by name and ignored, with a `DeprecationWarning` |

The parameters keep their 1.5 order. `edm`, `expand_beats` and `max_wait` are keyword-only.

#### Available Features

`features` names the add-ons to run with the analysis, as 1.5 named them:

- `mode`, `energy`, `loudness`, `danceability`, `tatum`, `key` - [audio features](#audio-features)
- `tags` - [tags](#tags)
- `lyrics` - [lyrics](#lyrics)

#### Available Genres

`"Default"`, `"Afro House"`, `"Tech House"`, `"Bass House"`, `"Blues"`, `"Breakbeat"`, `"Classic Rock"`, `"Country"`, `"Deep House"`, `"Drum N Bass"`, `"Dubstep"`, `"Gospel"`, `"Grime140"`, `"House"`, `"Indie"`, `"Jazz"`, `"Latin"`, `"Metal"`, `"Minimal House"`, `"Pop"`, `"R&B"`, `"Rock"`, `"Techno"`, `"Trance"`, `"Trap"`, `"UK Garage"`

#### Returns

A dictionary containing:
- `analysis_id`: The analysis's id, for the add-ons
- `audio_segmentation`: The analysis with every add-on result so far (the merged view,
  `GET /db/{userId}/execution/{exeId}/analysis`):
  - `format_version` (4), `duration`, `bpm`, `tempo_mode`, `time_signature`, `bar1`,
    `song_start`, `mood`, `mode`
  - `grid`: the [tempo map](#the-tempo-map)
  - `sections`: `[{label, start, end, start_bar, bars, phrases, ...}, ...]`
  - `phrases`, `lead_in`
  - `song_analysis`: what the add-ons have filled so far: `energy`, `danceability`, `loudness`,
    `mode`, `mode_confidence`, `tatum`, `key` (audio features), `genre`, `song_tags` (tags),
    `lyrics`, `lyrics_lines` (lyrics). `{}` before any add-on has run
  - `segment_analysis`: one object per section, with the same per-section values (`{}` until an
    add-on fills it) and each section's `lyrics`
  - `first_vocal_beat_time`: when the vocals start (once lyrics exist)
  - `beat_times`, `bar_times`: with `expand_beats=True`
  - An analysis from before the tempo map (format 2 or 3) has its own `beat_times` and
    `bar_times` instead of `grid`
- `segmentation`: The same object, under its 1.5 name
- `execution`: The analysis execution (with `features`: the final pipeline status)
- `files`: `{folder, files}` -- the saved `analysis.json`
- `warnings`: With `features`, the add-ons that could not be made (only when there are some)

#### Example

```python
import audial

song = audial.segment("path/to/audio.mp3", genre="Tech House")
analysis_id = song["analysis_id"]

for section in song["audio_segmentation"]["sections"]:
    print(f"{section['start']:7.2f}  {section['label']}")

# The add-ons, one call each, any time later
features = audial.audio_features(analysis_id)
tags = audial.tags(analysis_id)
lyrics = audial.lyrics(analysis_id)

# Or everything in one call, as in 1.5 (slower)
full = audial.segment("path/to/audio.mp3", features=["energy", "danceability", "tags", "lyrics"])
print(full["audio_segmentation"]["song_analysis"]["energy"])
```

Cost: an analysis counts as one run. Everything you add to it (features, tags, lyrics, a sample
pack) is included. Calling those on their own, without an analysis, counts as a run each (for
example `generate_samples(file_path)`, which makes its own analysis).

#### The tempo map

Beats and bars aren't listed one by one. `grid` describes them: where each constant-tempo piece
starts, its BPM, and its bar and beat. Every beat time is `start + k × 60 / bpm`. Most tracks
have one piece.

```python
"grid": {
  "beats_per_bar": 4, "tolerance_ms": 25, "max_error_ms": 9.2,
  "beat_count": 841, "bar_count": 208,
  "pieces": [{"start": 0.195, "bpm": 129.0, "bar": -2, "beat": 1, "count": 841}]
}
```

The whole rule: for each piece, beat `k` (from 0 to `count - 1`) is at `start + k × 60 / bpm`
and carries the label (`bar`, `beat`); the beat then moves on by one, and after beat
`beats_per_bar` comes beat 1 of the next bar. Beat times are all the pieces' beats in order,
rounded to 3 decimals. Bar times are the beats with `beat == 1` and `bar >= 1`; bars 0 and below
are the lead-in before bar 1. Every expanded beat is within `tolerance_ms` of the detected beat.

`audial.grid` implements it with the standard library only:

| Function | Returns |
|----------|---------|
| `audial.grid.expand(grid)` | `[(time, bar, beat), ...]` for every beat |
| `audial.grid.beat_times(grid)` | every beat time (`len == grid["beat_count"]`) |
| `audial.grid.bar_times(grid)` | the start of every bar from bar 1 (`len == grid["bar_count"]`) |
| `audial.grid.beats_of(analysis)` | `(beat times, bar times)` of an analysis of any format |

```python
beats, bars = audial.grid.beats_of(song["audio_segmentation"])
```

With `expand_beats=True` (the 1.6 default) `segment()` adds `beat_times` and `bar_times` itself,
so scripts written for older results keep working; the first time, a `FutureWarning` says that
2.0 makes this opt-in. Pass `expand_beats=False` and use `audial.grid` to be ready for 2.0.

### Analysis Add-ons

Each add-on is one call on an analysis, any time after it: `audial.audio_features`,
`audial.tags`, `audial.lyrics` and `audial.generate_samples(analysis_id=...)` ([Sample Pack
Generation](#sample-pack-generation)). Each starts its run
(`POST /functions/run/{audio-features | audio-tags | lyrics | sample-pack}` with
`{userId, analysisExeId}`), waits for it, and returns its result, which is also saved as
`<results folder>/<analysis_id>_analysis/<features|tags|lyrics>.json`.

- **Prerequisites.** Every add-on needs an analysis (`audial.segment()`). Tags, lyrics and the
  sample pack also read the analysis's stems, which are made automatically in the background
  as soon as the analysis starts; there is nothing to do. Until they are ready the API answers
  `409 STEMS_NOT_READY` ("This track is still being prepared. Try again in a minute."), and the
  SDK keeps trying for up to `wait_s` seconds. If making the stems failed, the SDK starts it
  again once. Audio features need only the mix.
- **Cost.** An analysis counts as one run. Everything you add to it (features, tags, lyrics, a
  sample pack) is included. Calling those on their own, without an analysis, counts as a run
  each.
- **Repeats.** A call while that add-on is running, or after it finished, returns that run's
  result instead of starting another; `rerun=True` makes a new one.
- **Older analyses.** Analyses made by the `segmentation` pipeline before 1.6 work too (their id
  from your history is accepted). One that kept no stems answers `409 ADDON_UNAVAILABLE`.

#### Function Signatures

```python
audial.audio_features(analysis_id: str, **options) -> Dict[str, Any]
audial.tags(analysis_id: str, **options) -> Dict[str, Any]
audial.lyrics(analysis_id: str, **options) -> Dict[str, Any]
```

All three take the same options:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `analysis_id` | str | - | The `analysis_id` that `segment()` returned |
| `rerun` | bool | `False` | Make a new result even if one exists |
| `wait_s` | float | `600` | Seconds to keep trying while the stems are being made (or the analysis is still running) |
| `max_wait` | float | `900` | Seconds to wait for the result once the run has started. It keeps running after that; calling again collects it |
| `poll_interval` | float | `5` | Seconds between status checks |
| `results_folder` | str | `None` | Folder to save the result in (uses default if `None`) |
| `api_key` | str | `None` | API key to use (uses default if `None`) |
| `on_progress` | Callable | `None` | Called with the run's execution record after every check; it carries `warmup` while a machine starts |

`audial.lyrics` is also the module of the [per-note lyric grammar](#per-note-lyrics):
`audial.lyrics(analysis_id)` calls the add-on, and `audial.lyrics.parse_per_note_lyrics` and
the rest stay where they were.

#### Audio features

Energy, danceability, loudness, mode, key and beat division (tatum), for the song and for each
section. Energy and danceability are 0–100% (0 to 1 in the result). Energy reflects loudness,
rhythmic activity and low end. Danceability reflects how strong and regular the beat is. Both
are measured per section, so a drop reads higher than its breakdown. Loudness is in LUFS and
follows the broadcast standard over both channels; it reads 3–6 LU higher than in results from
before 1.6.

```python
features = audial.audio_features(analysis_id)
{
  "features_version": 1,
  "song": {"key": "A min", "key_source": "detected", "loudness": -7.1, "energy": 0.62,
           "danceability": 0.71, "mode": "aeolian", "mode_confidence": 0.8, "tatum": "1/16"},
  "sections": [{"index": 0, "label": "INTRO", "start": 0.2, "end": 30.0,
                "energy": 0.41, "danceability": 0.55, ...}, ...],
  "warnings": []
}
```

A value that could not be measured is `None`.

#### Tags

Genre, moods, instruments and artist tags for the mix and for each of its parts (drums, bass,
melody and vocals), plus a written description of the track. The values are exactly what the Audial
website shows: use the genres as they are.

```python
tags = audial.tags(analysis_id)
{
  "genre": ["UK Garage", "Speed Garage"],
  "song_tags": {
    "full":   {"moods": [...], "instruments": [...], "artist_tags": [...]},
    "drums":  {"moods": [...], "instruments": [...], "silent": False},
    "bass":   {"moods": [...], "instruments": [...], "silent": False},
    "melody": {"moods": [...], "instruments": [...], "silent": False},
    "vocals": {"moods": [...], "instruments": [...], "silent": False}
  },
  "description": "A driving UK garage cut ...",   # "" when none was made
  "warnings": []
}
```

Every list is present, empty when nothing was found. A part whose stem is silent has
`"silent": True` and empty lists (for `vocals`, the track has no vocals). An analysis made before
the drums and vocals were tagged has the first three parts only and no description (`""`). The same
values are in `song_analysis` of the analysis (`genre`, `song_tags`, `description`).

#### Lyrics

The lyrics with a start and end for every word, in seconds on the track's timeline: ready for
a karaoke-style highlight.

```python
lyrics = audial.lyrics(analysis_id)
{
  "lyrics": "hello there ...",
  "is_instrumental": False,
  "lines": [
    {"start": 12.34, "end": 13.10,
     "words": [["hello", 12.34, 12.71], ["there", 12.80, 13.10]]},
    ...
  ],
  "segments": [{"text": "hello there", "start": 12.34, "end": 13.10}, ...],
  "section_lyrics": ["", "hello there ...", ...],   # one per section of the analysis
  "first_vocal_beat_time": 12.34,                   # None without vocals
  "warnings": []
}

for line in lyrics["lines"]:
    for word, start, end in line["words"]:
        print(f"{start:7.2f}  {word}")
```

An instrumental has `is_instrumental` `True` and no lines ("No vocals in this track."). After
lyrics have run, the merged view (`segment()`'s result) also has them as
`song_analysis.lyrics_lines`, each section's `lyrics`, and `first_vocal_beat_time`. See
[examples/lyrics_lines.py](examples/lyrics_lines.py).

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

Generate a sample pack from an audio file, or from an analysis you already have.

- **From a file** (`file_path`): this runs the `sample-pack` [pipeline](#pipelines). The
  analysis and the stems start together (step `prepare`), then the pack is built from them
  (step `sample-pack`), in a single API call. Tempo and key are detected automatically.
  `execution` in the result is the pipeline status, so every step and its timing is visible
  there; `audial.pipelines.run("sample-pack", ...)` is the same job without the downloads. It
  counts as one run.
- **From an analysis** (`analysis_id`): the pack is built from that analysis's stems and
  sections, with no new analysis or stem split. It is an [add-on](#analysis-add-ons), included
  with the analysis. The stems are made in the background as soon as the analysis starts;
  until they are ready the API answers `409 STEMS_NOT_READY` and the SDK keeps trying for up to
  `wait_s` seconds.

#### Function Signature

```python
audial.generate_samples(
    file_path: Optional[str] = None,
    job_type: Optional[str] = None,
    components: Optional[List[str]] = None,
    genre: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None,
    poll_interval: float = 5,
    analysis_id: Optional[str] = None,
    wait_s: float = 600,
    max_wait: float = 900
) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | One of `file_path`, `analysis_id` | - | Path to the audio file |
| `job_type` | str | No | `"sample_pack"` | Type of sample pack job to run |
| `components` | List[str] | No | `["drums", "bass", "melody"]` | Components to include in the sample pack |
| `genre` | str | No | `"Default"` | Genre of the track (not used with `analysis_id`) |
| `results_folder` | str | No | `None` | Folder to save results (uses default if `None`) |
| `api_key` | str | No | `None` | API key to use (uses default if `None`) |
| `on_progress` | Callable | No | `None` | Called with the pipeline status after every poll (with `analysis_id`: the sample-pack run's execution record) |
| `poll_interval` | float | No | `5` | Seconds between status polls |
| `analysis_id` | str | One of `file_path`, `analysis_id` | `None` | An analysis of yours: the `analysis_id` that `segment()` returned |
| `wait_s` | float | No | `600` | With `analysis_id`: seconds to keep trying while the stems are being made |
| `max_wait` | float | No | `900` | With `analysis_id`: seconds to wait for the pack once it has started |

#### Available Components

- `drums` - Drum samples
- `bass` - Bass samples
- `melody` - Melodic samples

#### Available Genres

Same as [Audio Segmentation](#audio-segmentation).

#### Returns

A dictionary containing:
- `execution`: The final pipeline status (steps, outputs, timings); with `analysis_id`, the
  analysis record
- `files`: Information about downloaded files
  - `folder`: Path to the results folder
  - `files`: Dictionary mapping filenames to local file paths
- `analysis_id`: With `analysis_id`, the analysis's id
- `components`: With `analysis_id`, what each part gave:
  `{"drums": {"status": "ok" | "empty" | "failed" | "skipped", ...}, ...}`

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

# From an analysis: its stems and sections, included with it
song = audial.segment("path/to/audio.mp3", genre="Tech House")
pack = audial.generate_samples(analysis_id=song["analysis_id"], components=["drums", "bass"])
print(pack["components"])
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

Synthesize a [Vital](https://vital.audio/) synth preset that reproduces the timbre of one
isolated sound. This is a paid function -- it requires an active Audial subscription in
addition to a valid API key (see [Error Handling](#error-handling)).

**Input:** One isolated sound: a single note, chord stab or hit, ideally 1-4 seconds and dry, 20 seconds at most. Not a loop, melody, drum pattern or anything with several notes in sequence: those produce a poor preset even under 20 seconds. To use a loop, trim it to one note first.

#### Function Signature

```python
audial.sound2vital(
    file_path: str,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    max_wait: float = 360,
    poll_interval: float = 5,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None
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
| `on_progress` | callable | No | `None` | Called with the execution record after every poll -- see [Cold Starts and Service Status](#cold-starts-and-service-status) |

#### Returns

A dictionary containing:
- `execution`: API response data
- `files`: Information about downloaded files
  - `folder`: Path to the results folder
  - `files`: Dictionary mapping filenames to local file paths (the `.vital` preset plus
    any generated render/keyboard/report files)
- `preset`: Local path to the downloaded `.vital` preset, if the job produced one
- `scores`: `generation_metadata.scores` -- `huang_similarity`, `at_threshold`,
  `threshold`, `model` -- if present. `at_threshold: False` means a weaker match, usually
  because the input was not one isolated sound
- `report`: `generation_metadata.report`, if present
- `warnings`: `generation_metadata.warnings` list, if present. Includes a note when the
  input sounds like several notes in a row

#### Example

```python
import audial

result = audial.sound2vital("path/to/clip.wav")

print(f"Preset: {result['preset']}")
print(f"Similarity score: {result['scores']['huang_similarity']}")
```

### Sound-to-Serum 2 Resynthesis (sound2serum)

Synthesize a [Serum 2](https://xferrecords.com/products/serum-2) preset that reproduces
the timbre of one isolated sound. No Audial plugin is needed for this one -- the output
is a `.SerumPreset` file opened directly in Xfer's Serum 2. This is a paid function -- it
requires an active Audial subscription in addition to a valid API key (see [Error
Handling](#error-handling)).

**Input:** One isolated sound: a single note, chord stab or hit, ideally 1-4 seconds and dry, 20 seconds at most. Not a loop, melody, drum pattern or anything with several notes in sequence: those produce a poor preset even under 20 seconds. To use a loop, trim it to one note first.

Serum runs take about 2.5 minutes, plus up to another 2.5 minutes if a worker has to
cold-start -- `max_wait` defaults higher than `sound2vital`'s to cover that.

#### Function Signature

```python
audial.sound2serum(
    file_path: str,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    max_wait: float = 480,
    poll_interval: float = 5,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None
) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | Yes | - | Path to the input audio file. Must be 20 seconds or shorter |
| `results_folder` | str | No | `None` | Folder to save results (uses default if `None`) |
| `api_key` | str | No | `None` | API key to use (uses default if `None`) |
| `max_wait` | float | No | `480` | Maximum seconds to wait for completion (Serum runs take ~2.5 min, plus up to ~2.5 min for a cold start) |
| `poll_interval` | float | No | `5` | Seconds between execution status polls |
| `on_progress` | callable | No | `None` | Called with the execution record after every poll -- see [Cold Starts and Service Status](#cold-starts-and-service-status) |

#### Returns

A dictionary containing:
- `execution`: API response data
- `files`: Information about downloaded files
  - `folder`: Path to the results folder
  - `files`: Dictionary mapping filenames to local file paths (the `.SerumPreset`
    preset plus any generated render/keyboard/report files)
- `preset`: Local path to the downloaded `.SerumPreset` preset, if the job produced
  one. Saved as `<source file stem>.SerumPreset` -- Serum shows the file name as the
  preset name, so naming it after your sample is what shows up inside Serum
- `scores`: `generation_metadata.scores` -- `huang_similarity`, `at_threshold`,
  `threshold`, `model` -- if present. `at_threshold: False` means a weaker match, usually
  because the input was not one isolated sound
- `report`: `generation_metadata.report`, if present
- `warnings`: `generation_metadata.warnings` list, if present. Includes a note when the
  input sounds like several notes in a row

#### Example

```python
import audial

result = audial.sound2serum("path/to/clip.wav")

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
    poll_interval: float = 5,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None
) -> Dict[str, Any]
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `reference_file` | str | Yes | - | Path to a short (5-10s) reference voice clip -- the voice to sing in |
| `lyrics` | str | Yes | - | The lyrics to sing. In `per_note` mode this is pipe-delimited, one token per MIDI note -- see [Per-note lyrics](#per-note-lyrics) |
| `midi_file` | str | One of midi_file/melody_audio_file | `None` | Path to a MIDI file driving the melody |
| `melody_audio_file` | str | One of midi_file/melody_audio_file | `None` | Path to override melody audio (skips strict-pitch synthesis) |
| `word_timestamps_file` | str | No | `None` | Path to a word-timestamps JSON, used by auto-align |
| `lyrics_mode` | str | No | `"auto"` | `"auto"` (word count matches MIDI notes, auto-aligns via word_timestamps), `"per_note"` (pipe-delimited, one token per note -- see [Per-note lyrics](#per-note-lyrics)), or `"1to1"` (passed straight through) |
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
| `on_progress` | callable | No | `None` | Called with the execution record after every poll -- see [Cold Starts and Service Status](#cold-starts-and-service-status) |

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

#### Per-note lyrics

`lyrics_mode="per_note"` gives you a syllable per MIDI note. The lyrics are pipe-delimited,
one token per note, and there is exactly one concept beyond "a syllable on a note": a
**hold**, which means "keep singing the previous syllable through this note".

| Token | Meaning |
|-------|---------|
| `grace` | Sung on this note |
| `-` | Hold: continue the previous syllable through this note (the documented form) |
| `+` | Hold as well (a Synthesizer V habit) |
| *empty* | Hold as well -- what a double pipe `a\|\|b` produces |

A token may be a whole word spread over several notes:

```python
import audial

result = audial.text2vox(
    reference_file="voice_clip.wav",
    midi_file="melody.mid",          # 9 notes
    lyrics="amazing|-|-|grace|-|how|sweet|the|sound",
    lyrics_mode="per_note",
)
```

Here "amazing" is sung across notes 1-3 and "grace" across notes 4-5; the held notes are
merged into their predecessor before synthesis and their pitch movement is kept as a bend,
so the sung line still follows the drawn melody and the returned MIDI shows the merged
notes.

**There is no rest token.** A note that should be silent should not be in the MIDI at all.

Two rules apply:

1. The token count must equal the MIDI note count.
2. The first token must be a syllable -- a hold continues something, and there is nothing
   before note 1.

Rule 2 (and an empty lyric string) is checked by the SDK **before anything is uploaded**,
so a typo costs no uploads and creates no execution:

```python
from audial.api.exceptions import AudialValidationError

try:
    audial.text2vox(..., lyrics="-|grace", lyrics_mode="per_note")
except AudialValidationError as e:
    print(e)           # note 1 has no syllable; the first note needs one
    print(e.position)  # 1 -- the 1-based note the message is about
```

Rule 1 needs the MIDI, so it is the API's; it comes back as the same exception, raised
from the API's `400 {"code": "LYRICS_INVALID", "position", "message"}` response:

```
9 tokens for 10 notes; the first unmatched note starts at 2.4 s
```

`audial.text2vox_tokens()` answers "how many notes does this lyric string need?" without
running anything, and raises the same error for input that cannot be sung:

```python
tokens = audial.text2vox_tokens("amazing|-|-|grace|-|how|sweet|the|sound")
len(tokens)                               # 9 -- notes required
[t.text for t in tokens if not t.hold]    # ['amazing', 'grace', 'how', 'sweet', 'the', 'sound']
tokens[1]                                 # Token(text='', hold=True)
```

`auto` and `1to1` are unchanged, and every per-note string that worked before renders
identically.

### Cold Starts and Service Status

Audial's GPU workers scale to zero. The first request after an idle period has to start a
worker and load the model before any audio is processed, which adds a few minutes to that
one job; every run after it is fast. Without a word about it, a cold start looks exactly
like a hung job.

The API decides warm vs cold before it dispatches and writes the phase onto the execution
(and onto each pipeline step), so every client reads the same field:

```python
"warmup": {
  "state": "cold" | "initializing" | "working" | "done",
  "expectedColdStartMs": 180000,   # this endpoint's recent cold-start p50
  "expectedRunMs": 42000,
  "delayMs": 174000                # state "done": what the wait actually cost
}
```

Every function that polls -- `text2vox`, `sound2vital`, `sound2serum`, `generate_music`,
`stem_split`, `master`, `generate_midi`, `analyze`, `segment`, the add-ons `audio_features`,
`tags` and `lyrics`, and `generate_samples` -- takes an optional `on_progress` callback that receives each status as
it arrives. `audial.warmup` turns one into the sentence the CLI, the website and the MCP
server all show, and `WarmupTracker` reduces the stream to one line per change:

```python
import audial

tracker = audial.warmup.WarmupTracker()

def report(status):
    for line in tracker.changes(status):
        print(line)

audial.sound2vital("kick.wav", on_progress=report)
# Warming up the machine - the first request takes a few minutes longer than
# usual (about 3 min); every run after this is faster
# Working on your job...
```

`audial.status()` wraps `GET /functions/status`, which can be called *before* a job exists
-- the only way to explain the wait before someone sits through it:

```python
doc = audial.status("text2vox")
# {'items': [{'function': 'text2vox', 'warm': False, 'queued': 0,
#             'expectedColdStartMs': 180000, 'expectedRunMs': 42000}]}

if audial.warmup.is_cold(doc, "text2vox"):
    print(audial.warmup.cold_start_message(
        audial.warmup.find_function(doc, "text2vox").get("expectedColdStartMs")
    ))
```

`status()` accepts either an SDK name (`"generate_samples"`) or the API's own name
(`"sample-pack"`), and omitting it reports every function.

The analysis add-ons run on machines of their own (`audio-features`, `audio-tags`, `lyrics` and
`sample-pack`), so the first add-on after a quiet period can wait for a machine to start even
when the analysis was quick ("Starting up — this can take a minute"). Their `on_progress`
receives the add-on run's execution record, with its `warmup`, and `audial.status("tags")`
(or `"audio_features"`, `"lyrics"`) asks before you call. Tags, lyrics and the sample pack can
also wait for the analysis's stems, which is reported as "Preparing the track…". The call is cached server-side
and costs no rate-limit allowance. The CLI does this automatically before every job (see
[Service Status Command](#service-status-command)).

### Error Handling

The SDK provides custom exception classes for better error handling:

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
    # Input rejected before (or instead of) running anything -- today this is
    # per-note lyrics; `position` is the 1-based note the message is about
except SubscriptionRequiredError as e:
    print(f"Subscription required: {e}")
    # sound2vital, sound2serum and text2vox require an active Audial subscription
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

The analysis add-ons (`audio_features`, `tags`, `lyrics`, `generate_samples(analysis_id=...)`)
raise `AudialAPIError` with `status_code` 409 and `code` set when the API refuses them:

| `code` | Message | When |
|--------|---------|------|
| `STEMS_NOT_READY` | "This track is still being prepared. Try again in a minute." | Tags, lyrics or a sample pack whose stems were still being made after `wait_s` seconds. The SDK retries this answer by itself until then. When the stems could not be made at all (the SDK restarts them once), the message starts "We couldn't prepare this track." |
| `ADDON_UNAVAILABLE` | "This result can't be added to this analysis." | The add-on's inputs can't be found, for example an older analysis that kept no stems. While the analysis itself is still running, the SDK waits instead |

```python
try:
    lyrics = audial.lyrics(analysis_id, wait_s=120)
except AudialAPIError as e:
    if e.code == "STEMS_NOT_READY":
        print("Still preparing the track; try again in a minute")
    elif e.code == "ADDON_UNAVAILABLE":
        print("This analysis can't have lyrics")
    else:
        raise
```

Every `AudialAPIError` has `status_code` (the HTTP status, or `None` for a network error) and
`code` (the API's error code, when it sent one).

Note: `SubscriptionRequiredError` is a subclass of `AudialAPIError`, so an `except
AudialAPIError` clause also catches it -- catch `SubscriptionRequiredError` first if you
need to handle it differently (e.g. prompting the user to subscribe).
`AudialValidationError` is a subclass of `AudialError` and carries a `position`; see
[Per-note lyrics](#per-note-lyrics).

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

Run a whole pipeline in one call, printing a line per step change: `sample-pack` (the
analysis and its stems, then the pack) or `segmentation` (the analysis, then its add-ons).

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

Find a track's sections, tempo and bars in about half a minute. It prints the analysis id,
which the [add-on commands](#analysis-add-on-commands) take.

#### Basic Segmentation

```bash
audial segment path/to/audio.mp3
```

#### Specific Genre

```bash
audial segment path/to/audio.mp3 --genre "Tech House"
```

#### Section Names

```bash
audial segment path/to/audio.mp3 --edm      # INTRO, UP, CHORUS, DOWN, OUTRO
audial segment path/to/audio.mp3 --no-edm   # INTRO, VERSE, UP, CHORUS, OUTRO
```

#### With Add-ons (as in 1.5)

```bash
audial segment path/to/audio.mp3 --features energy loudness danceability tags lyrics
```

Runs the `segmentation` pipeline, which waits for the add-ons too, so it takes longer.

#### JSON Output

```bash
audial segment path/to/audio.mp3 --json
```

#### Custom Results Folder

```bash
audial segment path/to/audio.mp3 --results-folder path/to/custom/folder
```

#### Custom API Key

```bash
audial segment path/to/audio.mp3 --api-key your_custom_api_key
```

### Analysis Add-on Commands

`features`, `tags` and `lyrics` take an analysis id (from `audial segment`) or an audio file;
a file is analysed first. Each waits for its result and prints it. They are included with the
analysis.

```bash
audial features <analysis_id>      # energy, danceability, loudness, mode, key, beat division
audial tags <analysis_id>          # genre, moods, instruments, artist tags
audial lyrics <analysis_id>        # timed lines
audial lyrics path/to/audio.mp3 --genre "Pop"
```

| Flag | Description |
|------|-------------|
| `--genre` | Genre of the track, when a file is analysed first |
| `--rerun` | Make a new result even if one exists |
| `--wait-s` | Seconds to keep trying while the track is being prepared (default 600) |
| `--json` | Print the result as JSON (progress goes to stderr) |
| `--results-folder` | Folder to save results |
| `--api-key` | API key to use |

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

#### From an Analysis

```bash
audial generate-samples --analysis-id <analysis_id> --components drums bass
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

### sound2serum Commands

Requires an active Audial subscription. No Audial plugin is needed -- the output is a
`.SerumPreset` file opened directly in Xfer's Serum 2. Serum runs take about 2.5 minutes,
plus up to another 2.5 minutes if a worker has to cold-start.

#### Basic Usage

```bash
audial sound2serum path/to/clip.wav
```

#### Custom Results Folder

```bash
audial sound2serum path/to/clip.wav --results-folder path/to/custom/folder
```

#### Custom API Key

```bash
audial sound2serum path/to/clip.wav --api-key your_custom_api_key
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

One token per MIDI note; `-` (or `+`, or an empty token) holds the previous syllable
through that note, so a word can span notes. See [Per-note lyrics](#per-note-lyrics).

```bash
audial text2vox voice_clip.wav "amazing|-|-|grace|-|how|sweet|the|sound" \
  --midi melody.mid --lyrics-mode per_note
```

A lyric string that cannot be sung is refused before anything is uploaded:

```
Error: note 1 has no syllable; the first note needs one
```

#### Custom Results Folder

```bash
audial text2vox path/to/voice_clip.wav "la la la la" --midi path/to/melody.mid --results-folder path/to/custom/folder
```

#### Custom API Key

```bash
audial text2vox path/to/voice_clip.wav "la la la la" --midi path/to/melody.mid --api-key your_custom_api_key
```

### Service Status Command

Which functions have a worker awake right now (`GET /functions/status`):

```bash
audial status
```

```
Service status:
  text2vox: warming up
    Warming up the machine - the first request takes a few minutes longer than usual (about 3 min); every run after this is faster
  sample-pack: ready
  stem-splitter: ready, 2 queued
```

One function, or the raw document:

```bash
audial status --function text2vox
audial status --json
```

Every command that runs a job makes this check itself before it submits, and then prints
each warm-up phase as the job reports it, so a cold start is explained rather than looking
like a hang. See [Cold Starts and Service Status](#cold-starts-and-service-status).

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

Some functions may include additional fields with function-specific data, such as `analysis` for the `analyze` function, and `analysis_id` and `audio_segmentation` for `segment`. The analysis add-ons (`audio_features`, `tags`, `lyrics`) return their result itself (see [Analysis Add-ons](#analysis-add-ons)).