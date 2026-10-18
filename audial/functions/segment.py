"""
Audio segmentation implementation for Audial SDK.

Segmentation analyses separated stems, so this runs the `segmentation`
pipeline (stem-split -> segmentation) rather than orchestrating the two calls
here: one request uploads the file and the API runs both steps.
"""

from typing import Any, Callable, Dict, List, Optional
import json
import os
from urllib.parse import unquote

from audial import pipelines
from audial.api.constants import (
    DEFAULT_PIPELINE_POLL_INTERVAL,
    PIPELINE_SEGMENTATION,
)
from audial.api.exceptions import AudialError
from audial.utils.config import get_api_key, get_results_folder
from audial.utils.file_utils import download_file

VALID_GENRES = [
    "Default", "Afro House", "Tech House", "Bass House", "Blues", "Breakbeat",
    "Classic Rock", "Country", "Deep House", "Drum N Bass", "Dubstep", "Gospel",
    "Grime140", "House", "Indie", "Jazz", "Latin", "Metal", "Minimal House",
    "Pop", "R&B", "Rock", "Techno", "Trance", "Trap", "UK Garage"
]

VALID_FEATURES = [
    "mode", "energy", "loudness", "danceability", "tatum", "lyrics", "key", "tags"
]


def segment(
    file_path: str,
    components: Optional[List[str]] = None,
    analysis_type: Optional[str] = None,
    features: Optional[List[str]] = None,
    genre: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None,
    poll_interval: float = DEFAULT_PIPELINE_POLL_INTERVAL,
) -> Dict[str, Any]:
    """
    Segment an audio file into logical sections and analyze its components.

    Runs the `segmentation` pipeline: the track is split into stems, then the
    sections are detected and analysed from them. Tempo and key are detected
    automatically.

    Args:
        file_path (str): Path to the audio file.
        components (List[str], optional): Components to segment (default: ["bass", "beat", "melody", "vocal"]).
        analysis_type (str, optional): Type of analysis to perform (default: "select_features").
        features (List[str], optional): Features to extract (default: ["mode", "energy", "loudness", "danceability", "tatum", "lyrics", "tags"]).
        genre (str, optional): Genre of the track (default: "Default").
        results_folder (str, optional): Folder to save results. Uses default if None.
        api_key (str, optional): API key to use. Uses default if None.
        on_progress (callable, optional): Called with the PipelineStatus dict
            after every poll, for callers that report progress themselves.
        poll_interval (float, optional): Seconds between pipeline status polls.

    Returns:
        Dict[str, Any]: Segmentation results:
            execution: The final PipelineStatus (steps, outputs, timings).
            segmentation: The parsed `audio_segmentation` data.
            files: {folder, files} -- the downloaded segmentation file(s).

    Raises:
        AudialError: If segmentation fails.
    """
    # Set default values
    components = components or ["bass", "beat", "melody", "vocal"]
    analysis_type = analysis_type or "select_features"
    features = features or ["mode", "energy", "loudness", "danceability", "tatum", "lyrics", "tags"]
    genre = genre or "Default"

    if genre not in VALID_GENRES:
        raise AudialError(f"Invalid genre: {genre}. Must be one of: {', '.join(VALID_GENRES)}")

    for feature in features:
        if feature not in VALID_FEATURES:
            raise AudialError(
                f"Invalid feature: {feature}. Must be one of: {', '.join(VALID_FEATURES)}"
            )

    # Initialize configuration
    api_key = api_key or get_api_key()
    results_dir = results_folder or get_results_folder()
    os.makedirs(results_dir, exist_ok=True)

    if not os.path.isfile(file_path):
        raise AudialError(f"File not found: {file_path}")

    tracker = pipelines.StepTracker()

    def report(status: Dict[str, Any]) -> None:
        for line in tracker.changes(status):
            print(f"  {line}")
        if on_progress is not None:
            on_progress(status)

    try:
        print(f"Running the segmentation pipeline (stem split, then segmentation) on {file_path}")
        status = pipelines.run(
            PIPELINE_SEGMENTATION,
            file_path,
            # The pipeline's options are components/genre/bpm/keyString/
            # featuresToExtract; the segmentation step's analysisType is fixed
            # at "select_features" by the runner, so `analysis_type` is still
            # validated and accepted here but has nothing to override.
            options={
                "components": components,
                "genre": genre,
                "featuresToExtract": features,
            },
            poll_interval=poll_interval,
            on_progress=report,
            api_key=api_key,
        )
    except AudialError:
        raise
    except Exception as e:
        raise AudialError(f"Audio segmentation failed: {str(e)}")

    segmentation_urls = pipelines.outputs(status, "segmentation") or []
    segmentation_urls = [url for url in segmentation_urls if isinstance(url, str)]
    if not segmentation_urls:
        raise AudialError("Segmentation did not produce expected results")

    # The pruned analysis JSON is the file this function has always returned;
    # if the API names it differently, every segmentation output is kept.
    pruned = [url for url in segmentation_urls if _is_pruned_segmentation(url)]
    wanted = pruned or segmentation_urls

    original_filename = os.path.basename(file_path)
    result_folder = os.path.join(results_dir, f"{original_filename}_segmentation")
    os.makedirs(result_folder, exist_ok=True)

    downloaded_files: Dict[str, str] = {}
    segmentation_data = None

    for url in wanted:
        filename = _local_filename(url)
        local_path = os.path.join(result_folder, filename)
        try:
            print(f"Downloading Results: {filename}...")
            download_file(url, local_path)
            downloaded_files[filename] = local_path
        except Exception as e:
            print(f"Error downloading {filename}: {str(e)}")
            continue

        if segmentation_data is None and filename.lower().endswith(".json"):
            segmentation_data = _read_segmentation(local_path)

    return {
        "execution": status,
        "segmentation": segmentation_data,
        "files": {
            "folder": result_folder,
            "files": downloaded_files,
        },
    }


def _is_pruned_segmentation(url: str) -> bool:
    name = _local_filename(url).lower()
    return "pruned_" in name and "audio_segmentation" in name


def _read_segmentation(path: str) -> Optional[Any]:
    """Pull `audio_segmentation` out of a downloaded analysis JSON."""
    try:
        with open(path, "r") as f:
            content = json.load(f)
    except Exception as e:
        print(f"Error parsing segmentation data: {str(e)}")
        return None
    if isinstance(content, dict) and "audio_segmentation" in content:
        return content["audio_segmentation"]
    return None


def _local_filename(url: str) -> str:
    """A flat, safe filename for a result URL."""
    filename = os.path.basename(url.split("?")[0])
    if "%" in filename:
        filename = unquote(filename)
    return filename.replace("/", "_").replace("\\", "_") or "segmentation.json"
