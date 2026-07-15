"""Shared helpers for the live integration tests.

These tests drive the *running* MCP server over HTTP (via `fastmcp.Client`),
exercising the real Teamscale REST API behind it. They auto-skip when the stack
is unreachable (see the `client` fixture in conftest.py), so `uv run pytest`
still passes with nothing running.

Config can be overridden by environment variables; the defaults target the dev
stack from docker-compose.yaml with the committed dev fixture credentials.
"""

import os
from pathlib import Path

import httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

# Dev-stack defaults (see docker-compose.yaml). Overridable for other targets.
MCP_URL = os.environ.get("TEAMSCALE_MCP_URL", "http://localhost:8081/mcp")
HEALTH_URL = MCP_URL.rsplit("/", 1)[0] + "/health"
DEV_USER = os.environ.get("TEAMSCALE_MCP_USER", "admin")

# Seeded fixture projects (from teamscale-backup.zip): "jabref" + "junit-framework".
PROJECT = os.environ.get("TEAMSCALE_MCP_PROJECT", "jabref")

_TOKEN_FILE = Path(__file__).resolve().parents[3] / "api.token"


def dev_token() -> str:
    """The per-request client token: env override, else the committed dev token."""
    return os.environ.get("TEAMSCALE_MCP_TOKEN") or _TOKEN_FILE.read_text().strip()


def stack_reachable() -> bool:
    """True when the MCP server answers /health with 'ok'."""
    try:
        response = httpx.get(HEALTH_URL, timeout=2.0)
    except httpx.HTTPError:
        return False
    return response.status_code == 200 and response.text.strip() == "ok"


def make_client(user: str = DEV_USER, token: str | None = None) -> Client:
    """A fastmcp Client that presents identity headers on every call.

    Defaults to the dev fixture identity; `user`/`token` override it (e.g. to
    assert that a wrong token is rejected).
    """
    transport = StreamableHttpTransport(
        MCP_URL,
        headers={
            "X-Teamscale-User": user,
            "X-Teamscale-Token": token if token is not None else dev_token(),
        },
    )
    return Client(transport)


def result_list(call_result) -> list:
    """Unwrap a list-returning tool result.

    FastMCP wraps a bare JSON array response as ``{"result": [...]}`` (structured
    output must be an object), so array tools like getAllProjects / getFindings
    surface their list under ``.data["result"]``.
    """
    data = call_result.data
    if isinstance(data, dict) and "result" in data:
        return data["result"]
    return data
