# Deploying the Teamscale MCP sidecar with OAuth (`oauth` mode)

This guide sets up the **standard MCP OAuth flow**: an MCP client (Claude, MCP
Inspector, …) logs in through a browser against a generic OIDC issuer, and the
sidecar forwards the user's **upstream** access-token JWT to Teamscale, which
validates it itself. No credentials are stored by the sidecar and every call runs
as the logged-in Teamscale user.

For the default header-based auth (`X-Teamscale-User`/`X-Teamscale-Token`) see the
main README; that mode needs none of this. This document is only for `oauth` mode.

## How it fits together

```
MCP client ──OAuth 2.1 (browser login)──▶ sidecar (FastMCP OIDCProxy) ──▶ OIDC issuer
     │                                          │  proxies login; stores upstream token;
     │                                          │  issues its OWN reference JWT to the client
     └── Bearer <reference JWT> on /mcp ────────▶│ token swap → validates the UPSTREAM token
                                                 │             (issuer JWKS / issuer / aud)
                                                 ▼
                                     forwards the UPSTREAM JWT as
                                     Authorization: Bearer  ──▶ Teamscale REST API
                                                                (validates signature + username claim)
```

Two facts that drive the whole setup:

1. **The sidecar forwards the *upstream* IdP token, not the token the client sends
   it.** OIDCProxy mints its own reference JWT for the client and keeps the upstream
   token server-side; the sidecar retrieves the upstream token (`get_access_token().token`)
   and forwards *that*. So Teamscale must trust the **IdP's** signing key, not the
   sidecar.
2. **Teamscale validates the forwarded JWT via its "Authentication Proxy / Bearer
   Token" mode** — signature against a configured public key (JWK) plus a *username
   claim* that must match a Teamscale username. OIDC/SAML SSO is **not** this; SSO is
   web-UI login only and does not make the REST API accept bearer tokens.

## Prerequisites

