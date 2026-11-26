"""
Unit tests for the analysis and its add-ons (SDK 2.0, analysis format 5):
segment(), the audio_features / tags / lyrics add-ons,
generate_samples(analysis_id=...) and the CLI subcommands that wrap them.

The HTTP layer is mocked at requests.Session.get/post with a small URL
router, and the base URL points at a host that does not exist, so no request
can leave the process. Sleeping is replaced by a fake clock.
"""

import importlib
import json
import os
import subprocess
import sys
import warnings
from unittest import mock

import pytest
import requests

import audial
from audial import grid
from audial.api.exceptions import AudialAPIError, AudialError
from audial.functions import _addon
from audial.functions.audio_features import audio_features
from audial.functions.lyrics import lyrics as lyrics_function
from audial.functions.samples import generate_samples
from audial.functions.segment import segment
from audial.functions.tags import tags

from conftest import FakeResponse

# `audial.functions.segment` the attribute is the function; this is the module.
segment_module = importlib.import_module("audial.functions.segment")

BASE = "https://api.test.invalid/api"
USER = "test-user-id"


# ---------------------------------------------------------------------------
# A fake API and a fake clock
# ---------------------------------------------------------------------------

class FakeAPI:
    """Routes (method, path) to queued responses; the last one repeats."""

    def __init__(self):
        self.routes = {}
        self.calls = []

    def on(self, method, path, *responses):
        self.routes[(method, path)] = list(responses)

    def handle(self, method, url, **kwargs):
        assert url.startswith(BASE), f"request to an unexpected host: {url}"
        path = url[len(BASE):]
        self.calls.append((method, path, kwargs))
        queue = self.routes.get((method, path))
        if not queue:
            raise AssertionError(f"unexpected request {method} {path}")
        response = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(response, Exception):
            raise response
        return response

    def requests_to(self, method, path):
        return [kwargs for m, p, kwargs in self.calls if m == method and p == path]


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("AUDIAL_API_BASE_URL", BASE)
    fake = FakeAPI()
    monkeypatch.setattr(requests.Session, "get", lambda self, url, **kw: fake.handle("GET", url, **kw))
    monkeypatch.setattr(requests.Session, "post", lambda self, url, **kw: fake.handle("POST", url, **kw))
    monkeypatch.setattr(requests.Session, "put", lambda self, url, **kw: fake.handle("PUT", url, **kw))
    return fake


@pytest.fixture
def clock(monkeypatch):
    fake = Clock()
    monkeypatch.setattr(_addon, "time", fake)
    monkeypatch.setattr(segment_module, "time", fake)
    return fake


# ---------------------------------------------------------------------------
# Fixtures: an analysis record and its merged view (format 5)
# ---------------------------------------------------------------------------

GRID = {
    "beat_count": 12,
    "bar_count": 2,
    "max_error_ms": 0.0,
    "pieces": [{"start": 0.3, "bpm": 125.0, "bar": -1, "beat": 2, "count": 12}],
}


def _view(sections=None, **blocks):
    """A format 5 merged view; `blocks` are its add-on blocks (features, tags, description, lyrics)."""
    view = {
        "format_version": 5,
        "duration": 6.0,
        "bpm": 125.0,
        "tempo_mode": "constant",
        "time_signature": "4/4",
        "key": "Amin",
        "camelot": "8A",
        "structure": "dance",
        "bar1": 3.66,
        "grid": GRID,
        "lead_in": None,
        "sections": sections or [
            {"label": "INTRO", "start": 0.3, "end": 3.66, "start_bar": -1, "bars": 2, "fills": []},
            {"label": "UP", "start": 3.66, "end": 6.0, "start_bar": 1, "bars": 2, "fills": [5.5]},
        ],
    }
    view.update(blocks)
    return view


with open(os.path.join(os.path.dirname(__file__), "fixtures", "analysis_format5.json")) as _f:
    FULL_VIEW = json.load(_f)["view"]   # a real analysis with every add-on, lyrics made up


def _analysis(state="completed", stems="running", **addons):
    record = {
        "exeId": "exe-ana",
        "exeType": "segmentation",
        "state": state,
        "original": {"filename": "track.wav", "url": "https://storage.example/track.wav"},
        "stems": {"state": stems, "exeId": "exe-stem"},
    }
    if addons:
        record["addons"] = addons
    return record


def _ok(body):
    return FakeResponse(200, body)


def _refusal(code, state=None, error="The track is still being prepared. Try again in a moment."):
    body = {"error": error, "code": code}
    if state is not None:
        body["state"] = state
    return FakeResponse(409, body)


EXE = f"/db/{USER}/execution/exe-ana"
VIEW = f"{EXE}/analysis"


# ---------------------------------------------------------------------------
# segment(): the fast analysis
# ---------------------------------------------------------------------------

