"""
Command-line interface for Audial SDK.
"""

import os
import sys
import argparse
import contextlib
import json
from typing import List, Optional, Dict, Any

from audial.functions.analyze import analyze
from audial.functions.master import master
from audial.functions.midi import generate_midi
from audial.functions.samples import generate_samples
from audial.functions.segment import segment
from audial.functions.audio_features import audio_features
from audial.functions.tags import tags
from audial.functions.lyrics import lyrics as lyrics_addon
from audial.functions.stem_split import stem_split
from audial.functions.generate_music import generate_music
from audial.functions.sound2vital import sound2vital
from audial.functions.sound2serum import sound2serum
from audial.functions.text2vox import text2vox
from audial import pipelines
from audial import warmup
from audial.status import status as functions_status
from audial.api.constants import (
    ADDON_DEFAULT_WAIT_S,
    INSTRUMENTAL_TEXT,
    PIPELINE_FIRST_FUNCTION,
    PIPELINES,
    STATUS_FUNCTIONS,
)
from audial.utils.config import get_api_key, get_results_folder, set_api_key, set_results_folder, get_user_id, set_user_id
from audial.api.exceptions import AudialError
from audial.api import device_login
from audial.utils import config as audial_config


GENRE_CHOICES = [
    "Default", "Afro House", "Tech House", "Bass House", "Blues", "Breakbeat",
    "Classic Rock", "Country", "Deep House", "Drum N Bass", "Dubstep", "Gospel",
    "Grime140", "House", "Indie", "Jazz", "Latin", "Metal", "Minimal House",
    "Pop", "R&B", "Rock", "Techno", "Trance", "Trap", "UK Garage"
]


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
        help='Generate a sample pack from an audio file, or from an analysis with --analysis-id'
    )
    parser.add_argument('file_path', nargs='?', default=None,
                       help='Path to the audio file (leave out with --analysis-id)')
    parser.add_argument('--analysis-id', default=None,
                       help='Make the pack from an analysis instead (its stems and sections; included with it)')
    parser.add_argument('--job-type', default='sample_pack', choices=['sample_pack'],
                       help='Type of sample pack job to run (default: sample_pack)')
    parser.add_argument('--components', nargs='+', default=['drums', 'bass', 'melody'],
                       choices=['drums', 'bass', 'melody'],
                       help='Components to include in the sample pack (default: drums bass melody)')
    parser.add_argument('--genre', default='Default', choices=GENRE_CHOICES,
                       help='Genre of the track (default: Default)')
    parser.add_argument('--results-folder', help='Folder to save results (uses default if not specified)')
    parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
    parser.set_defaults(func=generate_samples_command)


SEGMENT_HELP = (
    "Find a track's sections, tempo and bars in about half a minute. "
    "Add audio features, tags or lyrics afterwards with `audial features`, `audial tags` "
    "and `audial lyrics` on the analysis id it prints"
)


def setup_segment_parser(subparsers):
    """Setup the parser for the segment command."""
    parser = subparsers.add_parser('segment', help=SEGMENT_HELP, description=SEGMENT_HELP)
    parser.add_argument('file_path', help='Path to the audio file (the mix; no stems needed)')
    parser.add_argument('--genre', default=None, choices=GENRE_CHOICES,
                       help='Genre of the track; it picks dance or song section names')
    edm = parser.add_mutually_exclusive_group()
    edm.add_argument('--edm', dest='edm', action='store_const', const=True, default=None,
                     help='Dance section names: INTRO, UP, CHORUS, DOWN, OUTRO')
    edm.add_argument('--no-edm', dest='edm', action='store_const', const=False,
                     help='Song section names: INTRO, VERSE, UP, CHORUS, OUTRO')
    parser.add_argument('--features', nargs='+', default=None,
                       choices=['mode', 'energy', 'loudness', 'danceability', 'tatum', 'lyrics', 'key', 'tags'],
                       help='Also run these add-ons with the analysis (slower: tags and lyrics wait for '
                            'the stems). Default: none')
    # Accepted for scripts written for 1.5; no longer used.
    parser.add_argument('--analysis-type', default=None, help=argparse.SUPPRESS)
    parser.add_argument('--json', dest='as_json', action='store_true',
                       help='Print the result as JSON instead of a summary')
    parser.add_argument('--results-folder', help='Folder to save results (uses default if not specified)')
    parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
    parser.set_defaults(func=segment_command)


