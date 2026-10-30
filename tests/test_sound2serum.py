"""
Unit tests for audial.functions.sound2serum and its proxy/HTTP layer.

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
from audial.functions.sound2serum import sound2serum


# ---------------------------------------------------------------------------
# AudialProxy.upload_execution_file
#
# Mirrors tests/test_sound2vital.py -- upload_execution_file isn't specific
# to either function, but the plan calls for mirroring every test.
# ---------------------------------------------------------------------------

def test_upload_execution_file_sanitizes_filename_and_url(audio_file, fake_response):
    proxy = AudialProxy()
    proxy.session.put = mock.MagicMock(
        return_value=fake_response(200, {"url": "https://storage.example/my_song__final__v2.wav"})
    )

    result = proxy.upload_execution_file(audio_file, "upload-placeholder-id", "reference")

    # Filename sanitized to [A-Za-z0-9_-] stem + lowercase extension.
    assert result["filename"] == "My_Song__Final__v2.wav"
    assert result["url"] == "https://storage.example/my_song__final__v2.wav"

    called_url = proxy.session.put.call_args.args[0]
    assert called_url == (
        f"{proxy.base_url}/files/test-user-id/execution/upload-placeholder-id/reference/My_Song__Final__v2.wav"
    )

    # Multipart field also carries the sanitized filename.
    files_arg = proxy.session.put.call_args.kwargs["files"]
    assert files_arg["file"][0] == "My_Song__Final__v2.wav"


def test_upload_execution_file_missing_file_raises(fake_response, tmp_path):
    proxy = AudialProxy()
    proxy.session.put = mock.MagicMock()

    with pytest.raises(FileNotFoundError):
        proxy.upload_execution_file(str(tmp_path / "does-not-exist.wav"), "exe-id", "reference")

    proxy.session.put.assert_not_called()


def test_upload_execution_file_402_raises_subscription_required(audio_file, fake_response):
    proxy = AudialProxy()
    proxy.session.put = mock.MagicMock(
        return_value=fake_response(
            402, {"error": "This feature needs an active Audial subscription.", "code": "SUBSCRIPTION_REQUIRED"}
        )
    )

    with pytest.raises(SubscriptionRequiredError) as excinfo:
        proxy.upload_execution_file(audio_file, "exe-id", "reference")

    assert excinfo.value.status_code == 402


# ---------------------------------------------------------------------------
# AudialProxy.run_sound2serum
# ---------------------------------------------------------------------------

def test_run_sound2serum_request_body(fake_response):
    proxy = AudialProxy()
    proxy.session.post = mock.MagicMock(
        return_value=fake_response(200, {"exeId": "exe-123", "state": "created"})
    )

    response = proxy.run_sound2serum({"filename": "clip.wav", "url": "https://storage.example/clip.wav"})

    assert response == {"exeId": "exe-123", "state": "created"}
    called_url = proxy.session.post.call_args.args[0]
    assert called_url == f"{proxy.base_url}/functions/run/sound2serum"
    body = proxy.session.post.call_args.kwargs["json"]
    assert body == {
        "userId": "test-user-id",
        "original": {"filename": "clip.wav", "url": "https://storage.example/clip.wav"},
    }


def test_run_sound2serum_402_raises_subscription_required(fake_response):
    proxy = AudialProxy()
    proxy.session.post = mock.MagicMock(
        return_value=fake_response(
            402,
            {
                "error": "This feature needs an active Audial subscription. Subscribe at audialmusic.ai and try again.",
                "code": "SUBSCRIPTION_REQUIRED",
            },
        )
    )

    with pytest.raises(SubscriptionRequiredError) as excinfo:
        proxy.run_sound2serum({"filename": "clip.wav", "url": "https://storage.example/clip.wav"})

    assert excinfo.value.status_code == 402
    assert "subscription" in str(excinfo.value).lower()


def test_run_sound2serum_401_raises_auth_error(fake_response):
    from audial.api.exceptions import AudialAuthError

    proxy = AudialProxy()
    proxy.session.post = mock.MagicMock(return_value=fake_response(401, {"error": "Invalid API key"}))

    with pytest.raises(AudialAuthError):
        proxy.run_sound2serum({"filename": "clip.wav", "url": "https://storage.example/clip.wav"})


# ---------------------------------------------------------------------------
# sound2serum() end-to-end orchestration (submit / poll / download)
# ---------------------------------------------------------------------------

def _completed_execution():
    return {
        "exeId": "exe-123",
        "state": "completed",
        "preset": {
            "presetSerumPreset": {"filename": "preset.SerumPreset", "url": "https://storage.example/preset.SerumPreset"}
        },
        "generated": {
            "renderwav": {"filename": "render.wav", "url": "https://storage.example/render.wav"},
            "keyboard_48wav": {"filename": "keyboard_48.wav", "url": "https://storage.example/keyboard_48.wav"},
        },
        "generation_metadata": {
            "scores": {"huang_similarity": 0.92, "at_threshold": True, "threshold": 0.8, "model": "v3"},
            "report": {"notes": "ok"},
            "warnings": [],
        },
    }


def test_sound2serum_polls_to_completed_and_downloads(audio_file, tmp_path):
    downloaded = []

    with mock.patch(
        "audial.functions.sound2serum.AudialProxy.upload_execution_file",
        return_value={"filename": "clip.wav", "url": "https://storage.example/clip.wav", "type": "audio/wav"},
    ) as mock_upload, mock.patch(
        "audial.functions.sound2serum.AudialProxy.run_sound2serum",
        return_value={"exeId": "exe-123", "state": "created"},
    ) as mock_run, mock.patch(
        "audial.functions.sound2serum.AudialProxy.get_execution",
        side_effect=[{"exeId": "exe-123", "state": "processing"}, _completed_execution()],
    ) as mock_get, mock.patch(
        "audial.functions.sound2serum.download_file",
        side_effect=lambda url, dest: downloaded.append((url, dest)) or dest,
    ), mock.patch("audial.functions.sound2serum.time.sleep", return_value=None):
        result = sound2serum(audio_file, results_folder=str(tmp_path))

    mock_upload.assert_called_once()
    mock_run.assert_called_once()
    assert mock_get.call_count == 2

    # Serum shows the file name as the preset name, so the SDK renames the
    # downloaded preset to <source file stem>.SerumPreset.
    source_stem = os.path.splitext(os.path.basename(audio_file))[0]
    expected_name = f"{source_stem}.SerumPreset"

    assert result["execution"]["state"] == "completed"
    assert result["preset"].endswith(expected_name)
    assert set(result["files"]["files"].keys()) == {expected_name, "render.wav", "keyboard_48.wav"}
    assert result["scores"]["huang_similarity"] == 0.92
    assert result["report"] == {"notes": "ok"}
    assert result["warnings"] == []
    assert len(downloaded) == 3


def test_sound2serum_falls_back_to_any_serumpreset_entry(audio_file, tmp_path):
    """If the preset isn't under `presetSerumPreset`, fall back to any entry
    whose filename ends in .SerumPreset."""
    execution = _completed_execution()
    execution["preset"] = {
        "somethingElse": {"filename": "preset.SerumPreset", "url": "https://storage.example/preset.SerumPreset"}
    }

    with mock.patch(
        "audial.functions.sound2serum.AudialProxy.upload_execution_file",
        return_value={"filename": "clip.wav", "url": "https://storage.example/clip.wav", "type": "audio/wav"},
    ), mock.patch(
        "audial.functions.sound2serum.AudialProxy.run_sound2serum",
        return_value={"exeId": "exe-123", "state": "created"},
    ), mock.patch(
        "audial.functions.sound2serum.AudialProxy.get_execution",
        return_value=execution,
    ), mock.patch(
        "audial.functions.sound2serum.download_file",
        side_effect=lambda url, dest: dest,
    ), mock.patch("audial.functions.sound2serum.time.sleep", return_value=None):
        result = sound2serum(audio_file, results_folder=str(tmp_path))

    source_stem = os.path.splitext(os.path.basename(audio_file))[0]
    assert result["preset"].endswith(f"{source_stem}.SerumPreset")


def test_sound2serum_failed_state_raises(audio_file, tmp_path):
    with mock.patch(
        "audial.functions.sound2serum.AudialProxy.upload_execution_file",
        return_value={"filename": "clip.wav", "url": "https://storage.example/clip.wav", "type": "audio/wav"},
    ), mock.patch(
        "audial.functions.sound2serum.AudialProxy.run_sound2serum",
        return_value={"exeId": "exe-123", "state": "created"},
    ), mock.patch(
        "audial.functions.sound2serum.AudialProxy.get_execution",
        return_value={"exeId": "exe-123", "state": "failed", "error": "Input is 25.0 s; the limit is 20 s"},
    ), mock.patch("audial.functions.sound2serum.time.sleep", return_value=None):
        with pytest.raises(AudialAPIError) as excinfo:
            sound2serum(audio_file, results_folder=str(tmp_path))

    assert "Input is 25.0 s" in str(excinfo.value)


def test_sound2serum_missing_file_raises_before_any_upload(tmp_path):
    with mock.patch("audial.functions.sound2serum.AudialProxy.upload_execution_file") as mock_upload:
        with pytest.raises(AudialError):
            sound2serum(str(tmp_path / "nope.wav"), results_folder=str(tmp_path))
    mock_upload.assert_not_called()


def test_sound2serum_402_propagates_as_subscription_required(audio_file, tmp_path):
    with mock.patch(
        "audial.functions.sound2serum.AudialProxy.upload_execution_file",
        return_value={"filename": "clip.wav", "url": "https://storage.example/clip.wav", "type": "audio/wav"},
    ), mock.patch(
        "audial.functions.sound2serum.AudialProxy.run_sound2serum",
        side_effect=SubscriptionRequiredError(response=None),
    ):
        with pytest.raises(SubscriptionRequiredError):
            sound2serum(audio_file, results_folder=str(tmp_path))


# ---------------------------------------------------------------------------
# AUDIAL_API_BASE_URL override
# ---------------------------------------------------------------------------

def test_env_override_base_url_used_by_proxy(monkeypatch, fake_response):
    monkeypatch.setenv("AUDIAL_API_BASE_URL", "https://staging.audial.test/api")

    assert get_api_base_url() == "https://staging.audial.test/api"

    proxy = AudialProxy()
    assert proxy.base_url == "https://staging.audial.test/api"
    assert proxy.auth_endpoint == "https://staging.audial.test/api/proxy"

    proxy.session.post = mock.MagicMock(return_value=fake_response(200, {"exeId": "exe-1", "state": "created"}))
    proxy.run_sound2serum({"filename": "clip.wav", "url": "https://storage.example/clip.wav"})

    called_url = proxy.session.post.call_args.args[0]
    assert called_url == "https://staging.audial.test/api/functions/run/sound2serum"


def test_env_override_base_url_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("AUDIAL_API_BASE_URL", "https://staging.audial.test/api/")
    assert get_api_base_url() == "https://staging.audial.test/api"


def test_default_base_url_when_env_unset():
    assert get_api_base_url() == "https://api.audialmusic.ai/api"
    proxy = AudialProxy()
    assert proxy.base_url == "https://api.audialmusic.ai/api"