def test_segment_runs_one_analysis_call_with_the_mix(api, clock, audio_file, tmp_path):
    api.on("POST", "/functions/run/segmentation",
           _ok({"exeId": "exe-ana", "state": "processing", "exeType": "segmentation"}))
    api.on("GET", EXE, _ok(_analysis(state="processing")), _ok(_analysis()))
    api.on("GET", VIEW, _ok(_view()))
    seen = []

    with warnings.catch_warnings():
        warnings.simplefilter("error")   # 2.0 says nothing about beat lists
        result = segment(audio_file, genre="Tech House", edm=True, results_folder=str(tmp_path),
                         on_progress=lambda s: seen.append(s["state"]))

    # One run on the mix: the file goes up with the request, nothing else is started.
    [post] = api.requests_to("POST", "/functions/run/segmentation")
    assert post["files"]["original"][0] == os.path.basename(audio_file)
    fields = dict(post["data"])
    assert fields["userId"] == USER
    assert json.loads(fields["segmentationParameters"]) == {"genre": "Tech House", "edm": True}
    assert "Content-Type" not in post["headers"]
    assert not [c for c in api.calls if c[1].startswith("/pipelines")]

    # The result is the merged view as the API served it (format 5), under `analysis`.
    assert result["analysis_id"] == "exe-ana"
    assert result["analysis"] == _view()
    assert result["analysis"]["format_version"] == 5
    assert "audio_segmentation" not in result and "segmentation" not in result
    assert "beat_times" not in result["analysis"] and "bar_times" not in result["analysis"]
    assert result["execution"]["state"] == "completed"
    assert seen == ["processing", "processing", "completed"]

    # The saved analysis.json is the format 5 object itself, with no wrapper.
    saved = result["files"]["files"]["analysis.json"]
    with open(saved) as f:
        assert json.load(f) == _view()
    assert result["files"]["folder"].endswith("_segmentation")


def test_segment_returns_the_full_format5_view(api, clock, audio_file, tmp_path):
    api.on("POST", "/functions/run/segmentation", _ok(_analysis()))
    api.on("GET", EXE, _ok(_analysis()))
    api.on("GET", VIEW, _ok(FULL_VIEW))

    result = segment(audio_file, results_folder=str(tmp_path))

    analysis = result["analysis"]
    assert analysis == FULL_VIEW
    assert (analysis["key"], analysis["camelot"], analysis["structure"]) == ("Bmin", "10A", "dance")
    assert analysis["sections"][0]["loudness_lufs"] == -10.42
    for gone in ("song_analysis", "segment_analysis", "phrases", "first_vocal_beat_time",
                 "filtered_segments", "segment_classifications", "mood", "mode", "song_start"):
        assert gone not in analysis
    assert grid.bar_times(result)[:1] == [5.753]


def test_segment_expand_beats_is_opt_in(api, clock, audio_file, tmp_path):
    """expand_beats=True adds beat_times and bar_times from grid; the saved file stays format 5."""
    api.on("POST", "/functions/run/segmentation", _ok(_analysis()))
    api.on("GET", EXE, _ok(_analysis()))
    api.on("GET", VIEW, _ok(_view()))

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = segment(audio_file, results_folder=str(tmp_path), expand_beats=True)
    data = result["analysis"]
    beats, bars = grid.beats_of({"time_signature": "4/4", "grid": GRID})
    assert data["grid"] == GRID
    assert data["beat_times"] == beats
    assert data["bar_times"] == bars == [3.66, 5.58]
    assert len(data["beat_times"]) == GRID["beat_count"]
    with open(result["files"]["files"]["analysis.json"]) as f:
        assert "beat_times" not in json.load(f)


def test_segment_takes_off_an_older_api_wrapper(api, clock, audio_file, tmp_path):
    """An API from before format 5 wraps the view in audio_segmentation: the SDK takes it off."""
    api.on("POST", "/functions/run/segmentation", _ok(_analysis()))
    api.on("GET", EXE, _ok(_analysis()))
    api.on("GET", VIEW, _ok({"audio_segmentation": _view()}))

    result = segment(audio_file, results_folder=str(tmp_path))
    assert result["analysis"] == _view()


def test_segment_accepts_the_old_parameters_with_a_deprecation_warning(api, clock, audio_file, tmp_path):
    api.on("POST", "/functions/run/segmentation", _ok(_analysis()))
    api.on("GET", EXE, _ok(_analysis()))
    api.on("GET", VIEW, _ok(_view()))

    with pytest.warns(DeprecationWarning, match="components"):
        segment(audio_file, components=["bass", "beat", "melody", "vocal"],
                analysis_type="select_features", results_folder=str(tmp_path), expand_beats=False)

    # Nothing of them goes out: the request carries only the mix and the user.
    [post] = api.requests_to("POST", "/functions/run/segmentation")
    assert dict(post["data"]) == {"userId": USER}


def test_segment_raises_when_the_analysis_fails(api, clock, audio_file, tmp_path):
    api.on("POST", "/functions/run/segmentation", _ok(_analysis(state="processing")))
    api.on("GET", EXE, _ok(dict(_analysis(state="failed"), error="The analysis produced no result")))

    with pytest.raises(AudialError) as excinfo:
        segment(audio_file, results_folder=str(tmp_path))
    assert "The analysis produced no result" in str(excinfo.value)


def test_segment_refuses_before_calling_the_api(api, audio_file, tmp_path):
    with pytest.raises(AudialError):
        segment(audio_file, genre="Polka", results_folder=str(tmp_path))
    with pytest.raises(AudialError):
        segment(audio_file, features=["kazoo"], results_folder=str(tmp_path))
    with pytest.raises(AudialError):
        segment(str(tmp_path / "missing.wav"), results_folder=str(tmp_path))
    assert api.calls == []


# ---------------------------------------------------------------------------
# segment(features=...): the segmentation pipeline (the API adds the add-ons)
# ---------------------------------------------------------------------------

def _pipeline_done(warnings_=None):
    outputs = {
        "segmentation": ["https://storage.example/segmentation/pruned_audio_segmentation.json"],
        "analysis": f"https://api.audialmusic.ai/api/db/{USER}/execution/exe-ana/analysis",
    }
    if warnings_:
        outputs["warnings"] = warnings_
    return {
        "pipelineId": "pl-2",
        "pipeline": "segmentation",
        "state": "completed",
        "steps": [
            {"name": "segmentation", "state": "completed", "exeId": "exe-ana", "durationMs": 28000},
            {"name": "add-ons", "state": "completed", "exeId": "exe-ana", "durationMs": 61000},
        ],
        "outputs": outputs,
    }


