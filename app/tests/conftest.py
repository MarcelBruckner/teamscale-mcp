import pytest

from server import _incoming_token, _incoming_user


@pytest.fixture(autouse=True)
def reset_contextvars():
    """Ensure contextvars are reset to None after each test."""
    yield
    # Reset to defaults after each test
    _incoming_user.set(None)
    _incoming_token.set(None)
