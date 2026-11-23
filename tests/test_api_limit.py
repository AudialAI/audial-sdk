"""
Tests for the API-call limit: 402 API_LIMIT_REACHED (final, never retried),
429 RATE_LIMITED with Retry-After, and audial.usage().

HTTP is mocked at requests.Session.get/post; the base URL points at a host
that does not exist and sleeping is mocked.
"""

import os
from datetime import datetime, timezone
from unittest import mock

import pytest

import audial
from audial.api.exceptions import (
    AudialAPIError,
    AudialLimitReached,
    SubscriptionRequiredError,
)
from audial.api.proxy import AudialProxy
from audial.functions import _addon

from conftest import FakeResponse

BASE = "https://api.test.invalid/api"

LIMIT_BODY = {
    "error": "You have used all 100 API calls for this month.",
    "code": "API_LIMIT_REACHED",
    "limit": 100,
    "used": 100,
    "resetsAt": 1798000000000,
    "upgradeUrl": "https://audialmusic.ai/product/pricing",
}


class Resp(FakeResponse):
    def __init__(self, status_code=200, json_data=None, headers=None):
        super().__init__(status_code, json_data)
        self.headers = headers or {}


@pytest.fixture(autouse=True)
def base_url(monkeypatch):
    monkeypatch.setenv("AUDIAL_API_BASE_URL", BASE)


def test_limit_reached_raises_after_one_request():
    with mock.patch("requests.Session.post", return_value=Resp(402, LIMIT_BODY)) as post, \
         mock.patch("time.sleep") as sleep:
        with pytest.raises(AudialLimitReached) as info:
            AudialProxy().run_addon("audio-tags", "exe-1")
    assert post.call_count == 1
    sleep.assert_not_called()
    exc = info.value
    assert (exc.limit, exc.used) == (100, 100)
    assert exc.upgrade_url == "https://audialmusic.ai/product/pricing"
    assert exc.resets_at == datetime.fromtimestamp(1798000000, tz=timezone.utc)
    assert exc.status_code == 402 and exc.code == "API_LIMIT_REACHED"
    assert isinstance(exc, AudialAPIError)
    assert str(exc) == (
        f"Monthly API limit reached (100/100). Resets {exc.resets_at:%Y-%m-%d}. "
        "More calls: https://audialmusic.ai/product/pricing"
    )


def test_limit_reached_is_not_retried_by_addon_loop():
    with mock.patch("requests.Session.post", return_value=Resp(402, LIMIT_BODY)) as post, \
         mock.patch("time.sleep") as sleep:
        with pytest.raises(AudialLimitReached):
            audial.tags("exe-1", wait_s=300)
    assert post.call_count == 1
    sleep.assert_not_called()


def test_limit_reached_is_not_retried_by_midi_loop():
    proxy = AudialProxy()
    with mock.patch("requests.Session.post", return_value=Resp(402, LIMIT_BODY)) as post, \
         mock.patch("time.sleep") as sleep:
        with pytest.raises(AudialLimitReached):
            proxy.run_generate_midi("exe-1", {"stems": []})
    assert post.call_count == 1
    sleep.assert_not_called()


def test_limit_reached_is_not_retried_by_pipeline_poll():
    with mock.patch("requests.Session.get", return_value=Resp(402, LIMIT_BODY)) as get, \
         mock.patch("time.sleep") as sleep:
        with pytest.raises(AudialLimitReached):
            audial.pipelines.get("pl-1")
    assert get.call_count == 1
    sleep.assert_not_called()


def test_subscription_required_is_unchanged():
    body = {"error": "Subscribe to continue.", "code": "SUBSCRIPTION_REQUIRED"}
    with mock.patch("requests.Session.post", return_value=Resp(402, body)) as post:
        with pytest.raises(SubscriptionRequiredError) as info:
            AudialProxy().run_addon("audio-tags", "exe-1")
    assert post.call_count == 1
    assert not isinstance(info.value, AudialLimitReached)
    assert info.value.code == "SUBSCRIPTION_REQUIRED"


def test_rate_limit_honours_retry_after():
    limited = Resp(
        429,
        {"error": "Too many calls.", "code": "RATE_LIMITED", "retryAfter": 2},
        headers={"Retry-After": "2"},
    )
    ok = Resp(200, {"exeId": "x", "state": "queued"})
    with mock.patch("requests.Session.post", side_effect=[limited, ok]) as post, \
         mock.patch("time.sleep") as sleep:
        _addon._start(AudialProxy(), "tags", "exe-1", False, None, 60, 0.1)
    assert post.call_count == 2
    waited = sum(c.args[0] for c in sleep.call_args_list)
    assert waited >= 2


def test_rate_limit_without_header_keeps_backoff():
    limited = Resp(429, {"error": "Too many calls.", "code": "RATE_LIMITED"})
    ok = Resp(200, {"exeId": "x", "state": "queued"})
    with mock.patch("requests.Session.post", side_effect=[limited, ok]), \
         mock.patch("time.sleep") as sleep:
        _addon._start(AudialProxy(), "tags", "exe-1", False, None, 60, 0.1)
    assert sleep.call_args_list[0].args[0] == pytest.approx(0.1)


def test_midi_retry_waits_for_retry_after():
    limited = Resp(429, {"error": "slow down", "code": "RATE_LIMITED", "retryAfter": 45},
                   headers={"Retry-After": "45"})
    ok = Resp(200, {"exeId": "x"})
    with mock.patch("requests.Session.post", side_effect=[limited, ok]), \
         mock.patch("time.sleep") as sleep:
        try:
            AudialProxy().run_generate_midi("exe-1", {"stems": []})
        except Exception:
            pass  # only the first wait matters here
    assert sleep.call_args_list[0].args[0] >= 45


def test_usage_returns_the_api_block():
    block = {"plan": "creator", "monthlyLimit": 100, "used": 42, "remaining": 58,
             "topupRemaining": 0, "resetsAt": 1798000000000}
    with mock.patch("requests.Session.get",
                    return_value=Resp(200, {"allowance": 2, "api": block})) as get:
        assert audial.usage() == block
    assert get.call_args.args[0] == f"{BASE}/functions/allowance"


def test_usage_is_none_when_absent():
    with mock.patch("requests.Session.get", return_value=Resp(200, {"allowance": 2})):
        assert audial.usage() is None
