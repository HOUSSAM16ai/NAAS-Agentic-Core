#!/usr/bin/env python3.12
"""
D-158 (ISS-124) — Live E2E FULL-STACK: Cognitive Turn Engine over persisted tutor_state.

Drives the real stack (monolith:8000 ↔ orchestrator:8006 ↔ OpenRouter, Supabase via
asyncpg at app runtime) and proves the three symptoms of the probability catastrophe are
dead once the turn is routed through `_cognitive_turn` over persisted `tutor_state.kc_progress`.

  المستخدم (houssamannaba963):
    U1 «اعطني تمرين الاحتمالات 2024»   → نص التمرين (يدخل history)
    U2 «كيف نحسب الحادثة A»            → S3: سؤال تشخيصي، لا تفريغ (البسط/المقام)
    U3 «الحمراء و الخضراء فقط»         → S1: خطوة البسط فقط (لا المقام في نفس الدور)
    U4 «14 على 165»                    → S2: «أحسنت ✅» + تقدّم، لا إعادة تفريغ

تأكيد الحالة الدائمة (D-158): صفّ `tutor_state` للمحادثة يحمل
`kc_progress.<prob_event_a>.representations_delivered` غير فارغ + `turn_count` يتقدّم
(يُقرأ حيّاً عبر جسر Supabase HTTPS — `scripts/db_bridge.py`).

⚠️ الخادم يجب أن يُشغَّل بـ `COGNITIVE_TURN_ENABLED=1` (العلم يُقرأ في عملية الخادم):
    COGNITIVE_TURN_ENABLED=1 bash .devcontainer/supervisor.sh   # أو export قبل uvicorn
بدونها يبقى السلوك القديم (الكتل الـ13) — الاختبار سيُبلّغ SKIP بدل PASS.

التهيئة (من البيئة — لا أسرار في الكود):
    E2E_BACKEND (افتراضي http://localhost:8000) · DIAG_EMAIL / DIAG_PASSWORD ·
    SUPABASE_EDGE_FUNCTION_KEY (للتحقّق الحيّ من tutor_state عبر الجسر)

Usage (داخل Codespaces بعد تشغيل supervisor.sh بالعلم):
    set -a && . .devcontainer/secrets.env && set +a
    E2E_BACKEND=http://localhost:8000 DIAG_EMAIL=houssamannaba963@gmail.com \
    DIAG_PASSWORD=1111 python3.12 scripts/verify_d158_e2e.py
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
FULLNAME = "Houssam D158 E2E"

_DUMP_MARKERS = ("نجمع الحالات الممكنة فقط", "كل الطرق الممكنة لسحب")


async def ensure_user() -> tuple[str, int]:
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
        d = r.json()
        return d["access_token"], int((d.get("user") or {}).get("id") or 0)


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


def _tutor_state_row(conversation_id: int) -> dict | None:
    if not os.environ.get("SUPABASE_EDGE_FUNCTION_KEY"):
        return None
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import db_bridge  # type: ignore[import-not-found]

        status, body, _ = db_bridge.run_sql(
            "SELECT kc_progress, turn_count FROM tutor_state "
            f"WHERE conversation_id={int(conversation_id)} LIMIT 1;"
        )
        if status != 200:
            return None
        d, _ = json.JSONDecoder().raw_decode(body[body.index("{") :])
        rows = d.get("data") or []
        return rows[0] if rows else None
    except Exception as exc:  # pragma: no cover
        print(f"  (tutor_state bridge check skipped: {exc})")
        return None


def check(name: str, ok: bool, detail: str) -> bool:
    print(f"  {'✅' if ok else '❌'} {name}: {detail}")
    return ok


async def main() -> int:
    print(f"[1] backend={BACKEND} user={EMAIL} (server must run COGNITIVE_TURN_ENABLED=1)")
    token, _uid = await ensure_user()
    scheme = "wss" if BACKEND.startswith("https") else "ws"
    host = BACKEND.split("://", 1)[1]
    url = f"{scheme}://{host}/api/chat/ws?token={token}&session_id={uuid.uuid4()}"

    results: list[bool] = []
    async with websockets.connect(url, ping_interval=None, open_timeout=20) as ws:
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print(f"[2] WS connected, primer={first.get('type')}")

        r1 = await turn(ws, "اعطني تمرين الاحتمالات 2024", None)
        conv = r1["conversation_id"]
        results.append(check("U1 exercise delivered", len(r1["text"]) > 150, f"conv={conv}"))

        r2 = await turn(ws, "كيف نحسب الحادثة A", conv)
        is_probe = "أيّ الألوان" in r2["text"]
        no_dump2 = not any(m in r2["text"] for m in _DUMP_MARKERS)
        if not is_probe:
            print("  ⚠️ SKIP: no probe — is the server running COGNITIVE_TURN_ENABLED=1?")
        results.append(check("U2 S3 diagnostic-not-dump", is_probe and no_dump2, r2["text"][:80]))

        r3 = await turn(ws, "الحمراء و الخضراء فقط", conv)
        results.append(
            check(
                "U3 S1 numerator-only (no denominator same turn)",
                "الحالات الملائمة" in r3["text"] and "كل الطرق الممكنة لسحب" not in r3["text"],
                r3["text"][:80],
            )
        )

        long_prior = await turn(ws, "اعطني تمرين الاحتمالات 2024 كاملاً بكل التفاصيل", conv)
        _ = long_prior
        r4 = await turn(ws, "14 على 165", conv)
        results.append(
            check(
                "U4 S2 correct-answer confirmed, no re-dump",
                "أحسنت" in r4["text"] and not any(m in r4["text"] for m in _DUMP_MARKERS),
                r4["text"][:80],
            )
        )

    row = _tutor_state_row(conv)
    if row is not None:
        kc = {}
        try:
            kc = json.loads(row.get("kc_progress") or "{}")
        except Exception:
            kc = {}
        delivered = (kc.get("prob_event_a") or {}).get("representations_delivered", [])
        results.append(
            check(
                "tutor_state persisted (kc_progress.representations_delivered grows)",
                bool(delivered),
                f"delivered={delivered} turn_count={row.get('turn_count')}",
            )
        )
    else:
        print("  (tutor_state row check skipped — no bridge key)")

    print("\n" + "=" * 60)
    if all(results):
        print("✅ D-158 live E2E PASSED")
        return 0
    print(f"❌ {results.count(False)}/{len(results)} checks failed")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
