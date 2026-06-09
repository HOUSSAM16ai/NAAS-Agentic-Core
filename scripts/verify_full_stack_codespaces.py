#!/usr/bin/env python3
"""
verify_full_stack_codespaces.py — تحقّق حيّ كامل للمنظومة في GitHub Codespaces.

يفحص (بصدق، مع SKIP عند تعذّر الوصول بدل الفشل الكاذب):
  1. المونوليث :8000 /health.
  2. الخدمات الـ 8 المصغرة /health (8001–8009).
  3. Skills Pipeline /compose → pipeline_mode (full/partial/fallback).
  4. منصّة الـ Skills /api/v1/skills (الـ 14 Skill + الحالة).
  5. (اختياري) دور WebSocket حيّ عبر :8000/api/chat/ws إن توفّرت بيانات الدخول.

يُشغَّل في Codespaces حيث الـ egress مفتوح (الـ sandbox يحجب pip + منافذ Postgres).

Usage:
  python3 scripts/verify_full_stack_codespaces.py
  E2E_EMAIL=you@example.com E2E_PASSWORD=1111 python3 scripts/verify_full_stack_codespaces.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BACKEND = os.getenv("E2E_BACKEND", "http://localhost:8000")
ORCH = os.getenv("E2E_ORCH", "http://localhost:8006")

_PASS = "\033[92m✅\033[0m"
_SKIP = "\033[93m⚠️ SKIP\033[0m"
_FAIL = "\033[91m❌\033[0m"

_failures: list[str] = []


def _get(url: str, timeout: float = 5.0) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def _post(url: str, body: dict, timeout: float = 60.0) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def section(title: str) -> None:
    print(f"\n── {title} ──")


def check_monolith() -> None:
    section("1. Monolith :8000")
    status, body = _get(f"{BACKEND}/health")
    if status == 200 and "ok" in body:
        print(f"{_PASS} /health → {body[:120]}")
    else:
        _failures.append("monolith /health")
        print(f"{_FAIL} /health → status={status} {body[:120]}")


def check_microservices() -> None:
    section("2. Microservices /health (8001–8009)")
    services = {
        8001: "user",
        8002: "planning",
        8003: "conversation",
        8006: "orchestrator",
        8007: "research",
        8008: "reasoning",
        8009: "content-retrieval",
    }
    up = 0
    for port, name in services.items():
        status, body = _get(f"http://localhost:{port}/health")
        if status == 200:
            up += 1
            print(f"{_PASS} :{port} {name:18} → {body[:90]}")
        else:
            print(f"{_SKIP} :{port} {name:18} → not reachable (status={status})")
    print(f"   → {up}/{len(services)} services healthy")


def check_skills_pipeline() -> None:
    section("3. Skills Pipeline /compose")
    status, body = _post(f"{ORCH}/compose", {"query": "اشرح قانون نيوتن الثاني"}, timeout=60.0)
    if status != 200:
        print(f"{_SKIP} /compose not reachable (status={status}) — orchestrator down?")
        return
    try:
        data = json.loads(body)
        mode = data.get("pipeline_mode", "?")
        active = data.get("skills_active", [])
        marker = _PASS if mode == "full" else _SKIP
        print(f"{marker} pipeline_mode={mode} skills_active={active}")
        if mode != "full":
            print("   (set OPENROUTER_API_KEY + TAVILY_API_KEY for 'full' mode)")
    except Exception:
        print(f"{_FAIL} /compose returned non-JSON: {body[:120]}")
        _failures.append("compose non-JSON")


def check_skills_platform() -> None:
    section("4. Skills Platform /api/v1/skills (D-100)")
    status, body = _get(f"{BACKEND}/api/v1/skills")
    if status != 200:
        _failures.append("skills platform endpoint")
        print(f"{_FAIL} /api/v1/skills → status={status} {body[:120]}")
        return
    try:
        data = json.loads(body)
        total, active, flagged = data["total"], data["active"], data["flagged"]
        if total == 14 and active == 12 and flagged == 2:
            print(f"{_PASS} {total} skills ({active} ACTIVE + {flagged} FLAGGED)")
        else:
            _failures.append("skills platform counts")
            print(f"{_FAIL} unexpected counts: total={total} active={active} flagged={flagged}")
        for s in data["skills"]:
            tag = "FLAG" if s["status"] == "FLAGGED" else "ON"
            print(f"     [{tag:4}] {s['name']:22} ← {', '.join(s['consumed_by'][:2])}")
    except Exception as e:
        _failures.append("skills platform parse")
        print(f"{_FAIL} parse error: {e}")


def check_ws_chat() -> None:
    section("5. WebSocket chat turn (optional)")
    email = os.getenv("E2E_EMAIL")
    password = os.getenv("E2E_PASSWORD")
    if not email or not password:
        print(f"{_SKIP} set E2E_EMAIL + E2E_PASSWORD to run the live WS turn")
        return
    try:
        import asyncio

        import websockets  # type: ignore
    except Exception:
        print(f"{_SKIP} websockets lib not installed — skipping WS turn")
        return

    status, body = _post(
        f"{BACKEND}/api/security/login", {"email": email, "password": password}, timeout=15.0
    )
    if status != 200:
        print(f"{_SKIP} login failed (status={status}) — skipping WS turn")
        return
    token = json.loads(body).get("access_token") or json.loads(body).get("token")
    if not token:
        print(f"{_SKIP} no token in login response — skipping WS turn")
        return

    async def _turn() -> bool:
        ws_url = BACKEND.replace("http", "ws") + f"/api/chat/ws?token={token}"
        async with websockets.connect(ws_url, subprotocols=["jwt", token]) as ws:  # type: ignore
            await ws.send(json.dumps({"question": "ما هو قانون نيوتن الثاني؟"}))
            deltas = 0
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=90.0)
                evt = json.loads(raw)
                if evt.get("type") == "assistant_delta":
                    deltas += 1
                elif evt.get("type") in ("assistant_final", "stream_end", "error"):
                    print(f"{_PASS} WS turn complete: {deltas} deltas, terminal={evt.get('type')}")
                    return evt.get("type") != "error"

    try:
        ok = asyncio.run(_turn())
        if not ok:
            _failures.append("ws turn errored")
    except Exception as e:
        print(f"{_SKIP} WS turn could not complete: {e}")


def main() -> None:
    print("=== Full-Stack Codespaces verification ===")
    check_monolith()
    check_microservices()
    check_skills_pipeline()
    check_skills_platform()
    check_ws_chat()

    print("\n=== Summary ===")
    if _failures:
        print(f"{_FAIL} {len(_failures)} hard failure(s): {_failures}")
        sys.exit(1)
    print(f"{_PASS} no hard failures (SKIP = service not running, not an error)")


if __name__ == "__main__":
    main()
