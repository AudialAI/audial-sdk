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

# 1. The analysis: sections, the tempo map and the key (analysis format 5).
analysis = audial.segment(track, genre="Tech House")
analysis_id = analysis["analysis_id"]
data = analysis["analysis"]

print(f"\nAnalysis {analysis_id}: {data.get('bpm')} BPM, key {data.get('key')} ({data.get('camelot')})")
for section in data["sections"]:
    print(f"  {section['start']:7.2f} s  {section['label']:8} bar {section['start_bar']}, {section['bars']} bars")

# Beats and bars come from the tempo map (`grid`); audial.grid reads any analysis.
beats, bars = audial.grid.beats_of(data)
print(f"{len(beats)} beats, {len(bars)} bars" + (f"; bar 1 at {bars[0]:.2f} s" if bars else ""))

# 2. Audio features: energy, danceability and loudness for the song and per section, mode and tatum.
features = audial.audio_features(analysis_id)
song = features["features"]
print(f"\nKey {features.get('key')}, mode {song.get('mode')}, loudness {song.get('loudness_lufs')} LUFS")
for section in features["sections"]:
    energy = section.get("energy")
    print(f"  {str(section.get('label')):8} energy " + (f"{energy:.0%}" if energy is not None else "-"))

# 3. Tags: genres, instruments, moods and a written description. They read the analysis's stems, which
#    are made in the background; the call waits until they are ready.
tags = audial.tags(analysis_id)
print("\n" + (tags["description"] or "No description."))
print("Genres:", ", ".join(tags["genres"]) or "-")  # genres are ready to show as they are
print("Moods:", ", ".join(tags["moods"]) or "-")
for part, part_tags in tags["stems"].items():
    print(f"  {part}:", "silent" if part_tags.get("silent") else ", ".join(part_tags["instruments"]) or "-")
