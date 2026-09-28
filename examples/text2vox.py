"""Example: Sing lyrics in the timbre of a reference voice clip.

Requires an active Audial subscription (see API_DOCUMENTATION.md).
Exactly one of midi_file / melody_audio_file must be given.
"""
import audial

# Driven by a MIDI file
result = audial.text2vox(
    reference_file="path/to/voice_clip.wav",
    lyrics="la la la la",
    midi_file="path/to/melody.mid",
)
print(f"Generated files: {list(result['files']['files'].keys())}")

# Driven by melody audio instead, with pipe-delimited per-note lyrics
# result = audial.text2vox(
#     reference_file="path/to/voice_clip.wav",
#     lyrics="la|la|la|la",
#     melody_audio_file="path/to/melody.wav",
#     lyrics_mode="per_note",
# )

metadata = result.get("metadata")
if metadata:
    print(f"Duration: {metadata.get('duration_s')}s, sample rate: {metadata.get('sample_rate')}")