def test_segment_with_features_runs_the_pipeline_and_reads_the_merged_view(api, clock, audio_file, tmp_path):
    api.on("GET", VIEW, _ok(_view(features={"energy": 0.62}, tags={"genres": ["House"]})))

    with mock.patch("audial.pipelines.run",
                    return_value=_pipeline_done(["Lyrics could not be made: no vocals"])) as run:
        result = segment(audio_file, features=["energy", "tags", "key"], genre="House",
                         results_folder=str(tmp_path), expand_beats=False)

    assert run.call_args.args[:2] == ("segmentation", audio_file)
    options = run.call_args.kwargs["options"]
    assert options["genre"] == "House"
    # "key" comes with the audio features; the API's list doesn't have it.
    assert options["featuresToExtract"] == ["energy", "tags"]
    assert "components" not in options

    # The merged view is read from the API (never from outputs.analysis's host).
    assert api.requests_to("GET", VIEW)
    assert result["analysis_id"] == "exe-ana"
    assert result["analysis"]["features"]["energy"] == 0.62
    assert result["analysis"]["tags"]["genres"] == ["House"]
    assert result["execution"]["pipelineId"] == "pl-2"
    assert result["warnings"] == ["Lyrics could not be made: no vocals"]


def test_segment_with_features_and_edm_runs_the_add_ons_itself(api, clock, audio_file, tmp_path):
    """The pipeline has no edm option: the fast analysis runs with it, then each add-on."""
    api.on("POST", "/functions/run/segmentation", _ok(_analysis()))
    api.on("POST", "/functions/run/audio-features",
           _ok({"exeId": "exe-feat", "analysisExeId": "exe-ana", "addon": "features", "state": "completed"}))
    api.on("POST", "/functions/run/lyrics",
           _refusal("ADDON_UNAVAILABLE", error="This analysis has no stems to build this from."))
    api.on("GET", EXE, _ok(_analysis(features={"state": "completed", "exeId": "exe-feat", "startedAt": 1,
                                               "result": FEATURES})))
    api.on("GET", VIEW, _ok(_view(features={"energy": 0.62})))

    with mock.patch("audial.pipelines.run") as pipeline:
        result = segment(audio_file, edm=False, features=["energy", "mode", "lyrics"],
                         results_folder=str(tmp_path), expand_beats=False)

    pipeline.assert_not_called()
    [post] = api.requests_to("POST", "/functions/run/segmentation")
    assert json.loads(dict(post["data"])["segmentationParameters"]) == {"edm": False}
    assert len(api.requests_to("POST", "/functions/run/audio-features")) == 1   # once for both
    assert result["analysis"]["features"]["energy"] == 0.62
    assert result["warnings"] == [
        "Lyrics could not be made: This result can't be added to this analysis. "
        "This analysis has no stems to build this from. (ADDON_UNAVAILABLE)"
    ]


def test_segment_with_only_key_still_asks_for_the_audio_features(api, clock, audio_file, tmp_path):
    api.on("GET", VIEW, _ok(_view()))
    with mock.patch("audial.pipelines.run", return_value=_pipeline_done()) as run:
        segment(audio_file, features=["key"], results_folder=str(tmp_path), expand_beats=False)
    assert run.call_args.kwargs["options"]["featuresToExtract"] == ["mode"]


# ---------------------------------------------------------------------------
# Add-ons: audio_features, tags, lyrics
# ---------------------------------------------------------------------------

# What each add-on's run stored on the analysis record (its own worker shape). Only its
# `warnings` reach the caller; the values come from the merged view (format 5).
FEATURES = {
    "features_version": 1,
    "song": {"key": "A min", "loudness": -7.1, "energy": 0.62, "danceability": 0.71, "mode": "aeolian"},
    "sections": [{"index": 0, "label": "INTRO", "energy": 0.4}, {"index": 1, "label": "UP", "energy": 0.8}],
    "warnings": [],
}

STORED_TAGS = {
    "tags_version": 2,
    "genre": ["Electronic---UK Garage"],
    "song_tags": {"full": {"moods": ["dark"]}},
    "source": {"title": "A title", "artist": "An artist"},
    "warnings": ["The description could not be made."],
}

STORED_LYRICS = {"lyrics": "hello there", "is_instrumental": False, "first_vocal_beat_time": 12.34}

# The view's blocks once the add-ons have run.
FEATURES_VIEW = {
    "features": {"energy": 0.62, "danceability": 0.71, "loudness_lufs": -7.1,
                 "mode": "Natural Minor", "mode_confidence": 0.8, "tatum": "1/16"},
    "sections": [
        {"label": "INTRO", "start": 0.3, "end": 3.66, "start_bar": -1, "bars": 2, "fills": [],
         "energy": 0.4, "danceability": 0.5, "loudness_lufs": -12.0},
        {"label": "UP", "start": 3.66, "end": 6.0, "start_bar": 1, "bars": 2, "fills": [5.5],
         "energy": 0.8, "danceability": 0.75, "loudness_lufs": None},
    ],
}

FEATURES_RESULT = {
    "key": "Amin",
    "camelot": "8A",
    "features": FEATURES_VIEW["features"],
    "sections": [
        {"label": "INTRO", "start": 0.3, "end": 3.66, "energy": 0.4, "danceability": 0.5, "loudness_lufs": -12.0},
        {"label": "UP", "start": 3.66, "end": 6.0, "energy": 0.8, "danceability": 0.75, "loudness_lufs": None},
    ],
    "warnings": [],
}