ADDON_COMMANDS = {
    'features': (
        'Get audio features (energy, danceability, loudness, mode, key, beat division) for an '
        'analysis id or an audio file (a file is analysed first)'
    ),
    'tags': (
        'Get tags (genre, moods, instruments, artist tags) for an analysis id or an audio file '
        '(a file is analysed first)'
    ),
    'lyrics': (
        'Get lyrics with word timings for an analysis id or an audio file (a file is analysed first)'
    ),
}


def setup_addon_parsers(subparsers):
    """Setup the parsers for the features, tags and lyrics commands."""
    for name, text in ADDON_COMMANDS.items():
        parser = subparsers.add_parser(name, help=text, description=(
            text + '. Included with the analysis. Tags and lyrics read the analysis\'s stems, '
            'which are made in the background; until they are ready this waits '
            '("This track is still being prepared").'
        ))
        parser.add_argument('target', metavar='analysis_id_or_file',
                           help='An analysis id (from `audial segment`) or a path to an audio file')
        parser.add_argument('--genre', default=None, choices=GENRE_CHOICES,
                           help='Genre of the track, when a file is analysed first')
        parser.add_argument('--rerun', action='store_true',
                           help='Make a new result even if one exists')
        parser.add_argument('--wait-s', type=float, default=ADDON_DEFAULT_WAIT_S,
                           help='Seconds to keep trying while the track is being prepared '
                                f'(default: {ADDON_DEFAULT_WAIT_S})')
        parser.add_argument('--json', dest='as_json', action='store_true',
                           help='Print the result as JSON instead of a summary')
        parser.add_argument('--results-folder', help='Folder to save results (uses default if not specified)')
        parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
        parser.set_defaults(func=addon_command, addon=name)


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
        help='Generate music from a text prompt with the Audial music model'
    )
    parser.add_argument('prompt', help='Text describing the desired music style, mood, genre')
    parser.add_argument('--task-type', '-t', default='text2music',
                       choices=['text2music', 'cover', 'remix', 'lego', 'understand'],
                       help='Generation mode (default: text2music)')
    parser.add_argument('--source', '-s', dest='source_file', default=None,
                       help='Source audio file path (required for remix/lego/understand)')
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


def setup_sound2vital_parser(subparsers):
    """Setup the parser for the sound2vital command."""
    parser = subparsers.add_parser(
        'sound2vital',
        help='Synthesize a Vital preset that reproduces the timbre of one isolated sound, not a loop'
    )
    parser.add_argument('file_path', help='Path to one isolated sound: a single note or hit, 20 seconds at most. Loops give a poor preset')
    parser.add_argument('--results-folder', help='Folder to save results (uses default if not specified)')
    parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
    parser.set_defaults(func=sound2vital_command)


def setup_sound2serum_parser(subparsers):
    """Setup the parser for the sound2serum command."""
    parser = subparsers.add_parser(
        'sound2serum',
        help='Synthesize a Serum 2 preset that reproduces the timbre of one isolated sound, not a loop'
    )
    parser.add_argument('file_path', help='Path to one isolated sound: a single note or hit, 20 seconds at most. Loops give a poor preset')
    parser.add_argument('--results-folder', help='Folder to save results (uses default if not specified)')
    parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
    parser.set_defaults(func=sound2serum_command)


