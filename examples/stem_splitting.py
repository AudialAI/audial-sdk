import audial

result = audial.stem_split(
    "/Users/zachfarrell/Desktop/Coding_Projects/Audial-All Current Code/audial-sdk/test_audio/01 Operator (Original Mix) - 10A - 2.mp3",
    stems=["vocals", "drums", "bass", "other"],
    target_bpm=140,
    target_key="Dmaj",
    algorithm="primaudio"
)