TAGS_VIEW = {
    "tags": {
        "genres": ["UK Garage", "Speed Garage"],
        "instruments": ["drum machine"],
        "moods": ["driving", "groovy"],
        "stems": {
            "drums": {"instruments": ["kick"], "moods": ["driving"]},
            "bass": {"instruments": ["sub bass"], "moods": ["deep"]},
            "melody": {"instruments": ["electric piano"], "moods": ["warm"]},
            "vocals": {"silent": True},
        },
    },
    "description": "A driving UK garage cut built on a swung two-step groove.",
}

TAGS = dict(TAGS_VIEW["tags"], description=TAGS_VIEW["description"], warnings=[])

LYRICS_VIEW = {
    "lyrics": {
        "vocal_start": 12.34,
        # The database keeps arrays as objects when it feels like it; the SDK hands back lists.
        "lines": {"0": {"start": 12.34, "end": 13.1,
                        "words": {"0": ["hello", 12.34, 12.71], "1": ["there", 12.8, 13.1]}}},
    },
}


def test_addon_waits_for_stems(api, clock, tmp_path):
    """409 STEMS_NOT_READY, then 200: the result comes back after a retry."""
    api.on("POST", "/functions/run/audio-tags",
           _refusal("STEMS_NOT_READY", "running"),
           _ok({"exeId": "exe-tags", "analysisExeId": "exe-ana", "addon": "tags", "state": "queued"}))
    api.on("GET", EXE,
           _ok(_analysis(stems="completed", tags={"state": "running", "exeId": "exe-tags", "startedAt": 1})),
           _ok(_analysis(stems="completed", tags={"state": "completed", "exeId": "exe-tags", "startedAt": 1,
                                                  "result": STORED_TAGS})))
    api.on("GET", f"/db/{USER}/execution/exe-tags", _ok({"exeId": "exe-tags", "state": "processing"}))
    api.on("GET", VIEW, _ok(_view(**TAGS_VIEW)))

    result = tags("exe-ana", results_folder=str(tmp_path), poll_interval=5)

    starts = api.requests_to("POST", "/functions/run/audio-tags")
    assert len(starts) == 2
    assert starts[0]["json"] == {"userId": USER, "analysisExeId": "exe-ana"}
    # The view's tags block and description come back unchanged, plus the run's warnings.
    assert result == dict(TAGS, warnings=["The description could not be made."])
    assert list(result) == ["genres", "instruments", "moods", "stems", "description", "warnings"]
    assert "source" not in result and "tags_version" not in result and "song_tags" not in result
    assert json.load(open(tmp_path / "exe-ana_analysis" / "tags.json")) == result
    assert clock.sleeps and clock.now < 600


def test_addon_gives_up_at_wait_s(api, clock, tmp_path):
    api.on("POST", "/functions/run/lyrics", _refusal("STEMS_NOT_READY", "running"))

    with pytest.raises(AudialAPIError) as excinfo:
        lyrics_function("exe-ana", wait_s=60, poll_interval=5, results_folder=str(tmp_path))

    assert "STEMS_NOT_READY" in str(excinfo.value)
    assert excinfo.value.code == "STEMS_NOT_READY"
    assert excinfo.value.status_code == 409
    assert "This track is still being prepared. Try again in a minute." in str(excinfo.value)
    assert 60 <= clock.now <= 65
    assert len(api.requests_to("POST", "/functions/run/lyrics")) >= 2


def test_addon_restarts_a_failed_stem_split_once(api, clock, tmp_path):
    api.on("POST", "/functions/run/lyrics",
           _refusal("STEMS_NOT_READY", "failed"),
           _ok({"exeId": "exe-lyr", "analysisExeId": "exe-ana", "addon": "lyrics", "state": "queued"}))
    api.on("POST", "/functions/run/stem-splitter",
           _ok({"exeId": "exe-stem2", "analysisExeId": "exe-ana", "addon": "stems", "state": "running"}))
    api.on("GET", EXE, _ok(_analysis(stems="completed", lyrics={"state": "completed", "exeId": "exe-lyr",
                                                                "startedAt": 1, "result": STORED_LYRICS})))
    api.on("GET", VIEW, _ok(_view(**LYRICS_VIEW)))

    lyrics_function("exe-ana", results_folder=str(tmp_path))

    [retry] = api.requests_to("POST", "/functions/run/stem-splitter")
    assert retry["json"] == {"userId": USER, "analysisExeId": "exe-ana"}


def test_addon_reports_stems_that_failed_twice(api, clock, tmp_path):
    api.on("POST", "/functions/run/audio-tags", _refusal("STEMS_NOT_READY", "failed"))
    api.on("POST", "/functions/run/stem-splitter",
           _ok({"exeId": "exe-stem2", "analysisExeId": "exe-ana", "addon": "stems", "state": "running"}))

    with pytest.raises(AudialAPIError) as excinfo:
        tags("exe-ana", results_folder=str(tmp_path))
    assert "We couldn't prepare this track." in str(excinfo.value)
    assert excinfo.value.code == "STEMS_NOT_READY"
    assert len(api.requests_to("POST", "/functions/run/stem-splitter")) == 1


def test_addon_unavailable_raises_at_once(api, clock, tmp_path):
    api.on("POST", "/functions/run/audio-tags",
           _refusal("ADDON_UNAVAILABLE", error="This analysis has no stems to build this from."))

    with pytest.raises(AudialAPIError) as excinfo:
        tags("exe-old", results_folder=str(tmp_path))
    assert "This result can't be added to this analysis." in str(excinfo.value)
    assert excinfo.value.code == "ADDON_UNAVAILABLE"
    assert clock.sleeps == []


