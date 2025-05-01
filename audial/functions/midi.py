"""
MIDI generation implementation for Audial SDK.
"""

from typing import Dict, Any, Optional, List, Union
import os
import time
import json
from urllib.parse import urlparse

import requests

from audial.api.proxy import AudialProxy
from audial.api.constants import API_BASE_URL
from audial.api.exceptions import AudialError
from audial.utils.config import get_api_key, get_results_folder, get_user_id

def generate_midi(
    file_path: Union[str, List[str]],
    bpm: Optional[float] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate MIDI data from one or more audio files.
    
    Args:
        file_path (str or List[str]): Path to one or more audio files.
        bpm (float, optional): Override BPM for the MIDI generation.
        results_folder (str, optional): Folder to save results. Uses default if None.
        api_key (str, optional): API key to use. Uses default if None.
        
    Returns:
        Dict[str, Any]: Results data including paths to downloaded files.
        
    Raises:
        AudialError: If MIDI generation fails.
    """
    # Initialize configuration
    api_key = api_key or get_api_key()
    user_id = get_user_id()
    results_dir = results_folder or get_results_folder()
    
    # Ensure results directory exists
    os.makedirs(results_dir, exist_ok=True)
    
    # Initialize proxy
    proxy = AudialProxy(api_key)
    
    # Convert single file_path to list for consistent handling
    if isinstance(file_path, str):
        file_paths = [file_path]
    else:
        file_paths = file_path
    
    # Execute workflow
    try:
        execution = proxy.create_execution()
        exe_id = execution["exeId"]
        
        # Upload all files
        files_info = []
        for idx, path in enumerate(file_paths):
            print(f"Uploading file {idx+1}/{len(file_paths)}: {path}")
            file_data = proxy.upload_file(path)
            filename = file_data.get("filename")
            print(f"File uploaded: {filename}")
            
            files_info.append({
                "name": filename,
                "url": file_data["url"]
            })
        
        print(f"Uploaded {len(files_info)} file(s)")
        
        # If BPM is not provided, use default
        if bpm is None:
            bpm = 120
            print(f"No BPM specified, using default of {bpm}")
        else:
            print(f"Using specified BPM: {bpm}")
        
        # Prepare MIDI generation request payload to match the UI structure exactly
        print("Starting MIDI generation...")
        midi_request = {
            "userId": user_id,
            "files": files_info,
            "bpm": bpm
        }
        
        # Run MIDI generation and get initial result
        midi_result = None
        try:
            midi_result = proxy.run_generate_midi(exe_id, midi_request)
            
            if isinstance(midi_result, dict):
                print("Received initial MIDI response")
                print(f"Response: {json.dumps(midi_result, indent=2)}")
                result = midi_result
            else:
                print("No immediate result, will poll for completion")
                result = None
        except Exception as e:
            print(f"Warning: MIDI generation request returned an error: {str(e)}")
            print("Will continue to check execution status in case processing is still occurring...")
            result = None
        
        # Polling configuration
        max_retries = 20
        backoff = 5  # Initial backoff in seconds
        max_backoff = 30  # Maximum backoff in seconds
        max_processing_time = 5 * 60  # 5 minutes timeout
        start_time = time.time()
        
        # Function to check if we have MIDI data in the result
        def has_midi_data(data):
            return (data and isinstance(data, dict) and 
                    'midi' in data and isinstance(data['midi'], dict) and 
                    len(data['midi']) > 0)
        
        # If we don't have MIDI data yet, poll for it
        if not has_midi_data(result):
            print(f"Polling for MIDI data with execution ID: {exe_id}")
            
            for attempt in range(max_retries):
                # Check for timeout
                current_time = time.time()
                elapsed = current_time - start_time
                if elapsed > max_processing_time:
                    raise AudialError(f"Processing timed out after {int(elapsed)} seconds")
                
                try:
                    # Check general execution status
                    exec_data = proxy.get_execution(exe_id)
                    
                    # Check for MIDI data in main execution response
                    if has_midi_data(exec_data):
                        print("Found MIDI data in execution response!")
                        result = exec_data
                        break
                    
                    # If execution completed but no MIDI data yet, still continue polling
                    if exec_data.get('state') == 'completed':
                        print("Execution completed, but no MIDI data yet. Will check again.")
                    elif exec_data.get('state') == 'failed':
                        error = exec_data.get("error", "Unknown error")
                        raise AudialError(f"MIDI generation failed: {error}")
                    
                    # Wait before next attempt
                    wait_time = min(max_backoff, backoff * (1 + attempt * 0.1))
                    print(f"Waiting {wait_time:.1f} seconds before next check (elapsed: {int(elapsed)}s)")
                    time.sleep(wait_time)
                    
                except AudialError as e:
                    # Re-raise AudialError exceptions
                    raise e
                except Exception as e:
                    print(f"Error checking status: {str(e)}")
                    time.sleep(backoff)
        
        # Final check - we should have a result
        if not result or not isinstance(result, dict):
            raise AudialError("Failed to retrieve execution results")
                
        # Try to construct MIDI URLs based on the frontend pattern
        midi_urls = []
        
        # First check for MIDI data in the response
        if 'midi' in result and isinstance(result['midi'], dict):
            for midi_key, midi_info in result['midi'].items():
                if isinstance(midi_info, dict) and 'url' in midi_info:
                    midi_urls.append(midi_info['url'])
                    print(f"Found MIDI URL in response: {midi_info['url']}")
        
        # If no MIDI URLs found, construct them based on the file patterns
        if not midi_urls:
            
            for file_info in files_info:
                # Get original filename (without extension) and replace spaces with underscores
                orig_filename = file_info.get('name', '')
                if orig_filename:
                    # Get the filename without extension and replace spaces with underscores
                    name_without_ext = os.path.splitext(orig_filename)[0].replace(' ', '_')
                    
                    # Construct the URL following the pattern from the frontend
                    midi_filename = f"{name_without_ext}_basic_pitch.mid"
                    midi_url = f"https://storage.googleapis.com/audial-dev-v2.firebasestorage.app/{user_id}%2Fexecution%2F{exe_id}%2Fmidi%2F{midi_filename}"
                    midi_urls.append(midi_url)
                    print(f"Constructed MIDI URL: {midi_url}")
        
        if not midi_urls:
            raise AudialError("No MIDI URLs found or could be constructed")
        
        
        # Download the MIDI files with retry logic
        print("Downloading MIDI files...")
        result_folder = os.path.join(results_dir, f"{exe_id}_midi")
        os.makedirs(result_folder, exist_ok=True)
        
        downloaded_files = {}

        # Use the execution ID we already have from the result
        result_exe_id = result.get("exeId")

        for midi_key, midi_info in result.get("midi", {}).items():
            try:
                # Get the filename directly from the result data
                filename = midi_info.get("filename")
                if not filename:
                    print(f"No filename in MIDI info for {midi_key}, skipping")
                    continue
                
                file_path = os.path.join(result_folder, filename)
                
                # Construct API URL directly
                api_url = f"{API_BASE_URL}/files/{user_id}/execution/{result_exe_id}/midi/{filename}"
                print(f"Downloading: {api_url} to {file_path}")
                
                # Use the same headers as in your other API calls
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "x-api-key": api_key,
                    "x-user-id": user_id
                }
                
                response = requests.get(api_url, headers=headers, stream=True, timeout=30)
                
                if response.status_code == 200:
                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    downloaded_files[filename] = file_path
                else:
                    print(f"Failed to download {api_url}, status code: {response.status_code}")
                    # Print response body for debugging
                    print(f"Response body: {response.text[:200]}...")
            except Exception as e:
                print(f"Error downloading MIDI file: {str(e)}")
        
        # Return results
        if downloaded_files:
            print(f"Successfully downloaded {len(downloaded_files)} MIDI files")
            return {
                "execution": result,
                "files": {
                    "folder": result_folder,
                    "files": downloaded_files
                }
            }
        else:
            # If we couldn't download any files but have URLs, include them in the error
            urls_str = "\n".join([f"- {url}" for url in midi_urls])
            raise AudialError(f"Failed to download MIDI files. You may need to manually download from these URLs:\n{urls_str}")
    
    except Exception as e:
        # Handle errors
        raise AudialError(f"MIDI generation failed: {str(e)}")