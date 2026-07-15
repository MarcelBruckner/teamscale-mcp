"""Regression test for free-form map request bodies.

Several Teamscale operations take a request body that is a free-form map
(OpenAPI ``{"type": "object", "additionalProperties": {...}}`` with no named
``properties``) -- e.g. ``getFindingTypeDescriptions``, ``setFindingDueDates``.

FastMCP's OpenAPI provider represents such a whole-body value as a single
synthetic ``body`` argument, but its RequestDirector then reconstructs the
outgoing body as ``{"body": <the map>}`` because the body schema's type is
"object". Teamscale rejects that double-wrapped shape with
``400 Cannot parse JSON because of mismatched input data``. build_server()
installs a patch so the map is forwarded verbatim.
"""

import json

import httpx
from fastmcp import Client

from server import build_server

MAP_BODY_SPEC = {
    "openapi": "3.0.1",
    "info": {"title": "Teamscale REST API", "version": "test"},
    "paths": {
        "/api/projects/{project}/finding-type-descriptors": {
            "post": {
                "operationId": "getFindingTypeDescriptions",
                "parameters": [
                    {
                        "name": "project",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "additionalProperties": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {"schema": {"type": "object"}}
                        },
                    }
                },
            }
        }
    },
}


def _capturing_client(captured: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content) if request.content else None
        return httpx.Response(200, json={})

    return httpx.AsyncClient(
        base_url="http://teamscale:8080",
        transport=httpx.MockTransport(handler),
    )


async def test_map_body_is_forwarded_unwrapped():
    captured: dict = {}
    mcp = build_server(client=_capturing_client(captured), spec=MAP_BODY_SPEC)
    async with Client(mcp) as client:
        await client.call_tool(
            "getFindingTypeDescriptions",
            {"project": "p", "body": {"scope": ["T1"]}},
        )
    # The map must reach Teamscale verbatim, not wrapped under a "body" key.
    assert captured["body"] == {"scope": ["T1"]}


async def test_empty_map_body_is_forwarded_unwrapped():
    captured: dict = {}
    mcp = build_server(client=_capturing_client(captured), spec=MAP_BODY_SPEC)
    async with Client(mcp) as client:
        await client.call_tool(
            "getFindingTypeDescriptions",
            {"project": "p", "body": {}},
        )
    assert captured["body"] == {}
