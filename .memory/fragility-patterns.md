# Architectural Fragility Patterns — Institutional Memory
> Created: 2026-05-09 | Authority: this file documents discovered systemic failures and their root causes.
> These are NOT bug reports. They are architectural lessons encoded as permanent institutional memory.
> Each pattern describes WHY the failure emerged, WHAT assumptions failed, and WHAT future agents must never repeat.

---

## Pattern 1 — Intent Routing Semantic Hijacking

### What was discovered
`app/services/chat/local_graph.py:_classify_intent()` uses pure lexical regex matching against a fixed keyword list. The function is the **sole live intent classifier** for every WS chat turn in default Codespaces. It produces three outputs: `"educational"`, `"general"`, or `"chat"`.

### The failure modes (verified by runtime test)

**Keyword dictatorship — false educational classification:**
Every one of these questions is classified `educational` by the live classifier:
- `"ما هو تمرين اليوغا المناسب للمبتدئين؟"` — تمرين = yoga exercise, not BAC math
- `"أريد تمرين رياضي"` — physical exercise, not school subject
- `"شرح لي كيف تعمل الشبكات الاجتماعية"` — شرح = explain, but about social networks
- `"حل مشكلة الإنترنت عندي"` — حل = solve, but about internet connectivity
- `"درس الموسيقى ممتع"` — درس = lesson, but music appreciation
- `"مادة البلاستيك"` — مادة = material (plastic), not school subject
- `"كيفية حل النزاعات"` — كيفية حل = how to solve, but conflict resolution
- `"ما هو الحل السياسي للأزمة؟"` — ما هو الحل = what is the solution, political
- `"solve my relationship problems"` — solve = educational trigger
- `"history of the internet"` — history = educational trigger

**Root cause:** The patterns match Arabic/English words in isolation without semantic context. The word `تمرين` (exercise) appears in both "math exercise" and "yoga exercise". The word `حل` (solution/solve) appears in both "solve the equation" and "solve the conflict". The regex has no understanding of the surrounding semantic field.

**Regex greediness — the `تمرين` collapse:**
The pattern `r"(تمرين|مسألة|شرح|درس|مادة|كيفية حل|باكالوريا|بكالوريا|bac)"` matches `تمرين` anywhere in the string. A student asking about yoga, physical fitness, or any non-academic "exercise" is routed to the educational prompt — which then gives them a structured BAC-style academic response to a casual question.

**Context amnesia:**
`_classify_intent(question: str)` receives only the current question string. It has no access to:
- Conversation history (what was said before)
- User profile (student level, subject preferences)
- Session context (are we mid-exercise or starting fresh?)
- Semantic field of the conversation

A student who has been discussing yoga for 5 turns and asks "أعطني تمرين آخر" (give me another exercise) will be routed to the educational path because `تمرين` appears in the string.

**Greeting anchor brittleness:**
Greeting patterns use `^...$` anchors: `r"^(السلام|مرحبا|أهلا|هلا|hello|hi\b|hey|salam|بونجور)[\s\W]*$"`. This means:
- `"شكرا"` → classified `chat` ✓
- `"شكرا جزيلا على المساعدة"` → classified `educational` ✗ (falls through to educational patterns)
- `"السلام عليكم"` → classified `educational` ✗ (anchor fails because of عليكم)
- `"hello how are you"` → classified `general` ✗ (not caught by either pattern)

**Intent priority inversion:**
The classifier checks greetings first, then educational, then defaults to general. This means educational keywords always win over general context. A student asking a general knowledge question that happens to contain a subject name (`"ما هي أهمية الفيزياء في الحياة اليومية؟"` — what is the importance of physics in daily life?) gets the structured educational prompt instead of a conversational answer.

### The hidden taxonomy split-brain

There are **two incompatible intent systems** in the codebase:

