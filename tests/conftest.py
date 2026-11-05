"""
Shared pytest fixtures for the Audial SDK test suite.
"""

import json
import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "dev: runs against the Audial dev API (real runs); skipped unless selected with -m dev",
    )


def pytest_collection_modifyitems(config, items):
    """`dev` tests make real API calls: they run only when `-m dev` asks for them."""
    if "dev" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="dev API test: run with `pytest -m dev`")
    for item in items:
        if item.get_closest_marker("dev") is not None:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def audial_env(monkeypatch):
    """
    Give every test a working API key / user id via environment variables
    (config.py checks these before falling back to the on-disk config file),
    and make sure AUDIAL_API_BASE_URL starts unset so each test controls it
    explicitly.
    """
    monkeypatch.setenv("AUDIAL_API_KEY", "test-api-key")
    monkeypatch.setenv("AUDIAL_USER_ID", "test-user-id")
    monkeypatch.delenv("AUDIAL_API_BASE_URL", raising=False)
    yield


class FakeResponse:
    """Minimal stand-in for requests.Response used across the test suite."""

    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text or json.dumps(self._json_data)

    def json(self):
        return self._json_data


@pytest.fixture
def fake_response():
    return FakeResponse


@pytest.fixture
def audio_file(tmp_path):
    """A dummy input audio file whose content is irrelevant -- upload calls
    are mocked, so only its existence/path matters."""
    path = tmp_path / "My Song [Final] v2.WAV"
    path.write_bytes(b"RIFF....WAVEfmt ")
    return str(path)
