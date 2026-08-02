#!/usr/bin/env python3
"""ISS-148 — إعادة تمثيل المحادثة 837 على **مسارٍ حيّ كامل** والحكم على ما يراه الطالب.

## لماذا هذا السكربت موجود

عقد الترانسكريبت (`tests/transcripts/iss148_procedure_question_leak.yaml`) يُشغّل مراحل
الدور الحتمية **داخل العملية**. هذا ضروري ولا يكفي: لا يمرّ بـWebSocket ولا بالمصادقة
ولا بقاعدة بيانات حقيقية ولا بحفظ الحالة الدائمة عبر الأدوار. والحالةُ الدائمة هي
بالضبط ما يقوم عليه كل منطق «لا تُعِد ما سُلِّم» — فاختبارٌ لا يحفظها يُخضِّر ما قد
يبقى أحمر عند الطالب.

هنا: تسجيل دخول حقيقي ⇒ JWT حقيقي ⇒ `ws://…/api/chat/ws` ⇒ ستّة أدوار كما كتبها
الطالب حرفياً ⇒ حكمٌ على النصّ الواصل ⇒ ثمّ قراءة الصفوف من قاعدة البيانات.

## التشغيل

    E2E_EMAIL=… E2E_PASSWORD=… python3 scripts/verify_iss148_live.py

المتغيّرات الاختيارية: ``E2E_BACKEND`` (افتراضياً ``http://127.0.0.1:8000``).
يخرج بـ0 عند النجاح، وبـ1 عند أوّل خرقٍ للعقد — مع طباعة الدور المخالف كاملاً.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
import yaml
from websockets.asyncio.client import connect

BACKEND = os.environ.get("E2E_BACKEND", "http://127.0.0.1:8000").rstrip("/")
WS_URL = BACKEND.replace("https://", "wss://").replace("http://", "ws://") + "/api/chat/ws"
EMAIL = os.environ.get("E2E_EMAIL", "")
PASSWORD = os.environ.get("E2E_PASSWORD", "")

#: العقد المُلتزَم هو **المصدر الوحيد** لأدوار الطالب — لا نسخة ثانية هنا.
#:
#: نسخُها في هذا الملفّ كان يخلق قائمتين لنفس الترانسكريبت تتفرّقان بأوّل تعديل، فيُثبت
#: المسار الحيّ شيئاً ويحرس CI شيئاً آخر. وهو أيضاً ما رفضته `check_intent_single_source`
#: بحقّ: صيغُ الطالب لها موطنٌ واحد (D-186/D-206·L6).
CONTRACT = (
    Path(__file__).resolve().parents[1] / "tests/transcripts/iss148_procedure_question_leak.yaml"
)


def _load_turns() -> tuple[str, tuple[str, ...]]:
    """يقرأ (الدور الافتتاحي، أدوار الطالب) من العقد المُلتزَم."""
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    opening = next(
        str(message["content"])
        for message in contract["seed_history"]
        if message.get("role") == "user"
    )
    # الدور الأخير في العقد حارسُ انحدارٍ على D-113 لا جزءٌ من ترانسكريبت الإنتاج.
    turns = tuple(str(turn["student"]) for turn in contract["turns"][:6])
    return opening, turns


#: أدنى طول لدورٍ مُجيب — الرسالة 4613 الكارثية كانت 136 حرفاً بلا خطوة واحدة.
_MIN_ANSWER_CHARS = 60

#: الاشتقاق الذي يجب ألّا يُطبع مرّتين (تكرار 4611 ⇒ 4615).
_DERIVATION = r"\dfrac{11\times 10\times 9}"


async def _login() -> str:
    """تسجيل دخول حقيقي — يُرجِع access_token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for path in ("/api/v1/auth/login", "/api/security/login"):
            try:
                response = await client.post(
                    f"{BACKEND}{path}", json={"email": EMAIL, "password": PASSWORD}
                )
            except Exception as exc:  # pragma: no cover - شبكة
                print(f"  ! {path}: {exc}")
                continue
            if response.status_code == 200:
                token = response.json().get("access_token")
                if token:
                    print(f"✅ تسجيل الدخول عبر {path}")
                    return str(token)
            print(f"  ! {path} ⇒ {response.status_code} {response.text[:160]}")
    raise SystemExit("❌ تعذّر تسجيل الدخول — لا يمكن إثبات شيء بلا جلسة حقيقية.")


