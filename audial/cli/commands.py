"""
Command-line interface for Audial SDK.
"""

import os
import sys
import argparse
import json
from typing import List, Optional, Dict, Any

from audial.functions.analyze import analyze
from audial.functions.master import master
from audial.functions.midi import generate_midi
from audial.functions.samples import generate_samples
from audial.functions.segment import segment
from audial.functions.stem_split import stem_split
from audial.functions.generate_music import generate_music
from audial.utils.config import get_api_key, get_results_folder, set_api_key, set_results_folder, get_user_id, set_user_id
from audial.api.exceptions import AudialError


def setup_analyze_parser(subparsers):
    """Setup the parser for the analyze command."""
    parser = subparsers.add_parser(
        'analyze',
        help='Analyze an audio file to extract metadata like BPM, key, and other characteristics'
    )
    parser.add_argument('file_path', help='Path to the audio file')
    parser.add_argument('--results-folder', help='Folder to save results (uses default if not specified)')
    parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
    parser.set_defaults(func=analyze_command)


def setup_master_parser(subparsers):
    """Setup the parser for the master command."""
    parser = subparsers.add_parser(
        'master',
        help='Apply professional mastering to an audio file'
    )
    parser.add_argument('file_path', help='Path to the audio file to master')
    parser.add_argument('--reference', dest='reference_file', required=True, 
                       help='Path to a reference file to match sound characteristics (required)')
    parser.add_argument('--results-folder', help='Folder to save results (uses default if not specified)')
    parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
    parser.set_defaults(func=master_command)


def setup_generate_midi_parser(subparsers):
    """Setup the parser for the generate-midi command."""
    parser = subparsers.add_parser(
        'generate-midi',
        help='Generate MIDI data from one or more audio files'
    )
    parser.add_argument('file_paths', nargs='+', help='Path to one or more audio files')
    parser.add_argument('--bpm', type=float, help='Override BPM for the MIDI generation')
    parser.add_argument('--results-folder', help='Folder to save results (uses default if not specified)')
    parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
    parser.set_defaults(func=generate_midi_command)


def setup_generate_samples_parser(subparsers):
    """Setup the parser for the generate-samples command."""
    parser = subparsers.add_parser(
        'generate-samples',
        help='Generate a sample pack from an audio file'
    )
    parser.add_argument('file_path', help='Path to the audio file')
    parser.add_argument('--job-type', default='sample_pack', choices=['sample_pack'],
                       help='Type of sample pack job to run (default: sample_pack)')
    parser.add_argument('--components', nargs='+', default=['drums', 'bass', 'melody'],
                       choices=['drums', 'bass', 'melody'],
                       help='Components to include in the sample pack (default: drums bass melody)')
    parser.add_argument('--genre', default='Default',
                       choices=[
                           "Default", "Afro House", "Tech House", "Bass House", "Blues", "Breakbeat",
                           "Classic Rock", "Country", "Deep House", "Drum N Bass", "Dubstep", "Gospel",
                           "Grime140", "House", "Indie", "Jazz", "Latin", "Metal", "Minimal House",
                           "Pop", "R&B", "Rock", "Techno", "Trance", "Trap", "UK Garage"
                       ],
                       help='Genre of the track (default: Default)')
    parser.add_argument('--results-folder', help='Folder to save results (uses default if not specified)')
    parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
    parser.set_defaults(func=generate_samples_command)


