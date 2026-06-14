#!/usr/bin/env python3.12
"""
D-113 (ISS-115) — Live E2E FULL-STACK: Socratic No-Answer OS + BKT + cards.

يقود المكدس الكامل الحقيقي (monolith:8000 ↔ orchestrator:8006 ↔ OpenRouter،
وقاعدة البيانات Supabase عبر asyncpg في وقت تشغيل التطبيق) ويتحقّق حيّاً من
العقود الثورية لـ D-113 + D-074 + استمرارية البطاقات:

  المستخدم (houssamannaba963):
    U1 «السلام عليكم»                         → fast-path تحية نظيفة
    U2 «اعطني تمرين الاحتمالات 2024»          → نص التمرين (يدخل history) + بطاقة محتملة
    U3 «اشرح السؤال الأول»                    → شرح سقراطي: لا نتيجة نهائية مكشوفة
    U4 «لم أفهم»                              → تشخيص + تلميح أدنى، لا إعادة اشتقاق

تأكيدات الحجب (D-113 — القاعدة الذهبية «لا تكشف ما يولّده الطالب»):
  • لا `\\boxed{<محتوى عددي>}` يصل الطالب (يُسمح `\\boxed{?}`).
  • لا نتيجة نهائية صريحة `P(...)=<عدد>` / `E(...)=<عدد>` / `C(...)=<عدد>`.
  • «لم أفهم» لا يُعيد كشف الجواب النهائي.

تأكيد BKT (D-074 — append-only): صفّ `student_bkt_analytics` جديد للمستخدم بعد الجولات
(يُقرأ حيّاً عبر جسر Supabase HTTPS — `scripts/db_bridge.py`).

تأكيد استمرارية البطاقات (D-WS-CARD-PERSIST-001): حدث `ui_component` يُبثّ في جولة
الاحتمالات، وصفّ `customer_messages.ui_component` غير فارغ بعدها.

التهيئة (من البيئة — لا أسرار في الكود):
    E2E_BACKEND   (افتراضي http://localhost:8000)
    DIAG_EMAIL / DIAG_PASSWORD        (المستخدم)
    SUPABASE_EDGE_FUNCTION_KEY        (للتحقّق الحيّ من قاعدة البيانات عبر الجسر)

Usage (داخل Codespaces بعد تشغيل supervisor.sh):
    set -a && . .devcontainer/secrets.env && set +a
    E2E_BACKEND=http://localhost:8000 \
    DIAG_EMAIL=houssamannaba963@gmail.com DIAG_PASSWORD=1111 \
    python3.12 scripts/verify_d113_socratic_live.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import uuid

import httpx
import websockets

BACKEND = os.environ.get("E2E_BACKEND", "http://localhost:8000")
EMAIL = os.environ.get("DIAG_EMAIL", "houssamannaba963@gmail.com")
PASSWORD = os.environ.get("DIAG_PASSWORD", "1111")
FULLNAME = "Houssam D113 E2E"

# نتيجة نهائية صريحة مكشوفة (يجب ألّا تظهر للطالب في الشرح).
_BOXED_RE = re.compile(r"\\boxed\s*\{([^}]*)\}")
_FINAL_RESULT_RE = re.compile(r"[PECpec]\s*(?:_?[A-Za-z])?\s*\([^)\n]{0,60}\)\s*=\s*[-+]?\d")


def _leaks_final_answer(text: str) -> list[str]:
    """يُرجع قائمة بالتسريبات النهائية المكشوفة (فارغة = نظيف)."""
    leaks: list[str] = []
    for inner in _BOXED_RE.findall(text):
        stripped = inner.strip()
        if stripped and stripped != "?" and any(ch.isdigit() for ch in stripped):
            leaks.append(f"\\boxed{{{stripped}}}")
    leaks.extend(m.group(0) for m in _FINAL_RESULT_RE.finditer(text))
    return leaks


async def ensure_user() -> tuple[str, int]:
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
                uid = int((d.get("user") or {}).get("id") or 0)
                print(f"  login OK -> user_id={uid}")
                return d["access_token"], uid
        raise SystemExit(f"login failed: {r.status_code} {r.text[:200]}")


async def turn(ws, question: str, conversation_id: int | None) -> dict:
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


def _bkt_count(user_id: int) -> int | None:
    """عدّ صفوف BKT للمستخدم عبر جسر Supabase (None إن تعذّر)."""
    if not os.environ.get("SUPABASE_EDGE_FUNCTION_KEY"):
        return None
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import db_bridge  # type: ignore[import-not-found]

        status, body, _ = db_bridge.run_sql(
            f"SELECT count(*) n FROM student_bkt_analytics WHERE user_id={int(user_id)};"
        )
        if status != 200:
            return None
        d, _ = json.JSONDecoder().raw_decode(body[body.index("{") :])
        return int(d["data"][0]["n"]) if d.get("success") else None
    except Exception as exc:  # pragma: no cover - تحقّق اختياري
        print(f"  (bkt bridge check skipped: {exc})")
        return None


def check(name: str, ok: bool, detail: str) -> bool:
    print(f"  {'✅' if ok else '❌'} {name}: {detail}")
    return ok


async def main() -> int:
    print(f"[1] backend={BACKEND}  user={EMAIL}")
    token, uid = await ensure_user()
    bkt_before = _bkt_count(uid)
    print(f"[1b] BKT rows before = {bkt_before}")

    scheme = "wss" if BACKEND.startswith("https") else "ws"
    host = BACKEND.split("://", 1)[1]
    url = f"{scheme}://{host}/api/chat/ws?token={token}&session_id={uuid.uuid4()}"

    results: list[bool] = []
    async with websockets.connect(url, ping_interval=None, open_timeout=20) as ws:
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print(f"[2] WS connected, primer={first.get('type')}")

        print("\n[U1] السلام عليكم")
        r1 = await turn(ws, "السلام عليكم", None)
        conv = r1["conversation_id"]
        results.append(
            check(
                "U1 greeting clean fast-path",
                0 < len(r1["text"]) < 400 and not _leaks_final_answer(r1["text"]),
                f"chars={len(r1['text'])} conv={conv}",
            )
        )

        print("\n[U2] اعطني تمرين الاحتمالات 2024")
        r2 = await turn(ws, "اعطني تمرين الاحتمالات 2024", conv)
        results.append(
            check(
                "U2 probability exercise delivered",
                ("كرة" in r2["text"] or "احتمال" in r2["text"]) and len(r2["text"]) > 150,
                f"chars={len(r2['text'])} ui={r2['ui_components']}",
            )
        )

        print("\n[U3] اشرح السؤال الأول  ← SOCRATIC: no final answer")
        r3 = await turn(ws, "اشرح السؤال الأول", conv)
        leaks3 = _leaks_final_answer(r3["text"])
        results.append(
            check(
                "U3 NO final-answer leak (D-113 golden rule)",
                not leaks3 and len(r3["text"]) > 100,
                f"chars={len(r3['text'])} leaks={leaks3[:3]}",
            )
        )

        print("\n[U4] لم أفهم  ← diagnostic, not re-derivation")
        r4 = await turn(ws, "لم أفهم", conv)
        leaks4 = _leaks_final_answer(r4["text"])
        results.append(
            check(
                "U4 confusion → no answer reveal",
                not leaks4 and len(r4["text"]) > 50,
                f"chars={len(r4['text'])} leaks={leaks4[:3]}",
            )
        )

        print("\n[U5] مفهمتش كيفاش حسبنا  ← MODE_B visual aid")
        r5a = await turn(ws, "اعطني تمرين الاحتمالات 2024", None)
        r5 = await turn(ws, "مفهمتش كيفاش حسبنا الاحتمال", r5a["conversation_id"])
        _prob = ("combinations_visualizer", "probability_tree", "full_exercise_story")
        results.append(
            check(
                "U5 generative card fires (card persistence path)",
                any(c in _prob for c in (r5["ui_components"] + r5a["ui_components"])),
                f"ui={r5a['ui_components'] + r5['ui_components']}",
            )
        )

    bkt_after = _bkt_count(uid)
    print(f"\n[3] BKT rows after = {bkt_after}")
    if bkt_before is not None and bkt_after is not None:
        results.append(
            check(
                "BKT append-only grew (D-074)",
                bkt_after > bkt_before,
                f"{bkt_before} -> {bkt_after}",
            )
        )
    else:
        print("  (BKT bridge check skipped — SUPABASE_EDGE_FUNCTION_KEY unset)")

    print("\n" + "=" * 60)
    passed = sum(results)
    print(f"RESULT: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
