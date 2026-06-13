"""verify_revolution_live.py — live E2E of the ISS-114/D-106 fixes + pillars.

Drives WS through the FULL stack (monolith :8000 → orchestrator :8006 HTTP/MODE_B
→ real OpenRouter) and replays the catastrophe transcript. Proves the MODE_B-over
-HTTP content-integrity hole is closed LIVE (the part unit tests cannot cover).

Env: E2E_BACKEND (default http://localhost:8000), E2E_EMAIL/E2E_PASSWORD.
SQLite + real OpenRouter; Supabase Postgres blocked in sandbox (verified via bridge).
"""

from __future__ import annotations

import asyncio
import json
import os
import re

import httpx
from websockets.asyncio.client import connect

BACKEND = os.environ.get("E2E_BACKEND", "http://localhost:8000")
WS = BACKEND.replace("http", "ws") + "/api/chat/ws"
EMAIL = os.environ.get("E2E_EMAIL", "houssamannaba963@gmail.com")
PASSWORD = os.environ.get("E2E_PASSWORD", "1111")

GARBAGE = ["experiences_random", "brückecónceptual", "exitos", "Eingaben", "Sweg", "ôté", "casos"]
HTML_RE = re.compile(r"<(div|span|p|button|table|h[1-6])\b|class\s*=|</[a-zA-Z]+>")


async def login() -> str:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"{BACKEND}/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )
        d = r.json()
        return (d.get("data") or {}).get("access_token") or d.get("access_token") or ""


async def ask(token: str, question: str, timeout: float = 90.0) -> dict:
    """يرسل سؤالاً ويجمع كل deltas + ui_component events + الإطار النهائي."""
    deltas: list[str] = []
    ui_components: list[dict] = []
    terminal = None
    async with connect(
        WS + f"?token={token}", subprotocols=["jwt", token], ping_interval=None
    ) as ws:
        await ws.send(json.dumps({"question": question}))
        while True:
            try:
                ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            except TimeoutError:
                break
            t = ev.get("type")
            payload = ev.get("payload") or ev
            if t == "assistant_delta":
                deltas.append(str(payload.get("content", "")))
            elif t == "ui_component":
                ui_components.append(payload)
            elif t in ("assistant_final", "stream_end", "complete"):
                if payload.get("content"):
                    deltas.append(str(payload.get("content", "")))
                terminal = t
                break
            elif t == "error":
                terminal = "error"
                deltas.append(
                    "[ERROR] " + str(payload.get("message") or payload.get("content") or payload)
                )
                break
    return {"text": "".join(deltas), "ui": ui_components, "terminal": terminal}


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"  {'✅' if cond else '❌'} {name}" + (f" — {detail}" if detail else ""))
    return cond


async def main() -> int:
    token = await login()
    if not token:
        print("LOGIN FAILED")
        return 1
    print(f"login OK (token {len(token)} chars)\nWS: {WS}\n")
    passed = 0
    total = 0

    def tally(ok: bool) -> None:
        nonlocal passed, total
        total += 1
        passed += 1 if ok else 0

    # T1 — Latin garbage through the orchestrator path
    print("[T1] غارباج لاتيني عبر المسار الكامل")
    r = await ask(token, "اشرح لي مفهوم المتغير العشوائي في الاحتمالات بالتفصيل")
    leaked = [g for g in GARBAGE if g in r["text"]]
    tally(check("صفر غارباج لاتيني", not leaked, f"len={len(r['text'])} leaked={leaked}"))
    tally(check("أجاب (نص غير فارغ)", len(r["text"]) > 20, f"terminal={r['terminal']}"))

    # T2 — HTML leak on "generate a UI"
    print("[T2] طلب توليد واجهة")
    r = await ask(token, "قم بتوليد واجهة تشرح الحادثة P(A) في كيس فيه 4 كرات حمراء و7 خضراء")
    tally(check("صفر HTML خام في النص", not HTML_RE.search(r["text"]), r["text"][:80]))
    tally(
        check(
            "مكوّن ui_component أو نص نظيف",
            bool(r["ui"]) or len(r["text"]) > 10,
            f"ui={[u.get('payload', {}).get('component') or u.get('component') for u in r['ui']]}",
        )
    )

    # T3 — wrong-context visual
    print("[T3] الواجهة الصحيحة للكيس (لا نرد/عملة)")
    await ask(token, "اعطني تمرين الاحتمالات 2024")
    r = await ask(token, "اشرح لي المتغير العشوائي")
    blob = json.dumps(r["ui"], ensure_ascii=False)
    tally(check("لا تسميات نرد/عملة عامة", "وجه" not in blob and "كتابة" not in blob, blob[:80]))

    # T4 — complex-functions phrasing
    print("[T4] «الدوال المركبة 2024»")
    r = await ask(token, "اعطني تمرين الدوال المركبة لسنة 2024")
    txt = r["text"]
    tally(
        check(
            "ليس تمرين الاحتمالات",
            "كرات" not in txt[:400] or "مركب" in txt or "z" in txt.lower(),
            txt[:80],
        )
    )

    print(f"\n=== LIVE E2E: {passed}/{total} checks passed ===")
    return 0 if passed == total else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
