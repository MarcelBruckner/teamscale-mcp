# Relationship to the Teamscale Claude Code plugin

Teamscale also ships an official [Claude Code plugin](https://github.com/teamscale/claude-code)
(`teamscale/claude-code`). It's **complementary** to this project, not a competitor —
they solve different halves of the same problem, and the strongest setup uses both.

The plugin is a **per-user Claude Code plugin**: you install it into your own Claude
Code (`/plugin marketplace add teamscale/claude-code` → `/plugin install`). It bundles
two things: a set of **curated skills** — `pr-fix-findings`, `pr-close-test-gaps`,
`fix-findings`, `local-fix-findings`, `local-select-tests`, `check-setup` — and a
**local stdio MCP server** (`bin/teamscale-dev-mcp mcp`, backed by the `ts_agent_helper`
Python package) that those skills call. Standing that MCP backend up is a
per-workstation job: Python 3.9+, the `teamscale-dev` CLI, a `.teamscale.toml` in your
checkout (server URL, `project.id`, folder→path mapping, branch), and credentials in
your environment or `~/.teamscale-dev.args`.

This repo ([`teamscale-mcp`](../../README.md)) is the other shape: **one central HTTP
sidecar**, deployed once next to Teamscale, exposing the **full REST surface
auto-generated from the live OpenAPI spec**, with **per-request credential
pass-through** and reachable by **any MCP client** over a URL.

|                | **teamscale-mcp** (this repo)                                            | **teamscale plugin** (`ts_agent_helper`)                              |
| -------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| Deployed       | once, centrally (by an admin)                                            | per user, per workstation                                             |
| Transport      | HTTP — remote, shared                                                    | local stdio — one process per user                                    |
| Tool surface   | full REST API, generated from the live spec, tracks the instance version | curated, hand-built task workflows                                    |
| Auth           | per-request `X-Teamscale-*` headers; no secret stored server-side        | local env vars / `~/.teamscale-dev.args`                              |
| Setup per user | one URL + two headers                                                    | Python 3.9+, `teamscale-dev` CLI, `.teamscale.toml`, a local checkout |
| Clients        | any MCP client (Claude Code, CI, web, …)                                 | Claude Code                                                           |

## Where teamscale-mcp really fits

The honest positioning is **not** "a drop-in replacement for `ts_agent_helper`."
That swap is narrow, and for the PR skills it is a wash — the agent has to redo the
git/PR orchestration the CLI bundled (see
[The plugin uses three backends, not one](#the-plugin-uses-three-backends-not-one)).
The real value is **reach the per-user plugin structurally cannot offer**: any MCP
client, any identity, and the full REST API — served centrally.

- **Best fit — automation, CI, and non-Claude-Code clients.** It's an HTTP endpoint
  with per-request identity, so a CI job, a shared team assistant, a web client, or a
  cron task can use it — authenticating as a **service / technical account**, not a
  developer's personal login. The plugin is Claude-Code-only and tied to a personal
  local config, so it can't serve this at all. This is the strongest reason to run
  the sidecar.
- **Best fit — ad-hoc analysis beyond the curated skills.** The plugin ships a
  handful of opinionated workflows; the sidecar exposes the *entire* REST surface.
  For exploratory questions no skill encodes (clone-coverage outliers,
  architecture-violation trends, finding diffs across branches), only the sidecar can
  answer.
- **Best fit — org-wide observability.** Every tool call flows through one server, so
  it's the single place to see **which Teamscale operations get used, by whom, and how
  often** — usage metrics and AI-adoption insight from one vantage point. Per-user
  local helpers each see only their own traffic and leave no central trail, so this is
  something the plugin model structurally *cannot* give you. For anyone rolling AI out
  across a team, that visibility is often the deciding factor.
- **Reasonable fit — one central backend for an org.** Deploy once, hand out a URL +
  token, no per-workstation Python; the tools track the live spec, so there is no
  version drift. Pointing the plugin's skills at it drops the per-user MCP backend —
  but sell that as **ops simplification**, accepting that the PR skills become more
  orchestration-heavy.
- **Weakest fit — an individual dev's everyday fix/PR loop.** On a laptop that
  already has the toolchain, the plugin (bundled git/PR orchestration + local skills)
  is smoother. There you'd want *both*: the plugin for workflows, the sidecar as the
  shared REST backend behind them.

## A different audience, not just a different deployment

The two also serve **different people**. The plugin's skills are built for a
**developer working on their code** — fix the findings in this file, close the test
gaps on my PR. They're code-facing and assume you have the checkout in front of you.

teamscale-mcp opens Teamscale to people working **with the data and the configuration
itself**, where there is no code to edit:

- **Consultants** (internal or partner) exploring an instance — pulling metrics,
  comparing projects, spotting hotspots — with no local checkout or per-machine setup,
  and able to act as a service account across customer instances.
- **Managers and other non-developers** who want what they see in a dashboard
  **explained**: "what is this test-gap number, is it bad, and where did it come from?"
  — answered conversationally instead of read off a chart.
- **Newcomers and admins** standing Teamscale up or evolving it: create or extend a
  project, wire up an analysis, adjust an **analysis profile** — configuration work the
  code-fixing skills never touch, but which the full REST surface exposes as tools.

Pair it with the companion
**[teamscale-docs-mcp](https://github.com/MarcelBruckner/teamscale-docs-mcp)** (the
Teamscale documentation served as MCP tools) and the agent can both **explain**
Teamscale (concepts, how-tos) and **act on it** (read data, set up projects and profiles
via REST) in one conversation — a data-and-understanding assistant, where the plugin is a
code-editing one.

## What the central HTTP sidecar adds

Beyond the reach above, running one shared server (rather than a helper per laptop)
brings the operational benefits below.

- **Install once, not once per developer.** The sidecar is stood up a single time by
  whoever runs Teamscale. Onboarding a new user to the MCP tools is then just "here's a
  URL, use your API token" — no per-workstation Python MCP backend to build or run.
  (`teamscale-dev` and `.teamscale.toml` still apply wherever local analysis is used;
  they're not what this replaces.)
- **No per-workstation drift.** Everyone talks to the same server, and its tools are
  generated from the deployed instance's own spec — so the tool surface always matches
  the Teamscale version you're actually running, with nothing to keep in lockstep on
  each machine.
- **Wraps any Teamscale API version — no version mismatch, ever.** Because the tools are
  generated at startup from the *live* OpenAPI spec of the instance it sits next to, the
  server exposes exactly the API that instance actually has — nothing is hand-coded
  against a fixed API version. There's no client library pinned to a Teamscale release to
  fall out of step, so an operation that exists on your instance becomes a tool, and one
  that doesn't simply isn't offered. The same image works unchanged across instances on
  different versions, and it can even **retrofit a very old Teamscale**: point the sidecar
  at it, and you get an MCP surface generated from that instance's own (older) spec, with
  no back-porting or per-version build.
- **No client secret stored server-side.** The sidecar persists no client credential:
  each client presents its own token per request, and Teamscale enforces that client's
  own permissions on the forwarded call (see [Security](../../README.md#security)). A
  user's token still lives in their own client config (`.mcp.json`, Claude's config, or
  an injected header) — much like the plugin's `~/.teamscale-dev.args` — but there's no
  central credential store on the server to breach, and the server only holds its own
  bootstrap account.
- **Central operations.** Trimming the tool surface, TLS termination, host protection,
  and upgrades all happen in one place — as does the org-wide **observability** called
  out above (one server = one place to log, monitor, and measure adoption).

## What the plugin still does better

The plugin isn't just an MCP backend — its real value is the parts this server
deliberately doesn't have:

- **Curated skills.** The `pr-*` / `local-*` commands are opinionated agentic recipes
  (fix findings on a PR, close test gaps, select impacted tests) with the prompting
  built in. This server ships raw tools, not workflows.
- **Local, uncommitted-change analysis.** Pre-commit analysis and mapping local folders
  to project paths operate on your working tree. This sidecar works against server-side
  data; the local dev loop is the plugin's domain.

## Optional: the shared backend for the plugin's skills

This is a *secondary* use, not the reason to adopt the sidecar — reach is (see
[Where teamscale-mcp really fits](#where-teamscale-mcp-really-fits)). But if you're an
org that wants to drop the per-workstation Python backend, you can point the plugin's
skills at the central sidecar instead. Treat it as **ops simplification**, and go in
eyes open: `fix-findings` is a clean win, but the PR skills get busier — the agent
must redo the git/PR resolution the CLI bundled (the "after" diagrams below show the
extra steps).

The target here is narrow: **only `ts_agent_helper`** — the per-user Python MCP backend
that talks to the Teamscale REST API. The `teamscale-dev` CLI and `.teamscale.toml`
stay; they serve a different purpose (local analysis, pre-commit, and mapping the
checkout to a project), which this sidecar doesn't cover.

Concretely — the plugin's `.mcp.json` today launches that backend as a bundled local
server:

```json
{ "mcpServers": { "teamscale": {
  "command": "${CLAUDE_PLUGIN_ROOT}/bin/teamscale-dev-mcp", "args": ["mcp"]
} } }
```

Point it at the central sidecar instead, so the REST-facing tools come from one shared
server rather than a Python backend on every workstation:

```json
{ "mcpServers": { "teamscale": {
  "type": "http", "url": "https://teamscale.example.com/mcp",
  "headers": {
    "X-Teamscale-User": "YOUR_USERNAME",
    "X-Teamscale-Token": "YOUR_API_TOKEN"
  }
} } }
```

The curated skills survive and keep working against the server-provided tools, and
`teamscale-dev` + `.teamscale.toml` remain in place for the local dev loop. In short:
use the plugin for its **workflows** and `teamscale-dev` for **local analysis**, and let
this sidecar be the shared **REST MCP backend** in place of `ts_agent_helper` (for those
workflows and every other MCP client).

## The plugin uses three backends, not one

Only three skills route through `ts_agent_helper`. Knowing which is which is the
whole point of the "after" story:

| Skill                | Today's backend                                                       | Replaceable by the sidecar?                                       |
| -------------------- | --------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `fix-findings`       | `ts-agent-helper` CLI                                                 | ✅ pure REST                                                       |
| `pr-fix-findings`    | `ts-agent-helper` CLI                                                 | ✅ but the agent must do the git/PR resolution the CLI bundled     |
| `pr-close-test-gaps` | `ts-agent-helper` CLI                                                 | ✅ same git/PR caveat                                              |
| `local-fix-findings` | `teamscale-dev` **local MCP** (`pre-commit`)                          | ❌ uploads the local working tree — a remote sidecar can't read it |
| `local-select-tests` | `teamscale-dev` **local MCP** (`pre-commit` + `fetch-impacted-tests`) | ❌ same local-file limitation                                      |
| `check-setup`        | `teamscale-dev` CLI                                                   | ➖ shifts to verifying the MCP endpoint + identity                 |

`ts_agent_helper` also bundles orchestration the sidecar doesn't: for the PR
skills it runs `git branch --show-current`, resolves the open merge request
(re-filtering locally for the exact branch), and falls back to a base-branch
compare. The sidecar exposes only the raw REST tools, so the **agent** performs
that resolution itself in the "after" diagrams — more steps, and it needs the
git-facing tags (`Merge Requests`, …) enabled in the tool surface.

### Command → REST → tool mapping (the replaceable skills)

| `ts_agent_helper` call      | Teamscale REST endpoint                        | `teamscale-mcp` tool¹                  |
| --------------------------- | ---------------------------------------------- | -------------------------------------- |
| `findings list`             | `GET .../findings/list`                        | `getFindings`                          |
| `findings type-descriptors` | `POST .../finding-type-descriptors`            | `getFindingTypeDescriptions`           |
| `findings flag`             | `PUT .../findings/flagged`                     | `flagFindings`                         |
| `findings for-pr`           | `GET .../merge-requests` + `.../finding-churn` | `getMergeRequests` + `getFindingChurn` |
| `test-gaps for-pr`          | `GET .../merge-requests` + `.../test-gaps.csv` | `getMergeRequests` + `getTestGaps`     |

¹ Tool names are illustrative — the actual names track each instance's OpenAPI
`operationId`s.

## Diagrams

These diagrams cover the *secondary* "point the skills at the sidecar" use above, not
the primary reach story. Each skill has a **before** (how it works today) and an
**after** (with the central sidecar as the REST backend) sequence diagram.

Each merged image shows **today (`ts_agent_helper`)** on the left and **with
`teamscale-mcp`** on the right.

### `check-setup` — shifts to verifying the endpoint

![](check-setup.png)

### `local-fix-findings` — stays local

Not `ts_agent_helper`; uploads the working tree, so it stays on `teamscale-dev`.

![](local-fix-findings.png)

### `local-select-tests` — stays local

![](local-select-tests.png)

### `fix-findings` — replaceable

![](fix-findings.png)

### `pr-fix-findings` — replaceable (agent takes over PR resolution)

![](pr-fix-findings.png)

### `pr-close-test-gaps` — replaceable (agent takes over PR resolution)

![](pr-close-test-gaps.png)

## Rendering

The `.puml` sources and their per-side renders (`<skill>-before.png`,
`<skill>-after.png`) both live in [`diagrams/`](diagrams/) and use the shared PlantUML
theme in [`../../theme.iuml`](../../theme.iuml). Each pair is
merged into one side-by-side `<skill>.png` one level up, next to this README — the
merged composites are the only PNGs here, and the images this README embeds.

Use the [`diagrams/regenerate.sh`](diagrams/regenerate.sh) script to rebuild
everything (render all diagrams **and** produce the merged side-by-side images);
it needs `plantuml` and ImageMagick (`magick`):

```bash
docs/comparison-to-teamscale-claude-code/diagrams/regenerate.sh
```

The repo `pre-commit` hook does the same automatically for out-of-date diagrams:
it renders each `.puml` in place and re-merges any before/after pair whose composite
is stale, staging both.
