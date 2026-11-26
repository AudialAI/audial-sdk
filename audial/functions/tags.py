"""
Tags of an analysis: genres, moods and instruments for the whole track,
instruments and moods for each of its parts, and a written description.
"""

from typing import Any, Callable, Dict, Optional

from audial.api.constants import (
    ADDON_DEFAULT_MAX_WAIT,
    ADDON_DEFAULT_POLL_INTERVAL,
    ADDON_DEFAULT_WAIT_S,
)
from audial.functions._addon import addon_result


def tags(
    analysis_id: str,
    rerun: bool = False,
    wait_s: float = ADDON_DEFAULT_WAIT_S,
    max_wait: float = ADDON_DEFAULT_MAX_WAIT,
    poll_interval: float = ADDON_DEFAULT_POLL_INTERVAL,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None,
) -> Dict[str, Any]:
    """
    Get the tags of an analysed track: genres, instruments and moods for the
    mix, instruments and moods for each part, and a written description.

    Prerequisites: an analysis (``audial.segment()``) and its stems. Every
    analysis makes its stems in the background as soon as it starts (the
    drums, bass, melody and vocals stems are what this reads), so there is nothing to do;
    until they are ready the API answers ``409 STEMS_NOT_READY`` ("This track is still being
    prepared. Try again in a minute.") and this function keeps trying for up to
    ``wait_s`` seconds. If making the stems failed, it is started again once.

    Cost: included with the analysis (free on an analysis of yours). Calling it
    again returns the same result without a new run; ``rerun=True`` makes a
    new one.

    Timing: the first request after a quiet period waits for a machine to start
    ("Starting up — this can take a minute"); ``on_progress`` reports it.

    Args:
        analysis_id (str): The ``analysis_id`` that ``audial.segment()``
            returned (or an analysis's id from your history).
        rerun (bool, optional): Tag again even if a result exists.
        wait_s (float, optional): Seconds to keep trying while the stems
            are being made (default 600).
        max_wait (float, optional): Seconds to wait for the result once it has
            started (default 900). It keeps running after that; calling again
            collects it.
        poll_interval (float, optional): Seconds between status checks.
        results_folder (str, optional): Where the result is saved, as
            ``<analysis_id>_analysis/tags.json``. Uses the default results
            folder if None.
        api_key (str, optional): API key to use. Uses default if None.
        on_progress (callable, optional): Called with the run's execution
            record after every check; it carries ``warmup`` while a machine
            starts (see ``audial.warmup``).

    Returns:
        Dict[str, Any]: The ``tags`` block and ``description`` of the analysis
        (format 5), exactly as the Audial website shows them::

            {
              "genres": ["UK Garage", "Deep House"],       # use as they are
              "instruments": ["synth bass", "synth pads"],
              "moods": ["hypnotic", "driving"],
              "stems": {
                "drums":  {"instruments": ["kick", ...], "moods": [...]},
                "bass":   {"instruments": [...], "moods": [...]},
                "melody": {"instruments": [...], "moods": [...]},
                "vocals": {"silent": True}                # no vocals in this track
              },
              "description": "This track is ...",          # "" when none was written
              "warnings": []                               # from this run
            }

        ``genres``, ``instruments`` and ``moods`` belong to the mix. A part of
        ``stems`` is ``{"instruments", "moods"}``, or just ``{"silent": True}``
        when that part of the track is silent. An analysis tagged before the
        drums and vocals were tagged has ``bass`` and ``melody`` only, and no
        description. Lists are always lists (empty when nothing was found).
        ``audial.segment()`` (the merged view) holds the same values under
        ``tags`` and ``description``.

    Raises:
        AudialAPIError: ``code == "STEMS_NOT_READY"`` when the stems are still
            not ready after ``wait_s`` or could not be made;
            ``code == "ADDON_UNAVAILABLE"`` when this analysis can't have tags
            (for example an older analysis that kept no stems); the run
            failed; or the API returned another error.
        AudialAuthError: If the credentials are rejected.
    """
    return addon_result("tags", analysis_id, rerun, wait_s, max_wait, poll_interval,
                        results_folder, api_key, on_progress)
