#!/usr/bin/env python3
"""verify_d185_notation_live — تحقّق حيّ من إغلاق كارثة «الرمز غير المُعرَّف» (D-185/ISS-138).

يُعيد تمثيل ترانسكريبت الطالب الحقيقي **حرفيّاً** على نظام حيّ، ويؤكّد أنّ الدور الرابع
(«ماذا نقصد بحرف C») صار يُجاب بتعريف بدل إعادة الاشتقاق وتسريب النتائج.

المراحل:
  1. عقد `notation-service :8011` حيّاً (`/health` · `/resolve` · `/define` · `/metrics`).
  2. تدهور رشيق: الخدمة مُطفأة ⇒ الجواب نفسه من السجلّ المحلّي.
  3. إعادة تمثيل الترانسكريبت عبر WebSocket الحقيقي على المونوليث `:8000`.
  4. «يجيب على كل سؤال»: بطارية أسئلة متنوّعة، كلٌّ ينتهي بإطار نهائي واحد.

الاستخدام (يتطلّب مونوليث حيّاً + مستخدماً حقيقيّاً):
    export E2E_BACKEND=http://localhost:8000
    export E2E_EMAIL=... E2E_PASSWORD=...
    python scripts/verify_d185_notation_live.py

بلا اعتماد على الخدمة: المراحل 1/2 تُتخطّى بوضوح إن لم تكن `:8011` تعمل (SKIP لا FAIL)،
لأن المونوليث **يجب** أن يعمل بدونها (قانون المهارات ٥). أما المرحلة 3 فإلزامية.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from typing import Any

BACKEND = os.environ.get("E2E_BACKEND", "http://localhost:8000")
NOTATION = os.environ.get("NOTATION_SERVICE_URL", "http://localhost:8011")
EMAIL = os.environ.get("E2E_EMAIL", "")
PASSWORD = os.environ.get("E2E_PASSWORD", "")

#: الترانسكريبت الحرفي من بلاغ المالك (BAC 2024 — تمرين الاحتمالات).
TRANSCRIPT: tuple[str, ...] = (
    "اعطني تمرين الاحتمالات 2024",
    "كيف افهم هذا التمرين؟",
    "لونين فقط الأبيض لا يمكن",
    "ماذا نقصد بحرف C",
)

#: أرقام التمرين التي يجب ألّا تظهر في دور التعريف (D-113: التعريف ليس إجابة).
LEAK_NUMBERS: tuple[str, ...] = ("14", "165", "56")

#: «يجيب على كل سؤال» — أصناف مختلفة، كلٌّ يجب أن ينتهي بإطار نهائي.
BATTERY: tuple[str, ...] = (
    "السلام عليكم",
    "ما معنى الرمز n!",
    "ما هو قانون أوم؟",
    "احسب تكامل x^2",
    "ما هي عاصمة الجزائر؟",
)


def _ok(message: str) -> None:
    print(f"✅ {message}")


def _fail(message: str) -> None:
    print(f"❌ {message}")


def _skip(message: str) -> None:
    print(f"⏭️  SKIP — {message}")


# ── 1/2: عقد الخدمة + التدهور الرشيق ─────────────────────────────────────────


def check_service() -> bool | None:
    """يفحص عقد `notation-service`. يُرجع None حين تكون الخدمة غير مُشغَّلة (SKIP)."""
    import httpx

    try:
        health = httpx.get(f"{NOTATION}/health", timeout=5.0).json()
    except Exception as exc:
        _skip(f"notation-service غير مُشغَّلة على {NOTATION} ({type(exc).__name__})")
        return None

    passed = True
    if health.get("status") != "healthy" or health.get("startup_state") != "ready":
        _fail(f"/health غير جاهز: {health}")
        passed = False
    else:
        _ok(f"/health: {health['symbols_loaded']} رمزاً · registry={health['registry_version']}")

    resolved = httpx.post(
        f"{NOTATION}/resolve",
        json={"text": "ماذا نقصد بحرف C"},
        headers={"X-Correlation-ID": "d185-live"},
        timeout=5.0,
    ).json()
    if not resolved.get("found") or resolved["symbol"]["symbol"] != "C(n,k)":
        _fail(f"/resolve أخفق على سؤال الكارثة: {resolved}")
        passed = False
    else:
        _ok(
            f"/resolve «ماذا نقصد بحرف C» → {resolved['symbol']['symbol']} "
            f"(trace={resolved['trace_id']})"
        )

    event = httpx.post(f"{NOTATION}/resolve", json={"text": "ما هي الحادثة C"}, timeout=5.0).json()
    if event.get("found"):
        _fail("التباس كارثي: «الحادثة C» عوملت كرمز")
        passed = False
    else:
        _ok("/resolve «ما هي الحادثة C» → لا رمز (حارس الالتباس يعمل)")

    unknown = httpx.post(f"{NOTATION}/define", json={"symbol": "zzz"}, timeout=5.0).json()
    if unknown.get("error", {}).get("code") != "NOTATION_SYMBOL_UNKNOWN":
        _fail(f"/define لم يُرجع خطأً مُهيكَلاً: {unknown}")
        passed = False
    else:
        _ok("/define رمز مجهول → خطأ مُهيكَل (fail-open، لا 500)")

    metrics = httpx.get(f"{NOTATION}/metrics", timeout=5.0).text
    if "cogniforge_notation_startup_info" not in metrics:
        _fail("/metrics بلا startup_info")
        passed = False
    else:
        _ok("/metrics يبثّ مقاييس الخدمة (سجلّ مستقلّ)")
    return passed


def check_local_fallback() -> bool:
    """يؤكّد أنّ المونوليث يُجيب بلا الخدمة إطلاقاً (قانون المهارات ٥)."""
    sys.path.insert(0, os.getcwd())
    from app.services.skills.notation_skill import get_notation_skill

    os.environ["NOTATION_SERVICE_URL"] = "http://127.0.0.1:1"  # عنوان ميّت عمداً
    entry = asyncio.run(get_notation_skill().resolve_via_service("ماذا نقصد بحرف C"))
    if entry is None or entry.symbol != "C(n,k)":
        _fail("التدهور الرشيق أخفق — الخدمة مُطفأة والجواب ضاع")
        return False
    _ok("التدهور الرشيق: الخدمة مُطفأة ⇒ الجواب نفسه من السجلّ المحلّي")
    return True


# ── 3/4: إعادة تمثيل الترانسكريبت عبر WebSocket الحقيقي ───────────────────────


def _login() -> str:
    """يسجّل الدخول ويُرجع رمز JWT (لا تُطبَع القيمة أبداً)."""
    import httpx

    response = httpx.post(
        f"{BACKEND}/api/security/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=30.0,
    )
    response.raise_for_status()
    return str(response.json()["access_token"])


async def _turn(websocket: Any, question: str) -> tuple[str, list[str]]:
    """يرسل سؤالاً ويجمع النصّ حتى الإطار النهائي. يُرجع (النص، أنواع الأطر)."""
    await websocket.send(json.dumps({"question": question, "client_request_id": str(uuid.uuid4())}))
    chunks: list[str] = []
    frames: list[str] = []
    while True:
        raw = await asyncio.wait_for(websocket.recv(), timeout=180.0)
        event = json.loads(raw)
        etype = str(event.get("type", ""))
        frames.append(etype)
        if etype == "assistant_delta":
            chunks.append(str((event.get("payload") or {}).get("content", "")))
        elif etype in {"assistant_final", "complete", "error"}:
            final = str((event.get("payload") or {}).get("content", ""))
            if final and not chunks:
                chunks.append(final)
            break
    return "".join(chunks), frames


async def replay_transcript() -> bool:
    """المرحلة الإلزامية: الدور الرابع يُجاب بتعريف، بلا تسريب وبلا تكرار."""
    import websockets

    token = _login()
    url = f"{BACKEND.replace('http', 'ws')}/api/chat/ws?token={token}&session_id={uuid.uuid4()}"
    passed = True
    async with websockets.connect(url, ping_interval=None, open_timeout=30) as websocket:
        await asyncio.wait_for(websocket.recv(), timeout=30.0)  # conversation_init
        answers: list[str] = []
        for index, question in enumerate(TRANSCRIPT, start=1):
            text, frames = await _turn(websocket, question)
            answers.append(text)
            terminal = [f for f in frames if f in {"assistant_final", "complete", "error"}]
            print(f"\n── دور {index}: {question!r}")
            print(f"   أطر: {len(frames)} · نهائي: {terminal} · طول: {len(text)} حرفاً")
            print(f"   مقتطف: {text[:160].replace(chr(10), ' ')}")
            if len(terminal) != 1 or terminal[0] == "error":
                _fail(f"الدور {index} لم ينتهِ بإطار نهائي واحد سليم: {terminal}")
                passed = False

        answer = answers[3]
        if "التوافيق" not in answer:
            _fail("الدور الرابع لم يُعرِّف الرمز C — الكارثة لم تُغلَق")
            passed = False
        else:
            _ok("الدور الرابع عرّف الرمز C (التوافيق) بدل إعادة الاشتقاق")

        leaked = [n for n in LEAK_NUMBERS if n in answer]
        if leaked:
            _fail(f"تسريب أرقام التمرين في دور التعريف: {leaked}")
            passed = False
        else:
            _ok("صفر تسريب: لا 14 ولا 165 ولا 56 في دور التعريف")

        previous_tokens = set(answers[2].split())
        current_tokens = set(answer.split())
        if previous_tokens and current_tokens:
            overlap = len(previous_tokens & current_tokens) / min(
                len(previous_tokens), len(current_tokens)
            )
            if overlap >= 0.8:
                _fail(f"تكرار حرفي للدور السابق (تداخل {overlap:.0%})")
                passed = False
            else:
                _ok(f"صفر تكرار: تداخل مع الدور السابق {overlap:.0%} (< 80%)")
    return passed


async def answer_everything() -> bool:
    """«يجيب على كل سؤال»: كل صنف ينتهي بإطار نهائي واحد، صفر تعليق."""
    import websockets

    token = _login()
    url = f"{BACKEND.replace('http', 'ws')}/api/chat/ws?token={token}&session_id={uuid.uuid4()}"
    passed = True
    async with websockets.connect(url, ping_interval=None, open_timeout=30) as websocket:
        await asyncio.wait_for(websocket.recv(), timeout=30.0)
        for question in BATTERY:
            try:
                text, frames = await _turn(websocket, question)
            except TimeoutError:
                _fail(f"تعليق بلا جواب: {question!r}")
                passed = False
                continue
            terminal = [f for f in frames if f in {"assistant_final", "complete", "error"}]
            if not text.strip() or terminal == ["error"]:
                _fail(f"جواب فارغ/خطأ: {question!r} → {terminal}")
                passed = False
            else:
                _ok(f"{question!r} → {len(text)} حرفاً ({terminal[0]})")
    return passed


def main() -> int:
    """يُشغّل المراحل الأربع ويُرجع 0 عند نجاح كل ما هو إلزامي."""
    print("=" * 78)
    print("D-185 / ISS-138 — تحقّق حيّ: «النظام يعرّف كل رمز يطبعه»")
    print("=" * 78)

    results: dict[str, bool | None] = {}

    print("\n[1] عقد notation-service")
    results["service_contract"] = check_service()

    print("\n[2] التدهور الرشيق (بلا الخدمة)")
    results["graceful_degradation"] = check_local_fallback()

    if not (EMAIL and PASSWORD):
        _skip("E2E_EMAIL/E2E_PASSWORD غير مضبوطين — تخطّي مراحل WebSocket")
        results["transcript_replay"] = None
        results["answer_everything"] = None
    else:
        print("\n[3] إعادة تمثيل الترانسكريبت عبر WebSocket")
        try:
            results["transcript_replay"] = asyncio.run(replay_transcript())
        except Exception as exc:
            _fail(f"إعادة التمثيل أخفقت: {type(exc).__name__}: {exc}")
            results["transcript_replay"] = False

        print("\n[4] «يجيب على كل سؤال»")
        try:
            results["answer_everything"] = asyncio.run(answer_everything())
        except Exception as exc:
            _fail(f"البطارية أخفقت: {type(exc).__name__}: {exc}")
            results["answer_everything"] = False

    print("\n" + "=" * 78)
    for stage, outcome in results.items():
        label = {True: "PASS", False: "FAIL", None: "SKIP"}[outcome]
        print(f"  {label:5} {stage}")
    print("=" * 78)
    return 1 if any(outcome is False for outcome in results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
