"""
Sample pack generation implementation for Audial SDK.

A sample pack is built from separated stems, so this runs the `sample-pack`
pipeline (stem-split -> sample-pack) rather than orchestrating the two calls
here: one request uploads the file and the API runs both steps.
"""

from typing import Any, Callable, Dict, List, Optional
import os
from urllib.parse import unquote

from audial import pipelines
from audial.api.constants import (
    DEFAULT_PIPELINE_POLL_INTERVAL,
    PIPELINE_SAMPLE_PACK,
)
from audial.api.exceptions import AudialError
from audial.utils.config import get_api_key, get_results_folder
from audial.utils.file_utils import download_file

VALID_JOB_TYPES = ["sample_pack"]
VALID_COMPONENTS = ["drums", "bass", "melody"]
VALID_GENRES = [
    "Default", "Afro House", "Tech House", "Bass House", "Blues", "Breakbeat",
    "Classic Rock", "Country", "Deep House", "Drum N Bass", "Dubstep", "Gospel",
    "Grime140", "House", "Indie", "Jazz", "Latin", "Metal", "Minimal House",
    "Pop", "R&B", "Rock", "Techno", "Trance", "Trap", "UK Garage"
]


def extract_sample_urls(status: Dict[str, Any]) -> List[str]:
    """
    Extract sample URLs from a pipeline status (or a sample-pack execution).

    A pipeline reports its results as `outputs.samples` (a list of URLs); the
    older per-execution shapes (`sample` maps, `sample_urls`) are still read so
    an execution record passed in here keeps working.

    Args:
        status (Dict[str, Any]): PipelineStatus or execution record.

    Returns:
        List[str]: The sample URLs found, in a stable order.
    """
    result_urls: List[str] = []

    outputs = status.get("outputs")
    if isinstance(outputs, dict):
        samples = outputs.get("samples")
        if isinstance(samples, list):
            result_urls.extend(url for url in samples if isinstance(url, str))

    # Flat and nested `sample` maps from an execution record.
    if isinstance(status.get("sample"), dict):
        for item in status["sample"].values():
            if isinstance(item, dict):
                if isinstance(item.get("url"), str):
                    result_urls.append(item["url"])
                else:
                    for file_data in item.values():
                        if isinstance(file_data, dict) and isinstance(file_data.get("url"), str):
                            result_urls.append(file_data["url"])

    if isinstance(status.get("sample_urls"), list):
        result_urls.extend(url for url in status["sample_urls"] if isinstance(url, str))

    # Deduplicate while keeping the order the URLs were reported in.
    seen = set()
    unique: List[str] = []
    for url in result_urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def generate_samples(
    file_path: str,
    job_type: Optional[str] = None,
    components: Optional[List[str]] = None,
    genre: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None,
    poll_interval: float = DEFAULT_PIPELINE_POLL_INTERVAL,
) -> Dict[str, Any]:
    """
    Generate a sample pack from an audio file.

    Runs the `sample-pack` pipeline: the track is split into stems, then the
    sample pack is built from them. Tempo and key are detected automatically.

    Args:
        file_path (str): Path to the audio file.
        job_type (str, optional): Type of sample pack job to run (default: "sample_pack").
        components (List[str], optional): Components to include in the sample pack (default: ["drums", "bass", "melody"]).
        genre (str, optional): Genre of the track (default: "Default").
        results_folder (str, optional): Folder to save results. Uses default if None.
        api_key (str, optional): API key to use. Uses default if None.
        on_progress (callable, optional): Called with the PipelineStatus dict
            after every poll, for callers that report progress themselves.
        poll_interval (float, optional): Seconds between pipeline status polls.

    Returns:
        Dict[str, Any]: Sample generation results:
            execution: The final PipelineStatus (steps, outputs, timings).
            files: {folder, files} -- the downloaded sample files.

    Raises:
        AudialError: If sample generation fails.
    """
    # Set default values
    job_type = job_type or "sample_pack"
    components = components or ["drums", "bass", "melody"]
    genre = genre or "Default"

    if job_type not in VALID_JOB_TYPES:
        raise AudialError(
            f"Invalid job type: {job_type}. Must be one of: {', '.join(VALID_JOB_TYPES)}"
        )

    for component in components:
        if component not in VALID_COMPONENTS:
            raise AudialError(
                f"Invalid component: {component}. Must be one of: {', '.join(VALID_COMPONENTS)}"
            )

    if genre not in VALID_GENRES:
        raise AudialError(f"Invalid genre: {genre}. Must be one of: {', '.join(VALID_GENRES)}")

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
        print(f"Running the sample-pack pipeline (stem split, then sample pack) on {file_path}")
        status = pipelines.run(
            PIPELINE_SAMPLE_PACK,
            file_path,
            options={"components": components, "genre": genre},
            poll_interval=poll_interval,
            on_progress=report,
            api_key=api_key,
        )
    except AudialError:
        raise
    except Exception as e:
        raise AudialError(f"Sample pack generation failed: {str(e)}")

    sample_urls = extract_sample_urls(status)

    # The folder is named after the sample-pack step's execution, so results
    # land where they always did for a given execution id.
    sample_step = pipelines.step(status, PIPELINE_SAMPLE_PACK) or {}
    folder_id = sample_step.get("exeId") or status.get("pipelineId") or "pipeline"
    download_folder = os.path.join(results_dir, f"{folder_id}_samples")
    os.makedirs(download_folder, exist_ok=True)

    downloaded_files: Dict[str, str] = {}
    for url in sample_urls:
        filename = _local_filename(url)
        local_path = os.path.join(download_folder, filename)
        if os.path.exists(local_path):
            downloaded_files[filename] = local_path
            continue
        try:
            print(f"Downloading sample file: {filename}")
            download_file(url, local_path)
            downloaded_files[filename] = local_path
        except Exception as e:
            print(f"Error downloading sample file {filename}: {str(e)}")

    if not downloaded_files:
        print("No samples were returned by the sample-pack pipeline")

    return {
        "execution": status,
        "files": {
            "folder": download_folder,
            "files": downloaded_files,
        },
    }


def _local_filename(url: str) -> str:
    """A flat, safe filename for a result URL."""
    filename = os.path.basename(url.split("?")[0])
    if "%" in filename:
        filename = unquote(filename)
    return filename.replace("/", "_").replace("\\", "_") or "sample"
