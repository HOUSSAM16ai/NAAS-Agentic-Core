from collections.abc import Generator

import pytest

import app.auth.jwt_handler as jwt_module
from app.auth.jwt_handler import JWTHandler, get_jwt_handler


@pytest.fixture(autouse=True)
def reset_global_jwt_handler() -> Generator[None, None, None]:
    """
    Fixture to reset the global JWT handler before and after each test
    to ensure full test isolation.
    """
    # Setup: ensure it's None before test
    jwt_module._global_jwt_handler = None
    yield
    # Teardown: ensure it's None after test
    jwt_module._global_jwt_handler = None


def test_get_jwt_handler_initialization():
    """Test that the handler initializes correctly with a valid secret key."""
    handler = get_jwt_handler(secret_key="my-super-secret-key")

    assert isinstance(handler, JWTHandler)
    assert handler.secret_key == "my-super-secret-key"


def test_get_jwt_handler_missing_secret_first_call():
    """Test that calling without a secret key on the first call raises ValueError."""
    with pytest.raises(ValueError, match="secret_key is required for first initialization"):
        get_jwt_handler()


def test_get_jwt_handler_singleton():
    """Test that subsequent calls return the exact same instance."""
    handler1 = get_jwt_handler(secret_key="first-secret-key")
    handler2 = get_jwt_handler()

    assert handler1 is handler2


def test_get_jwt_handler_ignores_new_secret():
    """Test that calling with a different secret after initialization ignores it."""
    handler1 = get_jwt_handler(secret_key="original-secret")
    handler2 = get_jwt_handler(secret_key="new-secret")

    assert handler1 is handler2
    assert handler2.secret_key == "original-secret"
