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

Starting is idempotent (a repeated call answers the run that exists), so a
retry never starts a second run.
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
                give_up = exc
            else:
                raise

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise give_up
        time.sleep(min(pause, remaining))


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
# Results: the same shape however the database kept them
# ---------------------------------------------------------------------------

def listify(value: Any) -> List[Any]:
    """A list as stored: lists stay lists; {"0": a, "1": b} (a sparse list) becomes [a, b]."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and value and all(str(k).isdigit() for k in value):
        return [value[k] for k in sorted(value, key=lambda k: int(k))]
    return []


def _strings(value: Any) -> List[str]:
    return [item for item in listify(value) if isinstance(item, str)]


SONG_TAG_LISTS = {
    "full": ("moods", "instruments", "artist_tags", "extra_tags"),
    "bass": ("moods", "instruments"),
    "melody": ("moods", "instruments"),
}


def normalize_result(key: str, result: Any) -> Dict[str, Any]:
    """An add-on's result with every list present as a list (the database drops empty ones)."""
    out: Dict[str, Any] = dict(result) if isinstance(result, dict) else {}

    if key == "features":
        out["sections"] = [s for s in listify(out.get("sections")) if isinstance(s, dict)]
        out["warnings"] = _strings(out.get("warnings"))
    elif key == "tags":
        out["genre"] = _strings(out.get("genre"))
        song_tags = dict(out.get("song_tags")) if isinstance(out.get("song_tags"), dict) else {}
        for part, names in SONG_TAG_LISTS.items():
            source = song_tags.get(part) if isinstance(song_tags.get(part), dict) else {}
            song_tags[part] = dict(source, **{name: _strings(source.get(name)) for name in names})
        out["song_tags"] = song_tags
        out["warnings"] = _strings(out.get("warnings"))
    elif key == "lyrics":
        out["lyrics"] = out.get("lyrics") if isinstance(out.get("lyrics"), str) else ""
        out["lines"] = [
            dict(line,
                 start=line.get("start") if isinstance(line.get("start"), (int, float)) else None,
                 end=line.get("end") if isinstance(line.get("end"), (int, float)) else None,
                 words=[listify(word) for word in listify(line.get("words"))])
            for line in listify(out.get("lines"))
            if isinstance(line, dict)
        ]
        out["segments"] = [s for s in listify(out.get("segments")) if isinstance(s, dict)]
        out["section_lyrics"] = [s if isinstance(s, str) else "" for s in listify(out.get("section_lyrics"))]
        vocal_start = out.get("first_vocal_beat_time")
        out["first_vocal_beat_time"] = vocal_start if isinstance(vocal_start, (int, float)) else None
        out["warnings"] = _strings(out.get("warnings"))
    return out


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
    """run_addon, then the normalized result, saved to the results folder."""
    analysis_exe_id, _, run = run_addon(
        key, analysis_id, rerun=rerun, wait_s=wait_s, max_wait=max_wait,
        poll_interval=poll_interval, on_progress=on_progress, api_key=api_key,
    )
    result = normalize_result(key, run.get("result"))
    path = save_result(key, analysis_exe_id, result, results_folder)
    print(f"{LABELS[key]} saved to {path}")
    return result
