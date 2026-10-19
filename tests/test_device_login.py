"""
Tests for browser sign-in (audial.api.device_login) and the credential resolution in
audial.utils.config. HTTP is mocked; nothing here touches a real API or the real home folder.
"""

import json
import os
import stat

import pytest

from audial.api import device_login
from audial.api.exceptions import AudialAuthError
from audial.utils import config

START = {
    "device_code": "dc", "user_code": "BCDF-GHJK",
    "verification_uri": "https://audialmusic.ai/activate",
    "verification_uri_complete": "https://audialmusic.ai/activate?code=BCDF-GHJK",
    "expires_in": 600, "interval": 0,
}
ISSUED = {"api_key": "aud_0123456789abcdef_" + "s" * 32, "user_id": "u1", "email": "a@b.c", "key_name": "Audial CLI on host"}


@pytest.fixture(autouse=True)
def signed_out(monkeypatch, tmp_path):
    """No credentials in the environment, and a private folder for the credentials file."""
    monkeypatch.delenv("AUDIAL_API_KEY", raising=False)
    monkeypatch.delenv("AUDIAL_USER_ID", raising=False)
    monkeypatch.setattr(config, "_get_config_file_path", lambda: tmp_path / config.CONFIG_FILE_NAME)
    monkeypatch.setattr(config, "_user_id_by_key", {})
    monkeypatch.setattr(device_login.time, "sleep", lambda _s: None)
    return tmp_path


def serve(monkeypatch, fake_response, replies):
    """Answer successive POSTs to the API with `replies` ((status, json) pairs)."""
    calls = []

    def post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers})
        status, data = replies[min(len(calls), len(replies)) - 1]
        return fake_response(status, data)

    monkeypatch.setattr(device_login.requests, "post", post)
    return calls


def test_login_saves_credentials_once_approved(monkeypatch, fake_response, signed_out):
    calls = serve(monkeypatch, fake_response, [
        (200, START), (400, {"error": "authorization_pending"}), (400, {"error": "slow_down"}), (200, ISSUED),
    ])
    shown = []
    credentials = device_login.login(client_name="audial-cli", open_browser=False, on_prompt=shown.append)

    assert shown[0].user_code == "BCDF-GHJK"
    assert calls[0]["url"].endswith("/auth/device/code")
    assert calls[0]["json"]["client_name"] == "audial-cli" and calls[0]["json"]["device_name"]
    assert [c["json"] for c in calls[1:]] == [{"device_code": "dc"}] * 3
    assert credentials["api_key"] == ISSUED["api_key"]

    path = signed_out / config.CREDENTIALS_FILE_NAME
    assert json.loads(path.read_text())["user_id"] == "u1"
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    # The SDK now uses the sign-in without any environment variable.
    assert config.get_api_key() == ISSUED["api_key"]
    assert config.get_user_id() == "u1"


@pytest.mark.parametrize("error", ["access_denied", "expired_token"])
def test_login_stops_when_refused_or_expired(monkeypatch, fake_response, error):
    serve(monkeypatch, fake_response, [(200, START), (400, {"error": error})])
    with pytest.raises(AudialAuthError):
        device_login.login(open_browser=False)
    assert config.load_credentials() is None


def test_wait_with_timeout_returns_none_and_keeps_the_sign_in_usable(monkeypatch, fake_response):
    serve(monkeypatch, fake_response, [(400, {"error": "authorization_pending"})])
    pending = device_login.DeviceLogin(**START)
    assert device_login.wait_for_device_login(pending, timeout=0) is None
    assert device_login.wait_for_device_login(pending, timeout=5, should_stop=lambda: True) is None


def test_environment_key_takes_priority_over_sign_in(monkeypatch):
    config.save_credentials(api_key=ISSUED["api_key"], user_id="u1")
    monkeypatch.setenv("AUDIAL_API_KEY", "legacy-key")
    monkeypatch.setenv("AUDIAL_USER_ID", "env-user")
    assert config.get_api_key() == "legacy-key"
    assert config.get_user_id() == "env-user"


def test_sign_in_is_not_used_for_a_different_api(monkeypatch):
    config.save_credentials(api_key=ISSUED["api_key"], user_id="u1")
    monkeypatch.setenv("AUDIAL_API_BASE_URL", "http://localhost:3000/api")
    assert config.load_credentials() is None
    assert config.get_api_key() is None


def test_new_format_key_needs_no_user_id(monkeypatch, fake_response):
    """AUDIAL_API_KEY=aud_... alone is enough: the user id is asked from the API, once."""
    lookups = []

    def get(url, headers=None, timeout=None):
        lookups.append(headers["x-api-key"])
        return fake_response(200, {"user_id": "u9", "email": None})

    monkeypatch.setattr(device_login.requests, "get", get)
    monkeypatch.setenv("AUDIAL_API_KEY", "aud_fedcba9876543210_" + "k" * 32)
    assert config.get_user_id() == "u9"
    assert config.get_user_id() == "u9"
    assert len(lookups) == 1


def test_logout_revokes_the_key_and_forgets_it(monkeypatch, fake_response):
    assert device_login.logout() is False
    config.save_credentials(api_key=ISSUED["api_key"], user_id="u1")
    calls = serve(monkeypatch, fake_response, [(200, {"status": "revoked"})])
    assert device_login.logout() is True
    assert calls[0]["url"].endswith("/auth/revoke") and calls[0]["headers"]["x-api-key"] == ISSUED["api_key"]
    assert config.load_credentials() is None
