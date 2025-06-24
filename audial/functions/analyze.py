"""
Audio analysis implementation for Audial SDK.
"""

from typing import Dict, Any, Optional
import os
import time
import json

from audial.api.proxy import AudialProxy
from audial.api.constants import API_BASE_URL
from audial.api.exceptions import AudialError
from audial.utils.config import get_api_key, get_results_folder

def analyze(
    file_path: str,
    results_folder: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze an audio file to extract metadata like BPM, key, and other characteristics.
    
    Args:
        file_path (str): Path to the audio file.
        results_folder (str, optional): Folder to save results. Uses default if None.
        api_key (str, optional): API key to use. Uses default if None.
        
    Returns:
        Dict[str, Any]: Analysis results including BPM, key, and other metadata.
        
    Raises:
        AudialError: If analysis fails.
    """
    # Initialize configuration
    api_key = api_key or get_api_key()
    results_dir = results_folder or get_results_folder()
    
    # Ensure results directory exists
    os.makedirs(results_dir, exist_ok=True)
    
    # Initialize proxy
    proxy = AudialProxy(api_key)
    
    # Execute workflow
    try:
        # Upload the file FIRST
        print(f"Uploading file: {file_path}")
        file_data = proxy.upload_file(file_path)
        filename = file_data.get("filename")
        print(f"File uploaded: {filename}")
        
        # Create execution with the original file data
        execution = proxy.create_execution('analysis', original=file_data)
        exe_id = execution["exeId"]
        
        print("Running primary analysis...")
        analysis_result = proxy.run_primary_analysis(exe_id, file_data["url"])
        print(analysis_result)
        
        # Extract BPM and key from analysis response
        bpm = None
        key = None
        analysis_exe_id = None
        
        # Check different possible response structures
        if isinstance(analysis_result, dict):
            # Check for execution ID in analysis response
            if 'exeId' in analysis_result:
                analysis_exe_id = analysis_result['exeId']
            
            # Check completion state
            state = analysis_result.get('state')
            
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
                
        # Print the analysis results
        # print(f"Analysis completed: BPM={bpm}, Key={key}")
        
        # If we don't have bpm or key yet, and have an analysis execution ID,
        # try to get more details from the analysis execution
        if (bpm is None or key is None) and analysis_exe_id and analysis_exe_id != exe_id:
            try:
                analysis_exe = proxy.get_execution(analysis_exe_id)
                
                if isinstance(analysis_exe, dict):
                    if 'original' in analysis_exe and isinstance(analysis_exe['original'], dict):
                        if bpm is None and 'bpm' in analysis_exe['original']:
                            bpm = analysis_exe['original']['bpm']
                        if key is None and 'key' in analysis_exe['original']:
                            key = analysis_exe['original']['key']
                
            except Exception as e:
                print(f"Warning: Could not get additional analysis details: {str(e)}")
        
        # By this point, for a simple analysis, we should already have the information we need.
        # The primary analysis execution should be complete with the BPM and key data.
        
        # Get the final execution data
        result = proxy.get_execution(exe_id)
        
        # Extract all analysis information
        analysis_data = {
            "bpm": bpm,
            "key": key,
            "execution_id": exe_id
        }
        
        # Add any additional metadata from the result
        if "original" in result and isinstance(result["original"], dict):
            for k, value in result["original"].items():
                if k not in analysis_data:
                    analysis_data[k] = value
        
        # Save analysis data to JSON file
        original_filename = os.path.basename(file_path)
        result_folder = os.path.join(results_dir, f"{original_filename}_analysis")
        os.makedirs(result_folder, exist_ok=True)
        
        analysis_file_path = os.path.join(result_folder, "analysis.json")
        with open(analysis_file_path, 'w') as f:
            json.dump(analysis_data, f, indent=2)
        
        # Return the analysis data
        return {
            "execution": result,
            "analysis": analysis_data,
            "files": {
                "folder": result_folder,
                "files": {
                    "analysis.json": analysis_file_path
                }
            }
        }
    
    except Exception as e:
        # Handle errors
        raise AudialError(f"Audio analysis failed: {str(e)}")