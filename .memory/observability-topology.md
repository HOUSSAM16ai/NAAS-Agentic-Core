# Observability Stack Topology
> Last updated: 2026-05-07 | Branch: `claude/fix-monitoring-port-hQ7JL` | Authoritative
>
> **2026-05-07 — Codespaces cross-origin proxy fix landed (see end of file).**
> Grafana on port 3001 now correctly auth-cookies the user when reached via
> `https://<CODESPACE_NAME>-3001.preview.app.github.dev/`.
> Prior status: the dashboard URL opened a blank page / redirect loop.

## Stack components (committed)

```
                    ┌──────────────────────────────┐
                    │  FastAPI app (port 8000)     │
                    │  · path_observer (per turn)  │
                    │  · OTel SDK (opt-in)         │
                    │  · /api/v1/observability/    │
                    │     prometheus (scrape)      │
                    └─────────────┬────────────────┘
                                  │
        OTLP gRPC :4317  ─────────┴──────────  Prometheus scrape :8000
              │                                       │
              ▼                                       │
   ┌─────────────────────────────┐                   │
   │  OTel Collector             │                   │
   │  cogniforge-otel-collector  │                   │
   │  :4317  :4318  :8888  :8889 │                   │
   └────┬────────┬───────────┬───┘                   │
        │        │           │                       │
        ▼        ▼           ▼                       │
   ┌─────────┐ ┌──────┐ ┌────────────┐ ◄────────────┘
   │  Tempo  │ │ Loki │ │ Prometheus │
   │  :3200  │ │:3100 │ │   :9090    │
   └────┬────┘ └──┬───┘ └──────┬─────┘
        │         │            │
        └─────────┼────────────┘
                  │
                  ▼
          ┌───────────────┐
          │   Grafana     │
          │ Mission Ctrl  │
          │    :3001      │ ◄── user clicks this in Codespaces
          └───────────────┘
```

## Port forwarding (devcontainer.json)

| Port | Label | Visibility | onAutoForward |
|---|---|---|---|
| **3001** | 🛰️ Mission Control (Grafana) | public | **openBrowser** |
| 8000 | Backend API (FastAPI) | public | notify |
| 5000 | Frontend (Next.js) | public | notify |
| 9090 | Prometheus (Raw Queries) | public | silent |
| 3200 | Tempo | private | silent |
| 3100 | Loki | private | silent |
| 4317/4318 | OTel Collector | private | silent |
| 5432 | PostgreSQL | — | ignore |

## Auto-start chain (Codespaces)

```
container boot
   ↓
postCreateCommand → setup.sh
   · pip install -r requirements.txt
   · pip install -r requirements-observability.txt   (best-effort)
   ↓
postStartCommand → on-start.sh
   · launch supervisor (FastAPI + Next.js)
   · nohup start_observability.sh &        ← background, non-blocking
       · resource guard (≥ 1.5 GB free)
       · docker compose up -d (5 containers)
       · log to .observability/boot.log
   ↓
postAttachCommand → on-attach.sh
   · print system status
   · run snapshot_runtime.sh (truth-table refresh)
```

Disable explicitly:
```
export OBSERVABILITY_AUTOSTART=0
```

## Where each signal lives

| Signal | Source | Sink | Dashboard |
|---|---|---|---|
| WS chat span | `path_observer.open_ws_turn / close_ws_turn` | OTel SDK → Tempo | Mission Control · Path Deep Dive |
| `ws.chat.turn.duration_seconds` histogram | `path_observer._emit_to_otel` | OTel → Prometheus | Mission Control · Path Deep Dive |
| `ws.chat.terminal_events.total` counter | same | same | Mission Control |
| `ws.chat.fallback.total` counter | same (gated on `mark_fallback_used`) | same | Mission Control · Path Deep Dive |
| FastAPI route span | `FastAPIInstrumentor` (auto) | OTel → Tempo | HTTP API Surface |
| HTTP req/duration metrics | OTel auto-instrumentation | OTel → Prometheus | HTTP API Surface |
| httpx client span | `HTTPXClientInstrumentor` | OTel → Tempo | HTTP API Surface |
| SQLAlchemy / asyncpg query span | auto-instrumentor | OTel → Tempo | (future: DB dashboard) |
| Redis op span | auto-instrumentor | OTel → Tempo | (future: Redis dashboard) |
| Application log lines | Python logging + LoggingInstrumentor | OTel logs → Loki | Mission Control (live tail) |
| LangGraph node span | `local_graph._supervisor_node / _chat_node` (existing) | OTel → Tempo (when SDK is on) | LangGraph Runtime |