def test_addon_waits_while_the_analysis_is_still_running(api, clock, tmp_path):
    api.on("POST", "/functions/run/audio-features",
           _refusal("ADDON_UNAVAILABLE", "processing", "The analysis has not finished, so this cannot run yet."),
           _ok({"exeId": "exe-feat", "analysisExeId": "exe-ana", "addon": "features", "state": "queued"}))
    api.on("GET", EXE, _ok(_analysis(features={"state": "completed", "exeId": "exe-feat", "startedAt": 1,
                                               "result": FEATURES})))
    api.on("GET", VIEW, _ok(_view(**FEATURES_VIEW)))

    result = audio_features("exe-ana", results_folder=str(tmp_path))
    assert result["features"]["energy"] == 0.62
    assert len(api.requests_to("POST", "/functions/run/audio-features")) == 2


def test_audio_features_returns_the_views_values_and_saves_them(api, clock, tmp_path):
    api.on("POST", "/functions/run/audio-features",
           _ok({"exeId": "exe-feat", "analysisExeId": "exe-ana", "addon": "features", "state": "completed"}))
    api.on("GET", EXE, _ok(_analysis(features={"state": "completed", "exeId": "exe-feat", "startedAt": 1,
                                               "result": dict(FEATURES, warnings=["Loudness was not measured."])})))
    api.on("GET", VIEW, _ok(_view(**FEATURES_VIEW)))

    result = audio_features("exe-ana", results_folder=str(tmp_path))

    # key and camelot (top level of the view), the features block, each section's numbers.
    assert result == dict(FEATURES_RESULT, warnings=["Loudness was not measured."])
    assert "song" not in result and "features_version" not in result
    with open(os.path.join(str(tmp_path), "exe-ana_analysis", "features.json")) as f:
        assert json.load(f) == result


def test_addon_rerun_is_sent(api, clock, tmp_path):
    api.on("POST", "/functions/run/audio-features",
           _ok({"exeId": "exe-feat2", "analysisExeId": "exe-ana", "addon": "features", "state": "queued"}))
    api.on("GET", EXE, _ok(_analysis(features={"state": "completed", "exeId": "exe-feat2", "startedAt": 1,
                                               "result": FEATURES})))
    api.on("GET", VIEW, _ok(_view(**FEATURES_VIEW)))
    audio_features("exe-ana", rerun=True, results_folder=str(tmp_path))
    [start] = api.requests_to("POST", "/functions/run/audio-features")
    assert start["json"]["rerun"] is True


def test_addon_that_failed_raises_its_error(api, clock, tmp_path):
    api.on("POST", "/functions/run/audio-tags",
           _ok({"exeId": "exe-tags", "analysisExeId": "exe-ana", "addon": "tags", "state": "queued"}))
    api.on("GET", EXE, _ok(_analysis(stems="completed", tags={
        "state": "failed", "exeId": "exe-tags", "startedAt": 1,
        "error": "The tags could not be made for this track."})))
    api.on("GET", f"/db/{USER}/execution/exe-tags", _ok({"exeId": "exe-tags", "state": "failed"}))

    with pytest.raises(AudialAPIError) as excinfo:
        tags("exe-ana", results_folder=str(tmp_path))
    assert "The tags could not be made for this track." in str(excinfo.value)


def test_addon_reports_progress_from_its_run(api, clock, tmp_path):
    warm = {"exeId": "exe-feat", "state": "processing", "warmup": {"state": "cold", "expectedColdStartMs": 60000}}
    api.on("POST", "/functions/run/audio-features",
           _ok({"exeId": "exe-feat", "analysisExeId": "exe-ana", "addon": "features", "state": "queued"}))
    api.on("GET", EXE,
           _ok(_analysis(features={"state": "running", "exeId": "exe-feat", "startedAt": 1})),
           _ok(_analysis(features={"state": "completed", "exeId": "exe-feat", "startedAt": 1, "result": FEATURES})))
    api.on("GET", f"/db/{USER}/execution/exe-feat", _ok(warm))
    api.on("GET", VIEW, _ok(_view(**FEATURES_VIEW)))
    seen = []

    audio_features("exe-ana", results_folder=str(tmp_path), on_progress=seen.append)
    assert seen and seen[0]["warmup"]["state"] == "cold"


def test_lyrics_returns_lines_with_word_times(api, clock, tmp_path):
    api.on("POST", "/functions/run/lyrics",
           _ok({"exeId": "exe-lyr", "analysisExeId": "exe-ana", "addon": "lyrics", "state": "queued"}))
    api.on("GET", EXE, _ok(_analysis(stems="completed", lyrics={"state": "completed", "exeId": "exe-lyr",
                                                                "startedAt": 1, "result": STORED_LYRICS})))
    api.on("GET", VIEW, _ok(_view(**LYRICS_VIEW)))

    # audial.lyrics is both the per-note lyric module and this add-on.
    result = audial.lyrics("exe-ana", results_folder=str(tmp_path))

    # The view's lyrics block: vocal_start and timed lines (sparse lists become lists).
    assert result == {
        "vocal_start": 12.34,
        "lines": [{"start": 12.34, "end": 13.1, "words": [["hello", 12.34, 12.71], ["there", 12.8, 13.1]]}],
        "warnings": [],
    }
    with open(os.path.join(str(tmp_path), "exe-ana_analysis", "lyrics.json")) as f:
        assert json.load(f) == result


