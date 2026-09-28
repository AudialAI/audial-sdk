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

class SubscriptionRequiredError(AudialAPIError):
    """
    Exception raised when the API refuses a request with HTTP 402 and
    code "SUBSCRIPTION_REQUIRED".

    Some functions (e.g. sound2vital, text2vox) require an active Audial
    subscription on top of a valid API key.
    """
    def __init__(self, message=None, response=None):
        super().__init__(
            message or (
                "This feature needs an active Audial subscription. "
                "Subscribe at audialmusic.ai and try again."
            ),
            status_code=402,
            response=response,
        )