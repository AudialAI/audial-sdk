"""
text2vox function for the Audial SDK.
"""

import os
import time
import uuid
from typing import Optional

from audial.api.proxy import AudialProxy
from audial.api.constants import (
    EXECUTION_STATE_COMPLETED,
    EXECUTION_STATE_FAILED,
    TEXT2VOX_DEFAULT_MAX_WAIT,
    TEXT2VOX_DEFAULT_POLL_INTERVAL,
    TEXT2VOX_LYRICS_MODES,
    FILETYPE_REFERENCE,
    FILETYPE_MIDI,
    FILETYPE_MELODY,
    FILETYPE_WORD_TS,
)
from audial.api.exceptions import AudialError, AudialAPIError
from audial.utils.config import get_results_folder
from audial.utils.file_utils import download_file


def text2vox(
    reference_file: str,
    lyrics: str,
    midi_file: Optional[str] = None,
    melody_audio_file: Optional[str] = None,
    word_timestamps_file: Optional[str] = None,
    lyrics_mode: str = "auto",
    reference_text: Optional[str] = None,
    cfg_strength: Optional[float] = None,
    nfe_steps: Optional[int] = None,
    pitch_shift: Optional[float] = None,
    strict_pitch: Optional[bool] = None,
    bend_smoothing_ms: Optional[float] = None,
    no_pitch_bends: Optional[bool] = None,
    leading_silence_s: Optional[float] = None,
    seed: Optional[int] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    max_wait: float = TEXT2VOX_DEFAULT_MAX_WAIT,
    poll_interval: float = TEXT2VOX_DEFAULT_POLL_INTERVAL,
) -> dict:
    """
    Synthesize a sung vocal in the timbre of a short reference voice clip,
    following a melody and lyrics.

    Exactly one of midi_file / melody_audio_file must be provided -- the
    worker needs one to drive the melody.

    Args:
        reference_file: Path to a short (5-10s) reference voice clip -- the
            voice to sing in.
        lyrics: The lyrics to sing. Required.
        midi_file: Path to a MIDI file driving the melody. Required unless
            melody_audio_file is given.
        melody_audio_file: Path to override melody audio. Required unless
            midi_file is given. When set, strict-pitch synthesis is skipped
            by the worker.
        word_timestamps_file: Path to a Whisper word-timestamps JSON for the
            source stem, used by auto-align.
        lyrics_mode: "auto" (default) matches word count to the MIDI note
            count and auto-aligns via word_timestamps; "per_note" expects
            lyrics pipe-delimited one token per note; "1to1" passes lyrics
            straight through.
        reference_text: What is said in the reference clip.
        cfg_strength: Worker synthesis option; see text2vox-runpod defaults.
        nfe_steps: Worker synthesis option.
        pitch_shift: Worker synthesis option.
        strict_pitch: Worker synthesis option.
        bend_smoothing_ms: Worker synthesis option.
        no_pitch_bends: Worker synthesis option.
        leading_silence_s: Worker synthesis option.
        seed: Random seed for reproducibility.
        results_folder: Where to save output files. Default: audial_results/
        api_key: API key override.
        max_wait: Maximum seconds to wait for completion.
        poll_interval: Seconds between execution status polls.

    Returns:
        dict with keys:
            execution: Full execution record from the API.
            files: {folder, files} dict of downloaded output paths -- the
                rendered wav, plus the MIDI actually used if the worker
                returned one.
            metadata: generation_metadata dict (duration_s, sample_rate),
                if present.
            warnings: generation_metadata.warnings list, if present.

    Raises:
        AudialError: If reference_file doesn't exist, lyrics is empty,
            lyrics_mode is invalid, or neither/both of midi_file and
            melody_audio_file are given.
        SubscriptionRequiredError: If the account has no active Audial
            subscription (HTTP 402).
        AudialAPIError: If the job fails, times out, or the API returns an
            error.
    """
    if not os.path.isfile(reference_file):
        raise AudialError(f"File not found: {reference_file}")

    if not lyrics:
        raise AudialError("text2vox requires non-empty lyrics")

    if lyrics_mode not in TEXT2VOX_LYRICS_MODES:
        raise AudialError(
            f"Invalid lyrics_mode '{lyrics_mode}'. Must be one of: {TEXT2VOX_LYRICS_MODES}"
        )

    if bool(midi_file) == bool(melody_audio_file):
        raise AudialError(
            "text2vox requires exactly one of midi_file or melody_audio_file"
        )

    if midi_file and not os.path.isfile(midi_file):
        raise AudialError(f"File not found: {midi_file}")
    if melody_audio_file and not os.path.isfile(melody_audio_file):
        raise AudialError(f"File not found: {melody_audio_file}")
    if word_timestamps_file and not os.path.isfile(word_timestamps_file):
        raise AudialError(f"File not found: {word_timestamps_file}")

    proxy = AudialProxy(api_key=api_key)
    results_dir = results_folder or get_results_folder()

    print("Starting text2vox...")

    # Step 1: Upload input files. The id used for the upload paths is only a
    # storage-path placeholder -- the run call below creates its own
    # execution, which may (and typically does) have a different exeId.
    upload_exe_id = str(uuid.uuid4())

    print(f"Uploading reference file: {reference_file}")
    reference_data = proxy.upload_execution_file(reference_file, upload_exe_id, FILETYPE_REFERENCE)
    print(f"Reference file uploaded: {reference_data.get('filename')}")

    midi_data = None
    if midi_file:
        print(f"Uploading MIDI file: {midi_file}")
        midi_data = proxy.upload_execution_file(midi_file, upload_exe_id, FILETYPE_MIDI)
        print(f"MIDI file uploaded: {midi_data.get('filename')}")

    melody_data = None
    if melody_audio_file:
        print(f"Uploading melody audio file: {melody_audio_file}")
        melody_data = proxy.upload_execution_file(melody_audio_file, upload_exe_id, FILETYPE_MELODY)
        print(f"Melody audio file uploaded: {melody_data.get('filename')}")

    word_timestamps_data = None
    if word_timestamps_file:
        print(f"Uploading word timestamps file: {word_timestamps_file}")
        word_timestamps_data = proxy.upload_execution_file(word_timestamps_file, upload_exe_id, FILETYPE_WORD_TS)
        print(f"Word timestamps file uploaded: {word_timestamps_data.get('filename')}")

    # Step 2: Run text2vox (API creates its own execution)
    print("Running text2vox...")
    response = proxy.run_text2vox(
        original_file=reference_data,
        lyrics=lyrics,
        lyrics_mode=lyrics_mode,
        reference_text=reference_text,
        midi_file=midi_data,
        melody_audio_file=melody_data,
        word_timestamps_file=word_timestamps_data,
        cfg_strength=cfg_strength,
        nfe_steps=nfe_steps,
        pitch_shift=pitch_shift,
        strict_pitch=strict_pitch,
        bend_smoothing_ms=bend_smoothing_ms,
        no_pitch_bends=no_pitch_bends,
        leading_silence_s=leading_silence_s,
        seed=seed,
    )

    exe_id = None
    if isinstance(response, dict):
        exe_id = response.get("exeId") or response.get("exe_id")
    if not exe_id:
        raise AudialAPIError("No execution ID returned from text2vox")
    print(f"Execution ID: {exe_id}")

    # Step 3: Poll for completion
    print("Waiting for text2vox to complete...")
    start_time = time.time()
    consecutive_errors = 0
    exe_data = response if response.get("state") in (EXECUTION_STATE_COMPLETED, EXECUTION_STATE_FAILED) else None

    while exe_data is None:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            raise AudialAPIError(f"text2vox timed out after {max_wait}s")

        time.sleep(poll_interval)

        try:
            candidate = proxy.get_execution(exe_id)
            consecutive_errors = 0
        except Exception:
            consecutive_errors += 1
            if consecutive_errors <= 3 or consecutive_errors % 10 == 0:
                print(f"  Polling error ({consecutive_errors}, {int(elapsed)}s elapsed), retrying...")
            continue

        state = candidate.get("state", "")
        if state == EXECUTION_STATE_COMPLETED:
            print("text2vox completed!")
            exe_data = candidate
        elif state == EXECUTION_STATE_FAILED:
            error = candidate.get("error", "Unknown error")
            raise AudialAPIError(f"text2vox failed: {error}")
        else:
            print(f"  Status: {state} ({int(elapsed)}s elapsed)")

    if exe_data.get("state") == EXECUTION_STATE_FAILED:
        error = exe_data.get("error", "Unknown error")
        raise AudialAPIError(f"text2vox failed: {error}")

    # Step 4: Download results
    result = {
        "execution": exe_data,
        "files": {"folder": None, "files": {}},
    }

    output_folder = os.path.join(results_dir, f"{exe_id}_text2vox")
    downloaded = {}

    for section in ("generated", "midi"):
        entry = exe_data.get(section, {})
        if isinstance(entry, dict):
            for key, file_info in entry.items():
                if isinstance(file_info, dict) and file_info.get("url"):
                    os.makedirs(output_folder, exist_ok=True)
                    filename = file_info.get("filename", key)
                    output_path = os.path.join(output_folder, filename)
                    print(f"Downloading: {filename}")
                    download_file(file_info["url"], output_path)
                    downloaded[filename] = output_path

    if downloaded:
        result["files"]["folder"] = output_folder
    result["files"]["files"] = downloaded

    # Generation metadata (duration_s, sample_rate, warnings)
    gen_metadata = exe_data.get("generation_metadata", {})
    if isinstance(gen_metadata, dict) and gen_metadata:
        result["metadata"] = gen_metadata
        if "warnings" in gen_metadata:
            result["warnings"] = gen_metadata.get("warnings")

    print(f"Done! {len(downloaded)} file(s) saved to {result['files'].get('folder')}")
    return result
