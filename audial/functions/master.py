"""
Audio mastering implementation for Audial SDK.
"""

from typing import Dict, Any, Optional
import os
import time
import json
from urllib.parse import urlparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from audial.api.proxy import AudialProxy
from audial.api.constants import API_BASE_URL
from audial.api.exceptions import AudialError
from audial.utils.config import get_api_key, get_results_folder, get_user_id


def master(
    file_path: str,
    reference_file: Optional[str] = None,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Apply professional mastering to an audio file.
    
    Args:
        file_path (str): Path to the audio file to master.
        reference_file (str, optional): Path to a reference file to match sound characteristics.
        results_folder (str, optional): Folder to save results. Uses default if None.
        api_key (str, optional): API key to use. Uses default if None.
        
    Returns:
        Dict[str, Any]: Results data including paths to downloaded files.
        
    Raises:
        AudialError: If mastering fails.
    """
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
        execution = proxy.create_execution()
        exe_id = execution["exeId"]
        
        # Function to upload a file and return its data
        def upload_file(file_path, file_type="main"):
            try:
                print(f"Uploading {file_type} file: {file_path}")
                file_data = proxy.upload_file(file_path)
                print(f"{file_type.capitalize()} file uploaded: {file_data.get('filename')}")
                return file_data
            except Exception as e:
                print(f"Error uploading {file_type} file: {str(e)}")
                raise
        
        # Upload both files concurrently
        file_data = None
        reference_data = None
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Start the main file upload
            main_upload = executor.submit(upload_file, file_path, "main")
            
            # Start reference file upload if provided
            ref_upload = None
            if reference_file:
                ref_upload = executor.submit(upload_file, reference_file, "reference")
            
            # Get results as they complete
            for future in as_completed([main_upload, ref_upload] if ref_upload else [main_upload]):
                try:
                    result = future.result()
                    if future == main_upload:
                        file_data = result
                    elif future == ref_upload:
                        reference_data = result
                except Exception as e:
                    raise AudialError(f"File upload failed: {str(e)}")
        
        # Verify we have the main file data
        if not file_data:
            raise AudialError("Failed to upload main file")
        
        # Prepare mastering request payload
        print("Starting mastering process...")
        mastering_request = {
            "userId": user_id,
            "original": {
                "exeId": exe_id,
                "filename": file_data.get("filename"),
                "url": file_data["url"],
                "type": file_data.get("type", "audio/mpeg")
                # Note: We're not including BPM and key since primary analysis is not needed
            }
        }
        
        # Add reference file if provided
        if reference_data:
            mastering_request["reference"] = {
                "exeId": exe_id,
                "filename": reference_data.get("filename"),
                "url": reference_data["url"],
                "type": reference_data.get("type", "audio/mpeg")
            }
                
        try:
            # Run mastering
            mastering_result = proxy.run_mastering(
                exe_id,
                mastering_request["original"],
                mastering_request.get("reference")
            )
            
            # Check if we got an immediate result
            if isinstance(mastering_result, dict):
                print("Received mastering result")
                result = mastering_result
                # Store the execution ID for polling
                new_exe_id = mastering_result.get("exeId", exe_id)
            else:
                # If no immediate result, we'll need to poll
                result = None
                new_exe_id = exe_id
                
        except Exception as e:
            print(f"Warning: Mastering request returned an error: {str(e)}")
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
            max_processing_time = 15 * 60  # 15 minutes timeout
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
                        raise AudialError(f"Mastering failed: {error}")
                    
                    # If not complete, wait with backoff
                    wait_time = min(max_backoff, backoff * (1 + attempt * 0.1))
                    print(f"Processing in progress... Waiting {wait_time:.1f} seconds (elapsed: {int(elapsed)}s)")
                    time.sleep(wait_time)
                    
                except Exception as e:
                    print(f"Error checking status: {str(e)}")
                    time.sleep(backoff)
        
        # At this point, we should have a result with mastered data
        if not result or not isinstance(result, dict):
            raise AudialError("Failed to retrieve execution results")
        
        # Download the mastered file
        print("Downloading mastered file...")
        result_folder = os.path.join(results_dir, f"{new_exe_id}_master")
        os.makedirs(result_folder, exist_ok=True)
        
        try:
            # Get the result execution ID
            result_exe_id = result.get("exeId", new_exe_id)
            
            # Extract filename - first try to get it from the result
            master_filename = None
            
            # Try to get filename from master data
            if "master" in result and isinstance(result["master"], dict):
                master_info = result["master"]
                if "filename" in master_info:
                    master_filename = master_info["filename"]
            
            # Try to get filename from modified data if not found
            if not master_filename and "modified" in result and isinstance(result["modified"], dict):
                modified_info = result["modified"]
                if "filename" in modified_info:
                    master_filename = modified_info["filename"]
            
            # If still no filename, construct one from original filename
            if not master_filename:
                original_filename = None
                if "original" in result and isinstance(result["original"], dict):
                    original_filename = result["original"].get("filename")
                
                if original_filename:
                    master_filename = f"{os.path.splitext(original_filename)[0]}-Mastered.mp3"
                else:
                    master_filename = "mastered.mp3"
            
            # Clean up filename - remove URL encoding
            if '%' in master_filename:
                from urllib.parse import unquote
                master_filename = unquote(master_filename)
            
            # Remove path components if present
            if '/' in master_filename:
                master_filename = master_filename.split('/')[-1]
            
            # Construct the API URL to download the file
            api_url = f"{API_BASE_URL}/files/{user_id}/execution/{result_exe_id}/master/{master_filename}"
            local_file_path = os.path.join(result_folder, master_filename)
                        
            # Use the same headers as in your other API calls
            headers = {
                "Authorization": f"Bearer {api_key}",
                "x-api-key": api_key,
                "x-user-id": user_id
            }
            
            response = requests.get(api_url, headers=headers, stream=True, timeout=30)
            
            if response.status_code == 200:
                with open(local_file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                print(f"Successfully downloaded mastered file to {local_file_path}")
                
                # Return the results
                return {
                    "execution": result,
                    "files": {
                        "folder": result_folder,
                        "files": {
                            master_filename: local_file_path
                        }
                    }
                }
            else:
                print(f"Failed to download mastered file, status code: {response.status_code}")
                print(f"Response body: {response.text[:200]}...")
                raise AudialError(f"Failed to download mastered file: HTTP {response.status_code}")
        except Exception as e:
            print(f"Error downloading mastered file: {str(e)}")
            raise AudialError(f"Failed to download mastered file: {str(e)}")
    
    except Exception as e:
        # Handle errors
        raise AudialError(f"Audio mastering failed: {str(e)}")