def test_lyrics_of_an_instrumental_has_no_lines(api, clock, tmp_path):
    api.on("POST", "/functions/run/lyrics",
           _ok({"exeId": "exe-lyr", "analysisExeId": "exe-ana", "addon": "lyrics", "state": "completed"}))
    api.on("GET", EXE, _ok(_analysis(stems="completed", lyrics={
        "state": "completed", "exeId": "exe-lyr", "startedAt": 1,
        "result": {"is_instrumental": True, "first_vocal_beat_time": None}})))
    # The database drops the empty list: the block arrives as {"vocal_start": null}.
    api.on("GET", VIEW, _ok(_view(lyrics={"vocal_start": None})))

    result = lyrics_function("exe-ana", results_folder=str(tmp_path))
    assert result == {"vocal_start": None, "lines": [], "warnings": []}


def test_lyrics_module_keeps_the_per_note_helpers():
    assert callable(audial.lyrics)
    assert audial.lyrics.parse_per_note_lyrics("a|-") == audial.lyrics.parse_per_note_lyrics("a|+")
    from audial.lyrics import text2vox_tokens   # noqa: F401  (still importable)


def test_addon_follows_the_real_analysis_id(api, clock, tmp_path):
    """A pipeline id from the pipeline era is answered with the analysis's own id."""
    api.on("POST", "/functions/run/audio-features",
           _ok({"exeId": "exe-feat", "analysisExeId": "exe-ana", "addon": "features", "state": "completed"}))
    api.on("GET", EXE, _ok(_analysis(features={"state": "completed", "exeId": "exe-feat", "startedAt": 1,
                                               "result": FEATURES})))
    api.on("GET", VIEW, _ok(_view(**FEATURES_VIEW)))
    audio_features("pl-old", results_folder=str(tmp_path))
    [start] = api.requests_to("POST", "/functions/run/audio-features")
    assert start["json"]["analysisExeId"] == "pl-old"
    assert api.requests_to("GET", EXE)
    assert api.requests_to("GET", VIEW)   # the analysis's own view, not the pipeline id's


def test_addon_needs_an_analysis_id(api):
    with pytest.raises(AudialError):
        tags("")
    assert api.calls == []


# ---------------------------------------------------------------------------
# generate_samples(analysis_id=...)
# ---------------------------------------------------------------------------

def test_generate_samples_on_an_analysis_uses_the_add_on(api, clock, tmp_path):
    files = {"drums": {"kick_01": {"filename": "kick_01.wav", "url": "https://storage.example/kick_01.wav"}},
             "bass_01": {"filename": "bass_01.wav", "url": "https://storage.example/bass_01.wav"}}
    api.on("POST", "/functions/run/sample-pack",
           _refusal("STEMS_NOT_READY", "running"),
           _ok({"exeId": "exe-sp", "analysisExeId": "exe-ana", "addon": "samplePack", "state": "queued"}))
    api.on("GET", EXE, _ok(_analysis(stems="completed", samplePack={
        "state": "completed", "exeId": "exe-sp", "startedAt": 1, "files": files,
        "result": {"components": {"drums": {"status": "ok"}, "bass": {"status": "ok"}}}})))
    downloaded = []

    with mock.patch("audial.pipelines.run") as pipeline, mock.patch(
        "audial.functions.samples.download_file",
        side_effect=lambda url, dest: downloaded.append(url) or dest,
    ):
        result = generate_samples(analysis_id="exe-ana", components=["drums", "bass"],
                                  results_folder=str(tmp_path))

    pipeline.assert_not_called()
    starts = api.requests_to("POST", "/functions/run/sample-pack")
    assert starts[-1]["json"] == {"userId": USER, "analysisExeId": "exe-ana",
                                  "samplePackParameters": {"components": ["drums", "bass"]}}
    assert sorted(downloaded) == ["https://storage.example/bass_01.wav", "https://storage.example/kick_01.wav"]
    assert result["analysis_id"] == "exe-ana"
    assert result["components"]["drums"]["status"] == "ok"
    assert result["files"]["folder"].endswith("exe-sp_samples")
    assert set(result["files"]["files"]) == {"kick_01.wav", "bass_01.wav"}


def test_generate_samples_needs_exactly_one_input(api, audio_file, tmp_path):
    with pytest.raises(AudialError):
        generate_samples(results_folder=str(tmp_path))
    with pytest.raises(AudialError):
        generate_samples(audio_file, analysis_id="exe-ana", results_folder=str(tmp_path))
    assert api.calls == []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli(argv):
    from audial.cli import commands
    with mock.patch.object(sys, "argv", ["audial"] + argv):
        return commands.cli()


def test_cli_features_on_a_file_analyses_it_first(audio_file, capsys):
    with mock.patch("audial.cli.commands.segment",
                    return_value={"analysis_id": "exe-ana", "analysis": {}}) as seg, \
            mock.patch("audial.cli.commands.audio_features", return_value=FEATURES_RESULT) as feat, \
            mock.patch("audial.cli.commands.warmup_reporter", return_value=None):
        _cli(["features", audio_file, "--genre", "House"])

    assert seg.call_args.kwargs["file_path"] == audio_file
    assert seg.call_args.kwargs["genre"] == "House"
    assert "features" not in seg.call_args.kwargs
    assert feat.call_args.args[0] == "exe-ana"
    out = capsys.readouterr().out
    assert "exe-ana" in out and "0.62" in out
    assert "Key: Amin (8A)" in out and "Loudness (LUFS): -7.1" in out and "Mode: Natural Minor" in out