| System | File | Status | Taxonomy |
|---|---|---|---|
| Live classifier | `app/services/chat/local_graph.py:_classify_intent` | **PARTIAL (active)** | `educational`, `general`, `chat` |
| Zombie classifier | `app/services/chat/intent_detector.py:IntentDetector` | **PARTIAL (loaded-not-invoked)** | `FILE_READ`, `FILE_WRITE`, `CODE_SEARCH`, `PROJECT_INDEX`, `DEEP_ANALYSIS`, `MISSION_COMPLEX`, `ANALYTICS_REPORT`, `LEARNING_SUMMARY`, `CURRICULUM_PLAN`, `CONTENT_RETRIEVAL`, `ADMIN_QUERY`, `HELP`, `DEFAULT` |
| Path observer | `app/telemetry/path_observer.py:classify_path` | **ACTIVE** | `educational`, `general_chat`, `fallback`, `admin`, `unknown` |

The zombie `IntentDetector` has a 13-intent taxonomy designed for tool-routing (file operations, code search, admin queries). It is instantiated by `CustomerChatBoundaryService.__init__` on the live path but its `detect()` method is never called from a real WS turn. If it were ever wired in, its `CONTENT_RETRIEVAL` pattern also matches `تمرين` — creating a third classification for the same word.

The path observer's `classify_path()` duplicates the live classifier's patterns verbatim (comment: "Duplicated intentionally so the router can classify before the graph runs"). This is a deliberate duplication, but it means any fix to the live classifier must be applied in two places.

### Architectural lesson

**Lexical routing is a local optimum that becomes a global failure at scale.** It works for a narrow vocabulary (pure BAC keywords) but collapses when the user population uses the same words in different semantic contexts. The failure is invisible in testing because test cases are written by people who know the intended vocabulary.

**The correct architecture:** Intent classification should be a semantic operation, not a lexical one. Options in order of increasing capability:
1. **Contextual keyword scoring** — weight keywords by surrounding context (subject names near `تمرين` → educational; body parts near `تمرين` → general)
2. **Embedding-based classification** — embed the question and compare to intent centroids
3. **LLM-based classification** — use a fast/cheap LLM call to classify intent before routing (adds latency but eliminates false positives)
4. **History-aware classification** — pass the last N turns to the classifier

**What must never be done:**
- Do not add more keywords to `_EDUCATIONAL_PATTERNS` to fix false negatives — this makes false positives worse
- Do not add more patterns to `_GREETING_PATTERNS` — the anchor brittleness is structural
- Do not wire the zombie `IntentDetector` into the live path without resolving the taxonomy incompatibility first
- Do not create a third intent taxonomy without retiring one of the existing two

**Files that must be updated together** if the classifier changes:
1. `app/services/chat/local_graph.py:_classify_intent` + `_EDUCATIONAL_PATTERNS` + `_GREETING_PATTERNS`
2. `app/telemetry/path_observer.py:classify_path` + `_EDUCATIONAL_PATTERNS` + `_GREETING_PATTERNS` (intentional duplicate — comment explains why)

---

## Pattern 2 — Hidden DOM Leakage

### What was discovered
Both sidebars in `frontend/app/components/CogniForgeApp.jsx` use CSS `transform: translateX(±100%)` to "hide" when closed. This is a **visual hiding strategy**, not a **DOM exclusion strategy**. The elements remain fully present in the DOM at all times.

### The rendering strategy

```css
/* Conversations sidebar — closed state */
.sidebar {
    transform: translateX(100%);   /* pushed off-screen RIGHT */
    position: absolute;
    z-index: 50;
}
.sidebar.open { transform: translateX(0); }

/* Agent sidebar — closed state */
.agent-sidebar {
    transform: translateX(-100%);  /* pushed off-screen LEFT */
    position: absolute;
    z-index: 50;
}
.agent-sidebar.open { transform: translateX(0); }
```

### Leakage surfaces

**1. Screen reader leakage**
Neither sidebar sets `aria-hidden="true"` when closed. Screen readers (NVDA, VoiceOver, JAWS) will announce the sidebar content to visually impaired users even when the sidebar is visually off-screen. A student using a screen reader hears the full conversation list and agent timeline status on every page load, regardless of whether they opened the sidebar.

