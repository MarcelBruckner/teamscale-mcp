import httpx
from fastmcp import FastMCP

from server import build_error_server, register_health


async def _health_status(mcp: FastMCP) -> tuple[int, str]:
    """Hit /health on the given server's ASGI app without starting uvicorn.

    Uses httpx's ASGITransport directly (no lifespan needed -- the health
    route is a plain Starlette custom_route) rather than
    starlette.testclient.TestClient, which currently emits a deprecation
    warning about its httpx dependency.
    """
    app = mcp.http_app(path="/mcp", host_origin_protection=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        return response.status_code, response.text


async def test_error_server_health_reports_503():
    mcp = build_error_server(RuntimeError("spec download failed"))
    status, body = await _health_status(mcp)
    assert status == 503
    assert "startup failed" in body


async def test_normal_server_health_reports_200():
    mcp = FastMCP(name="Teamscale MCP")
    register_health(mcp)
    status, body = await _health_status(mcp)
    assert status == 200
    assert body == "ok"


async def test_error_server_exposes_only_startup_error():
    mcp = build_error_server(RuntimeError("spec download failed"))
    tools = await mcp.list_tools()
    assert "startup_error" in {t.name for t in tools}


async def test_startup_error_tool_reports_the_failure():
    mcp = build_error_server(RuntimeError("spec download failed"))
    result = await mcp.call_tool("startup_error", {})
    # The rendered result text mentions the failure reason.
    assert "spec download failed" in str(result)
