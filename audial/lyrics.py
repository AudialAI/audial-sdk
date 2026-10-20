"""
Per-note lyrics: the pipe-delimited string ``lyrics_mode="per_note"`` takes.

In per-note mode the lyrics are one token per MIDI note, pipe-delimited, and
there is exactly one concept beyond "a syllable on a note": a **hold**, which
means "keep singing the previous syllable through this note".

    ===========  ===================================================
    token        meaning
    ===========  ===================================================
    ``grace``    sung on this note
    ``-``        hold: continue the previous syllable through this
                 note (the documented form)
    ``+``        hold too (Synthesizer V habit)
    empty        hold too (what a double pipe ``||`` produces)
    ===========  ===================================================

A token may be a whole word spread over several notes::

    amazing|-|-|grace|-|how|sweet|the|sound

There is no rest token: a note that should be silent should not be in the MIDI
at all. Held notes are merged into their predecessor before synthesis and the
pitch movement is kept as a bend, so the sung line follows the drawn melody.

Rules: the token count must equal the MIDI note count, and the first token
must be a syllable. ``validate_per_note_lyrics`` checks everything that can be
checked without the MIDI file (the SDK does not parse MIDI); the count is
checked by the worker, which has the notes, and reported as
``AudialValidationError`` by way of the API's ``LYRICS_INVALID`` response.

``audial.text2vox`` runs this validation itself before it uploads anything, so
a bad lyric string costs no uploads and creates no execution.
"""

from typing import List, NamedTuple

from audial.api.exceptions import AudialValidationError

__all__ = [
    "Token",
    "HOLD_TOKENS",
    "parse_per_note_lyrics",
    "validate_per_note_lyrics",
    "text2vox_tokens",
    "flat_lyrics",
]

# Written forms of a hold. An empty token (a double pipe, or a trailing pipe)
# is a hold as well; it is not in this set because it is tested by emptiness.
HOLD_TOKENS = ("-", "+")

# The separator between tokens. Not configurable: it is the API's.
SEPARATOR = "|"

EMPTY_MESSAGE = "no syllables provided"

LEADING_HOLD_MESSAGE = "note 1 has no syllable; the first note needs one"


class Token(NamedTuple):
    """One per-note lyric token.

    Attributes:
        text: The syllable sung on this note. Empty for a hold.
        hold: True when this note continues the previous syllable instead of
            starting a new one.
    """

    text: str
    hold: bool


def parse_per_note_lyrics(raw: str) -> List[Token]:
    """
    Split a per-note lyric string into typed tokens.

    Forgiving on purpose: ``-``, ``+`` and an empty token all mean the same
    hold, and surrounding whitespace in a token is ignored, so the three
    strings below parse identically::

        audial.lyrics.parse_per_note_lyrics("a|ma|zing|grace|-|how")
        audial.lyrics.parse_per_note_lyrics("a|ma|zing|grace|+|how")
        audial.lyrics.parse_per_note_lyrics("a|ma|zing|grace||how")

    This function does not raise: it describes what was written. Use
    ``validate_per_note_lyrics`` (or just call ``audial.text2vox``) to have
    unusable input rejected.

    Args:
        raw (str): The pipe-delimited lyrics.

    Returns:
        List[Token]: One token per note, in order.
    """
    if raw is None:
        return []
    tokens: List[Token] = []
    for piece in str(raw).split(SEPARATOR):
        text = piece.strip()
        if not text or text in HOLD_TOKENS:
            tokens.append(Token("", True))
        else:
            tokens.append(Token(text, False))
    return tokens


def validate_per_note_lyrics(raw: str) -> List[Token]:
    """
    Parse per-note lyrics and reject what cannot be sung.

    Checked here (no MIDI needed):

    * the string has to contain at least one token -- empty or whitespace-only
      lyrics are rejected;
    * the first token has to be a syllable, because a hold continues something
      and there is nothing before note 1.

    Checked by the worker, which has the MIDI: the token count must equal the
    note count. That failure comes back from the API as
    ``AudialValidationError`` too, with the same wording and a position.

    Args:
        raw (str): The pipe-delimited lyrics.

    Returns:
        List[Token]: The parsed tokens, when they are usable.

    Raises:
        AudialValidationError: With ``position`` set to the 1-based index of
            the offending note.
    """
    if raw is None or not str(raw).strip(SEPARATOR + " \t\r\n"):
        raise AudialValidationError(EMPTY_MESSAGE, position=1)

    tokens = parse_per_note_lyrics(raw)
    if not tokens:
        raise AudialValidationError(EMPTY_MESSAGE, position=1)
    if tokens[0].hold:
        raise AudialValidationError(LEADING_HOLD_MESSAGE, position=1)
    return tokens


def text2vox_tokens(lyrics: str) -> List[Token]:
    """
    The tokens ``audial.text2vox(..., lyrics_mode="per_note")`` will send.

    Exposed as ``audial.text2vox_tokens``: it answers "how many notes does
    this lyric string need, and which of them are holds?" before a render is
    started, and raises the same ``AudialValidationError`` that ``text2vox``
    would raise::

        tokens = audial.text2vox_tokens("amazing|-|-|grace|-|how|sweet")
        len(tokens)                                  # notes required: 7
        sum(1 for t in tokens if not t.hold)         # syllables sung: 4

    Args:
        lyrics (str): The pipe-delimited per-note lyrics.

    Returns:
        List[Token]: One token per note.

    Raises:
        AudialValidationError: If the lyrics cannot be sung as written.
    """
    return validate_per_note_lyrics(lyrics)


def flat_lyrics(tokens: List[Token]) -> str:
    """
    The sung syllables only, space-joined -- the lyrics without the holds.

    Args:
        tokens (List[Token]): Tokens from ``parse_per_note_lyrics``.

    Returns:
        str: e.g. "amazing grace how sweet the sound".
    """
    return " ".join(token.text for token in tokens if not token.hold)