def test_cli_lyrics_on_an_analysis_id_prints_timed_lines(capsys):
    lines = {"vocal_start": 12.34,
             "lines": [{"start": 12.34, "end": 13.1, "words": [["hello", 12.34, 12.71], ["there", 12.8, 13.1]]}],
             "warnings": []}
    with mock.patch("audial.cli.commands.segment") as seg, \
            mock.patch("audial.cli.commands.lyrics_addon", return_value=lines) as run, \
            mock.patch("audial.cli.commands.warmup_reporter", return_value=None):
        _cli(["lyrics", "exe-ana", "--wait-s", "30"])

    seg.assert_not_called()
    assert run.call_args.args[0] == "exe-ana"
    assert run.call_args.kwargs["wait_s"] == 30
    out = capsys.readouterr().out
    assert "0:12.34" in out and "hello there" in out


def test_cli_lyrics_of_an_instrumental(capsys):
    with mock.patch("audial.cli.commands.lyrics_addon",
                    return_value={"vocal_start": None, "lines": [], "warnings": []}), \
            mock.patch("audial.cli.commands.warmup_reporter", return_value=None):
        _cli(["lyrics", "exe-ana"])
    assert "No vocals in this track." in capsys.readouterr().out


def test_cli_tags_json_prints_only_json(capsys):
    with mock.patch("audial.cli.commands.tags", return_value=TAGS), \
            mock.patch("audial.cli.commands.warmup_reporter", return_value=None):
        _cli(["tags", "exe-ana", "--json"])
    assert json.loads(capsys.readouterr().out) == TAGS


def test_cli_tags_prints_the_description_first_and_genres_verbatim(capsys):
    with mock.patch("audial.cli.commands.tags", return_value=dict(TAGS, warnings=[])), \
            mock.patch("audial.cli.commands.warmup_reporter", return_value=None):
        _cli(["tags", "exe-ana"])
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines[0].startswith("Tags")  # the heading, then the description before anything else
    assert lines[1] == TAGS["description"]
    assert "Genres: UK Garage, Speed Garage" in out
    assert out.index(TAGS["description"]) < out.index("Genres:")
    assert "Song moods: driving, groovy" in out
    assert "Song instruments: drum machine" in out
    assert "artist" not in out
    assert "Drums instruments: kick" in out
    assert "Vocals: No vocals in this track." in out
    assert "Vocals moods" not in out


def test_cli_tags_silent_and_empty_parts_print_the_website_lines(capsys):
    """R17: a silent part prints its role's line; a part that is not silent but has no tags prints
    "Nothing to tag in this part."; a part the view does not have (version 1 drums, vocals) prints nothing."""
    stems = {
        "drums": {"silent": True},
        "bass": {"silent": True},
        "melody": {"silent": True},
        "vocals": {"instruments": [], "moods": []},
    }
    with mock.patch("audial.cli.commands.tags",
                    return_value=dict(TAGS, moods=["dark"], instruments=[], stems=stems)), \
            mock.patch("audial.cli.commands.warmup_reporter", return_value=None):
        _cli(["tags", "exe-ana"])
    out = capsys.readouterr().out
    assert "Drums: No drums in this track." in out
    assert "Bass: No bass in this track." in out
    assert "Melody: No melody in this track." in out
    assert "Vocals: Nothing to tag in this part." in out
    assert "Song moods: dark" in out and "Song: Nothing" not in out

    v1 = {"bass": {"instruments": [], "moods": []}, "melody": {"instruments": [], "moods": ["warm"]}}
    with mock.patch("audial.cli.commands.tags", return_value=dict(TAGS, stems=v1)), \
            mock.patch("audial.cli.commands.warmup_reporter", return_value=None):
        _cli(["tags", "exe-ana"])
    out = capsys.readouterr().out
    assert "Bass: Nothing to tag in this part." in out
    assert "Melody moods: warm" in out
    assert "Drums" not in out and "Vocals" not in out


def test_tags_without_description_or_extra_parts(api, clock, tmp_path):
    """Version 1 tags (older records): bass and melody only, no description; they stay as the view has them."""
    api.on("POST", "/functions/run/audio-tags",
           _ok({"exeId": "exe-tags", "analysisExeId": "exe-ana", "addon": "tags", "state": "queued"}))
    api.on("GET", EXE, _ok(_analysis(stems="completed", tags={"state": "completed", "exeId": "exe-tags",
                                                              "startedAt": 1, "result": {"warnings": []}})))
    api.on("GET", f"/db/{USER}/execution/exe-tags", _ok({"exeId": "exe-tags", "state": "processing"}))
    # The database drops empty lists, and keeps some lists as {"0": ...}.
    api.on("GET", VIEW, _ok(_view(tags={"genres": {"0": "House"}, "moods": ["dark"],
                                        "stems": {"bass": {}, "melody": {"moods": ["warm"]}}})))

    result = tags("exe-ana", results_folder=str(tmp_path))

    assert result == {
        "genres": ["House"],
        "instruments": [],
        "moods": ["dark"],
        "stems": {"bass": {"instruments": [], "moods": []},
                  "melody": {"instruments": [], "moods": ["warm"]}},
        "description": "",
        "warnings": [],
    }


def test_cli_segment_runs_the_fast_analysis_by_default(audio_file, capsys):
    with mock.patch("audial.cli.commands.segment", return_value={
        "analysis_id": "exe-ana", "analysis": _view(),
        "files": {"folder": "/tmp/x", "files": {"analysis.json": "/tmp/x/analysis.json"}},
    }) as seg, mock.patch("audial.cli.commands.warmup_reporter", return_value=None):
        _cli(["segment", audio_file])
    assert seg.call_args.kwargs["features"] is None
    out = capsys.readouterr().out
    assert "exe-ana" in out and "INTRO" in out and "audial lyrics exe-ana" in out
    assert "Key: Amin (8A)" in out and "Beats: 12, bars: 2" in out


