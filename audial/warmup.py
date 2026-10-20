"""
Machine warm-up: saying "this one is slow because the GPU was asleep".

Audial's workers scale to zero. The first request after an idle period has to
start a worker and load the model before any audio is processed, which adds a
few minutes to that one job; every run after it is fast. Without a word about
it, a cold start looks exactly like a hung job.

The API decides warm vs cold before it dispatches and writes the phase onto
the execution (and onto each pipeline step), so every client reads the same
field and shows the same sentence::

    "warmup": {
      "state": "cold" | "initializing" | "working" | "done",
      "detectedAt": ..., "updatedAt": ...,
      "expectedColdStartMs": 180000,   # the endpoint's 7-day cold-start p50
      "expectedRunMs": 42000,
      "delayMs": 174000                # state "done": what the wait cost
    }

This module is the one place the wording lives. The SDK's CLI and the MCP
server (`audial_mcp`) both format their messages with it, so the user reads
the same thing wherever they are.

Two ways in:

* Pass ``on_progress`` to any function that polls (``text2vox``,
  ``sound2vital``, ``generate_music``, ``stem_split``, ``master``,
  ``generate_midi``, ``analyze``, ``segment``, ``generate_samples``,
  ``pipelines.run``). It is called with each execution/pipeline status;
  ``message(status)`` turns one into a sentence, and ``WarmupTracker`` into
  one line per change::

      tracker = audial.warmup.WarmupTracker()
      audial.sound2vital("kick.wav", on_progress=lambda s: [
          print(line) for line in tracker.changes(s)
      ])

* Ask before you submit, with ``audial.status()`` -- a cold service can be
  announced before the job even exists::

      if audial.warmup.is_cold(audial.status(), "text2vox"):
          print(audial.warmup.cold_start_message())
"""

from typing import Any, Callable, Dict, List, Optional

__all__ = [
    "COLD_START_TEXT",
    "WORKING_TEXT",
    "STATE_COLD",
    "STATE_INITIALIZING",
    "STATE_WORKING",
    "STATE_DONE",
    "expected_minutes",
    "cold_start_message",
    "warmup_of",
    "state_of",
    "message",
    "WarmupTracker",
    "WarmupReporter",
    "notify",
    "find_function",
    "is_cold",
]

# Warm-up phases, as the API writes them onto an execution.
STATE_COLD = "cold"
STATE_INITIALIZING = "initializing"
STATE_WORKING = "working"
STATE_DONE = "done"

# The two sentences. `{about}` becomes " (about 3 min)" when the API told us
# what a cold start costs on this endpoint, and nothing when it did not.
COLD_START_TEXT = (
    "Warming up the machine — the first request takes a few minutes longer "
    "than usual{about}; every run after this is faster"
)

WORKING_TEXT = "Working on your job…"

_MS_PER_MINUTE = 60_000


def expected_minutes(expected_cold_start_ms: Optional[Any]) -> Optional[int]:
    """
    ``expectedColdStartMs`` as whole minutes, rounded, never below 1.

    Args:
        expected_cold_start_ms: Milliseconds, or None/anything unusable.

    Returns:
        Optional[int]: Minutes to quote, or None when there is no number to
            quote (the sentence then just says "a few minutes").
    """
    if isinstance(expected_cold_start_ms, bool) or not isinstance(
        expected_cold_start_ms, (int, float)
    ):
        return None
    if expected_cold_start_ms <= 0:
        return None
    return max(1, int(expected_cold_start_ms / _MS_PER_MINUTE + 0.5))


def cold_start_message(expected_cold_start_ms: Optional[Any] = None) -> str:
    """
    The sentence shown while a cold worker starts up.

    Args:
        expected_cold_start_ms: The endpoint's expected cold start in
            milliseconds, from a ``warmup`` object or ``audial.status()``.
            Omit it and the minute figure is left out.

    Returns:
        str: e.g. "Warming up the machine - the first request takes a few
            minutes longer than usual (about 3 min); every run after this is
            faster".
    """
    minutes = expected_minutes(expected_cold_start_ms)
    about = f" (about {minutes} min)" if minutes else ""
    return COLD_START_TEXT.format(about=about)


