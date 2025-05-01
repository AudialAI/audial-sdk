"""
Results management for the Audial SDK.

This module handles downloading and organizing result files from the API.
"""

import os
from typing import Dict, Any, List, Optional

from audial.utils.file_utils import download_file

def download_results(
    proxy: Any,
    exe_id: str,
    result_type: str,
    destination_folder: str
) -> Dict[str, Any]:
    """
    Download results files and save to the specified folder.
    
    Args:
        proxy: The proxy client.
        exe_id (str): The execution ID.
        result_type (str): The type of results to download (e.g., 'stem', 'midi').
        destination_folder (str): The folder to save results to.
        
    Returns:
        Dict[str, Any]: Information about the downloaded files.
    """
    # Get file listings
    files_data = proxy.get_execution_files_by_type(exe_id, result_type)
    
    # Create results subfolder
    result_folder = os.path.join(destination_folder, f"{exe_id}_{result_type}")
    os.makedirs(result_folder, exist_ok=True)
    
    # Download each file
    downloaded_files = {}
    for url in files_data.get("urls", []):
        filename = os.path.basename(url)
        local_path = os.path.join(result_folder, filename)
        
        try:
            # Download file
            download_file(url, local_path)
            
            # Add to result
            downloaded_files[filename] = local_path
        except Exception as e:
            print(f"Warning: Failed to download {filename}: {str(e)}")
    
    return {
        "folder": result_folder,
        "files": downloaded_files
    }

def save_results(
    execution_data: Dict[str, Any],
    result_type: str,
    destination_folder: str
) -> Dict[str, Any]:
    """
    Save results from execution data to the specified folder.
    
    Args:
        execution_data (Dict[str, Any]): The execution data.
        result_type (str): The type of results to download (e.g., 'stem', 'midi').
        destination_folder (str): The folder to save results to.
        
    Returns:
        Dict[str, Any]: Information about the saved files.
    """
    exe_id = execution_data.get("exeId")
    if not exe_id:
        raise ValueError("Execution data must contain 'exeId'")
    
    # Create results subfolder
    result_folder = os.path.join(destination_folder, f"{exe_id}_{result_type}")
    os.makedirs(result_folder, exist_ok=True)
    
    # Process files based on result type
    downloaded_files = {}
    
    if result_type == "stem":
        file_data = execution_data.get("stem", {})
    elif result_type == "midi":
        file_data = execution_data.get("midi", {})
    elif result_type == "samples":
        file_data = execution_data.get("samples", {})
    elif result_type == "segmentation":
        file_data = execution_data.get("segmentation", {})
    elif result_type == "master":
        file_data = execution_data.get("master", {})
    else:
        file_data = {}
    
    # Download files
    for key, data in file_data.items():
        if isinstance(data, dict) and "url" in data and "filename" in data:
            try:
                filename = data["filename"]
                url = data["url"]
                local_path = os.path.join(result_folder, filename)
                
                # Download file
                download_file(url, local_path)
                
                # Add to result
                downloaded_files[filename] = local_path
            except Exception as e:
                print(f"Warning: Failed to download {key}: {str(e)}")
    
    return {
        "folder": result_folder,
        "files": downloaded_files
    }