#!/usr/bin/env python3.12
"""
Live E2E proof for the orchestrator-service `routes.py` (ISS — runtime activation).

Exercises the chain that was DORMANT:
  1. direct  : POST {ORCH}/api/chat/messages         → routes.py LangGraph stream
  2. monolith: WS   {BACKEND}/api/chat/ws            → OrchestratorClient → orchestrator
  3. frontend: WS   {FRONTEND}/api/chat/ws (proxy)   → server.js → monolith → orchestrator

Env overrides:
  E2E_BACKEND   (default http://localhost:8000)
  E2E_ORCH      (default http://localhost:8006)
  E2E_FRONTEND  (default http://localhost:5000)
  E2E_EMAIL / E2E_PASSWORD / E2E_FULLNAME

Usage:
  python3.12 scripts/e2e_orchestrator_live.py "اشرح قانون نيوتن الثاني"
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid

import httpx
import websockets

BACKEND = os.environ.get("E2E_BACKEND", "http://localhost:8000")
ORCH = os.environ.get("E2E_ORCH", "http://localhost:8006")
FRONTEND = os.environ.get("E2E_FRONTEND", "http://localhost:5000")
EMAIL = os.environ.get("E2E_EMAIL", "houssamannaba963@gmail.com")
PASSWORD = os.environ.get("E2E_PASSWORD", "1111")
FULLNAME = os.environ.get("E2E_FULLNAME", "Houssam E2E")


def _ws_url(base: str, path: str, token: str) -> str:
    scheme = "wss" if base.startswith("https") else "ws"
    host = base.split("://", 1)[1]
    return f"{scheme}://{host}{path}?token={token}&session_id={uuid.uuid4()}&cb=E2E"


async def ensure_user() -> tuple[str, int]:
    """Login the test user; register first if needed. Returns (token, user_id)."""
    async with httpx.AsyncClient(timeout=30) as c:
        for attempt in ("login", "register", "login"):
            if attempt == "register":
                r = await c.post(
                    f"{BACKEND}/api/security/register",
                    json={"full_name": FULLNAME, "email": EMAIL, "password": PASSWORD},
                )
                print(f"  register -> HTTP {r.status_code}")
                continue
            r = await c.post(
                f"{BACKEND}/api/security/login",
                json={"email": EMAIL, "password": PASSWORD},
            )
            if r.status_code == 200:
                d = r.json()
                tok = d["access_token"]
                uid = (d.get("user") or {}).get("id")
                print(f"  login OK -> user_id={uid}")
                return tok, int(uid)
        raise SystemExit(f"login failed: {r.status_code} {r.text[:200]}")


async def orchestrator_direct(token: str, question: str) -> dict:
    """POST /api/chat/messages directly to the orchestrator and parse the NDJSON stream."""
    deltas = 0
    chars = 0
    frame_types: list[str] = []
    answer_parts: list[str] = []
    terminal = None
    t0 = time.time()
    ttft = None
    async with httpx.AsyncClient(timeout=180) as c:
        async with c.stream(
            "POST",
            f"{ORCH}/api/chat/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": question, "conversation_id": None},
        ) as resp:
            if resp.status_code != 200:
                body = (await resp.aread()).decode("utf-8", "replace")
                return {"ok": False, "status": resp.status_code, "body": body[:400]}
            async for raw_line in resp.aiter_lines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                et = ev.get("type", "?")
                if et not in frame_types[-1:]:
                    frame_types.append(et)
                payload = ev.get("payload", {}) if isinstance(ev.get("payload"), dict) else {}
                if et == "assistant_delta":
                    txt = payload.get("content", "")
                    if txt:
                        if ttft is None:
                            ttft = time.time() - t0
                        deltas += 1
                        chars += len(txt)
                        answer_parts.append(txt)
                elif et in ("assistant_final", "complete", "error"):
                    terminal = et
                    fc = payload.get("content", "")
                    if fc and not answer_parts:
                        answer_parts.append(fc)
    answer = "".join(answer_parts)
    return {
        "ok": terminal in ("assistant_final", "complete") and chars > 0,
        "deltas": deltas,
        "chars": chars,
        "terminal": terminal,
        "ttft": round(ttft, 2) if ttft else None,
        "total_s": round(time.time() - t0, 2),
        "frames": frame_types[:8],
        "answer_head": answer[:240],
        "answer_tail": answer[-160:] if len(answer) > 240 else "",
    }


async def ws_chat(base: str, token: str, question: str, label: str) -> dict:
    """Connect a WS chat (monolith or frontend proxy) and collect the streamed answer."""
    url = _ws_url(base, "/api/chat/ws", token)
    deltas = 0
    chars = 0
    answer_parts: list[str] = []
    frame_types: list[str] = []
    terminal = None
    close_code = None
    t0 = time.time()
    try:
        # Browser-style auth: ?token= query param, NO subprotocol. Going through
        # the Next.js server.js proxy (:5000), offering a subprotocol forces the
        # upstream ws-library client to require a subprotocol echo the monolith
        # does not send → 1011. useRealtimeConnection.js uses query-param too.
        async with websockets.connect(url, ping_interval=None, open_timeout=20) as ws:
            await ws.send(
                json.dumps({"question": question, "client_request_id": str(uuid.uuid4())})
            )
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=180)
                except TimeoutError:
                    terminal = "timeout"
                    break
                try:
                    ev = json.loads(raw)
                except Exception:
                    continue
                et = ev.get("type", "?")
                if et not in frame_types[-1:]:
                    frame_types.append(et)
                payload = ev.get("payload", {}) if isinstance(ev.get("payload"), dict) else {}
                if et == "assistant_delta":
                    txt = payload.get("content", "")
                    if txt:
                        deltas += 1
                        chars += len(txt)
                        answer_parts.append(txt)
                elif et in ("assistant_final", "complete", "error"):
                    terminal = et
                    fc = payload.get("content", "")
                    if fc and not answer_parts:
                        answer_parts.append(fc)
                    break
    except Exception as e:
        return {
            "ok": False,
            "label": label,
            "error": f"{type(e).__name__}: {e}",
            "close": close_code,
        }
    answer = "".join(answer_parts)
    return {
        "ok": terminal in ("assistant_final", "complete") and chars > 0,
        "label": label,
        "deltas": deltas,
        "chars": chars,
        "terminal": terminal,
        "total_s": round(time.time() - t0, 2),
        "frames": frame_types[:8],
        "answer_head": answer[:240],
    }


async def main() -> int:
    question = sys.argv[1] if len(sys.argv) > 1 else "اشرح قانون نيوتن الثاني بإيجاز"
    print(f"== E2E orchestrator live ==\n  backend={BACKEND} orch={ORCH} frontend={FRONTEND}")
    print(f"  question={question!r}")

    print("\n[1] auth")
    token, _uid = await ensure_user()

    print("\n[2] DIRECT orchestrator  POST /api/chat/messages")
    r1 = await orchestrator_direct(token, question)
    print("   ", json.dumps(r1, ensure_ascii=False))

    print("\n[3] MONOLITH WS  :8000/api/chat/ws")
    r2 = await ws_chat(BACKEND, token, question, "monolith")
    print("   ", json.dumps(r2, ensure_ascii=False))

    print("\n[4] FRONTEND WS (proxy)  :5000/api/chat/ws")
    r3 = await ws_chat(FRONTEND, token, question, "frontend")
    print("   ", json.dumps(r3, ensure_ascii=False))

    ok = bool(r1.get("ok"))  # direct orchestrator is the mandatory proof
    print(f"\n== RESULT: direct={r1.get('ok')} monolith={r2.get('ok')} frontend={r3.get('ok')} ==")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
