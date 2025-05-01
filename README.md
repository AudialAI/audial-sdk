# Audial SDK

A Python SDK for interacting with the Audial audio processing API.

## Installation (still need to deploy on pypi)

```bash
pip install audial-sdk
```

## Configuration

You need to set your API key and User ID to use the Audial SDK. You can obtain an API key from the [Audial website](https://audialmusic.ai).

There are several ways to set your API key:

### Environment Variable

### .env File

Create a file named `.env` in your project root:

```
AUDIAL_API_KEY=your_api_key_here
AUDIAL_USER_ID=you_user_id_here
```

### Python Code

```python
import audial
audial.config.set_api_key("your_api_key_here")
```

## Basic Usage

```python
import audial

# Stem splitting
result = audial.stem_split("path/to/audio.mp3")
print(f"Stem files saved to: {result['files']['folder']}")

# Audio analysis
analysis = audial.analyze("path/to/audio.mp3")
print(f"BPM: {analysis['execution']['original']['bpm']}")
print(f"Key: {analysis['execution']['original']['key']}")

# Segmentation
segments = audial.segment("path/to/audio.mp3")

# Mastering
mastered = audial.master("path/to/audio.mp3")

# Sample pack generation
samples = audial.generate_samples("path/to/audio.mp3")

# MIDI generation
midi = audial.generate_midi("path/to/audio.mp3")
```

## Command Line Interface

The SDK also provides a command-line interface:

```bash
still need to fix these
```

## Results Management

By default, all function results are saved to a folder named `./audial_results/` in your current working directory. You can configure the results folder:

```python
# Set custom results folder
audial.config.set_results_folder("path/to/custom/results/folder")
```

Or using the CLI:

```bash
audial config --results-folder path/to/custom/results/folder
```

## Documentation

For detailed documentation and examples, see the [Audial SDK Documentation](need to create page).