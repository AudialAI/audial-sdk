"""
Tags of an analysis: genre, moods and instruments for the whole track and for
each of its parts, artist tags and a written description.
"""

from typing import Any, Callable, Dict, Optional

from audial.api.constants import (
    ADDON_DEFAULT_MAX_WAIT,
    ADDON_DEFAULT_POLL_INTERVAL,
    ADDON_DEFAULT_WAIT_S,
)
from audial.api.proxy import AudialProxy
from audial.functions import _addon
from audial.functions.segment import _fetch_view


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
    Get the tags of an analysed track: genre, moods, instruments and artist tags for
    the mix and each part, plus a written description.

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
        Dict[str, Any]: The tags, exactly as the Audial website shows them::

            {
              "genre": ["UK Garage", "Speed Garage"],      # use as they are
              "song_tags": {
                "full":   {"moods": [...], "instruments": [...], "artist_tags": [...]},
                "drums":  {"moods": [...], "instruments": [...], "silent": False},
                "bass":   {"moods": [...], "instruments": [...], "silent": False},
                "melody": {"moods": [...], "instruments": [...], "silent": False},
                "vocals": {"moods": [...], "instruments": [...], "silent": False}
              },
              "description": "A driving UK garage cut ...",   # "" when none was made
              "warnings": []
            }

        There are five parts: ``full`` (the mix), ``drums``, ``bass``, ``melody``
        and ``vocals``. ``artist_tags`` belong to the mix. A part whose stem is
        silent has ``"silent": True`` and empty lists (for ``vocals``: no vocals
        in the track). An analysis made before the drums and vocals were tagged
        has the first three parts only, and no description. Lists that exist are
        always lists (empty when nothing was found).

    Raises:
        AudialAPIError: ``code == "STEMS_NOT_READY"`` when the stems are still
            not ready after ``wait_s`` or could not be made;
            ``code == "ADDON_UNAVAILABLE"`` when this analysis can't have tags
            (for example an older analysis that kept no stems); the run
            failed; or the API returned another error.
        AudialAuthError: If the credentials are rejected.
    """
    analysis_exe_id, record, run = _addon.run_addon(
        "tags", analysis_id, rerun=rerun, wait_s=wait_s, max_wait=max_wait,
        poll_interval=poll_interval, on_progress=on_progress, api_key=api_key,
    )
    # The values the website shows come from the merged view; the record has the warnings.
    view = _fetch_view(AudialProxy(api_key), analysis_exe_id, poll_interval)
    data = view.get("audio_segmentation") if isinstance(view.get("audio_segmentation"), dict) else {}
    song = data.get("song_analysis") if isinstance(data.get("song_analysis"), dict) else {}
    stored = run.get("result") if isinstance(run.get("result"), dict) else {}
    result = _addon.normalize_result("tags", {
        "genre": song.get("genre"),
        "song_tags": song.get("song_tags"),
        "description": song.get("description"),
        "warnings": stored.get("warnings"),
    })
    path = _addon.save_result("tags", analysis_exe_id, result, results_folder)
    print(f"{_addon.LABELS['tags']} saved to {path}")
    return result
