"""
Running one add-on on an analysis: start it, wait while the track is being
prepared, wait for the run, and hand back its result.

Shared by audial.audio_features, audial.tags, audial.lyrics and
audial.generate_samples(analysis_id=...). The API side:

    POST /functions/run/{audio-features|audio-tags|lyrics|sample-pack}
         {userId, analysisExeId, rerun?}      -> {exeId, analysisExeId, addon, state}
    409 STEMS_NOT_READY {state}               the track is still being prepared
    409 ADDON_UNAVAILABLE {state?}            the analysis hasn't finished, or kept no stems
    GET /db/{userId}/execution/{analysisExeId} -> addons.<key>: {state, exeId, result?, files?, error?}
    GET /db/{userId}/execution/{analysisExeId}/analysis -> the merged view (format 5)

Starting is idempotent (a repeated call answers the run that exists), so a
retry never starts a second run.

What audio_features, tags and lyrics return is read from the merged view, the
same format 5 object the API and the website show: each add-on's block of it
(see features_block, tags_block and lyrics_block), plus the run's warnings.
"""

import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from audial import warmup as warmup_module
from audial.api.constants import (
    ADDON_DEFAULT_MAX_WAIT,
    ADDON_DEFAULT_POLL_INTERVAL,
    ADDON_DEFAULT_WAIT_S,
    ADDON_FUNCTIONS,
    ADDON_STATE_CANCELLED,
    ADDON_STATE_COMPLETED,
    ADDON_STATE_FAILED,
    ADDON_UNAVAILABLE_TEXT,
    ANALYSIS_IN_FLIGHT_STATES,
    ERROR_ADDON_UNAVAILABLE,
    ERROR_ANALYSIS_NOT_READY,
    ERROR_STEMS_NOT_READY,
    PREPARING_TEXT,
    STEMS_FAILED_TEXT,
    STEMS_NOT_READY_TEXT,
)
from audial.api.exceptions import AudialAPIError, AudialError
from audial.api.proxy import AudialProxy
from audial.utils.config import get_results_folder

ProgressCallback = Callable[[Dict[str, Any]], Any]

LABELS = {
    "features": "Audio features",
    "tags": "Tags",
    "lyrics": "Lyrics",
    "samplePack": "The sample pack",
}

RUNNING_TEXT = {
    "features": "Getting audio features…",
    "tags": "Getting tags…",
    "lyrics": "Getting lyrics…",
    "samplePack": "Making the sample pack…",
}

RESULT_FILES = {"features": "features.json", "tags": "tags.json", "lyrics": "lyrics.json"}

MAX_TRANSIENT_ERRORS = 8


def check_analysis_id(analysis_id: Any) -> str:
    """The analysis id as a non-empty string, or AudialError."""
    if not isinstance(analysis_id, str) or not analysis_id.strip():
        raise AudialError(
            "An analysis id is needed: the analysis_id that audial.segment() returned "
            "(or an analysis's id from your history)."
        )
    return analysis_id.strip()


