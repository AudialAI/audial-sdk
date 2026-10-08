"""
Signing in to Audial from a program that cannot show a login page.

`login()` asks the API for a short code, opens the approval page in the user's browser, and
waits until they approve. The API then issues an API key for this machine, which is saved in
the shared credentials file (see audial.utils.config) and used by the SDK, the `audial`
command and the Audial MCP server from then on.

`start_device_login()` and `wait_for_device_login()` are the two halves of `login()`, for
callers that need to show the link themselves or wait without blocking.
"""

import socket
import time
import webbrowser
from dataclasses import dataclass
from typing import Callable, Dict, Optional

import requests

from audial.api.constants import REQUEST_TIMEOUT, get_api_base_url
from audial.api.exceptions import AudialAPIError, AudialAuthError
from audial.utils import config

DEFAULT_CLIENT_NAME = "audial-sdk"


@dataclass(frozen=True)
class DeviceLogin:
    """A sign-in that is waiting for the user to approve it in their browser."""

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


def device_name() -> str:
    """This machine's name as the approval page and the key list show it."""
    name = socket.gethostname().split(".")[0].strip()
    return name or "this computer"


def start_device_login(client_name: str = DEFAULT_CLIENT_NAME) -> DeviceLogin:
    """Ask the API for a code pair. Send the user to `verification_uri_complete` next."""
    try:
        response = requests.post(
            f"{get_api_base_url()}/auth/device/code",
            json={"client_name": client_name, "device_name": device_name()},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        raise AudialAPIError(f"Could not reach Audial to sign in: {e}")
    if response.status_code != 200:
        raise AudialAPIError(
            f"Could not start sign-in: HTTP {response.status_code}",
            status_code=response.status_code,
            response=response,
        )
    data = response.json()
    return DeviceLogin(
        device_code=data["device_code"],
        user_code=data["user_code"],
        verification_uri=data["verification_uri"],
        verification_uri_complete=data["verification_uri_complete"],
        expires_in=int(data.get("expires_in", 600)),
        interval=int(data.get("interval", 5)),
    )


def poll_device_login(login: DeviceLogin) -> Optional[Dict[str, str]]:
    """
    Check once whether the user has approved. Returns the saved credentials when they have,
    None while the sign-in is still waiting.

    Raises:
        AudialAuthError: The user refused, or the code expired.
    """
    try:
        response = requests.post(
            f"{get_api_base_url()}/auth/device/token",
            json={"device_code": login.device_code},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return None  # a dropped connection is not a refusal; the next poll tries again

    try:
        data = response.json()
    except ValueError:
        data = {}

    if response.status_code == 200 and data.get("api_key"):
        return config.save_credentials(
            api_key=data["api_key"],
            user_id=data["user_id"],
            email=data.get("email"),
            key_name=data.get("key_name"),
        )

    error = data.get("error")
    if error in ("authorization_pending", "slow_down"):
        return None
    if error == "access_denied":
        raise AudialAuthError("Sign-in was cancelled in the browser.")
    if error == "expired_token":
        raise AudialAuthError("The sign-in code expired before it was approved. Start again.")
    raise AudialAPIError(
        f"Sign-in failed: HTTP {response.status_code}", status_code=response.status_code, response=response
    )


def wait_for_device_login(
    login: DeviceLogin,
    timeout: Optional[float] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Optional[Dict[str, str]]:
    """
    Poll until the user approves. Returns the saved credentials, or None if `timeout` seconds
    passed (or `should_stop()` returned True) first; the sign-in can still be approved and
    picked up by a later call.
    """
    deadline = time.monotonic() + (login.expires_in if timeout is None else min(timeout, login.expires_in))
    while time.monotonic() < deadline:
        if should_stop is not None and should_stop():
            return None
        credentials = poll_device_login(login)
        if credentials:
            return credentials
        time.sleep(max(1, login.interval))
    if timeout is None:
        raise AudialAuthError("The sign-in code expired before it was approved. Start again.")
    return None


def login(
    client_name: str = DEFAULT_CLIENT_NAME,
    open_browser: bool = True,
    on_prompt: Optional[Callable[[DeviceLogin], None]] = None,
) -> Dict[str, str]:
    """
    Sign in to Audial through the browser and save the result for later use.

    Args:
        client_name: What the approval page calls this program.
        open_browser: Open the approval page automatically. The link is still passed to
            `on_prompt`, for machines without a browser.
        on_prompt: Called once with the pending sign-in, to show the link and code.

    Returns:
        The saved credentials: api_key, user_id, email, key_name.
    """
    pending = start_device_login(client_name)
    if on_prompt is not None:
        on_prompt(pending)
    if open_browser:
        try:
            webbrowser.open(pending.verification_uri_complete)
        except Exception:
            pass  # no browser here; the caller has the link from on_prompt
    return wait_for_device_login(pending)


def whoami(api_key: str) -> Dict[str, Optional[str]]:
    """The account an API key belongs to: user_id, email and (for new-format keys) key_name."""
    try:
        response = requests.get(
            f"{get_api_base_url()}/auth/whoami", headers={"x-api-key": api_key}, timeout=REQUEST_TIMEOUT
        )
    except requests.exceptions.RequestException as e:
        raise AudialAPIError(f"Could not reach Audial: {e}")
    if response.status_code in (401, 403):
        raise AudialAuthError(
            "Audial did not accept this API key. Run `audial login` to sign in again, "
            "or check AUDIAL_API_KEY."
        )
    if response.status_code != 200:
        raise AudialAPIError(
            f"Could not look up the account: HTTP {response.status_code}",
            status_code=response.status_code,
            response=response,
        )
    return response.json()


def logout() -> bool:
    """
    Sign out on this machine: revoke the key that `login()` saved and delete it locally.
    Returns False when nobody was signed in.
    """
    credentials = config.load_credentials()
    if not credentials:
        return False
    try:
        requests.post(
            f"{get_api_base_url()}/auth/revoke",
            headers={"x-api-key": credentials["api_key"]},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        pass  # offline: still sign out locally; the key can be removed at audialmusic.ai
    config.clear_credentials()
    return True
