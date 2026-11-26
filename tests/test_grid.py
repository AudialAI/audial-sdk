"""
Unit tests for audial.grid: the tempo map of an analysis (format 5, and the
older formats 4, 3 and 2).

The rule is shared with every other reader of Audial analysis files; the
vectors in fixtures/grid_vectors.json are the shared check. Nothing here
touches the network.
"""

import json
import os

import pytest

from audial import grid

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
VECTORS = os.path.join(FIXTURES, "grid_vectors.json")


def _cases():
    with open(VECTORS) as f:
        return json.load(f)["cases"]


def _format5():
    with open(os.path.join(FIXTURES, "analysis_format5.json")) as f:
        return json.load(f)["view"]


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["name"])
def test_grid_vectors(case):
    """expand() reproduces every stored expansion exactly (3 decimals)."""
    got = [list(beat) for beat in grid.expand(case["grid"])]
    assert got == case["expected"]


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["name"])
def test_grid_vectors_without_beats_per_bar(case):
    """A format 5 grid has no beats_per_bar: with time_signature "4/4" it expands the same."""
    g = {k: v for k, v in case["grid"].items() if k not in ("beats_per_bar", "tolerance_ms")}
    analysis = {"format_version": 5, "time_signature": "4/4", "grid": g}
    assert [list(beat) for beat in grid.expand(analysis)] == case["expected"]
    assert [list(beat) for beat in grid.expand(g)] == case["expected"]   # 4 by default


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["name"])
def test_counts_match_the_grid_header(case):
    """beat_count and bar_count in the file agree with the expansion."""
    g = case["grid"]
    assert len(grid.beat_times(g)) == g["beat_count"]
    assert len(grid.bar_times(g)) == g["bar_count"]


def test_expand_grid_is_the_same_rule_as_expand():
    case = _cases()[0]
    assert grid.expand_grid(case["grid"]) == grid.expand(case["grid"])


def test_bar_times_are_beat_ones_from_bar_one_on():
    # Lead-in from bar -1 beat 2: bars -1 and 0 are not bars of the song.
    g = {"beats_per_bar": 4, "pieces": [{"start": 0.3, "bpm": 125.0, "bar": -1, "beat": 2, "count": 12}]}
    assert grid.bar_times(g) == [3.66, 5.58]
    beats = grid.expand(g)
    assert beats[3] == (1.74, 0, 1)   # bar 0, beat 1: still lead-in


def test_format5_analysis_reads_its_grid_and_time_signature():
    """The real format 5 view: four pieces, 841 beats, 208 bars, bar 1 next to bar1."""
    view = _format5()
    beats, bars = grid.beats_of(view)
    assert len(beats) == view["grid"]["beat_count"] == 841
    assert len(bars) == view["grid"]["bar_count"] == 208
    assert abs(bars[0] - view["bar1"]) < 0.025
    assert grid.beat_times(view) == beats
    assert grid.bar_times(view) == bars
    assert grid.beats_per_bar(view) == 4
    # Every section starts on its bar (within the grid's tolerance).
    for section in view["sections"]:
        if section["start_bar"] >= 1:
            assert abs(bars[section["start_bar"] - 1] - section["start"]) <= grid.GRID_TOLERANCE_MS / 1000


def test_beats_per_bar_come_from_the_time_signature():
    g = {"beat_count": 7, "bar_count": 2,
         "pieces": [{"start": 0.0, "bpm": 60.0, "bar": 1, "beat": 1, "count": 7}]}
    waltz = {"format_version": 5, "time_signature": "3/4", "grid": g}
    assert grid.beats_per_bar(waltz) == 3
    assert grid.expand(waltz) == [(0.0, 1, 1), (1.0, 1, 2), (2.0, 1, 3), (3.0, 2, 1),
                                  (4.0, 2, 2), (5.0, 2, 3), (6.0, 3, 1)]
    assert grid.bar_times(waltz) == [0.0, 3.0, 6.0]
    # Without a time signature (or an unreadable one): 4.
    assert grid.beats_per_bar({"grid": g}) == 4
    assert grid.beats_per_bar({"grid": g, "time_signature": "odd"}) == 4
    assert grid.bar_times({"grid": g}) == [0.0, 4.0]
    # A format 4 grid's own beats_per_bar still wins.
    assert grid.beats_per_bar({"time_signature": "3/4", "grid": dict(g, beats_per_bar=4)}) == 4


def test_beats_of_reads_every_format():
    v3 = {"format_version": 3, "beat_times": [0.1, 0.6], "bar_times": [0.1]}
    assert grid.beats_of(v3) == ([0.1, 0.6], [0.1])
    assert grid.beat_times(v3) == [0.1, 0.6] and grid.bar_times(v3) == [0.1]

    v4 = {"format_version": 4, "grid": {"beats_per_bar": 4, "pieces": [
        {"start": 0.0, "bpm": 120.0, "bar": 1, "beat": 1, "count": 8}]}}
    assert grid.beats_of(v4) == ([0.5 * k for k in range(8)], [0.0, 2.0])

    v5 = {"format_version": 5, "time_signature": "4/4", "grid": {"pieces": [
        {"start": 0.0, "bpm": 120.0, "bar": 1, "beat": 1, "count": 8}]}}
    assert grid.beats_of(v5) == ([0.5 * k for k in range(8)], [0.0, 2.0])

    # A track with no beats: grid is null.
    assert grid.beats_of({"format_version": 5, "grid": None}) == ([], [])
    assert grid.expand({"format_version": 5, "grid": None}) == []
    assert grid.beats_of({}) == ([], [])


def test_beats_of_accepts_the_format_4_wrapper():
    view = {"audio_segmentation": {"grid": {"beats_per_bar": 4, "pieces": [
        {"start": 1.0, "bpm": 60.0, "bar": 1, "beat": 1, "count": 5}]}}}
    assert grid.beats_of(view) == ([1.0, 2.0, 3.0, 4.0, 5.0], [1.0, 5.0])


def test_every_function_accepts_a_segment_result():
    view = _format5()
    result = {"analysis_id": "exe-ana", "analysis": view, "files": {}}
    assert grid.beats_of(result) == grid.beats_of(view)
    assert grid.beat_times(result) == grid.beat_times(view)
    assert grid.bar_times(result) == grid.bar_times(view)
    assert grid.expand(result) == grid.expand(view)


def test_a_format3_grid_of_one_beat_pieces():
    """A format 3 file converted to format 5: one piece per beat, labels counted from bar_times."""
    g = {"beat_count": 5, "bar_count": 2, "max_error_ms": 0, "pieces": [
        {"start": 0.5, "bpm": 120.0, "bar": 0, "beat": 4, "count": 1},
        {"start": 1.0, "bpm": 120.0, "bar": 1, "beat": 1, "count": 1},
        {"start": 1.5, "bpm": 120.0, "bar": 1, "beat": 2, "count": 1},
        {"start": 2.0, "bpm": 120.0, "bar": 1, "beat": 3, "count": 1},
        {"start": 3.0, "bpm": 120.0, "bar": 2, "beat": 1, "count": 1},
    ]}
    assert grid.beats_of({"format_version": 5, "time_signature": "4/4", "grid": g}) == (
        [0.5, 1.0, 1.5, 2.0, 3.0], [1.0, 3.0])


def test_empty_grid():
    assert grid.expand({}) == []
    assert grid.bar_times({"pieces": []}) == []
