import audial

result = audial.segment(
    "/Users/zachfarrell/Desktop/Coding_Projects/Audial-All Current Code/audial-sdk/test_audio/01 Operator (Original Mix) - 10A - 2.mp3",
    components=["bass", "beat", "melody", "vocal"],
    analysis_type="select_features",
    features=["mode", "energy", "loudness", "danceability", "tatum", "lyrics", "tags"],
    genre="Tech House"
)