import audial

# Generate MIDI from a single file
# result = audial.generate_midi(
#     "/Users/zachfarrell/Desktop/Coding_Projects/Audial-All Current Code/audial-sdk/test_audio/01 Operator (Original Mix) - 10A - 7.mp3",
#     bpm=140
# )

# Example with multiple files
result = audial.generate_midi(
    [
        "/Users/zachfarrell/Desktop/Coding_Projects/Audial-All Current Code/audial-sdk/test_audio/01 Operator (Original Mix) - 10A - 6.mp3",
        "/Users/zachfarrell/Desktop/Coding_Projects/Audial-All Current Code/audial-sdk/test_audio/01 Operator (Original Mix) - 10A - 7.mp3"
    ],
    bpm=140
)