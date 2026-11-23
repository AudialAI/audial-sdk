"""
Exceptions for the Audial SDK.
"""

from datetime import datetime, timezone

class AudialError(Exception):
    """Base exception for all Audial SDK errors."""
    pass

class AudialAuthError(AudialError):
    """Exception raised for authentication errors."""
    pass

class AudialAPIError(AudialError):
    """
    Exception raised for API errors.

    `status_code` is the HTTP status (None for a transport error) and `code`
    the API's machine-readable error code when it sent one, e.g.
    "STEMS_NOT_READY" or "ADDON_UNAVAILABLE" (both HTTP 409, from the analysis
    add-ons), "INVALID_INPUT" or "SUBSCRIPTION_REQUIRED".
    """
    def __init__(self, message, status_code=None, response=None, code=None):
        self.status_code = status_code
        self.response = response
        self.code = code
        super().__init__(message)

    @property
    def retry_after(self):
        """
        Seconds the API asked us to wait (the `Retry-After` header of a 429),
        or None when the response had none.
        """
        headers = getattr(self.response, "headers", None)
        if not headers:
            return None
        try:
            value = headers.get("Retry-After")
            seconds = float(value) if value is not None else None
        except (TypeError, ValueError, AttributeError):
            return None
        return seconds if seconds is not None and seconds >= 0 else None

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
            code="SUBSCRIPTION_REQUIRED",
        )


class AudialLimitReached(AudialAPIError):
    """
    Raised when the account has used all its API calls for the month: HTTP 402
    with code "API_LIMIT_REACHED". It is final until the reset, so the SDK
    never retries it.

    Attributes:
        limit (int): Calls included in the plan this month.
        used (int): Calls used so far.
        resets_at (datetime or None): When the count resets, a timezone-aware
            UTC datetime (the API sends milliseconds since the epoch). None if
            the API did not say.
        upgrade_url (str or None): Where to get more calls.
    """
    def __init__(self, limit=None, used=None, resets_at=None, upgrade_url=None,
                 response=None, message=None):
        self.limit = limit
        self.used = used
        self.resets_at = resets_at
        self.upgrade_url = upgrade_url
        super().__init__(
            message or self._build_message(),
            status_code=402,
            response=response,
            code="API_LIMIT_REACHED",
        )

    def _build_message(self):
        text = "Monthly API limit reached"
        if self.limit is not None and self.used is not None:
            text += f" ({self.used}/{self.limit})"
        text += "."
        if self.resets_at is not None:
            text += f" Resets {self.resets_at.strftime('%Y-%m-%d')}."
        if self.upgrade_url:
            text += f" More calls: {self.upgrade_url}"
        return text

    @classmethod
    def from_body(cls, body, response=None):
        """Build it from the API's 402 JSON body."""
        body = body if isinstance(body, dict) else {}
        resets_at = None
        ms = body.get("resetsAt")
        if isinstance(ms, (int, float)) and not isinstance(ms, bool):
            try:
                resets_at = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                resets_at = None
        return cls(
            limit=body.get("limit"),
            used=body.get("used"),
            resets_at=resets_at,
            upgrade_url=body.get("upgradeUrl"),
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
