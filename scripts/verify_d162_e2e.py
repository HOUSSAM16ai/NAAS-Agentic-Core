#!/usr/bin/env python3.12
"""
D-162 (ISS-128) — Live E2E FULL-STACK: «السؤال ليس إجابة» — بوّابة الفعل الكلامي.

يعيد transcript الكارثة الحرفي عبر المكدّس الحقيقي (WS → monolith → cognitive turn →
OpenRouter عند الحاجة) ويُثبت موت الكارثة بنيوياً:

  المستخدم (houssamannaba963):
    T1 «اعطني تمرين الاحتمالات 2024»        → نص التمرين (يدخل history)
    T2 «كيف افهم قواعد هذا التمرين؟»          → probe تشخيصي (لا انحدار D-155؛
         صياغة «كيف» منذ D-165 — سؤال غير-كيف يهرب لطبقات الإجابة لا للـ probe)
    T3 «الحمراء و الخضراء فقط»               → اعتراف + خطوة البسط (pending=denominator)
    T4 «ماذا نسمي حساب 4 و 10 لم افهمها؟»    → ⚡ قلب الكارثة:
         ✅ يُجيب بالاسم («التوافيق») + يعيد طرح سؤال المقام
         ⛔ صفر «إجابتك في الطريق الصحيح» (الاعتراف الزائف)
         ⛔ صفر كشف 165 (جواب سؤاله المعلّق)
    T5 «165»                                  → اعتراف + خطوة النسبة (الحوار يستأنف)
    T6 «14 على 165»                           → «أحسنت ✅» + الانتقال للحادثة B

التهيئة (من البيئة — لا أسرار في الكود):
    E2E_BACKEND (افتراضي http://localhost:8000) · DIAG_EMAIL / DIAG_PASSWORD ·
    SUPABASE_EDGE_FUNCTION_KEY (اختياري — تحقّق tutor_state عبر جسر HTTPS)

Usage:
    set -a && . .devcontainer/secrets.env && set +a
    E2E_BACKEND=http://localhost:8000 DIAG_EMAIL=houssamannaba963@gmail.com \
    DIAG_PASSWORD=1111 python3.12 scripts/verify_d162_e2e.py
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
EMAIL = os.environ.get("DIAG_EMAIL", "houssamannaba963@gmail.com")
PASSWORD = os.environ.get("DIAG_PASSWORD", "1111")
FULLNAME = "Houssam D162 E2E"

_CATASTROPHE_Q = "ماذا نسمي حساب 4 و 10 لم افهمها؟"

_RESULTS: list[tuple[str, bool, str]] = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    _RESULTS.append((name, ok, detail))
    print(f"{'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else ""))


async def ensure_user() -> str:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{BACKEND}/api/security/login", json={"email": EMAIL, "password": PASSWORD}
        )
        if r.status_code != 200:
            await c.post(
                f"{BACKEND}/api/security/register",
                json={"full_name": FULLNAME, "email": EMAIL, "password": PASSWORD},
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


async def main() -> None:
    token = await ensure_user()
    ws_url = BACKEND.replace("http", "ws", 1) + f"/api/chat/ws?token={token}"
    async with websockets.connect(ws_url, ping_interval=None, max_size=2**23) as ws:
        # primer (session_ready) — يُتجاهل.
        with __import__("contextlib").suppress(TimeoutError, asyncio.TimeoutError):
            await asyncio.wait_for(ws.recv(), timeout=5)

        conv: int | None = None

        t1 = await turn(ws, "اعطني تمرين الاحتمالات 2024", conv)
        conv = t1["conversation_id"]
        _check("T1 exercise retrieved", "كرة" in t1["text"] and len(t1["text"]) > 300)

        # D-165 (ISS-129): سؤال غير-كيف («ما هي قواعد...») لم يعد يُختطف بالـ probe —
        # طلب المساعدة الإجرائي («كيف») هو ما يستحق «التشخيص قبل الشرح» (D-155).
        t2 = await turn(ws, "كيف افهم قواعد هذا التمرين؟", conv)
        _check("T2 diagnostic probe (no dump)", "أيّ الألوان" in t2["text"])

        t3 = await turn(ws, "الحمراء و الخضراء فقط", conv)
        _check("T3 numerator step", "الحالات الملائمة" in t3["text"])

        # ⚡ T4 — قلب الكارثة الحرفي.
        t4 = await turn(ws, _CATASTROPHE_Q, conv)
        _check("T4 names the concept (التوافيق)", "التوافيق" in t4["text"], t4["text"][:120])
        _check(
            "T4 no fake acknowledgment",
            "إجابتك في الطريق الصحيح" not in t4["text"],
        )
        _check("T4 does not reveal 165", "165" not in t4["text"])
        _check(
            "T4 re-asks the pending question",
            "كم عدد كل الطرق الممكنة" in t4["text"],
        )

        t5 = await turn(ws, "165", conv)
        _check(
            "T5 '165' acknowledged (dialogue resumes)",
            "165" in t5["text"] and "الاحتمال" in t5["text"],
        )

        t6 = await turn(ws, "14 على 165", conv)
        _check(
            "T6 final ratio → أحسنت + الحادثة B (no regression)",
            "أحسنت" in t6["text"] and "الحادثة B" in t6["text"],
        )

    failed = [n for n, ok, _ in _RESULTS if not ok]
    print("\n=== D-162 E2E:", "ALL PASS ✅" if not failed else f"FAILED: {failed} ❌", "===")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