**2. Keyboard focus leakage**
No `tabindex="-1"` or `inert` attribute is applied to closed sidebars. A keyboard-only user pressing Tab will cycle through all interactive elements in the sidebar (conversation items, close button) even when the sidebar is visually hidden. This creates a confusing UX where focus disappears off-screen.

**3. Browser find-in-page leakage**
`Ctrl+F` / `Cmd+F` searches the entire DOM including off-screen elements. A student searching for a conversation title will find matches in the sidebar even when it is closed, with no visual indication of where the match is.

**4. AgentTimeline data exposure**
The `agent-sidebar` contains `<AgentTimeline />` which renders agent phase status (`فهم السؤال`, `وضع الخطة`, `تصميم الحل`, etc.). This data is always in the DOM. The `useAgentTimeline` hook subscribes to `window.addEventListener("agent:event", ...)` — meaning agent state events are processed and rendered into the DOM even when the sidebar is closed. The rendered phase labels are accessible to screen readers at all times.

**5. Clipboard contamination risk**
`ChatInterface.jsx` renders copy buttons for every assistant message. The copy button calls `navigator.clipboard.writeText(msg.content)`. These buttons are always in the DOM. If a user accidentally triggers a copy action (keyboard shortcut, accessibility tool) while the sidebar is open, the clipboard receives the full raw `msg.content` string — including any markdown, LaTeX, or structured data that the `<Markdown>` component would normally render safely.

**6. Text selection in off-screen elements**
CSS `transform` does not prevent text selection. A user can programmatically select text in off-screen sidebar elements via JavaScript (`window.getSelection()`, `document.execCommand('copy')`). This is a minor surface but relevant for browser extensions.

### Root cause analysis

The `transform: translateX` pattern is chosen for its animation quality — it produces smooth slide-in/slide-out transitions. The alternative (`display: none` / `visibility: hidden`) would eliminate the leakage surfaces but also eliminate the CSS transition animation, since elements with `display: none` cannot be transitioned.

This is a classic **performance vs. correctness trade-off** that was resolved in favor of visual quality without documenting the accessibility and security implications.

### Architectural lesson

**Visual hiding ≠ DOM exclusion.** Any time a UI element is "hidden" via CSS transform, opacity, or visibility (but not `display: none`), it remains a live DOM citizen with all associated capabilities: focus, selection, screen reader access, find-in-page, event listeners.

**The correct pattern for animated sidebars:**
```jsx
// Option A: inert attribute (modern browsers, HTML spec)
<div className={`sidebar ${isOpen ? 'open' : ''}`} inert={!isOpen || undefined}>

// Option B: aria-hidden + tabindex management
<div
  className={`sidebar ${isOpen ? 'open' : ''}`}
  aria-hidden={!isOpen}
  // Also set tabindex="-1" on all interactive children when closed
>

// Option C: conditional rendering with animation via CSS class
// Render null when closed, add class on mount for enter animation
```

**What must never be done:**
- Do not assume `transform: translateX(100%)` hides content from screen readers
- Do not assume off-screen elements are inaccessible to keyboard navigation
- Do not add sensitive data to sidebar components without considering that the data is always in the DOM

**The `AgentTimeline` specific risk:**
`AgentTimeline` renders agent operational state (which phases are running/completed). If the agent stack were ever fully wired (DORMANT → ACTIVE), this component would expose real-time agent execution state to screen readers regardless of sidebar visibility. This is an information leakage surface that grows in severity as the agent stack becomes more capable.

---

## Pattern 3 — Runtime Truth Governance Gaps

### What was discovered
The runtime truth governance system (`scripts/runtime_truth.py` + `.runtime/truth_table.lock.json` + `.github/workflows/runtime_truth.yml`) enforces **static** architectural truth — import presence and call chain reachability. It does not and cannot enforce **runtime** truth — whether code actually executes and produces observable effects.

### The three-leg proof and its CI gap

