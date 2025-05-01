"""
Exceptions for the Audial SDK.
"""

class AudialError(Exception):
    """Base exception for all Audial SDK errors."""
    pass

class AudialAuthError(AudialError):
    """Exception raised for authentication errors."""
    pass

class AudialAPIError(AudialError):
    """Exception raised for API errors."""
    def __init__(self, message, status_code=None, response=None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)