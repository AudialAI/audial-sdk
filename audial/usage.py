"""
API usage: how many API calls the account has used this month.

``GET /functions/allowance`` carries an ``api`` block with the plan, the
monthly limit and what is left. Reading it costs no API call.
"""

from typing import Any, Dict, Optional

from audial.api.proxy import AudialProxy

__all__ = ["usage"]


def usage(api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Read the account's API usage for the month.

    ::

        >>> audial.usage()
        {'plan': 'creator', 'monthlyLimit': 100, 'used': 42, 'remaining': 58,
         'topupRemaining': 0, 'resetsAt': 1798000000000}

    Args:
        api_key (str, optional): API key override.

    Returns:
        Optional[Dict[str, Any]]: The ``api`` block of ``/functions/allowance``:
            ``plan`` ("creator", "pro", "studio" or "default"), ``monthlyLimit``,
            ``used``, ``remaining``, ``topupRemaining`` and ``resetsAt``
            (milliseconds since the epoch, or None before the first call).
            None when the API sent no ``api`` block.

    Raises:
        AudialAuthError: If the credentials are rejected.
        AudialAPIError: If the API returns any other error.
    """
    body = AudialProxy(api_key).get_allowance()
    block = body.get("api") if isinstance(body, dict) else None
    return block if isinstance(block, dict) else None
