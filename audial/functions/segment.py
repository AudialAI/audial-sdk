"""
Audio segmentation implementation for Audial SDK.
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

def segment(
    file_path: str,
    components: Optional[List[str]] = None,
    analysis_type: Optional[str] = None,
    features: Optional[List[str]] = None,
    genre: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Segment an audio file into logical sections and analyze its components.
    
    Args:
        file_path (str): Path to the audio file.
        components (List[str], optional): Components to segment (default: ["bass", "beat", "melody", "vocal"]).
        analysis_type (str, optional): Type of analysis to perform (default: "select_features").
        features (List[str], optional): Features to extract (default: ["mode", "energy", "loudness", "danceability", "tatum", "lyrics", "tags"]).
        genre (str, optional): Genre of the track (default: "Default").
        results_folder (str, optional): Folder to save results. Uses default if None.
        api_key (str, optional): API key to use. Uses default if None.
        
    Returns:
        Dict[str, Any]: Segmentation results.
        
    Raises:
        AudialError: If segmentation fails.
    """
    # Set default values
    components = components or ["bass", "beat", "melody", "vocal"]
    analysis_type = analysis_type or "select_features"
    features = features or ["mode", "energy", "loudness", "danceability", "tatum", "lyrics", "tags"]
    genre = genre or "Default"
    
    # Validate genre
    valid_genres = [
        "Default", "Afro House", "Tech House", "Bass House", "Blues", "Breakbeat",
        "Classic Rock", "Country", "Deep House", "Drum N Bass", "Dubstep", "Gospel",
        "Grime140", "House", "Indie", "Jazz", "Latin", "Metal", "Minimal House",
        "Pop", "R&B", "Rock", "Techno", "Trance", "Trap", "UK Garage"
    ]
    
    if genre not in valid_genres:
        raise AudialError(f"Invalid genre: {genre}. Must be one of: {', '.join(valid_genres)}")
    
    # Validate features
    valid_features = ["mode", "energy", "loudness", "danceability", "tatum", "lyrics", "key", "tags"]
    
    for feature in features:
        if feature not in valid_features:
            raise AudialError(f"Invalid feature: {feature}. Must be one of: {', '.join(valid_features)}")
    
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
        # Check if the file exists
        if not os.path.isfile(file_path):
            raise AudialError(f"File not found: {file_path}")
        
        execution = proxy.create_execution()
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
        
        # For segmentation, we need to split the track into stems first
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
        
        # Prepare the file URLs for segmentation
        file_urls = {}
        
        # Get the stem URLs from the stem result
        if "stem" in stem_status and isinstance(stem_status["stem"], dict):
            stem_mapping = {
                'drumsmp3': 'beat_audio',
                'vocalsmp3': 'vocal_audio', 
                'bassmp3': 'bass_audio',
                'othermp3': 'melody_audio'
            }
            
            for stem_key, stem_value in stem_status["stem"].items():
                mapped_key = stem_mapping.get(stem_key)
                if mapped_key and "url" in stem_value:
                    file_urls[mapped_key] = stem_value["url"]
        
        # Add the original URL as the segmentation_audio
        if "original" in stem_status and "url" in stem_status["original"]:
            file_urls["segmentation_audio"] = stem_status["original"]["url"]
        
        # Now run the segmentation - ONLY ONCE
        print("Running segmentation...")
        
        # Update the original file info for segmentation
        original_file.update({
            "type": "audio/mpeg",
            "exeId": stem_exe_id
        })
        
        # Prepare the segmentation request data for logging
        segmentation_request = {
            "job_type": "segment_analysis",
            "userId": user_id,
            "userId": user_id,
            "original": original_file,
            "segmentationParameters": {
                "components": components,
                "bpm": bpm,
                "keyString": key,
                "analysisType": analysis_type,
                "featuresToExtract": features,
                "genre": genre
            },
            "execution_id": stem_exe_id,
            "executionId": stem_exe_id,
            "bpm": bpm,
            "key_string": key,
            "keyString": key,
            "analysis_type": analysis_type,
            "features_to_extract": features,
            "genre": genre,
            "fileUrls": file_urls
        }
        
        # Run the segmentation - we do this ONCE and ONLY ONCE
        segmentation_result = proxy.run_segmentation(
            stem_exe_id,
            original_file,
            components=components,
            analysis_type=analysis_type,
            features=features,
            genre=genre,
            file_urls=file_urls
        )
        
        # Store the segmentation execution ID
        segment_exe_id = segmentation_result.get("exeId")
        if not segment_exe_id:
            raise AudialError("Failed to get execution ID from segmentation result")
            
        
        # Poll for segmentation completion - using ONLY get_execution, NOT run_segmentation
        print("Polling for segmentation completion...")
        max_poll_time = 600  # 10 minutes
        poll_interval = 5  # 5 seconds
        poll_start = time.time()
        pruned_file_key = None
        found_pruned_file = False
        
        # Keep track of poll count for logging
        poll_count = 0
        
        # Poll until we find the results, encounter an error, or timeout
        while (time.time() - poll_start) < max_poll_time:
            poll_count += 1
            
            try:
                # ONLY use get_execution to check status, NOT run_segmentation
                segment_status = proxy.get_execution(segment_exe_id)
                
                # Get the current state
                state = segment_status.get("state")
                
                # Check for completion or failure
                if state == "completed":
                    print("Segmentation completed successfully.")
                    break
                elif state == "failed":
                    error_msg = segment_status.get("error", "Unknown error")
                    raise AudialError(f"Segmentation failed: {error_msg}")
                
                # Even if not completed, check for segmentation files
                if "segmentation" in segment_status and segment_status["segmentation"]:
                    segmentation_files = segment_status["segmentation"]
                    
                    # Look for pruned file
                    for key in segmentation_files.keys():
                        if "pruned_" in key.lower() and "audio_segmentation" in key.lower():
                            pruned_file_key = key
                            found_pruned_file = True
                            
                            # If we have the pruned file and it's been at least 30 seconds
                            # since we started polling, consider it done even if state isn't "completed"
                            if (time.time() - poll_start) > 30:
                                break
                
                # If we found the pruned file, we can exit the polling loop
                if found_pruned_file and (time.time() - poll_start) > 30:
                    break
                
                # Wait before next poll
                time.sleep(poll_interval)
                
            except Exception as e:
                print(f"Error during segmentation polling: {str(e)}")
                # Continue polling despite error
                time.sleep(poll_interval)
        
        # Check if we timed out without completing
        if (time.time() - poll_start) >= max_poll_time:
            # Try one last get_execution to see if we have any results
            try:
                segment_status = proxy.get_execution(segment_exe_id)
                # Check for segmentation files again
                if "segmentation" in segment_status and segment_status["segmentation"]:
                    for key in segment_status["segmentation"].keys():
                        if "pruned_" in key.lower() and "audio_segmentation" in key.lower():
                            pruned_file_key = key
                            found_pruned_file = True
            except Exception as e:
                print(f"Error checking final status: {str(e)}")
        
        # If we still don't have the pruned file, raise an error
        if not found_pruned_file:
            raise AudialError("Segmentation did not produce expected results")
        
        # Create result folder
        result_folder = os.path.join(results_dir, f"{segment_exe_id}_segmentation")
        os.makedirs(result_folder, exist_ok=True)
        
        downloaded_files = {}
        segmentation_data = None
        
        # Download the pruned JSON file if found
        if "segmentation" in segment_status and pruned_file_key and pruned_file_key in segment_status["segmentation"]:
            file_info = segment_status["segmentation"][pruned_file_key]
            if "url" in file_info:
                file_url = file_info["url"]
                
                # Get the filename, but we need to handle it differently
                url_filename = file_info.get("filename", os.path.basename(file_url))
                
                # Create a clean, flat filename without directories
                if "%" in url_filename:
                    from urllib.parse import unquote
                    decoded_name = unquote(url_filename)
                else:
                    decoded_name = url_filename
                    
                # Extract just the base filename without any path structure
                # We want the pruned_*.json part without any directories
                base_filename = os.path.basename(decoded_name)
                
                # Ensure it's a valid filename
                base_filename = base_filename.replace('/', '_').replace('\\', '_')
                
                # Set the local path without nested directories
                local_path = os.path.join(result_folder, base_filename)
                
                # Download the file
                print(f"Downloading Results: {base_filename}...")
                
                try:
                    # Try direct URL download first
                    response = requests.get(file_url, timeout=30)
                    
                    if response.status_code == 200:
                        # Create the directory if it doesn't exist
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        
                        with open(local_path, 'wb') as f:
                            f.write(response.content)
                        
                        downloaded_files[base_filename] = local_path
                        print(f"Downloaded to {local_path}")
                        
                        # Load and parse the segmentation data
                        try:
                            with open(local_path, 'r') as f:
                                json_content = json.load(f)
                            
                            if "audio_segmentation" in json_content:
                                segmentation_data = json_content["audio_segmentation"]
                        except Exception as e:
                            print(f"Error parsing segmentation data: {str(e)}")
                    else:
                        # Construct API URL similar to MIDI code
                        api_url = f"{API_BASE_URL}/files/{user_id}/execution/{segment_exe_id}/segmentation/{os.path.basename(url_filename)}"
                        
                        headers = get_auth_headers(api_key)
                        api_response = requests.get(api_url, headers=headers, timeout=30)
                        
                        if api_response.status_code == 200:
                            with open(local_path, 'wb') as f:
                                f.write(api_response.content)
                            
                            downloaded_files[base_filename] = local_path
                            print(f"Downloaded via API to {local_path}")
                            
                            # Load and parse the segmentation data
                            try:
                                with open(local_path, 'r') as f:
                                    json_content = json.load(f)
                                
                                if "audio_segmentation" in json_content:
                                    segmentation_data = json_content["audio_segmentation"]
                            except Exception as e:
                                print(f"Error parsing segmentation data: {str(e)}")
                        else:
                            print(f"API download failed: {api_response.status_code}")
                except Exception as e:
                    print(f"Error downloading {base_filename}: {str(e)}")
        
        # Return the results
        return {
            "execution": segment_status,
            "segmentation": segmentation_data,
            "files": {
                "folder": result_folder,
                "files": downloaded_files
            }
        }
    
    except Exception as e:
        # Handle errors
        raise AudialError(f"Audio segmentation failed: {str(e)}")