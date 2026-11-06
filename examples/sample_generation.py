"""Example: make a sample pack, from a file or from an analysis.

From a file, one call runs the sample-pack pipeline: the analysis and the
stems start together, then the pack is built from them.

From an analysis you already have, the pack reuses that analysis's stems and
sections, so nothing is analysed or split again, and it is included with the
analysis.

    python examples/sample_generation.py [path/to/track.mp3]

Without a path it uses the demo track in test_audio/.
"""
import os
import sys

import audial

HERE = os.path.dirname(os.path.abspath(__file__))
track = (sys.argv[1] if len(sys.argv) > 1 else None) or os.environ.get("AUDIAL_EXAMPLE_AUDIO") or os.path.join(
    HERE, "..", "test_audio", "01 Operator (Original Mix) - 10A - 8.mp3"
)

# 1. From a file: one call, counted as one run.
result = audial.generate_samples(
    track,
    components=["drums", "bass", "melody"],
    genre="Tech House",
)
print(f"{len(result['files']['files'])} samples in {result['files']['folder']}")

# 2. From an analysis: the analysis counts once, and the pack is included with it.
analysis = audial.segment(track, genre="Tech House", expand_beats=False)
pack = audial.generate_samples(analysis_id=analysis["analysis_id"], components=["drums", "bass"])
print(f"{len(pack['files']['files'])} samples in {pack['files']['folder']}")
for part, report in pack["components"].items():
    print(f"  {part}: {report.get('status')}")
