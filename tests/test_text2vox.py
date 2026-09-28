"""
Unit tests for audial.functions.text2vox and its proxy/HTTP layer.

The HTTP layer (requests.Session methods on AudialProxy, and
audial.utils.file_utils.download_file) is mocked throughout via
unittest.mock -- no real network calls are made.
"""

import os
from unittest import mock

import pytest

from audial.api.constants import get_api_base_url
from audial.api.exceptions import AudialAPIError, AudialError, SubscriptionRequiredError
from audial.api.proxy import AudialProxy
from audial.functions.text2vox import text2vox


@pytest.fixture
def midi_file(tmp_path):
    path = tmp_path / "melody (draft) #2.mid"
    path.write_bytes(b"MThd")
    return str(path)


# ---------------------------------------------------------------------------
# Client-side validation
# ---------------------------------------------------------------------------

def test_requires_exactly_one_of_midi_or_melody_audio(audio_file, midi_file, tmp_path):
    # Neither given.
    with pytest.raises(AudialError):
        text2vox(reference_file=audio_file, lyrics="la la la", results_folder=str(tmp_path))

    # Both given.
    melody_path = tmp_path / "melody.wav"
    melody_path.write_bytes(b"RIFF")
    with pytest.raises(AudialError):
        text2vox(
            reference_file=audio_file,
            lyrics="la la la",
            midi_file=midi_file,
            melody_audio_file=str(melody_path),
            results_folder=str(tmp_path),
        )


def test_requires_nonempty_lyrics(audio_file, midi_file, tmp_path):
    with pytest.raises(AudialError):
        text2vox(reference_file=audio_file, lyrics="", midi_file=midi_file, results_folder=str(tmp_path))


def test_rejects_invalid_lyrics_mode(audio_file, midi_file, tmp_path):
    with pytest.raises(AudialError):
        text2vox(
            reference_file=audio_file,
            lyrics="la la la",
            midi_file=midi_file,
            lyrics_mode="not-a-real-mode",
            results_folder=str(tmp_path),
        )


def test_missing_reference_file_raises(midi_file, tmp_path):
    with mock.patch("audial.functions.text2vox.AudialProxy.upload_execution_file") as mock_upload:
        with pytest.raises(AudialError):
            text2vox(
                reference_file=str(tmp_path / "nope.wav"),
                lyrics="la la la",
                midi_file=midi_file,
                results_folder=str(tmp_path),
            )
    mock_upload.assert_not_called()


# ---------------------------------------------------------------------------
# AudialProxy.upload_execution_file (filename sanitizing, shared with sound2vital)
# ---------------------------------------------------------------------------

def test_upload_execution_file_sanitizes_midi_filename(midi_file, fake_response):
    proxy = AudialProxy()
    proxy.session.put = mock.MagicMock(
        return_value=fake_response(200, {"url": "https://storage.example/melody_draft_2.mid"})
    )

    result = proxy.upload_execution_file(midi_file, "upload-placeholder-id", "midi")

    assert result["filename"] == "melody__draft___2.mid"
    called_url = proxy.session.put.call_args.args[0]
    assert called_url.endswith("/execution/upload-placeholder-id/midi/melody__draft___2.mid")


# ---------------------------------------------------------------------------
# AudialProxy.run_text2vox
# ---------------------------------------------------------------------------

def test_run_text2vox_request_body(fake_response):
    proxy = AudialProxy()
    proxy.session.post = mock.MagicMock(
        return_value=fake_response(200, {"exeId": "exe-456", "state": "created"})
    )

    response = proxy.run_text2vox(
        original_file={"filename": "voice.wav", "url": "https://storage.example/voice.wav"},
        lyrics="la la la",
        lyrics_mode="auto",
        midi_file={"filename": "song.mid", "url": "https://storage.example/song.mid"},
        seed=2025,
    )

    assert response == {"exeId": "exe-456", "state": "created"}
    called_url = proxy.session.post.call_args.args[0]
    assert called_url == f"{proxy.base_url}/functions/run/text2vox"
    body = proxy.session.post.call_args.kwargs["json"]
    assert body == {
        "userId": "test-user-id",
        "original": {"filename": "voice.wav", "url": "https://storage.example/voice.wav"},
        "text2vox": {
            "lyrics": "la la la",
            "lyricsMode": "auto",
            "midi": {"filename": "song.mid", "url": "https://storage.example/song.mid"},
            "options": {"seed": 2025},
        },
    }


