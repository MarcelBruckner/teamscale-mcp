import base64

import httpx
import pytest

from server import fetch_spec


def test_downloads_spec_with_basic_auth_and_param():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("authorization")
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"openapi": "3.0.1", "paths": {}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    spec = fetch_spec("http://teamscale:8080", "tech", "tok", False, client=client)

    assert spec == {"openapi": "3.0.1", "paths": {}}
    assert captured["auth"] == "Basic " + base64.b64encode(b"tech:tok").decode()
    assert "include-internal=false" in captured["url"]


def test_include_internal_true_sets_param():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"openapi": "3.0.1", "paths": {}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetch_spec("http://teamscale:8080/", "tech", "tok", True, client=client)
    assert "include-internal=true" in captured["url"]


def test_http_error_is_wrapped_in_runtimeerror():
    def handler(request):
        return httpx.Response(401)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="openapi.json"):
        fetch_spec("http://teamscale:8080", "tech", "tok", client=client)
