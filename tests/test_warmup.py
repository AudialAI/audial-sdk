"""
Unit tests for audial.warmup and audial.status.

The HTTP layer is mocked throughout (the Session methods on AudialProxy) --
no real network calls are made.
"""

from unittest import mock

import pytest

from audial import warmup
from audial.api.exceptions import AudialAPIError, AudialAuthError
from audial.api.proxy import AudialProxy
from audial.functions.sound2vital import sound2vital
from audial.functions.text2vox import text2vox
from audial.status import status

COLD_SENTENCE = (
    "Warming up the machine — the first request takes a few minutes longer than usual "
    "(about 3 min); every run after this is faster"
)


def _warmup(state, **extra):
    return dict({"state": state, "expectedColdStartMs": 180000}, **extra)


def _execution(state="processing", warmup_state=None, **extra):
    record = {"exeId": "exe-1", "state": state}
    if warmup_state is not None:
        record["warmup"] = _warmup(warmup_state, **extra)
    return record


# ---------------------------------------------------------------------------
# The message
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "ms,expected",
    [
        (180000, 3),
        (150000, 3),      # 2.5 min rounds up
        (90000, 2),       # 1.5 min rounds up
        (20000, 1),       # never says "about 0 min"
        (0, None),
        (-1, None),
        (None, None),
        ("180000", None),  # anything unusable is simply not quoted
        (True, None),
    ],
)
def test_expected_minutes(ms, expected):
    assert warmup.expected_minutes(ms) == expected


def test_cold_start_message_quotes_the_endpoints_own_number():
    assert warmup.cold_start_message(180000) == COLD_SENTENCE


def test_cold_start_message_without_a_number_still_reads():
    message = warmup.cold_start_message()
    assert message == (
        "Warming up the machine — the first request takes a few minutes longer than usual; "
        "every run after this is faster"
    )
    assert "about" not in message


@pytest.mark.parametrize(
    "state,expected",
    [
        ("cold", COLD_SENTENCE),
        ("initializing", COLD_SENTENCE),
        ("working", "Working on your job…"),
        ("done", None),
    ],
)
def test_message_per_state(state, expected):
    assert warmup.message(_execution(warmup_state=state)) == expected


def test_a_job_that_never_waited_says_nothing():
    assert warmup.message(_execution()) is None
    assert warmup.state_of(_execution()) is None
    assert warmup.message(None) is None
    assert warmup.message({}) is None


def test_message_accepts_a_bare_warmup_object():
    assert warmup.message(_warmup("working")) == "Working on your job…"


# ---------------------------------------------------------------------------
# Pipelines carry one warm-up per step
# ---------------------------------------------------------------------------

def _pipeline(current, step_states):
    return {
        "pipelineId": "pl-1",
        "pipeline": "sample-pack",
        "state": "running",
        "currentStep": current,
        "steps": [
            dict({"name": name, "state": "running"},
                 **({"warmup": _warmup(ws)} if ws else {}))
            for name, ws in step_states
        ],
    }


def test_pipeline_warmup_comes_from_the_step_being_run():
    status_doc = _pipeline(
        "sample-pack", [("stem-split", "done"), ("sample-pack", "initializing")]
    )
    assert warmup.state_of(status_doc) == "initializing"
    assert warmup.message(status_doc) == COLD_SENTENCE


def test_pipeline_without_a_current_step_prefers_the_one_still_warming():
    status_doc = _pipeline(None, [("stem-split", "done"), ("sample-pack", "working")])
    assert warmup.state_of(status_doc) == "working"


def test_pipeline_with_no_warmup_anywhere_says_nothing():
    assert warmup.message(_pipeline("stem-split", [("stem-split", None)])) is None


# ---------------------------------------------------------------------------
# WarmupTracker: one line per change
# ---------------------------------------------------------------------------

def test_tracker_reports_each_phase_once():
    tracker = warmup.WarmupTracker()

    assert tracker.changes(_execution(warmup_state="cold")) == [COLD_SENTENCE]
    # Same sentence for "initializing": the user is already told.
    assert tracker.changes(_execution(warmup_state="initializing")) == []
    assert tracker.changes(_execution(warmup_state="working")) == ["Working on your job…"]
    assert tracker.changes(_execution(warmup_state="working")) == []
    assert tracker.changes(_execution("completed", warmup_state="done", delayMs=174000)) == []
    assert tracker.state == "done"