def test_run_text2vox_402_raises_subscription_required(fake_response):
    proxy = AudialProxy()
    proxy.session.post = mock.MagicMock(
        return_value=fake_response(402, {"error": "Subscribe to use text2vox.", "code": "SUBSCRIPTION_REQUIRED"})
    )

    with pytest.raises(SubscriptionRequiredError) as excinfo:
        proxy.run_text2vox(
            original_file={"filename": "voice.wav", "url": "https://storage.example/voice.wav"},
            lyrics="la la la",
            midi_file={"filename": "song.mid", "url": "https://storage.example/song.mid"},
        )

    assert excinfo.value.status_code == 402


# ---------------------------------------------------------------------------
# text2vox() end-to-end orchestration (submit / poll / download)
# ---------------------------------------------------------------------------

def _completed_execution():
    return {
        "exeId": "exe-456",
        "state": "completed",
        "generated": {"songwav": {"filename": "song.wav", "url": "https://storage.example/song.wav"}},
        "midi": {"songmid": {"filename": "song.mid", "url": "https://storage.example/song.mid"}},
        "generation_metadata": {"duration_s": 12.3, "sample_rate": 44100, "warnings": []},
    }


def test_text2vox_polls_to_completed_and_downloads(audio_file, midi_file, tmp_path):
    downloaded = []

    with mock.patch(
        "audial.functions.text2vox.AudialProxy.upload_execution_file",
        side_effect=[
            {"filename": "voice.wav", "url": "https://storage.example/voice.wav", "type": "audio/wav"},
            {"filename": "song.mid", "url": "https://storage.example/song.mid", "type": "audio/midi"},
        ],
    ) as mock_upload, mock.patch(
        "audial.functions.text2vox.AudialProxy.run_text2vox",
        return_value={"exeId": "exe-456", "state": "created"},
    ) as mock_run, mock.patch(
        "audial.functions.text2vox.AudialProxy.get_execution",
        side_effect=[{"exeId": "exe-456", "state": "processing"}, _completed_execution()],
    ) as mock_get, mock.patch(
        "audial.functions.text2vox.download_file",
        side_effect=lambda url, dest: downloaded.append((url, dest)) or dest,
    ), mock.patch("audial.functions.text2vox.time.sleep", return_value=None):
        result = text2vox(
            reference_file=audio_file,
            lyrics="la la la",
            midi_file=midi_file,
            results_folder=str(tmp_path),
        )

    assert mock_upload.call_count == 2
    mock_run.assert_called_once()
    assert mock_get.call_count == 2

    assert result["execution"]["state"] == "completed"
    assert set(result["files"]["files"].keys()) == {"song.wav", "song.mid"}
    assert result["metadata"]["duration_s"] == 12.3
    assert result["warnings"] == []
    assert len(downloaded) == 2


def test_text2vox_failed_state_raises(audio_file, midi_file, tmp_path):
    with mock.patch(
        "audial.functions.text2vox.AudialProxy.upload_execution_file",
        return_value={"filename": "voice.wav", "url": "https://storage.example/voice.wav", "type": "audio/wav"},
    ), mock.patch(
        "audial.functions.text2vox.AudialProxy.run_text2vox",
        return_value={"exeId": "exe-456", "state": "created"},
    ), mock.patch(
        "audial.functions.text2vox.AudialProxy.get_execution",
        return_value={"exeId": "exe-456", "state": "failed", "error": "text2vox returned no wav"},
    ), mock.patch("audial.functions.text2vox.time.sleep", return_value=None):
        with pytest.raises(AudialAPIError) as excinfo:
            text2vox(
                reference_file=audio_file,
                lyrics="la la la",
                midi_file=midi_file,
                results_folder=str(tmp_path),
            )

    assert "text2vox returned no wav" in str(excinfo.value)


# ---------------------------------------------------------------------------
# AUDIAL_API_BASE_URL override
# ---------------------------------------------------------------------------

def test_env_override_base_url_used_by_proxy(monkeypatch, fake_response):
    monkeypatch.setenv("AUDIAL_API_BASE_URL", "https://staging.audial.test/api")

    assert get_api_base_url() == "https://staging.audial.test/api"

    proxy = AudialProxy()
    assert proxy.base_url == "https://staging.audial.test/api"

    proxy.session.post = mock.MagicMock(return_value=fake_response(200, {"exeId": "exe-1", "state": "created"}))
    proxy.run_text2vox(
        original_file={"filename": "voice.wav", "url": "https://storage.example/voice.wav"},
        lyrics="la la la",
        midi_file={"filename": "song.mid", "url": "https://storage.example/song.mid"},
    )

    called_url = proxy.session.post.call_args.args[0]
    assert called_url == "https://staging.audial.test/api/functions/run/text2vox"