def test_cli_segment_json_prints_the_result(audio_file, capsys):
    result = {"analysis_id": "exe-ana", "analysis": _view(),
              "files": {"folder": "/tmp/x", "files": {"analysis.json": "/tmp/x/analysis.json"}}}
    with mock.patch("audial.cli.commands.segment", return_value=result), \
            mock.patch("audial.cli.commands.warmup_reporter", return_value=None):
        _cli(["segment", audio_file, "--json"])
    assert json.loads(capsys.readouterr().out) == result


def test_python_m_audial_lists_the_new_subcommands():
    out = subprocess.run([sys.executable, "-m", "audial", "--help"], capture_output=True, text=True,
                         timeout=60, env=dict(os.environ, AUDIAL_API_BASE_URL=BASE))
    assert out.returncode == 0, out.stderr
    for name in ("segment", "features", "tags", "lyrics"):
        assert name in out.stdout


def test_status_names_cover_the_add_ons():
    from audial.api.constants import STATUS_FUNCTIONS
    assert STATUS_FUNCTIONS["audio_features"] == "audio-features"
    assert STATUS_FUNCTIONS["tags"] == "audio-tags"
    assert STATUS_FUNCTIONS["lyrics"] == "lyrics"


def test_version():
    assert audial.__version__ == "2.0.0"


def test_segment_keeps_the_15_positional_order():
    """1.5 callers that pass arguments by position keep working: the new options are keyword-only."""
    import inspect
    from audial.functions.segment import segment as seg
    params = list(inspect.signature(seg).parameters.values())
    assert [p.name for p in params[:9]] == ["file_path", "components", "analysis_type", "features", "genre",
                                            "results_folder", "api_key", "on_progress", "poll_interval"]
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params if p.name in ("edm", "expand_beats", "max_wait"))


def test_segment_expand_beats_defaults_to_false():
    import inspect
    from audial.functions.segment import segment as seg
    assert inspect.signature(seg).parameters["expand_beats"].default is False


# ---------------------------------------------------------------------------
# The add-on blocks, read from a format 5 view
# ---------------------------------------------------------------------------

def test_blocks_of_the_full_format5_view():
    features = _addon.features_block(FULL_VIEW)
    assert features["key"] == "Bmin" and features["camelot"] == "10A"
    assert features["features"] == FULL_VIEW["features"]
    assert len(features["sections"]) == len(FULL_VIEW["sections"])
    assert features["sections"][0] == {"label": "INTRO", "start": 5.768, "end": 35.511,
                                       "energy": 0.599, "danceability": 0.58, "loudness_lufs": -10.42}

    tagged = _addon.tags_block(FULL_VIEW)
    assert list(tagged) == ["genres", "instruments", "moods", "stems", "description"]
    assert tagged["genres"] == FULL_VIEW["tags"]["genres"]
    assert tagged["stems"] == FULL_VIEW["tags"]["stems"]
    assert tagged["description"] == FULL_VIEW["description"]

    assert _addon.lyrics_block(FULL_VIEW) == FULL_VIEW["lyrics"]


def test_blocks_before_their_add_on_has_run():
    bare = _view()
    assert _addon.features_block(bare) == {
        "key": "Amin", "camelot": "8A", "features": {},
        "sections": [
            {"label": "INTRO", "start": 0.3, "end": 3.66, "energy": None, "danceability": None, "loudness_lufs": None},
            {"label": "UP", "start": 3.66, "end": 6.0, "energy": None, "danceability": None, "loudness_lufs": None},
        ],
    }
    assert _addon.tags_block(bare) == {"genres": [], "instruments": [], "moods": [], "stems": {}, "description": ""}
    assert _addon.lyrics_block(bare) == {"vocal_start": None, "lines": []}
    no_key = _addon.features_block(dict(bare, key=None, camelot=None))
    assert no_key["key"] is None and no_key["camelot"] is None


def test_stem_parts_are_instruments_and_moods_or_silent():
    view = _view(tags={"stems": {
        "vocals": {"silent": True, "instruments": [], "moods": []},
        "drums": {"silent": False, "instruments": ["kick"]},
        "bass": {"instruments": {"0": "sub bass"}, "moods": ["deep"]},
    }})
    stems = _addon.tags_block(view)["stems"]
    assert stems == {
        "drums": {"instruments": ["kick"], "moods": []},
        "bass": {"instruments": ["sub bass"], "moods": ["deep"]},
        "vocals": {"silent": True},
    }
    assert list(stems) == ["drums", "bass", "vocals"]   # the website's order


def test_lyrics_lines_with_unknown_times():
    """Plain text from an older analysis is one line with null times: it comes back as it is."""
    view = _view(lyrics={"vocal_start": None, "lines": [
        {"start": None, "end": None, "text": "hello there", "words": []},
        {"start": "1.0", "end": 2.0, "words": [["hi", None, 2.0], [None, 1, 2], "junk"]},
    ]})
    assert _addon.lyrics_block(view)["lines"] == [
        {"start": None, "end": None, "text": "hello there", "words": []},
        {"start": None, "end": 2.0, "words": [["hi", None, 2.0]]},
    ]


def test_view_object_takes_off_only_the_old_wrapper():
    assert _addon.view_object({"audio_segmentation": {"format_version": 4}}) == {"format_version": 4}
    assert _addon.view_object(FULL_VIEW) is FULL_VIEW
    assert _addon.view_object(None) == {}