def test_tracker_stays_quiet_for_a_warm_job():
    tracker = warmup.WarmupTracker()
    assert tracker.changes(_execution()) == []
    assert tracker.changes(_execution("completed")) == []
    assert tracker.state is None


def test_tracker_can_be_told_what_was_already_said():
    tracker = warmup.WarmupTracker(last_message=COLD_SENTENCE)
    assert tracker.changes(_execution(warmup_state="cold")) == []


# ---------------------------------------------------------------------------
# WarmupReporter: the CLI's pre-flight + live output
# ---------------------------------------------------------------------------

def test_reporter_warns_before_submitting_when_the_service_is_cold():
    lines = []
    reporter = warmup.WarmupReporter(printer=lines.append)

    with mock.patch(
        "audial.status.status",
        return_value={"items": [{"function": "text2vox", "warm": False,
                                 "queued": 0, "expectedColdStartMs": 180000}]},
    ):
        said = reporter.preflight("text2vox")

    assert said == COLD_SENTENCE
    assert lines == [COLD_SENTENCE]

    # The execution then reports the same phase: it is not announced twice.
    reporter(_execution(warmup_state="initializing"))
    assert lines == [COLD_SENTENCE]
    # ...but the next phase is.
    reporter(_execution(warmup_state="working"))
    assert lines == [COLD_SENTENCE, "Working on your job…"]


def test_reporter_says_nothing_when_the_service_is_warm():
    lines = []
    reporter = warmup.WarmupReporter(printer=lines.append)

    with mock.patch(
        "audial.status.status",
        return_value={"items": [{"function": "text2vox", "warm": True, "queued": 0}]},
    ):
        assert reporter.preflight("text2vox") is None
    assert lines == []


def test_a_broken_status_endpoint_never_stops_a_job():
    lines = []
    reporter = warmup.WarmupReporter(printer=lines.append)

    with mock.patch("audial.status.status", side_effect=AudialAPIError("boom")):
        assert reporter.preflight("text2vox") is None
    assert lines == []


# ---------------------------------------------------------------------------
# find_function / is_cold
# ---------------------------------------------------------------------------

STATUS_DOC = {
    "items": [
        {"function": "text2vox", "warm": False, "queued": 2,
         "expectedColdStartMs": 180000, "expectedRunMs": 42000},
        {"function": "sample-pack", "warm": True, "queued": 0, "expectedRunMs": 87000},
    ]
}


@pytest.mark.parametrize(
    "name,expected_function",
    [
        ("text2vox", "text2vox"),
        ("sample-pack", "sample-pack"),
        # An SDK name is translated to the API's name for that function.
        ("generate_samples", "sample-pack"),
        ("stem_split", None),
    ],
)
def test_find_function_accepts_either_spelling(name, expected_function):
    item = warmup.find_function(STATUS_DOC, name)
    assert (item or {}).get("function") == expected_function


def test_is_cold():
    assert warmup.is_cold(STATUS_DOC, "text2vox") is True
    assert warmup.is_cold(STATUS_DOC, "generate_samples") is False
    # A function the document says nothing about is never warned about.
    assert warmup.is_cold(STATUS_DOC, "stem_split") is False
    assert warmup.is_cold({}, "text2vox") is False
    assert warmup.is_cold(None) is False


# ---------------------------------------------------------------------------
# audial.status(): GET /functions/status
# ---------------------------------------------------------------------------

def test_status_returns_the_api_envelope(fake_response):
    proxy = AudialProxy()
    proxy.session.get = mock.MagicMock(return_value=fake_response(200, STATUS_DOC))

    with mock.patch("audial.status.AudialProxy", return_value=proxy):
        doc = status()

    assert doc == STATUS_DOC
    item = doc["items"][0]
    assert set(item) == {
        "function", "warm", "queued", "expectedColdStartMs", "expectedRunMs"
    }
    assert proxy.session.get.call_args.args[0] == f"{proxy.base_url}/functions/status"
    assert proxy.session.get.call_args.kwargs["params"] is None


def test_status_translates_an_sdk_function_name(fake_response):
    proxy = AudialProxy()
    proxy.session.get = mock.MagicMock(return_value=fake_response(200, {"items": []}))

    with mock.patch("audial.status.AudialProxy", return_value=proxy):
        status("generate_samples")

    assert proxy.session.get.call_args.kwargs["params"] == {"function": "sample-pack"}


