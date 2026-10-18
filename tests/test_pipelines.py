"""
Unit tests for audial.pipelines and the functions that run on top of it.

`requests` is mocked throughout (the Session methods on AudialProxy, and
audial.utils.file_utils.download_file) -- no real network calls are made.
"""

from unittest import mock

import pytest

from audial import pipelines
from audial.api.exceptions import AudialAPIError, AudialAuthError, AudialError
from audial.api.proxy import AudialProxy
from audial.functions.samples import generate_samples
from audial.functions.segment import segment


# ---------------------------------------------------------------------------
# Status fixtures
# ---------------------------------------------------------------------------

def _queued(pipeline="sample-pack"):
    return {
        "pipelineId": "pl-1",
        "pipeline": pipeline,
        "state": "queued",
        "steps": [
            {"name": "stem-split", "state": "pending"},
            {"name": pipeline.replace("sample-pack", "sample-pack"), "state": "pending"},
        ],
        "outputs": {},
        "original": {"filename": "track.wav", "url": "https://storage.example/track.wav"},
    }


def _running():
    return {
        "pipelineId": "pl-1",
        "pipeline": "sample-pack",
        "state": "running",
        "currentStep": "sample-pack",
        "steps": [
            {"name": "stem-split", "state": "completed", "exeId": "exe-stem", "durationMs": 41000},
            {"name": "sample-pack", "state": "running", "exeId": "exe-sample",
             "subStage": "analysis"},
        ],
        "outputs": {"stems": {"drumsmp3": {"filename": "drums.mp3",
                                           "url": "https://storage.example/drums.mp3"}}},
    }


def _completed_sample_pack():
    return {
        "pipelineId": "pl-1",
        "pipeline": "sample-pack",
        "state": "completed",
        "durationMs": 128000,
        "steps": [
            {"name": "stem-split", "state": "completed", "exeId": "exe-stem", "durationMs": 41000},
            {"name": "sample-pack", "state": "completed", "exeId": "exe-sample",
             "durationMs": 87000},
        ],
        "outputs": {
            "stems": {"drumsmp3": {"filename": "drums.mp3",
                                   "url": "https://storage.example/drums.mp3"}},
            "samples": [
                "https://storage.example/sample/kick_01.wav",
                "https://storage.example/sample/bass_01.wav",
            ],
        },
    }


def _completed_segmentation():
    return {
        "pipelineId": "pl-2",
        "pipeline": "segmentation",
        "state": "completed",
        "steps": [
            {"name": "stem-split", "state": "completed", "exeId": "exe-stem", "durationMs": 40000},
            {"name": "segmentation", "state": "completed", "exeId": "exe-seg",
             "durationMs": 20000},
        ],
        "outputs": {
            "stems": {"vocalsmp3": {"filename": "vocals.mp3",
                                    "url": "https://storage.example/vocals.mp3"}},
            "segmentation": [
                "https://storage.example/segmentation/pruned_audio_segmentation.json",
                "https://storage.example/segmentation/raw_audio_segmentation.json",
            ],
        },
    }


def _failed(step="sample-pack"):
    return {
        "pipelineId": "pl-1",
        "pipeline": "sample-pack",
        "state": "failed",
        "steps": [
            {"name": "stem-split", "state": "completed", "exeId": "exe-stem", "durationMs": 41000},
            {"name": step, "state": "failed", "exeId": "exe-sample",
             "error": {"code": "WORKER_FAILED", "message": "the worker ran out of memory"}},
        ],
        "outputs": {"stems": {}},
        "error": {"step": step, "code": "WORKER_FAILED",
                  "message": "the worker ran out of memory"},
    }


# ---------------------------------------------------------------------------
# AudialProxy.create_pipeline: the multipart request
# ---------------------------------------------------------------------------

def test_create_pipeline_posts_multipart_with_options(audio_file, fake_response):
    proxy = AudialProxy()
    proxy.session.post = mock.MagicMock(return_value=fake_response(202, _queued()))

    status = proxy.create_pipeline(
        "sample-pack",
        file_path=audio_file,
        options={"components": ["drums", "bass"], "genre": "Tech House", "bpm": None},
    )

    assert status["state"] == "queued"
    assert proxy.session.post.call_args.args[0] == f"{proxy.base_url}/pipelines"

    kwargs = proxy.session.post.call_args.kwargs
    fields = kwargs["data"]
    assert ("pipeline", "sample-pack") in fields
    assert ("userId", "test-user-id") in fields
    # A list option repeats its key once per item; a None option is dropped so
    # the API applies its own default.
    assert ("options.components", "drums") in fields
    assert ("options.components", "bass") in fields
    assert ("options.genre", "Tech House") in fields
    assert not [key for key, _ in fields if key == "options.bpm"]

    # The audio file goes in the `original` part, and Content-Type is left to
    # requests so it carries the multipart boundary.
    assert "original" in kwargs["files"]
    assert kwargs["files"]["original"][0] == "My Song [Final] v2.WAV"
    assert "Content-Type" not in kwargs["headers"]


