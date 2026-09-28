"""Example: Turn a short audio clip into a Vital synth preset.

Requires an active Audial subscription (see API_DOCUMENTATION.md).
"""
import audial

result = audial.sound2vital("path/to/clip.wav")

print(f"Preset: {result.get('preset')}")
print(f"Downloaded files: {list(result['files']['files'].keys())}")

scores = result.get("scores")
if scores:
    print(f"Huang similarity: {scores.get('huang_similarity')}")
    print(f"At threshold ({scores.get('threshold')}): {scores.get('at_threshold')}")

warnings = result.get("warnings")
if warnings:
    print(f"Warnings: {warnings}")