def setup_segment_parser(subparsers):
    """Setup the parser for the segment command."""
    parser = subparsers.add_parser(
        'segment',
        help='Segment an audio file into logical sections and analyze its components'
    )
    parser.add_argument('file_path', help='Path to the audio file')
    # Components is not configurable by the user as per requirements
    parser.add_argument('--analysis-type', default='select_features',
                       help='Type of analysis to perform (default: select_features)')
    parser.add_argument('--features', nargs='+',
                       default=['mode', 'energy', 'loudness', 'danceability', 'tatum', 'lyrics', 'tags'],
                       choices=['mode', 'energy', 'loudness', 'danceability', 'tatum', 'lyrics', 'key', 'tags'],
                       help='Features to extract')
    parser.add_argument('--genre', default='Default',
                       choices=[
                           "Default", "Afro House", "Tech House", "Bass House", "Blues", "Breakbeat",
                           "Classic Rock", "Country", "Deep House", "Drum N Bass", "Dubstep", "Gospel",
                           "Grime140", "House", "Indie", "Jazz", "Latin", "Metal", "Minimal House",
                           "Pop", "R&B", "Rock", "Techno", "Trance", "Trap", "UK Garage"
                       ],
                       help='Genre of the track (default: Default)')
    parser.add_argument('--results-folder', help='Folder to save results (uses default if not specified)')
    parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
    parser.set_defaults(func=segment_command)


def setup_stem_split_parser(subparsers):
    """Setup the parser for the stem-split command."""
    parser = subparsers.add_parser(
        'stem-split',
        help='Split an audio file into separate stems'
    )
    parser.add_argument('file_path', help='Path to the audio file')
    parser.add_argument('--stems', nargs='+', 
                       choices=['vocals', 'drums', 'bass', 'other', 
                               'full_song_without_vocals', 'full_song_without_drums',
                               'full_song_without_bass', 'full_song_without_other'],
                       default=['vocals', 'drums', 'bass', 'other'],
                       help='List of stems to extract (default: vocals drums bass other)')
    parser.add_argument('--target-bpm', type=float, help='Target BPM for tempo adjustment')
    parser.add_argument('--target-key', help='Target key for pitch adjustment')
    parser.add_argument('--algorithm', default='primaudio', choices=['primaudio', 'quintessound'],
                      help='Algorithm to use for stem separation (default: primaudio)')
    parser.add_argument('--results-folder', help='Folder to save results (uses default if not specified)')
    parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
    parser.set_defaults(func=stem_split_command)


def setup_generate_music_parser(subparsers):
    """Setup the parser for the generate command."""
    parser = subparsers.add_parser(
        'generate',
        help='Generate music from a text prompt using the ACE-Step 1.5 model'
    )
    parser.add_argument('prompt', help='Text describing the desired music style, mood, genre')
    parser.add_argument('--task-type', '-t', default='text2music',
                       choices=['text2music', 'cover', 'remix', 'extract',
                                'lego', 'complete', 'understand'],
                       help='Generation mode (default: text2music)')
    parser.add_argument('--source', '-s', dest='source_file', default=None,
                       help='Source audio file path (required for remix/extract/lego/complete/understand)')
    parser.add_argument('--reference', '-r', dest='reference_file', default=None,
                       help='Reference audio file path (required for cover mode)')
    parser.add_argument('--lyrics', '-l', default=None, help='Song lyrics')
    parser.add_argument('--bpm', type=int, default=None, help='Target BPM')
    parser.add_argument('--key', dest='key_scale', default=None,
                       help="Musical key (e.g. 'C major')")
    parser.add_argument('--duration', dest='audio_duration', type=float, default=None,
                       help='Duration in seconds (10-600)')
    parser.add_argument('--batch-size', '-b', type=int, default=1,
                       help='Number of variations to generate (1-8, default: 1)')
    parser.add_argument('--format', '-f', dest='audio_format', default='mp3',
                       choices=['mp3', 'flac', 'wav', 'opus', 'aac'],
                       help='Output audio format (default: mp3)')
    parser.add_argument('--instrumental', action='store_true',
                       help='Generate without vocals')
    parser.add_argument('--seed', type=int, default=None, help='Random seed for reproducibility')
    parser.add_argument('--steps', dest='inference_steps', type=int, default=50,
                       help='Inference steps (8=fast/turbo, 50=quality, default: 50)')
    parser.add_argument('--guidance', dest='guidance_scale', type=float, default=7.0,
                       help='Guidance scale (1.0-15.0, default: 7.0)')
    parser.add_argument('--cover-strength', dest='audio_cover_strength', type=float, default=None,
                       help='Cover/remix fidelity to original (0.0-1.0)')
    parser.add_argument('--track-name', default=None,
                       help='Track to extract/replace (extract/lego modes)')
    parser.add_argument('--negative-prompt', default=None,
                       help='Text describing what to avoid')
    parser.add_argument('--results-folder', help='Folder to save results (uses default if not specified)')
    parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
    parser.set_defaults(func=generate_music_command)


