import pytest
import pytest_asyncio

from ._client import HEALTH_URL, make_client, stack_reachable


def _skip_if_down() -> None:
    if not stack_reachable():
        pytest.skip(f"live MCP stack not reachable at {HEALTH_URL}")


@pytest.fixture
def require_stack():
    """Skip when the stack is down, without opening a client.

    For tests that build their own client (e.g. with a deliberately wrong token)
    or talk to the endpoint directly.
    """
    _skip_if_down()


@pytest_asyncio.fixture
async def client():
    """A connected fastmcp Client against the running MCP server.

    Skips the test when the stack is unreachable, so the live suite is a no-op
    when nothing is running (the unit suite still runs).
    """
    _skip_if_down()
    async with make_client() as connected:
        yield connected
