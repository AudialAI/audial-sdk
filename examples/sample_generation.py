import audial

result = audial.generate_samples(
    "/Users/zachfarrell/Desktop/Coding_Projects/Audial-All Current Code/audial-sdk/test_audio/01 Operator (Original Mix) - 10A - 8.mp3",
    job_type="sample_pack",
    components=["drums", "bass", "melody"],
    genre="Default"
)