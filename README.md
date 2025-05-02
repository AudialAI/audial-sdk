# Audial SDK

![Audial Logo](https://your-logo-url-here.png)

A powerful Python SDK for audio analysis and manipulation through the Audial API.

## Overview

The Audial SDK provides a user-friendly interface to Audial's powerful audio processing capabilities. With just a few lines of code, you can perform professional-grade audio operations including:

- **Stem Splitting**: Separate tracks into individual components (vocals, drums, bass, other)
- **Audio Analysis**: Extract BPM, key signatures, and other audio metadata
- **Audio Segmentation**: Identify logical sections in audio tracks
- **Audio Mastering**: Apply professional mastering to your tracks
- **Sample Pack Generation**: Create reusable samples from audio tracks
- **MIDI Generation**: Convert audio to MIDI data

The SDK supports both a Python API for integration into your projects and a command-line interface for direct use.

## Installation

### Prerequisites

Before installing the Audial SDK, ensure you have the following:

- Python 3.7 or higher
- pip package manager (typically included with Python)
- An Audial API key and User ID (obtain from the [Audial website](https://audialmusic.ai))

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
git clone https://github.com/audial/audial-sdk.git

# Navigate to the project directory
cd audial-sdk

# Install the package
pip install -e .
```

## Configuration

After installation, you need to configure your API key and User ID. You have several options:

### Option 1: Environment Variables

Set the `AUDIAL_API_KEY` and `AUDIAL_USER_ID` environment variables:

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
audial config show
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
audial config show
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

### Audio Segmentation

Segment an audio track into sections and extract features:

```python
segments = audial.segment(
    "path/to/audio.mp3",
    components=["bass", "beat", "melody", "vocal"],
    analysis_type="select_features",
    features=["energy", "tempo", "loudness", "danceability"],
    genre="electronic"
)
```

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

Generate a sample pack from an audio track:

```python
samples = audial.generate_samples(
    "path/to/audio.mp3",
    job_type="sample_pack",
    components=["drums", "bass", "melody"],
    genre="Tech House"
)
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

## Command Line Interface

The SDK provides a powerful command-line interface:

```bash
# Stem splitting
audial stem-split audio.mp3 --stems vocals,drums,bass,other

# Audio analysis
audial analyze audio.mp3

# Segmentation
audial segment audio.mp3 --features energy,loudness,danceability

# Mastering
audial master audio.mp3 --reference reference.mp3

# Sample pack generation
audial generate-samples audio.mp3 --components drums,bass,melody

# MIDI generation
audial generate-midi audio.mp3 --bpm 120

# Configuration
audial config --api-key your_api_key_here
audial config --user-id your_user_id_here
audial config --results-folder path/to/results
audial config show
```

## Result Format

All functions return a consistent result structure:

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
from audial.api.exceptions import AudialError, AudialAuthError, AudialAPIError

try:
    result = audial.stem_split("path/to/audio.mp3")
except AudialAuthError as e:
    print(f"Authentication error: {e}")
except AudialAPIError as e:
    print(f"API error: {e}")
except AudialError as e:
    print(f"General error: {e}")
```

## Advanced Usage

See the [API Documentation](API_DOCUMENTATION.md) for detailed information about all functions and their parameters.

## Examples

The SDK includes example scripts in the [examples directory](examples/):

- [Stem Splitting](examples/stem_splitting.py)
- [Audio Analysis](examples/analysis.py)
- [Audio Segmentation](examples/segmentation.py)
- [Audio Mastering](examples/mastering.py)
- [Sample Pack Generation](examples/sample_generation.py)
- [MIDI Generation](examples/midi_generation.py)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or feedback, please [create an issue](https://github.com/audial/audial-sdk/issues) on our GitHub repository or contact support@audial.io.