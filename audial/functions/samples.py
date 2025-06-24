"""
Sample pack generation implementation for Audial SDK.
"""

from typing import Dict, Any, Optional, List
import os
import time
import json
import requests
from audial.api.constants import API_BASE_URL
from audial.api.auth import get_auth_headers
from audial.api.proxy import AudialProxy
from audial.api.exceptions import AudialError
from audial.utils.config import get_api_key, get_results_folder, get_user_id

def extract_sample_urls(status: Dict[str, Any]) -> List[str]:
    """
    Extract all sample URLs from an execution response.
    This approach mirrors the React implementation's comprehensive URL extraction.
    
    Args:
        status (Dict[str, Any]): Execution status response
        
    Returns:
        List[str]: List of all sample URLs found in the response
    """
    result_urls = []
    
    # Direct URL extraction from 'sample' object (flat structure)
    if isinstance(status.get('sample'), dict):
        for key, item in status['sample'].items():
            if isinstance(item, dict) and 'url' in item:
                result_urls.append(item['url'])
    
    # Handle nested sample structure (sample/category/file)
    # Check for sample/{category} directory structure
    if isinstance(status.get('sample'), dict):
        for category_key, category_data in status['sample'].items():
            if isinstance(category_data, dict):
                for file_key, file_data in category_data.items():
                    if isinstance(file_data, dict) and 'url' in file_data:
                        result_urls.append(file_data['url'])
    
    # Check for entries in /files/userId/execution/exeId/sample endpoint
    # These would typically be returned when calling getExecutionFilesByType with filetype=sample
    if 'sample_urls' in status and isinstance(status['sample_urls'], list):
        result_urls.extend(status['sample_urls'])
    
    # Check alternative data structures
    if isinstance(status.get('sample_pack'), dict) and isinstance(status['sample_pack'].get('results'), list):
        result_urls.extend(status['sample_pack']['results'])
    
    if isinstance(status.get('samplePack'), dict) and isinstance(status['samplePack'].get('results'), list):
        result_urls.extend(status['samplePack']['results'])
    
    if isinstance(status.get('output'), dict) and isinstance(status['output'].get('results_url'), list):
        result_urls.extend(status['output']['results_url'])
    
    # Make the list unique
    return list(set(result_urls))

def debug_execution_structure(status: Dict[str, Any]):
    """
    Print detailed structure of the execution response for debugging.
    
    Args:
        status (Dict[str, Any]): Execution status response
    """

    
    if 'sample' in status:

        if isinstance(status['sample'], dict):
            # Print first item structure if available
            if status['sample'] and list(status['sample'].keys()):
                first_key = list(status['sample'].keys())[0]
                if isinstance(status['sample'][first_key], dict):
                    print(f"    Keys: {list(status['sample'][first_key].keys())}")
    
    # Add detailed debugging for other potential structures
    for key in ['sample_pack', 'samplePack', 'output']:
        if key in status:

            if isinstance(status[key], dict):
                if 'results' in status[key] and isinstance(status[key]['results'], list):
                    if status[key]['results']:
                        print(f"  First result: {status[key]['results'][0]}")
                if 'results_url' in status[key] and isinstance(status[key]['results_url'], list):
                    if status[key]['results_url']:
                        print(f"  First result_url: {status[key]['results_url'][0]}")
    

