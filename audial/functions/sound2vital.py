"""
sound2vital function for the Audial SDK.
"""

import os
import time
import uuid
from typing import Optional

from audial.api.proxy import AudialProxy
from audial.api.constants import (
    EXECUTION_STATE_COMPLETED,
    EXECUTION_STATE_FAILED,
    SOUND2VITAL_DEFAULT_MAX_WAIT,
    SOUND2VITAL_DEFAULT_POLL_INTERVAL,
    FILETYPE_REFERENCE,
)
from audial.api.exceptions import AudialError, AudialAPIError
from audial.utils.config import get_results_folder
from audial.utils.file_utils import download_file


def sound2vital(
    file_path: str,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    max_wait: float = SOUND2VITAL_DEFAULT_MAX_WAIT,
    poll_interval: float = SOUND2VITAL_DEFAULT_POLL_INTERVAL,
) -> dict:
    """
    Synthesize a Vital synth preset that reproduces the timbre of a short
    audio clip (the Audial Synth "resynthesis" engine).

    Args:
        file_path: Path to the input audio file. Must be 20 seconds or
            shorter -- longer input fails the job.
        results_folder: Where to save output files. Default: audial_results/
        api_key: API key override.
        max_wait: Maximum seconds to wait for completion. Jobs typically
            take 60-250s; default leaves headroom above that.
        poll_interval: Seconds between execution status polls.

    Returns:
        dict with keys:
            execution: Full execution record from the API.
            files: {folder, files} dict of downloaded output paths -- the
                .vital preset plus any generated render/keyboard/report
                files.
            preset: Local path to the downloaded .vital preset, if the job
                produced one.
            scores: generation_metadata.scores dict (huang_similarity,
                at_threshold, threshold, model), if present.
            report: generation_metadata.report, if present.
            warnings: generation_metadata.warnings list, if present.

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

    print("Starting sound2vital...")

    # Step 1: Upload the reference audio. The id used for the upload path is
    # only a storage-path placeholder -- the run call below creates its own
    # execution, which may (and typically does) have a different exeId.
    upload_exe_id = str(uuid.uuid4())
    print(f"Uploading reference file: {file_path}")
    original_file = proxy.upload_execution_file(file_path, upload_exe_id, FILETYPE_REFERENCE)
    print(f"Reference file uploaded: {original_file.get('filename')}")

    # Step 2: Run sound2vital (API creates its own execution)
    print("Running sound2vital...")
    response = proxy.run_sound2vital(original_file)

    exe_id = None
    if isinstance(response, dict):
        exe_id = response.get("exeId") or response.get("exe_id")
    if not exe_id:
        raise AudialAPIError("No execution ID returned from sound2vital")
    print(f"Execution ID: {exe_id}")

    # Step 3: Poll for completion
    print("Waiting for sound2vital to complete...")
    start_time = time.time()
    consecutive_errors = 0
    exe_data = response if response.get("state") in (EXECUTION_STATE_COMPLETED, EXECUTION_STATE_FAILED) else None

    while exe_data is None:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            raise AudialAPIError(f"sound2vital timed out after {max_wait}s")

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
            print("sound2vital completed!")
            exe_data = candidate
        elif state == EXECUTION_STATE_FAILED:
            error = candidate.get("error", "Unknown error")
            raise AudialAPIError(f"sound2vital failed: {error}")
        else:
            print(f"  Status: {state} ({int(elapsed)}s elapsed)")

    if exe_data.get("state") == EXECUTION_STATE_FAILED:
        error = exe_data.get("error", "Unknown error")
        raise AudialAPIError(f"sound2vital failed: {error}")

    # Step 4: Download results
    result = {
        "execution": exe_data,
        "files": {"folder": None, "files": {}},
    }

    output_folder = os.path.join(results_dir, f"{exe_id}_sound2vital")
    downloaded = {}

    preset = exe_data.get("preset", {})
    preset_info = preset.get("presetvital") if isinstance(preset, dict) else None
    if isinstance(preset_info, dict) and preset_info.get("url"):
        os.makedirs(output_folder, exist_ok=True)
        filename = preset_info.get("filename", "preset.vital")
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
