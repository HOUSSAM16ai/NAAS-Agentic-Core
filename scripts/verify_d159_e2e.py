#!/usr/bin/env python3
"""verify_d159_e2e.py — E2E FULL-STACK حي: المحرّك متعدد العُقد A→B فوق tutor_state (D-159).

يقود المكدس الحقيقي (uvicorn + WS + JWT + DB) ويُثبت:
  U1 «اعطني تمرين الاحتمالات 2024»  → التمرين (يبدأ محادثة جديدة نظيفة)
  U2 «كيف نحسب الحادثة A»           → S3: سؤال تشخيصي (لا تفريغ)
  U3 «هل هي 14 على 165»             → S2: أحسنت + **الانتقال للحادثة B** (بذر العقدة)
  U4 «الكرات الفردية عددها 8»        → B: اعتراف + خطوة النسبة (المحرّك على عقدة B)
  U5 «هل هي 56 من 165»              → B: أحسنت + إقفال عقدة B (understood)

ثم يقرأ صفّ `tutor_state` من قاعدة البيانات مباشرة (SQLite محلياً عبر D159_SQLITE_PATH،
أو Supabase عبر الجسر حين يتوفر SUPABASE_EDGE_FUNCTION_KEY على المكدس الحقيقي) ويؤكد:
`kc_progress.prob_event_a.state == understood` و `kc_progress.prob_event_b.state == understood`
— **الهيكل الدائم يحمل آلة الحالات المعرفية فعلاً** (لا مسح نصّ).

Usage:
    COGNITIVE_TURN_ENABLED=1 <شغّل الخادم> ثم:
    E2E_BACKEND=http://localhost:8000 DIAG_EMAIL=... DIAG_PASSWORD=... \
    D159_SQLITE_PATH=/path/to/e2e.db python3.12 scripts/verify_d159_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import uuid

import httpx
import websockets

BACKEND = os.environ.get("E2E_BACKEND", "http://localhost:8000")
EMAIL = os.environ.get("DIAG_EMAIL", "houssamannaba963@gmail.com")
PASSWORD = os.environ.get("DIAG_PASSWORD", "1111")
SQLITE_PATH = os.environ.get("D159_SQLITE_PATH", "")


async def ensure_user() -> str:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{BACKEND}/api/security/login", json={"email": EMAIL, "password": PASSWORD}
        )
        if r.status_code != 200:
            await c.post(
                f"{BACKEND}/api/security/register",
                json={"full_name": "Houssam D159 E2E", "email": EMAIL, "password": PASSWORD},
            )
            r = await c.post(
                f"{BACKEND}/api/security/login", json={"email": EMAIL, "password": PASSWORD}
            )
        if r.status_code != 200:
            raise SystemExit(f"login failed: {r.status_code} {r.text[:200]}")
        return r.json()["access_token"]


async def turn(ws, question: str, conversation_id: int | None) -> dict:
    payload: dict = {"question": question, "client_request_id": str(uuid.uuid4())}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    await ws.send(json.dumps(payload))
    parts: list[str] = []
    conv = conversation_id
    while True:
        event = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
        etype, ep = event.get("type"), (event.get("payload") or {})
        if etype == "conversation_init":
            conv = ep.get("conversation_id") or conv
        elif etype == "assistant_delta":
            parts.append(str(ep.get("content") or ""))
        elif etype in ("assistant_final", "complete", "error", "assistant_error"):
            break
    return {"text": "".join(parts), "conversation_id": conv}


def read_kc_progress(conversation_id: int) -> dict | None:
    """يقرأ kc_progress للمحادثة — SQLite مباشرة أو Supabase عبر الجسر."""
    if SQLITE_PATH and os.path.exists(SQLITE_PATH):
        con = sqlite3.connect(SQLITE_PATH)
        try:
            row = con.execute(
                "SELECT kc_progress FROM tutor_state WHERE conversation_id=? LIMIT 1",
                (conversation_id,),
            ).fetchone()
        finally:
            con.close()
        return json.loads(row[0]) if row and row[0] else None
    if os.environ.get("SUPABASE_EDGE_FUNCTION_KEY"):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import db_bridge  # type: ignore[import-not-found]

        status, body, _ = db_bridge.run_sql(
            f"SELECT kc_progress FROM tutor_state WHERE conversation_id={int(conversation_id)} LIMIT 1;"
        )
        if status == 200:
            rows = (json.loads(body) or {}).get("data") or []
            if rows:
                return json.loads(rows[0].get("kc_progress") or "{}")
    return None


def check(results: list[bool], name: str, ok: bool, detail: str) -> None:
    results.append(ok)
    print(f"  {'✅' if ok else '❌'} {name}: {detail[:110]}")


async def main() -> int:
    print(f"[1] backend={BACKEND} user={EMAIL} (server must run COGNITIVE_TURN_ENABLED=1)")
    token = await ensure_user()
    scheme = "wss" if BACKEND.startswith("https") else "ws"
    host = BACKEND.split("://", 1)[1]
    url = f"{scheme}://{host}/api/chat/ws?token={token}&session_id={uuid.uuid4()}"

    results: list[bool] = []
    async with websockets.connect(url, ping_interval=None, open_timeout=20) as ws:
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print(f"[2] WS connected, primer={first.get('type')}")

        r1 = await turn(ws, "اعطني تمرين الاحتمالات 2024", None)
        conv = r1["conversation_id"]
        check(results, "U1 exercise", len(r1["text"]) > 150, f"conv={conv}")

        r2 = await turn(ws, "كيف نحسب الحادثة A", conv)
        check(
            results,
            "U2 S3 probe (لا تفريغ)",
            "سؤال واحد قبل أي حساب" in r2["text"] and "165" not in r2["text"],
            r2["text"],
        )

        r3 = await turn(ws, "هل هي 14 على 165", conv)
        check(
            results,
            "U3 اعتراف A + انتقال للحادثة B",
            "أحسنت" in r3["text"] and "الحادثة B" in r3["text"],
            r3["text"],
        )

        r4 = await turn(ws, "الكرات الفردية عددها 8", conv)
        check(
            results,
            "U4 عقدة B نشطة (اعتراف + خطوة النسبة)",
            "الحادثة B" in r4["text"] and "أحسنت" not in r4["text"],
            r4["text"],
        )

        r5 = await turn(ws, "هل هي 56 من 165", conv)
        check(results, "U5 إقفال عقدة B", "أحسنت" in r5["text"], r5["text"])

    # record_turn يكتب بعد الإطار النهائي (fail-open، غير حاجز للبثّ) — retry قصير ضد السباق.
    a_state = b_state = None
    for _ in range(10):
        kcp = read_kc_progress(int(conv or 0)) or {}
        a_state = (kcp.get("prob_event_a") or {}).get("state")
        b_state = (kcp.get("prob_event_b") or {}).get("state")
        if a_state == "understood" and b_state == "understood":
            break
        await asyncio.sleep(1)
    check(
        results,
        "DB: آلة الحالات الدائمة تحمل A+B",
        a_state == "understood" and b_state == "understood",
        f"prob_event_a={a_state} prob_event_b={b_state}",
    )

    print("=" * 60)
    if all(results):
        print("✅ D-159 live E2E PASSED — المحرّك متعدد العُقد فوق الحالة الدائمة")
        return 0
    print("❌ D-159 live E2E FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
