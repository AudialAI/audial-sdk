"""
Configuration management for the Audial SDK.
"""

import os
import json
from pathlib import Path
from typing import Optional
import dotenv

# Load environment variables from .env file if it exists
dotenv.load_dotenv()

# Configuration constants
DEFAULT_RESULTS_FOLDER = "./audial_results"
CONFIG_ENV_VAR = "AUDIAL_API_KEY"
USER_ID_ENV_VAR = "AUDIAL_USER_ID"
CONFIG_FILE_NAME = ".audial_config.json"
DEFAULT_USER_ID = None  # No default user ID, should be explicitly provided

# Determine config file path based on OS
def _get_config_file_path() -> Path:
    """Get the path to the config file."""
    home_dir = Path.home()
    
    # Windows
    if os.name == "nt":
        config_dir = home_dir / "AppData" / "Roaming" / "Audial"
    # macOS/Linux
    else:
        config_dir = home_dir / ".audial"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / CONFIG_FILE_NAME

def _load_config() -> dict:
    """Load configuration from file."""
    config_file = _get_config_file_path()
    if not config_file.exists():
        return {"api_key": None, "results_folder": DEFAULT_RESULTS_FOLDER, "user_id": DEFAULT_USER_ID}
    
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
            # Ensure the user_id field exists
            if "user_id" not in config:
                config["user_id"] = DEFAULT_USER_ID
            return config
    except (json.JSONDecodeError, IOError):
        return {"api_key": None, "results_folder": DEFAULT_RESULTS_FOLDER, "user_id": DEFAULT_USER_ID}

def _save_config(config: dict) -> None:
    """Save configuration to file."""
    config_file = _get_config_file_path()
    
    try:
        with open(config_file, "w") as f:
            json.dump(config, f)
        
        # Set file permissions to 0600
        os.chmod(config_file, 0o600)
    except IOError as e:
        raise IOError(f"Could not save configuration to {config_file}: {str(e)}")

def get_api_key() -> Optional[str]:
    """
    Get the API key from environment variable or config file.
    
    Returns:
        str: The API key if found, None otherwise.
    """
    # Check environment variable first
    api_key = os.environ.get(CONFIG_ENV_VAR)
    if api_key:
        return api_key
    
    # Then check config file
    config = _load_config()
    return config.get("api_key")

def set_api_key(api_key: str) -> None:
    """
    Set the API key in the config file.
    
    Args:
        api_key (str): The API key to set.
    """
    config = _load_config()
    config["api_key"] = api_key
    _save_config(config)

def get_user_id() -> Optional[str]:
    """
    Get the user ID from environment variable or config file.
    
    Returns:
        str: The user ID if found, None otherwise.
    """
    # Check environment variable first
    user_id = os.environ.get(USER_ID_ENV_VAR)
    if user_id:
        return user_id
    
    # Then check config file
    config = _load_config()
    return config.get("user_id")

def set_user_id(user_id: str) -> None:
    """
    Set the user ID in the config file.
    
    Args:
        user_id (str): The user ID to set.
    """
    config = _load_config()
    config["user_id"] = user_id
    _save_config(config)

def get_results_folder() -> str:
    """
    Get the results folder path.
    
    Returns:
        str: The path to the results folder.
    """
    config = _load_config()
    return config.get("results_folder", DEFAULT_RESULTS_FOLDER)

def set_results_folder(folder_path: str) -> None:
    """
    Set the results folder path.
    
    Args:
        folder_path (str): The path to the results folder.
    """
    config = _load_config()
    config["results_folder"] = folder_path
    _save_config(config)

def verify_api_key() -> bool:
    """
    Verify that an API key is available.
    
    Returns:
        bool: True if an API key is available, False otherwise.
    """
    return get_api_key() is not None

def verify_user_id() -> bool:
    """
    Verify that a user ID is available.
    
    Returns:
        bool: True if a user ID is available, False otherwise.
    """
    return get_user_id() is not None