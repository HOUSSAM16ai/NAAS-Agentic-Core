# Observability Stack Topology
> Last updated: 2026-05-06 | Branch: `claude/autonomous-runtime-observability-pjzY9` | Authoritative

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
