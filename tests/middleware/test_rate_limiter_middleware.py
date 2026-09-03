import pytest
from starlette.requests import Request

from app.middleware.rate_limiter_middleware import (
    _rate_limiters,
    get_rate_limiter,
    reset_rate_limiter,
)


def _build_request(host: str) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "client": (host, 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
        "app": None,
        "asgi": {"version": "3.0", "spec_version": "2.3"},
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset the global _rate_limiters state before and after each test."""
    for limiter in _rate_limiters.values():
        limiter.reset()
    yield
    for limiter in _rate_limiters.values():
        limiter.reset()


def test_reset_rate_limiter_existing_key():
    limiter = get_rate_limiter("default")
    request = _build_request("1.1.1.1")

    # Consume one token
    allowed, metadata = limiter.is_allowed(request)
    assert allowed
    assert metadata["remaining"] == limiter.max_requests - 1

    # Consume another token
    allowed, metadata = limiter.is_allowed(request)
    assert allowed
    assert metadata["remaining"] == limiter.max_requests - 2

    # Reset the rate limiter
    reset_rate_limiter("default")

    # It should have max requests again
    allowed, metadata = limiter.is_allowed(request)
    assert allowed
    assert metadata["remaining"] == limiter.max_requests - 1


def test_reset_rate_limiter_non_existing_key():
    unknown_key = "non_existent_key_123"
    assert unknown_key not in _rate_limiters

    # This should not raise an exception
    reset_rate_limiter(unknown_key)

    # Assert that the unknown key was not added (no auto-vivification)
    assert unknown_key not in _rate_limiters
