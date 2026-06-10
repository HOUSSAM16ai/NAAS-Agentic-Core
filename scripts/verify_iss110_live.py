#!/usr/bin/env python3.12
"""
ISS-110 (D-101) — Live E2E: topic-switch catastrophe reproduction + fix proof.

يستنسخ transcript المستخدم الحقيقي (2026-06-10) حرفياً في محادثة واحدة:
  Q1 «اعطني تمرين الأعداد المركبة»          → تمرين الأعداد المركبة (نص)
  Q2 «اعطني تمرين الاحتمالات»               → تمرين الاحتمالات (نص) — يدخل history
  Q3 «اعطني تمرين الدوال العددية»           → تمرين الدوال 2016 (كان: combinations_visualizer!)
  Q4 «اعطني تمرين الدوال العددية لسنة 2016» → نفس الشيء
  Q5 «مفهمتش كيفاش حسبنا الاحتمال» (regression) → ui_component يبقى يعمل (MODE_B)

Usage:
    E2E_BACKEND=http://localhost:8000 python3.12 scripts/verify_iss110_live.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

import httpx
import websockets

BACKEND = os.environ.get("E2E_BACKEND", "http://localhost:8000")
EMAIL = os.environ.get("E2E_EMAIL", "houssamannaba963@gmail.com")
PASSWORD = os.environ.get("E2E_PASSWORD", "1111")
FULLNAME = "Houssam E2E"


async def ensure_user() -> str:
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
                print(f"  login OK -> user_id={(d.get('user') or {}).get('id')}")
                return d["access_token"]
        raise SystemExit(f"login failed: {r.status_code} {r.text[:200]}")


async def turn(ws, question: str, conversation_id: int | None) -> dict:
    """يرسل سؤالاً واحداً ويجمع كل الأحداث حتى الإطار النهائي."""
    payload: dict = {"question": question, "client_request_id": str(uuid.uuid4())}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    await ws.send(json.dumps(payload))

    text_parts: list[str] = []
    ui_components: list[str] = []
    conv_id = conversation_id
    terminal = None
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=180)
        event = json.loads(raw)
        etype = event.get("type")
        ep = event.get("payload") or {}
        if etype == "conversation_init":
            conv_id = ep.get("conversation_id") or conv_id
        elif etype == "assistant_delta":
            text_parts.append(str(ep.get("content") or ""))
        elif etype == "ui_component":
            ui_components.append(str(ep.get("component") or "?"))
        elif etype in ("assistant_final", "complete", "error", "assistant_error"):
            terminal = etype
            if etype in ("assistant_final", "complete"):
                # انتظر إطار persisted إن وُجد (غير إلزامي) بمهلة قصيرة
                try:
                    extra = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                    if extra.get("type") == "ui_component":
                        ui_components.append(
                            str((extra.get("payload") or {}).get("component") or "?")
                        )
                except TimeoutError:
                    pass
            break
    return {
        "text": "".join(text_parts),
        "ui_components": ui_components,
        "conversation_id": conv_id,
        "terminal": terminal,
    }


def check(name: str, ok: bool, detail: str) -> bool:
    mark = "✅" if ok else "❌"
    print(f"  {mark} {name}: {detail}")
    return ok


async def main() -> int:
    print(f"[1] backend={BACKEND}")
    token = await ensure_user()
    scheme = "wss" if BACKEND.startswith("https") else "ws"
    host = BACKEND.split("://", 1)[1]
    url = f"{scheme}://{host}/api/chat/ws?token={token}&session_id={uuid.uuid4()}"

    results: list[bool] = []
    async with websockets.connect(url, ping_interval=None, open_timeout=20) as ws:
        # primer frame (session_ready) — تخطَّ
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print(f"[2] WS connected, primer={first.get('type')}")

        conv: int | None = None

        print("\n[Q1] اعطني تمرين الأعداد المركبة")
        r1 = await turn(ws, "اعطني تمرين الأعداد المركبة", conv)
        conv = r1["conversation_id"]
        results.append(
            check(
                "Q1 complex numbers exercise",
                "المركبة" in r1["text"] and len(r1["text"]) > 200,
                f"chars={len(r1['text'])} ui={r1['ui_components']} conv={conv}",
            )
        )

        print("\n[Q2] اعطني تمرين الاحتمالات")
        r2 = await turn(ws, "اعطني تمرين الاحتمالات", conv)
        results.append(
            check(
                "Q2 probability exercise text",
                ("كرة" in r2["text"] or "احتمال" in r2["text"]) and len(r2["text"]) > 200,
                f"chars={len(r2['text'])} ui={r2['ui_components']}",
            )
        )

        print("\n[Q3] اعطني تمرين الدوال العددية  ← THE CATASTROPHE TURN")
        r3 = await turn(ws, "اعطني تمرين الدوال العددية", conv)
        results.append(
            check(
                "Q3 NO probability UI hijack",
                "combinations_visualizer" not in r3["ui_components"]
                and "probability_tree" not in r3["ui_components"]
                and "full_exercise_story" not in r3["ui_components"],
                f"ui={r3['ui_components']}",
            )
        )
        results.append(
            check(
                "Q3 numerical-functions exercise delivered",
                "الدوال العددية" in r3["text"] and len(r3["text"]) > 500,
                f"chars={len(r3['text'])} head={r3['text'][:80]!r}",
            )
        )

        print("\n[Q4] اعطني تمرين الدوال العددية لسنة 2016")
        r4 = await turn(ws, "اعطني تمرين الدوال العددية لسنة 2016", conv)
        results.append(
            check(
                "Q4 NO probability UI hijack",
                "combinations_visualizer" not in r4["ui_components"],
                f"ui={r4['ui_components']}",
            )
        )
        results.append(
            check(
                "Q4 numerical-functions 2016 delivered",
                "الدوال العددية" in r4["text"] and len(r4["text"]) > 500,
                f"chars={len(r4['text'])}",
            )
        )

        print("\n[Q5] مفهمتش كيفاش حسبنا الاحتمال  ← MODE_B regression")
        # السيناريو الحقيقي V31.5: الحيرة تأتي مباشرةً بعد تمرين الاحتمالات
        # (داخل نافذة آخر-6 رسائل للـ skill) — محادثة جديدة تعكس ذلك بدقة.
        r5a = await turn(ws, "اعطني تمرين الاحتمالات", None)
        conv2 = r5a["conversation_id"]
        r5 = await turn(ws, "مفهمتش كيفاش حسبنا الاحتمال", conv2)
        _prob_components = ("combinations_visualizer", "probability_tree", "full_exercise_story")
        results.append(
            check(
                "Q5 probability visual aid still fires (MODE_B)",
                any(c in _prob_components for c in r5["ui_components"]),
                f"ui={r5['ui_components']} chars={len(r5['text'])}",
            )
        )

    print("\n" + "=" * 60)
    passed = sum(results)
    print(f"RESULT: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
