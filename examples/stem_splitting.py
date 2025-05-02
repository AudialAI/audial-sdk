import audial

# #Basic stems
# result = audial.stem_split(
#     "/Users/zachfarrell/Desktop/Coding_Projects/Audial-All Current Code/audial-sdk/test_audio/01 Operator (Original Mix) - 10A - 1.mp3",
#     stems=["vocals", "drums", "bass", "other"],
#     target_bpm=140,
#     target_key="Dmaj",
#     algorithm="primaudio"
# )

# More stems
result = audial.stem_split(
    "/Users/zachfarrell/Desktop/Coding_Projects/Audial-All Current Code/audial-sdk/test_audio/01 Operator (Original Mix) - 10A - 4.mp3",
    stems=["vocals", "drums", "bass", "other", "full_song_without_vocals", "full_song_without_drums", "full_song_without_bass", "full_song_without_other"],
    target_bpm=140,
    target_key="Dmaj",
    algorithm="primaudio"
)