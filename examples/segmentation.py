"""Example: analyse a track, then add audio features and tags.

Analysis finds the track's sections, tempo and bars in about half a minute,
from the mix alone. Audio features and tags are added afterwards, one call
each, on the analysis id; they are included with the analysis.

    python examples/segmentation.py [path/to/track.mp3]

Without a path it uses the demo track in test_audio/.
"""
import os
import sys

import audial

HERE = os.path.dirname(os.path.abspath(__file__))
track = (sys.argv[1] if len(sys.argv) > 1 else None) or os.environ.get("AUDIAL_EXAMPLE_AUDIO") or os.path.join(
    HERE, "..", "test_audio", "01 Operator (Original Mix) - 10A - 2.mp3"
)

# 1. The analysis: sections, phrases and the tempo map.
# expand_beats=False: read beats from the tempo map with audial.grid (how 2.0 works).
analysis = audial.segment(track, genre="Tech House", expand_beats=False)
analysis_id = analysis["analysis_id"]
data = analysis["audio_segmentation"]

print(f"\nAnalysis {analysis_id}: {data.get('bpm')} BPM")
for section in data["sections"]:
    print(f"  {section['start']:7.2f} s  {section['label']}")

# Beats and bars come from the tempo map (`grid`); audial.grid reads any analysis.
beats, bars = audial.grid.beats_of(data)
print(f"{len(beats)} beats, {len(bars)} bars" + (f"; bar 1 at {bars[0]:.2f} s" if bars else ""))

# 2. Audio features: energy, danceability, loudness, mode and key, per song and per section.
features = audial.audio_features(analysis_id)
song = features["song"]
print(f"\nKey {song.get('key')}, loudness {song.get('loudness')} LUFS")
for section in features["sections"]:
    energy = section.get("energy")
    print(f"  {str(section.get('label')):8} energy " + (f"{energy:.0%}" if energy is not None else "-"))

# 3. Tags: genre, moods and instruments. They read the analysis's stems, which are
#    made in the background; the call waits until they are ready.
tags = audial.tags(analysis_id)
print("\nGenre:", ", ".join(genre.split("---")[-1] for genre in tags["genre"]) or "-")
print("Moods:", ", ".join(tags["song_tags"]["full"]["moods"]) or "-")