def warmup_of(status: Any) -> Optional[Dict[str, Any]]:
    """
    The ``warmup`` object in an execution record or a pipeline status.

    A pipeline carries one per step; the one that matters is the step being
    run, so ``currentStep`` is preferred and otherwise the last step that has
    a warm-up object and has not finished warming.

    Args:
        status: An execution record, a PipelineStatus, or a ``warmup``
            object itself (so callers can pass whichever they hold).

    Returns:
        Optional[Dict[str, Any]]: The warm-up object, or None.
    """
    if not isinstance(status, dict):
        return None

    if status.get("state") in (STATE_COLD, STATE_INITIALIZING, STATE_WORKING, STATE_DONE) and (
        "warmup" not in status
    ):
        # Already a warm-up object: its "state" is a warm-up phase, which an
        # execution's or pipeline's "state" never is.
        return status

    own = status.get("warmup")
    if isinstance(own, dict) and own:
        return own

    steps = [step for step in (status.get("steps") or []) if isinstance(step, dict)]
    if not steps:
        return None

    current = status.get("currentStep")
    if current:
        for step in steps:
            if step.get("name") == current:
                candidate = step.get("warmup")
                if isinstance(candidate, dict) and candidate:
                    return candidate

    unfinished = [
        step.get("warmup")
        for step in steps
        if isinstance(step.get("warmup"), dict)
        and step["warmup"]
        and step["warmup"].get("state") != STATE_DONE
    ]
    if unfinished:
        return unfinished[-1]

    finished = [
        step.get("warmup")
        for step in steps
        if isinstance(step.get("warmup"), dict) and step["warmup"]
    ]
    return finished[-1] if finished else None


def state_of(status: Any) -> Optional[str]:
    """
    The warm-up state of an execution or pipeline status, if it has one.

    Args:
        status: An execution record or a PipelineStatus.

    Returns:
        Optional[str]: "cold", "initializing", "working", "done", or None
            when the job never needed a warm-up (the usual case).
    """
    warmup = warmup_of(status)
    if not warmup:
        return None
    state = warmup.get("state")
    return state if isinstance(state, str) else None


def message(status: Any) -> Optional[str]:
    """
    What to tell the user about this status, or None to say nothing.

    "cold" and "initializing" both mean the machine is starting, so both get
    the cold-start sentence; "working" means the job itself is running on a
    worker that had to be started; "done" and a job that never waited get
    nothing, because there is nothing unusual to explain.

    Args:
        status: An execution record, a PipelineStatus, or a ``warmup`` object.

    Returns:
        Optional[str]: The sentence to show, or None.
    """
    warmup = warmup_of(status)
    if not warmup:
        return None
    state = warmup.get("state")
    if state in (STATE_COLD, STATE_INITIALIZING):
        return cold_start_message(warmup.get("expectedColdStartMs"))
    if state == STATE_WORKING:
        return WORKING_TEXT
    return None


class WarmupTracker:
    """
    Turns a stream of statuses into one line per warm-up change.

    Polling returns the whole status every time; what a user wants to see is
    the moment it changed. ``changes()`` returns the sentence only when it is
    not the one already shown, so a cold start that was announced before the
    job was submitted is not announced again when the execution reports it::

        tracker = WarmupTracker()
        tracker.changes(cold_status)         # ["Warming up the machine ..."]
        tracker.changes(initializing)        # [] -- same sentence, said once
        tracker.changes(working)             # ["Working on your job..."]
        tracker.changes(done)                # []

    Mirrors ``audial.pipelines.StepTracker``, and is used the same way by the
    CLI and by the MCP server.
    """

    def __init__(self, last_message: Optional[str] = None):
        """
        Args:
            last_message (str, optional): A sentence already shown, so it is
                not repeated. ``WarmupReporter`` passes its pre-flight line.
        """
        self._last = last_message
        self._state: Optional[str] = None

    def suppress(self, line: str) -> None:
        """Treat `line` as already shown, so `changes` will not repeat it."""
        self._last = line

    @property
    def state(self) -> Optional[str]:
        """The warm-up state last seen, or None if none was ever reported."""
        return self._state

    def changes(self, status: Any) -> List[str]:
        """
        The warm-up sentences in `status` that have not been shown yet.

        Args:
            status: An execution record or a PipelineStatus.

        Returns:
            List[str]: Zero or one sentence. A list, to read like
                ``StepTracker.changes`` at the call site.
        """
        state = state_of(status)
        if state is not None:
            self._state = state
        text = message(status)
        if not text or text == self._last:
            return []
        self._last = text
        return [text]


