"""
The tempo map ("grid") of an Audial analysis.

Beats and bars aren't listed one by one. ``grid`` describes them: where each
constant-tempo piece starts, its BPM, and its bar and beat. Every beat time is
``start + k * 60 / bpm``. Most tracks have one piece::

    "time_signature": "4/4",
    "grid": {
      "beat_count": 841, "bar_count": 208, "max_error_ms": 9.2,
      "pieces": [{"start": 0.195, "bpm": 129.0, "bar": -2, "beat": 1, "count": 841}]
    }

The whole rule::

    for piece in pieces:
        for k in 0 .. piece.count - 1:
            beat k is at piece.start + k * 60 / piece.bpm, labelled (bar, beat)
            then the beat moves on by one; after the last beat of a bar comes beat 1 of the next

- Beats per bar are the top number of the analysis's ``time_signature``
  ("4/4" -> 4), and 4 when there is none. (Format 4 grids carried
  ``beats_per_bar`` themselves; it is still read.)
- Beat times are all the pieces' beats in order, rounded to 3 decimals.
- Bar times are the times of the beats with ``beat == 1`` and ``bar >= 1``.
- Bars 0 and below are the lead-in before bar 1, counted back (..., -1, 0).
- ``beat_count`` and ``bar_count`` are the totals, so nothing needs expanding
  just to count.

Every function here takes a ``grid`` on its own or a whole analysis:

- the format 5 analysis ``audial.segment()`` returns under ``analysis`` (or the
  whole ``segment()`` result);
- an older analysis file: format 4 (with or without its ``audio_segmentation``
  wrapper), or format 2 and 3, which list ``beat_times`` and ``bar_times``
  instead of a grid.

``audial.segment(expand_beats=True)`` adds ``beat_times`` and ``bar_times`` to
its result with these functions.

Standard library only.
"""

from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "GRID_TOLERANCE_MS",
    "expand",
    "expand_grid",
    "beat_times",
    "bar_times",
    "beats_of",
    "beats_per_bar",
    "next_label",
]

GRID_TOLERANCE_MS = 25.0   # every expanded beat is within this many ms of the detected beat
DEFAULT_BEATS_PER_BAR = 4

Beat = Tuple[float, int, int]


def next_label(label: Tuple[int, int], beats_per_bar: int = DEFAULT_BEATS_PER_BAR) -> Tuple[int, int]:
    """The (bar, beat) after ``label``: beat ``beats_per_bar`` is followed by beat 1 of the next bar."""
    bar, beat = label
    return (bar + 1, 1) if beat >= beats_per_bar else (bar, beat + 1)


def _positive_int(value: Any) -> Optional[int]:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _numerator(time_signature: Any) -> Optional[int]:
    """The top number of a time signature ("4/4" -> 4, "6/8" -> 6), or None."""
    if not isinstance(time_signature, str) or "/" not in time_signature:
        return None
    return _positive_int(time_signature.split("/", 1)[0].strip())


def _is_grid(obj: Dict[str, Any]) -> bool:
    return "pieces" in obj


def _analysis(obj: Any) -> Dict[str, Any]:
    """The analysis inside ``obj``: a segment() result, a format 4 wrapper, or the analysis itself."""
    if not isinstance(obj, dict):
        return {}
    if isinstance(obj.get("audio_segmentation"), dict):
        return obj["audio_segmentation"]
    # A segment() result: {"analysis_id": ..., "analysis": {...}, ...}.
    if isinstance(obj.get("analysis"), dict) and "grid" not in obj and "beat_times" not in obj:
        return obj["analysis"]
    return obj