def run_addon(
    key: str,
    analysis_id: str,
    rerun: bool = False,
    extra: Optional[Dict[str, Any]] = None,
    wait_s: float = ADDON_DEFAULT_WAIT_S,
    max_wait: float = ADDON_DEFAULT_MAX_WAIT,
    poll_interval: float = ADDON_DEFAULT_POLL_INTERVAL,
    on_progress: Optional[ProgressCallback] = None,
    api_key: Optional[str] = None,
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """
    Start add-on `key` on an analysis and wait until it has finished.

    Returns:
        (analysis exeId, the analysis record, its `addons.<key>` entry), once
        that entry is completed. The exeId is the analysis's own, also when a
        pipeline id was passed in.

    Raises:
        AudialAPIError: code STEMS_NOT_READY when the track is still not
            prepared after `wait_s` (or could not be prepared), code
            ADDON_UNAVAILABLE when the add-on can't run on this analysis, or
            the add-on failed or ran past `max_wait`.
    """
    analysis_id = check_analysis_id(analysis_id)
    proxy = AudialProxy(api_key)
    answer = _start(proxy, key, analysis_id, rerun, extra, wait_s, poll_interval)
    analysis_exe_id = answer.get("analysisExeId") or analysis_id
    record, run = _wait(proxy, key, analysis_exe_id, answer, max_wait, poll_interval, on_progress)
    return analysis_exe_id, record, run


def _body(exc: AudialAPIError) -> Dict[str, Any]:
    response = getattr(exc, "response", None)
    if response is None:
        return {}
    try:
        body = response.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


def _is_transient(exc: AudialAPIError) -> bool:
    """429, any 5xx, or a transport error (no status code) is worth retrying."""
    code = getattr(exc, "status_code", None)
    return code is None or code == 429 or (isinstance(code, int) and code >= 500)


def _start(
    proxy: AudialProxy,
    key: str,
    analysis_id: str,
    rerun: bool,
    extra: Optional[Dict[str, Any]],
    wait_s: float,
    poll_interval: float,
) -> Dict[str, Any]:
    """POST the add-on run, retrying while the track is being prepared."""
    function = ADDON_FUNCTIONS[key]
    deadline = time.monotonic() + max(0.0, float(wait_s))
    restarted_stems = False
    announced = False
    transient = 0

    while True:
        try:
            answer = proxy.run_addon(function, analysis_id, rerun=rerun, extra=extra)
            print(RUNNING_TEXT[key])
            return answer if isinstance(answer, dict) else {}
        except AudialAPIError as exc:
            body = _body(exc)
            state = body.get("state")
            pause = poll_interval
            retry_after = 0

            if exc.status_code == 409 and exc.code == ERROR_STEMS_NOT_READY:
                give_up = AudialAPIError(
                    f"{STEMS_NOT_READY_TEXT} ({ERROR_STEMS_NOT_READY})",
                    status_code=409, response=exc.response, code=ERROR_STEMS_NOT_READY,
                )
                if state in (ADDON_STATE_FAILED, ADDON_STATE_CANCELLED):
                    if restarted_stems:
                        detail = body.get("error")
                        raise AudialAPIError(
                            f"{STEMS_FAILED_TEXT} Try again later, or contact support "
                            f"if it keeps happening. ({ERROR_STEMS_NOT_READY}"
                            f"{', ' + detail if detail and detail != STEMS_FAILED_TEXT else ''})",
                            status_code=409, response=exc.response, code=ERROR_STEMS_NOT_READY,
                        )
                    # Preparing the track failed once: start it again (free), then wait.
                    proxy.retry_stems(analysis_id)
                    restarted_stems = True
                if not announced:
                    print(PREPARING_TEXT)
                    announced = True
            elif exc.status_code == 409 and exc.code == ERROR_ADDON_UNAVAILABLE:
                if state not in ANALYSIS_IN_FLIGHT_STATES:
                    detail = body.get("error")
                    raise AudialAPIError(
                        f"{ADDON_UNAVAILABLE_TEXT}{' ' + detail if detail else ''} ({ERROR_ADDON_UNAVAILABLE})",
                        status_code=409, response=exc.response, code=ERROR_ADDON_UNAVAILABLE,
                    )
                # The analysis itself is still running: wait for it.
                give_up = AudialAPIError(
                    f"The analysis hasn't finished yet. Try again in a minute. ({ERROR_ADDON_UNAVAILABLE})",
                    status_code=409, response=exc.response, code=ERROR_ADDON_UNAVAILABLE,
                )
            elif _is_transient(exc):
                transient += 1
                if transient > MAX_TRANSIENT_ERRORS:
                    raise
                pause = min(poll_interval * transient, 60)
                if exc.retry_after:
                    # The API said how long to wait: wait at least that long.
                    pause = max(pause, exc.retry_after)
                    retry_after = exc.retry_after
                give_up = exc
            else:
                raise

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise give_up
        time.sleep(max(min(pause, remaining), retry_after))


def _wait(
    proxy: AudialProxy,
    key: str,
    analysis_exe_id: str,
    answer: Dict[str, Any],
    max_wait: float,
    poll_interval: float,
    on_progress: Optional[ProgressCallback],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Poll the analysis record until `addons.<key>` has finished."""
    label = LABELS[key]
    child_id = answer.get("exeId")
    deadline = time.monotonic() + max(0.0, float(max_wait))
    errors = 0

    while True:
        record: Optional[Dict[str, Any]] = None
        try:
            record = proxy.get_execution(analysis_exe_id)
            errors = 0
        except AudialAPIError:
            errors += 1
            if errors > MAX_TRANSIENT_ERRORS:
                raise

        if isinstance(record, dict):
            addons = record.get("addons") if isinstance(record.get("addons"), dict) else {}
            run = addons.get(key) if isinstance(addons.get(key), dict) else {}
            # Follow the run the record names (a later Try again replaces ours).
            if isinstance(run.get("exeId"), str) and run["exeId"]:
                child_id = run["exeId"]
            state = run.get("state")
            if state == ADDON_STATE_COMPLETED:
                return record, run
            if state in (ADDON_STATE_FAILED, ADDON_STATE_CANCELLED):
                verb = "was cancelled" if state == ADDON_STATE_CANCELLED else "failed"
                error = run.get("error")
                raise AudialAPIError(f"{label} {verb}{': ' + error if error else ''}")
            if child_id:
                _report(proxy, child_id, on_progress)

        if time.monotonic() >= deadline:
            raise AudialAPIError(
                f"{label} is still running after {int(max_wait)} s. It keeps going: call this "
                "again later to collect the result (it won't start a second run)."
            )
        time.sleep(poll_interval)


def _report(proxy: AudialProxy, child_id: str, on_progress: Optional[ProgressCallback]) -> None:
    """Hand the run's own execution (it carries `warmup`) to the progress callback."""
    if on_progress is None:
        return
    try:
        child = proxy.get_execution(child_id)
    except Exception:
        return
    if isinstance(child, dict):
        warmup_module.notify(on_progress, child)



# ---------------------------------------------------------------------------
# The merged view (format 5), and the blocks the add-ons fill in it
# ---------------------------------------------------------------------------

VIEW_ATTEMPTS = 6


def fetch_view(proxy: AudialProxy, exe_id: str, poll_interval: float) -> Dict[str, Any]:
    """
    The merged view of an analysis (GET /db/{userId}/execution/{exeId}/analysis),
    as the format 5 object; retried briefly while it is not readable yet
    (409 ANALYSIS_NOT_READY, 5xx, or no answer).
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return view_object(proxy.get_analysis_view(exe_id))
        except AudialAPIError as exc:
            retry = (
                exc.code == ERROR_ANALYSIS_NOT_READY
                or exc.status_code is None
                or (isinstance(exc.status_code, int) and exc.status_code >= 500)
            )
            if not retry or attempt >= VIEW_ATTEMPTS:
                raise
        time.sleep(poll_interval)


def view_object(view: Any) -> Dict[str, Any]:
    """
    The analysis object of a merged view. The API serves format 5 with no
    wrapper; an ``{"audio_segmentation": ...}`` wrapper (an API from before
    format 5) is taken off, and nothing else is changed.
    """
    if not isinstance(view, dict):
        return {}
    if isinstance(view.get("audio_segmentation"), dict):
        return view["audio_segmentation"]
    return view


def listify(value: Any) -> List[Any]:
    """A list as stored: lists stay lists; {"0": a, "1": b} (a sparse list) becomes [a, b]."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and value and all(str(k).isdigit() for k in value):
        return [value[k] for k in sorted(value, key=lambda k: int(k))]
    return []


def _strings(value: Any) -> List[str]:
    return [item for item in listify(value) if isinstance(item, str)]


def _number(value: Any) -> Optional[float]:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


# The per-section numbers Audio Features adds to each section of the view.
SECTION_FEATURES = ("energy", "danceability", "loudness_lufs")

# Stem parts in the order the website shows them; any other part follows.
STEM_PARTS = ("drums", "bass", "melody", "vocals")


def features_block(view: Dict[str, Any]) -> Dict[str, Any]:
    """
    What Audio Features fills in the view::

        {"key": "Bmin", "camelot": "10A",
         "features": {"energy", "danceability", "loudness_lufs", "mode", "mode_confidence", "tatum"},
         "sections": [{"label", "start", "end", "energy", "danceability", "loudness_lufs"}, ...]}

    ``key`` and ``camelot`` are the view's top-level ones. A number that was
    not measured is None.
    """
    features = view.get("features") if isinstance(view.get("features"), dict) else {}
    sections = []
    for section in listify(view.get("sections")):
        if not isinstance(section, dict):
            continue
        row: Dict[str, Any] = {
            "label": section.get("label"),
            "start": _number(section.get("start")),
            "end": _number(section.get("end")),
        }
        for name in SECTION_FEATURES:
            row[name] = _number(section.get(name))
        sections.append(row)
    return {
        "key": view.get("key") if isinstance(view.get("key"), str) else None,
        "camelot": view.get("camelot") if isinstance(view.get("camelot"), str) else None,
        "features": dict(features),
        "sections": sections,
    }


def _stem_part(part: Any) -> Dict[str, Any]:
    if isinstance(part, dict) and part.get("silent") is True:
        return {"silent": True}
    part = part if isinstance(part, dict) else {}
    return {"instruments": _strings(part.get("instruments")), "moods": _strings(part.get("moods"))}


def tags_block(view: Dict[str, Any]) -> Dict[str, Any]:
    """
    What Tags fills in the view: its ``tags`` block and ``description``::

        {"genres": [...], "instruments": [...], "moods": [...],
         "stems": {"drums": {"instruments": [...], "moods": [...]}, ..., "vocals": {"silent": True}},
         "description": "..."}

    A stem part is ``{"instruments", "moods"}``, or ``{"silent": True}`` when
    that part of the track is silent. Parts the view does not have stay absent
    (older tags have ``bass`` and ``melody`` only). Lists are always lists.
    """
    tags = view.get("tags") if isinstance(view.get("tags"), dict) else {}
    stems_in = tags.get("stems") if isinstance(tags.get("stems"), dict) else {}
    order = [p for p in STEM_PARTS if p in stems_in] + [p for p in stems_in if p not in STEM_PARTS]
    description = view.get("description")
    return {
        "genres": _strings(tags.get("genres")),
        "instruments": _strings(tags.get("instruments")),
        "moods": _strings(tags.get("moods")),
        "stems": {part: _stem_part(stems_in[part]) for part in order},
        "description": description if isinstance(description, str) else "",
    }


def _word(word: Any) -> List[Any]:
    entry = listify(word)
    if not entry or not isinstance(entry[0], str):
        return []
    text = entry[0]
    start = _number(entry[1]) if len(entry) > 1 else None
    end = _number(entry[2]) if len(entry) > 2 else None
    return [text, start, end]


def lyrics_block(view: Dict[str, Any]) -> Dict[str, Any]:
    """
    What Lyrics fills in the view: its ``lyrics`` block::

        {"vocal_start": 12.34,
         "lines": [{"start": 12.34, "end": 13.1, "words": [["hello", 12.34, 12.71], ...]}, ...]}

    Without vocals: ``{"vocal_start": None, "lines": []}``. Words are
    ``[word, start, end]``; a time that is not known is None.
    """
    lyrics = view.get("lyrics") if isinstance(view.get("lyrics"), dict) else {}
    lines = []
    for line in listify(lyrics.get("lines")):
        if not isinstance(line, dict):
            continue
        words = [w for w in (_word(word) for word in listify(line.get("words"))) if w]
        lines.append(dict(line, start=_number(line.get("start")), end=_number(line.get("end")), words=words))
    return {"vocal_start": _number(lyrics.get("vocal_start")), "lines": lines}


BLOCKS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "features": features_block,
    "tags": tags_block,
    "lyrics": lyrics_block,
}


def run_warnings(run: Dict[str, Any]) -> List[str]:
    """The warnings the add-on's run left on the analysis record (``[]`` when none)."""
    stored = run.get("result") if isinstance(run.get("result"), dict) else {}
    return _strings(stored.get("warnings"))


def save_result(key: str, analysis_exe_id: str, result: Dict[str, Any],
                results_folder: Optional[str] = None) -> str:
    """Write an add-on's result to <results>/<analysis id>_analysis/<name>.json."""
    folder = os.path.join(results_folder or get_results_folder(), f"{analysis_exe_id}_analysis")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, RESULT_FILES[key])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return path


def addon_result(
    key: str,
    analysis_id: str,
    rerun: bool,
    wait_s: float,
    max_wait: float,
    poll_interval: float,
    results_folder: Optional[str],
    api_key: Optional[str],
    on_progress: Optional[ProgressCallback],
) -> Dict[str, Any]:
    """
    run_addon, then the add-on's block of the merged view (format 5) plus the
    run's ``warnings``, saved to the results folder.
    """
    analysis_exe_id, _, run = run_addon(
        key, analysis_id, rerun=rerun, wait_s=wait_s, max_wait=max_wait,
        poll_interval=poll_interval, on_progress=on_progress, api_key=api_key,
    )
    view = fetch_view(AudialProxy(api_key), analysis_exe_id, poll_interval)
    result = BLOCKS[key](view)
    result["warnings"] = run_warnings(run)
    path = save_result(key, analysis_exe_id, result, results_folder)
    print(f"{LABELS[key]} saved to {path}")
    return result
