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
