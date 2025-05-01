# Audial SDK Usage Guide

This guide explains how to use the Audial SDK for audio analysis and manipulation.

## Table of Contents

- [Basic Concepts](#basic-concepts)
- [Audio Processing Functions](#audio-processing-functions)
  - [Stem Splitting](#stem-splitting)
  - [Audio Analysis](#audio-analysis)
  - [Audio Segmentation](#audio-segmentation)
  - [Audio Mastering](#audio-mastering)
  - [Sample Pack Generation](#sample-pack-generation)
  - [MIDI Generation](#midi-generation)
- [Results Management](#results-management)
- [Command Line Interface](#command-line-interface)
- [Advanced Usage](#advanced-usage)

## Basic Concepts

The Audial SDK provides both a Python API and a command-line interface (CLI) for audio processing. All functions follow a consistent pattern:

1. Submit an audio file for processing
2. Wait for processing to complete
3. Download and save the results
4. Return structured data about the operation

Results are automatically saved to a local folder (default: `./audial_results/`).

## Audio Processing Functions

### Stem Splitting

Split an audio track into its component parts:

```python
import audial

# Basic stem splitting (extracts vocals, drums, bass, other)
result = audial.stem_split("path/to/your/audio.mp3")

# Access the paths to the downloaded files
stems_folder = result["files"]["folder"]
vocals_path = result["files"]["files"]["vocals.mp3"]
drums_path = result["files"]["files"]["drums.mp3"]
bass_path = result["files"]["files"]["bass.mp3"]
other_path = result["files"]["files"]["other.mp3"]

# Custom stem splitting with specific stems and adjustments
result = audial.stem_split(
    "path/to/your/audio.mp3",
    stems=["vocals", "drums", "full_song_without_vocals"],
    target_bpm=120,
    target_key="Cmaj"
)
```

**Available stem options:**
- `vocals` - Vocal track
- `drums` - Drum track
- `bass` - Bass track
- `other` - All other instruments
- `full_song_without_vocals` - Full mix minus vocals
- `full_song_without_drums` - Full mix minus drums
- `full_song_without_bass` - Full mix minus bass
- `full_song_without_other` - Full mix minus other instruments

### Audio Analysis

Analyze an audio track to extract BPM, key, and other metadata:

```python
analysis = audial.analyze("path/to/your/audio.mp3")

# Access analysis results
bpm = analysis["execution"]["original"]["bpm"]
key = analysis["execution"]["original"]["key"]

print(f"BPM: {bpm}")
print(f"Key: {key}")
```

### Audio Segmentation

Segment an audio track into sections and extract features:

```python
segments = audial.segment(
    "path/to/your/audio.mp3", 
    components=["intro", "verse", "chorus", "outro"],
    features=["energy", "tempo", "loudness"],
    genre="electronic"
)

# The segmentation files are saved to the results folder
segmentation_json = segments["files"]["files"]["audio_segmentation.json"]
features_plot = segments["files"]["files"].get("features_plot.png")
```

### Audio Mastering

Master an audio track:

```python
# Basic mastering
mastered = audial.master("path/to/your/audio.mp3")

# Mastering with reference track
mastered = audial.master(
    "path/to/your/audio.mp3",
    reference_file="path/to/reference.mp3"
)

# Get the path to the mastered file
master_file = mastered["files"]["files"].get("master.mp3")
```

### Sample Pack Generation

Generate a sample pack from an audio track:

```python
samples = audial.generate_samples(
    "path/to/your/audio.mp3",
    job_type="drums",
    components=["kick", "snare", "hihat"],
    genre="electronic"
)

# Access the sample pack folder
samples_folder = samples["files"]["folder"]
```

### MIDI Generation

Convert an audio track to MIDI:

```python
midi = audial.generate_midi(
    "path/to/your/audio.mp3",
    bpm=120
)

# Get the path to the MIDI file
midi_file = midi["files"]["files"].get("output.mid")
```

## Results Management

All function results are saved to a local directory. You can configure the results folder:

```python
# Set custom results folder
audial.config.set_results_folder("path/to/custom/results/folder")

# Get current results folder
current_folder = audial.config.get_results_folder()
```

Each function returns a dictionary with two main sections:

1. `execution`: Contains the API response data
2. `files`: Contains information about downloaded files
   - `folder`: The path to the results folder
   - `files`: A dictionary mapping filenames to local file paths

Example result structure:

```python
{
    "execution": {
        "exeId": "-OObjYxEV8EOKbVSEVE8",
        "state": "completed",
        "original": {
            "bpm": 129,
            "key": "Bmin",
            "filename": "track.mp3",
            "url": "https://storage.googleapis.com/..."
        },
        # Other execution data...
    },
    "files": {
        "folder": "./audial_results/-OObjYxEV8EOKbVSEVE8_stem",
        "files": {
            "bass.mp3": "./audial_results/-OObjYxEV8EOKbVSEVE8_stem/bass.mp3",
            "drums.mp3": "./audial_results/-OObjYxEV8EOKbVSEVE8_stem/drums.mp3",
            "other.mp3": "./audial_results/-OObjYxEV8EOKbVSEVE8_stem/other.mp3",
            "vocals.mp3": "./audial_results/-OObjYxEV8EOKbVSEVE8_stem/vocals.mp3",
            "results.json": "./audial_results/-OObjYxEV8EOKbVSEVE8_stem/results.json"
        }
    }
}
```

## Command Line Interface

The SDK also provides a command-line interface:

```bash
# Stem splitting
audial stem-split path/to/audio.mp3 --stems vocals,drums,bass,other

# Audio analysis
audial analyze path/to/audio.mp3

# Segmentation
audial segment path/to/audio.mp3 --components intro,verse,chorus,outro

# Mastering
audial master path/to/audio.mp3 --reference path/to/reference.mp3

# Sample pack generation
audial generate-samples path/to/audio.mp3 --job-type drums --components kick,snare,hihat

# MIDI generation
audial generate-midi path/to/audio.mp3 --bpm 120

# Configuration
audial config --api-key your_api_key_here
audial config --results-folder path/to/results/folder
audial config show
```

Use the `--verbose` or `-v` flag to see detailed output:

```bash
audial analyze path/to/audio.mp3 --verbose
```

## Advanced Usage

### Error Handling

Proper error handling in your applications:

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

### Custom API Keys

You can provide custom API keys for specific operations:

```python
# Use a specific API key for this operation
result = audial.analyze(
    "path/to/audio.mp3",
    api_key="your_custom_api_key_here"
)
```

### Working with Large Files

For large files, you might want to use a custom results folder on a drive with ample space:

```python
import os
from pathlib import Path

# Create a dedicated folder on an external drive
external_drive = "/mnt/external"
results_dir = os.path.join(external_drive, "audial_results")
os.makedirs(results_dir, exist_ok=True)

# Set as the results folder
audial.config.set_results_folder(results_dir)

# Process a large audio file
result = audial.stem_split("path/to/large_audio_file.wav")
```

### Processing Multiple Files

Example of batch processing multiple files:

```python
import os
import audial

def process_directory(directory, output_dir):
    """Process all audio files in a directory."""
    # Set the results folder
    audial.config.set_results_folder(output_dir)
    
    # Get all audio files
    audio_files = [
        os.path.join(directory, f) for f in os.listdir(directory)
        if f.endswith(('.mp3', '.wav', '.flac', '.aiff', '.m4a'))
    ]
    
    results = []
    for audio_file in audio_files:
        print(f"Processing: {os.path.basename(audio_file)}")
        try:
            # Process the file
            result = audial.stem_split(audio_file)
            results.append((audio_file, result))
            print(f"Completed: {os.path.basename(audio_file)}")
        except Exception as e:
            print(f"Error processing {os.path.basename(audio_file)}: {e}")
    
    return results

# Example usage
results = process_directory("./my_audio_files", "./my_results")
```

## Additional Resources

- [Example Scripts](https://github.com/audial/audial-sdk/tree/main/examples)
- [API Reference](https://audial.io/docs/sdk/api-reference)
- [FAQ](https://audial.io/docs/sdk/faq)