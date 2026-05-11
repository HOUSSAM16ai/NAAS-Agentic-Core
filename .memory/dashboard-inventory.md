# Grafana Dashboard Inventory
> Last updated: 2026-05-06 | Branch: `claude/autonomous-runtime-observability-pjzY9` | Folder: `CogniForge`

All dashboards live under `observability/grafana/dashboards/` and are
auto-provisioned by Grafana on container start. Filename prefix controls
the left-nav order. The `00-` dashboard is set as Grafana's default home.

## Dashboards

| File | UID | Role | Refresh | Audience |
|---|---|---|---|---|
| `00-mission-control.json` | `cogniforge-mission-control` | **Default home.** Single-pane view: 6 KPIs + path latency + path donut + terminal-events + HTTP status + live log tail + recent traces. | 5s | Everyone — first stop |
| `10-paths-deep.json` | `cogniforge-paths-deep` | Per-`path_type` deep dive (educational / general_chat / fallback / admin). Variable-driven filtering. | 10s | On-call · debugging a single path |
| `20-langgraph.json` | `cogniforge-langgraph` | LangGraph node runtime: invocations/min, p95 per node, intent distribution, MemorySaver writes, recent traces. | 10s | LLM/graph engineers |
| `30-http-api.json` | `cogniforge-http-api` | FastAPI HTTP surface: req/s, error %, p95, top endpoints, latency heatmap, 5xx-by-endpoint. | 10s | API engineers |
| `40-stack-health.json` | `cogniforge-stack-health` | Stack self-monitoring: `up{}` table, OTel collector receive/refuse/fail, Loki/Tempo ingestion. | 30s | Platform ops |
| `50-microservices-transition.json` | `cogniforge-ms-transition-step2` | Step 2: routing mode (state_graph vs agent), StateGraph metrics, Tavily status, microservices health matrix, fallback chain progress. | 10s | Migration engineers |
| `60-microservices-step3-live.json` | `cogniforge-ms-step3-live` | Step 3: orchestrator-service live activation — health, routing distribution, LangGraph nodes, intent classification, fallback chain, memory/CPU. 20 panels. | 10s | Migration engineers |
| `70-microservices-step4-persistence.json` | `cogniforge-ms-step4-persistence` | Step 4: OUTBOX_RELAY + /metrics — startup_info, relay cycles/rates, StateGraph heatmap, HTTP P50/P95/P99, active connections, scrape health. 24 panels. | 10s | Migration engineers · SRE |
| `80-microservices-step5-user-service.json` | `cogniforge-ms-step5-user-service` | Step 5: user-service live — startup_info, HTTP traffic, auth operations (register/login/verify), DB ops, microservices health matrix. 17 panels. | 10s | Migration engineers · SRE |
| `90-microservices-step6-planning-agent.json` | `cogniforge-ms-step6-planning-agent` | Step 6: planning-agent live — startup_info, HTTP traffic, plan generation (success/fallback), DSPy invocations, DB ops, Docker Compose guide, microservices health matrix. 20 panels. | 10s | Migration engineers · SRE |
| `100-microservices-step7-research-agent.json` | `cogniforge-ms-step7-research-agent` | Step 7: research-agent live — startup_info, Tavily status, HTTP traffic, search rate/duration, Tavily calls/errors, deep research, DB ops, microservices health matrix. 20+ panels. | 10s | Migration engineers · SRE |
| `110-microservices-step8-reasoning-agent.json` | `cogniforge-ms-step8-reasoning-agent` | **Step 8 (current):** reasoning-agent live — startup_info, LLM backend, HTTP traffic, invocations (success/error/fallback), MCTS expansions by depth, LLM calls/errors, fallback responses, microservices health matrix (steps 4-8), Prometheus scrape health. 20+ panels. | 10s | Migration engineers · SRE |

## Drill-down navigation

* Mission Control header has a "All CogniForge Dashboards" link (Grafana
  links → `tags=["cogniforge"]`) that lists every dashboard in the folder.
* `tracesToLogsV2`, `tracesToMetrics`, `derivedFields` are wired in the
  Tempo / Loki datasources. Hovering a span surfaces "View logs" + "View
  metrics" buttons that carry the time range and tags.
* The Mission Control "Recent Traces" panel uses TraceQL `{ name = "ws.chat.turn" }`
  — clicking any row opens the full waterfall in Tempo.

## Adding a new dashboard

1. Author it in Grafana UI (Dashboard → Settings → Save JSON → File).
2. Save the JSON under `observability/grafana/dashboards/` with a numeric
   prefix that respects the order (e.g. `25-something.json`).
3. Make sure `uid` is unique.
4. CI will JSON-parse it on the next PR; bad JSON fails the build.
5. Grafana picks it up within ~15s without restart (provisioning watch).

## Required dashboard hygiene

* **Instrumentation first, visualization second:** Dashboards must never outpace instrumentation.
* **Debugging support:** Every visualization must support debugging and investigation.
* Title MUST be human-readable; emoji prefix is encouraged for the home row.
* Description (panel-level) MUST explain the metric's source AND interpretation.
* `tags` MUST include `cogniforge` so the folder grouping works.
* Time range MUST be reasonable for the dashboard's role (mission-control: 15m,
  drill-downs: 30m–1h).
* No hard-coded org/datasource UIDs other than `prometheus`, `loki`, `tempo`
  (matches `provisioning/datasources/datasources.yml`).