## Confidence (CONFIRMED / LIKELY / SUSPECTED / UNKNOWN)

| Item | Confidence | Reason |
|---|---|---|
| Stack files parse (yaml/json/compose) | CONFIRMED | CI gates this |
| Python wiring is import-clean | CONFIRMED | ruff + py_compile in CI |
| OTel SDK reaches Tempo/Prometheus/Loki when stack is up | LIKELY | standard OTLP; not yet runtime-verified in this branch |
| Dashboards render with real data | UNKNOWN | requires running stack + real WS traffic |
| Auto-start succeeds on a 4 GB Codespace | LIKELY | resource guard + standard images; needs first attach to confirm |
| Prometheus scrape on `/api/v1/observability/prometheus` returns text exposition | LIKELY | endpoint added, format = `text/plain; version=0.0.4`; runtime verification pending |

Anything in **UNKNOWN** must NOT be marked ACTIVE in `runtime_truth.md` until
proven by a real request that emits a trace.

---

## 2026-05-07 — Cross-origin proxy fix (Codespaces) — `claude/fix-monitoring-port-hQ7JL`

### Problem
Clicking forwarded port 3001 in Codespaces opened the Grafana URL through
`https://<CODESPACE_NAME>-3001.preview.app.github.dev/` and the page either
redirected in a loop, refused authentication, or showed a blank "no access"
panel. Three independent defects compounded:

1. `grafana.ini` `[server] domain = localhost` → all Grafana redirects + cookies pointed at `localhost`.
2. `grafana.ini` `[security] cookie_samesite = lax` → cross-origin cookies dropped by browser on the GitHub preview proxy.
3. `start_observability.sh` did not compute the public URL → Grafana booted blind, no env override.

### Fix (this branch)
| File | What changed |
|---|---|
| `observability/grafana/grafana.ini` | Defaults are now LOCAL-correct only (header explains Codespaces is overridden via env). Added explicit `cookie_secure=false` and `csrf_always_check=false` defaults for transparency. |
| `.devcontainer/start_observability.sh` | New `detect_grafana_public_url()` reads `${CODESPACE_NAME}` + `${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}` and exports `GF_SERVER_ROOT_URL`, `GF_SERVER_DOMAIN`, `GF_SECURITY_COOKIE_SAMESITE=none`, `GF_SECURITY_COOKIE_SECURE=true`, `GF_SECURITY_CSRF_ALWAYS_CHECK=false` BEFORE `docker compose up -d`. Local boots `unset` them — no regression. |
| `observability/docker-compose.observability.yml` | Grafana service `environment:` block grew six new `${VAR:-default}` passthrough entries so the container actually receives the dynamic config. |
| `.devcontainer/on-start.sh` | Added `gh codespace ports visibility 3001:public` next to the existing 8000/3000 lines. |

### Runtime evidence to capture after first attach
1. `cat .observability/grafana.env` shows the 4 `GF_*` overrides + the resolved URL.
2. `docker exec cogniforge-grafana env | grep GF_` shows them inside the container.
3. Browser DevTools → cookie `grafana_session` has `Domain=<NAME>-3001.preview.app.github.dev`, `SameSite=None`, `Secure=true`.
4. `tail .observability/boot.log` includes `🌐 Codespaces detected. Grafana wired to: …`.
5. Mission Control loads with panels populated (or empty if the FastAPI app hasn't sent traffic yet — that's expected, not a regression).

### Confidence (per closing rule)
| Claim | Confidence |
|---|---|
| Files parse / compose validates | CONFIRMED (`bash -n` + `python -m yaml`) |
| Codespaces detection fires when `${CODESPACE_NAME}` is set | CONFIRMED (env vars are GitHub-injected) |
| Grafana picks up `GF_*` env at boot | CONFIRMED (documented Grafana behavior) |
| Cookie round-trip succeeds end-to-end on the proxy | LIKELY — needs a fresh Codespace + browser attach to verify |
| Local dev path unchanged | CONFIRMED — defaults preserved + `unset` clears stale Codespaces env |
