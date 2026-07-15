#!/usr/bin/env bash
#
# Reset the dev Teamscale to the committed clean fixture, then run the tests.
#
# Flow:
#   1. stop the stack
#   2. wipe teamscale-data/{repo,storage,logs} (keeping config/teamscale.license)
#   3. start a fresh Teamscale
#   4. import teamscale-backup.zip via the REST API as the fresh-instance admin
#   5. wait until the seeded projects are restored
#   6. trigger re-analysis and wait until findings are computed (the backup is a
#      config backup: it restores project definitions + the Git connectors, and
#      Teamscale re-analyzes the source from GitHub to regenerate findings)
#   7. (re)build & start the MCP server against the restored instance
#   8. run pytest (extra args pass through, e.g. ./run-tests-clean.sh tests/live -q)
#
# A fresh Teamscale's admin is "admin" / "admin"; override with
# TEAMSCALE_ADMIN_USER / TEAMSCALE_ADMIN_PASSWORD. Teamscale's REST Basic auth
# expects an *access key* as the password (not the login password), so the
# script logs in once to obtain one, then imports the backup with it. Importing
# the backup restores the real admin user whose access key lives in api.token —
# which is what the MCP server (TEAMSCALE_SPEC_TOKEN) and the tests use afterwards.
#
# For the quick, non-destructive runner that just runs pytest against whatever is
# up, use run-tests.sh instead.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

TS_URL="${TEAMSCALE_URL:-http://localhost:8080}"
API="$TS_URL/api/v2026.4"
ADMIN_USER="${TEAMSCALE_ADMIN_USER:-admin}"
ADMIN_PW="${TEAMSCALE_ADMIN_PASSWORD:-admin}"
MCP_HEALTH="${MCP_HEALTH_URL:-http://localhost:8081/health}"
BACKUP="teamscale-backup.zip"
TOKEN="$(cat api.token)"

[ -f "$BACKUP" ] || { echo "ERROR: $BACKUP not found in $REPO_ROOT" >&2; exit 1; }

echo "== Stopping the stack =="
docker compose stop

echo "== Wiping Teamscale repo + storage (keeping config/teamscale.license) =="
rm -rf teamscale-data/repo teamscale-data/storage teamscale-data/logs

echo "== Starting a fresh Teamscale =="
docker compose up -d --wait --wait-timeout 420 teamscale

echo "== Logging in as $ADMIN_USER to obtain a REST access key =="
access_key="$(curl -fsS -X POST "$API/auth/login/access-key" \
  -H 'Content-Type: application/json' \
  --data "{\"username\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PW}\"}")" || {
    echo "ERROR: login as $ADMIN_USER failed. A fresh instance defaults to admin/admin;" >&2
    echo "       override with TEAMSCALE_ADMIN_USER / TEAMSCALE_ADMIN_PASSWORD." >&2
    exit 1
  }

echo "== Importing $BACKUP =="
http_code="$(curl -s -o /tmp/ts-import.out -w '%{http_code}' \
  -u "$ADMIN_USER:$access_key" \
  -F "backup=@${BACKUP}" \
  "$API/backups/import")"
echo "  import -> HTTP $http_code: $(cat /tmp/ts-import.out)"
if [ "$http_code" -ge 400 ]; then
  echo "ERROR: backup import failed (HTTP $http_code): $(cat /tmp/ts-import.out)" >&2
  exit 1
fi

echo "== Waiting for the seeded projects to be restored (up to 10 min) =="
deadline=$((SECONDS + 600))
until curl -fs -u "$ADMIN_USER:$TOKEN" "$API/projects/ids" 2>/dev/null | grep -q '"jabref"'; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "ERROR: seeded projects not restored within 10 min." >&2
    exit 1
  fi
  sleep 3
done
projects="$(curl -fs -u "$ADMIN_USER:$TOKEN" "$API/projects/ids")"
echo "  restored: $projects"

# The backup carries project config + Git connectors but not the analysis
# findings, and the imported projects keep a stale "analyzed" timestamp — so
# Teamscale won't recompute on its own. Trigger re-analysis explicitly; it
# re-fetches the source from GitHub and regenerates the findings.
echo "== Triggering re-analysis of imported projects =="
for project in $(printf '%s' "$projects" | tr -d '[]"' | tr ',' ' '); do
  code="$(curl -s -o /dev/null -w '%{http_code}' -u "$ADMIN_USER:$TOKEN" \
    -X POST "$API/projects/$project/reanalysis")"
  echo "  reanalysis $project -> HTTP $code"
done

echo "== Waiting for findings to be computed (up to ${FINDINGS_TIMEOUT:-1200}s) =="
deadline=$((SECONDS + ${FINDINGS_TIMEOUT:-1200}))
until [ "$(curl -fs -u "$ADMIN_USER:$TOKEN" \
      "$API/projects/${TEAMSCALE_MCP_PROJECT:-jabref}/findings/list/with-count?max=1" 2>/dev/null \
      | sed -n 's/.*"resultSize"[: ]*\([0-9]*\).*/\1/p')" -gt 0 ] 2>/dev/null; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "ERROR: findings not computed within the timeout (is GitHub reachable for analysis?)." >&2
    exit 1
  fi
  sleep 10
done
echo "  findings available for ${TEAMSCALE_MCP_PROJECT:-jabref}."

echo "== (Re)building and starting the MCP server =="
docker compose up -d --build --wait --wait-timeout 180 teamscale-mcp

echo "== Waiting for MCP health =="
until [ "$(curl -fs "$MCP_HEALTH" 2>/dev/null || true)" = "ok" ]; do sleep 1; done
echo "  MCP healthy."

echo "== Running tests =="
( cd app && uv run pytest "$@" )
