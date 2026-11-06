"""
The tempo map ("grid") of an Audial analysis.

Beats and bars aren't listed one by one. ``grid`` describes them: where each
constant-tempo piece starts, its BPM, and its bar and beat. Every beat time is
``start + k * 60 / bpm``. Most tracks have one piece::

    "grid": {
      "beats_per_bar": 4, "tolerance_ms": 25, "max_error_ms": 9.2,
      "beat_count": 841, "bar_count": 208,
      "pieces": [{"start": 0.195, "bpm": 129.0, "bar": -2, "beat": 1, "count": 841}]
    }

The whole rule::

    for piece in pieces:
        for k in 0 .. piece.count - 1:
            beat k is at piece.start + k * 60 / piece.bpm, labelled (bar, beat)
            then the beat moves on by one; after beat beats_per_bar comes beat 1 of the next bar

- Beat times are all the pieces' beats in order, rounded to 3 decimals.
- Bar times are the times of the beats with ``beat == 1`` and ``bar >= 1``.
- Bars 0 and below are the lead-in before bar 1, counted back (..., -1, 0).
- ``beat_count`` and ``bar_count`` are the totals, so nothing needs expanding
  just to count.

Analyses made before the tempo map (format 2 and 3) list ``beat_times`` and
``bar_times`` instead; ``beats_of`` reads either. ``audial.segment()`` adds
``beat_times`` and ``bar_times`` to its result for you (``expand_beats=True``).

Standard library only.
"""

from typing import Any, Dict, List, Tuple

__all__ = [
    "GRID_TOLERANCE_MS",
    "expand",
    "expand_grid",
    "beat_times",
    "bar_times",
    "beats_of",
    "next_label",
]

GRID_TOLERANCE_MS = 25.0   # every expanded beat is within this many ms of the detected beat

Beat = Tuple[float, int, int]


def next_label(label: Tuple[int, int], beats_per_bar: int = 4) -> Tuple[int, int]:
    """The (bar, beat) after ``label``: beat ``beats_per_bar`` is followed by beat 1 of the next bar."""
    bar, beat = label
    return (bar + 1, 1) if beat >= beats_per_bar else (bar, beat + 1)


def expand_grid(grid: Dict[str, Any]) -> List[Beat]:
    """[(time, bar, beat), ...] for every beat of the grid, times rounded to 0.001 s."""
    bpb = int(grid.get("beats_per_bar", 4))
    out: List[Beat] = []
    for piece in grid.get("pieces", []):
        period = 60.0 / float(piece["bpm"])
        label = (int(piece["bar"]), int(piece["beat"]))
        start = float(piece["start"])
        for k in range(int(piece["count"])):
            out.append((round(start + k * period, 3), label[0], label[1]))
            label = next_label(label, bpb)
    return out


def expand(grid: Dict[str, Any]) -> List[Beat]:
    """
    Every beat of a tempo map as ``(time, bar, beat)``.

    Args:
        grid (dict): The ``grid`` object of an analysis.

    Returns:
        List[Tuple[float, int, int]]: One tuple per beat, in order; times in
            seconds, rounded to 3 decimals. Lead-in beats have bar 0 or below.
    """
    return expand_grid(grid)


def beat_times(grid: Dict[str, Any]) -> List[float]:
    """Every beat time of a tempo map, in seconds (``len(...) == grid["beat_count"]``)."""
    return [t for t, _, _ in expand_grid(grid)]


def bar_times(grid: Dict[str, Any]) -> List[float]:
    """Start time of every bar from bar 1 on (``len(...) == grid["bar_count"]``)."""
    return [t for t, bar, beat in expand_grid(grid) if beat == 1 and bar >= 1]


def beats_of(seg: Dict[str, Any]) -> Tuple[List[float], List[float]]:
    """
    (beat times, bar times) of an analysis of any format.

    Args:
        seg (dict): The ``audio_segmentation`` object (or the whole
            ``{"audio_segmentation": ...}`` document). Format 4 carries
            ``grid``; formats 2 and 3 list ``beat_times`` and ``bar_times``.

    Returns:
        Tuple[List[float], List[float]]: The beat times and the bar times.
    """
    if isinstance(seg.get("audio_segmentation"), dict):
        seg = seg["audio_segmentation"]
    if seg.get("grid"):
        beats = expand_grid(seg["grid"])
        return [t for t, _, _ in beats], [t for t, bar, beat in beats if beat == 1 and bar >= 1]
    return list(seg.get("beat_times") or []), list(seg.get("bar_times") or [])
