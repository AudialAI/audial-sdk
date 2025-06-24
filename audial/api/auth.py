"""
Authentication utilities for the Audial SDK.
"""

from typing import Dict
import uuid
import os
import json

from audial.api.exceptions import AudialAuthError
from audial.utils.config import get_user_id

def load_dotenv():
    """
    Load environment variables from .env file.
    """
    try:
        # Check if .env file exists
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip().strip('"\'')
                        os.environ[key.strip()] = value
    except Exception as e:
        print(f"Warning: Could not load .env file: {str(e)}")

def get_api_key():
    """
    Get the API key from environment or config file.
    
    Returns:
        str: The API key.
        
    Raises:
        AudialAuthError: If no API key is available.
    """
    # Try to load from .env file first
    load_dotenv()
    
    # Check environment variable
    api_key = os.environ.get("AUDIAL_API_KEY")
    
    if not api_key:
        # Check config file
        config_dir = os.path.expanduser("~/.audial")
        config_file = os.path.join(config_dir, "config.json")
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    api_key = config.get("api_key")
            except Exception as e:
                pass
    
    # If still no API key, raise an error
    if not api_key:
        raise AudialAuthError(
            "No API key available. Please set your API key using "
            "audial.config.set_api_key() or by setting the AUDIAL_API_KEY "
            "environment variable."
        )
    
    return api_key

def get_auth_headers(api_key: str = None) -> Dict[str, str]:
    """
    Get the authentication headers for API requests.
    
    Args:
        api_key (str, optional): The API key to use. If not provided, it will be loaded from the configuration.
        
    Returns:
        Dict[str, str]: The authentication headers.
        
    Raises:
        AudialAuthError: If no API key is available.
    """
    # Get API key from config if not provided
    if api_key is None:
        api_key = get_api_key()
    
    # Check if API key is available
    if not api_key:
        raise AudialAuthError(
            "No API key available. Please set your API key using "
            "audial.config.set_api_key() or by setting the AUDIAL_API_KEY "
            "environment variable."
        )
    
    # Get user ID from configuration
    user_id = get_user_id()
    if not user_id:
        raise AudialAuthError(
            "No user ID available. Please set your user ID using "
            "audial.config.set_user_id() or by setting the AUDIAL_USER_ID "
            "environment variable."
        )
    
    # Generate request ID for tracking
    request_id = str(uuid.uuid4())
    
    # Return headers matching exactly what the frontend sends
    # This is critical - including both x-api-key and Authorization headers,
    # as well as the required x-user-id header
    # print(f"Using API Key: {api_key}, Using x-user-id: {user_id}")
    return {
        # "Authorization": f"Bearer {api_key}",
        "x-api-key": api_key,
        "x-user-id": user_id,  
        "Content-Type": "application/json",
        "X-Request-ID": request_id
    }
