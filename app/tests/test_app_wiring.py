import httpx

import server
from server import (
    AUTH_MODE_ENV,
    TeamscaleBasicAuth,
    TeamscaleBearerAuth,
    TokenCaptureMiddleware,
    build_asgi_app,
    build_server,
)

FAKE_SPEC = {
    "openapi": "3.0.1",
    "info": {"title": "Teamscale REST API", "version": "test"},
    "paths": {
        "/api/findings": {
            "get": {
                "operationId": "getFindings",
                "tags": ["Findings"],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        }
    },
}


def _client():
    return httpx.AsyncClient(base_url="http://teamscale:8080")


def test_headers_mode_uses_basic_auth_and_wrapping(monkeypatch):
    monkeypatch.delenv(AUTH_MODE_ENV, raising=False)
    client = _client()
    mcp = build_server(client=client, spec=FAKE_SPEC)
    assert isinstance(client.auth, TeamscaleBasicAuth)
    assert mcp.auth is None
    app = build_asgi_app(mcp)
    assert isinstance(app, TokenCaptureMiddleware)


def test_oauth_mode_uses_bearer_auth_and_no_wrapping(monkeypatch):
    monkeypatch.setenv(AUTH_MODE_ENV, "oauth")

    sentinel = object()
    monkeypatch.setattr(server, "build_auth", lambda: sentinel)

    client = _client()
    mcp = build_server(client=client, spec=FAKE_SPEC)
    assert isinstance(client.auth, TeamscaleBearerAuth)
    assert mcp.auth is sentinel

    # mcp.auth is a bare sentinel object here (not a real AuthProvider), which
    # proves it was forwarded from build_auth() -- but FastMCP's http_app()
    # would crash trying to build real auth middleware/routes from it. Swap in
    # None so we can still exercise build_asgi_app's mode-based wrap/no-wrap
    # branch (which is driven by auth_mode(), not by mcp.auth) without needing
    # a full fake OIDCProxy.
    mcp.auth = None
    app = build_asgi_app(mcp)
    assert not isinstance(app, TokenCaptureMiddleware)


def test_injected_client_with_existing_auth_is_not_overwritten(monkeypatch):
    monkeypatch.delenv(AUTH_MODE_ENV, raising=False)
    preset = TeamscaleBasicAuth()
    client = _client()
    client.auth = preset
    build_server(client=client, spec=FAKE_SPEC)
    assert client.auth is preset


def test_error_server_force_token_gate_wraps_in_oauth_mode(monkeypatch):
    monkeypatch.setenv(AUTH_MODE_ENV, "oauth")

    from server import build_error_server

    mcp = build_error_server(RuntimeError("boom"))
    app = build_asgi_app(mcp, force_token_gate=True)
    assert isinstance(app, TokenCaptureMiddleware)


def test_build_asgi_app_oauth_unwrapped_without_force(monkeypatch):
    monkeypatch.setenv(AUTH_MODE_ENV, "oauth")
    monkeypatch.setattr(server, "build_auth", lambda: None)

    client = _client()
    mcp = build_server(client=client, spec=FAKE_SPEC)
    app = build_asgi_app(mcp)
    assert not isinstance(app, TokenCaptureMiddleware)