def generate_samples(
    file_path: str,
    job_type: Optional[str] = None,
    components: Optional[List[str]] = None,
    genre: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a sample pack from an audio file.
    
    Args:
        file_path (str): Path to the audio file.
        job_type (str, optional): Type of sample pack job to run (default: "sample_pack").
        components (List[str], optional): Components to include in the sample pack (default: ["drums", "bass", "melody"]).
        genre (str, optional): Genre of the track (default: "Default").
        results_folder (str, optional): Folder to save results. Uses default if None.
        api_key (str, optional): API key to use. Uses default if None.
        
    Returns:
        Dict[str, Any]: Sample generation results.
        
    Raises:
        AudialError: If sample generation fails.
    """
    # Set default values
    job_type = job_type or "sample_pack"
    components = components or ["drums", "bass", "melody"]
    genre = genre or "Default"
    
    # Validate job_type
    valid_job_types = ["sample_pack"]
    if job_type not in valid_job_types:
        raise AudialError(f"Invalid job type: {job_type}. Must be one of: {', '.join(valid_job_types)}")
    
    # Validate components
    valid_components = ["drums", "bass", "melody"]
    for component in components:
        if component not in valid_components:
            raise AudialError(f"Invalid component: {component}. Must be one of: {', '.join(valid_components)}")
    
    # Validate genre
    valid_genres = [
        "Default", "Afro House", "Tech House", "Bass House", "Blues", "Breakbeat",
        "Classic Rock", "Country", "Deep House", "Drum N Bass", "Dubstep", "Gospel",
        "Grime140", "House", "Indie", "Jazz", "Latin", "Metal", "Minimal House",
        "Pop", "R&B", "Rock", "Techno", "Trance", "Trap", "UK Garage"
    ]
    
    if genre not in valid_genres:
        raise AudialError(f"Invalid genre: {genre}. Must be one of: {', '.join(valid_genres)}")
    
    # Initialize configuration
    api_key = api_key or get_api_key()
    results_dir = results_folder or get_results_folder()
    
    # Ensure results directory exists
    os.makedirs(results_dir, exist_ok=True)
    
    # Initialize proxy
    proxy = AudialProxy(api_key)
    
    # Execute workflow
    try:
        # Check if the file exists
        if not os.path.isfile(file_path):
            raise AudialError(f"File not found: {file_path}")
        
        execution = proxy.create_execution('sample')
        exe_id = execution["exeId"]
        
        print(f"Uploading file: {file_path}")
        file_data = proxy.upload_file(file_path)
        filename = file_data.get("filename")
        file_url = file_data.get("url")
        
        if not file_url:
            raise AudialError("Failed to get file URL after upload")
        
        print(f"File uploaded: {filename}")
        
        print("Running primary analysis...")
        analysis_result = proxy.run_primary_analysis(exe_id, file_url)
        print(f"Primary analysis result: {analysis_result}")
        
        # Extract BPM and key from analysis response
        bpm = None
        key = None
        
        # Check different possible response structures
        if isinstance(analysis_result, dict):
            # Direct fields
            if 'bpm' in analysis_result:
                bpm = analysis_result['bpm']
            if 'key' in analysis_result:
                key = analysis_result['key']
                
            # Nested in 'original'
            if 'original' in analysis_result and isinstance(analysis_result['original'], dict):
                if bpm is None and 'bpm' in analysis_result['original']:
                    bpm = analysis_result['original']['bpm']
                if key is None and 'key' in analysis_result['original']:
                    key = analysis_result['original']['key']
        
        # For sample pack generation, we need to split the track into stems first
        print("Running stem splitting...")
        stems_requested = ["vocals", "drums", "bass", "other"]
        
        original_file = {
            "filename": filename,
            "url": file_url,
            "bpm": bpm,
            "key": key
        }
        
        stem_result = proxy.run_stem_splitter(
            exe_id,
            original_file,
            stems_requested
        )
        
        print(f"Stem splitting result: {stem_result}")
        
        # Wait for the stem splitting to complete
        print("Waiting for stem splitting to complete...")
        stem_exe_id = stem_result.get("exeId") or exe_id
        stem_complete = False
        max_wait_time = 300  # 5 minutes
        start_time = time.time()
        
        while not stem_complete and (time.time() - start_time) < max_wait_time:
            stem_status = proxy.get_execution(stem_exe_id)
            stem_state = stem_status.get("state")
            
            if stem_state == "completed":
                stem_complete = True
                print("Stem splitting completed successfully.")
                break
            elif stem_state == "failed":
                raise AudialError(f"Stem splitting failed: {stem_status.get('error', 'Unknown error')}")
            else:
                print(f"Stem splitting in progress: {stem_state}")
                time.sleep(5)  # Wait 5 seconds before checking again
        
        if not stem_complete:
            raise AudialError(f"Stem splitting timed out after {max_wait_time} seconds")
        
        # Create fileUrls structure for the request
        stem_urls = {}
        
        # Get the stem URLs from the stem result
        if "stem" in stem_status and isinstance(stem_status["stem"], dict):
            stem_mapping = {
                'drumsmp3': 'beat_audio',  # FIXED: Changed from 'drum_audio' to 'beat_audio'
                'vocalsmp3': 'vocal_audio',
                'bassmp3': 'bass_audio',
                'othermp3': 'melody_audio'  # Map "other" to melody
            }
            
            for stem_key, stem_value in stem_status["stem"].items():
                mapped_key = stem_mapping.get(stem_key)
                if mapped_key and "url" in stem_value:
                    stem_urls[mapped_key] = stem_value["url"]
                    print(f"Mapped stem {stem_key} to {mapped_key}: {stem_value['url']}")
        
        # Add the original URL as the original_audio
        if "original" in stem_status and "url" in stem_status["original"]:
            stem_urls["original_audio"] = stem_status["original"]["url"]
        
        # Now run the sample pack generation
        print("Running sample pack generation...")
        
        # Start sample pack generation - this may time out, which is expected
        try:
            sample_result = proxy.run_sample_pack(
                stem_exe_id,
                original_file,
                job_type=job_type,
                components=components,
                genre=genre,
                file_urls=stem_urls
            )
        except Exception as e:
            # Check if this is a timeout exception, which is expected
            if "timeout" in str(e).lower() or "read timed out" in str(e).lower():
                sample_result = {
                    "exeId": stem_exe_id,
                    "state": "processing",
                    "info": "Sample pack generation initiated but timed out"
                }
            else:
                # If not a timeout, re-raise
                raise
        
        # Begin polling for results regardless of whether the initiation call timed out
        sample_exe_id = sample_result.get("exeId") or stem_exe_id
        
        # Set up polling variables
        print(f"Starting to poll for sample pack results with execution ID: {sample_exe_id}")
        poll_start_time = time.time()
        max_poll_time = 10 * 60  # 10 minutes maximum polling time
        min_poll_time = 60  # At least 60 seconds of polling, even if state is "completed"
        poll_interval = 5  # 5 seconds between polls
        previous_samples = []
        no_change_count = 0
        download_folder = os.path.join(results_dir, f"{sample_exe_id}_samples")
        downloaded_files = {}
        
        # Create the results folder
        os.makedirs(download_folder, exist_ok=True)
        
        # Poll until we find the results, encounter a terminal error, or timeout
        while (time.time() - poll_start_time) < max_poll_time:
            try:
                # Get the current status
                sample_status = proxy.get_execution(sample_exe_id)
                current_state = sample_status.get("state", "processing")
                
                
                # Debug the execution response structure to help diagnose issues
                debug_execution_structure(sample_status)
                
                # Check for failure
                if current_state == "failed":
                    error_msg = sample_status.get("error", "Unknown error")
                    raise AudialError(f"Sample pack generation failed: {error_msg}")
                
                # Extract sample URLs using the enhanced extraction function
                current_samples = extract_sample_urls(sample_status)
                
                # Attempt to fetch sample URLs from files endpoint if none found directly
                if not current_samples:
                    try:
                        # Query the files endpoint directly for sample files
                        files_result = proxy.get_execution_files_by_type(sample_exe_id, "sample")
                        if files_result and 'urls' in files_result and files_result['urls']:
                            current_samples.extend(files_result['urls'])
                    except Exception as e:
                        print(f"Error querying files endpoint: {str(e)}")
                
                # If we have samples, download them
                if current_samples:
                    for url in current_samples:
                        try:
                            # Get the filename from the URL
                            filename = os.path.basename(url)
                            
                            # Handle URL encoding
                            if "%" in filename:
                                from urllib.parse import unquote
                                filename = unquote(filename)
                            
                            # Ensure valid filename
                            filename = filename.replace('/', '_').replace('\\', '_')
                            
                            # Set local path
                            local_path = os.path.join(download_folder, filename)
                            
                            # Skip if already downloaded
                            if os.path.exists(local_path):
                                downloaded_files[filename] = local_path
                                continue
                            
                            # Download the file
                            print(f"Downloading sample file: {filename}")
                            response = requests.get(url, timeout=30)
                            
                            if response.status_code == 200:
                                with open(local_path, 'wb') as f:
                                    f.write(response.content)
                                
                                downloaded_files[filename] = local_path
                                print(f"Downloaded to {local_path}")
                            else:
                                print(f"Failed to download {filename}: HTTP {response.status_code}")
                        
                        except Exception as e:
                            print(f"Error downloading sample file: {str(e)}")
                    
                    # Check if samples have changed since last poll
                    if len(current_samples) == len(previous_samples):
                        # Check if all samples are the same
                        all_same = True
                        current_set = set(current_samples)
                        previous_set = set(previous_samples)
                        
                        if current_set == previous_set:
                            no_change_count += 1
                            
                            # If we've had no changes for 2 polls, consider it complete
                            # But only if we've been polling for at least min_poll_time seconds
                            if no_change_count >= 2 and (time.time() - poll_start_time) > min_poll_time:
                                break
                        else:
                            # Samples have changed, reset counter
                            no_change_count = 0
                    else:
                        # Samples count changed, reset counter
                        no_change_count = 0
                    
                    # Update the previous samples list
                    previous_samples = list(current_samples)
                    
                    # If we've been polling for at least min_poll_time and have samples, we can stop
                    # if the state is "completed" or we've polled for double the min time
                    if (time.time() - poll_start_time) > min_poll_time and len(current_samples) > 0:
                        if current_state == "completed" or (time.time() - poll_start_time) > 2 * min_poll_time:
                            break
                else:
                    # No samples yet - check if we should try special queries to find samples
                    # Try querying specific sample directories
                    for component in components:
                        try:
                            component_files = proxy.get_execution_files_by_type(sample_exe_id, f"sample/{component}")
                            if component_files and 'urls' in component_files and component_files['urls']:
                                current_samples.extend(component_files['urls'])
                        except Exception as e:
                            print(f"Error querying {component} files: {str(e)}")
                    
                    # If we found samples through special queries, process them
                    if current_samples:
                        # Update the previous samples list and continue polling
                        previous_samples = list(current_samples)
                        continue
                    
                    # No samples found through any method - don't immediately give up if state is "completed" 
                    # Keep polling if we haven't met the minimum wait time
                    if current_state == "completed" and (time.time() - poll_start_time) > min_poll_time:
                        time.sleep(poll_interval)
                        
                        # Try one more time to get samples
                        last_chance_status = proxy.get_execution(sample_exe_id)
                        
                        # Check for samples one more time with our enhanced extraction
                        last_chance_samples = extract_sample_urls(last_chance_status)
                        
                        # Try directly querying files endpoint as a last resort
                        if not last_chance_samples:
                            try:
                                last_files = proxy.get_execution_files_by_type(sample_exe_id, "sample")
                                if last_files and 'urls' in last_files:
                                    last_chance_samples.extend(last_files['urls'])
                            except Exception as e:
                                print(f"Error in final files query: {str(e)}")
                        
                        
                        if last_chance_samples:
                            # Process these samples but then exit the polling loop
                            current_samples = last_chance_samples
                            sample_status = last_chance_status
                            # Download these samples
                            for url in current_samples:
                                try:
                                    filename = os.path.basename(url)
                                    if "%" in filename:
                                        from urllib.parse import unquote
                                        filename = unquote(filename)
                                    filename = filename.replace('/', '_').replace('\\', '_')
                                    local_path = os.path.join(download_folder, filename)
                                    
                                    if os.path.exists(local_path):
                                        downloaded_files[filename] = local_path
                                        continue
                                    
                                    response = requests.get(url, timeout=30)
                                    
                                    if response.status_code == 200:
                                        with open(local_path, 'wb') as f:
                                            f.write(response.content)
                                        downloaded_files[filename] = local_path
                                except Exception as e:
                                    print(f"Error downloading final sample: {str(e)}")
                            break
                        else:
                            # Really no samples after final check, end polling
                            break
                
                # Wait before polling again if we need to continue
                elapsed_seconds = int(time.time() - poll_start_time)
                time.sleep(poll_interval)
                
            except Exception as e:
                print(f"Error during polling: {str(e)}")
                # Continue polling despite errors
                time.sleep(poll_interval)
        
        # Check if we timed out without completing
        if (time.time() - poll_start_time) >= max_poll_time:
            # If we have any samples, consider it a partial success
            if downloaded_files:
                print(f"Returning {len(downloaded_files)} samples found before timeout")
            else:
                print("No samples found before timeout")
        
        # Return the results, even if only partial
        return {
            "execution": sample_status if 'sample_status' in locals() else {"exeId": sample_exe_id, "state": "timeout"},
            "files": {
                "folder": download_folder,
                "files": downloaded_files
            }
        }
    
    except Exception as e:
        # Handle errors
        raise AudialError(f"Sample pack generation failed: {str(e)}")