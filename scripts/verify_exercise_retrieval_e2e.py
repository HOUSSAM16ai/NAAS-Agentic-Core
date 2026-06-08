#!/usr/bin/env python3
"""
التحقق الحي E2E لاسترجاع التمارين الثلاثة (الاحتمالات / الأعداد المركبة / الدوال العددية).

ثلاث طبقات تحقّق، كلٌّ مستقلة وتتخطّى نفسها بأمان عند غياب متطلباتها:

  A. مصفوفة التعرّف (recognition) — يثبت أن كل تمرين يُطابِق التمرين الصحيح عبر صياغات
     كثيرة (عربي ±«ال»، ±سنة، فرنسي، إنجليزي). يحتاج تبعيات التطبيق (pydantic).

  B. التحقّق من SQL المُسترجِع مقابل Supabase الحقيقي عبر جسر HTTPS (Edge Function).
     يثبت أن استعلام المُسترجِع الفعلي يُرجِع التمرين الصحيح من قاعدة الإنتاج. stdlib فقط.
     يحتاج: SUPABASE_EDGE_FUNCTION_URL + SUPABASE_EDGE_FUNCTION_KEY.

  C. اختبار WebSocket كامل (Codespaces) — تسجيل دخول → WS → إرسال الطلبات الثلاثة →
     التأكد أن الرد يحوي علامات التمرين الصحيح ولا يحوي علامات الآخرين. يحتاج التطبيق
     قيد التشغيل (E2E_BACKEND) + websockets + httpx.

أمثلة:
    python3 scripts/verify_exercise_retrieval_e2e.py                 # A + B
    set -a && . .devcontainer/secrets.env && set +a && python3 scripts/verify_exercise_retrieval_e2e.py
    E2E_BACKEND=http://localhost:8000 E2E_EMAIL=... E2E_PASSWORD=... python3 scripts/verify_exercise_retrieval_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request

# تشغيل السكربت مباشرةً يضع scripts/ في sys.path[0] لا جذر المشروع → أضف الجذر
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─────────────────────────────────────────────────────────────────────────────
# العلامات المميِّزة لكل تمرين (للتأكيد على الرد المتدفق في الطبقة C)
# ─────────────────────────────────────────────────────────────────────────────
EXERCISE_MARKERS: dict[str, dict[str, object]] = {
    "complex": {
        "query": "أعطني تمرين الأعداد المركبة 2024",
        "must_contain_any": ["الأعداد المركبة", "\\mathbb{C}", "z_A", "الشكل المثلثي"],
        "must_not_contain": ["كرة متماثلة", "11 كرة"],
        "expected_topic": "Complex Numbers",
        "expected_exercise_number": 2,
    },
    "probability": {
        "query": "أعطني تمرين الاحتمالات 2024",
        "must_contain_any": ["الاحتمالات", "11 كرة", "P(A)", "كرة"],
        "must_not_contain": ["الأعداد المركبة", "\\mathbb{C}"],
        "expected_topic": "Probability",
        "expected_exercise_number": 1,
    },
    "numerical": {
        "query": "اعطني تمرين الدوال العددية 2016",
        "must_contain_any": ["الدوال العددية", "g(x)", "g\\(x\\)", "جدول التغيرات", "الدالة g"],
        "must_not_contain": ["الأعداد المركبة", "كرة متماثلة"],
        "expected_topic": "Numerical Functions",
        "expected_exercise_number": 4,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# الطبقة A: مصفوفة التعرّف
# ─────────────────────────────────────────────────────────────────────────────
def layer_a_recognition() -> bool | None:
    try:
        from app.services.capabilities.exercise_retrieval import (
            ExerciseRetrievalRequest,
            detect_exercise_retrieval,
        )
    except Exception as exc:
        print(f"[A] SKIP recognition matrix (app deps unavailable: {exc})")
        return None

    cases = [
        ("أعطني تمرين الأعداد المركبة 2024", 2),
        ("اعطني تمرين الأعداد المركبة", 2),
        ("اعطني تمرين أعداد مركبة 2024", 2),
        ("complex numbers exercise 2024", 2),
        ("nombres complexes 2024", 2),
        ("تمرين الاحتمالات 2024", 1),
        ("أعطني تمرين الاحتمالات", 1),
        ("اعطني تمرين الدوال العددية 2016", 4),
        ("تمرين الدوال العددية", 4),
        ("numerical functions exercise", 4),
    ]
    ok = True
    print("[A] Recognition matrix (definite article + phrasings):")
    for query, expected in cases:
        d = detect_exercise_retrieval(ExerciseRetrievalRequest(question=query))
        got = d.matched_entry.exercise_number if d.matched_entry else None
        status = "PASS" if (d.recognized and got == expected) else "FAIL"
        ok = ok and status == "PASS"
        print(f"    [{status}] {query!r:42} ex#={got} (expect {expected})")
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# الطبقة B: SQL المُسترجِع مقابل Supabase الحقيقي عبر الجسر
# ─────────────────────────────────────────────────────────────────────────────
def _bridge_run(sql: str) -> dict:
    url = os.environ.get(
        "SUPABASE_EDGE_FUNCTION_URL",
        "https://aocnuqhxrhxgbfcgbxfy.supabase.co/functions/v1/claude-admin",
    )
    key = os.environ.get("SUPABASE_EDGE_FUNCTION_KEY")
    if not key:
        raise RuntimeError("SUPABASE_EDGE_FUNCTION_KEY not set")
    body = json.dumps({"sql_query": sql}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _to_literal(sql: str, params: dict) -> str:
    out = sql
    for k in sorted(params, key=len, reverse=True):
        v = params[k]
        lit = str(v) if isinstance(v, int) else "'" + str(v).replace("'", "''") + "'"
        out = out.replace(":" + k, lit)
    return out


def layer_b_supabase_sql() -> bool | None:
    if not os.environ.get("SUPABASE_EDGE_FUNCTION_KEY"):
        print("[B] SKIP Supabase SQL verification (SUPABASE_EDGE_FUNCTION_KEY not set)")
        return None
    try:
        from app.services.capabilities.bac_db_retriever import (
            build_candidate_query,
            extract_db_facets,
        )
    except Exception as exc:
        print(f"[B] SKIP Supabase SQL verification (app deps unavailable: {exc})")
        return None

    print("[B] Retriever SQL vs REAL Supabase (via HTTPS bridge):")
    ok = True
    for name, spec in EXERCISE_MARKERS.items():
        facets = extract_db_facets(str(spec["query"]))
        sql, params = build_candidate_query(facets)
        sql = sql.replace(
            "SELECT id, subject, topic, year, session, exam_ref, exercise_number, raw_text",
            "SELECT topic, year, exercise_number",
        )
        try:
            res = _bridge_run(_to_literal(sql, params))
        except Exception as exc:
            print(f"    [FAIL] {name}: bridge error {exc}")
            ok = False
            continue
        rows = res.get("data", []) if res.get("success") else []
        hit = any(
            r.get("topic") == spec["expected_topic"]
            and r.get("exercise_number") == spec["expected_exercise_number"]
            for r in rows
        )
        ok = ok and hit
        print(
            f"    [{'PASS' if hit else 'FAIL'}] {name:12} -> "
            f"{[(r.get('topic'), r.get('exercise_number')) for r in rows]}"
        )
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# الطبقة C: WebSocket كامل (Codespaces — التطبيق قيد التشغيل)
# ─────────────────────────────────────────────────────────────────────────────
async def _ws_one(backend_ws: str, token: str, query: str) -> str:
    from websockets.asyncio.client import connect  # type: ignore

    sep = "&" if "?" in backend_ws else "?"
    url = f"{backend_ws}{sep}token={token}"
    chunks: list[str] = []
    async with connect(url, subprotocols=["jwt", token], ping_interval=None) as ws:
        await ws.send(json.dumps({"question": query}))
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=90)
            event = json.loads(raw)
            payload = event.get("payload") or event
            etype = event.get("type")
            if etype == "assistant_delta":
                chunks.append(str(payload.get("content", "")))
            elif etype in ("assistant_final", "complete", "error", "stream_end"):
                break
    return "".join(chunks)


def layer_c_websocket() -> bool | None:
    backend = os.environ.get("E2E_BACKEND")
    email = os.environ.get("E2E_EMAIL", "houssamannaba963@gmail.com")
    password = os.environ.get("E2E_PASSWORD", "1111")
    if not backend:
        print("[C] SKIP WebSocket E2E (set E2E_BACKEND=http://localhost:8000 to run — Codespaces)")
        return None
    try:
        import httpx  # type: ignore
        import websockets  # type: ignore  # noqa: F401
    except Exception as exc:
        print(f"[C] SKIP WebSocket E2E (httpx/websockets unavailable: {exc})")
        return None

    import httpx  # type: ignore

    print("[C] Full WebSocket E2E (live app):")
    try:
        login = httpx.post(
            f"{backend}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=30,
        )
        token = (login.json() or {}).get("access_token")
        if not token:
            print(f"    [FAIL] login returned no token: {login.status_code}")
            return False
    except Exception as exc:
        print(f"    [FAIL] login error: {exc}")
        return False

    ws_base = backend.replace("http://", "ws://").replace("https://", "wss://") + "/api/chat/ws"
    ok = True
    for name, spec in EXERCISE_MARKERS.items():
        try:
            text = asyncio.run(_ws_one(ws_base, token, str(spec["query"])))
        except Exception as exc:
            print(f"    [FAIL] {name}: WS error {exc}")
            ok = False
            continue
        has_any = any(m in text for m in spec["must_contain_any"])  # type: ignore[operator]
        has_forbidden = any(m in text for m in spec["must_not_contain"])  # type: ignore[operator]
        good = has_any and not has_forbidden and len(text) > 40
        ok = ok and good
        print(
            f"    [{'PASS' if good else 'FAIL'}] {name:12} chars={len(text)} "
            f"contains_expected={has_any} contains_forbidden={has_forbidden}"
        )
    return ok


def main() -> int:
    print("=" * 78)
    print("E2E VERIFICATION — BAC Exercise Retrieval (3 exercises, billions-ready)")
    print("=" * 78)
    results = {
        "A_recognition": layer_a_recognition(),
        "B_supabase_sql": layer_b_supabase_sql(),
        "C_websocket": layer_c_websocket(),
    }
    print("-" * 78)
    ran = {k: v for k, v in results.items() if v is not None}
    for k, v in results.items():
        label = "PASS" if v is True else ("FAIL" if v is False else "SKIP")
        print(f"  {k:18} {label}")
    print("=" * 78)
    if any(v is False for v in results.values()):
        return 1
    if not ran:
        print("No layer could run in this environment.")
        return 2
    print("All runnable layers PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