def test_status_passes_an_api_function_name_through(fake_response):
    proxy = AudialProxy()
    proxy.session.get = mock.MagicMock(return_value=fake_response(200, {"items": []}))

    with mock.patch("audial.status.AudialProxy", return_value=proxy):
        status("text2vox")

    assert proxy.session.get.call_args.kwargs["params"] == {"function": "text2vox"}


def test_status_surfaces_auth_failure(fake_response):
    proxy = AudialProxy()
    proxy.session.get = mock.MagicMock(return_value=fake_response(401, {"error": "nope"}))

    with mock.patch("audial.status.AudialProxy", return_value=proxy):
        with pytest.raises(AudialAuthError):
            status()


# ---------------------------------------------------------------------------
# on_progress receives the warm-up states from a real poll loop
# ---------------------------------------------------------------------------

def test_sound2vital_on_progress_receives_every_warmup_state(audio_file, tmp_path):
    seen = []
    tracker = warmup.WarmupTracker()
    lines = []

    def on_progress(status_dict):
        seen.append(warmup.state_of(status_dict))
        lines.extend(tracker.changes(status_dict))

    polls = [
        _execution(warmup_state="cold"),
        _execution(warmup_state="initializing"),
        _execution(warmup_state="working"),
        dict(_execution("completed", warmup_state="done", delayMs=174000), preset={}),
    ]

    with mock.patch(
        "audial.functions.sound2vital.AudialProxy.upload_execution_file",
        return_value={"filename": "kick.wav", "url": "https://storage.example/kick.wav"},
    ), mock.patch(
        "audial.functions.sound2vital.AudialProxy.run_sound2vital",
        return_value={"exeId": "exe-1", "state": "created"},
    ), mock.patch(
        "audial.functions.sound2vital.AudialProxy.get_execution", side_effect=polls
    ), mock.patch("audial.functions.sound2vital.time.sleep", return_value=None):
        result = sound2vital(
            file_path=audio_file, results_folder=str(tmp_path), on_progress=on_progress
        )

    # The submit response, then one call per poll.
    assert seen == [None, "cold", "initializing", "working", "done"]
    assert lines == [COLD_SENTENCE, "Working on your job…"]
    assert result["execution"]["warmup"]["delayMs"] == 174000


def test_text2vox_on_progress_receives_the_warmup_object(audio_file, tmp_path):
    midi = tmp_path / "melody.mid"
    midi.write_bytes(b"MThd")
    seen = []

    polls = [
        _execution(warmup_state="initializing"),
        dict(_execution("completed", warmup_state="done", delayMs=120000), generated={}),
    ]

    with mock.patch(
        "audial.functions.text2vox.AudialProxy.upload_execution_file",
        return_value={"filename": "voice.wav", "url": "https://storage.example/voice.wav"},
    ), mock.patch(
        "audial.functions.text2vox.AudialProxy.run_text2vox",
        return_value={"exeId": "exe-1", "state": "created"},
    ), mock.patch(
        "audial.functions.text2vox.AudialProxy.get_execution", side_effect=polls
    ), mock.patch("audial.functions.text2vox.time.sleep", return_value=None):
        text2vox(
            reference_file=audio_file,
            lyrics="a|ma|zing|grace",
            midi_file=str(midi),
            lyrics_mode="per_note",
            results_folder=str(tmp_path),
            on_progress=seen.append,
        )

    assert [warmup.state_of(record) for record in seen] == [None, "initializing", "done"]
    assert warmup.message(seen[1]) == COLD_SENTENCE


def test_a_progress_callback_that_raises_does_not_fail_the_job(audio_file, tmp_path):
    def explode(_status):
        raise RuntimeError("callback is buggy")

    with mock.patch(
        "audial.functions.sound2vital.AudialProxy.upload_execution_file",
        return_value={"filename": "kick.wav", "url": "https://storage.example/kick.wav"},
    ), mock.patch(
        "audial.functions.sound2vital.AudialProxy.run_sound2vital",
        return_value={"exeId": "exe-1", "state": "created"},
    ), mock.patch(
        "audial.functions.sound2vital.AudialProxy.get_execution",
        return_value=_execution("completed", warmup_state="done"),
    ), mock.patch("audial.functions.sound2vital.time.sleep", return_value=None):
        result = sound2vital(
            file_path=audio_file, results_folder=str(tmp_path), on_progress=explode
        )

    assert result["execution"]["state"] == "completed"
