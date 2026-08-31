"""Unit tests for the /api/analyze rate limiter (web.api.enforce_rate_limit).

Calls the limiter function directly rather than going through FastAPI's
TestClient -- httpx (TestClient's transport dependency) isn't in this
project's dependency set, and adding it isn't worth the risk this close to
the submission deadline for what a direct function call already proves.
"""
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from web.api import (
    enforce_rate_limit,
    _client_ip,
    _RATE_LIMIT_BUCKETS,
    RATE_LIMIT_MAX_REQUESTS,
    RATE_LIMIT_WINDOW_S,
)


def make_request(ip: str = "1.2.3.4", cf_header: str | None = None) -> Mock:
    request = Mock()
    request.client.host = ip
    request.headers = {"cf-connecting-ip": cf_header} if cf_header else {}
    return request


@pytest.fixture(autouse=True)
def clean_buckets():
    _RATE_LIMIT_BUCKETS.clear()
    yield
    _RATE_LIMIT_BUCKETS.clear()


def test_requests_within_budget_pass():
    request = make_request("10.0.0.1")
    for i in range(RATE_LIMIT_MAX_REQUESTS):
        enforce_rate_limit(request, now=float(i))  # no exception


def test_request_over_budget_raises_429():
    request = make_request("10.0.0.2")
    for i in range(RATE_LIMIT_MAX_REQUESTS):
        enforce_rate_limit(request, now=0.0)

    with pytest.raises(HTTPException) as exc_info:
        enforce_rate_limit(request, now=0.0)

    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


def test_window_slides_and_recovers():
    request = make_request("10.0.0.3")
    for i in range(RATE_LIMIT_MAX_REQUESTS):
        enforce_rate_limit(request, now=0.0)

    with pytest.raises(HTTPException):
        enforce_rate_limit(request, now=0.0)

    # Past the window: old entries expire, request succeeds again.
    enforce_rate_limit(request, now=RATE_LIMIT_WINDOW_S + 1.0)


def test_clients_are_isolated():
    request_a = make_request("10.0.0.4")
    request_b = make_request("10.0.0.5")

    for i in range(RATE_LIMIT_MAX_REQUESTS):
        enforce_rate_limit(request_a, now=0.0)

    with pytest.raises(HTTPException):
        enforce_rate_limit(request_a, now=0.0)

    # Different client, same instant: unaffected.
    enforce_rate_limit(request_b, now=0.0)


def test_cf_connecting_ip_preferred_over_client_host():
    request = make_request(ip="10.0.0.6", cf_header="203.0.113.9")
    assert _client_ip(request) == "203.0.113.9"


def test_falls_back_to_client_host_without_cf_header():
    request = make_request(ip="10.0.0.7")
    assert _client_ip(request) == "10.0.0.7"
