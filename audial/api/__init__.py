"""
API client for the Audial SDK.
"""

from audial.api.proxy import AudialProxy
from audial.api.auth import get_auth_headers
from audial.api.exceptions import AudialError, AudialAuthError, AudialAPIError

__all__ = [
    "AudialProxy",
    "get_auth_headers",
    "AudialError",
    "AudialAuthError",
    "AudialAPIError",
]