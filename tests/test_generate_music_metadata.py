"""generate_music returns the run's generation metadata, including lyrics Audial wrote.

The API stores ``generation_metadata`` at the top level of the execution record, next to
``generated`` (not under ``analysis``).
"""
from unittest.mock import MagicMock, patch

from audial.functions import generate_music as gm_module

WRITTEN = "[Verse]\nNeon rain on the window\n\n[Chorus]\nWe run tonight"
FILES = {"f0": {"filename": "song.mp3", "url": "http://example.com/song.mp3"}}


def _run(tmp_path, executions):
    proxy = MagicMock()
    proxy.run_music_generator.return_value = {"exeId": "exe-1"}
    proxy.get_execution.side_effect = list(executions)
    with patch.object(gm_module, "AudialProxy", return_value=proxy), \
         patch.object(gm_module, "download_file"), \
         patch.object(gm_module.time, "sleep"):
        result = gm_module.generate_music("dreamy synth pop", results_folder=str(tmp_path), api_key="k")
    return result, proxy


def test_top_level_generation_metadata_is_returned(tmp_path):
    meta = {"written_lyrics": WRITTEN, "audio_seconds": [60.2], "seed_values": ["7"]}
    result, _ = _run(tmp_path, [{"state": "completed", "generated": FILES, "generation_metadata": meta}])
    assert result["metadata"]["written_lyrics"] == WRITTEN
    assert result["metadata"]["audio_seconds"] == [60.2]


def test_metadata_written_after_the_files_is_picked_up(tmp_path):
    # The API writes the files and the metadata at the same time, so a poll can see the files
    # first. generate_music reads the record once more before giving up on the metadata.
    meta = {"written_lyrics": WRITTEN}
    result, proxy = _run(tmp_path, [
        {"state": "processing", "generated": FILES},
        {"state": "completed", "generated": FILES, "generation_metadata": meta},
    ])
    assert result["metadata"]["written_lyrics"] == WRITTEN
    assert result["execution"]["generation_metadata"] == meta
    assert proxy.get_execution.call_count == 2


def test_records_with_metadata_under_analysis_still_work(tmp_path):
    meta = {"seed_values": ["7"]}
    result, _ = _run(tmp_path, [
        {"state": "completed", "generated": FILES, "analysis": {"generation_metadata": meta}},
    ])
    assert result["metadata"] == meta


def test_no_metadata_gives_an_empty_dict(tmp_path):
    result, _ = _run(tmp_path, [
        {"state": "completed", "generated": FILES},
        {"state": "completed", "generated": FILES},
    ])
    assert result["metadata"] == {}
