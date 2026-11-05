"""
Sample pack generation implementation for Audial SDK.

From a file, this runs the `sample-pack` pipeline: the analysis and the stems
start together (`prepare`), then the pack is built from them (`sample-pack`),
from one request that uploads the file.

From an analysis (`analysis_id`), it runs the sample-pack add-on on that
analysis: the pack is built from the analysis's own stems and sections, with
no new analysis or stem split.
"""

from typing import Any, Callable, Dict, List, Optional
import os
from urllib.parse import unquote

from audial import pipelines
from audial.api.constants import (
    ADDON_DEFAULT_MAX_WAIT,
    ADDON_DEFAULT_WAIT_S,
    DEFAULT_PIPELINE_POLL_INTERVAL,
    PIPELINE_SAMPLE_PACK,
)
from audial.api.exceptions import AudialError
from audial.functions import _addon
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
    file_path: Optional[str] = None,
    job_type: Optional[str] = None,
    components: Optional[List[str]] = None,
    genre: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None,
    poll_interval: float = DEFAULT_PIPELINE_POLL_INTERVAL,
    analysis_id: Optional[str] = None,
    wait_s: float = ADDON_DEFAULT_WAIT_S,
    max_wait: float = ADDON_DEFAULT_MAX_WAIT,
) -> Dict[str, Any]:
    """
    Generate a sample pack: drums by type, bass and melody loops.

    Give either a file or an analysis:

    - ``file_path``: runs the ``sample-pack`` pipeline. The analysis and the
      stems start together (step ``prepare``), then the pack is built from
      them (step ``sample-pack``). Tempo and key are detected automatically.
      Counts as one run.
    - ``analysis_id``: builds the pack from that analysis's stems and
      sections, with no new analysis or stem split. Included with the
      analysis (free on an analysis of yours). The stems are made in the
      background as soon as an analysis starts; until they are ready the API
      answers ``409 STEMS_NOT_READY`` and this keeps trying for up to
      ``wait_s`` seconds.

    Args:
        file_path (str, optional): Path to the audio file.
        job_type (str, optional): Type of sample pack job to run (default: "sample_pack").
        components (List[str], optional): Components to include in the sample pack (default: ["drums", "bass", "melody"]).
        genre (str, optional): Genre of the track (default: "Default"). Not
            used with ``analysis_id`` (the analysis already has its sections).
        results_folder (str, optional): Folder to save results. Uses default if None.
        api_key (str, optional): API key to use. Uses default if None.
        on_progress (callable, optional): Called with the PipelineStatus dict
            after every poll (with ``analysis_id``: the sample-pack run's
            execution record), for callers that report progress themselves.
        poll_interval (float, optional): Seconds between status polls.
        analysis_id (str, optional): An analysis of yours (the
            ``analysis_id`` that ``audial.segment()`` returned), instead of
            ``file_path``.
        wait_s (float, optional): With ``analysis_id``: seconds to keep
            trying while the stems are being made (default 600).
        max_wait (float, optional): With ``analysis_id``: seconds to wait for
            the pack once it has started (default 900).

    Returns:
        Dict[str, Any]: Sample generation results:
            execution: The final PipelineStatus (steps, outputs, timings);
                with ``analysis_id``, the analysis record.
            files: {folder, files} -- the downloaded sample files.
            analysis_id: With ``analysis_id``, the analysis's id.
            components: With ``analysis_id``, what each part gave:
                {"drums": {"status": "ok" | "empty" | "failed" | "skipped", ...}, ...}.

    Raises:
        AudialError: If the input is invalid or sample generation fails.
        AudialAPIError: ``code == "STEMS_NOT_READY"`` or
            ``"ADDON_UNAVAILABLE"`` (with ``analysis_id``), or another API error.
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

    if (file_path is None) == (analysis_id is None):
        raise AudialError("generate_samples needs either file_path or analysis_id (not both)")

    # Initialize configuration
    api_key = api_key or get_api_key()
    results_dir = results_folder or get_results_folder()
    os.makedirs(results_dir, exist_ok=True)

    if analysis_id is not None:
        return _samples_from_analysis(
            analysis_id, components, results_dir, api_key, on_progress,
            poll_interval, wait_s, max_wait,
        )

    if not os.path.isfile(file_path):
        raise AudialError(f"File not found: {file_path}")

    tracker = pipelines.StepTracker()

    def report(status: Dict[str, Any]) -> None:
        for line in tracker.changes(status):
            print(f"  {line}")
        if on_progress is not None:
            on_progress(status)

    try:
        print(f"Running the sample-pack pipeline (analysis and stems, then the sample pack) on {file_path}")
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
    downloaded_files, download_folder = _download_samples(sample_urls, results_dir, folder_id)

    if not downloaded_files:
        print("No samples were returned by the sample-pack pipeline")

    return {
        "execution": status,
        "files": {
            "folder": download_folder,
            "files": downloaded_files,
        },
    }


def _samples_from_analysis(
    analysis_id: str,
    components: List[str],
    results_dir: str,
    api_key: Optional[str],
    on_progress: Optional[Callable[[Dict[str, Any]], Any]],
    poll_interval: float,
    wait_s: float,
    max_wait: float,
) -> Dict[str, Any]:
    """The sample-pack add-on on an analysis, then the downloads."""
    print(f"Making a sample pack from analysis {analysis_id}")
    analysis_exe_id, record, run = _addon.run_addon(
        "samplePack",
        analysis_id,
        extra={"samplePackParameters": {"components": components}},
        wait_s=wait_s,
        max_wait=max_wait,
        poll_interval=poll_interval,
        on_progress=on_progress,
        api_key=api_key,
    )
    sample_urls = extract_sample_urls({"sample": run.get("files") or {}})
    folder_id = run.get("exeId") or analysis_exe_id
    downloaded_files, download_folder = _download_samples(sample_urls, results_dir, folder_id)
    if not downloaded_files:
        print("No samples were returned for this analysis")

    report = run.get("result") if isinstance(run.get("result"), dict) else {}
    return {
        "execution": record,
        "analysis_id": analysis_exe_id,
        "components": report.get("components") if isinstance(report.get("components"), dict) else {},
        "files": {
            "folder": download_folder,
            "files": downloaded_files,
        },
    }


def _download_samples(sample_urls: List[str], results_dir: str, folder_id: str):
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
    return downloaded_files, download_folder


def _local_filename(url: str) -> str:
    """A flat, safe filename for a result URL."""
    filename = os.path.basename(url.split("?")[0])
    if "%" in filename:
        filename = unquote(filename)
    return filename.replace("/", "_").replace("\\", "_") or "sample"
