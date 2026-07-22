# Runbook — Supabase SQL bridge (HTTPS Edge Function)

**Why:** the sandbox / Codespaces firewall blocks raw TCP to Postgres ports
(**5432 / 6543**), so direct DB access (asyncpg/psql) fails from this environment.
A Supabase **Edge Function** (`claude-admin`) executes SQL over **HTTPS :443** and
returns JSON. Use it for **read / diagnosis / manual DDL only** — never for a second
write path (D-006 single-writer stands).

## Tooling (already in the repo — do not reinvent)

`scripts/db_bridge.py` (stdlib-only `urllib`, works with zero third-party deps) is the
canonical client. It reads the endpoint + token **from the environment** — the secret
is never hardcoded and never committed.

| Env var | Meaning |
|---|---|
| `SUPABASE_EDGE_FUNCTION_URL` | public endpoint (`.../functions/v1/claude-admin`) |
| `SUPABASE_EDGE_FUNCTION_KEY` | bearer token — **secret**, lives in git-ignored `.devcontainer/secrets.env` |

## Contract

```
POST  <SUPABASE_EDGE_FUNCTION_URL>
Headers:  Authorization: Bearer <SUPABASE_EDGE_FUNCTION_KEY>
          Content-Type: application/json
Body:     {"sql_query": "SELECT ..."}
```

## Usage

```bash
# 1. Load secrets into the process env (git-ignored — never commit this file)
set -a && . .devcontainer/secrets.env && set +a

# 2. Run SQL
python3 scripts/db_bridge.py --version              # SELECT version();
python3 scripts/db_bridge.py "SELECT 1;"            # inline SQL
echo "SELECT now();" | python3 scripts/db_bridge.py # SQL from stdin
```

Exit codes: `0` = HTTP 2xx · `1` = HTTP/network error · `2` = bad usage / missing token.

## Rules

- **Secrets stay in the environment.** Put the real URL + token in
  `.devcontainer/secrets.env` (git-ignored). Never paste them into code, docs, commits,
  or PR bodies.
- **Read/diagnose/DDL only.** Application writes go through the monolith
  (`customer_messages` / `admin_messages` — D-006). The bridge is not a write path.
- **Cache work (D-180):** the cognitive cache is in-process (per-worker `deque`) and does
  not touch Postgres, so the bridge is only needed to verify *persisted chat rows* during
  a live E2E run — not the cache itself.
