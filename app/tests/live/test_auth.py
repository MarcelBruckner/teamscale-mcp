"""Live tests for the auth model end-to-end through the running server.

Complements the unit tests: here the deployed middleware + Basic-auth
pass-through are exercised against real Teamscale.
"""

import httpx
import pytest

from ._client import MCP_URL, make_client


async def test_wrong_token_is_rejected(require_stack):
    """A present-but-invalid token passes the middleware but Teamscale rejects it."""
    async with make_client(token="definitely-not-a-valid-teamscale-token") as bad:
        with pytest.raises(Exception) as excinfo:
            await bad.call_tool("getAllProjects", {})
    message = str(excinfo.value)
    assert "401" in message or "Unauthorized" in message


def test_missing_identity_headers_are_rejected(require_stack):
    """The token-capture middleware rejects with 401 before MCP, when headers are absent."""
    response = httpx.post(
        MCP_URL,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        timeout=5.0,
    )
    assert response.status_code == 401
