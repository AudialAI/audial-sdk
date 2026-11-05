"""Example: a track's lyrics with word timings, laid out by section.

Lyrics are an add-on of an analysis: analyse the track, then ask for its
lyrics. Each line has a start and end, and each word is [word, start, end] in
seconds on the track's timeline, ready for a karaoke-style highlight.

    python examples/lyrics_lines.py [path/to/track.mp3]

Without a path it uses the demo track in test_audio/.
"""
import os
import sys

import audial

HERE = os.path.dirname(os.path.abspath(__file__))
track = (sys.argv[1] if len(sys.argv) > 1 else None) or os.environ.get("AUDIAL_EXAMPLE_AUDIO") or os.path.join(
    HERE, "..", "test_audio", "01 Operator (Original Mix) - 10A - 2.mp3"
)

analysis = audial.segment(track, expand_beats=False)
sections = analysis["audio_segmentation"]["sections"]

# Waits while the track's vocal stem is made in the background (409 STEMS_NOT_READY
# is retried for up to wait_s seconds), then for the lyrics themselves.
lyrics = audial.lyrics(analysis["analysis_id"])

if lyrics["is_instrumental"] or not lyrics["lines"]:
    print("No vocals in this track.")
    sys.exit(0)


def section_at(t):
    """The label of the section playing at time t."""
    label = None
    for section in sections:
        if t is not None and section["start"] <= t:
            label = section["label"]
    return label


current = None
for line in lyrics["lines"]:
    label = section_at(line["start"])
    if label != current:
        print(f"\n[{label}]")
        current = label
    words = "  ".join(f"{word[0]}@{word[1]:.2f}" for word in line["words"])
    print(f"{line['start'] or 0:7.2f}-{line['end'] or 0:<7.2f} {words}")

if lyrics["first_vocal_beat_time"] is not None:
    print(f"\nVocals start at {lyrics['first_vocal_beat_time']:.2f} s")
