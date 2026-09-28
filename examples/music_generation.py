"""Example: Generate music using the Audial SDK."""
import audial

# Basic text-to-music
result = audial.generate_music(
    prompt="upbeat electronic dance track with driving bass and ethereal synths",
    audio_duration=60,
    batch_size=2,
    audio_format="mp3",
)
print(f"Generated files: {list(result['files']['files'].keys())}")

# Cover mode (requires source audio)
# result = audial.generate_music(
#     prompt="jazz lounge style",
#     task_type="cover",
#     reference_file="path/to/original.mp3",
#     audio_cover_strength=0.7,
# )

# Understand mode (music-to-text analysis)
# result = audial.generate_music(
#     prompt="",
#     task_type="understand",
#     source_file="path/to/song.mp3",
# )
# print(f"Caption: {result['caption_result']}")
