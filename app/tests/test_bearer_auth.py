import httpx
import pytest

import server
from server import TeamscaleBearerAuth


def _run_auth(request):
    flow = TeamscaleBearerAuth().auth_flow(request)
    next(flow)  # apply the single mutation and yield the request
    return request


class _FakeToken:
    def __init__(self, token):
        self.token = token


def test_sets_bearer_from_access_token(monkeypatch):
    monkeypatch.setattr(server, "get_access_token", lambda: _FakeToken("upstream-jwt"))
    request = _run_auth(httpx.Request("GET", "http://teamscale:8080/api/x"))
    assert request.headers["Authorization"] == "Bearer upstream-jwt"


def test_missing_access_token_raises(monkeypatch):
    monkeypatch.setattr(server, "get_access_token", lambda: None)
    with pytest.raises(RuntimeError):
        _run_auth(httpx.Request("GET", "http://teamscale:8080/api/x"))


def test_empty_token_raises(monkeypatch):
    monkeypatch.setattr(server, "get_access_token", lambda: _FakeToken(""))
    with pytest.raises(RuntimeError):
        _run_auth(httpx.Request("GET", "http://teamscale:8080/api/x"))
