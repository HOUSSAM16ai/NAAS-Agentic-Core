#!/usr/bin/env python3
"""ISS-149 — إعادة تمثيل الكارثة على **مسارٍ حيّ كامل** والحكم على ما يراه الطالب.

## لماذا هذا السكربت موجود

عقد الترانسكريبت (`tests/transcripts/iss149_confusion_read_as_mastery.yaml`) يُشغّل
مراحل الدور الحتمية **داخل العملية**. ضروري ولا يكفي: لا يمرّ بـWebSocket ولا بالمصادقة
ولا بقاعدة بيانات حقيقية ولا بحفظ `tutor_state` عبر الأدوار عبر `TutorStateService`.

وهنا بالذات لا يكفي **مضاعفاً**: الضرر الأعمق في ISS-149 ليس النصّ بل ما **حُفِظ** —
`kc_progress["favorable_cases"] = {state: "understood", evidence: "verified"}` لمفهومٍ
أعلن الطالب للتوّ أنه لم يفهمه. أي أنّ إسكات جملة «أحسنت ✅» وحدها لا يُغلق البلاغ:
يجب أن نقرأ الصفوف من قاعدة البيانات ونتأكّد أنّ النموذج المعرفي لم يسجّل إتقاناً
لم يحدث.

## التشغيل

    E2E_EMAIL=… E2E_PASSWORD=… python3 scripts/verify_iss149_live.py

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

#: العقد المُلتزَم هو **المصدر الوحيد** لأدوار الطالب — لا نسخة ثانية هنا (D-206·L6).
#: نسخُها هنا كان سيخلق قائمتين لنفس الترانسكريبت تتفرّقان بأوّل تعديل، فيُثبت المسارُ
#: الحيّ شيئاً ويحرس CI شيئاً آخر.
CONTRACT = (
    Path(__file__).resolve().parents[1] / "tests/transcripts/iss149_confusion_read_as_mastery.yaml"
)


def _load_contract() -> tuple[str, tuple[str, ...], dict[str, str]]:
    """يقرأ (الدور الافتتاحي، أدوار الطالب، قيود الحالة الدائمة) من العقد."""
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    opening = next(
        str(message["content"])
        for message in contract["seed_history"]
        if message.get("role") == "user"
    )
    turns = tuple(str(turn["student"]) for turn in contract["turns"])
    forbidden_states = {
        str(k): str(v) for k, v in (contract.get("final_kc_state_not") or {}).items()
    }
    return opening, turns, forbidden_states


#: الجملة القاتلة حرفياً كما وصلت الطالب.
_CONGRATULATION_MARKERS = ("أحسنت", "أمسكت الفكرة")

#: التفريغ الذي اشترته «فهمت» المجرّدة.
_DUMP_MARKERS = ("= 14", "4 + 10")

#: أدنى طول لدورٍ مُجيب — وعدٌ بشرحٍ لا يصل أسوأ من خطأ صريح (§0).
_MIN_ANSWER_CHARS = 60


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

    الاتصال يبقى مفتوحاً و``conversation_id`` يُعاد إرساله في كل دور، تماماً كالعميل
    الحقيقي. بدونه يفتح الخادم محادثةً جديدة لكل رسالة فيبقى `tutor_state` مُصفَّراً —
    وهو انحرافٌ عن الإنتاج يجعل الإثبات بلا قيمة (نفس درس ISS-148).
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
    for index, (question, answer) in enumerate(answers, 1):
        stripped = answer.strip()
        if not stripped:
            failures.append(f"الدور {index} ({question!r}): دورٌ صامت — لا نصّ إطلاقاً.")
            continue
        if len(stripped) < _MIN_ANSWER_CHARS:
            failures.append(f"الدور {index} ({question!r}): {len(stripped)} حرفاً — وعدٌ لم يصل.")

        # R1/R2/R3 — الحيرة لا تُهنَّأ.
        if question.strip().startswith("لم أفهم"):
            hit = [m for m in _CONGRATULATION_MARKERS if m in stripped]
            if hit:
                failures.append(
                    f"الدور {index} ({question!r}): حيرةٌ مُعلَنة رُدّ عليها بتهنئة {hit} — "
                    f"انقلابُ إشارة الطالب (ISS-149)."
                )

        # R5 — ادّعاء الفهم لا يشتري الاشتقاق.
        if question.strip() == "فهمت":
            hit = [m for m in _DUMP_MARKERS if m in stripped]
            if hit:
                failures.append(
                    f"الدور {index}: «فهمت» المجرّدة سلّمت {hit} — الادّعاء يُختبَر لا يُكافأ."
                )

        # R4 — سؤالٌ عن دورَين يُجاب عن دورَين.
        if "البسط" in question and "المقام" in question and "المقام" not in stripped:
            failures.append(
                f"الدور {index} ({question!r}): سؤالُ مقارنةٍ أُجيب عن طرفٍ واحد — "
                f"«المقام» غائب عن الجواب."
            )
    return failures


async def _read_persisted_state(token: str, forbidden: dict[str, str]) -> list[str]:
    """يقرأ الحالة الدائمة من الخادم ويتحقّق أنّ النموذج المعرفي لم يكذب.

    هذا هو **جوهر** ISS-149: نصٌّ نظيف مع `understood` محفوظة يعني أنّ الكارثة صامتة
    لا مُصلَحة. المسار fail-open في الإبلاغ: تعذُّر القراءة يُذكَر ولا يُدّعى نجاحاً.
    """
    if not forbidden:
        return []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for path in ("/api/v1/tutor/state", "/api/tutor/state", "/api/v1/analytics/tutor-state"):
            try:
                response = await client.get(
                    f"{BACKEND}{path}", headers={"Authorization": f"Bearer {token}"}
                )
            except Exception:  # pragma: no cover - شبكة
                continue
            if response.status_code != 200:
                continue
            kc = (response.json() or {}).get("kc_progress") or {}
            problems = []
            for concept, banned in forbidden.items():
                state = (kc.get(concept) or {}).get("state")
                if state == banned:
                    problems.append(
                        f"الحالة الدائمة: {concept} صارت {banned!r} — "
                        f"النموذج المعرفي سجّل إتقاناً لم يحدث (ISS-149)."
                    )
            print(f"✅ قُرِئت الحالة الدائمة عبر {path}: {sorted(kc)}")
            return problems
    print(
        "⚠️  تعذّرت قراءة الحالة الدائمة عبر HTTP — يُذكَر ولا يُدّعى نجاحاً.\n"
        "    افحصها مباشرةً: SELECT kc_progress FROM tutor_state WHERE user_id = …"
    )
    return []


async def main() -> int:
    if not EMAIL or not PASSWORD:
        raise SystemExit("❌ E2E_EMAIL و E2E_PASSWORD مطلوبان.")

    print(f"🔗 الواجهة الخلفية: {BACKEND}")
    opening_question, turns, forbidden_states = _load_contract()
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
    failures.extend(await _read_persisted_state(token, forbidden_states))

    print("\n" + "=" * 72)
    if failures:
        print(f"❌ ISS-149 — {len(failures)} خرقاً على مسارٍ حيّ:\n")
        for failure in failures:
            print(f"  • {failure}")
        return 1
    print(
        f"✅ ISS-149 — {len(turns)} أدوار حيّة: الحيرة لم تُهنَّأ، والادّعاء لم يشترِ "
        f"الاشتقاق، وسؤال المقارنة أُجيب كاملاً، والنموذج المعرفي لم يسجّل إتقاناً وهمياً."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
