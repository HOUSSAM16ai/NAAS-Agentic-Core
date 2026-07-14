#!/usr/bin/env python3.12
"""
D-165 (ISS-129) — Live E2E FULL-STACK: سؤال «غاية التمرين» يُجاب + لا probe-hijack.

يعيد transcript الكارثة الحرفي عبر المكدّس الحقيقي (WS → monolith → cognitive turn →
orchestrator/OpenRouter عند الحاجة) ويُثبت موت الكارثة بنيوياً:

  المستخدم (houssamannaba963):
    T1 «اعطني تمرين الاحتمالات 2024»      → نص التمرين (يدخل history)
    T2 «ماذا نستفيد كن هذا التمرين»        → ⚡ قلب الكارثة (بالـ typo «كن» حرفياً):
         ✅ إجابة الغاية الحتمية (عناوين المكوّنات المعرفية — معنى الحادثة، فضاء العيّنة...)
         ⛔ صفر probe-hijack («لنبدأ من فهمك أنت»)
         ⛔ صفر كشف (14/165)
    T3 «كيف احل السؤال الأول»              → probe تشخيصي (D-155 محفوظ)
    T4 «ما هو قانون نيوتن الثاني؟»          → إجابة حقيقية (ضمانة «يجيب على كل سؤال»
         — D-101 topic-switch + D-112 العمود الفقري؛ يتطلب orchestrator :8006 حيّاً)

التهيئة (من البيئة — لا أسرار في الكود):
    E2E_BACKEND (افتراضي http://localhost:8000) · DIAG_EMAIL / DIAG_PASSWORD ·
    E2E_SKIP_GENERAL=1 لتخطّي T4 حين لا يعمل orchestrator :8006.

Usage:
    set -a && . .devcontainer/secrets.env && set +a
    E2E_BACKEND=http://localhost:8000 DIAG_EMAIL=houssamannaba963@gmail.com \
    DIAG_PASSWORD=1111 python3.12 scripts/verify_iss129_e2e.py
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import uuid

import httpx
import websockets

BACKEND = os.environ.get("E2E_BACKEND", "http://localhost:8000")
EMAIL = os.environ.get("DIAG_EMAIL", "houssamannaba963@gmail.com")
PASSWORD = os.environ.get("DIAG_PASSWORD", "1111")
FULLNAME = "Houssam ISS129 E2E"

#: رسالة الكارثة الحرفية من transcript المالك (بالـ typo «كن»).
_CATASTROPHE_Q = "ماذا نستفيد كن هذا التمرين"
_PROBE_MARK = "لنبدأ من فهمك أنت"

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
    terminal = ""
    while True:
        event = json.loads(await asyncio.wait_for(ws.recv(), timeout=240))
        etype, ep = event.get("type"), (event.get("payload") or {})
        if etype == "conversation_init":
            conv = ep.get("conversation_id") or conv
        elif etype == "assistant_delta":
            parts.append(str(ep.get("content") or ""))
        elif etype in ("assistant_final", "complete", "error", "assistant_error"):
            terminal = etype
            break
    return {"text": "".join(parts), "conversation_id": conv, "terminal": terminal}


async def main() -> None:
    token = await ensure_user()
    ws_url = BACKEND.replace("http", "ws", 1) + f"/api/chat/ws?token={token}"
    async with websockets.connect(ws_url, ping_interval=None, max_size=2**23) as ws:
        # primer (session_ready) — يُتجاهل.
        with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
            await asyncio.wait_for(ws.recv(), timeout=5)

        conv: int | None = None

        t1 = await turn(ws, "اعطني تمرين الاحتمالات 2024", conv)
        conv = t1["conversation_id"]
        _check("T1 exercise retrieved", "كرة" in t1["text"] and len(t1["text"]) > 300)

        # ⚡ T2 — قلب الكارثة الحرفي: سؤال الغاية يُجاب، لا يُختطف بالـ probe.
        t2 = await turn(ws, _CATASTROPHE_Q, conv)
        _check(
            "T2 purpose answered (KC titles)",
            "معنى الحادثة" in t2["text"] and "فضاء العيّنة" in t2["text"],
            t2["text"][:120],
        )
        _check("T2 no probe hijack", _PROBE_MARK not in t2["text"])
        _check(
            "T2 zero leak (no 14/165)",
            "14/165" not in t2["text"] and "14 من 165" not in t2["text"],
        )

        # T3 — D-155 محفوظ: طلب المساعدة الإجرائي يتلقى «التشخيص قبل الشرح».
        t3 = await turn(ws, "كيف احل السؤال الأول", conv)
        _check("T3 kayf gets the diagnostic probe (D-155)", "أيّ الألوان" in t3["text"])

        # T4 — «يجيب على كل سؤال»: سؤال عام وسط محادثة الاحتمالات ⇒ إجابة حقيقية
        # (topic-switch D-101 يمنع الاختطاف؛ D-112 يمرّره للعمود الفقري).
        if os.environ.get("E2E_SKIP_GENERAL", "").strip() not in ("1", "true"):
            t4 = await turn(ws, "ما هو قانون نيوتن الثاني؟", conv)
            _check(
                "T4 general question answered (no hijack, no probe)",
                t4["terminal"] != "error"
                and len(t4["text"]) > 60
                and _PROBE_MARK not in t4["text"]
                and "أيّ الألوان" not in t4["text"],
                f"terminal={t4['terminal']} len={len(t4['text'])}",
            )
        else:
            print("⏭️  T4 skipped (E2E_SKIP_GENERAL=1 — orchestrator :8006 not running)")

    failed = [n for n, ok, _ in _RESULTS if not ok]
    print("\n=== ISS-129 E2E:", "ALL PASS ✅" if not failed else f"FAILED: {failed} ❌", "===")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
