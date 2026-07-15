# Contributing

- [Local development environment](#local-development-environment)
  - [Seeded instance credentials](#seeded-instance-credentials)
  - [Talking to the MCP server](#talking-to-the-mcp-server)
- [Running the tests](#running-the-tests)
  - [Running against a clean, reproducible fixture](#running-against-a-clean-reproducible-fixture)
- [Tools generated from the OpenAPI spec](#tools-generated-from-the-openapi-spec)

## Local development environment

The repo ships a ready-to-run dev stack: a throwaway Teamscale instance plus the MCP
server built from local source.

```bash
docker compose up -d --build
```

This starts two services (see [`docker-compose.yaml`](docker-compose.yaml)):

| Service         | URL                       | Notes                                        |
| --------------- | ------------------------- | --------------------------------------------- |
| `teamscale`     | http://localhost:8080     | Web UI + REST API                             |
| `teamscale-mcp` | http://localhost:8081/mcp | MCP endpoint (built from local `Dockerfile`)  |

The `teamscale-mcp` service uses `build: .`, so it always runs your local code. After
changing anything under `app/`, rebuild with `docker compose up -d --build`.

Check the MCP server is up:

```bash
curl http://localhost:8081/health   # -> ok
```

### Seeded instance credentials

Committed as a **development fixture**, scoped to this disposable instance only — do
not reuse it anywhere real.

- **Teamscale web UI:** log in at http://localhost:8080 as `admin` using the API
  token in [`api.token`](api.token) as the password (or generate your own via
  *Admin → Users*).
- **API token:** [`api.token`](api.token) — also wired up as `TEAMSCALE_SPEC_TOKEN`
  for the `teamscale-mcp` service in `docker-compose.yaml`, and the credential an MCP
  client passes in the `X-Teamscale-Token` header (paired with `X-Teamscale-User:
  admin`).

The clean seeded state is committed as [`teamscale-backup.zip`](teamscale-backup.zip) —
a Teamscale backup export of the disposable instance — so a known fixture can be
restored for testing. The live `teamscale-data/` directory the container reads and
writes is untracked (only its volatile subdirs are gitignored; see
[`.gitignore`](.gitignore)).

### Talking to the MCP server

Point any MCP client at the endpoint with the dev username + token:

```bash
claude mcp add teamscale-dev --transport http \
  http://localhost:8081/mcp \
  --header "X-Teamscale-User: admin" \
  --header "X-Teamscale-Token: $(cat api.token)"
```

## Running the tests

Tests live in `app/tests/` and come in two kinds:

- **Unit tests** (`app/tests/test_*.py`) drive `server.py` through a mock HTTP
  transport — no running Teamscale required.
- **Live integration tests** (`app/tests/live/`) drive the *running* MCP server over
  HTTP with `fastmcp.Client`, exercising the real Teamscale behind it. They
  **auto-skip** when the MCP `/health` endpoint is unreachable, so the suite still
  passes with nothing running. Bring the [dev stack](#local-development-environment)
  up first to run them.

[`run-tests.sh`](run-tests.sh) runs both kinds; extra arguments pass through to
`pytest`:

```bash
./run-tests.sh                       # full suite (live tests skip if the stack is down)
./run-tests.sh tests/live -v         # just the live tests
./run-tests.sh -k test_fetch_spec    # a single test by keyword
```

Or run pytest directly:

```bash
cd app
uv run pytest        # or: .venv/bin/python -m pytest
```

The live tests target the dev stack and the committed `api.token` by default;
override with `TEAMSCALE_MCP_URL`, `TEAMSCALE_MCP_USER`, `TEAMSCALE_MCP_TOKEN`, and
`TEAMSCALE_MCP_PROJECT` to point them elsewhere.

### Running against a clean, reproducible fixture

[`run-tests-clean.sh`](run-tests-clean.sh) resets Teamscale to the committed seed
before testing, so the live tests always run against a known state. It:

1. stops the stack and wipes `teamscale-data/{repo,storage,logs}` (keeping
   `config/teamscale.license`);
2. starts a fresh Teamscale — a wiped instance comes up as `admin` / `admin`;
3. logs in to obtain a REST **access key** (Teamscale's Basic auth uses the access
   key as the password, not the login password) and imports
   [`teamscale-backup.zip`](teamscale-backup.zip);
4. triggers re-analysis and waits for findings — the backup restores the project
   **config + Git connectors**, and Teamscale re-analyzes the source from GitHub to
   regenerate the findings (needs network; ~a couple of minutes for the seed
   projects);
5. rebuilds and starts the MCP server, then runs pytest (extra args pass through).

```bash
./run-tests-clean.sh                 # full reset, then the whole suite
./run-tests-clean.sh tests/live -q   # reset, then just the live tests
```

It is destructive to the local instance data (which is disposable) but leaves the
stack running and seeded at the end. Overrides: `TEAMSCALE_ADMIN_USER` /
`TEAMSCALE_ADMIN_PASSWORD` (default `admin`/`admin`) and `FINDINGS_TIMEOUT` (default
1200s). Use the quick [`run-tests.sh`](run-tests.sh) instead when you just want to
run pytest against whatever is already up.

## Tools generated from the OpenAPI spec

All MCP tools are generated automatically at startup from the **live** Teamscale
OpenAPI spec (`GET {TEAMSCALE_SERVER_URL}/openapi.json`) via `FastMCP.from_openapi` —
see [`app/server.py`](app/server.py). The tool surface can be narrowed with
`TEAMSCALE_EXCLUDE_TAGS`/`TEAMSCALE_INCLUDE_TAGS`. Endpoints that don't fit the generic
JSON-in/JSON-out mold can be special-cased in `app/server.py` as they're discovered — cover
any such handling with a test in `app/tests/`.
