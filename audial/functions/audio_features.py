"""
Audio features of an analysis: energy, danceability and loudness for the song
and for each section, and the song's mode and beat division (tatum), with the
track's key.
"""

from typing import Any, Callable, Dict, Optional

from audial.api.constants import (
    ADDON_DEFAULT_MAX_WAIT,
    ADDON_DEFAULT_POLL_INTERVAL,
    ADDON_DEFAULT_WAIT_S,
)
from audial.functions._addon import addon_result


def audio_features(
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
    Get the audio features of an analysed track.

    Energy and danceability are 0-1 (shown as 0-100%). Energy reflects
    loudness, rhythmic activity and low end; danceability reflects how strong
    and regular the beat is. Both are measured per section, so a drop reads
    higher than its breakdown. Loudness is integrated loudness in LUFS
    (ITU-R BS.1770, over both channels).

    Prerequisite: an analysis (``audial.segment()``). Audio features read the
    mix, so they can run as soon as the analysis has finished.

    Cost: included with the analysis (free on an analysis of yours). Calling it
    again returns the same result without a new run; ``rerun=True`` makes a
    new one.

    Timing: the first request after a quiet period waits for a machine to start
    ("Starting up — this can take a minute"); ``on_progress`` reports it.

    Args:
        analysis_id (str): The ``analysis_id`` that ``audial.segment()``
            returned (or an analysis's id from your history).
        rerun (bool, optional): Measure again even if a result exists.
        wait_s (float, optional): Seconds to keep trying while the analysis is
            still running (default 600).
        max_wait (float, optional): Seconds to wait for the result once it has
            started (default 900). It keeps running after that; calling again
            collects it.
        poll_interval (float, optional): Seconds between status checks.
        results_folder (str, optional): Where the result is saved, as
            ``<analysis_id>_analysis/features.json``. Uses the default results
            folder if None.
        api_key (str, optional): API key to use. Uses default if None.
        on_progress (callable, optional): Called with the run's execution
            record after every check; it carries ``warmup`` while a machine
            starts (see ``audial.warmup``).

    Returns:
        Dict[str, Any]: What audio features add to the analysis (format 5)::

            {
              "key": "Bmin",                  # the track's key (top level of the analysis)
              "camelot": "10A",
              "features": {"energy": 0.597, "danceability": 0.474, "loudness_lufs": -8.94,
                           "mode": "Natural Minor", "mode_confidence": 0.806,
                           "tatum": "1/32"},
              "sections": [{"label": "INTRO", "start": 5.768, "end": 35.511,
                            "energy": 0.599, "danceability": 0.58,
                            "loudness_lufs": -10.42}, ...],   # one per section
              "warnings": []                  # from this run
            }

        A value that could not be measured is None. ``key`` is found by the
        analysis itself; on an analysis made before 2026-11-26 it comes from
        these audio features, and is None until they have run. ``camelot``
        is None when ``key`` is. ``audial.segment()`` (the merged view) holds
        the same values: ``key``, ``camelot``, ``features``, and the numbers
        on each of its ``sections``.

    Raises:
        AudialAPIError: ``code == "ADDON_UNAVAILABLE"`` when this analysis
            can't have audio features; the run failed; or the API returned
            another error.
        AudialAuthError: If the credentials are rejected.
    """
    return addon_result("features", analysis_id, rerun, wait_s, max_wait, poll_interval,
                        results_folder, api_key, on_progress)