- A generic OIDC issuer that mints **JWT** (not opaque) access tokens (examples below
  use [Authentik](https://goauthentik.io)).
- A Teamscale instance you can administer.
- A reverse proxy (examples use [Caddy](https://caddyserver.com)) and DNS control.
- A container image of this server (see *Build the image*).
- Placeholders used below — substitute your own:
  - `<ISSUER>` — OIDC issuer base URL, e.g. `https://auth.example.com`
  - `<ISSUER_APP>` — the issuer application slug, e.g. `teamscale`
  - `<TEAMSCALE>` — Teamscale base URL, e.g. `https://teamscale.example.com`
  - `<MCP_HOST>` — the sidecar's **own** public host, e.g. `https://teamscale-mcp.example.com`
  - `<SIDECAR_ORIGIN>` — where the container listens on your network, e.g. `10.0.0.5:8082`

> **The sidecar needs its own hostname.** OAuth requires the sidecar to serve several
> paths (`/mcp`, `/.well-known/oauth-protected-resource/*`, `/auth/callback`,
> `/authorize`, `/token`, `/register`, `/health`). Routing only `/mcp` to it — or
> sharing a host with Teamscale — breaks the flow and risks path collisions. Give it a
> dedicated subdomain so **all** paths reach it.

---

## 1. OIDC issuer — create an application + provider

Using Authentik (adapt for other issuers):

**Providers → Create → OAuth2/OpenID Provider:**
- **Client type:** Confidential (the sidecar authenticates with a client secret).
- **Redirect URIs (Strict):** `<MCP_HOST>/auth/callback`
  *(This is the only redirect the issuer needs — the MCP client registers its own
  redirect dynamically with the sidecar, not with the issuer. Strict mode allows
  multiple URIs, one per line, if this provider is shared with e.g. Teamscale UI SSO.)*
- **Signing Key:** a certificate/keypair — its public key (JWKS) is what Teamscale will
  verify against.
- **Subject mode:** **"Based on the User's username"** (recommended — see the claim note
  below).
- Note the **Client ID** and **Client Secret**.

**Applications → Create:** bind it to the provider and set a **slug** (`<ISSUER_APP>`).
The slug fixes your endpoints:
- Discovery: `<ISSUER>/application/o/<ISSUER_APP>/.well-known/openid-configuration`
- JWKS: `<ISSUER>/application/o/<ISSUER_APP>/jwks/`

### Choosing the username claim (important)

Teamscale must read a claim that is (a) present in the **access token** and (b) equal
to a Teamscale username.

- **Recommended: `sub`.** Set the provider **Subject mode = username** so `sub` == the
  username. `sub` is always in every JWT, independent of scopes — the most robust
  choice.
- **Alternative: `preferred_username`.** Works only if it is in the **access token**
  (Authentik includes it when the `profile` scope is granted). Confirm by decoding a
  real token (see *Verify*) — if it is missing, switch to `sub`.

Either way, a Teamscale user whose username equals the claim value must exist (see
step 2).

---

## 2. Teamscale — enable Bearer Token validation

Admin → **Settings → Authentication → the "Bearer Token" section → Add**:

- **Public Key:** paste the single JWK from `<ISSUER>/application/o/<ISSUER_APP>/jwks/`
  (the object inside `"keys": [ … ]` whose `kid` matches your signing cert). If the
  field accepts a **JWKS URL** instead, use the JWKS URL so key rotation is tracked
  automatically. Fetch it with:
  ```bash
  curl -s <ISSUER>/application/o/<ISSUER_APP>/jwks/ | python3 -m json.tool
  ```
- **Claim for username:** `sub` (or `preferred_username` per your choice above).
- **Additional Headers:** leave empty (the token rides in `Authorization`).
- **Save all.**

Ensure a Teamscale user exists whose username matches the claim value, with permission
to view a project. (Tip: if you also configure the **OpenID Connect** SSO connector
with "Automatically create authenticated users", logging into the Teamscale **UI** once
via the issuer auto-provisions that user — but SSO is optional and is *not* what
validates API bearer tokens.)

---

## 3. Build the image

Pushing to the default branch (or a `v*` tag) builds a multi-arch image and pushes it:

- **GitLab CI** (`.gitlab-ci.yml`) → `registry.gitlab.com/cqse/internal/teamscale-mcp`
  (tags: `sha-<short>`, `latest` on default branch, semver on `v*`). This registry is
  **private** — the pulling host must `docker login registry.gitlab.com` with a token
  that has `read_registry`.
- **GitHub Actions** (`.github/workflows/publish.yml`) → `ghcr.io/<owner>/teamscale-mcp`
  (same tag scheme). New ghcr packages are **private** by default — either make the
  package **public** (GitHub → your packages → the package → Package settings → change
  visibility) or `docker login ghcr.io` on the pulling host with a PAT that has
  `read:packages`.

You can also build locally: the repo's `docker-compose.yaml` has `build: .`.

Confirm the pipeline for your commit finished before pulling, or the registry still has
the old image.

---

## 4. Reverse proxy + DNS

### DNS

Add a record for the sidecar's dedicated host `<MCP_HOST>` pointing at your proxy
(e.g. a Cloudflare `CNAME` to your apex/existing host, or an `A` record). Confirm it
resolves from a public resolver:
```bash
dig +short <mcp-host> @1.1.1.1
```
(If your own machine cached an NXDOMAIN from before the record existed, flush it —
macOS: `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`.)

### Caddy

Give the sidecar its own site block so **every** path reaches it:
```caddy
teamscale-mcp.example.com {
    reverse_proxy <SIDECAR_ORIGIN>
}
```
Reload Caddy. (If the host is fronted by Cloudflare in proxied mode, mirror whatever
your existing working host uses; the edge cert covers first-level subdomains.)

---

## 5. Sidecar configuration (`oauth` mode)

All config is environment variables. Required for `oauth` mode:

```bash
TEAMSCALE_AUTH_MODE=oauth
TEAMSCALE_SERVER_URL=<TEAMSCALE>          # may be an internal URL if the sidecar reaches TS directly
# Bootstrap creds — STILL required: startup downloads the OpenAPI spec via HTTP Basic
TEAMSCALE_SPEC_USER=<bootstrap-user>
TEAMSCALE_SPEC_TOKEN=<bootstrap-access-key>
# OAuth:
TEAMSCALE_OIDC_CONFIG_URL=<ISSUER>/application/o/<ISSUER_APP>/.well-known/openid-configuration
TEAMSCALE_OIDC_CLIENT_ID=<client-id>
TEAMSCALE_OIDC_CLIENT_SECRET=<client-secret>
MCP_BASE_URL=<MCP_HOST>                   # the sidecar's public base URL (used for redirect + metadata)
# Optional: TEAMSCALE_OIDC_AUDIENCE (leave unset for bring-up; skips the aud check).
#           MCP_PATH (defaults to /mcp), MCP_PORT (8081), MCP_ALLOWED_HOSTS.
```

Point your deployment's image at the built one, then recreate:
```yaml
  teamscale-mcp:
    image: ghcr.io/<owner>/teamscale-mcp:latest   # or the GitLab registry image
```
```bash
docker compose pull teamscale-mcp && docker compose up -d teamscale-mcp
```

If startup fails (bad OIDC config, spec download unreachable), the container still
answers with a single `startup_error` tool describing the failure (header-gated), and
`/health` reports 503 — check the container logs.

---

## 6. Verify

### Endpoint smoke tests
```bash
curl -s  <MCP_HOST>/health                                            # -> ok
curl -si <MCP_HOST>/mcp -X POST -H 'content-type: application/json' -d '{}' | grep -i www-authenticate
#   -> www-authenticate: Bearer resource_metadata="<MCP_HOST>/.well-known/oauth-protected-resource/mcp"
curl -s  <MCP_HOST>/.well-known/oauth-protected-resource/mcp          # -> JSON with resource + authorization_servers
```
A `WWW-Authenticate: Bearer` header confirms the new image **and** `oauth` mode. (The
metadata path is resource-scoped — note the trailing `/mcp`. The bare
`/.well-known/oauth-protected-resource` returns 404.)

### Full login with MCP Inspector
```bash
npx @modelcontextprotocol/inspector
```
- **Transport:** Streamable HTTP · **URL:** `<MCP_HOST>/mcp` · **Connect**.
- A browser opens to the issuer login. Authenticate as a user that matches a Teamscale
  user.
- On success Inspector lists the Teamscale tools — this proves the token was issued and
  accepted by the sidecar's verifier.
- Run a read tool (e.g. `getProjects`). Returning your projects proves the upstream JWT
  was forwarded and Teamscale authenticated you.

### Decode the token (definitive check)
From Inspector's Authentication panel, copy the access token:
```bash
echo '<ACCESS_TOKEN>' | cut -d. -f2 | base64 -d 2>/dev/null | python3 -m json.tool   # payload: claim == TS username?
echo '<ACCESS_TOKEN>' | cut -d. -f1 | base64 -d 2>/dev/null; echo                    # header: kid == the JWK in Teamscale?
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `curl` returns nothing (empty) | DNS/TLS/connection, not the app (`-s` hid the error) | `curl -v …`; check DNS with `dig … @1.1.1.1`; flush local DNS cache |
| `/mcp` 401 with **no** `WWW-Authenticate` | Running old image, or `TEAMSCALE_AUTH_MODE` ≠ `oauth`, or container not recreated | Pull new image + recreate; confirm the env var |
| Issuer "redirect URI mismatch" | `<MCP_HOST>/auth/callback` not in the provider's redirect URIs (Strict, exact) | Add it exactly (scheme/host, no trailing slash) |
| Inspector connects, tools list, but tool call → Teamscale **401/403** | Username claim missing from the access token, or ≠ a Teamscale user, or wrong JWK/`kid` in Teamscale | Decode the token; switch claim to `sub` + Subject mode = username; verify the pasted JWK's `kid` |
| `access forbidden` pulling the image | Private registry, host not logged in | `docker login` to the registry with a read-scoped token, or make the package public |
| Tools list but every call fails only in production | The upstream token isn't reaching the outgoing call | Confirm `get_access_token()` context propagation; fall back to a middleware that stashes the swapped token into a contextvar |
| Everything 404/route to Teamscale, not the sidecar | Proxy routes only `/mcp` (or shares Teamscale's host) | Give the sidecar its own host; route all paths to it |