The doctrine requires three legs for ACTIVE status:
1. **Import** — the module is imported by code reachable from `app/main.py`
2. **Call chain** — there is a live caller flowing from a router/middleware/startup hook
3. **Runtime evidence** — the code actually executes on the production path

CI enforces legs 1 and 2 via static analysis. **Leg 3 is never verified in CI.** This creates a structural gap: a component can be classified ACTIVE in the truth table while producing zero observable runtime effects.

### Concrete governance gaps identified

**Gap 1 — Zombie metrics undetected by static analysis**
`app/services/chat/local_graph.py` is correctly classified PARTIAL. But the LangGraph Grafana dashboard (`observability/grafana/dashboards/20-langgraph.json`) queries four metrics that are never emitted:
- `cogniforge_langgraph_node_count_total` — not emitted anywhere
- `cogniforge_langgraph_node_duration_seconds` — not emitted anywhere
- `cogniforge_langgraph_intent_total` — not emitted anywhere
- `cogniforge_langgraph_checkpointer_writes_total` — not emitted anywhere

`local_graph.py` uses `UnifiedObservabilityService.start_trace()` / `end_span()` — which writes to an in-process span store, not to Prometheus. The dashboard panels will always be empty. The static truth table cannot detect this because it only checks import reachability, not metric emission.

**Gap 2 — Dashboard-metric contract has no CI enforcement**
No CI step verifies that metric names referenced in Grafana dashboard JSON files (`observability/grafana/dashboards/*.json`) are actually emitted by the application code. A dashboard can reference any metric name and CI will pass. The only way to discover the mismatch is to run the full observability stack and observe empty panels.

**Gap 3 — Metric namespace drift across three systems**
Three metric emission systems coexist with different naming conventions:
- `UnifiedObservabilityService` — uses dot notation: `ws.chat.turn.duration_seconds`, `langgraph.supervisor`, `langgraph.chat_node`
- OTel SDK (`otel_setup.py`) — uses underscore notation with `cogniforge_` prefix: `cogniforge_ws_chat_turn_duration_seconds`
- Prometheus export (`metrics.py:export_prometheus_metrics`) — translates dot→underscore and adds `cogniforge_` prefix

The translation is: `ws.chat.turn.duration_seconds` → `cogniforge_ws_chat_turn_duration_seconds`. This works for the WS metrics. But `langgraph.supervisor` (a span name, not a metric) has no corresponding Prometheus metric — the dashboard query `cogniforge_langgraph_node_count_total` has no emitter.

**Gap 4 — PARTIAL (loaded-not-invoked) is invisible to the lock file**
The truth table correctly classifies `CustomerChatBoundaryService` as PARTIAL (split) — persistence methods ACTIVE, streaming methods never invoked. But the lock file stores only `expected_status: "PARTIAL"` without distinguishing which methods are active. A future agent reading the lock file cannot determine which half of the boundary service is live without reading the full `.memory/runtime_truth.md` prose.

**Gap 5 — The lock file branch is stale**
`.runtime/truth_table.lock.json` records `"branch": "jules-5513332666705839536-7e7df21b"` — a Jules AI agent branch, not a human-authored branch. The lock file was last regenerated on `2026-05-08T09:54:43.624200+00:00`. Any architectural changes since then that affect import topology will cause CI drift without a corresponding lock update.

### Architectural lesson

**Static analysis is necessary but not sufficient for runtime truth governance.** The import + call chain check prevents the worst failures (a ZOMBIE acquiring a live importer silently). But it cannot detect:
- Metric emission gaps (code runs but emits nothing useful)
- Dashboard-metric contract violations (dashboard queries non-existent metrics)
- Behavioral dead code (code runs but its output is discarded)
- Configuration-gated dormancy (code runs but is a no-op without env vars)

**The missing governance layer:** A metric contract test that:
1. Parses all `*.json` dashboard files and extracts Prometheus query expressions
2. Extracts all metric names from those expressions
3. Greps the application source for those metric names in emit calls
4. Fails CI if a dashboard references a metric with no emitter

