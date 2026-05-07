# CogniForge — Replit Environment

## Overview

CogniForge is an AI-powered enterprise platform featuring a hybrid monolith/microservices architecture. It is built on FastAPI (Python 3.12) for the backend and Next.js 16 (React 18) for the frontend.

## Architecture

- **Backend** — FastAPI app at `app/` served via uvicorn on port 8000
- **Frontend** — Next.js app at `frontend/` served on port 5000 (visible in preview pane)
- **Database** — PostgreSQL (Replit-managed, connected via `DATABASE_URL` secret)
- **Authentication** — Custom JWT-based auth (no external auth provider)

## Workflows

- **Project** — runs both Frontend and Backend in parallel
- **Frontend** — `cd frontend && npm run dev` → port 5000 (webview)
- **Backend** — `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` → port 8000 (console)

## Key Files

- `app/main.py` — FastAPI entry point
- `app/kernel.py` — RealityKernel bootstrapper (middleware, routers, lifespan)
- `app/core/settings/base.py` — Pydantic settings (AppSettings)
- `app/core/database.py` — Async SQLAlchemy engine factory
- `app/core/db_schema.py` — Schema validation and auto-fix on startup
- `app/core/db_schema_config.py` — All 18 table definitions and indexes
- `frontend/app/` — Next.js app directory (pages, components, hooks)
- `frontend/next.config.js` — Rewrites `/api/*` and `/health` to backend at port 8000

## Environment Variables (set via Replit Secrets)

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes (auto-set by Replit) | PostgreSQL connection string |
| `BACKEND_CORS_ORIGINS` | Yes | JSON array of allowed CORS origins |
| `ALLOWED_HOSTS` | Yes | JSON array of trusted hosts |
| `FRONTEND_URL` | Yes | Frontend base URL |
| `ENVIRONMENT` | Yes | `development` / `production` |
| `OPENAI_API_KEY` | Optional | Enables AI features (LLM calls) |
| `OPENROUTER_API_KEY` | Optional | Alternative LLM provider |

## Database Setup

All 18 tables are auto-created/validated by `app/core/db_schema.py` on startup. The following tables exist:
`users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `refresh_tokens`, `audit_log`, `customer_conversations`, `customer_messages`, `missions`, `mission_plans`, `tasks`, `mission_events`, `admin_conversations`, `prompt_templates`, `generated_prompts`, `knowledge_nodes`, `knowledge_edges`

## Notes

- The `hnsw` vector index on `knowledge_nodes.embedding` requires the `pgvector` PostgreSQL extension. This index is skipped on startup but the rest of the schema is fully operational.
- The app uses pydantic-settings so list env vars (like `BACKEND_CORS_ORIGINS`) must be set as JSON arrays: `["value1","value2"]`
- Microservices in `microservices/` are not started by default — the monolith at `app/` handles all primary functionality.

## Observability (Mission Control / Grafana)

The full observability stack (Grafana on port 3001, Prometheus 9090, Loki 3100, Tempo 3200, OTel collector 4317/4318) is committed under `observability/` and is wired to autostart in **GitHub Codespaces** via `.devcontainer/start_observability.sh`. **It does NOT autostart on Replit** — Replit's container model doesn't expose a Docker daemon, so docker-compose is not available.

To experiment with the stack on Replit:
- Either run a local Docker host externally and point `OTEL_EXPORTER_OTLP_ENDPOINT` to it, or
- Skip the full stack and rely on the FastAPI app's in-process telemetry: `/api/v1/observability/metrics`, `/api/v1/observability/prometheus` (text/plain Prometheus exposition).

### Codespaces-only fixes landed 2026-05-07 (branch `claude/fix-monitoring-port-hQ7JL`)
Two stacked failures, fixed in one branch:

**§6.12 — cross-origin proxy auth.** Clicking forwarded port 3001 hit a redirect loop because Grafana's defaults (`domain=localhost`, `cookie_samesite=lax`, `cookie_secure=false`) collided with the cross-origin `https://<NAME>-3001.<DOMAIN>/` proxy. Fix: `start_observability.sh` detects `${CODESPACE_NAME}` + `${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}` and exports `GF_SERVER_ROOT_URL`, `GF_SECURITY_COOKIE_SAMESITE=none`, `GF_SECURITY_COOKIE_SECURE=true`, `GF_SECURITY_CSRF_ALWAYS_CHECK=false` before `docker compose up -d`. Local boots `unset` those — no regression.

**§6.13 — the missing-Docker catastrophe (deeper root cause).** Even after §6.12, the URL still returned `ERR_HTTP_RESPONSE_CODE_FAILURE`. Diagnosis: the devcontainer had **no Docker access at all** — `features` was missing `docker-in-docker`, and `docker-compose.host.yml` did not mount the host's docker socket. `start_observability.sh` was bailing silently on `command -v docker`. Fix: added `ghcr.io/devcontainers/features/docker-in-docker:2` to `devcontainer.json`, added `hostRequirements: 4cpu/8GB/32GB`, and added a `loud_warn()` helper that mirrors silent failures to the visible supervisor log. **Codespaces users must run "Codespaces: Rebuild Container" once after pulling this branch.**

**Replit users**: neither fix affects Replit (no Docker, no Codespaces env vars). Replit boots the FastAPI app and Next.js as usual; observability falls back to the in-process endpoints listed above.

See `CLAUDE.md` §6.12 + §6.13 and `.memory/observability-topology.md` for the full forensic trail.
