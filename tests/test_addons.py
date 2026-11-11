"""
Unit tests for the analysis and its add-ons (SDK 1.6): segment(), the
audio_features / tags / lyrics add-ons, generate_samples(analysis_id=...)
and the CLI subcommands that wrap them.

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


@pytest.fixture(autouse=True)
def fresh_warning_state(monkeypatch):
    # The 2.0 notice is shown once per process; every test starts from "not shown yet".
    monkeypatch.setattr(segment_module, "_EXPANSION_NOTICE_SHOWN", False)


# ---------------------------------------------------------------------------
# Fixtures: an analysis record and its merged view (format 4)
# ---------------------------------------------------------------------------

GRID = {
    "beats_per_bar": 4,
    "tolerance_ms": 25,
    "max_error_ms": 0.0,
    "beat_count": 12,
    "bar_count": 2,
    "pieces": [{"start": 0.3, "bpm": 125.0, "bar": -1, "beat": 2, "count": 12}],
}


def _view(**song):
    return {
        "audio_segmentation": {
            "format_version": 4,
            "bpm": 125.0,
            "duration": 6.0,
            "time_signature": "4/4",
            "grid": GRID,
            "sections": [
                {"label": "INTRO", "start": 0.3, "end": 3.66, "start_bar": -1, "bars": 2},
                {"label": "UP", "start": 3.66, "end": 6.0, "start_bar": 1, "bars": 2},
            ],
            "phrases": [],
            "song_analysis": dict(song),
            "segment_analysis": [{}, {}],
            "bar_analysis": [],
        }
    }


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

    with pytest.warns(FutureWarning):
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

    assert result["analysis_id"] == "exe-ana"
    assert result["audio_segmentation"]["grid"] == GRID
    assert result["segmentation"] is result["audio_segmentation"]
    assert result["execution"]["state"] == "completed"
    assert seen == ["processing", "processing", "completed"]

    # The merged view is saved, as the analysis JSON always was.
    saved = result["files"]["files"]["analysis.json"]
    with open(saved) as f:
        assert json.load(f)["audio_segmentation"]["grid"] == GRID
    assert result["files"]["folder"].endswith("_segmentation")


def test_segment_compat(api, clock, audio_file, tmp_path):
    """Format 4: beat_times and bar_times are added from grid; expand_beats=False adds neither."""
    api.on("POST", "/functions/run/segmentation", _ok(_analysis()))
    api.on("GET", EXE, _ok(_analysis()))
    api.on("GET", VIEW, _ok(_view()))

    with pytest.warns(FutureWarning, match="2.0"):
        result = segment(audio_file, results_folder=str(tmp_path))
    data = result["audio_segmentation"]
    beats, bars = grid.beats_of({"grid": GRID})
    assert data["grid"] == GRID
    assert data["beat_times"] == beats
    assert data["bar_times"] == bars == [3.66, 5.58]
    assert len(data["beat_times"]) == GRID["beat_count"]

    api.on("GET", VIEW, _ok(_view()))
    with warnings.catch_warnings():
        warnings.simplefilter("error")   # no notice when nothing is expanded
        plain = segment(audio_file, results_folder=str(tmp_path), expand_beats=False)
    assert "grid" in plain["audio_segmentation"]
    assert "beat_times" not in plain["audio_segmentation"]
    assert "bar_times" not in plain["audio_segmentation"]


def test_segment_warns_about_2_0_only_once(api, clock, audio_file, tmp_path):
    api.on("POST", "/functions/run/segmentation", _ok(_analysis()))
    api.on("GET", EXE, _ok(_analysis()))
    api.on("GET", VIEW, _ok(_view()))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        segment(audio_file, results_folder=str(tmp_path))
        api.on("GET", VIEW, _ok(_view()))
        segment(audio_file, results_folder=str(tmp_path))
    notices = [w for w in caught if issubclass(w.category, FutureWarning)]
    assert len(notices) == 1


def test_segment_keeps_an_older_file_as_it_is(api, clock, audio_file, tmp_path):
    older = {"audio_segmentation": {"format_version": 3, "beat_times": [0.5, 1.0], "bar_times": [0.5],
                                    "song_analysis": {}, "segment_analysis": []}}
    api.on("POST", "/functions/run/segmentation", _ok(_analysis()))
    api.on("GET", EXE, _ok(_analysis()))
    api.on("GET", VIEW, _ok(older))

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = segment(audio_file, results_folder=str(tmp_path))
    assert result["audio_segmentation"]["beat_times"] == [0.5, 1.0]


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
    api.on("GET", VIEW, _ok(_view(energy=0.62, genre=["Electronic---House"])))

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
    assert result["audio_segmentation"]["song_analysis"]["energy"] == 0.62
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
    api.on("GET", VIEW, _ok(_view(energy=0.62)))

    with mock.patch("audial.pipelines.run") as pipeline:
        result = segment(audio_file, edm=False, features=["energy", "mode", "lyrics"],
                         results_folder=str(tmp_path), expand_beats=False)

    pipeline.assert_not_called()
    [post] = api.requests_to("POST", "/functions/run/segmentation")
    assert json.loads(dict(post["data"])["segmentationParameters"]) == {"edm": False}
    assert len(api.requests_to("POST", "/functions/run/audio-features")) == 1   # once for both
    assert result["audio_segmentation"]["song_analysis"]["energy"] == 0.62
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

FEATURES = {
    "features_version": 1,
    "song": {"key": "A min", "loudness": -7.1, "energy": 0.62, "danceability": 0.71, "mode": "aeolian"},
    "sections": [{"index": 0, "label": "INTRO", "energy": 0.4}, {"index": 1, "label": "UP", "energy": 0.8}],
    "warnings": [],
}

# What the add-on stored on the record (internal), and what the merged view shows (display-ready).
STORED_TAGS = {
    "tags_version": 2,
    "genre": ["Electronic---UK Garage"],
    "song_tags": {"full": {"moods": ["dark"]}},
    "source": {"title": "Operator", "artist": "Hans Glader"},
    "warnings": ["The description could not be made."],
}

TAGS = {
    "genre": ["UK Garage", "Speed Garage"],
    "song_tags": {
        "full": {"moods": ["driving", "groovy"], "instruments": ["drum machine"],
                 "artist_tags": ["uk garage", "ukg"]},
        "drums": {"moods": ["driving"], "instruments": ["kick"], "silent": False},
        "bass": {"moods": ["deep"], "instruments": ["sub bass"], "silent": False},
        "melody": {"moods": ["warm"], "instruments": ["electric piano"], "silent": False},
        "vocals": {"moods": [], "instruments": [], "silent": True},
    },
    "description": "A driving UK garage cut built on a swung two-step groove.",
}

LYRICS = {
    "lyrics": "hello there",
    "is_instrumental": False,
    # The database keeps arrays as objects when it feels like it; the SDK hands back lists.
    "lines": {"0": {"start": 12.34, "end": 13.1, "words": {"0": ["hello", 12.34, 12.71], "1": ["there", 12.8, 13.1]}}},
    "section_lyrics": ["", "hello there"],
    "first_vocal_beat_time": 12.34,
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
    api.on("GET", VIEW, _ok(_view(**TAGS)))

    result = tags("exe-ana", results_folder=str(tmp_path), poll_interval=5)

    starts = api.requests_to("POST", "/functions/run/audio-tags")
    assert len(starts) == 2
    assert starts[0]["json"] == {"userId": USER, "analysisExeId": "exe-ana"}
    # The merged view's display-ready values come back unchanged, plus the record's warnings.
    assert result == dict(TAGS, warnings=["The description could not be made."])
    assert "source" not in result and "tags_version" not in result
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
                                                                "startedAt": 1, "result": LYRICS})))

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

    result = audio_features("exe-ana", results_folder=str(tmp_path))
    assert result["song"]["energy"] == 0.62
    assert len(api.requests_to("POST", "/functions/run/audio-features")) == 2


def test_audio_features_returns_the_result_and_saves_it(api, clock, tmp_path):
    api.on("POST", "/functions/run/audio-features",
           _ok({"exeId": "exe-feat", "analysisExeId": "exe-ana", "addon": "features", "state": "completed"}))
    api.on("GET", EXE, _ok(_analysis(features={"state": "completed", "exeId": "exe-feat", "startedAt": 1,
                                               "result": FEATURES})))

    result = audio_features("exe-ana", results_folder=str(tmp_path))

    assert result == FEATURES
    with open(os.path.join(str(tmp_path), "exe-ana_analysis", "features.json")) as f:
        assert json.load(f) == FEATURES


def test_addon_rerun_is_sent(api, clock, tmp_path):
    api.on("POST", "/functions/run/audio-features",
           _ok({"exeId": "exe-feat2", "analysisExeId": "exe-ana", "addon": "features", "state": "queued"}))
    api.on("GET", EXE, _ok(_analysis(features={"state": "completed", "exeId": "exe-feat2", "startedAt": 1,
                                               "result": FEATURES})))
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
    seen = []

    audio_features("exe-ana", results_folder=str(tmp_path), on_progress=seen.append)
    assert seen and seen[0]["warmup"]["state"] == "cold"


def test_lyrics_returns_lines_with_word_times(api, clock, tmp_path):
    api.on("POST", "/functions/run/lyrics",
           _ok({"exeId": "exe-lyr", "analysisExeId": "exe-ana", "addon": "lyrics", "state": "queued"}))
    api.on("GET", EXE, _ok(_analysis(stems="completed", lyrics={"state": "completed", "exeId": "exe-lyr",
                                                                "startedAt": 1, "result": LYRICS})))

    # audial.lyrics is both the per-note lyric module and this add-on.
    result = audial.lyrics("exe-ana", results_folder=str(tmp_path))

    assert result["lines"] == [
        {"start": 12.34, "end": 13.1, "words": [["hello", 12.34, 12.71], ["there", 12.8, 13.1]]}
    ]
    assert result["lyrics"] == "hello there"
    assert result["section_lyrics"] == ["", "hello there"]
    assert result["first_vocal_beat_time"] == 12.34


def test_lyrics_of_an_instrumental_has_no_lines(api, clock, tmp_path):
    api.on("POST", "/functions/run/lyrics",
           _ok({"exeId": "exe-lyr", "analysisExeId": "exe-ana", "addon": "lyrics", "state": "completed"}))
    api.on("GET", EXE, _ok(_analysis(stems="completed", lyrics={
        "state": "completed", "exeId": "exe-lyr", "startedAt": 1,
        "result": {"is_instrumental": True, "first_vocal_beat_time": None}})))

    result = lyrics_function("exe-ana", results_folder=str(tmp_path))
    assert result["is_instrumental"] is True
    assert result["lines"] == [] and result["lyrics"] == ""


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
    audio_features("pl-old", results_folder=str(tmp_path))
    [start] = api.requests_to("POST", "/functions/run/audio-features")
    assert start["json"]["analysisExeId"] == "pl-old"
    assert api.requests_to("GET", EXE)


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
                    return_value={"analysis_id": "exe-ana", "audio_segmentation": {}}) as seg, \
            mock.patch("audial.cli.commands.audio_features", return_value=FEATURES) as feat, \
            mock.patch("audial.cli.commands.warmup_reporter", return_value=None):
        _cli(["features", audio_file, "--genre", "House"])

    assert seg.call_args.kwargs["file_path"] == audio_file
    assert seg.call_args.kwargs["genre"] == "House"
    assert "features" not in seg.call_args.kwargs
    assert feat.call_args.args[0] == "exe-ana"
    out = capsys.readouterr().out
    assert "exe-ana" in out and "0.62" in out


def test_cli_lyrics_on_an_analysis_id_prints_timed_lines(capsys):
    lines = {"lyrics": "hello there", "is_instrumental": False,
             "lines": [{"start": 12.34, "end": 13.1, "words": [["hello", 12.34, 12.71], ["there", 12.8, 13.1]]}]}
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
                    return_value={"is_instrumental": True, "lines": [], "lyrics": ""}), \
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
    assert "Genre: UK Garage, Speed Garage" in out
    assert out.index(TAGS["description"]) < out.index("Genre:")
    assert "Song artist tags: uk garage, ukg" in out
    assert "Drums instruments: kick" in out
    assert "Vocals: No vocals in this track." in out
    assert "Vocals moods" not in out


def test_cli_tags_silent_and_empty_parts_print_the_website_lines(capsys):
    """R17: a silent part prints its role's line; a part that is not silent but has no tags prints
    "Nothing to tag in this part."; a part the view does not have (version 1 drums, vocals) prints nothing."""
    song_tags = {
        "full": {"moods": ["dark"], "instruments": [], "artist_tags": []},
        "drums": {"moods": [], "instruments": [], "silent": True},
        "bass": {"moods": [], "instruments": [], "silent": True},
        "melody": {"moods": [], "instruments": [], "silent": True},
        "vocals": {"moods": [], "instruments": [], "silent": False},
    }
    with mock.patch("audial.cli.commands.tags", return_value=dict(TAGS, song_tags=song_tags, warnings=[])), \
            mock.patch("audial.cli.commands.warmup_reporter", return_value=None):
        _cli(["tags", "exe-ana"])
    out = capsys.readouterr().out
    assert "Drums: No drums in this track." in out
    assert "Bass: No bass in this track." in out
    assert "Melody: No melody in this track." in out
    assert "Vocals: Nothing to tag in this part." in out
    assert "Song moods: dark" in out and "Song: Nothing" not in out

    v1 = {"full": {"moods": ["dark"], "instruments": [], "artist_tags": []},
          "bass": {"moods": [], "instruments": []}, "melody": {"moods": ["warm"], "instruments": []}}
    with mock.patch("audial.cli.commands.tags", return_value=dict(TAGS, song_tags=v1, warnings=[])), \
            mock.patch("audial.cli.commands.warmup_reporter", return_value=None):
        _cli(["tags", "exe-ana"])
    out = capsys.readouterr().out
    assert "Bass: Nothing to tag in this part." in out
    assert "Melody moods: warm" in out
    assert "Drums" not in out and "Vocals" not in out


def test_tags_without_description_or_extra_parts(api, clock, tmp_path):
    """An older record's view has no description and no drums or vocals: they stay as the view has them."""
    api.on("POST", "/functions/run/audio-tags",
           _ok({"exeId": "exe-tags", "analysisExeId": "exe-ana", "addon": "tags", "state": "queued"}))
    api.on("GET", EXE, _ok(_analysis(stems="completed", tags={"state": "completed", "exeId": "exe-tags",
                                                              "startedAt": 1, "result": {"warnings": []}})))
    api.on("GET", f"/db/{USER}/execution/exe-tags", _ok({"exeId": "exe-tags", "state": "processing"}))
    api.on("GET", VIEW, _ok(_view(genre=["House"], song_tags={"full": {"moods": ["dark"]}, "bass": {}})))

    result = tags("exe-ana", results_folder=str(tmp_path))

    assert result["description"] == ""
    assert result["genre"] == ["House"]
    assert result["song_tags"]["full"]["moods"] == ["dark"]
    assert result["song_tags"]["bass"] == {"moods": [], "instruments": []}
    assert "vocals" not in result["song_tags"]
    assert result["warnings"] == []


def test_cli_segment_runs_the_fast_analysis_by_default(audio_file, capsys):
    view = _view()["audio_segmentation"]
    with mock.patch("audial.cli.commands.segment", return_value={
        "analysis_id": "exe-ana", "audio_segmentation": view, "segmentation": view,
        "files": {"folder": "/tmp/x", "files": {"analysis.json": "/tmp/x/analysis.json"}},
    }) as seg, mock.patch("audial.cli.commands.warmup_reporter", return_value=None):
        _cli(["segment", audio_file])
    assert seg.call_args.kwargs["features"] is None
    out = capsys.readouterr().out
    assert "exe-ana" in out and "INTRO" in out and "audial lyrics exe-ana" in out


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
    assert audial.__version__ == "1.7.1"


def test_segment_keeps_the_15_positional_order():
    """1.5 callers that pass arguments by position keep working: the new options are keyword-only."""
    import inspect
    from audial.functions.segment import segment as seg
    params = list(inspect.signature(seg).parameters.values())
    assert [p.name for p in params[:9]] == ["file_path", "components", "analysis_type", "features", "genre",
                                            "results_folder", "api_key", "on_progress", "poll_interval"]
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params if p.name in ("edm", "expand_beats", "max_wait"))
