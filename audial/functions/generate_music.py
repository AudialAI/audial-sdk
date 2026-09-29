"""
Music generation function for the Audial SDK.
"""

import os
import time
from typing import Optional, List

from audial.api.proxy import AudialProxy
from audial.api.constants import (
    EXECUTION_STATE_COMPLETED,
    EXECUTION_STATE_FAILED,
    MUSIC_GENERATOR_TASK_TYPES,
    DEFAULT_INFERENCE_STEPS,
    DEFAULT_GUIDANCE_SCALE,
    DEFAULT_BATCH_SIZE,
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_VOCAL_LANGUAGE,
)
from audial.api.exceptions import AudialError, AudialAPIError
from audial.utils.config import get_results_folder
from audial.utils.file_utils import download_file


def generate_music(
    prompt: str,
    task_type: str = "text2music",
    lyrics: str = None,
    source_file: str = None,
    reference_file: str = None,
    bpm: int = None,
    key_scale: str = None,
    time_signature: str = None,
    audio_duration: float = None,
    vocal_language: str = DEFAULT_VOCAL_LANGUAGE,
    audio_cover_strength: float = None,
    repainting_start: float = None,
    repainting_end: float = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    seed: int = None,
    inference_steps: int = DEFAULT_INFERENCE_STEPS,
    guidance_scale: float = DEFAULT_GUIDANCE_SCALE,
    audio_format: str = DEFAULT_AUDIO_FORMAT,
    track_name: str = None,
    track_classes: list = None,
    instrumental: bool = False,
    negative_prompt: str = None,
    results_folder: str = None,
    api_key: str = None,
    max_wait: float = 900,
    poll_interval: float = 5,
) -> dict:
    """
    Generate music with the Audial music model.

    Args:
        prompt: Text describing desired music style, mood, genre.
        task_type: Generation mode -- one of:
            text2music, cover, remix, extract, lego, complete, understand
        lyrics: Song lyrics for vocal generation (ignored if instrumental=True).
        source_file: Path to source audio (required for remix/extract/lego/complete/understand).
        reference_file: Path to reference audio (required for cover mode).
        bpm: Target beats per minute.
        key_scale: Target musical key (e.g. "C major", "A minor").
        time_signature: Time signature (e.g. "4/4", "3/4").
        audio_duration: Duration in seconds (10-600).
        vocal_language: Language code (e.g. "en", "zh", "ja"). Default "en".
        audio_cover_strength: 0.0-1.0, fidelity to original (cover/remix modes).
        repainting_start: Start time for remix in seconds.
        repainting_end: End time for remix in seconds (-1 = end of song).
        batch_size: Number of variations (1-8).
        seed: Random seed for reproducibility.
        inference_steps: Diffusion steps. 8 = turbo (fast), 50 = standard (quality).
        guidance_scale: Classifier-free guidance. Higher = more prompt-adherent.
        audio_format: Output format -- mp3, flac, wav, opus, or aac.
        track_name: Track to extract/replace (extract/lego modes).
            Options: vocals, drums, bass, guitar, piano, strings, synth, other
        track_classes: Instrument classes for complete mode.
        instrumental: If True, generate without vocals.
        negative_prompt: Text describing what to avoid.
        results_folder: Where to save output files. Default: audial_results/
        api_key: API key override.
        max_wait: Seconds to wait for the job before raising AudialAPIError. Default 900
            (cold-started workers can take several minutes).
        poll_interval: Seconds between status checks. Default 5.

    Returns:
        dict with keys:
            execution: Full execution record from the API.
            files: {folder, files} dict of downloaded output paths.
            caption_result: (understand mode only) Analysis data.
    """
    # Validate task type
    if task_type not in MUSIC_GENERATOR_TASK_TYPES:
        raise AudialError(
            f"Invalid task_type '{task_type}'. Must be one of: {MUSIC_GENERATOR_TASK_TYPES}"
        )

    # Validate that source/reference files are provided when required
    needs_source = task_type in ("remix", "extract", "lego", "complete", "understand")
    needs_reference = task_type == "cover"

    if needs_source and not source_file:
        raise AudialError(f"task_type '{task_type}' requires a source_file")
    if needs_reference and not reference_file:
        raise AudialError(f"task_type '{task_type}' requires a reference_file")

    # Initialize proxy
    proxy = AudialProxy(api_key=api_key)
    results_folder = results_folder or get_results_folder()

    print(f"Starting music generation (task: {task_type})...")

    # Step 1: Upload source/reference files if provided
    source_file_data = None
    reference_file_data = None

    if source_file:
        print(f"Uploading source file: {source_file}")
        source_file_data = proxy.upload_file(source_file)
        print(f"Source file uploaded: {source_file_data.get('filename')}")

    if reference_file:
        print(f"Uploading reference file: {reference_file}")
        reference_file_data = proxy.upload_file(reference_file)
        print(f"Reference file uploaded: {reference_file_data.get('filename')}")

    # Step 2: Call music generator directly (API creates its own execution)
    print("Running music generation...")
    response = proxy.run_music_generator(
        exe_id="",
        task_type=task_type,
        prompt=prompt,
        lyrics=lyrics,
        bpm=bpm,
        key_scale=key_scale,
        time_signature=time_signature,
        audio_duration=audio_duration,
        vocal_language=vocal_language,
        reference_file=reference_file_data,
        source_file=source_file_data,
        audio_cover_strength=audio_cover_strength,
        repainting_start=repainting_start,
        repainting_end=repainting_end,
        batch_size=batch_size,
        seed=seed,
        inference_steps=inference_steps,
        guidance_scale=guidance_scale,
        audio_format=audio_format,
        track_name=track_name,
        track_classes=track_classes,
        instrumental=instrumental,
        negative_prompt=negative_prompt,
    )

    # Get execution ID from the API response
    exe_id = None
    if isinstance(response, dict):
        exe_id = response.get("exeId") or response.get("exe_id")
    if not exe_id:
        raise AudialAPIError("No execution ID returned from music generator")
    print(f"Execution ID: {exe_id}")

    # Step 3: Poll for completion
    print("Waiting for generation to complete...")
    start_time = time.time()
    consecutive_errors = 0

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            raise AudialAPIError(f"Music generation timed out after {max_wait}s")

        time.sleep(poll_interval)

        try:
            exe_data = proxy.get_execution(exe_id)
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors <= 3 or consecutive_errors % 10 == 0:
                print(f"  Polling error ({consecutive_errors}, {int(elapsed)}s elapsed), retrying...")
            continue

        state = exe_data.get("state", "")

        # Check for generated files (frontend also uses this as completion signal)
        generated = exe_data.get("generated")
        if generated and isinstance(generated, dict) and len(generated) > 0:
            print("Generation completed!")
            break

        if state == EXECUTION_STATE_COMPLETED:
            print("Generation completed!")
            break
        elif state == EXECUTION_STATE_FAILED:
            error = exe_data.get("error", "Unknown error")
            raise AudialAPIError(f"Music generation failed: {error}")
        else:
            print(f"  Status: {state} ({int(elapsed)}s elapsed)")

    # Step 4: Download results
    result = {
        "execution": exe_data,
        "files": {"folder": None, "files": {}},
    }

    # Handle understand task -- caption result, no audio files
    if task_type == "understand":
        # Re-fetch execution to ensure we have the latest data with analysis
        time.sleep(3)  # Brief wait for Firebase writes to complete
        try:
            exe_data = proxy.get_execution(exe_id)
            result["execution"] = exe_data
        except Exception:
            pass
        analysis = exe_data.get("analysis", {})
        caption_result = analysis.get("caption_result", {}) if isinstance(analysis, dict) else {}
        if isinstance(caption_result, dict) and caption_result:
            result["caption_result"] = caption_result
        print("Caption result retrieved.")
        return result

    # Handle generation tasks -- download generated audio files
    generated = exe_data.get("generated", {})
    if generated:
        output_folder = os.path.join(results_folder, f"{exe_id}_generated")
        os.makedirs(output_folder, exist_ok=True)
        result["files"]["folder"] = output_folder

        for key, file_info in generated.items():
            if isinstance(file_info, dict) and file_info.get("url"):
                filename = file_info.get("filename", f"{key}.{audio_format}")
                output_path = os.path.join(output_folder, filename)
                print(f"Downloading: {filename}")
                download_file(file_info["url"], output_path)
                result["files"]["files"][filename] = output_path

    # Include generation metadata if available
    analysis = exe_data.get("analysis", {})
    gen_metadata = analysis.get("generation_metadata", {})
    if isinstance(gen_metadata, dict):
        result["metadata"] = gen_metadata.get("metadata", gen_metadata)

    print(f"Done! {len(result['files']['files'])} file(s) saved to {result['files'].get('folder')}")
    return result