def setup_config_parser(subparsers):
    """Setup the parser for the config command."""
    parser = subparsers.add_parser(
        'config',
        help='Configure Audial SDK settings'
    )
    parser.add_argument('--api-key', help='Set the API key')
    parser.add_argument('--user-id', help='Set the user ID')  # Add this line
    parser.add_argument('--results-folder', help='Set the results folder path')
    parser.add_argument('--show', action='store_true', help='Show current configuration')
    parser.set_defaults(func=config_command)


def analyze_command(args) -> Dict[str, Any]:
    """Handle the analyze command."""
    try:
        result = analyze(
            file_path=args.file_path,
            results_folder=args.results_folder,
            api_key=args.api_key
        )
        
        # Print a summary of the results
        print("\nAnalysis Results:")
        print(f"BPM: {result['analysis'].get('bpm')}")
        print(f"Key: {result['analysis'].get('key')}")
        print(f"\nResults saved to: {result['files']['folder']}")
        
        # Return the full result for programmatic use if needed
        return result
    
    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def master_command(args) -> Dict[str, Any]:
    """Handle the master command."""
    try:
        # Validate that reference file is different from file_path
        if args.file_path == args.reference_file:
            raise ValueError("The reference file must be different from the input file")
        
        result = master(
            file_path=args.file_path,
            reference_file=args.reference_file,
            results_folder=args.results_folder,
            api_key=args.api_key
        )
        
        # Print a summary of the results
        print("\nMastering Results:")
        print(f"Files downloaded: {len(result['files']['files'])}")
        print(f"\nResults saved to: {result['files']['folder']}")
        
        # Return the full result for programmatic use if needed
        return result
    
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def generate_midi_command(args) -> Dict[str, Any]:
    """Handle the generate-midi command."""
    try:
        # Use file_paths as a list even if only one path is provided
        result = generate_midi(
            file_path=args.file_paths,
            bpm=args.bpm,
            results_folder=args.results_folder,
            api_key=args.api_key
        )
        
        # Print a summary of the results
        print("\nMIDI Generation Results:")
        print(f"Files downloaded: {len(result['files']['files'])}")
        print(f"\nResults saved to: {result['files']['folder']}")
        
        # Return the full result for programmatic use if needed
        return result
    
    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def generate_samples_command(args) -> Dict[str, Any]:
    """Handle the generate-samples command."""
    try:
        result = generate_samples(
            file_path=args.file_path,
            job_type=args.job_type,
            components=args.components,
            genre=args.genre,
            results_folder=args.results_folder,
            api_key=args.api_key
        )
        
        # Print a summary of the results
        print("\nSample Generation Results:")
        print(f"Files downloaded: {len(result['files']['files'])}")
        print(f"\nResults saved to: {result['files']['folder']}")
        
        # Return the full result for programmatic use if needed
        return result
    
    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def segment_command(args) -> Dict[str, Any]:
    """Handle the segment command."""
    try:
        # Always use the default components as per requirements
        components = ['bass', 'beat', 'melody', 'vocal']
        
        result = segment(
            file_path=args.file_path,
            components=components,  # Always use default components
            analysis_type=args.analysis_type,
            features=args.features,
            genre=args.genre,
            results_folder=args.results_folder,
            api_key=args.api_key
        )
        
        # Print a summary of the results
        print("\nSegmentation Results:")
        print(f"Files downloaded: {len(result['files']['files'])}")
        print(f"\nResults saved to: {result['files']['folder']}")
        
        # Return the full result for programmatic use if needed
        return result
    
    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def stem_split_command(args) -> Dict[str, Any]:
    """Handle the stem-split command."""
    try:
        result = stem_split(
            file_path=args.file_path,
            stems=args.stems,
            target_bpm=args.target_bpm,
            target_key=args.target_key,
            results_folder=args.results_folder,
            api_key=args.api_key,
            algorithm=args.algorithm
        )
        
        # Print a summary of the results
        print("\nStem Splitting Results:")
        print(f"Files downloaded: {len(result['files']['files'])}")
        file_names = list(result['files']['files'].keys())
        print(f"Files: {', '.join(file_names)}")
        print(f"\nResults saved to: {result['files']['folder']}")
        
        # Return the full result for programmatic use if needed
        return result
    
    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def generate_music_command(args) -> Dict[str, Any]:
    """Handle the generate command."""
    try:
        result = generate_music(
            prompt=args.prompt,
            task_type=args.task_type,
            source_file=args.source_file,
            reference_file=args.reference_file,
            lyrics=args.lyrics,
            bpm=args.bpm,
            key_scale=args.key_scale,
            audio_duration=args.audio_duration,
            batch_size=args.batch_size,
            audio_format=args.audio_format,
            instrumental=args.instrumental,
            seed=args.seed,
            inference_steps=args.inference_steps,
            guidance_scale=args.guidance_scale,
            audio_cover_strength=args.audio_cover_strength,
            track_name=args.track_name,
            negative_prompt=args.negative_prompt,
            results_folder=args.results_folder,
            api_key=args.api_key,
        )

        if args.task_type == "understand":
            print("\nCaption Result:")
            for k, v in result.get("caption_result", {}).items():
                print(f"  {k}: {v}")
        else:
            files = result.get("files", {}).get("files", {})
            print(f"\nGenerated {len(files)} file(s):")
            for name, path in files.items():
                print(f"  {path}")

        return result

    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def config_command(args) -> None:
    """Handle the config command."""
    try:
        # Set API key if provided
        if args.api_key:
            set_api_key(args.api_key)
            print(f"API key has been set")
        
        # Set user ID if provided
        if args.user_id:  # Add this block
            set_user_id(args.user_id)
            print(f"User ID has been set")
        
        # Set results folder if provided
        if args.results_folder:
            # Ensure the directory exists
            os.makedirs(args.results_folder, exist_ok=True)
            set_results_folder(args.results_folder)
            print(f"Results folder set to: {args.results_folder}")
        
        # Show current configuration if requested or if no other options provided
        if args.show or (not args.api_key and not args.user_id and not args.results_folder):
            current_api_key = get_api_key()
            current_user_id = get_user_id()  # Add this
            current_results_folder = get_results_folder()
            
            print("\nCurrent Configuration:")
            # Print redacted API key for security
            if current_api_key:
                masked_key = current_api_key[:4] + "*" * (len(current_api_key) - 8) + current_api_key[-4:]
                print(f"API Key: {masked_key}")
            else:
                print("API Key: Not set")
            
            # Print user ID
            if current_user_id:  # Add this block
                print(f"User ID: {current_user_id}")
            else:
                print("User ID: Not set")
            
            print(f"Results Folder: {current_results_folder}")
    
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def cli():
    """Main entry point for the Audial CLI."""
    parser = argparse.ArgumentParser(
        description='Audial SDK command-line interface for audio analysis and manipulation',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    subparsers = parser.add_subparsers(
        title='commands',
        dest='command',
        help='Command to execute',
        required=True
    )
    
    # Setup all command parsers
    setup_analyze_parser(subparsers)
    setup_master_parser(subparsers)
    setup_generate_midi_parser(subparsers)
    setup_generate_samples_parser(subparsers)
    setup_generate_music_parser(subparsers)
    setup_segment_parser(subparsers)
    setup_stem_split_parser(subparsers)
    setup_config_parser(subparsers)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Execute the appropriate command but don't return its result
    args.func(args)
    
    # Return success exit code
    return 0


# Keep main() for backwards compatibility or direct script execution
def main():
    return cli()


if __name__ == '__main__':
    cli()