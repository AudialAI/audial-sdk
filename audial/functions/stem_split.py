"""
Fixed stem splitting implementation with correct URL construction and polling for all stems.
"""

from typing import List, Dict, Any, Optional, Union
import os
import time
import json
from urllib.parse import urlparse

from audial.api.proxy import AudialProxy
from audial.api.constants import (
    EXECUTION_TYPE_STEM,
    DEFAULT_STEM_OPTIONS,
    ALL_STEM_OPTIONS,
    API_BASE_URL
)
from audial.api.exceptions import AudialError, AudialAPIError
from audial.utils.config import get_api_key, get_results_folder, get_user_id

def are_all_stems_complete(available_stems, requested_stems):
    """
    Check if all requested stems are present in the available stems.
    
    Args:
        available_stems (dict): The stems available in the execution result.
        requested_stems (list): The list of stems that were requested.
        
    Returns:
        bool: True if all requested stems are present, False otherwise.
    """
    # Normalization function: remove spaces, underscores, and a trailing "mp3" (case-insensitive)
    def normalize(stem_name):
        return stem_name.lower().replace("_", "").replace(" ", "").replace("mp3", "")
    
    # For each requested stem, if it starts with "full_song_without_", 
    # we expect the API to return a stem with key "no" + (the rest) normalized.
    expected_files = []
    for stem in requested_stems:
        if stem.startswith("full_song_without_"):
            # For "full_song_without_vocals", expect "no_vocals" or "novocals"
            expected_files.append(normalize(f"no_{stem.replace('full_song_without_', '')}"))
        else:
            expected_files.append(normalize(stem))
    
    # Normalize available stem keys from the API response
    available_stem_types = [normalize(key) for key in available_stems.keys()]
    
    # Check if all expected files are in the available stems
    return all(exp in available_stem_types for exp in expected_files)

