"""
Unit tests for audial.lyrics: the per-note lyric grammar.

Nothing here touches the network -- that is the point of the module: every
rule that can be checked without the MIDI file is checked before a request is
made.
"""

import pytest

from audial.api.exceptions import AudialError, AudialValidationError
from audial.lyrics import (
    EMPTY_MESSAGE,
    LEADING_HOLD_MESSAGE,
    Token,
    flat_lyrics,
    parse_per_note_lyrics,
    text2vox_tokens,
    validate_per_note_lyrics,
)

SUNG = False
HOLD = True


# ---------------------------------------------------------------------------
# The grammar table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        # A syllable per note, no holds.
        ("a|ma|zing|grace", [("a", SUNG), ("ma", SUNG), ("zing", SUNG), ("grace", SUNG)]),
        # The three written forms of a hold are the same thing.
        ("grace|-", [("grace", SUNG), ("", HOLD)]),
        ("grace|+", [("grace", SUNG), ("", HOLD)]),
        ("grace||", [("grace", SUNG), ("", HOLD), ("", HOLD)]),
        # A whole word spread over notes: the documented example.
        (
            "amazing|-|-|grace|-|how|sweet|the|sound",
            [
                ("amazing", SUNG), ("", HOLD), ("", HOLD),
                ("grace", SUNG), ("", HOLD),
                ("how", SUNG), ("sweet", SUNG), ("the", SUNG), ("sound", SUNG),
            ],
        ),
        # Whitespace around a token is ignored, including a whitespace-only
        # token (which is a hold, like an empty one).
        (" a | ma | zing ", [("a", SUNG), ("ma", SUNG), ("zing", SUNG)]),
        ("grace| ", [("grace", SUNG), ("", HOLD)]),
        # A single syllable is a valid one-note lyric.
        ("grace", [("grace", SUNG)]),
    ],
)
def test_parse_table(raw, expected):
    assert parse_per_note_lyrics(raw) == [Token(text, hold) for text, hold in expected]


@pytest.mark.parametrize(
    "a,b",
    [
        ("a|ma|zing|grace|-|how", "a|ma|zing|grace|+|how"),
        ("a|ma|zing|grace|-|how", "a|ma|zing|grace||how"),
    ],
)
def test_the_three_hold_spellings_are_one_lyric(a, b):
    assert parse_per_note_lyrics(a) == parse_per_note_lyrics(b)
    assert validate_per_note_lyrics(a) == validate_per_note_lyrics(b)


def test_token_count_is_the_note_count_required():
    tokens = text2vox_tokens("amazing|-|-|grace|-|how|sweet|the|sound")
    assert len(tokens) == 9
    assert sum(1 for token in tokens if not token.hold) == 6
    assert flat_lyrics(tokens) == "amazing grace how sweet the sound"


def test_parse_never_raises():
    # parse_ describes what was written; validate_ judges it.
    assert parse_per_note_lyrics("-|a") == [Token("", HOLD), Token("a", SUNG)]
    assert parse_per_note_lyrics("") == [Token("", HOLD)]
    assert parse_per_note_lyrics(None) == []


# ---------------------------------------------------------------------------
# What is rejected, with which message and position
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["-|a", "+|a", "|a", "-", " |grace", "-|-|grace"])
def test_a_hold_on_the_first_note_is_rejected(raw):
    with pytest.raises(AudialValidationError) as excinfo:
        validate_per_note_lyrics(raw)
    assert str(excinfo.value) == LEADING_HOLD_MESSAGE
    assert str(excinfo.value) == "note 1 has no syllable; the first note needs one"
    assert excinfo.value.position == 1


@pytest.mark.parametrize("raw", ["", "   ", "|", "|||", None])
def test_empty_lyrics_are_rejected(raw):
    with pytest.raises(AudialValidationError) as excinfo:
        validate_per_note_lyrics(raw)
    assert str(excinfo.value) == EMPTY_MESSAGE
    assert excinfo.value.position == 1


def test_validation_error_is_an_audial_error():
    # Callers that only catch AudialError keep working.
    with pytest.raises(AudialError):
        validate_per_note_lyrics("-|a")


def test_valid_lyrics_return_their_tokens():
    assert validate_per_note_lyrics("grace|-") == [Token("grace", SUNG), Token("", HOLD)]
