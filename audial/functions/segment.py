"""
Analysis: a track's sections, tempo and bars.

Analysis needs only the mix. Without ``features`` this is one call
(POST /functions/run/segmentation) that answers in about half a minute; audio
features, tags, lyrics and a sample pack are added afterwards, one call each
(``audial.audio_features``, ``audial.tags``, ``audial.lyrics``,
``audial.generate_samples(analysis_id=...)``).

With ``features`` it runs the ``segmentation`` pipeline as before: the API
runs the analysis, then the add-ons the features ask for, and the result
already holds them.

Either way the result is the merged view of the analysis
(GET /db/{userId}/execution/{exeId}/analysis) plus its ``analysis_id``.
"""

import json
import os
import re
import time
import warnings
from typing import Any, Callable, Dict, List, Optional, Tuple

from audial import grid
from audial import pipelines
from audial import warmup as warmup_module
from audial.api.constants import (
    ANALYSIS_DEFAULT_MAX_WAIT,
    ANALYSIS_DEFAULT_POLL_INTERVAL,
    DEFAULT_PIPELINE_POLL_INTERVAL,
    ERROR_ANALYSIS_NOT_READY,
    EXECUTION_STATE_COMPLETED,
    EXECUTION_STATE_FAILED,
    FEATURE_ADDONS,
    PIPELINE_SEGMENTATION,
)
from audial.api.exceptions import AudialAPIError, AudialError
from audial.api.proxy import AudialProxy
from audial.functions import _addon
from audial.utils.config import get_api_key, get_results_folder

VALID_GENRES = [
    "Default", "Afro House", "Tech House", "Bass House", "Blues", "Breakbeat",
    "Classic Rock", "Country", "Deep House", "Drum N Bass", "Dubstep", "Gospel",
    "Grime140", "House", "Indie", "Jazz", "Latin", "Metal", "Minimal House",
    "Pop", "R&B", "Rock", "Techno", "Trance", "Trap", "UK Garage"
]

VALID_FEATURES = [
    "mode", "energy", "loudness", "danceability", "tatum", "lyrics", "key", "tags"
]

EXECUTION_STATE_CANCELLED = "cancelled"
MAX_TRANSIENT_POLL_ERRORS = 8
VIEW_ATTEMPTS = 6

EXPANSION_NOTICE = (
    "audial.segment() added beat_times and bar_times, computed from the tempo map ('grid'). "
    "From Audial SDK 2.0 they are added only with expand_beats=True; audial.grid.beat_times() "
    "and audial.grid.bar_times() compute them from any result."
)

# Shown once per process (see _expand_beats).
_EXPANSION_NOTICE_SHOWN = False