def test_create_pipeline_without_a_file_posts_json(fake_response):
    proxy = AudialProxy()
    proxy.session.post = mock.MagicMock(return_value=fake_response(202, _queued()))

    proxy.create_pipeline(
        "segmentation",
        original={"filename": "track.wav", "url": "https://storage.example/track.wav"},
        from_exe_id="exe-stem",
        callback_url="https://hooks.example/done",
    )

    body = proxy.session.post.call_args.kwargs["json"]
    assert body["pipeline"] == "segmentation"
    assert body["original"]["url"] == "https://storage.example/track.wav"
    assert body["from"] == {"exeId": "exe-stem"}
    assert body["callbackUrl"] == "https://hooks.example/done"


def test_create_pipeline_needs_a_file_or_an_original():
    proxy = AudialProxy()
    proxy.session.post = mock.MagicMock()

    with pytest.raises(AudialError):
        proxy.create_pipeline("sample-pack")
    proxy.session.post.assert_not_called()


def test_create_pipeline_error_message_carries_the_code(audio_file, fake_response):
    proxy = AudialProxy()
    proxy.session.post = mock.MagicMock(
        return_value=fake_response(400, {"error": "Unknown pipeline: sample_pack",
                                         "code": "INVALID_PIPELINE"})
    )

    with pytest.raises(AudialAPIError) as excinfo:
        proxy.create_pipeline("sample-pack", file_path=audio_file)

    assert "INVALID_PIPELINE" in str(excinfo.value)
    assert excinfo.value.status_code == 400


def test_pipeline_401_raises_auth_error(fake_response):
    proxy = AudialProxy()
    proxy.session.get = mock.MagicMock(return_value=fake_response(401, {"error": "nope"}))

    with pytest.raises(AudialAuthError):
        proxy.get_pipeline("pl-1")


def test_get_and_list_and_cancel_hit_the_documented_routes(fake_response):
    proxy = AudialProxy()
    proxy.session.get = mock.MagicMock(return_value=fake_response(200, {"items": []}))
    proxy.session.post = mock.MagicMock(
        return_value=fake_response(200, {"pipelineId": "pl-1", "state": "cancelled"})
    )

    proxy.get_pipeline("pl-1")
    assert proxy.session.get.call_args.args[0] == f"{proxy.base_url}/pipelines/pl-1"

    proxy.list_pipelines(limit=5, cursor="c1")
    assert proxy.session.get.call_args.args[0] == f"{proxy.base_url}/pipelines"
    assert proxy.session.get.call_args.kwargs["params"] == {"limit": 5, "cursor": "c1"}

    proxy.cancel_pipeline("pl-1")
    assert proxy.session.post.call_args.args[0] == f"{proxy.base_url}/pipelines/pl-1/cancel"


# ---------------------------------------------------------------------------
# pipelines.run / get / cancel / list
# ---------------------------------------------------------------------------

def test_run_polls_until_completed_and_reports_progress(audio_file):
    seen = []

    with mock.patch.object(
        AudialProxy, "create_pipeline", return_value=_queued()
    ) as create, mock.patch.object(
        AudialProxy, "get_pipeline", side_effect=[_running(), _completed_sample_pack()]
    ) as get, mock.patch("audial.pipelines.time.sleep", return_value=None) as sleep:
        status = pipelines.run(
            "sample-pack",
            audio_file,
            options={"genre": "Tech House"},
            poll_interval=3,
            on_progress=lambda s: seen.append(s["state"]),
        )

    assert status["state"] == "completed"
    assert status["outputs"]["samples"][0].endswith("kick_01.wav")
    assert create.call_args.kwargs["options"] == {"genre": "Tech House"}
    assert create.call_args.args[0] == "sample-pack"
    assert get.call_args_list == [mock.call("pl-1"), mock.call("pl-1")]
    # The initial response and every poll are reported.
    assert seen == ["queued", "running", "completed"]
    assert sleep.call_args_list == [mock.call(3), mock.call(3)]


def test_run_without_wait_returns_the_queued_status(audio_file):
    with mock.patch.object(
        AudialProxy, "create_pipeline", return_value=_queued()
    ), mock.patch.object(AudialProxy, "get_pipeline") as get:
        status = pipelines.run("sample-pack", audio_file, wait=False)

    assert status["state"] == "queued"
    get.assert_not_called()


