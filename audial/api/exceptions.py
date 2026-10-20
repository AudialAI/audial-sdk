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


class AudialValidationError(AudialError):
    """
    Exception raised for input the SDK rejects before calling the API.

    `position` locates the problem in the input the user wrote: for
    `lyrics_mode="per_note"` it is the 1-based index of the token (and so of
    the MIDI note) the message is about, so an editor can highlight that note.
    It is None when the message is not about one particular token.

    The API raises the same error server-side as
    `400 {"code": "LYRICS_INVALID", "position", "message"}`; the SDK turns
    that response back into this exception, so client-side and server-side
    rejections are caught the same way::

        try:
            audial.text2vox(..., lyrics_mode="per_note", lyrics=lyrics)
        except AudialValidationError as exc:
            print(exc, exc.position)
    """
    def __init__(self, message, position=None):
        self.message = message
        self.position = position
        super().__init__(message)
