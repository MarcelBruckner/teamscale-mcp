import base64

import httpx
import pytest

from server import TeamscaleBasicAuth, _incoming_token, _incoming_user


def _run_auth(request):
    flow = TeamscaleBasicAuth().auth_flow(request)
    next(flow)  # apply the single mutation and yield the request
    return request


def test_assembles_basic_auth_from_contextvars():
    _incoming_user.set("alice")
    _incoming_token.set("s3cret")
    request = _run_auth(httpx.Request("GET", "http://teamscale:8080/api/x"))
    expected = "Basic " + base64.b64encode(b"alice:s3cret").decode()
    assert request.headers["Authorization"] == expected


def test_missing_user_raises():
    _incoming_user.set(None)
    _incoming_token.set("s3cret")
    with pytest.raises(RuntimeError):
        _run_auth(httpx.Request("GET", "http://teamscale:8080/api/x"))


def test_missing_token_raises():
    _incoming_user.set("alice")
    _incoming_token.set(None)
    with pytest.raises(RuntimeError):
        _run_auth(httpx.Request("GET", "http://teamscale:8080/api/x"))
