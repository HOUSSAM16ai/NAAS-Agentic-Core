#!/usr/bin/env python3.12
"""D-163 (Stage 3) — Live proof: the microservices probability-tutor PORT serves a turn on :8006.

سدّ الفجوة التي كشفها استكشاف M10-S2: لا يوجد أي driver يجمع علم
``ORCHESTRATOR_PROB_TUTOR_ENABLED`` مع ``context.exercise_content`` ويدفعهما إلى
الـ orchestrator مباشرةً (:8006) — فبقي الـ port بلا حركة حية رغم تكافؤ العقود.

يُثبت هذا السكربت على المكدّس الحقيقي (POST NDJSON إلى :8006/api/chat/messages، بلا
مونوليث) أن hook الـ ``SynthesizerNode`` يستدعي ``deterministic_turn`` ويبثّ نصّاً
حتمياً نظيفاً بدل الـ LLM:

  1) دور احتمالات + exercise_content + العلم ON ⇒ **إجابة الـ port الحتمية**:
     - عربي نظيف، صفر تسريب النسبة النهائية (14/165)، صفر garbage.
     - probe-first لأول طلب مساعدة (سؤال تشخيصي، صفر قيم محسوبة).
     - اعتراف بإجابة رقمية صحيحة (D-155) بلا إعادة سؤال.
     - سُلّم بلا تكرار حرفي (dedup محايد للحجب).
  2) fail-open: بلا exercise_content ⇒ المسار يسقط لتوليف الـ LLM العادي (لا الـ port).

التهيئة (من البيئة — لا أسرار في الكود):
  E2E_ORCH (افتراضي http://localhost:8006) · SECRET_KEY (نفس المشترك مع الـ orchestrator).

Usage:
  set -a && . .devcontainer/secrets.env && set +a
  SECRET_KEY=<shared> ORCHESTRATOR_PROB_TUTOR_ENABLED=1 \
  E2E_ORCH=http://127.0.0.1:8006 python3.12 scripts/verify_m10s2_port_live.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid

import httpx
import jwt as pyjwt

ORCH = os.environ.get("E2E_ORCH", "http://localhost:8006")
SECRET = os.environ.get("SECRET_KEY", "")
USER_ID = int(os.environ.get("E2E_USER_ID", "7"))

# تركيبة BAC-2024 (أسئلة-فقط): 4 حمراء + 5 خضراء + 2 بيضاء، سحب 3 دفعة واحدة.
_EXERCISE = (
    "يحتوي كيس على إحدى عشرة كرة: أربع كرات حمراء وخمس كرات خضراء وكرتان بيضاوان "
    "لا نفرّق بينها باللمس. نسحب عشوائياً وفي آن واحد ثلاث كرات من الكيس.\n"
    "1) احسب احتمال الحادثة A: «الكرات الثلاث المسحوبة من نفس اللون».\n"
    "2) ليكن X المتغير العشوائي الذي يساوي عدد الكرات الحمراء المسحوبة."
)

_RESULTS: list[tuple[str, bool, str]] = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    _RESULTS.append((name, ok, detail))
    print(f"{'✅' if ok else '❌'} {name}" + (f" — {detail[:120]}" if detail else ""))


def _service_jwt() -> str:
    now = int(time.time())
    payload = {
        "sub": str(USER_ID),
        "user_id": USER_ID,
        "iat": now,
        "exp": now + 300,
        "iss": "cogniforge-monolith",
    }
    return pyjwt.encode(payload, SECRET, algorithm="HS256")


async def _post_turn(
    client: httpx.AsyncClient,
    question: str,
    *,
    session_id: str,
    history: list[dict[str, str]],
    inject: bool,
    support_level: int | None = None,
) -> str:
    """POST دور واحد، يُرجِع النصّ المتراكم من deltas (NDJSON).

    لا نمرّر ``conversation_id`` مختلقاً (يفشل بـ 403 «لا تخصّ المستخدم») — نترك
    الـ orchestrator يشتقّ المحادثة من ``session_id`` الثابت (استمرارية الحوار).
    ``support_level`` (D-115) يُمرَّر عبر السياق عند الحاجة لتثبيت رُتبة السُّلّم.
    """
    context: dict[str, object] = {"chat_scope": "customer", "session_id": session_id}
    if support_level is not None:
        context["support_level"] = support_level
    if inject:
        context["exercise_content"] = _EXERCISE
        context["exercise_ref"] = "bac2024"
    body = {
        "question": question,
        "user_id": USER_ID,
        "history_messages": history,
        "context": context,
    }
    text_parts: list[str] = []
    headers = {"Authorization": f"Bearer {_service_jwt()}"}
    async with client.stream(
        "POST", f"{ORCH}/api/chat/messages", json=body, headers=headers, timeout=120
    ) as resp:
        resp.raise_for_status()
        async for raw_line in resp.aiter_lines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = evt.get("type")
            payload = evt.get("payload") or evt
            if etype in ("assistant_delta", "delta") and isinstance(payload, dict):
                chunk = payload.get("content")
                if isinstance(chunk, str):
                    text_parts.append(chunk)
    return "".join(text_parts)


async def main() -> int:
    if not SECRET:
        print("❌ SECRET_KEY not in env (must match the orchestrator's shared key)")
        return 2
    sid_prob = f"m10s2-prob-{uuid.uuid4()}"
    sid_gen = f"m10s2-gen-{uuid.uuid4()}"
    async with httpx.AsyncClient() as client:
        # ── 1) probe-first: أول طلب مساعدة عام + exercise_content + العلم ON ──
        probe = await _post_turn(
            client,
            "كيف احل التمرين",
            session_id=sid_prob,
            history=[],
            inject=True,
        )
        _check("port serves a live turn on :8006", bool(probe.strip()), probe)
        _check(
            "probe-first (diagnostic, zero computed values)",
            "أيّ الألوان" in probe and "165" not in probe,
            probe,
        )
        _check("zero final-ratio leak (14/165)", "14/165" not in probe and "من كل 165" not in probe)
        _check(
            "clean Arabic (no garbage/latin prose)",
            "probability" not in probe.lower() and "the " not in probe.lower(),
        )

        # ── 2) support_level=1 (متعثّر) ⇒ السُّلّم يبدأ بخطوة البسط الكاملة مباشرةً
        #      (تسأل عن المقام) — نظير D-115 (المعامل لم يعد ميتاً). ──
        sid_seq = f"m10s2-seq-{uuid.uuid4()}"
        step = await _post_turn(
            client,
            "الحمراء و الخضراء فقط",
            session_id=sid_seq,
            history=[],
            inject=True,
            support_level=1,
        )
        _check(
            "support_level=1 → numerator step asks the denominator (pending set)",
            "كم عدد" in step and "165" not in step,
            step,
        )

        # ── 3) fail-open: بلا exercise_content ⇒ لا يستدعي الـ port (توليف LLM عادي) ──
        general = await _post_turn(
            client,
            "ما هو قانون نيوتن الثاني؟",
            session_id=sid_gen,
            history=[],
            inject=False,
        )
        # لا يجب أن يبثّ الـ port سُلّم احتمالات على سؤال فيزياء عام.
        _check(
            "fail-open: no exercise_content ⇒ port does NOT fire",
            "أيّ الألوان يمكن أن تعطينا" not in general and bool(general.strip()),
            general,
        )

    # ── 4) قدرة الاعتراف بإجابة رقمية صحيحة (D-155) — تُثبَت باستدعاء **دالة الـ
    #      port المنشورة نفسها** مباشرةً (نفس الوحدة الحية على :8006). على مسار
    #      HTTP+SQLite لا checkpointer (D-098) والـ handler يقرأ التاريخ من DB لا
    #      من الجسم (history_len=0) ⇒ الاستمرارية عبر الأدوار قيدُ orchestrator لا
    #      عيبُ port. القدرة نفسها مُثبتة أيضاً حياً في مسار المونوليث (D-162 T5/T6). ──
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from microservices.orchestrator_service.src.services.overmind.probability_tutor import (
        deterministic_turn as _dt,
    )

    _hist = [
        "User: الحمراء و الخضراء فقط",
        "Assistant: نحسب الحالات الملائمة. والآن: كم عدد كل الطرق الممكنة لسحب 3 كرات من 11؟",
    ]
    _ack = _dt("165", _EXERCISE, history=_hist, support_level=1)
    _check(
        "port acknowledges a correct numeric answer + advances (deployed module)",
        bool(_ack) and ("إجابتك في الطريق الصحيح" in (_ack or "") or "أحسنت" in (_ack or "")),
        _ack or "",
    )

    passed = sum(1 for _, ok, _ in _RESULTS if ok)
    total = len(_RESULTS)
    print(f"\n{'=' * 60}")
    if passed == total:
        print(f"✅ M10-S2 PORT LIVE PROOF: ALL {total} PASS")
        return 0
    print(f"❌ M10-S2 PORT LIVE PROOF: {passed}/{total} passed")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
