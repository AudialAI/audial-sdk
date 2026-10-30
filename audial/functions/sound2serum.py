"""
sound2serum function for the Audial SDK.
"""

import os
import time
import uuid
from typing import Any, Callable, Dict, Optional

from audial.api.proxy import AudialProxy
from audial.api.constants import (
    EXECUTION_STATE_COMPLETED,
    EXECUTION_STATE_FAILED,
    SOUND2SERUM_DEFAULT_MAX_WAIT,
    SOUND2SERUM_DEFAULT_POLL_INTERVAL,
    FILETYPE_REFERENCE,
)
from audial.api.exceptions import AudialError, AudialAPIError
from audial import warmup as warmup_module
from audial.utils.config import get_results_folder
from audial.utils.file_utils import download_file


def sound2serum(
    file_path: str,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    max_wait: float = SOUND2SERUM_DEFAULT_MAX_WAIT,
    poll_interval: float = SOUND2SERUM_DEFAULT_POLL_INTERVAL,
    on_progress: Optional[Callable[[Dict[str, Any]], Any]] = None,
) -> dict:
    """
    Synthesize a Serum 2 preset that reproduces the timbre of one isolated
    sound (the Audial Synth "resynthesis" engine). No Audial plugin is needed
    for this one -- the output is a `.SerumPreset` file opened directly in
    Xfer's Serum 2.

    Serum shows the file's name as the preset name (it ignores any name
    baked into the header), so the downloaded file is renamed from the
    worker's generic `preset.SerumPreset` to `<source file stem>.SerumPreset`
    -- open it in Serum and the preset name you see is your sample's name.

    Args:
        file_path: Path to the input audio file: one isolated sound, such as
            a single note, chord stab or hit, ideally 1-4 seconds and dry.
            Longer than 20 seconds fails the job. A loop, melody or drum
            pattern gives a poor preset even under 20 seconds; trim it to
            one note first.
        results_folder: Where to save output files. Default: audial_results/
        api_key: API key override.
        max_wait: Maximum seconds to wait for completion. Serum runs take
            about 2.5 minutes plus up to another 2.5 minutes if a worker has
            to cold-start; default leaves headroom above that.
        poll_interval: Seconds between execution status polls.
        on_progress: Called with the execution record after every poll.
            Carries the API's `warmup` object when the job had to wait for a
            worker to start; see audial.warmup.

    Returns:
        dict with keys:
            execution: Full execution record from the API.
            files: {folder, files} dict of downloaded output paths -- the
                .SerumPreset preset plus any generated render/keyboard/report
                files.
            preset: Local path to the downloaded .SerumPreset preset, if the
                job produced one.
            scores: generation_metadata.scores dict (huang_similarity,
                at_threshold, threshold, model), if present. at_threshold False
                means a weaker match, usually because the input was not one
                isolated sound.
            report: generation_metadata.report, if present.
            warnings: generation_metadata.warnings list, if present. Includes a
                note when the input sounds like several notes in a row.

    Raises:
        AudialError: If the input file doesn't exist.
        SubscriptionRequiredError: If the account has no active Audial
            subscription (HTTP 402).
        AudialAPIError: If the job fails, times out, or the API returns an
            error.
    """
    if not os.path.isfile(file_path):
        raise AudialError(f"File not found: {file_path}")

    proxy = AudialProxy(api_key=api_key)
    results_dir = results_folder or get_results_folder()

    print("Starting sound2serum...")

    # Step 1: Upload the reference audio. The id used for the upload path is
    # only a storage-path placeholder -- the run call below creates its own
    # execution, which may (and typically does) have a different exeId.
    upload_exe_id = str(uuid.uuid4())
    print(f"Uploading reference file: {file_path}")
    original_file = proxy.upload_execution_file(file_path, upload_exe_id, FILETYPE_REFERENCE)
    print(f"Reference file uploaded: {original_file.get('filename')}")

    # Step 2: Run sound2serum (API creates its own execution)
    print("Running sound2serum...")
    response = proxy.run_sound2serum(original_file)

    exe_id = None
    if isinstance(response, dict):
        exe_id = response.get("exeId") or response.get("exe_id")
    if not exe_id:
        raise AudialAPIError("No execution ID returned from sound2serum")
    print(f"Execution ID: {exe_id}")

    # Step 3: Poll for completion
    print("Waiting for sound2serum to complete...")
    start_time = time.time()
    consecutive_errors = 0
    exe_data = response if response.get("state") in (EXECUTION_STATE_COMPLETED, EXECUTION_STATE_FAILED) else None
    warmup_module.notify(on_progress, response)

    while exe_data is None:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            raise AudialAPIError(f"sound2serum timed out after {max_wait}s")

        time.sleep(poll_interval)

        try:
            candidate = proxy.get_execution(exe_id)
            consecutive_errors = 0
        except Exception:
            consecutive_errors += 1
            if consecutive_errors <= 3 or consecutive_errors % 10 == 0:
                print(f"  Polling error ({consecutive_errors}, {int(elapsed)}s elapsed), retrying...")
            continue

        warmup_module.notify(on_progress, candidate)

        state = candidate.get("state", "")
        if state == EXECUTION_STATE_COMPLETED:
            print("sound2serum completed!")
            exe_data = candidate
        elif state == EXECUTION_STATE_FAILED:
            error = candidate.get("error", "Unknown error")
            raise AudialAPIError(f"sound2serum failed: {error}")
        else:
            print(f"  Status: {state} ({int(elapsed)}s elapsed)")

    if exe_data.get("state") == EXECUTION_STATE_FAILED:
        error = exe_data.get("error", "Unknown error")
        raise AudialAPIError(f"sound2serum failed: {error}")

    # Step 4: Download results
    result = {
        "execution": exe_data,
        "files": {"folder": None, "files": {}},
    }

    output_folder = os.path.join(results_dir, f"{exe_id}_sound2serum")
    downloaded = {}

    preset = exe_data.get("preset", {})
    preset_info = preset.get("presetSerumPreset") if isinstance(preset, dict) else None
    if not isinstance(preset_info, dict) and isinstance(preset, dict):
        # Fallback: find any preset entry whose filename ends in .SerumPreset,
        # in case the key the API stamps it under ever changes.
        for candidate_info in preset.values():
            if (
                isinstance(candidate_info, dict)
                and isinstance(candidate_info.get("filename"), str)
                and candidate_info["filename"].endswith(".SerumPreset")
            ):
                preset_info = candidate_info
                break

    if isinstance(preset_info, dict) and preset_info.get("url"):
        os.makedirs(output_folder, exist_ok=True)
        # Serum shows the file name as the preset name, so save it named
        # after the source sample rather than the worker's generic
        # "preset.SerumPreset".
        source_stem = os.path.splitext(os.path.basename(file_path))[0]
        filename = f"{source_stem}.SerumPreset"
        output_path = os.path.join(output_folder, filename)
        print(f"Downloading: {filename}")
        download_file(preset_info["url"], output_path)
        downloaded[filename] = output_path
        result["preset"] = output_path

    generated = exe_data.get("generated", {})
    if isinstance(generated, dict):
        for key, file_info in generated.items():
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

    # Generation metadata (scores/report/warnings)
    gen_metadata = exe_data.get("generation_metadata", {})
    if isinstance(gen_metadata, dict):
        if "scores" in gen_metadata:
            result["scores"] = gen_metadata.get("scores")
        if "report" in gen_metadata:
            result["report"] = gen_metadata.get("report")
        if "warnings" in gen_metadata:
            result["warnings"] = gen_metadata.get("warnings")

    print(f"Done! {len(downloaded)} file(s) saved to {result['files'].get('folder')}")
    return result