def setup_text2vox_parser(subparsers):
    """Setup the parser for the text2vox command."""
    parser = subparsers.add_parser(
        'text2vox',
        help='Synthesize a sung vocal in the timbre of a reference voice clip, following a melody and lyrics'
    )
    parser.add_argument('reference_file', help='Path to a short (5-10s) reference voice clip')
    parser.add_argument('lyrics',
                       help='Lyrics to sing. With --lyrics-mode per_note: one token per MIDI '
                            'note, pipe-delimited, where "-" (or "+", or an empty token) holds '
                            'the previous syllable through that note, e.g. '
                            '"amazing|-|-|grace|-|how|sweet|the|sound"')
    parser.add_argument('--midi', dest='midi_file', default=None,
                       help='Path to a MIDI file driving the melody (required unless --melody-audio is given)')
    parser.add_argument('--melody-audio', dest='melody_audio_file', default=None,
                       help='Path to override melody audio (required unless --midi is given)')
    parser.add_argument('--word-timestamps', dest='word_timestamps_file', default=None,
                       help='Path to a word-timestamps JSON for the reference clip, used by auto-align')
    parser.add_argument('--lyrics-mode', default='auto', choices=['auto', 'per_note', '1to1'],
                       help='Lyrics alignment mode (default: auto). per_note takes one token '
                            'per MIDI note; see the lyrics argument for the hold grammar')
    parser.add_argument('--reference-text', default=None, help='What is said in the reference clip')
    parser.add_argument('--cfg-strength', type=float, default=None, help='Worker synthesis option')
    parser.add_argument('--nfe-steps', type=int, default=None, help='Worker synthesis option')
    parser.add_argument('--pitch-shift', type=float, default=None, help='Worker synthesis option')
    parser.add_argument('--strict-pitch', action='store_true', default=None, help='Worker synthesis option')
    parser.add_argument('--bend-smoothing-ms', type=float, default=None, help='Worker synthesis option')
    parser.add_argument('--no-pitch-bends', action='store_true', default=None, help='Worker synthesis option')
    parser.add_argument('--leading-silence-s', type=float, default=None, help='Worker synthesis option')
    parser.add_argument('--seed', type=int, default=None, help='Random seed for reproducibility')
    parser.add_argument('--results-folder', help='Folder to save results (uses default if not specified)')
    parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
    parser.set_defaults(func=text2vox_command)


def setup_pipeline_parser(subparsers):
    """Setup the parser for the pipeline command."""
    parser = subparsers.add_parser(
        'pipeline',
        help='Run a multi-step Audial pipeline in one call: segmentation (the analysis, then its add-ons) '
             'or sample-pack (the analysis and stems, then the pack)'
    )
    parser.add_argument('name', choices=sorted(PIPELINES),
                       help='Pipeline to run: ' + '; '.join(
                           f"{name} ({' -> '.join(steps)})" for name, steps in sorted(PIPELINES.items())
                       ))
    parser.add_argument('file_path', help='Path to the audio file')
    parser.add_argument('--genre', default=None,
                       help='Genre hint for the analysis (default: Default)')
    parser.add_argument('--components', nargs='+', default=None,
                       help='Components to process, e.g. drums bass melody (sample-pack) '
                            'or bass beat melody vocal (segmentation)')
    parser.add_argument('--bpm', type=float, default=None,
                       help='Override the detected tempo (BPM)')
    parser.add_argument('--key', dest='key_string', default=None,
                       help="Override the detected key, e.g. 'A minor'")
    parser.add_argument('--no-wait', action='store_true',
                       help='Start the pipeline and print its id without waiting for it')
    parser.add_argument('--poll-interval', type=float, default=5,
                       help='Seconds between status polls (default: 5)')
    parser.add_argument('--json', dest='as_json', action='store_true',
                       help='Print the pipeline status as JSON instead of a summary')
    parser.add_argument('--api-key', help='API key to use (uses default if not specified)')
    parser.set_defaults(func=pipeline_command)


def setup_status_parser(subparsers):
    """Setup the parser for the status command."""
    parser = subparsers.add_parser(
        'status',
        help='Show which Audial functions have a worker awake right now'
    )
    parser.add_argument(
        '--function',
        choices=sorted(STATUS_FUNCTIONS),
        help='Only report this function (default: all of them)'
    )
    parser.add_argument('--json', dest='as_json', action='store_true',
                        help='Print the raw /functions/status document')
    parser.add_argument('--api-key', help='API key to use')
    parser.set_defaults(func=status_command)


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


