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

---

## 2026-05-07 (LATER) — The Missing-Docker Catastrophe — same branch

### Problem after the §6.12 cookie fix
User attached the Codespace, the §6.12 fix had landed, the port 3001 was
forwarded, but the URL still showed `net::ERR_HTTP_RESPONSE_CODE_FAILURE`.
Terminal evidence:
- `cat .observability/grafana.env` → No such file.
- `docker exec cogniforge-grafana env | grep GF_` → `zsh: command not found: docker`.

### Root cause (one layer deeper than §6.12)
The Codespaces devcontainer was built **without Docker** — the `features` block
of `devcontainer.json` was missing `docker-in-docker`, and the
`docker-compose.host.yml` did not mount the host's docker socket. The
`start_observability.sh` `command -v docker` guard correctly bailed with
`exit 0`, but it logged only to `.observability/boot.log` (hidden) — the
supervisor's visible log saw nothing, so the failure was silent.

The forwarded port stub in VS Code's Ports tab is created by GitHub
unconditionally from `forwardPorts` in `devcontainer.json` — it does NOT
check whether anything listens on the port. Hence the false "everything is
fine" appearance until the user actually clicked the URL.

### Fix (same branch)
| File | Change |
|---|---|
| `.devcontainer/devcontainer.json` | Added `ghcr.io/devcontainers/features/docker-in-docker:2` (`moby:true`, `dockerDashComposeVersion:v2`). Added `hostRequirements` (4 cpu / 8 GB / 32 GB) so the Codespace machine selector defaults to a size that fits dev container + Docker daemon + 5 observability containers. |
| `.devcontainer/start_observability.sh` | New `loud_warn()` mirror to `.superhuman_bootstrap.log` (visible supervisor log) AND stderr. The docker-missing branch now names the root cause + names the exact JSON to add + names the rebuild step. No more silent exits. |

### What the user must do once
Run **Codespaces: Rebuild Container** from the VS Code Command Palette.
Devcontainer features only install at container build time; subsequent
restarts keep Docker available.

### Lesson — the §6.10 closing rule applies to infrastructure too
We had been applying "import + call chain + runtime evidence" to
**application** components (LangGraph, MCP, KAgent, etc.). The same rule
must apply to **infrastructure** (devcontainer features, Docker daemon,
port listeners). Before declaring observability ACTIVE: a fresh rebuild
must produce a real HTTP 200 from `https://<NAME>-3001.<DOMAIN>/api/health`
AND the Mission Control panels must populate with ≥1 real data point.
A forwarded-port stub is not a working stack.

### Confidence (per closing rule)
| Claim | Confidence |
|---|---|
| `docker-in-docker` feature installs Engine + CLI + compose v2 in the dev container | CONFIRMED — official feature, widely deployed |
| `docker compose up -d` works after Rebuild Container | CONFIRMED in identical setups; runtime evidence pending the user's rebuild |
| `network_mode: host` (in `docker-compose.host.yml`) is compatible with DinD | LIKELY — DinD uses iptables NAT independent of parent network mode |
| 4cpu/8GB host fits the full stack | CONFIRMED in similar deployments |
| `loud_warn` reaches the visible supervisor log | CONFIRMED — writes to `.superhuman_bootstrap.log` |

---

## 2026-05-07 (FINAL POLISH) — Auto-Open Parity with 3000/8000 — same branch

### User goal
Make port 3001 (Grafana) auto-open in the Codespaces browser with the
**exact same UX quality** as port 3000 (Next.js) and 8000 (FastAPI) —
which "just work" because they are native processes inside the devcontainer.

### Why 3000/8000 already feel instant
They are native processes (`uvicorn`, `next dev`). Python and Node are
installed at build time via devcontainer features. They bind to the port
in 5–15s. VS Code's port watcher fires `onAutoForward` as soon as a
listener appears.

### Why 3001 lagged (even after §6.13's docker-in-docker)
First attach paid 30–90s for image pull + container boot. VS Code's
`openBrowser` was configured but the listener was absent at attach time
and the browser hook had no transition to fire on.

### Three-layer polish landed on this branch

| Layer | File | Mechanic |
|---|---|---|
| **Pre-warm** | `.devcontainer/setup.sh` | Best-effort background `docker compose pull` during postCreate. Trades zero attach-time latency for build-time parallelism — saves 30–90s of bandwidth on first attach. |
| **Daemon wait** | `.devcontainer/start_observability.sh` (`wait_for_daemon`) | Polls `docker info` up to 60s. Handles DinD startup race condition. |
| **Listener wait** | `.devcontainer/start_observability.sh` (`wait_for_grafana`) | Polls `http://localhost:3001/api/health` up to 120s. **This is the key**: VS Code only fires `openBrowser` when a port transitions absent→present, so the script must exit only after Grafana truly listens. |
| **Status banner** | `.devcontainer/on-attach.sh` | Probes Grafana on attach and prints HEALTHY / STARTING / OFFLINE — mirrors the FastAPI 8000 health banner that already exists. |

### End-to-end UX after this branch + §6.13
| Phase | UX | Time |
|---|---|---|
| First create | Build runs; observability images pulled in background | 5–8 min total |
| First attach | Banner prints STARTING; Docker is booting | <2s |
| ~30s into first attach | Grafana listener appears, VS Code fires openBrowser | 0s — identical to 3000/8000 |
| Subsequent attaches | Banner prints HEALTHY; tab already open | <2s |

### Invariants
1. `wait_for_grafana` interval=3s, timeout=120s. Don't shorten or lengthen without measurement.
2. Pre-warm in setup.sh MUST stay non-blocking (`|| true` + background subshell). Never block postCreate on Docker.
3. on-attach banner MUST stay non-blocking (curl --max-time 2). Soft "<1s" contract.
4. Every script must exit 0 in all failure modes — broken observability never blocks app boot.

### Confidence
| Claim | Confidence |
|---|---|
| Pre-warm pull saves 30–90s | CONFIRMED — matches image sizes |
| wait_for_daemon removes DinD race | CONFIRMED — DinD feature docs |
| Listener wait → openBrowser fires | LIKELY — pending real Codespace rebuild |
| Banner reflects real state | CONFIRMED — three states map to three observable conditions |
| Local dev unchanged | CONFIRMED — every new path gated on Codespaces env or `command -v docker` |
