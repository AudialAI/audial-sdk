# Audial SDK Installation Guide

This guide provides step-by-step instructions for installing and configuring the Audial SDK.

## Prerequisites

Before installing the Audial SDK, ensure you have the following:

- Python 3.7 or higher
- pip package manager (typically included with Python)
- An Audial API key (obtain from the [Audial website](https://audial.io))

## Installation Methods

### 1. Install from PyPI (Recommended)

The simplest way to install the Audial SDK is via pip:

```bash
pip install audial-sdk
```

### 2. Install from Source

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

After installation, you need to configure your API key. You have several options:

### Option 1: Environment Variable

Set the `AUDIAL_API_KEY` environment variable:

**Linux/macOS:**
```bash
export AUDIAL_API_KEY=your_api_key_here
```

**Windows (Command Prompt):**
```cmd
set AUDIAL_API_KEY=your_api_key_here
```

**Windows (PowerShell):**
```powershell
$env:AUDIAL_API_KEY = "your_api_key_here"
```

### Option 2: .env File

Create a file named `.env` in your project directory:

```
AUDIAL_API_KEY=your_api_key_here
```

### Option 3: Configuration Command

Use the built-in configuration command:

```bash
# Set API key via CLI
audial config --api-key your_api_key_here

# Set results folder
audial config --results-folder path/to/results/folder
```

### Option 4: Python Code

Set the API key programmatically in your Python code:

```python
import audial
audial.config.set_api_key("your_api_key_here")
```

## Verifying Installation

You can verify that the SDK is correctly installed and configured:

```bash
# Check the version
python -c "import audial; print(audial.__version__)"

# Check configuration
audial config show
```

## Troubleshooting

If you encounter issues during installation:

### Dependency Issues

If you have dependency conflicts, try installing in a virtual environment:

```bash
# Create and activate a virtual environment
python -m venv audial-env
source audial-env/bin/activate  # Linux/macOS
# or
audial-env\Scripts\activate  # Windows

# Install the SDK (not going to work yet)
pip install audial-sdk
```

### Permission Issues

If you encounter permission errors during installation:

```bash
# Install for the current user only (not going to work yet)
pip install --user audial-sdk
```

### API Key Issues

If you get authentication errors:

1. Verify your API key is correct
2. Check that the key is being properly set/loaded
3. Ensure your account has the necessary permissions

## Next Steps

Once installed, you can proceed to the [usage guide](USAGE.md) to learn how to use the Audial SDK.