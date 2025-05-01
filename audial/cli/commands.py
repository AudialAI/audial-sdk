"""
Command-line interface commands for the Audial SDK.
"""

import sys
import json
import click
from typing import List, Optional

import audial
from audial.api.constants import ALL_STEM_OPTIONS
from audial.api.exceptions import AudialError, AudialAuthError
from audial.utils.config import get_api_key, set_api_key, get_results_folder, set_results_folder

# Helper functions
def _print_json(data):
    """Print JSON data in a formatted way."""
    click.echo(json.dumps(data, indent=2))

def _validate_stems(ctx, param, value):
    """Validate stem options."""
    if not value:
        return None
    
    stems = value.split(",")
    invalid_stems = [stem for stem in stems if stem not in ALL_STEM_OPTIONS]
    
    if invalid_stems:
        raise click.BadParameter(
            f"Invalid stem type(s): {', '.join(invalid_stems)}. "
            f"Valid options are: {', '.join(ALL_STEM_OPTIONS)}"
        )
    
    return stems

def _validate_list(ctx, param, value):
    """Convert comma-separated string to list."""
    if not value:
        return None
    
    return value.split(",")

def _handle_error(func):
    """Decorator to handle errors in CLI commands."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AudialAuthError as e:
            click.echo(f"Authentication error: {str(e)}", err=True)
            click.echo("Please set your API key using 'audial config --api-key YOUR_API_KEY'", err=True)
            sys.exit(1)
        except AudialError as e:
            click.echo(f"Error: {str(e)}", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"Unexpected error: {str(e)}", err=True)
            sys.exit(1)
    
    return wrapper

# CLI command group
@click.group()
def cli():
    """Audial SDK command-line interface."""
    pass

# Configuration commands
@cli.group()
def config():
    """Configure the Audial SDK."""
    pass

@config.command("api-key")
@click.argument("api_key", required=True)
def config_api_key(api_key: str):
    """Set the API key."""
    set_api_key(api_key)
    click.echo("API key set successfully.")

@config.command("results-folder")
@click.argument("folder", required=True)
def config_results_folder(folder: str):
    """Set the results folder."""
    set_results_folder(folder)
    click.echo(f"Results folder set to: {folder}")

@config.command("show")
def config_show():
    """Show current configuration."""
    api_key = get_api_key()
    results_folder = get_results_folder()
    
    if api_key:
        masked_key = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]
        click.echo(f"API key: {masked_key}")
    else:
        click.echo("API key: Not set")
    
    click.echo(f"Results folder: {results_folder}")

# Audio processing commands
@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--stems", help="Comma-separated list of stems to extract", callback=_validate_stems)
@click.option("--target-bpm", type=float, help="Target BPM for tempo adjustment")
@click.option("--target-key", help="Target key for pitch adjustment")
@click.option("--results-folder", type=click.Path(), help="Folder to save results")
@_handle_error
def stem_split(file_path: str, stems: Optional[List[str]], target_bpm: Optional[float], target_key: Optional[str], results_folder: Optional[str]):
    """Split an audio file into separate stems."""
    click.echo(f"Stem splitting: {file_path}")
    
    result = audial.stem_split(
        file_path,
        stems=stems,
        target_bpm=target_bpm,
        target_key=target_key,
        results_folder=results_folder
    )
    
    click.echo(f"Stem splitting completed. Results saved to: {result['files']['folder']}")
    
    # List downloaded files
    click.echo("\nDownloaded files:")
    for filename, filepath in result["files"]["files"].items():
        click.echo(f"  - {filename}: {filepath}")

@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--results-folder", type=click.Path(), help="Folder to save results")
@_handle_error
def analyze(file_path: str, results_folder: Optional[str]):
    """Analyze an audio file to extract BPM, key, and other metadata."""
    click.echo(f"Analyzing: {file_path}")
    
    result = audial.analyze(
        file_path,
        results_folder=results_folder
    )
    
    # Display analysis results
    original = result["execution"].get("original", {})
    click.echo("\nAnalysis results:")
    click.echo(f"  BPM: {original.get('bpm')}")
    click.echo(f"  Key: {original.get('key')}")
    
    # Show full JSON if verbose
    if "--verbose" in sys.argv:
        click.echo("\nFull response:")
        _print_json(result)

@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--components", help="Comma-separated list of components to segment", callback=_validate_list)
@click.option("--analysis-type", help="Type of analysis to perform")
@click.option("--features", help="Comma-separated list of features to extract", callback=_validate_list)
@click.option("--genre", help="Genre of the track")
@click.option("--results-folder", type=click.Path(), help="Folder to save results")
@_handle_error
def segment(file_path: str, components: Optional[List[str]], analysis_type: Optional[str], features: Optional[List[str]], genre: Optional[str], results_folder: Optional[str]):
    """Segment an audio file into logical sections and extract features."""
    click.echo(f"Segmenting: {file_path}")
    
    result = audial.segment(
        file_path,
        components=components,
        analysis_type=analysis_type,
        features=features,
        genre=genre,
        results_folder=results_folder
    )
    
    click.echo(f"Segmentation completed. Results saved to: {result['files']['folder']}")
    
    # List downloaded files
    click.echo("\nDownloaded files:")
    for filename, filepath in result["files"]["files"].items():
        click.echo(f"  - {filename}: {filepath}")

@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--reference", type=click.Path(exists=True), help="Reference file for matching sound characteristics")
@click.option("--results-folder", type=click.Path(), help="Folder to save results")
@_handle_error
def master(file_path: str, reference: Optional[str], results_folder: Optional[str]):
    """Apply professional mastering to an audio file."""
    click.echo(f"Mastering: {file_path}")
    
    if reference:
        click.echo(f"Using reference: {reference}")
    
    result = audial.master(
        file_path,
        reference_file=reference,
        results_folder=results_folder
    )
    
    click.echo(f"Mastering completed. Results saved to: {result['files']['folder']}")
    
    # List downloaded files
    click.echo("\nDownloaded files:")
    for filename, filepath in result["files"]["files"].items():
        click.echo(f"  - {filename}: {filepath}")

@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--job-type", help="Type of sample pack to generate")
@click.option("--components", help="Comma-separated list of components to include", callback=_validate_list)
@click.option("--genre", help="Genre of the track")
@click.option("--results-folder", type=click.Path(), help="Folder to save results")
@_handle_error
def generate_samples(file_path: str, job_type: Optional[str], components: Optional[List[str]], genre: Optional[str], results_folder: Optional[str]):
    """Generate a sample pack from an audio file."""
    click.echo(f"Generating samples from: {file_path}")
    
    result = audial.generate_samples(
        file_path,
        job_type=job_type,
        components=components,
        genre=genre,
        results_folder=results_folder
    )
    
    click.echo(f"Sample pack generation completed. Results saved to: {result['files']['folder']}")
    
    # List downloaded files
    click.echo("\nDownloaded files:")
    for filename, filepath in result["files"]["files"].items():
        click.echo(f"  - {filename}: {filepath}")

@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--bpm", type=float, help="BPM to use for the MIDI generation")
@click.option("--results-folder", type=click.Path(), help="Folder to save results")
@_handle_error
def generate_midi(file_path: str, bpm: Optional[float], results_folder: Optional[str]):
    """Generate MIDI data from an audio file."""
    click.echo(f"Generating MIDI from: {file_path}")
    
    result = audial.generate_midi(
        file_path,
        bpm=bpm,
        results_folder=results_folder
    )
    
    click.echo(f"MIDI generation completed. Results saved to: {result['files']['folder']}")
    
    # List downloaded files
    click.echo("\nDownloaded files:")
    for filename, filepath in result["files"]["files"].items():
        click.echo(f"  - {filename}: {filepath}")

# Add verbose option to all commands
for command in [stem_split, analyze, segment, master, generate_samples, generate_midi]:
    command.params.append(
        click.Option(
            ["--verbose", "-v"],
            is_flag=True,
            help="Show detailed output"
        )
    )

if __name__ == "__main__":
    cli()