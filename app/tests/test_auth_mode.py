import pytest

import server
from server import AUTH_MODE_ENV, auth_mode, build_auth


def test_auth_mode_defaults_to_headers(monkeypatch):
    monkeypatch.delenv(AUTH_MODE_ENV, raising=False)
    assert auth_mode() == "headers"


def test_auth_mode_oauth(monkeypatch):
    monkeypatch.setenv(AUTH_MODE_ENV, "oauth")
    assert auth_mode() == "oauth"


def test_auth_mode_rejects_unknown(monkeypatch):
    monkeypatch.setenv(AUTH_MODE_ENV, "banana")
    with pytest.raises(RuntimeError):
        auth_mode()


def test_build_auth_none_in_headers_mode(monkeypatch):
    monkeypatch.delenv(AUTH_MODE_ENV, raising=False)
    assert build_auth() is None


def test_build_auth_raises_when_oauth_config_missing(monkeypatch):
    monkeypatch.setenv(AUTH_MODE_ENV, "oauth")
    for var in ("TEAMSCALE_OIDC_CONFIG_URL", "TEAMSCALE_OIDC_CLIENT_ID",
                "TEAMSCALE_OIDC_CLIENT_SECRET", "MCP_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError):
        build_auth()


def test_build_auth_constructs_oidc_proxy(monkeypatch):
    monkeypatch.setenv(AUTH_MODE_ENV, "oauth")
    monkeypatch.setenv("TEAMSCALE_OIDC_CONFIG_URL",
                       "https://idp.example/.well-known/openid-configuration")
    monkeypatch.setenv("TEAMSCALE_OIDC_CLIENT_ID", "cid")
    monkeypatch.setenv("TEAMSCALE_OIDC_CLIENT_SECRET", "secret")
    monkeypatch.setenv("TEAMSCALE_OIDC_AUDIENCE", "teamscale")
    monkeypatch.setenv("MCP_BASE_URL", "https://mcp.example")

    captured = {}

    class FakeOIDCProxy:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    # Patch the symbol used inside server so no network discovery happens.
    monkeypatch.setattr(server, "OIDCProxy", FakeOIDCProxy)

    auth = build_auth()
    assert isinstance(auth, FakeOIDCProxy)
    assert str(captured["config_url"]) == \
        "https://idp.example/.well-known/openid-configuration"
    assert captured["client_id"] == "cid"
    assert captured["client_secret"] == "secret"
    assert captured["audience"] == "teamscale"
    assert str(captured["base_url"]) == "https://mcp.example"
    assert captured["verify_id_token"] is False
