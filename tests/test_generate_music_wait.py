import inspect
from audial.functions.generate_music import generate_music
from audial.functions.midi import generate_midi


def test_generate_music_exposes_max_wait():
    params = inspect.signature(generate_music).parameters
    assert params["max_wait"].default == 900
    assert params["poll_interval"].default == 5


def test_generate_midi_exposes_max_wait():
    params = inspect.signature(generate_midi).parameters
    assert params["max_wait"].default == 900