async def _turn(
    websocket, question: str, conversation_id: int | None
) -> tuple[str, int, int | None]:
    """دورٌ واحد على اتصالٍ **مفتوح** — يُرجِع (النصّ، عدد الأطر النهائية، مُعرّف المحادثة).

    الاتصال يبقى مفتوحاً عبر الأدوار كما يفعل العميل الحقيقي، و``conversation_id``
    يُعاد إرساله في كل دور. بدونه يفتح الخادم **محادثةً جديدة لكل رسالة**: فيبقى
    `history_messages` فارغاً و`tutor_state` مُصفَّراً، فلا يتقدّم العقل الحتمي أبداً
    ويُسلَّم الدورُ للـLLM. أي أن الطالب يبدأ من الصفر في كل سؤال — وهو انحرافٌ عن
    الإنتاج يجعل الإثبات بلا قيمة.
    """
    chunks: list[str] = []
    terminal = 0
    message: dict[str, object] = {"question": question}
    if conversation_id is not None:
        message["conversation_id"] = conversation_id
    await websocket.send(json.dumps(message))
    while True:
        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=180)
        except TimeoutError:
            break
        event = json.loads(raw)
        etype = event.get("type")
        payload = event.get("payload") or {}
        if etype == "conversation_init":
            _cid = payload.get("conversation_id")
            if isinstance(_cid, int):
                conversation_id = _cid
        elif etype == "assistant_delta":
            chunks.append(str(payload.get("content", "")))
        elif etype in ("assistant_final", "complete", "error", "stream_end"):
            terminal += 1
            if etype == "error":
                chunks.append(f"[ERROR] {payload}")
            break
    return "".join(chunks), terminal, conversation_id


def _judge(answers: list[tuple[str, str]]) -> list[str]:
    """يحكم على ما وصل الطالب فعلاً — كل خرق يُسمّى ويُطبع."""
    failures: list[str] = []
    derivation_turns = [i for i, (_, a) in enumerate(answers, 1) if _DERIVATION in a]
    if len(derivation_turns) > 1:
        failures.append(
            f"اشتقاق المقام طُبع في الأدوار {derivation_turns} — يُكشَف مرّة واحدة (ISS-148)."
        )

    seen: dict[str, int] = {}
    for index, (question, answer) in enumerate(answers, 1):
        stripped = answer.strip()
        if not stripped:
            failures.append(f"الدور {index} ({question!r}): دورٌ صامت — لا نصّ إطلاقاً.")
            continue
        if len(stripped) < _MIN_ANSWER_CHARS:
            failures.append(f"الدور {index} ({question!r}): {len(stripped)} حرفاً فقط — وعدٌ لم يصل.")
        if "لنُكمل معاً خطوة بخطوة حتى النهاية" in stripped and "$C_" not in stripped:
            failures.append(
                f"الدور {index} ({question!r}): وعدَ بخطواتٍ ولم يُعطِ خطوة (الرسالة 4613)."
            )
        previous = seen.get(stripped)
        if previous:
            failures.append(f"الدور {index} ({question!r}): نسخة حرفية من الدور {previous}.")
        seen[stripped] = index
    return failures


async def main() -> int:
    if not EMAIL or not PASSWORD:
        raise SystemExit("❌ E2E_EMAIL و E2E_PASSWORD مطلوبان.")

    print(f"🔗 الواجهة الخلفية: {BACKEND}")
    opening_question, turns = _load_turns()
    token = await _login()

    answers: list[tuple[str, str]] = []
    async with connect(
        f"{WS_URL}?token={token}", subprotocols=["jwt", token], ping_interval=None
    ) as websocket:
        print(f"\n▶️  فتح السياق: {opening_question!r}")
        opening, _, conversation_id = await _turn(websocket, opening_question, None)
        print(f"   ({len(opening)} حرفاً · المحادثة {conversation_id})")

        for index, question in enumerate(turns, 1):
            answer, terminal, conversation_id = await _turn(websocket, question, conversation_id)
            print(f"\n═══ الدور {index} — الطالب: {question}")
            print(answer if answer.strip() else "  (فارغ)")
            if terminal != 1:
                print(f"  ⚠️  أطر نهائية = {terminal} (المتوقّع 1 — §6.5)")
            answers.append((question, answer))

    failures = _judge(answers)
    print("\n" + "=" * 72)
    if failures:
        print(f"❌ ISS-148 — {len(failures)} خرقاً على مسارٍ حيّ:\n")
        for failure in failures:
            print(f"  • {failure}")
        return 1
    print("✅ ISS-148 — ستّة أدوار حيّة: لا تسريب مكرَّر، لا دور فارغ، لا نسخة حرفية.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
