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
# Written by `audial login` (audial.api.device_login). One file per machine, shared by the
# SDK, the `audial` command, the Audial MCP server and the Audial plugins.
CREDENTIALS_FILE_NAME = "credentials.json"
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

def _get_credentials_file_path() -> Path:
    """Path of the sign-in credentials file (next to the config file)."""
    return _get_config_file_path().parent / CREDENTIALS_FILE_NAME

def _current_api_base_url() -> str:
    # Imported here: audial.api imports this module.
    from audial.api.constants import get_api_base_url
    return get_api_base_url()

def load_credentials() -> Optional[dict]:
    """
    The credentials saved by signing in (`audial login`), or None when nobody is signed in.

    Credentials are only returned for the API they were issued by, so signing in to a local
    or staging API never gets its key sent to production or the other way round.
    """
    credentials_file = _get_credentials_file_path()
    try:
        with open(credentials_file, "r") as f:
            credentials = json.load(f)
    except (IOError, ValueError):
        return None
    if not isinstance(credentials, dict) or not credentials.get("api_key") or not credentials.get("user_id"):
        return None
    if credentials.get("api_base_url") != _current_api_base_url():
        return None
    return credentials

def save_credentials(api_key: str, user_id: str, email: Optional[str] = None, key_name: Optional[str] = None) -> dict:
    """Save sign-in credentials for this machine (file mode 0600) and return them."""
    credentials = {
        "api_key": api_key,
        "user_id": user_id,
        "email": email,
        "key_name": key_name,
        "api_base_url": _current_api_base_url(),
    }
    credentials_file = _get_credentials_file_path()
    # Created private from the start, so the key is never readable by other users.
    fd = os.open(credentials_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(credentials, f, indent=2)
    os.chmod(credentials_file, 0o600)
    return credentials

def clear_credentials() -> None:
    """Delete the saved sign-in credentials, if any."""
    try:
        _get_credentials_file_path().unlink()
    except FileNotFoundError:
        pass

def get_api_key() -> Optional[str]:
    """
    Get the API key: the AUDIAL_API_KEY environment variable, else the key saved by
    signing in (`audial login`), else the key set with set_api_key().
    
    Returns:
        str: The API key if found, None otherwise.
    """
    # Check environment variable first
    api_key = os.environ.get(CONFIG_ENV_VAR)
    if api_key:
        return api_key
    
    # Then the sign-in credentials
    credentials = load_credentials()
    if credentials:
        return credentials["api_key"]
    
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

# User ids looked up from the API for keys that were given without one, by key.
_user_id_by_key = {}

def get_user_id(api_key: Optional[str] = None) -> Optional[str]:
    """
    Get the user ID that goes with the API key in use.

    The AUDIAL_USER_ID environment variable wins when set. Otherwise the id comes from
    wherever the key came from: the sign-in credentials, or, for a key of the form
    "aud_...", the API itself (such a key identifies its owner, so no user ID has to be
    configured). Failing that, the user ID set with set_user_id().

    Args:
        api_key (str, optional): The key in use, when it was passed explicitly rather than
            taken from the configuration.
    
    Returns:
        str: The user ID if found, None otherwise.
    """
    # Check environment variable first
    user_id = os.environ.get(USER_ID_ENV_VAR)
    if user_id:
        return user_id
    
    api_key = api_key or get_api_key()
    credentials = load_credentials()
    if credentials and credentials["api_key"] == api_key:
        return credentials["user_id"]
    
    if api_key and api_key.startswith("aud_"):
        if api_key not in _user_id_by_key:
            from audial.api.device_login import whoami
            _user_id_by_key[api_key] = whoami(api_key)["user_id"]
        return _user_id_by_key[api_key]
    
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