def setup_login_parsers(subparsers):
    """Setup the parsers for the login, logout and whoami commands."""
    parser = subparsers.add_parser(
        'login',
        help='Sign in to Audial through your browser (no API key to copy)'
    )
    parser.add_argument('--no-browser', action='store_true',
                       help='Print the sign-in link instead of opening a browser')
    parser.set_defaults(func=login_command)

    parser = subparsers.add_parser('logout', help='Sign out of Audial on this computer')
    parser.set_defaults(func=logout_command)

    parser = subparsers.add_parser('whoami', help='Show which Audial account is in use')
    parser.set_defaults(func=whoami_command)


def login_command(args) -> None:
    """Handle the login command."""
    def show(pending):
        print("Sign in to Audial in your browser:\n")
        print(f"  {pending.verification_uri_complete}\n")
        print(f"Check that the page shows this code: {pending.user_code}")
        print("Waiting for you to approve...", flush=True)

    try:
        credentials = device_login.login(
            client_name='audial-cli', open_browser=not args.no_browser, on_prompt=show
        )
    except KeyboardInterrupt:
        print("\nSign-in cancelled.", file=sys.stderr)
        sys.exit(130)
    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    print(f"\nSigned in as {credentials.get('email') or credentials['user_id']}.")
    if os.environ.get('AUDIAL_API_KEY'):
        print("Note: AUDIAL_API_KEY is set in this shell and takes priority over this sign-in.")


def logout_command(args) -> None:
    """Handle the logout command."""
    if device_login.logout():
        print("Signed out.")
    else:
        print("Not signed in.")


def whoami_command(args) -> None:
    """Handle the whoami command."""
    api_key = get_api_key()
    if not api_key:
        print("Not signed in. Run `audial login`.", file=sys.stderr)
        sys.exit(1)
    credentials = audial_config.load_credentials()
    if os.environ.get('AUDIAL_API_KEY'):
        source = "the AUDIAL_API_KEY environment variable"
    elif credentials and credentials['api_key'] == api_key:
        source = "`audial login`"
    else:
        source = "`audial config --api-key`"
    try:
        account = device_login.whoami(api_key) if api_key.startswith('aud_') else {
            'user_id': get_user_id(api_key), 'email': None,
        }
    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    print(f"Account: {account.get('email') or account.get('user_id') or 'unknown'}")
    print(f"User ID: {account.get('user_id') or 'Not set'}")
    print(f"Credentials from: {source}")

def warmup_reporter(function: str, args) -> warmup.WarmupReporter:
    """
    Warm-up output for one command: a pre-flight check, then live changes.

    Audial's workers scale to zero, so the first job after an idle period
    waits for a GPU to start. `GET /functions/status` says whether that is
    about to happen *before* the job is submitted, which is the only way to
    explain the wait to someone watching a terminal; after that the execution
    itself reports each phase and the reporter prints what changed.

    The returned object is the `on_progress` callback to hand to the SDK.
    """
    reporter = warmup.WarmupReporter()
    reporter.preflight(function, api_key=getattr(args, "api_key", None))
    return reporter


