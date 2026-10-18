"""
Pipelines: multi-step Audial jobs run as a single API call.

A pipeline is an ordered list of Audial functions that the API runs for you,
feeding each step's output into the next. Two pipelines exist today:

    segmentation   stem-split -> segmentation
    sample-pack    stem-split -> sample-pack

Both of those second steps need separated stems, so calling them directly
means running the stem splitter first and passing the stem URLs along.
`audial.pipelines.run()` sends the file once and the API does the rest::

    import audial

    status = audial.pipelines.run(
        "sample-pack",
        "track.wav",
        options={"genre": "Tech House", "components": ["drums", "bass"]},
        on_progress=lambda s: print(s["state"], s.get("currentStep")),
    )
    print(status["outputs"]["samples"])

The dict returned (and handed to `on_progress`) is the API's PipelineStatus::

    {
      "pipelineId": ..., "pipeline": "sample-pack",
      "state": "queued" | "running" | "completed" | "failed" | "cancelled",
      "currentStep": "sample-pack",
      "steps": [{"name": "stem-split", "state": "completed", "exeId": ...,
                 "durationMs": 41000, "subStage": ..., "error": ...}, ...],
      "outputs": {"stems": {...}, "segmentation": [...], "samples": [...]},
      "original": {"filename": ..., "url": ...},
      "options": {...},
      "error": {"step": ..., "code": ..., "message": ...}   # failed only
    }
"""

import os
import time
from typing import Any, Callable, Dict, List, Optional

from audial.api.constants import (
    DEFAULT_PIPELINE_LIST_LIMIT,
    DEFAULT_PIPELINE_POLL_INTERVAL,
    PIPELINE_STATE_CANCELLED,
    PIPELINE_STATE_FAILED,
    PIPELINE_STEP_COMPLETED,
    PIPELINE_STEP_FAILED,
    PIPELINE_TERMINAL_STATES,
    PIPELINES,
)
from audial.api.exceptions import AudialError
from audial.api.proxy import AudialProxy

# NOTE: `list` below shadows the builtin inside this module on purpose --
# `audial.pipelines.list()` is the documented name. Nothing in this module
# calls the builtin `list()`; use a literal or `List` from typing instead.
__all__ = [
    "run",
    "get",
    "cancel",
    "list",
    "StepTracker",
    "PIPELINES",
]

ProgressCallback = Callable[[Dict[str, Any]], Any]


