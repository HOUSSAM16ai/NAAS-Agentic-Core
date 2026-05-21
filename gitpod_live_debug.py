"""
اختبار حي لتشخيص الأخطاء الأربعة الحرجة في CogniForge.

يتصل بـ:
  - Supabase (PostgreSQL) مباشرة للتحقق من بيانات المستخدم
  - OpenRouter API لاختبار نموذج اللغة
  - الـ monolith (localhost:8000) لمحاكاة تسلسل المحادثة الكامل

تسلسل الاختبار:
  1. "اعطني تمرين الاحتمالات 2024"
  2. "اسئلة الاحتمالات فقط"
  3. "اعطني شجرة الاحتمالات"
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
from typing import Any

import httpx

# ─── إعداد المسار ────────────────────────────────────────────────────────────
sys.path.insert(0, "/workspaces/NAAS-Agentic-Core")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", os.environ.get("APP_DATABASE_URL", ""))
MONOLITH_BASE = "http://localhost:8000"

STUDENT_EMAIL = "houssamannaba963@gmail.com"
STUDENT_PIN = "1111"

CONVERSATION_SEQUENCE = [
    "اعطني تمرين الاحتمالات 2024",
    "اسئلة الاحتمالات فقط",
    "اعطني شجرة الاحتمالات",
]

SEP = "─" * 70


def _hdr(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


# ─── 1. فحص الاتصال بقاعدة البيانات ─────────────────────────────────────────

async def check_database() -> dict[str, Any]:
    _hdr("1. DATABASE CONNECTION (Supabase)")
    result: dict[str, Any] = {"ok": False}
    try:
        import asyncpg  # type: ignore[import]

        # تحويل URL لـ asyncpg (بدون sslmode في query string)
        url = DATABASE_URL
        if "sslmode=require" in url:
            url = url.replace("?sslmode=require", "").replace("&sslmode=require", "")
        # تحويل postgresql:// → postgres://
        url = url.replace("postgresql://", "postgres://", 1)
        # تحويل port 6543 → 5432 لـ asyncpg
        url = url.replace(":6543/", ":5432/")

        print(f"  Connecting to: {url[:60]}...")
        conn = await asyncpg.connect(url, ssl="require", statement_cache_size=0)
        row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM users WHERE email = $1", STUDENT_EMAIL)
        count = row["cnt"] if row else 0
        print(f"  ✅ Connected. Student account found: {count > 0} (email={STUDENT_EMAIL})")
        result = {"ok": True, "student_found": count > 0}
        await conn.close()
    except ImportError:
        print("  ⚠️  asyncpg not installed — skipping direct DB check")
        result = {"ok": True, "skipped": "asyncpg_not_installed"}
    except Exception as exc:
        print(f"  ❌ DB connection failed: {exc}")
        traceback.print_exc()
        result = {"ok": False, "error": str(exc)}
    return result


# ─── 2. فحص OpenRouter API مباشرة ────────────────────────────────────────────

async def check_openrouter() -> dict[str, Any]:
    _hdr("2. OPENROUTER API (direct)")
    result: dict[str, Any] = {"ok": False}
    if not OPENROUTER_API_KEY:
        print("  ❌ OPENROUTER_API_KEY not set in environment")
        return result
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openai/gpt-oss-20b:free",
                    "messages": [{"role": "user", "content": "قل: مرحبا"}],
                    "max_tokens": 30,
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            print(f"  ✅ OpenRouter OK. Model response: {content[:80]!r}")
            result = {"ok": True, "response": content}
    except Exception as exc:
        print(f"  ❌ OpenRouter failed: {exc}")
        traceback.print_exc()
        result = {"ok": False, "error": str(exc)}
    return result


# ─── 3. تسجيل الدخول عبر الـ monolith ───────────────────────────────────────

async def login_student(client: httpx.AsyncClient) -> str | None:
    _hdr("3. STUDENT LOGIN (monolith :8000)")
    try:
        resp = await client.post(
            f"{MONOLITH_BASE}/api/auth/login",
            json={"email": STUDENT_EMAIL, "pin": STUDENT_PIN},
            timeout=10.0,
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token") or resp.json().get("token")
            print(f"  ✅ Login OK. Token: {str(token)[:40]}...")
            return token
        else:
            print(f"  ❌ Login failed: HTTP {resp.status_code} — {resp.text[:200]}")
            return None
    except Exception as exc:
        print(f"  ❌ Login exception: {exc}")
        traceback.print_exc()
        return None


# ─── 4. إنشاء محادثة جديدة ───────────────────────────────────────────────────

async def create_conversation(client: httpx.AsyncClient, token: str) -> int | None:
    _hdr("4. CREATE CONVERSATION")
    try:
        resp = await client.post(
            f"{MONOLITH_BASE}/api/conversations",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "Debug Session — Live Test"},
            timeout=10.0,
        )
        if resp.status_code in (200, 201):
            conv_id = resp.json().get("id") or resp.json().get("conversation_id")
            print(f"  ✅ Conversation created: id={conv_id}")
            return int(conv_id)
        else:
            print(f"  ❌ Create conversation failed: HTTP {resp.status_code} — {resp.text[:200]}")
            return None
    except Exception as exc:
        print(f"  ❌ Create conversation exception: {exc}")
        traceback.print_exc()
        return None


# ─── 5. إرسال رسالة عبر HTTP (لاكتشاف الأخطاء الخلفية) ─────────────────────

async def send_message_http(
    client: httpx.AsyncClient,
    token: str,
    conversation_id: int,
    question: str,
    turn: int,
) -> dict[str, Any]:
    """
    يرسل رسالة عبر HTTP POST ويلتقط أي استجابة خطأ خام.
    هذا يكشف عن Bug A: الـ backend crash الذي يُسبب Next.js HTML bleed.
    """
    print(f"\n  [Turn {turn}] Question: {question!r}")
    result: dict[str, Any] = {"turn": turn, "question": question}

    try:
        resp = await client.post(
            f"{MONOLITH_BASE}/api/chat/messages",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "question": question,
                "conversation_id": conversation_id,
            },
            timeout=60.0,
        )

        status = resp.status_code
        content_type = resp.headers.get("content-type", "")
        raw_body = resp.text[:500]

        print(f"  HTTP {status} | Content-Type: {content_type}")

        if "text/html" in content_type or raw_body.strip().startswith("<!DOCTYPE"):
            print(f"  🚨 BUG A CONFIRMED: Backend returned HTML instead of JSON!")
            print(f"  HTML preview: {raw_body[:300]}")
            result["bug_a"] = True
            result["html_response"] = raw_body[:300]
        elif status >= 500:
            print(f"  🚨 SERVER ERROR {status}: {raw_body[:300]}")
            result["server_error"] = raw_body[:300]
        elif status == 200:
            try:
                data = resp.json()
                answer = (
                    data.get("response")
                    or data.get("content")
                    or data.get("message")
                    or str(data)[:200]
                )
                print(f"  ✅ Response ({len(answer)} chars): {answer[:200]!r}")
                result["ok"] = True
                result["response"] = answer
            except Exception:
                print(f"  ⚠️  Non-JSON 200 response: {raw_body[:200]}")
                result["raw"] = raw_body[:200]
        else:
            print(f"  ⚠️  Unexpected status {status}: {raw_body[:200]}")
            result["unexpected"] = raw_body[:200]

    except httpx.ReadTimeout:
        print(f"  ⏱️  Timeout after 60s — backend may be hanging")
        result["timeout"] = True
    except Exception as exc:
        print(f"  ❌ Exception: {exc}")
        traceback.print_exc()
        result["error"] = str(exc)

    return result


# ─── 6. اختبار الـ fallback chain مباشرة ────────────────────────────────────

async def test_fallback_chain_directly() -> None:
    """
    يختبر الـ fallback chain مباشرة بدون HTTP لاكتشاف الأخطاء الداخلية.
    يكشف عن:
      - Bug B: RAG semantic blindness (كلا التمرينين يُعادان)
      - Bug C: LangGraph amnesia (history لا يُمرَّر)
      - Bug D: abstract labels في شجرة الاحتمالات
    """
    _hdr("6. DIRECT FALLBACK CHAIN TESTS (in-process)")

    # ── Bug B: اختبار semantic boundary slicing ──────────────────────────────
    print("\n  [Bug B] Testing RAG semantic boundary slicing...")
    try:
        from app.services.capabilities.exercise_retrieval import (
            ExerciseRetrievalRequest,
            detect_exercise_retrieval,
            format_exercise_for_display,
            load_exercise_content,
        )

        req = ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024")
        decision = detect_exercise_retrieval(req)
        print(f"  Decision: recognized={decision.recognized}, reason={decision.reason}")
        if decision.matched_entry:
            entry = decision.matched_entry
            print(f"  Matched entry: exercise_number={entry.exercise_number}, topics={entry.topics}")
            raw = load_exercise_content(entry)
            if raw:
                formatted = format_exercise_for_display(entry, raw)
                # Bug B: هل يحتوي الرد على كلا التمرينين؟
                has_ex1 = "التمرين الأول" in formatted
                has_ex2 = "التمرين الثاني" in formatted
                if has_ex1 and has_ex2:
                    print(f"  🚨 BUG B CONFIRMED: Both exercises returned! (ex1={has_ex1}, ex2={has_ex2})")
                    print(f"  Formatted length: {len(formatted)} chars")
                    # عرض بداية التمرين الثاني لتأكيد التسرب
                    idx = formatted.find("التمرين الثاني")
                    if idx != -1:
                        print(f"  Ex2 leaks at char {idx}: {formatted[idx:idx+100]!r}")
                else:
                    print(f"  ✅ Bug B NOT present: ex1={has_ex1}, ex2={has_ex2}")
                    print(f"  Formatted length: {len(formatted)} chars")
    except Exception as exc:
        print(f"  ❌ Bug B test failed: {exc}")
        traceback.print_exc()

    # ── Bug C: اختبار LangGraph history passing ──────────────────────────────
    print("\n  [Bug C] Testing LangGraph history passing...")
    try:
        from app.services.capabilities.exercise_retrieval import (
            ExerciseRetrievalRequest,
            detect_exercise_retrieval,
        )

        # محاكاة سؤال متابعة بدون ذكر الموضوع
        follow_up = "اسئلة الاحتمالات فقط"
        req2 = ExerciseRetrievalRequest(question=follow_up)
        decision2 = detect_exercise_retrieval(req2)
        print(f"  Follow-up '{follow_up}': recognized={decision2.recognized}, reason={decision2.reason}")

        # اختبار _classify_intent مع history
        from app.services.chat.local_graph import _classify_intent, _format_history

        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
            {"role": "assistant", "content": "إليك تمرين الاحتمالات..."},
        ]
        history_text = _format_history(history)
        intent_no_history = _classify_intent(follow_up)
        print(f"  Intent without history: {intent_no_history!r}")
        print(f"  History text generated: {len(history_text)} chars")
        if not history_text:
            print(f"  🚨 BUG C INDICATOR: _format_history returned empty for non-empty history!")
        else:
            print(f"  ✅ History text: {history_text[:100]!r}")

    except Exception as exc:
        print(f"  ❌ Bug C test failed: {exc}")
        traceback.print_exc()

    # ── Bug D: اختبار abstract labels في شجرة الاحتمالات ────────────────────
    print("\n  [Bug D] Testing probability tree label extraction (Abstraction Ban)...")
    try:
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        # سؤال من تمرين الاحتمالات 2024 (كرات ملونة)
        question_with_context = (
            "اعطني شجرة الاحتمالات — يحتوي كيس على كرات حمراء وبيضاء وخضراء"
        )
        props = OrchestratorClient._detect_probability_tree(question_with_context)
        if props:
            tree = props.get("tree", {})
            children = tree.get("children", [])
            labels_generic = props.get("labels_generic", False)
            if children:
                first_label = children[0].get("label", "")
                print(f"  First branch label: {first_label!r}")
                print(f"  labels_generic flag: {labels_generic}")
                abstract_banned = {"a", "b", "ā", "b̄", "a'", "b'"}
                if first_label.lower() in abstract_banned:
                    print(f"  🚨 BUG D CONFIRMED: Abstract label {first_label!r} in tree!")
                elif first_label in ("الحدث الأول", "الحدث الثاني"):
                    print(f"  ⚠️  BUG D PARTIAL: Generic fallback label {first_label!r} — LLM enrichment needed")
                else:
                    print(f"  ✅ Concrete label extracted: {first_label!r}")
        else:
            print(f"  ⚠️  No tree detected for question with explicit context")

        # سؤال بدون كيانات ملموسة (يجب أن يُطلق LLM enrichment)
        question_abstract = "اعطني شجرة الاحتمالات للتمرين"
        props2 = OrchestratorClient._detect_probability_tree(question_abstract)
        if props2:
            labels_generic2 = props2.get("labels_generic", False)
            tree2 = props2.get("tree", {})
            children2 = tree2.get("children", [])
            first_label2 = children2[0].get("label", "") if children2 else ""
            print(f"\n  Abstract question tree:")
            print(f"  labels_generic={labels_generic2}, first_label={first_label2!r}")
            if first_label2 in ("الحدث الأول",) and labels_generic2:
                print(f"  ✅ Correct: generic fallback used, LLM enrichment will be triggered")
            elif first_label2.lower() in {"a", "b"}:
                print(f"  🚨 BUG D CONFIRMED: Abstract symbol {first_label2!r} leaked!")
        else:
            print(f"  ⚠️  No tree detected for abstract question (no probability values)")

    except Exception as exc:
        print(f"  ❌ Bug D test failed: {exc}")
        traceback.print_exc()


# ─── 7. اختبار WebSocket (يكشف Bug A بشكل مباشر) ────────────────────────────

async def test_websocket_crash(token: str, conversation_id: int) -> None:
    """
    يتصل بـ WebSocket ويرسل تسلسل المحادثة الكامل.
    يلتقط أي استثناء خلفي يُسبب Next.js HTML bleed.
    """
    _hdr("7. WEBSOCKET CONVERSATION SEQUENCE (Bug A probe)")
    try:
        import websockets  # type: ignore[import]
    except ImportError:
        print("  ⚠️  websockets not installed — using HTTP fallback for Bug A probe")
        return

    ws_url = f"ws://localhost:8000/api/chat/ws?token={token}"
    print(f"  Connecting to: {ws_url[:60]}...")

    history: list[dict[str, str]] = []
    for i, question in enumerate(CONVERSATION_SEQUENCE, 1):
        print(f"\n  [Turn {i}] Sending: {question!r}")
        try:
            async with websockets.connect(ws_url, ping_interval=None) as ws:  # type: ignore[attr-defined]
                payload = {
                    "question": question,
                    "conversation_id": conversation_id,
                    "history_messages": history,
                }
                await ws.send(json.dumps(payload))

                chunks: list[str] = []
                error_detected = False
                final_received = False

                async for raw_msg in ws:
                    try:
                        msg = json.loads(raw_msg)
                    except json.JSONDecodeError:
                        # Bug A: HTML bleed — raw HTML instead of JSON
                        if raw_msg.strip().startswith("<!DOCTYPE") or "<html" in raw_msg:
                            print(f"  🚨 BUG A CONFIRMED via WebSocket: HTML received!")
                            print(f"  HTML preview: {raw_msg[:300]}")
                            error_detected = True
                            break
                        print(f"  ⚠️  Non-JSON WS message: {raw_msg[:100]}")
                        continue

                    msg_type = msg.get("type", "")

                    if msg_type == "assistant_delta":
                        chunk = msg.get("payload", {}).get("content", "")
                        chunks.append(chunk)
                    elif msg_type == "assistant_final":
                        final_received = True
                        break
                    elif msg_type in ("assistant_error", "error"):
                        payload_content = msg.get("payload", {})
                        print(f"  🚨 ERROR EVENT: {json.dumps(payload_content)[:200]}")
                        error_detected = True
                        break
                    elif msg_type == "ui_component":
                        component = msg.get("payload", {}).get("component", "")
                        props = msg.get("payload", {}).get("props", {})
                        print(f"  🎨 UI Component: {component}")
                        if component == "probability_tree":
                            tree = props.get("tree", {})
                            children = tree.get("children", [])
                            if children:
                                label = children[0].get("label", "")
                                print(f"     First branch label: {label!r}")
                                if label.lower() in {"a", "b"}:
                                    print(f"  🚨 BUG D CONFIRMED in live WS: abstract label {label!r}")
                                elif label in ("الحدث الأول",):
                                    print(f"  ⚠️  BUG D PARTIAL: generic fallback {label!r}")
                                else:
                                    print(f"  ✅ Concrete label: {label!r}")

                full_response = "".join(chunks)
                if not error_detected:
                    print(f"  ✅ Turn {i} OK: {len(full_response)} chars, final={final_received}")
                    print(f"  Preview: {full_response[:150]!r}")

                    # Bug B check: كلا التمرينين في رد واحد؟
                    if "التمرين الأول" in full_response and "التمرين الثاني" in full_response:
                        print(f"  🚨 BUG B CONFIRMED in live WS: Both exercises in response!")

                    # Bug C check: هل الرد يتجاهل السياق؟
                    if i > 1 and "التمرين الأول" in full_response and "التمرين الثاني" in full_response:
                        print(f"  🚨 BUG C INDICATOR: Follow-up dumped full document again!")

                    history.append({"role": "user", "content": question})
                    history.append({"role": "assistant", "content": full_response})

        except Exception as exc:
            print(f"  ❌ WS Turn {i} exception: {type(exc).__name__}: {exc}")
            traceback.print_exc()


# ─── 8. اختبار الـ backend crash مباشرة (Bug A) ──────────────────────────────

async def test_backend_crash_directly() -> None:
    """
    يستدعي الـ fallback chain مباشرة لاكتشاف الـ exception الذي يُسبب 500.
    """
    _hdr("8. DIRECT BACKEND CRASH PROBE (Bug A)")
    try:
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        client = OrchestratorClient()

        print("  Testing: 'اعطني شجرة الاحتمالات' via chat_with_agent...")
        events: list[dict] = []
        exception_caught: Exception | None = None

        try:
            async for event in client.chat_with_agent(
                question="اعطني شجرة الاحتمالات",
                user_id=1,
                conversation_id=999,
                history_messages=[
                    {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
                    {"role": "assistant", "content": "إليك تمرين الاحتمالات..."},
                ],
            ):
                events.append(event)
                if event.get("type") == "assistant_final":
                    break
                if len(events) > 200:
                    print("  ⚠️  Too many events, stopping")
                    break
        except Exception as exc:
            exception_caught = exc
            print(f"  🚨 BUG A EXCEPTION CAUGHT: {type(exc).__name__}: {exc}")
            traceback.print_exc()

        if exception_caught is None:
            print(f"  ✅ No exception. Events received: {len(events)}")
            for ev in events[:5]:
                print(f"    {ev.get('type')}: {str(ev.get('payload', {}))[:80]}")

    except Exception as exc:
        print(f"  ❌ Direct crash probe failed: {exc}")
        traceback.print_exc()


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("\n" + "═" * 70)
    print("  CogniForge Live Debug — 4 Fatal Bugs Diagnostic")
    print("  Environment: Gitpod | Date: 2026-05-21")
    print("═" * 70)

    # 1. DB check
    await check_database()

    # 2. OpenRouter check
    await check_openrouter()

    # 3-5. HTTP conversation sequence
    _hdr("5. HTTP CONVERSATION SEQUENCE (Bug A probe)")
    async with httpx.AsyncClient() as http_client:
        token = await login_student(http_client)
        if token:
            conv_id = await create_conversation(http_client, token)
            if conv_id:
                for i, question in enumerate(CONVERSATION_SEQUENCE, 1):
                    await send_message_http(http_client, token, conv_id, question, i)
            else:
                print("  ⚠️  Skipping HTTP turns — no conversation created")
        else:
            print("  ⚠️  Skipping HTTP turns — login failed")

    # 6. Direct in-process tests
    await test_fallback_chain_directly()

    # 7. WebSocket test
    if token and conv_id:  # type: ignore[possibly-undefined]
        await test_websocket_crash(token, conv_id)  # type: ignore[possibly-undefined]

    # 8. Direct backend crash probe
    await test_backend_crash_directly()

    _hdr("SUMMARY")
    print("  Diagnostic complete. Review 🚨 markers above for confirmed bugs.")
    print("  ✅ = working correctly")
    print("  🚨 = bug confirmed")
    print("  ⚠️  = partial / needs investigation")
    print()


if __name__ == "__main__":
    asyncio.run(main())
