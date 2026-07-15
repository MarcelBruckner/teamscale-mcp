from server import TokenCaptureMiddleware, _incoming_token, _incoming_user


async def _call(mw, scope):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await mw(scope, receive, send)
    return sent


async def _ok_app(scope, receive, send):
    # Records the identity visible to the wrapped app, then returns 200.
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"downstream"})


def _scope(path, headers):
    return {"type": "http", "path": path, "headers": headers}


async def test_missing_both_headers_returns_401():
    sent = await _call(TokenCaptureMiddleware(_ok_app), _scope("/mcp", []))
    assert sent[0]["status"] == 401


async def test_missing_token_returns_401():
    headers = [(b"x-teamscale-user", b"alice")]
    sent = await _call(TokenCaptureMiddleware(_ok_app), _scope("/mcp", headers))
    assert sent[0]["status"] == 401


async def test_health_bypasses_auth():
    sent = await _call(TokenCaptureMiddleware(_ok_app), _scope("/health", []))
    assert sent[0]["status"] == 200


async def test_both_headers_populate_contextvars_and_forward():
    seen = {}

    async def spy_app(scope, receive, send):
        seen["user"] = _incoming_user.get()
        seen["token"] = _incoming_token.get()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    headers = [(b"x-teamscale-user", b"alice"), (b"x-teamscale-token", b"tok")]
    sent = await _call(TokenCaptureMiddleware(spy_app), _scope("/mcp", headers))
    assert sent[0]["status"] == 200
    assert seen == {"user": "alice", "token": "tok"}
    # Reset after the request completes.
    assert _incoming_user.get() is None
    assert _incoming_token.get() is None