This is a static check (no runtime required) and would catch the LangGraph dashboard gap immediately.

**What must never be done:**
- Do not add a Grafana dashboard panel without first verifying the metric is emitted
- Do not classify a component ACTIVE in the truth table based only on import + call chain — document what runtime evidence would look like
- Do not assume the lock file is current — check its `generated_at_utc` before trusting it
- Do not use span names as metric names — they are different namespaces

---

## Pattern 4 — Observability Integrity Failures

### What was discovered
The observability stack has a structural split between what is instrumented, what is exported, and what is visualized. These three layers are not contractually bound to each other, creating conditions where dashboards appear healthy while the underlying system is producing no signal.

### The instrumentation-export-visualization gap

```
local_graph.py
  └── obs.start_trace("langgraph.supervisor", ...)   ← UnifiedObs span (in-process)
  └── obs.end_span(...)                               ← stored in completed_traces deque
                                                       NOT exported to Prometheus
                                                       NOT exported to OTel/Tempo
                                                       (unless OTEL_EXPORTER_OTLP_ENDPOINT set)

path_observer.py
  └── _emit_to_otel(handle)                           ← OTel SDK histogram/counter
  └── obs.record_metric("ws.chat.turn.duration_seconds", ...)  ← UnifiedObs metric
                                                       BOTH paths active
                                                       OTel → Prometheus (when stack up)
                                                       UnifiedObs → /api/v1/observability/prometheus

Dashboard 20-langgraph.json
  └── cogniforge_langgraph_node_count_total           ← ZOMBIE METRIC (no emitter)
  └── cogniforge_langgraph_intent_total               ← ZOMBIE METRIC (no emitter)
  └── cogniforge_langgraph_node_duration_seconds      ← ZOMBIE METRIC (no emitter)
  └── cogniforge_langgraph_checkpointer_writes_total  ← ZOMBIE METRIC (no emitter)
```

### The fake telemetry risk

A dashboard with empty panels is not neutral — it is actively misleading. An operator looking at the LangGraph dashboard during an incident sees:
- "Invocations/min" panel: empty (no data)
- "p95 node latency" panel: empty (no data)
- "Intent distribution" panel: empty (no data)

The operator cannot distinguish between "LangGraph is not running" and "LangGraph is running but metrics are not emitted". Both states produce identical empty panels. This is **fake certainty through absence** — the dashboard implies it would show data if there were data, but there is no data because the metrics don't exist.

### The dual-path metric emission problem

For WS chat turns, metrics are emitted through two paths simultaneously:
1. `path_observer._emit_to_otel()` → OTel SDK → Prometheus (when stack up)
2. `obs.record_metric("ws.chat.turn.duration_seconds", ...)` → UnifiedObs → `/api/v1/observability/prometheus`

Both paths emit `ws.chat.turn.duration_seconds`. When the OTel stack is up, Prometheus scrapes both the OTel collector endpoint and the FastAPI `/api/v1/observability/prometheus` endpoint. This creates **double-counting** of WS turn metrics in Prometheus. The Mission Control dashboard's "Turns/min" panel would show 2x the actual turn rate.

This is a **dual-write anti-pattern at the metrics layer** — analogous to the dual-write persistence bug (ISS-014) but for telemetry.

### The OTel dormancy masquerade

`app/telemetry/otel_setup.py` is classified ACTIVE in the truth table because it is imported by `app/kernel.py` at boot. But when `OTEL_EXPORTER_OTLP_ENDPOINT` is not set (default Codespaces), `setup_otel()` returns early after creating a no-op meter. The instruments (`_OTEL_HISTOGRAM_TURN`, `_OTEL_COUNTER_TERMINAL`, `_OTEL_COUNTER_FALLBACK`) are created but emit to a no-op exporter — they produce no signal.