def beats_per_bar(obj: Dict[str, Any]) -> int:
    """
    Beats per bar of an analysis (or of a grid).

    A format 4 grid's own ``beats_per_bar`` comes first, then the top number of
    the analysis's ``time_signature``; 4 when neither is there.
    """
    if not isinstance(obj, dict):
        return DEFAULT_BEATS_PER_BAR
    if _is_grid(obj):
        return _positive_int(obj.get("beats_per_bar")) or DEFAULT_BEATS_PER_BAR
    seg = _analysis(obj)
    grid = seg.get("grid") if isinstance(seg.get("grid"), dict) else {}
    return (
        _positive_int(grid.get("beats_per_bar"))
        or _numerator(seg.get("time_signature"))
        or DEFAULT_BEATS_PER_BAR
    )


def expand_grid(grid: Dict[str, Any], beats_per_bar: Optional[int] = None) -> List[Beat]:
    """
    [(time, bar, beat), ...] for every beat of a grid, times rounded to 0.001 s.

    Beats per bar: ``beats_per_bar`` when given, else the grid's own (format 4),
    else 4. For a format 5 analysis use ``expand(analysis)``, which reads them
    from its ``time_signature``.
    """
    bpb = (
        _positive_int(beats_per_bar)
        or _positive_int((grid or {}).get("beats_per_bar"))
        or DEFAULT_BEATS_PER_BAR
    )
    out: List[Beat] = []
    for piece in (grid or {}).get("pieces") or []:
        period = 60.0 / float(piece["bpm"])
        label = (int(piece["bar"]), int(piece["beat"]))
        start = float(piece["start"])
        for k in range(int(piece["count"])):
            out.append((round(start + k * period, 3), label[0], label[1]))
            label = next_label(label, bpb)
    return out


def expand(obj: Dict[str, Any]) -> List[Beat]:
    """
    Every beat of a tempo map as ``(time, bar, beat)``.

    Args:
        obj (dict): An analysis (format 5 or 4, or a ``segment()`` result) or
            its ``grid``.

    Returns:
        List[Tuple[float, int, int]]: One tuple per beat, in order; times in
            seconds, rounded to 3 decimals. Lead-in beats have bar 0 or below.
            An analysis without a grid (format 2 and 3, or a track with no
            beats) gives ``[]``: ``beats_of`` reads its lists.
    """
    if not isinstance(obj, dict):
        return []
    if _is_grid(obj):
        return expand_grid(obj)
    seg = _analysis(obj)
    grid = seg.get("grid")
    if not isinstance(grid, dict):
        return []
    return expand_grid(grid, beats_per_bar(seg))


def _bars(beats: List[Beat]) -> List[float]:
    return [t for t, bar, beat in beats if beat == 1 and bar >= 1]


def beats_of(obj: Dict[str, Any]) -> Tuple[List[float], List[float]]:
    """
    (beat times, bar times) of an analysis of any format.

    Args:
        obj (dict): A format 5 analysis (as ``audial.segment()`` returns it
            under ``analysis``, or the whole ``segment()`` result), an older
            analysis file (format 4, with or without its ``audio_segmentation``
            wrapper; formats 2 and 3 list ``beat_times`` and ``bar_times``), or
            a ``grid``.

    Returns:
        Tuple[List[float], List[float]]: The beat times and the bar times.
    """
    if not isinstance(obj, dict):
        return [], []
    if _is_grid(obj):
        beats = expand_grid(obj)
        return [t for t, _, _ in beats], _bars(beats)
    seg = _analysis(obj)
    if isinstance(seg.get("grid"), dict):
        beats = expand_grid(seg["grid"], beats_per_bar(seg))
        return [t for t, _, _ in beats], _bars(beats)
    return list(seg.get("beat_times") or []), list(seg.get("bar_times") or [])


def beat_times(obj: Dict[str, Any]) -> List[float]:
    """Every beat time, in seconds (``len(...) == grid["beat_count"]``), of an analysis or a grid."""
    return beats_of(obj)[0]


def bar_times(obj: Dict[str, Any]) -> List[float]:
    """Start time of every bar from bar 1 on (``len(...) == grid["bar_count"]``), of an analysis or a grid."""
    return beats_of(obj)[1]
