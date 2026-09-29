import inspect
from unittest.mock import MagicMock, patch

import pytest

from audial.api.exceptions import AudialAPIError
from audial.functions import midi as midi_module
from audial.functions.generate_music import generate_music
from audial.functions.midi import generate_midi


def test_generate_music_exposes_max_wait():
    params = inspect.signature(generate_music).parameters
    assert params["max_wait"].default == 900
    assert params["poll_interval"].default == 5


def test_generate_midi_exposes_max_wait():
    params = inspect.signature(generate_midi).parameters
    assert params["max_wait"].default == 900


def test_generate_midi_raises_audial_api_error_on_timeout(tmp_path):
    """generate_midi's poll loop must raise AudialAPIError (not AudialError)
    once max_wait elapses, with a message containing 'timed out after {max_wait}s'.
    """
    mock_proxy = MagicMock()
    mock_proxy.create_execution.return_value = {"exeId": "exe-test"}
    mock_proxy.upload_file.return_value = {
        "filename": "f.wav",
        "url": "http://example.com/f.wav",
    }
    # No 'midi' key -> has_midi_data() is False, so the poll loop is entered.
    mock_proxy.run_generate_midi.return_value = {}
    mock_proxy.get_execution.return_value = {"state": "running"}

    # First call to time.time() is start_time; every call after that reports
    # 0.02s elapsed, which is past max_wait=0.01 -- so the very first
    # iteration of the poll loop hits the timeout branch without any real
    # waiting (time.sleep is never reached).
    call_count = {"n": 0}

    def fake_time():
        call_count["n"] += 1
        return 1000.0 if call_count["n"] == 1 else 1000.02

    with patch.object(midi_module, "AudialProxy", return_value=mock_proxy), \
         patch.object(midi_module.time, "time", side_effect=fake_time):
        with pytest.raises(AudialAPIError, match=r"timed out after 0\.01s"):
            midi_module.generate_midi(
                "fake_source.wav",
                results_folder=str(tmp_path),
                api_key="test-key",
                max_wait=0.01,
            )