The truth table note says: "Hard no-op when OTEL_EXPORTER_OTLP_ENDPOINT is unset". This is accurate but the ACTIVE classification is misleading — the component is imported and called, but produces zero observable output in the default environment. This is a fourth status tier that doesn't exist in the current taxonomy: **ACTIVE (no-op)**.

### The trace split-brain

Two tracing systems coexist:
- `UnifiedObservabilityService` — in-process span store, exposed via `/api/v1/observability/traces`
- OTel SDK → Tempo — distributed traces, exposed via Grafana/Tempo

These are not connected. A span created by `obs.start_trace("langgraph.supervisor")` appears in `/api/v1/observability/traces` but NOT in Tempo. A span created by OTel auto-instrumentation (FastAPI routes) appears in Tempo but NOT in `/api/v1/observability/traces`. An operator debugging a slow request must check two separate systems and manually correlate.

The W3C `traceparent` header is propagated by `ObservabilityMiddleware` and read by `TraceContext.from_headers()` — but this context is stored in `UnifiedObservabilityService`, not forwarded to the OTel SDK. The OTel SDK creates its own trace context independently. The two systems share no trace IDs.

### Architectural lesson

**Instrumentation, export, and visualization are three separate contracts. Each must be explicitly verified.**

The observability doctrine ("instrumentation before visualization") is correct but incomplete. It should be: **instrumentation → export contract → visualization**. A metric that is instrumented but not exported is as useless as a metric that is not instrumented. A dashboard that visualizes a metric with no emitter is worse than no dashboard — it creates false confidence.

**The zombie metric anti-pattern:**
A zombie metric is a Prometheus query in a dashboard that has no corresponding emitter in the application code. It is the observability equivalent of a ZOMBIE component — it exists in the visualization layer but has no live call chain in the instrumentation layer. Zombie metrics are dangerous because they make dashboards appear to be monitoring something they are not.

**The dual-write metrics anti-pattern:**
Emitting the same logical metric through two different paths (UnifiedObs + OTel) creates double-counting when both paths are active. The correct pattern is a single emission path with a clear owner. For WS turn metrics: either UnifiedObs owns them (and OTel reads from UnifiedObs) or OTel owns them (and UnifiedObs reads from OTel). Not both independently.

**What must never be done:**
- Do not add a Grafana panel without first confirming the metric name exists in an emitter
- Do not classify `otel_setup.py` as ACTIVE without noting it is a no-op in default Codespaces
- Do not assume UnifiedObs spans appear in Tempo — they are separate systems
- Do not emit the same metric through both UnifiedObs and OTel without a deduplication strategy
- Do not present empty dashboard panels as "no data yet" — document whether the metric has an emitter

---

## Pattern 5 — Retrieval Context Blindness (ISS-038, RESOLVED 2026-05-10)

**What happened:** `detect_exercise_retrieval()` used a flat keyword list. Any question containing `"تمرين"`, `"احتمالات"`, `"درس"`, or `"بكالوريا"` triggered `_build_local_retrieval_response()`. Since `knowledge_base/` contained exactly one file (the probability BAC exercise), every triggered retrieval returned that file — regardless of what the student actually asked. A student asking "اشرح الجزء أ من هذا التمرين" received a probability exercise instead of an explanation.

**Root cause:** Keyword presence was treated as intent. The system had no model of *why* the user mentioned the keyword — explanation context, conceptual question, and explicit retrieval request all looked identical to the classifier.

**The fix:** Two-phase intent classifier:
1. Explanation-intent patterns (`"اشرح"`, `"كيف"`, `"هذا التمرين"`, `"ساعدني"`, …) cancel retrieval at highest priority.
2. Explicit retrieval patterns (`"تمرين بكالوريا"`, `"التمرين الأول"`, `"exercise 1"`, year+exercise combos) trigger retrieval.
3. Default: no retrieval → LangGraph.

**The structural risk that remains:** `knowledge_base/` is a single-file directory. Any retrieval trigger — even a correct one — returns the same file. As the knowledge base grows, the retrieval system needs semantic ranking, not just file enumeration. Until then, the two-phase classifier is the only guard against context blindness.