def test_run_raises_with_the_failed_step_and_message(audio_file):
    with mock.patch.object(
        AudialProxy, "create_pipeline", return_value=_queued()
    ), mock.patch.object(
        AudialProxy, "get_pipeline", return_value=_failed("sample-pack")
    ), mock.patch("audial.pipelines.time.sleep", return_value=None):
        with pytest.raises(AudialError) as excinfo:
            pipelines.run("sample-pack", audio_file)

    message = str(excinfo.value)
    assert "sample-pack" in message
    assert "the worker ran out of memory" in message
    assert "WORKER_FAILED" in message


def test_run_raises_for_a_cancelled_pipeline(audio_file):
    cancelled = {
        "pipelineId": "pl-1",
        "pipeline": "segmentation",
        "state": "cancelled",
        "steps": [
            {"name": "stem-split", "state": "completed", "durationMs": 1000},
            {"name": "segmentation", "state": "cancelled"},
        ],
    }
    with mock.patch.object(
        AudialProxy, "create_pipeline", return_value=_queued("segmentation")
    ), mock.patch.object(
        AudialProxy, "get_pipeline", return_value=cancelled
    ), mock.patch("audial.pipelines.time.sleep", return_value=None):
        with pytest.raises(AudialError) as excinfo:
            pipelines.run("segmentation", audio_file)

    assert "cancelled" in str(excinfo.value)


def test_run_rejects_an_unknown_pipeline_and_a_missing_file(audio_file, tmp_path):
    with mock.patch.object(AudialProxy, "create_pipeline") as create:
        with pytest.raises(AudialError) as unknown:
            pipelines.run("mastering", audio_file)
        with pytest.raises(AudialError) as missing:
            pipelines.run("sample-pack", str(tmp_path / "nope.wav"))
    create.assert_not_called()
    assert "Unknown pipeline" in str(unknown.value)
    assert "File not found" in str(missing.value)


def test_get_cancel_list_delegate_to_the_proxy():
    with mock.patch.object(
        AudialProxy, "get_pipeline", return_value=_running()
    ) as get, mock.patch.object(
        AudialProxy, "cancel_pipeline", return_value={"state": "cancelled"}
    ) as cancel, mock.patch.object(
        AudialProxy, "list_pipelines", return_value={"items": [_running()], "nextCursor": "c2"}
    ) as listed:
        assert pipelines.get("pl-1")["state"] == "running"
        assert pipelines.cancel("pl-1")["state"] == "cancelled"
        page = pipelines.list(limit=5)

    get.assert_called_once_with("pl-1")
    cancel.assert_called_once_with("pl-1")
    listed.assert_called_once_with(limit=5, cursor=None)
    assert page["nextCursor"] == "c2" and len(page["items"]) == 1


# ---------------------------------------------------------------------------
# StepTracker
# ---------------------------------------------------------------------------

def test_step_tracker_reports_only_what_changed():
    tracker = pipelines.StepTracker()

    assert tracker.changes(_queued()) == []

    running = tracker.changes(_running())
    assert running == ["stem-split completed in 41 s", "sample-pack running (analysis)"]

    # Same status again: nothing new to say.
    assert tracker.changes(_running()) == []

    done = tracker.changes(_completed_sample_pack())
    assert done[0] == "sample-pack completed in 87 s"
    assert done[-1] == "pipeline completed in 128 s"


def test_step_tracker_reports_a_failed_step_with_its_message():
    tracker = pipelines.StepTracker()
    tracker.changes(_queued())
    lines = tracker.changes(_failed("sample-pack"))
    assert "sample-pack failed: the worker ran out of memory" in lines


# ---------------------------------------------------------------------------
# generate_samples / segment run as pipelines
# ---------------------------------------------------------------------------

def test_generate_samples_runs_the_sample_pack_pipeline(audio_file, tmp_path):
    downloaded = []

    with mock.patch(
        "audial.pipelines.run", return_value=_completed_sample_pack()
    ) as run, mock.patch(
        "audial.functions.samples.download_file",
        side_effect=lambda url, dest: downloaded.append((url, dest)) or dest,
    ):
        result = generate_samples(
            audio_file,
            components=["drums", "bass"],
            genre="Tech House",
            results_folder=str(tmp_path),
        )

    assert run.call_args.args[0] == "sample-pack"
    assert run.call_args.args[1] == audio_file
    assert run.call_args.kwargs["options"] == {
        "components": ["drums", "bass"],
        "genre": "Tech House",
    }
    assert callable(run.call_args.kwargs["on_progress"])

    # Same return shape as before: execution + files{folder, files}.
    assert result["execution"]["state"] == "completed"
    assert set(result["files"]["files"]) == {"kick_01.wav", "bass_01.wav"}
    assert result["files"]["folder"].endswith("exe-sample_samples")
    assert len(downloaded) == 2