def stem_split(
    file_path: str,
    stems: Optional[List[str]] = None,
    target_bpm: Optional[float] = None,
    target_key: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None,
    algorithm: str = "primaudio"
) -> Dict[str, Any]:
    """
    Split an audio file into separate stems.
    
    Args:
        file_path (str): Path to the audio file.
        stems (List[str], optional): List of stems to extract. Defaults to ["vocals", "drums", "bass", "other"].
            Valid options are: "vocals", "drums", "bass", "other", "full_song_without_vocals",
            "full_song_without_drums", "full_song_without_bass", "full_song_without_other".
        target_bpm (float, optional): Target BPM for tempo adjustment.
        target_key (str, optional): Target key for pitch adjustment.
        results_folder (str, optional): Folder to save results. Uses default if None.
        api_key (str, optional): API key to use. Uses default if None.
        algorithm (str, optional): Algorithm to use for stem separation. Defaults to "primaudio".
        
    Returns:
        Dict[str, Any]: Results data including paths to downloaded files.
        
    Raises:
        AudialError: If stem splitting fails.
        ValueError: If invalid stem types are provided.
    """
    # Validate stem options
    if stems is not None:
        invalid_stems = [stem for stem in stems if stem not in ALL_STEM_OPTIONS]
        if invalid_stems:
            raise ValueError(
                f"Invalid stem type(s): {', '.join(invalid_stems)}. "
                f"Valid options are: {', '.join(ALL_STEM_OPTIONS)}"
            )
    
    # Use default stems if not provided
    stems = stems or DEFAULT_STEM_OPTIONS
    
    # Initialize configuration
    api_key = api_key or get_api_key()
    user_id = get_user_id()
    results_dir = results_folder or get_results_folder()
    
    # Ensure results directory exists
    os.makedirs(results_dir, exist_ok=True)
    
    # Initialize proxy
    proxy = AudialProxy(api_key)
    
    # Execute workflow
    try:
        # Upload file FIRST
        print(f"Uploading file: {file_path}")
        file_data = proxy.upload_file(file_path)
        print(f"File uploaded: {file_data.get('filename')}")
        filename = file_data.get("filename")
        
        # Create execution with the original file data
        execution = proxy.create_execution('stem', original=file_data)
        exe_id = execution["exeId"]
        
        # Run primary analysis
        print("Running primary analysis...")
        analysis = proxy.run_primary_analysis(exe_id, file_data["url"])
        
        # Extract BPM and key from analysis response
        bpm = None
        key = None
        
        # Check different possible response structures
        if isinstance(analysis, dict):
            # Direct fields
            if 'bpm' in analysis:
                bpm = analysis['bpm']
            if 'key' in analysis:
                key = analysis['key']
                
            # Nested in 'original'
            if 'original' in analysis and isinstance(analysis['original'], dict):
                if bpm is None and 'bpm' in analysis['original']:
                    bpm = analysis['original']['bpm']
                if key is None and 'key' in analysis['original']:
                    key = analysis['original']['key']
        
        print(f"Analysis completed: BPM={bpm}, Key={key}")
        
        # Ensure we have non-null BPM and key values
        if bpm is None:
            bpm = 120  # Default BPM
            
        if key is None:
            key = "C"  # Default key
        
        # Prepare stem request payload
        original_file = {
            "filename": filename,
            "url": file_data["url"],
            "type": file_data.get("type", "audio/mpeg"),
            "bpm": bpm,
            "key": key
        }
        
        # Run stem splitting
        print("Running stem splitter... For longer audio this may take up to 2 minutes")
        response = None
        new_exe_id = exe_id
        
        try:
            # Run stem splitting
            response = proxy.run_stem_splitter(
                exe_id,
                original_file,
                stems,
                target_bpm,
                target_key
            )
            
            # Check if execution ID is returned
            if isinstance(response, dict) and "exeId" in response:
                new_exe_id = response["exeId"]
                
            # Check if stems are already available (unlikely for full request)
            if isinstance(response, dict) and "stem" in response and response["stem"]:
                # We have immediate results, no need to poll
                result = response
            else:
                # No immediate stems, need to poll
                response = None
                
        except Exception as e:
            response = None
        
        # If we need to poll for results
        if response is None or "stem" not in response or not response["stem"]:
            # Configure polling parameters
            max_retries = 30
            backoff = 5  # Initial backoff in seconds
            max_backoff = 30  # Maximum backoff in seconds
            max_processing_time = 15 * 60  # 15 minutes timeout
            start_time = time.time()
            result = None
            
            for attempt in range(max_retries):
                # Check for timeout
                current_time = time.time()
                elapsed = current_time - start_time
                if elapsed > max_processing_time:
                    raise AudialError(f"Processing timed out after {int(elapsed)} seconds")
                
                try:
                    execution_result = proxy.get_execution(new_exe_id)
                    
                    state = execution_result.get("state")
                    
                    # Check if execution has stem data
                    stems_data = execution_result.get("stem", {})
                    if stems_data and isinstance(stems_data, dict):
                        result = execution_result
                        
                        # Check if all requested stems are present
                        if are_all_stems_complete(stems_data, stems):
                            print("All requested stems are complete!")
                            break
                            
                    # Check if execution is completed
                    if state == "completed":
                        # Even if state is completed, double-check if all stems are present
                        if "stem" in execution_result and isinstance(execution_result["stem"], dict):
                            result = execution_result
                            if are_all_stems_complete(execution_result["stem"], stems):
                                print("All requested stems are complete!")
                                break
                                
                    # Check if execution failed
                    elif state == "failed":
                        error = execution_result.get("error", "Unknown error")
                        raise AudialError(f"Stem splitting failed: {error}")
                    
                    # If not complete, wait with backoff
                    wait_time = min(max_backoff, backoff * (1 + attempt * 0.1))
                    time.sleep(wait_time)
                    
                except Exception as e:
                    time.sleep(backoff)
        else:
            # We already got results from the initial API call
            result = response
        
        # At this point, we should have a result with stem data
        if not result or not isinstance(result, dict):
            raise AudialError("Failed to retrieve execution results")
            
        # Check if we have stem data
        if "stem" not in result or not isinstance(result["stem"], dict) or not result["stem"]:
            raise AudialError("No stem data found in execution result")
            
        # Successfully got stems! Now we need to construct the URLs
        stems_data = result["stem"]
        
        # Construct the stem URLs following the API pattern from OpenAPI spec
        # Format: /files/{userId}/execution/{exeId}/{filetype}/{filename}
        result_exe_id = result.get("exeId", new_exe_id)
        
        # Construct stem URLs
        stem_urls = []
        for stem_key, stem_info in stems_data.items():
            # Check if the API already provided a URL
            if isinstance(stem_info, dict) and "url" in stem_info and stem_info["url"]:
                # Use the provided URL
                stem_urls.append(stem_info["url"])
            else:
                # Construct URL based on API pattern
                filename = stem_info.get("filename") if isinstance(stem_info, dict) else f"{stem_key}.mp3"
                
                # Remove "mp3" suffix if present in the key
                if stem_key.endswith("mp3"):
                    stem_name = stem_key[:-3]
                else:
                    stem_name = stem_key
                
                # Construct the URL
                stem_url = f"{API_BASE_URL.rstrip('/')}/files/{user_id}/execution/{result_exe_id}/stem/{filename}"
                stem_urls.append(stem_url)
                
                # If the stem_info is a dict, add the URL to it for reference
                if isinstance(stem_info, dict):
                    stem_info["url"] = stem_url
        
        # Download the stem files
        print("Downloading stem files...")
        result_folder = os.path.join(results_dir, f"{filename}_{EXECUTION_TYPE_STEM}")
        os.makedirs(result_folder, exist_ok=True)
        
        downloaded_files = {}
        import requests
        
        for url in stem_urls:
            try:
                # Extract filename from URL
                filename = os.path.basename(urlparse(url).path)
                if not filename:
                    filename = f"file_{len(downloaded_files) + 1}.mp3"
                
                file_path = os.path.join(result_folder, filename)
                
                # Download file
                print(f"Downloading {url} to {file_path}")
                response = requests.get(url, stream=True, timeout=30)
                
                if response.status_code == 200:
                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    downloaded_files[filename] = file_path
                else:
                    print(f"Failed to download {url}, status code: {response.status_code}")
            except Exception as e:
                print(f"Error downloading {url}: {str(e)}")
        
        # Return the results
        if downloaded_files:
            return {
                "execution": result,
                "files": {
                    "folder": result_folder,
                    "files": downloaded_files
                }
            }
        else:
            raise AudialError("Failed to download any stem files")
    
    except Exception as e:
        # Handle errors
        raise AudialError(f"Stem splitting failed: {str(e)}")