**What must never be done:**
- Do not add new keywords to `detect_exercise_retrieval()` without also adding corresponding explanation-intent negation patterns.
- Do not assume keyword presence = retrieval intent. Always model the *why*.
- Do not expand `knowledge_base/` without also updating the retrieval ranking logic in `local_store.py` — a larger knowledge base with a flat retrieval strategy will return arbitrary results.
- Do not remove the `reason` field from `ExerciseRetrievalDecision` — it is the audit trail for debugging misclassifications.

---

## Cross-Pattern Synthesis

These five patterns share a common root: **the gap between what the system claims to do and what it actually does**.

| Pattern | Claim | Reality |
|---|---|---|
| Intent routing | "Routes educational questions to the educational path" | Routes any question containing `تمرين`, `حل`, `شرح`, etc. to educational — regardless of semantic context |
| DOM leakage | "Sidebar is hidden when closed" | Sidebar is visually off-screen but fully present in DOM, accessible to screen readers, keyboard, and find-in-page |
| Runtime truth | "CI enforces architectural truth" | CI enforces static import topology; runtime behavior, metric emission, and dashboard contracts are unverified |
| Observability | "LangGraph dashboard shows node metrics" | LangGraph dashboard queries metrics that are never emitted; panels are permanently empty |
| Retrieval context blindness | "Retrieves relevant exercise content" | Returns the same single file for any question containing "تمرين" — keyword presence ≠ retrieval intent |

**The systemic failure mode:** Each layer of the system (routing, rendering, governance, observability) has a local definition of "working" that does not align with the user-visible definition of "working". The system passes its own checks while failing the user's expectations.

**The institutional memory imperative:** These patterns must be remembered because they will recur.

---

## Pattern 6: In-Memory Singleton Secrets (ISS-090, 2026-05-27)

**What happened:** `_get_or_create_dev_secret_key()` generated a random key stored
only in `_DEV_SECRET_KEY_CACHE` (process memory). Every uvicorn restart produced a
new key. All active JWT tokens were invalidated. Users were thrown to the login page
and re-entered automatically in an infinite loop. The HTTP probe in
`useRealtimeConnection` returned 200 (same process, same key) so the loop treated
every 4401 as "transient" and kept retrying forever.

**Why it recurs:** The pattern looks correct at first glance — "cache the key so it
doesn't change within a session." The flaw is that "session" means "process lifetime,"
not "user session." Cloud environments restart processes routinely.

**The fix:** Persist the key to disk on first generation. Read from disk on subsequent
starts. The disk file outlives any single process.

**What must never be done:**
- Do not generate cryptographic secrets in memory only. Always persist to disk or
  read from an external secrets manager.
- Do not assume a `lru_cache` or module-level variable survives a process restart.
- Do not use `${SECRET_KEY:-some-default}` as a fallback in supervisor scripts without
  first ensuring the variable is populated from a stable source. Each service that
  uses a different default breaks cross-service JWT verification silently.
- Do not rely on the HTTP probe in `useRealtimeConnection` to distinguish "key changed"
  from "token expired" — both return 401/4401 and the probe cannot tell them apart.

**The structural risk that remains:** `.devcontainer/state/dev_secret_key` is a local
file that does not survive a full devcontainer rebuild. After a rebuild, a new key is
generated and all previously issued tokens (stored in browser localStorage) become
invalid. Users will need to log in again after a rebuild — this is acceptable and
expected behavior, but should be documented in the onboarding guide. Every time a new feature is added:
- A new keyword will be added to `_EDUCATIONAL_PATTERNS` instead of fixing the semantic classifier
- A new keyword will be added to `detect_exercise_retrieval()` without a negation guard, re-introducing context blindness
- A new sidebar will use `transform: translateX` without `aria-hidden`
- A new dashboard panel will be added without verifying the metric emitter
- A new component will be classified ACTIVE based on import presence alone

The purpose of this document is to make these failure modes visible before they are repeated.