def test_generate_samples_forwards_progress_to_its_caller(audio_file, tmp_path):
    seen = []

    def fake_run(name, file_path, **kwargs):
        kwargs["on_progress"](_running())
        return _completed_sample_pack()

    with mock.patch("audial.pipelines.run", side_effect=fake_run), mock.patch(
        "audial.functions.samples.download_file", side_effect=lambda url, dest: dest
    ):
        generate_samples(audio_file, results_folder=str(tmp_path),
                         on_progress=lambda s: seen.append(s["state"]))

    assert seen == ["running"]


def test_generate_samples_still_validates_before_calling_the_api(audio_file, tmp_path):
    with mock.patch("audial.pipelines.run") as run:
        with pytest.raises(AudialError):
            generate_samples(audio_file, components=["kazoo"], results_folder=str(tmp_path))
        with pytest.raises(AudialError):
            generate_samples(audio_file, genre="Polka", results_folder=str(tmp_path))
    run.assert_not_called()


def test_segment_runs_the_segmentation_pipeline_and_parses_the_pruned_json(audio_file, tmp_path):
    def fake_download(url, dest):
        with open(dest, "w") as f:
            f.write('{"audio_segmentation": [{"label": "intro", "start": 0}]}')
        return dest

    with mock.patch(
        "audial.pipelines.run", return_value=_completed_segmentation()
    ) as run, mock.patch(
        "audial.functions.segment.download_file", side_effect=fake_download
    ):
        result = segment(audio_file, genre="House", results_folder=str(tmp_path))

    assert run.call_args.args[0] == "segmentation"
    options = run.call_args.kwargs["options"]
    assert options["genre"] == "House"
    assert options["components"] == ["bass", "beat", "melody", "vocal"]
    assert "tags" in options["featuresToExtract"]

    # Only the pruned analysis JSON is downloaded, as before.
    assert list(result["files"]["files"]) == ["pruned_audio_segmentation.json"]
    assert result["segmentation"] == [{"label": "intro", "start": 0}]
    assert result["execution"]["state"] == "completed"
    assert result["files"]["folder"].endswith("_segmentation")


def test_segment_raises_when_the_pipeline_returned_no_segmentation(audio_file, tmp_path):
    empty = dict(_completed_segmentation(), outputs={"stems": {}})

    with mock.patch("audial.pipelines.run", return_value=empty):
        with pytest.raises(AudialError) as excinfo:
            segment(audio_file, results_folder=str(tmp_path))

    assert "did not produce expected results" in str(excinfo.value)


def test_run_retries_transient_poll_errors(monkeypatch):
    from audial import pipelines
    from audial.api.exceptions import AudialAPIError

    calls = {"n": 0}

    class Proxy:
        def __init__(self, *a, **k):
            pass

        def create_pipeline(self, *a, **k):
            return {"pipelineId": "p1", "state": "queued", "steps": []}

        def get_pipeline(self, pid):
            calls["n"] += 1
            if calls["n"] < 3:
                raise AudialAPIError("Failed to get pipeline p1: HTTP 429", status_code=429)
            return {"pipelineId": "p1", "state": "completed", "steps": [], "outputs": {}}

    monkeypatch.setattr(pipelines, "AudialProxy", Proxy)
    monkeypatch.setattr(pipelines.time, "sleep", lambda *_: None)
    status = pipelines.run("sample-pack", __file__, wait=True, poll_interval=0)
    assert status["state"] == "completed"
    assert calls["n"] == 3


def test_run_gives_up_on_non_transient_poll_errors(monkeypatch):
    import pytest
    from audial import pipelines
    from audial.api.exceptions import AudialAPIError

    class Proxy:
        def __init__(self, *a, **k):
            pass

        def create_pipeline(self, *a, **k):
            return {"pipelineId": "p1", "state": "queued", "steps": []}

        def get_pipeline(self, pid):
            raise AudialAPIError("Failed to get pipeline p1: HTTP 404", status_code=404)

    monkeypatch.setattr(pipelines, "AudialProxy", Proxy)
    monkeypatch.setattr(pipelines.time, "sleep", lambda *_: None)
    with pytest.raises(AudialAPIError):
        pipelines.run("sample-pack", __file__, wait=True, poll_interval=0)