def status_command(args) -> Dict[str, Any]:
    """Handle the status command."""
    try:
        doc = functions_status(args.function, api_key=args.api_key)
        if getattr(args, "as_json", False):
            print(json.dumps(doc, indent=2, default=str))
            return doc

        items = [item for item in (doc.get("items") or []) if isinstance(item, dict)]
        if not items:
            print("No function status reported.")
            return doc

        print("\nService status:")
        for item in items:
            warm = item.get("warm")
            label = "ready" if warm else ("warming up" if warm is False else "unknown")
            queued = item.get("queued")
            queued_text = f", {queued} queued" if isinstance(queued, int) and queued else ""
            print(f"  {item.get('function')}: {label}{queued_text}")
            if warm is False:
                print(f"    {warmup.cold_start_message(item.get('expectedColdStartMs'))}")
        return doc

    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def analyze_command(args) -> Dict[str, Any]:
    """Handle the analyze command."""
    try:
        result = analyze(
            file_path=args.file_path,
            results_folder=args.results_folder,
            api_key=args.api_key,
            on_progress=warmup_reporter("analyze", args),
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
            api_key=args.api_key,
            on_progress=warmup_reporter("master", args),
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
            api_key=args.api_key,
            on_progress=warmup_reporter("generate_midi", args),
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
        if bool(args.file_path) == bool(args.analysis_id):
            raise AudialError("Give an audio file or --analysis-id (one of them)")
        result = generate_samples(
            file_path=args.file_path,
            analysis_id=args.analysis_id,
            job_type=args.job_type,
            components=args.components,
            genre=args.genre,
            results_folder=args.results_folder,
            api_key=args.api_key,
            on_progress=warmup_reporter("generate_samples", args),
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


def _quiet_stdout(as_json: bool):
    """With --json, progress lines go to stderr so stdout holds only the JSON."""
    return contextlib.redirect_stdout(sys.stderr) if as_json else contextlib.nullcontext()


def _clock(seconds) -> str:
    if not isinstance(seconds, (int, float)):
        return "?:??"
    return f"{int(seconds // 60)}:{seconds % 60:05.2f}"


def _print_analysis(result: Dict[str, Any]) -> None:
    data = result.get("audio_segmentation") or {}
    analysis_id = result.get("analysis_id")
    print("\nAnalysis:")
    print(f"Analysis ID: {analysis_id}")
    if data.get("bpm"):
        print(f"BPM: {data['bpm']}")
    grid = data.get("grid") if isinstance(data.get("grid"), dict) else {}
    beats = grid.get("beat_count", len(data.get("beat_times") or []))
    bars = grid.get("bar_count", len(data.get("bar_times") or []))
    if beats:
        print(f"Beats: {beats}, bars: {bars}")
    sections = data.get("sections") if isinstance(data.get("sections"), list) else []
    if sections:
        print("Sections:")
        for section in sections:
            if isinstance(section, dict):
                print(f"  {_clock(section.get('start'))}  {section.get('label')}")
    for warning in result.get("warnings") or []:
        print(f"Warning: {warning}")
    files = (result.get("files") or {}).get("files") or {}
    if files:
        print(f"\nResults saved to: {next(iter(files.values()))}")
    if analysis_id:
        print(f"\nNext: audial features {analysis_id} | audial tags {analysis_id} | audial lyrics {analysis_id}")


def segment_command(args) -> Dict[str, Any]:
    """Handle the segment command."""
    try:
        with _quiet_stdout(args.as_json):
            result = segment(
                file_path=args.file_path,
                genre=args.genre,
                edm=args.edm,
                features=args.features,
                results_folder=args.results_folder,
                on_progress=warmup_reporter("segment", args),
                api_key=args.api_key,
            )
        if args.as_json:
            print(json.dumps({k: v for k, v in result.items() if k != "segmentation"}, indent=2, default=str))
        else:
            _print_analysis(result)
        return result

    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


ADDON_FUNCTIONS_BY_COMMAND = {
    'features': ('audio_features', 'Audio features'),
    'tags': ('tags', 'Tags'),
    'lyrics': ('lyrics', 'Lyrics'),
}


def _print_features(result: Dict[str, Any]) -> None:
    song = result.get("song") or {}
    for name, label in (("key", "Key"), ("mode", "Mode"), ("energy", "Energy"),
                        ("danceability", "Danceability"), ("loudness", "Loudness (LUFS)"),
                        ("tatum", "Beat division")):
        if name in song:
            print(f"{label}: {song[name]}")
    sections = result.get("sections") or []
    if sections:
        print("Sections (energy / danceability):")
        for section in sections:
            print(f"  {_clock(section.get('start'))}  {section.get('label')}: "
                  f"{section.get('energy')} / {section.get('danceability')}")


def _print_tags(result: Dict[str, Any]) -> None:
    if result.get("description"):
        print(result["description"])
    print(f"Genre: {', '.join(result.get('genre') or []) or '-'}")
    song_tags = result.get("song_tags") or {}
    for part, label in (("full", "Song"), ("drums", "Drums"), ("bass", "Bass"),
                        ("melody", "Melody"), ("vocals", "Vocals")):
        tags_of = song_tags.get(part) or {}
        if tags_of.get("silent"):
            note = INSTRUMENTAL_TEXT if part == "vocals" else "No " + label.lower() + " in this track."
            print(f"{label}: {note}")
            continue
        for name in ("moods", "instruments", "artist_tags"):
            values = tags_of.get(name) or []
            if values:
                print(f"{label} {name.replace('_', ' ')}: {', '.join(values)}")


def _print_lyrics(result: Dict[str, Any]) -> None:
    lines = result.get("lines") or []
    if result.get("is_instrumental") or not lines:
        print(INSTRUMENTAL_TEXT)
        return
    for line in lines:
        words = " ".join(str(word[0]) for word in line.get("words") or [] if word)
        print(f"  {_clock(line.get('start'))}  {words}")


def addon_command(args) -> Dict[str, Any]:
    """Handle the features, tags and lyrics commands."""
    function_name, label = ADDON_FUNCTIONS_BY_COMMAND[args.addon]
    run = {"audio_features": audio_features, "tags": tags, "lyrics": lyrics_addon}[function_name]
    try:
        with _quiet_stdout(args.as_json):
            analysis_id = args.target
            looks_like_a_path = os.sep in args.target or '.' in os.path.basename(args.target)
            if looks_like_a_path and not os.path.isfile(args.target):
                raise AudialError(f"File not found: {args.target}")
            if os.path.isfile(args.target):
                analysed = segment(
                    file_path=args.target,
                    genre=args.genre,
                    results_folder=args.results_folder,
                    on_progress=warmup_reporter("segment", args),
                    api_key=args.api_key,
                )
                analysis_id = analysed["analysis_id"]
                print(f"Analysis ID: {analysis_id}")
            result = run(
                analysis_id,
                rerun=args.rerun,
                wait_s=args.wait_s,
                results_folder=args.results_folder,
                api_key=args.api_key,
                on_progress=warmup_reporter(function_name, args),
            )
        if args.as_json:
            print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
            return result

        print(f"\n{label} (analysis {analysis_id}):")
        {"features": _print_features, "tags": _print_tags, "lyrics": _print_lyrics}[args.addon](result)
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
            algorithm=args.algorithm,
            on_progress=warmup_reporter("stem_split", args),
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
            on_progress=warmup_reporter("generate_music", args),
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


def sound2vital_command(args) -> Dict[str, Any]:
    """Handle the sound2vital command."""
    try:
        result = sound2vital(
            file_path=args.file_path,
            results_folder=args.results_folder,
            api_key=args.api_key,
            on_progress=warmup_reporter("sound2vital", args),
        )

        print("\nsound2vital Results:")
        if "preset" in result:
            print(f"Preset: {result['preset']}")
        if "scores" in result and isinstance(result["scores"], dict):
            print(f"Scores: {result['scores']}")
        print(f"Files downloaded: {len(result['files']['files'])}")
        print(f"\nResults saved to: {result['files']['folder']}")

        return result

    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def sound2serum_command(args) -> Dict[str, Any]:
    """Handle the sound2serum command."""
    try:
        result = sound2serum(
            file_path=args.file_path,
            results_folder=args.results_folder,
            api_key=args.api_key,
            on_progress=warmup_reporter("sound2serum", args),
        )

        print("\nsound2serum Results:")
        if "preset" in result:
            print(f"Preset: {result['preset']}")
        if "scores" in result and isinstance(result["scores"], dict):
            print(f"Scores: {result['scores']}")
        print(f"Files downloaded: {len(result['files']['files'])}")
        print(f"\nResults saved to: {result['files']['folder']}")

        return result

    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def text2vox_command(args) -> Dict[str, Any]:
    """Handle the text2vox command."""
    try:
        result = text2vox(
            reference_file=args.reference_file,
            lyrics=args.lyrics,
            midi_file=args.midi_file,
            melody_audio_file=args.melody_audio_file,
            word_timestamps_file=args.word_timestamps_file,
            lyrics_mode=args.lyrics_mode,
            reference_text=args.reference_text,
            cfg_strength=args.cfg_strength,
            nfe_steps=args.nfe_steps,
            pitch_shift=args.pitch_shift,
            strict_pitch=args.strict_pitch,
            bend_smoothing_ms=args.bend_smoothing_ms,
            no_pitch_bends=args.no_pitch_bends,
            leading_silence_s=args.leading_silence_s,
            seed=args.seed,
            results_folder=args.results_folder,
            api_key=args.api_key,
            on_progress=warmup_reporter("text2vox", args),
        )

        print("\ntext2vox Results:")
        print(f"Files downloaded: {len(result['files']['files'])}")
        print(f"\nResults saved to: {result['files']['folder']}")

        return result

    except AudialError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


def pipeline_command(args) -> Dict[str, Any]:
    """Handle the pipeline command."""
    try:
        options = {
            "components": args.components,
            "genre": args.genre,
            "bpm": args.bpm,
            "keyString": args.key_string,
        }
        options = {k: v for k, v in options.items() if v is not None}

        tracker = pipelines.StepTracker()
        # A pipeline's steps run on the same workers as the functions they
        # wrap, so a pipeline waits on a cold start too; the warm-up phase
        # arrives on steps[].warmup and is reported the same way everywhere.
        reporter = None
        if not args.as_json:
            reporter = warmup.WarmupReporter(printer=lambda line: print(f"  {line}"))
            reporter.preflight(PIPELINE_FIRST_FUNCTION.get(args.name, PIPELINES[args.name][0]),
                               api_key=args.api_key)

        def on_progress(status):
            # Step progress, one line per change; suppressed under --json so the
            # only thing on stdout is the JSON document.
            if args.as_json:
                return
            for line in tracker.changes(status):
                print(f"  {line}")
            reporter(status)

        status = pipelines.run(
            args.name,
            args.file_path,
            options=options or None,
            wait=not args.no_wait,
            poll_interval=args.poll_interval,
            on_progress=on_progress,
            api_key=args.api_key,
        )

        if args.as_json:
            print(json.dumps(status, indent=2, default=str))
            return status

        print(f"\nPipeline {status.get('pipeline', args.name)}: {status.get('state')}")
        print(f"Pipeline ID: {status.get('pipelineId')}")
        for step in status.get("steps") or []:
            exe = f" (execution {step.get('exeId')})" if step.get("exeId") else ""
            print(f"  {step.get('name')}: {step.get('state')}{exe}")

        outputs = status.get("outputs") or {}
        stems = outputs.get("stems") or {}
        if stems:
            print(f"\nStems: {', '.join(sorted(stems))}")
        for key in ("samples", "segmentation"):
            urls = outputs.get(key) or []
            if urls:
                print(f"\n{key.capitalize()} ({len(urls)}):")
                for url in urls:
                    print(f"  {url}")
        if outputs.get("analysis"):
            print(f"\nAnalysis with every add-on: {outputs['analysis']}")
        for warning in outputs.get("warnings") or []:
            print(f"Warning: {warning}")

        return status

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
            try:
                current_user_id = get_user_id()
            except AudialError:
                current_user_id = None
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
        prog='audial',
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
    setup_sound2vital_parser(subparsers)
    setup_sound2serum_parser(subparsers)
    setup_text2vox_parser(subparsers)
    setup_segment_parser(subparsers)
    setup_addon_parsers(subparsers)
    setup_pipeline_parser(subparsers)
    setup_stem_split_parser(subparsers)
    setup_status_parser(subparsers)
    setup_config_parser(subparsers)
    setup_login_parsers(subparsers)
    
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