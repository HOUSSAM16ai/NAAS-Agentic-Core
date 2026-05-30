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
