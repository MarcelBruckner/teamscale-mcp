#!/usr/bin/env bash
#
# Run the test suite under app/tests/. Unit tests (mock httpx transport) need no
# running Teamscale; the live integration tests (app/tests/live/) drive the running
# MCP server and auto-skip when it's unreachable. Bring up `docker compose up -d`
# first to exercise them. Extra args pass through to pytest.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT/app"
uv run pytest "$@"
