"""
Unit tests for audial.grid: the tempo map of an analysis (format 4).

The rule is shared with every other reader of Audial analysis files; the
vectors in fixtures/grid_vectors.json are the shared check. Nothing here
touches the network.
"""

import json
import os

import pytest

from audial import grid

VECTORS = os.path.join(os.path.dirname(__file__), "fixtures", "grid_vectors.json")


def _cases():
    with open(VECTORS) as f:
        return json.load(f)["cases"]


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["name"])
def test_grid_vectors(case):
    """expand() reproduces every stored expansion exactly (3 decimals)."""
    got = [list(beat) for beat in grid.expand(case["grid"])]
    assert got == case["expected"]


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


def test_beats_of_reads_every_format():
    v3 = {"format_version": 3, "beat_times": [0.1, 0.6], "bar_times": [0.1]}
    assert grid.beats_of(v3) == ([0.1, 0.6], [0.1])

    v4 = {"format_version": 4, "grid": {"beats_per_bar": 4, "pieces": [
        {"start": 0.0, "bpm": 120.0, "bar": 1, "beat": 1, "count": 8}]}}
    assert grid.beats_of(v4) == ([0.5 * k for k in range(8)], [0.0, 2.0])

    assert grid.beats_of({}) == ([], [])


def test_beats_of_accepts_the_merged_view_wrapper():
    view = {"audio_segmentation": {"grid": {"beats_per_bar": 4, "pieces": [
        {"start": 1.0, "bpm": 60.0, "bar": 1, "beat": 1, "count": 5}]}}}
    assert grid.beats_of(view) == ([1.0, 2.0, 3.0, 4.0, 5.0], [1.0, 5.0])


def test_empty_grid():
    assert grid.expand({}) == []
    assert grid.bar_times({"pieces": []}) == []
