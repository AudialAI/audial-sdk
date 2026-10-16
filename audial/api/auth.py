"""
Authentication utilities for the Audial SDK.
"""

from typing import Dict
import uuid
import os
import json

from audial.api.exceptions import AudialAuthError
from audial.utils.config import get_user_id
from audial.utils.config import get_api_key as _config_get_api_key


def get_api_key():
    """
    Get the API key from environment or config file.

    Returns:
        str: The API key.

    Raises:
        AudialAuthError: If no API key is available.
    """
    api_key = _config_get_api_key()

    if not api_key:
        raise AudialAuthError(
            "Not signed in to Audial. Run `audial login` (or audial.login() in Python) to "
            "sign in through your browser, or set the AUDIAL_API_KEY environment variable."
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
            "Not signed in to Audial. Run `audial login` (or audial.login() in Python) to "
            "sign in through your browser, or set the AUDIAL_API_KEY environment variable."
        )
    
    # The user ID that goes with this key (see audial.utils.config.get_user_id)
    user_id = get_user_id(api_key)
    if not user_id:
        raise AudialAuthError(
            "No user ID available for this API key. Run `audial login` to sign in through "
            "your browser, or set the AUDIAL_USER_ID environment variable."
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
