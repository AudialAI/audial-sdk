"""
Fixed stem splitting implementation with correct URL construction.
"""

from typing import List, Dict, Any, Optional, Union
import os
import time
import json
import random
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
        print("Creating execution...")
        execution = proxy.create_execution()
        exe_id = execution["exeId"]
        print(f"Execution created with ID: {exe_id}")
        
        print(f"Uploading file: {file_path}")
        file_data = proxy.upload_file(file_path)
        print(f"File uploaded: {file_data.get('filename')}")
        filename = file_data.get("filename")
        
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
            print("WARNING: Using default BPM of 120")
            
        if key is None:
            key = "C"  # Default key
            print("WARNING: Using default key of C")
        
        # Prepare stem request payload
        print(f"Starting stem splitting with stems: {stems}")
        stem_request = {
            "userId": user_id,
            "original": {
                "filename": filename,
                "url": file_data["url"],
                "type": file_data.get("type", "audio/mpeg"),
                "bpm": bpm,
                "key": key
            },
            "splitStemsRequest": {
                "targetBPM": target_bpm,
                "targetKey": target_key,
                "modelName": algorithm,
                "originalBPM": bpm,
                "originalKey": key,
                "stemsRequested": stems
            }
        }
        
        print(f"Sending stem request: {json.dumps(stem_request, indent=2)}")
        
        try:
            # Run stem splitting
            stem_result = proxy.run_stem_splitter(
                exe_id,
                stem_request["original"],
                stems,
                target_bpm,
                target_key
            )
            print("Stem splitting initiated successfully")
            
            # Check if we got an immediate result
            if isinstance(stem_result, dict):
                print("Received stem splitting result")
                result = stem_result
                # Store the execution ID for polling
                new_exe_id = stem_result.get("exeId", exe_id)
            else:
                # If no immediate result, we'll need to poll
                result = None
                new_exe_id = exe_id
                
        except Exception as e:
            print(f"Warning: Stem splitting request returned an error: {str(e)}")
            print("Will continue to check execution status in case processing is still occurring...")
            result = None
            new_exe_id = exe_id
        
        # If we don't have a result yet, poll for it
        if result is None:
            print(f"Polling for execution completion with ID: {new_exe_id}")
            
            # Configure polling parameters
            max_retries = 20
            backoff = 5  # Initial backoff in seconds
            max_backoff = 30  # Maximum backoff in seconds
            max_processing_time = 10 * 60  # 10 minutes timeout
            start_time = time.time()
            
            for attempt in range(max_retries):
                # Check for timeout
                current_time = time.time()
                elapsed = current_time - start_time
                if elapsed > max_processing_time:
                    raise AudialError(f"Processing timed out after {int(elapsed)} seconds")
                
                try:
                    print(f"Checking execution status (attempt {attempt+1}/{max_retries})...")
                    result = proxy.get_execution(new_exe_id)
                    
                    state = result.get("state")
                    print(f"Current state: {state}")
                    
                    # Check if execution is completed
                    if state == "completed":
                        print("Processing completed successfully!")
                        break
                        
                    # Check if execution failed
                    elif state == "failed":
                        error = result.get("error", "Unknown error")
                        raise AudialError(f"Stem splitting failed: {error}")
                    
                    # If not complete, wait with backoff
                    wait_time = min(max_backoff, backoff * (1 + attempt * 0.1))
                    print(f"Processing in progress... Waiting {wait_time:.1f} seconds (elapsed: {int(elapsed)}s)")
                    time.sleep(wait_time)
                    
                except Exception as e:
                    print(f"Error checking status: {str(e)}")
                    time.sleep(backoff)
        
        # At this point, we should have a result with stem data
        if not result or not isinstance(result, dict):
            raise AudialError("Failed to retrieve execution results")
            
        # Check if we have stem data
        if "stem" not in result or not isinstance(result["stem"], dict) or not result["stem"]:
            raise AudialError("No stem data found in execution result")
            
        # Successfully got stems! Now we need to construct the URLs
        stems_data = result["stem"]
        print(f"Found {len(stems_data)} stems in the execution result")
        
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
        
        print(f"Constructed {len(stem_urls)} stem URLs")
        
        # Download the stem files
        print("Downloading stem files...")
        result_folder = os.path.join(results_dir, f"{result_exe_id}_{EXECUTION_TYPE_STEM}")
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