class WarmupReporter:
    """
    The CLI's warm-up output: a pre-flight check, then one line per change.

    Used as the ``on_progress`` callback itself::

        reporter = WarmupReporter()
        reporter.preflight("text2vox", api_key=key)   # before submitting
        audial.text2vox(..., on_progress=reporter)    # while polling

    The pre-flight call (``GET /functions/status``) explains the long wait
    before the request that causes it is even sent; it is best-effort, and a
    status endpoint that is unreachable or unknown never stops a job.
    """

    def __init__(self, printer: Callable[[str], Any] = print):
        """
        Args:
            printer (callable, optional): Where lines go. Defaults to print;
                tests and wrappers pass their own.
        """
        self._printer = printer
        self._tracker = WarmupTracker()
        self.lines: List[str] = []

    def preflight(self, function: str, api_key: Optional[str] = None) -> Optional[str]:
        """
        Announce a cold service before the job is submitted.

        Args:
            function (str): An SDK function name ("text2vox") or an API
                function name ("stem-splitter").
            api_key (str, optional): API key override.

        Returns:
            Optional[str]: The sentence shown, or None if the service is warm
                (or the check could not be made).
        """
        from audial.status import status as functions_status

        try:
            item = find_function(functions_status(function, api_key=api_key), function)
        except Exception:
            # Nothing about a cold start is worth failing a job over.
            return None
        if not item or item.get("warm"):
            return None
        return self._say(cold_start_message(item.get("expectedColdStartMs")))

    def __call__(self, status: Any) -> None:
        """Report any warm-up change in `status`. Shape of ``on_progress``."""
        for line in self._tracker.changes(status):
            self._say(line)

    def _say(self, line: str) -> str:
        self.lines.append(line)
        # Keep the tracker from repeating a sentence this reporter has shown.
        self._tracker.suppress(line)
        self._printer(line)
        return line


def notify(on_progress: Optional[Callable[[Dict[str, Any]], Any]], status: Any) -> None:
    """
    Call a progress callback with a status; never let it fail the job.

    Used by every polling function in the SDK, the same way
    ``pipelines._notify`` is used for pipelines.

    Args:
        on_progress (callable, optional): The caller's callback, or None.
        status: The execution record or PipelineStatus to hand it.
    """
    if on_progress is None:
        return
    try:
        on_progress(status)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Progress callback raised {type(exc).__name__}: {exc}")


def find_function(status_doc: Any, function: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    One function's entry in an ``audial.status()`` document.

    Args:
        status_doc: ``{"items": [{"function", "warm", ...}, ...]}``.
        function (str, optional): An SDK name ("generate_samples") or an API
            name ("sample-pack"). With one item and no name given, that item
            is returned.

    Returns:
        Optional[Dict[str, Any]]: The item, or None if it is not in there.
    """
    if not isinstance(status_doc, dict):
        return None
    items = [item for item in (status_doc.get("items") or []) if isinstance(item, dict)]
    if not items:
        return None
    if function is None:
        return items[0] if len(items) == 1 else None

    from audial.api.constants import STATUS_FUNCTIONS

    wanted = {function, STATUS_FUNCTIONS.get(function, function)}
    for item in items:
        if item.get("function") in wanted:
            return item
    return None


def is_cold(status_doc: Any, function: Optional[str] = None) -> bool:
    """
    Whether a function's workers are all asleep right now.

    Args:
        status_doc: An ``audial.status()`` document.
        function (str, optional): Which function to look at.

    Returns:
        bool: True only when the service is known to be cold; an unknown
            function or an unreadable document is False, so a caller never
            warns about a warm-up that may not happen.
    """
    item = find_function(status_doc, function)
    if not item:
        return False
    return item.get("warm") is False