def run(
    name: str,
    file_path: str,
    options: Optional[Dict[str, Any]] = None,
    wait: bool = True,
    poll_interval: float = DEFAULT_PIPELINE_POLL_INTERVAL,
    on_progress: Optional[ProgressCallback] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run a pipeline on a local audio file.

    The file is uploaded with the request (POST /pipelines), then the pipeline
    is polled (GET /pipelines/{id}) until it reaches a terminal state.

    Args:
        name (str): Pipeline name: "sample-pack" or "segmentation".
        file_path (str): Path to the local audio file.
        options (Dict[str, Any], optional): Pipeline options. Recognized keys:
            components (List[str]), genre (str), bpm (float), keyString (str),
            featuresToExtract (List[str]). Anything omitted gets the API's
            default; BPM and key are detected from the file when not given.
        wait (bool, optional): Wait for the pipeline to finish (default True).
            When False, the initial queued status is returned immediately.
        poll_interval (float, optional): Seconds between status polls.
        on_progress (callable, optional): Called with the PipelineStatus dict
            for the initial response and after every poll.
        api_key (str, optional): API key override.

    Returns:
        Dict[str, Any]: The PipelineStatus. Terminal (state "completed") when
            `wait` is True, otherwise whatever state it is in so far.

    Raises:
        AudialError: If the pipeline name is unknown, the file does not exist,
            or the pipeline ends up "failed" or "cancelled" (the message names
            the step that failed and quotes the API's message).
        SubscriptionRequiredError: If the account's free allowance is used up
            and it has no active subscription (HTTP 402).
        AudialAPIError: If the API returns any other error.
    """
    if name not in PIPELINES:
        known = ", ".join(sorted(PIPELINES))
        raise AudialError(f"Unknown pipeline: {name}. Must be one of: {known}")

    if not os.path.isfile(file_path):
        raise AudialError(f"File not found: {file_path}")

    proxy = AudialProxy(api_key)

    status = proxy.create_pipeline(name, file_path=file_path, options=options)
    pipeline_id = _pipeline_id(status)
    if not pipeline_id:
        raise AudialError(f"No pipeline ID returned when starting pipeline {name}")

    _notify(on_progress, status)

    if not wait:
        return status

    while status.get("state") not in PIPELINE_TERMINAL_STATES:
        time.sleep(poll_interval)
        status = proxy.get_pipeline(pipeline_id)
        _notify(on_progress, status)

    _raise_if_unsuccessful(status, name)
    return status


def get(pipeline_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Get a pipeline's current status (GET /pipelines/{id}).

    Args:
        pipeline_id (str): The pipeline ID.
        api_key (str, optional): API key override.

    Returns:
        Dict[str, Any]: The PipelineStatus.
    """
    return AudialProxy(api_key).get_pipeline(pipeline_id)


def cancel(pipeline_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Cancel a pipeline (POST /pipelines/{id}/cancel).

    Cancellation is honored between steps and, where the running step's job id
    is known, on the running step itself. A pipeline that has already finished
    is returned unchanged.

    Args:
        pipeline_id (str): The pipeline ID.
        api_key (str, optional): API key override.

    Returns:
        Dict[str, Any]: The PipelineStatus after the cancel request.
    """
    return AudialProxy(api_key).cancel_pipeline(pipeline_id)


def list(
    limit: int = DEFAULT_PIPELINE_LIST_LIMIT,
    cursor: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List your pipelines, newest first (GET /pipelines).

    Args:
        limit (int, optional): Page size (default 20).
        cursor (str, optional): `nextCursor` from a previous page.
        api_key (str, optional): API key override.

    Returns:
        Dict[str, Any]: {"items": [PipelineStatus, ...], "nextCursor": str?}
            -- the API's page envelope, so paging is possible.
    """
    return AudialProxy(api_key).list_pipelines(limit=limit, cursor=cursor)


# ---------------------------------------------------------------------------
# Progress reporting
# ---------------------------------------------------------------------------

class StepTracker:
    """
    Turns a stream of PipelineStatus dicts into one line per step change.

    Polling returns the whole status every time; what a caller usually wants to
    show is the difference. Feed each status to `changes()` and it returns the
    human-readable step transitions since the previous call, e.g.::

        ["stem-split completed in 41 s", "sample-pack running"]

    Used by the CLI's `audial pipeline` progress output and by wrappers (the
    MCP server) that forward step changes to their own clients.
    """

    def __init__(self):
        self._steps: Dict[str, str] = {}
        self._state: Optional[str] = None

    def changes(self, status: Dict[str, Any]) -> List[str]:
        """Step/state transitions in `status` that have not been reported yet."""
        lines: List[str] = []

        for step in status.get("steps") or []:
            if not isinstance(step, dict):
                continue
            name = step.get("name")
            if not name:
                continue
            # A step's substage (the sample-pack worker reports "analysis",
            # then "rendering") is tracked as part of its state, so moving
            # between substages is itself a reportable change.
            state = step.get("state") or "pending"
            key = f"{state}:{step.get('subStage') or ''}"
            if self._steps.get(name) == key:
                continue
            self._steps[name] = key
            line = _step_line(step)
            if line:
                lines.append(line)

        state = status.get("state")
        if state != self._state:
            self._state = state
            if state in PIPELINE_TERMINAL_STATES and not _failed_steps(status):
                lines.append(f"pipeline {state}{_duration_suffix(status)}")

        return lines


def _step_line(step: Dict[str, Any]) -> Optional[str]:
    name = step.get("name")
    state = step.get("state") or "pending"
    sub_stage = step.get("subStage")

    if state == "pending":
        return None
    if state == PIPELINE_STEP_COMPLETED:
        return f"{name} completed{_duration_suffix(step)}"
    if state == PIPELINE_STEP_FAILED:
        return f"{name} failed: {_step_error(step)}"
    if state == "running":
        if sub_stage:
            return f"{name} running ({sub_stage})"
        return f"{name} running"
    return f"{name} {state}"


def _duration_suffix(record: Dict[str, Any]) -> str:
    duration_ms = record.get("durationMs")
    if not isinstance(duration_ms, (int, float)):
        return ""
    return f" in {round(duration_ms / 1000)} s"


def _step_error(step: Dict[str, Any]) -> str:
    error = step.get("error")
    if isinstance(error, dict):
        return error.get("message") or error.get("code") or "unknown error"
    if isinstance(error, str) and error:
        return error
    return "unknown error"


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _pipeline_id(status: Dict[str, Any]) -> Optional[str]:
    if not isinstance(status, dict):
        return None
    for key in ("pipelineId", "pipeline_id", "id"):
        value = status.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _notify(on_progress: Optional[ProgressCallback], status: Dict[str, Any]) -> None:
    """Call the progress callback; its failure must not fail the pipeline."""
    if on_progress is None:
        return
    try:
        on_progress(status)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Progress callback raised {type(exc).__name__}: {exc}")


def _failed_steps(status: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        step
        for step in (status.get("steps") or [])
        if isinstance(step, dict) and step.get("state") == PIPELINE_STEP_FAILED
    ]


def _raise_if_unsuccessful(status: Dict[str, Any], name: str) -> None:
    """Raise AudialError naming the step for a failed or cancelled pipeline."""
    state = status.get("state")
    if state not in (PIPELINE_STATE_FAILED, PIPELINE_STATE_CANCELLED):
        return

    error = status.get("error") if isinstance(status.get("error"), dict) else {}
    failed = _failed_steps(status)
    step = error.get("step") or (failed[0].get("name") if failed else None)
    step = step or status.get("currentStep")

    message = error.get("message")
    if not message and failed:
        message = _step_error(failed[0])
    if not message:
        message = (
            "cancelled" if state == PIPELINE_STATE_CANCELLED else "unknown error"
        )

    code = error.get("code")
    where = f" at step {step}" if step else ""
    suffix = f" ({code})" if code else ""
    raise AudialError(f"Pipeline {name} {state}{where}: {message}{suffix}")


def outputs(status: Dict[str, Any], key: str) -> Any:
    """`status["outputs"][key]`, tolerating a status with no outputs yet."""
    all_outputs = status.get("outputs")
    if not isinstance(all_outputs, dict):
        return None
    return all_outputs.get(key)


def step(status: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    """The step record called `name`, if the status has one."""
    for record in status.get("steps") or []:
        if isinstance(record, dict) and record.get("name") == name:
            return record
    return None
