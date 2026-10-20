"""
Service status: which Audial functions have a worker awake right now.

``GET /functions/status`` is the one call that can be made *before* a job
exists, so a client can warn about a cold start before the user waits through
one. It costs no rate-limit allowance and the API serves it from a cache.
"""

from typing import Any, Dict, Optional

from audial.api.proxy import AudialProxy

__all__ = ["status"]


def status(function: Optional[str] = None, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Ask which functions are warm (``GET /functions/status``).

    ::

        >>> audial.status("text2vox")
        {'items': [{'function': 'text2vox', 'warm': False, 'queued': 0,
                    'expectedColdStartMs': 180000, 'expectedRunMs': 42000}]}

    ``warm`` is False when every worker for that function is asleep: the next
    job will pay a cold start of roughly ``expectedColdStartMs`` on top of its
    own ``expectedRunMs``. ``audial.warmup`` turns that into the sentence the
    CLI, the website and the MCP server all show::

        doc = audial.status("text2vox")
        if audial.warmup.is_cold(doc, "text2vox"):
            print(audial.warmup.cold_start_message(
                audial.warmup.find_function(doc, "text2vox")["expectedColdStartMs"]
            ))

    Args:
        function (str, optional): Limit the answer to one function. Either an
            SDK name ("stem_split", "generate_samples", "text2vox") or the
            API's own name ("stem-splitter", "sample-pack"). Omit for every
            function.
        api_key (str, optional): API key override.

    Returns:
        Dict[str, Any]: ``{"items": [{"function", "warm", "queued",
            "expectedColdStartMs", "expectedRunMs"}, ...]}`` -- the API's
            envelope, unchanged. ``expectedColdStartMs`` and
            ``expectedRunMs`` are absent for a function with no history yet.

    Raises:
        AudialAuthError: If the credentials are rejected.
        AudialAPIError: If the API returns any other error.
    """
    return AudialProxy(api_key).get_functions_status(function)