def segment(
    file_path: str,
    genre: Optional[str] = None,
    edm: Optional[bool] = None,
    features: Optional[List[str]] = None,
    results_folder: Optional[str] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None,
    expand_beats: bool = True,
    *,
    api_key: Optional[str] = None,
    poll_interval: Optional[float] = None,
    max_wait: float = ANALYSIS_DEFAULT_MAX_WAIT,
    components: Optional[List[str]] = None,
    analysis_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyse a track: its sections, phrases and tempo map.

    Analysis finds your track's sections, tempo and bars in about half a
    minute. Send the mix: no stems are needed. Add audio features, tags,
    lyrics or a sample pack afterwards, one call each, with the
    ``analysis_id`` this returns (``audial.audio_features``, ``audial.tags``,
    ``audial.lyrics``, ``audial.generate_samples(analysis_id=...)``).

    Without ``features`` this is one fast call. With ``features`` it runs the
    ``segmentation`` pipeline, as in earlier versions: the API runs the
    analysis, then the add-ons those features need (audio features for mode,
    energy, loudness, danceability, tatum and key; tags; lyrics), and the
    result holds them. That takes longer, because tags and lyrics wait for the
    analysis's stems, which are made in the background.

    Beats and bars aren't listed one by one: ``grid`` describes them (where
    each constant-tempo piece starts, its BPM, and its bar and beat; every beat
    time is ``start + k * 60 / bpm``). With ``expand_beats=True``, the default
    in 1.6, ``beat_times`` and ``bar_times`` are added from it, so scripts
    written for older results keep working; a one-time FutureWarning says that
    2.0 makes this opt-in. See ``audial.grid``.

    Cost: an analysis counts as one run. Everything added to it (features,
    tags, lyrics, a sample pack) is included.

    Args:
        file_path (str): Path to the audio file (the full mix).
        genre (str, optional): Genre of the track, from the list in
            ``VALID_GENRES``. It decides between dance section names (INTRO,
            UP, CHORUS, DOWN, OUTRO) and song section names (INTRO, VERSE, UP,
            CHORUS, OUTRO) when ``edm`` is not given.
        edm (bool, optional): True for dance section names, False for song
            section names. Default: from the genre, else from the audio.
        features (List[str], optional): Add-ons to run with the analysis, as
            1.5 named them: "mode", "energy", "loudness", "danceability",
            "tatum", "key" (audio features), "tags", "lyrics". Default: none
            (the fast analysis).
        results_folder (str, optional): Folder to save the result in, as
            ``<file name>_segmentation/analysis.json``. Uses default if None.
        on_progress (callable, optional): Called with the analysis execution
            after every status check (with ``features``: the pipeline status).
            It carries ``warmup`` while a machine starts; see audial.warmup.
        expand_beats (bool, optional): Add ``beat_times`` and ``bar_times``
            computed from ``grid`` (default True).
        api_key (str, optional): API key to use. Uses default if None.
        poll_interval (float, optional): Seconds between status checks
            (default 3; 5 for the pipeline).
        max_wait (float, optional): Seconds to wait for the analysis (default
            900). The first request after a quiet period also waits for a
            machine to start.
        components: No longer used (deprecated; accepted and ignored).
        analysis_type: No longer used (deprecated; accepted and ignored).

    Returns:
        Dict[str, Any]:
            analysis_id: The analysis's id, for the add-ons.
            audio_segmentation: The merged view of the analysis:
                ``format_version`` (4), ``duration``, ``bpm``, ``tempo_mode``,
                ``time_signature``, ``grid``, ``sections`` (label, start, end,
                start_bar, bars, ...), ``phrases``, ``lead_in``, ``bar1``,
                ``song_start``, ``mood``, ``mode``, ``song_analysis`` (what the
                add-ons have filled so far; ``{}`` before any),
                ``segment_analysis`` (one object per section),
                ``first_vocal_beat_time`` once lyrics exist, and, with
                ``expand_beats``, ``beat_times`` and ``bar_times``. An analysis
                from before the tempo map has its own ``beat_times`` and
                ``bar_times`` instead of ``grid``.
            segmentation: The same object (the 1.5 name).
            execution: The analysis execution (with ``features``: the final
                pipeline status).
            files: {folder, files} -- the saved ``analysis.json``.
            warnings: With ``features``, the add-ons that could not be made
                (present only when there are some).

    Raises:
        AudialError: Invalid input, a missing file, or a failed analysis.
        SubscriptionRequiredError: The free allowance is used up and the
            account has no subscription (HTTP 402).
        AudialAPIError: Any other API error.
    """
    if isinstance(genre, (list, tuple)):
        raise AudialError(
            "segment(): since 1.6 the second argument is the genre. components is no longer "
            "used; pass any other options by name, e.g. segment(path, genre='House')."
        )
    if components is not None or analysis_type is not None:
        warnings.warn(
            "segment(): components and analysis_type are no longer used (analysis needs only "
            "the mix) and will be removed in 2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
    if genre is not None and genre not in VALID_GENRES:
        raise AudialError(f"Invalid genre: {genre}. Must be one of: {', '.join(VALID_GENRES)}")
    if edm is not None and not isinstance(edm, bool):
        raise AudialError("edm must be True, False or None")
    features = list(features or [])
    for feature in features:
        if feature not in VALID_FEATURES:
            raise AudialError(
                f"Invalid feature: {feature}. Must be one of: {', '.join(VALID_FEATURES)}"
            )
    if not os.path.isfile(file_path):
        raise AudialError(f"File not found: {file_path}")

    api_key = api_key or get_api_key()
    results_dir = results_folder or get_results_folder()
    os.makedirs(results_dir, exist_ok=True)
    proxy = AudialProxy(api_key)

    addon_warnings: List[str] = []
    if features and edm is None:
        execution, analysis_id = _run_pipeline(
            file_path, genre, features, on_progress,
            poll_interval if poll_interval is not None else DEFAULT_PIPELINE_POLL_INTERVAL, api_key,
        )
        addon_warnings = [w for w in (pipelines.outputs(execution, "warnings") or []) if isinstance(w, str)]
    else:
        interval = poll_interval if poll_interval is not None else ANALYSIS_DEFAULT_POLL_INTERVAL
        execution, analysis_id = _run_analysis(proxy, file_path, genre, edm, on_progress, interval, max_wait)
        if features:
            # The pipeline has no edm option, so with edm the add-ons are started here.
            addon_warnings = _run_addons(analysis_id, features, interval, api_key)
            execution = proxy.get_execution(analysis_id)

    view = _fetch_view(proxy, analysis_id, poll_interval or ANALYSIS_DEFAULT_POLL_INTERVAL)
    data = view.get("audio_segmentation") if isinstance(view.get("audio_segmentation"), dict) else {}
    if expand_beats:
        _expand_beats(data)

    folder = os.path.join(results_dir, f"{os.path.basename(file_path)}_segmentation")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "analysis.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"audio_segmentation": data}, f, indent=2, ensure_ascii=False)

    sections = data.get("sections") if isinstance(data.get("sections"), list) else []
    print(f"Analysis {analysis_id}: {len(sections)} sections"
          f"{', ' + str(data['bpm']) + ' BPM' if data.get('bpm') else ''}. Saved to {path}")

    result: Dict[str, Any] = {
        "analysis_id": analysis_id,
        "audio_segmentation": data,
        "segmentation": data,
        "execution": execution,
        "files": {"folder": folder, "files": {"analysis.json": path}},
    }
    if addon_warnings:
        result["warnings"] = addon_warnings
    return result


# ---------------------------------------------------------------------------
# The fast analysis
# ---------------------------------------------------------------------------

def _run_analysis(
    proxy: AudialProxy,
    file_path: str,
    genre: Optional[str],
    edm: Optional[bool],
    on_progress: Optional[Callable[[Dict[str, Any]], Any]],
    poll_interval: float,
    max_wait: float,
) -> Tuple[Dict[str, Any], str]:
    """POST /functions/run/segmentation with the mix, then wait for the analysis."""
    parameters: Dict[str, Any] = {}
    if genre is not None:
        parameters["genre"] = genre
    if edm is not None:
        parameters["edm"] = edm

    print(f"Analysing {file_path}…")
    try:
        execution = proxy.run_analysis(file_path, parameters or None)
    except FileNotFoundError as e:
        raise AudialError(str(e))
    exe_id = execution.get("exeId") if isinstance(execution, dict) else None
    if not exe_id:
        raise AudialAPIError("No analysis id was returned when starting the analysis")
    warmup_module.notify(on_progress, execution)

    deadline = time.monotonic() + max(0.0, float(max_wait))
    errors = 0
    while execution.get("state") not in (
        EXECUTION_STATE_COMPLETED, EXECUTION_STATE_FAILED, EXECUTION_STATE_CANCELLED
    ):
        if time.monotonic() >= deadline:
            raise AudialAPIError(
                f"The analysis {exe_id} is still running after {int(max_wait)} s. It keeps going; "
                "it is listed in your history at audialmusic.ai."
            )
        time.sleep(poll_interval)
        try:
            candidate = proxy.get_execution(exe_id)
        except AudialAPIError:
            errors += 1
            if errors > MAX_TRANSIENT_POLL_ERRORS:
                raise
            continue
        errors = 0
        if isinstance(candidate, dict):
            execution = candidate
            warmup_module.notify(on_progress, execution)

    state = execution.get("state")
    if state == EXECUTION_STATE_FAILED:
        raise AudialAPIError(f"Analysis failed: {_error_text(execution)}")
    if state == EXECUTION_STATE_CANCELLED:
        raise AudialAPIError("Analysis was cancelled")
    return execution, exe_id


def _error_text(execution: Dict[str, Any]) -> str:
    error = execution.get("error")
    if isinstance(error, dict):
        error = error.get("message") or error.get("error") or error.get("code")
    return error if isinstance(error, str) and error else "unknown error"


def _fetch_view(proxy: AudialProxy, exe_id: str, poll_interval: float) -> Dict[str, Any]:
    """The merged view, retried briefly while it is not readable yet (409/502/5xx)."""
    attempt = 0
    while True:
        attempt += 1
        try:
            view = proxy.get_analysis_view(exe_id)
            return view if isinstance(view, dict) else {}
        except AudialAPIError as exc:
            retry = (
                exc.code == ERROR_ANALYSIS_NOT_READY
                or exc.status_code is None
                or (isinstance(exc.status_code, int) and exc.status_code >= 500)
            )
            if not retry or attempt >= VIEW_ATTEMPTS:
                raise
        time.sleep(poll_interval)


# ---------------------------------------------------------------------------
# With features: the segmentation pipeline (or the add-ons, with edm)
# ---------------------------------------------------------------------------

def _api_features(features: List[str]) -> List[str]:
    """featuresToExtract as the API takes it: "key" comes with the audio features."""
    wanted: List[str] = []
    for feature in features:
        if feature != "key" and feature not in wanted:
            wanted.append(feature)
    if "key" in features and not any(FEATURE_ADDONS[f] == "features" for f in wanted):
        wanted.append("mode")
    return wanted


def _run_pipeline(
    file_path: str,
    genre: Optional[str],
    features: List[str],
    on_progress: Optional[Callable[[Dict[str, Any]], Any]],
    poll_interval: float,
    api_key: Optional[str],
) -> Tuple[Dict[str, Any], str]:
    tracker = pipelines.StepTracker()

    def report(status: Dict[str, Any]) -> None:
        for line in tracker.changes(status):
            print(f"  {line}")
        if on_progress is not None:
            on_progress(status)

    options: Dict[str, Any] = {"featuresToExtract": _api_features(features)}
    if genre is not None:
        options["genre"] = genre

    try:
        print(f"Running the segmentation pipeline (the analysis, then {', '.join(options['featuresToExtract'])}) "
              f"on {file_path}")
        status = pipelines.run(
            PIPELINE_SEGMENTATION,
            file_path,
            options=options,
            poll_interval=poll_interval,
            on_progress=report,
            api_key=api_key,
        )
    except AudialError:
        raise
    except Exception as e:
        raise AudialError(f"Audio segmentation failed: {str(e)}")

    analysis_id = _analysis_id_of(status)
    if not analysis_id:
        raise AudialError("Segmentation did not produce expected results")
    return status, analysis_id


def _analysis_id_of(status: Dict[str, Any]) -> Optional[str]:
    """The analysis execution of a segmentation pipeline: its `segmentation` step."""
    step = pipelines.step(status, "segmentation") or {}
    if isinstance(step.get("exeId"), str) and step["exeId"]:
        return step["exeId"]
    url = pipelines.outputs(status, "analysis")
    if isinstance(url, str):
        match = re.search(r"/execution/([^/?#]+)/analysis", url)
        if match:
            return match.group(1)
    return None


def _run_addons(analysis_id: str, features: List[str], poll_interval: float,
                api_key: Optional[str]) -> List[str]:
    """The add-ons `features` asks for, one after the other; failures become warnings."""
    keys: List[str] = []
    for feature in features:
        key = FEATURE_ADDONS[feature]
        if key not in keys:
            keys.append(key)
    problems: List[str] = []
    for key in keys:
        try:
            _addon.run_addon(key, analysis_id, poll_interval=poll_interval, api_key=api_key)
        except AudialAPIError as exc:
            problems.append(f"{_addon.LABELS[key]} could not be made: {exc}")
    return problems


# ---------------------------------------------------------------------------
# beat_times / bar_times from the tempo map
# ---------------------------------------------------------------------------

def _expand_beats(data: Dict[str, Any]) -> None:
    """Add beat_times and bar_times from `grid` (format 4); older files have their own."""
    global _EXPANSION_NOTICE_SHOWN
    if not isinstance(data.get("grid"), dict) or "beat_times" in data:
        return
    data["beat_times"], data["bar_times"] = grid.beats_of(data)
    if not _EXPANSION_NOTICE_SHOWN:
        _EXPANSION_NOTICE_SHOWN = True
        warnings.warn(EXPANSION_NOTICE, FutureWarning, stacklevel=3)
