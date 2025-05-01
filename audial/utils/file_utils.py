"""
File utility functions for the Audial SDK.
"""

import os
from pathlib import Path
from typing import Optional
import requests
from tqdm import tqdm
import mimetypes

def get_file_extension(filename: str) -> str:
    """
    Get the extension of a file.
    
    Args:
        filename (str): The filename.
        
    Returns:
        str: The file extension.
    """
    return os.path.splitext(filename)[1].lower()

def download_file(url: str, destination: str) -> str:
    """
    Download a file from a URL to a local destination with progress bar.
    
    Args:
        url (str): The URL to download from.
        destination (str): The local path to save the file to.
        
    Returns:
        str: The path to the downloaded file.
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
    
    # Stream download with progress bar
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    total_size = int(response.headers.get('content-length', 0))
    block_size = 1024  # 1 Kibibyte
    
    with open(destination, 'wb') as file, tqdm(
        desc=os.path.basename(destination),
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(block_size):
            size = file.write(data)
            bar.update(size)
    
    return destination

def create_results_dir(base_dir: str, execution_id: str, result_type: str) -> str:
    """
    Create a directory for storing results.
    
    Args:
        base_dir (str): The base directory for results.
        execution_id (str): The execution ID.
        result_type (str): The type of result.
        
    Returns:
        str: The path to the created directory.
    """
    result_dir = os.path.join(base_dir, f"{execution_id}_{result_type}")
    os.makedirs(result_dir, exist_ok=True)
    return result_dir

def get_mime_type(file_path: str) -> str:
    """
    Get the MIME type of a file.
    
    Args:
        file_path (str): The path to the file.
        
    Returns:
        str: The MIME type of the file.
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        # Default to binary data if MIME type can't be determined
        mime_type = 'application/octet-stream'
    return mime_type