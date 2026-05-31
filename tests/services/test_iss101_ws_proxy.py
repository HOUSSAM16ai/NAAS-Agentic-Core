"""
Regression test — server.js WebSocket proxy must be reliable (ISS-101 / D-WS-PROXY-001).

USER REPORT + LIVE DIAGNOSTIC (GitHub Codespaces, 2026-05-29):
Running scripts/diagnose_chat.py inside the user's Codespace produced the decisive
evidence (all backend health green; all fixes deployed; token 1440 min):

  -- direct backend :8000 (no proxy) --
  [direct:8000] round 1/2/3: OK answered  (session_ready→conversation_init→delta→assistant_final)
  -- via frontend :5000 (server.js proxy, the browser path) --
  [proxy:5000] round 1/2/3: NO ANSWER  close=1006  frames=[session_ready, CLOSED:1006]

ROOT CAUSE (D-WS-PROXY-001):
The backend is 100% healthy. The flapping/no-answer lived entirely in
`frontend/server.js`, which proxied the WebSocket with `http-proxy` (1.x,
unmaintained). It forwarded the first downstream frame (session_ready) then the
socket died with 1006, and — critically — it dropped the client's question that
the browser sends immediately after connect (before the upstream socket opens).
Result: no answer → reconnect → "connected/disconnected" in the first seconds.

FIX:
Rewrote the WS proxy with the `ws` library (noServer upgrade → upstream WebSocket
→ bidirectional pipe) PLUS a pending-message QUEUE that buffers client messages
sent before the upstream connection opens and flushes them on `open`. A faithful
Python replica proved it live: the greeting is queued, flushed on upstream open,
and the full answer streams back with a clean close (vs http-proxy's 1006).

INVARIANTS (enforced here):
A. server.js uses the `ws` library (WebSocketServer + WebSocket), not http-proxy, for WS.
B. server.js buffers early client messages in a queue and flushes on upstream open.
C. package.json declares `ws` as a dependency.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER = REPO_ROOT / "frontend" / "server.js"
PKG = REPO_ROOT / "frontend" / "package.json"
HOOK = REPO_ROOT / "frontend" / "app" / "hooks" / "useRealtimeConnection.js"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_heartbeat_is_non_fatal() -> None:
    """D-WS-PROXY-002: the client heartbeat must NOT force-close the WS on timeout.

    Live logs showed connections closing with 1001 ("heartbeat_timeout") right after
    session_ready/conversation_init and before the answer deltas → reconnect churn →
    incomplete answers + flapping. uvicorn protocol ping/pong + the browser's native
    dead-socket detection recycle truly-dead connections, so the app-level close is
    redundant and harmful. The active `ws.close(1001, "heartbeat_timeout")` call must
    be gone (the same text may remain only inside an explanatory comment).
    """
    src = _read(HOOK)
    assert 'ws.close(1001, "heartbeat_timeout")' not in src, (
        "D-WS-PROXY-002: heartbeat must not force-close with 1001 — it churned connections "
        "and cut answers. Keep the ping, drop the close."
    )


def test_server_js_uses_ws_library() -> None:
    src = _read(SERVER)
    assert 'require("ws")' in src or "require('ws')" in src, (
        "D-WS-PROXY-001: server.js must use the `ws` library for WebSocket proxying."
    )
    assert "WebSocketServer" in src and "noServer" in src, (
        "D-WS-PROXY-001: server.js must use WebSocketServer({ noServer: true }) to own the upgrade."
    )


def test_server_js_does_not_proxy_ws_via_http_proxy() -> None:
    src = _read(SERVER)
    # http-proxy may be mentioned in comments, but must NOT be used to proxy WS.
    assert "httpProxy.createProxyServer" not in src, (
        "D-WS-PROXY-001: http-proxy (1.x) drops WS frames with 1006 — must not be used for WS."
    )
    assert "wsProxy.ws(" not in src, (
        "D-WS-PROXY-001: the http-proxy `.ws()` call must be gone (it caused the 1006 flap)."
    )


def test_server_js_queues_early_client_messages() -> None:
    """The critical fix: buffer the greeting sent before the upstream socket opens."""
    src = _read(SERVER)
    assert "pending" in src, (
        "D-WS-PROXY-001: server.js must queue client messages sent before upstream `open` "
        "(the browser sends the question immediately after connect — http-proxy dropped it)."
    )
    # A guard distinguishing 'upstream ready' from 'not yet' must exist.
    assert "upstreamReady" in src or "ready" in src, (
        "D-WS-PROXY-001: server.js must track upstream readiness to know when to flush the queue."
    )
    # The queue must be drained on the upstream 'open' event.
    assert 'upstream.on("open"' in src or "upstream.on('open'" in src, (
        "D-WS-PROXY-001: queued messages must be flushed on the upstream 'open' event."
    )


def test_client_build_stamp_present() -> None:
    """D-WS-PROXY-002: the client stamps its build on the WS URL (?cb=) and server.js logs it,
    so we can prove which JS the browser is actually running."""
    hook = _read(HOOK)
    assert "CLIENT_BUILD" in hook and 'set("cb"' in hook, (
        "D-WS-PROXY-002: useRealtimeConnection must stamp ?cb=<CLIENT_BUILD> on the WS URL."
    )
    server = _read(SERVER)
    assert "build=" in server and "cb=" in server, (
        "D-WS-PROXY-002: server.js must log the client build (cb) per connection."
    )


def test_build_version_consistent() -> None:
    """D-WS-PROXY-003: buildVersion.js BUILD_VERSION must equal public/build.json `build`,
    so the self-heal check compares like-for-like (mismatch only means a truly stale tab)."""
    import json
    import re

    bv = (REPO_ROOT / "frontend" / "app" / "buildVersion.js").read_text(encoding="utf-8")
    m = re.search(r'BUILD_VERSION\s*=\s*"([^"]+)"', bv)
    assert m, "BUILD_VERSION constant missing in buildVersion.js"
    build_json = json.loads((REPO_ROOT / "frontend" / "public" / "build.json").read_text("utf-8"))
    assert build_json.get("build") == m.group(1), (
        f"D-WS-PROXY-003: build.json ({build_json.get('build')}) must equal "
        f"BUILD_VERSION ({m.group(1)})."
    )


def test_app_self_heals_stale_bundle() -> None:
    """D-WS-PROXY-003: CogniForgeApp must compare the served build (build.json) to its
    bundled BUILD_VERSION and reload once on mismatch — so a stale tab fixes itself."""
    app = (REPO_ROOT / "frontend" / "app" / "components" / "CogniForgeApp.jsx").read_text("utf-8")
    assert "build.json" in app and "BUILD_VERSION" in app, (
        "D-WS-PROXY-003: App must fetch build.json and compare to BUILD_VERSION."
    )
    assert "window.location.reload()" in app, (
        "D-WS-PROXY-003: App must reload once when the bundle is stale."
    )
    assert "sessionStorage" in app, (
        "D-WS-PROXY-003: the reload must be guarded (sessionStorage) to avoid loops."
    )


def test_supervisor_clears_next_unconditionally_on_boot() -> None:
    """D-WS-PROXY-003: supervisor must clear .next before launching the frontend so a fresh
    Codespace never serves a stale prebuilt bundle."""
    sup = (REPO_ROOT / ".devcontainer" / "supervisor.sh").read_text(encoding="utf-8")
    assert 'rm -rf "frontend/.next"' in sup
    assert "force a fresh client bundle" in sup, (
        "D-WS-PROXY-003: the .next clear must run unconditionally on frontend launch."
    )


def test_package_json_declares_ws() -> None:
    import json

    pkg = json.loads(_read(PKG))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert "ws" in deps, "D-WS-PROXY-001: package.json must declare `ws` as a dependency."


def test_server_js_loads_ws_defensively() -> None:
    """server.js must fall back to Next's vendored ws so it never crashes if `npm install`
    has not run yet in an existing Codespace (node_modules predates the new dependency)."""
    src = _read(SERVER)
    assert "next/dist/compiled/ws" in src, (
        "D-WS-PROXY-001: server.js must fall back to next/dist/compiled/ws (always present) "
        "if the top-level `ws` is not installed — otherwise require('ws') crashes the frontend "
        "after a git pull that added the dependency but before `npm install` runs."
    )


def test_supervisor_reinstalls_on_package_change() -> None:
    """The supervisor must reinstall frontend deps when package.json changed (not only when
    node_modules is missing), so a pulled `ws` dependency actually gets installed."""
    sup = (REPO_ROOT / ".devcontainer" / "supervisor.sh").read_text(encoding="utf-8")
    assert 'frontend/package.json" -nt "frontend/node_modules' in sup, (
        "D-WS-PROXY-001: supervisor.sh must reinstall when package.json is newer than "
        "node_modules (e.g. after git pull adds `ws`)."
    )


# ──────────────────────────────────────────────────────────────────────────────
# D-WS-RELOAD-001 (ISS-101 — 2026-05-31): the ~45s remount/reload loop.
#
# Forensic [CLIENT-LOG] from the user's Codespace showed 4× `ws_open`
# was_reconnect=false ~every 45s with NO ws_close, NO logout. Root cause:
# server.js destroyed every non-chat WebSocket upgrade — including
# /_next/webpack-hmr — and an aggressive setInterval re-asserted that its
# handler was the sole 'upgrade' listener every 3s. Next's dev (Fast Refresh)
# client, perpetually unable to keep its HMR socket, full-reloaded the page on
# a backoff (~45s) → useRealtimeConnection remounted → conversationId wiped
# ("new conversation") + connect/disconnect churn.
#
# Fix: delegate non-chat upgrades to Next's getUpgradeHandler (HMR preserved);
# remove the aggressive setInterval guard.
# ──────────────────────────────────────────────────────────────────────────────


def test_server_js_delegates_hmr_upgrades_to_next() -> None:
    """server.js must NOT destroy non-chat upgrades (it would kill /_next/webpack-hmr
    → Next dev client reload loop). It must delegate them to Next's getUpgradeHandler."""
    src = _read(SERVER)
    assert "getUpgradeHandler" in src, (
        "D-WS-RELOAD-001: server.js must obtain app.getUpgradeHandler() and delegate "
        "non-chat (HMR) upgrades to it — destroying them causes a periodic full-page "
        "reload that remounts the WS hook (conversation reset + connect/disconnect churn)."
    )


def test_server_js_has_no_aggressive_upgrade_guard() -> None:
    """The 3s setInterval that removed every non-own 'upgrade' listener guaranteed HMR
    could never work. It must be gone."""
    src = _read(SERVER)
    assert "upgradeGuard" not in src and "setInterval" not in src, (
        "D-WS-RELOAD-001: the periodic setInterval upgrade guard must be removed — it "
        "permanently disabled Next HMR and caused the ~45s reload/remount loop."
    )


def test_server_js_does_not_blanket_destroy_non_chat_upgrades() -> None:
    """A bare `socket.destroy()` for all non-chat upgrades is the regression. Destroy is
    only allowed as a fallback when getUpgradeHandler is unavailable."""
    src = _read(SERVER)
    # The only socket.destroy must sit inside the `if (nextUpgradeHandler) {...} else {`
    # fallback — never as the unconditional non-chat branch.
    assert src.count("socket.destroy()") <= 1, (
        "D-WS-RELOAD-001: server.js must not unconditionally destroy non-chat upgrades; "
        "delegate to Next instead (single destroy allowed only as the no-handler fallback)."
    )
