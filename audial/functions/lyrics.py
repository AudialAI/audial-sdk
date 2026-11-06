"""
Lyrics of an analysis, with word timings: the whole text, timed lines whose
words carry their own start and end, the lyrics of each section, and when the
vocals start.

Also reachable as ``audial.lyrics(analysis_id)``: the ``audial.lyrics`` module
(the per-note lyric grammar of text2vox) can be called like this function.
"""

from typing import Any, Callable, Dict, Optional

from audial.api.constants import (
    ADDON_DEFAULT_MAX_WAIT,
    ADDON_DEFAULT_POLL_INTERVAL,
    ADDON_DEFAULT_WAIT_S,
)
from audial.functions._addon import addon_result


def lyrics(
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
    Get the lyrics of an analysed track, with a start and end time for every word.

    Prerequisites: an analysis (``audial.segment()``) and its stems. Every
    analysis makes its stems in the background as soon as it starts (the
    vocal stem is what this reads), so there is nothing to do; until they
    are ready the API answers ``409 STEMS_NOT_READY`` ("This track is still being
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
        rerun (bool, optional): Transcribe again even if a result exists.
        wait_s (float, optional): Seconds to keep trying while the stems
            are being made (default 600).
        max_wait (float, optional): Seconds to wait for the result once it has
            started (default 900). It keeps running after that; calling again
            collects it.
        poll_interval (float, optional): Seconds between status checks.
        results_folder (str, optional): Where the result is saved, as
            ``<analysis_id>_analysis/lyrics.json``. Uses the default results
            folder if None.
        api_key (str, optional): API key to use. Uses default if None.
        on_progress (callable, optional): Called with the run's execution
            record after every check; it carries ``warmup`` while a machine
            starts (see ``audial.warmup``).

    Returns:
        Dict[str, Any]: The lyrics, times in seconds on the track's timeline::

            {
              "lyrics": "hello there ...",
              "is_instrumental": False,
              "lines": [
                {"start": 12.34, "end": 13.10,
                 "words": [["hello", 12.34, 12.71], ["there", 12.80, 13.10]]},
                ...
              ],
              "segments": [{"text": "hello there", "start": 12.34, "end": 13.10}, ...],
              "section_lyrics": ["", "hello there ...", ...],   # one per section
              "first_vocal_beat_time": 12.34,                   # None without vocals
              "warnings": []
            }

        ``lines`` and every word are ``[word, start, end]``, ready for a
        karaoke-style highlight. An instrumental has ``is_instrumental`` True
        and no lines ("No vocals in this track.").

    Raises:
        AudialAPIError: ``code == "STEMS_NOT_READY"`` when the stems are still
            not ready after ``wait_s`` or could not be made;
            ``code == "ADDON_UNAVAILABLE"`` when this analysis can't have lyrics
            (for example an older analysis that kept no stems); the run
            failed; or the API returned another error.
        AudialAuthError: If the credentials are rejected.
    """
    return addon_result("lyrics", analysis_id, rerun, wait_s, max_wait, poll_interval,
                        results_folder, api_key, on_progress)
