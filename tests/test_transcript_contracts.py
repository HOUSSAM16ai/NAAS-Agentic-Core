from __future__ import annotations

"""D-186 — عقود الترانسكريبت: كل كارثة مُبلَّغ عنها تصير اختباراً دائماً في CI.

## لماذا هذا الملف موجود

ثلاث كوارث متتالية (ISS-128 · ISS-138 · ISS-139) كان جذرها **واحداً**: كاشفات متعدّدة
لنفس نيّة الطالب تتفرّق. وكلّها أُغلقت باختبارات وحدة تفحص دالّةً بعينها — فحين تحرّك
الجذر إلى طبقة أخرى لم يلتقطه شيء، وعاد الطالب يرى الكارثة نفسها بصيغة مختلفة.

العقد هنا يفحص **ما يراه الطالب** لا ما تُرجعه دالّة. لذلك يُعيد تمثيل الأدوار على
**مراحل الدور الحتمية نفسها** التي يمرّ بها الطالب حيّاً (`TurnContext` + سلسلة المراحل
من `chat_turn.py`) — لا على إعادة تنفيذٍ موازية. اختبارٌ يعيد بناء المنطق يختبر نفسه.

## النطاق: حتمي فقط

يُشغَّل **المقطع الحتمي** من السلسلة. هذه هي المراحل التي تُنتج جواب المعلّم بلا LLM
ولا شبكة. المراحل التي تعتمد على LLM خارج النطاق عمداً: عقدٌ يعتمد على LLM ليس عقداً.

## ISS-148 — لماذا اتّسع النطاق

كان النطاق يقف عند `_stage_concept_example` (٧ مراحل من ١٢). فبقيت المراحل ٨→١١ —
وفيها `_stage_escape_hatch`، موطنُ `_build_probability_direct_explanation` — **خارج
مرمى كل عقد**. النتيجة المُبرهَنة: عقد ISS-144 أخضر بينما كان الطالب في الإنتاج
(المحادثة 837، 2026-08-02) يتلقّى `C(4,3)=4` و`C(5,3)=10` و`165` مسرَّبةً، ثمّ دوراً
فارغاً، ثمّ تكراراً لـ165 — كلّها من مراحل لا يبلغها المُشغِّل. **بوّابة بلا مرمى
ليست بوّابة**، والنطاق صار محروساً آلياً بـ`check_transcript_stage_coverage`.
"""

import asyncio
from pathlib import Path
from typing import Any

import pytest
import yaml

TRANSCRIPTS_DIR = Path(__file__).parent / "transcripts"

#: المقطع الحتمي من سلسلة المراحل (بترتيب `chat_turn.py` — الترتيب هو العقد).
#: ISS-148: امتدّ من ٧ إلى ١١ مرحلة. تحرس التطابقَ مع `chat_turn.py` بوّابةُ
#: `scripts/fitness/check_transcript_stage_coverage.py`.
_DETERMINISTIC_STAGES = (
    "_stage_policy_gate",
    "_stage_greeting",
    "_stage_question_only",
    "_stage_computational",
    "_stage_escalation_matrix",
    "_stage_definitional",
    "_stage_concept_example",
    "_stage_socratic_evaluation",
    "_stage_indexed_retrieval",
    "_stage_escape_hatch",
    "_stage_calculated_ui",
)

#: المراحل المُستثناة **بسببٍ مُصرَّح** (D-206·L11: الغياب لا يعني الغموض).
#: تقرأها البوّابة، فالاستثناء قرارٌ مكتوب لا سهوٌ صامت.
_LLM_DEPENDENT_STAGES = {
    # يبثّ شرحاً مُولَّداً عبر `_stream_exercise_explanation_response` (LLM + شبكة).
    "_stage_explanation_context": "يستدعي LLM — عقدٌ يعتمد على LLM ليس عقداً.",
}


def _load_contracts() -> list[dict[str, Any]]:
    """يقرأ كل عقود الترانسكريبت المُلتزَمة."""
    return [
        yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(TRANSCRIPTS_DIR.glob("*.yaml"))
    ]


_CONTRACTS = _load_contracts()


async def _run_turn(
    client: Any,
    question: str,
    history: list[dict[str, str]],
    tutor_state: dict[str, Any],
) -> str:
    """يُشغّل المقطع الحتمي لدورٍ واحد ويُعيد نصّ المعلّم كما يصل الطالب.

    ISS-148 — ``tutor_state`` يُمرَّر ويُدمَج عبر الأدوار. بدونه كان المُشغِّل
    **عديم الذاكرة**: `kc_progress` فارغ في كل دور، فيُعاد probe التشخيص كل مرّة
    ويبقى `representations_delivered` خالياً. أي أن العقد كان يختبر نظاماً لا
    وجود له — في الإنتاج الحالة **دائمة** (`TutorStateService.record_turn`)،
    وعليها يقوم كل منطق «لا تُعِد ما سُلِّم». عقدٌ يمثّل حالةً أبسط من الواقع
    يُخضِّر أعطاباً حقيقية.
    """
    from app.infrastructure.clients.orchestrator.turn_context import TurnContext

    ctx = TurnContext(
        question=question,
        user_id=1,
        conversation_id=1,
        history_messages=list(history),
        context={"tutor_state": tutor_state},
    )
    ctx.tutor_state = tutor_state
    chunks: list[str] = []
    for stage_name in _DETERMINISTIC_STAGES:
        stage = getattr(client, stage_name, None)
        if stage is None:  # pragma: no cover — المرحلة أُعيدت تسميتها
            pytest.fail(f"stage {stage_name!r} is missing — update _DETERMINISTIC_STAGES")
        async for event in stage(ctx):
            if not isinstance(event, dict) or event.get("type") != "assistant_delta":
                continue
            chunks.append(str((event.get("payload") or {}).get("content", "")))
        if ctx.turn_complete:
            break

    # مرآة `TutorStateService.record_turn` (app/services/analytics/tutor_state_service.py:156):
    # الدمج على مستوى المفتاح الأعلى — قيمة الدلتا تحلّ محلّ السابقة. نفس الدلالة،
    # لا إعادة بناء لمنطقٍ آخر.
    _delta = tutor_state.pop("kc_progress_delta", None)
    if isinstance(_delta, dict) and _delta:
        _merged = tutor_state.setdefault("kc_progress", {})
        for _key, _value in _delta.items():
            _merged[_key] = _value
    return "".join(chunks)


def _assert_needles(turn: dict[str, Any], answer: str, where: str) -> None:
    """قيود الوجود/الغياب النصّية لدورٍ واحد."""
    for needle in turn.get("must_contain", ()):
        assert needle in answer, f"{where}: غاب {needle!r} عن الجواب.\n--- الجواب ---\n{answer}"

    for needle in turn.get("must_not_contain", ()):
        assert needle not in answer, f"{where}: ظهر الممنوع {needle!r}.\n--- الجواب ---\n{answer}"

    forbidden_head = turn.get("must_not_start_with")
    if forbidden_head:
        assert not answer.strip().startswith(forbidden_head), (
            f"{where}: الجواب بدأ بـ {forbidden_head!r} — "
            f"سؤال تعريفي لا يُجاب بمثالٍ عارٍ.\n--- الجواب ---\n{answer}"
        )


@pytest.mark.parametrize("contract", _CONTRACTS, ids=[c["id"] for c in _CONTRACTS])
def test_transcript_contract(contract: dict[str, Any]) -> None:
    """يُعيد تمثيل ترانسكريبت كارثة ويفرض قيوده على كل دور."""
    from app.infrastructure.clients.orchestrator_client import OrchestratorClient

    client = OrchestratorClient()
    # سياق التمرين كما يراه الطالب حيّاً — بدونه تُغلَق بوّابة سياق الاحتمالات
    # (`_is_prob_context`) فلا يُمثَّل الترانسكريبت الحقيقي أصلاً.
    history: list[dict[str, str]] = [
        {"role": str(m["role"]), "content": str(m["content"])}
        for m in contract.get("seed_history", ())
    ]

    previous_answer = ""
    prior_answers: list[tuple[int, str]] = []
    # الحالة الدائمة كما تعيش في الإنتاج — تُبنى عبر الأدوار لا تُصفَّر (ISS-148).
    tutor_state: dict[str, Any] = {"kc_progress": {}}
    # ── ISS-148: دفتر الحقائق المكشوفة ────────────────────────────────────────
    # حارس التكرار في المحرك يُقنّع **كل رقم** إلى `#` قبل المقارنة
    # (`_norm_for_dedup`)، فـ165 غير مرئية له بنيوياً؛ ولا يقارن إلّا التشابه
    # النثري. لذلك أعاد الدورُ 4615 كشفَ 165 بصياغة أخرى ومرّ. الدفتر يقيس
    # **القيمة** لا الصياغة: قيمةٌ تُكشَف مرّة واحدة على امتداد العقد كلّه.
    reveal_once: list[str] = [str(v) for v in contract.get("reveal_once", ())]
    revealed_at: dict[str, int] = {}

    for index, turn in enumerate(contract["turns"], start=1):
        question = turn["student"]
        answer = asyncio.run(_run_turn(client, question, history, tutor_state))
        where = f"[{contract['id']} turn {index}] {question!r}"

        if turn.get("must_answer"):
            assert answer.strip(), f"{where}: الدور لم يُنتج جواباً حتمياً إطلاقاً"

        # ── ISS-148 (§0): وعدٌ بشرحٍ لا يصل أسوأ من خطأ صريح ──────────────────
        # الرسالة 4613 في الإنتاج: «لنُكمل معاً خطوة بخطوة حتى النهاية:» ثمّ ولا
        # خطوة — ١٣٦ حرفاً من العدم. الميزانية الدنيا تجعل «الجواب الفارغ ذو
        # الشكل الصحيح» عطباً مرئياً لا نجاحاً صامتاً.
        min_chars = turn.get("min_chars")
        if min_chars:
            assert len(answer.strip()) >= int(min_chars), (
                f"{where}: الجواب {len(answer.strip())} حرفاً < الحدّ الأدنى "
                f"{min_chars} — وعدٌ بشرحٍ لم يصل.\n--- الجواب ---\n{answer}"
            )

        _assert_needles(turn, answer, where)

        # ── L10 (D-206): الصمت انضباط لا فراغ ─────────────────────────────────
        # جدار النصّ عطبٌ لا وفرة. في ISS-141 كان الردّ على «أعطني السؤال الأول
        # **فقط**» هو التمرين كاملاً — بنيةٌ «صحيحة» وضررٌ حقيقي. الميزانية تجعل
        # الطول جزءاً من **عقد** الكارثة بدل أن يبقى اجتهاداً يتآكل.
        max_chars = turn.get("max_chars")
        if max_chars:
            assert len(answer) <= int(max_chars), (
                f"{where}: الجواب {len(answer)} حرفاً > الميزانية {max_chars} — "
                f"جدار نصّ.\n--- الجواب ---\n{answer[:400]}…"
            )

        if turn.get("must_differ_from_previous") and previous_answer:
            assert answer.strip() != previous_answer.strip(), (
                f"{where}: الجواب نسخة حرفية من الدور السابق — «صفر تكرار حرفي»."
                f"\n--- الجواب ---\n{answer}"
            )

        # ── ISS-148: التكرار ليس «الدور السابق» وحده ─────────────────────────
        # `must_differ_from_previous` تقارن بالدور الأخير فقط، فتكرارُ دورٍ أقدم
        # يمرّ. في الإنتاج تكرّر الكشفُ بعد **دورين**.
        if turn.get("must_not_repeat_any_prior"):
            for prior_index, prior in prior_answers:
                assert answer.strip() != prior.strip(), (
                    f"{where}: الجواب نسخة حرفية من الدور {prior_index} — "
                    f"التكرار عبر الأدوار.\n--- الجواب ---\n{answer}"
                )

        for value in reveal_once:
            if value not in answer:
                continue
            first = revealed_at.get(value)
            assert first is None, (
                f"{where}: القيمة {value!r} كُشِفت أصلاً في الدور {first} وأُعيد "
                f"كشفها هنا — دفتر الحقائق يُكشَف مرّة واحدة (ISS-148)."
                f"\n--- الجواب ---\n{answer}"
            )
            revealed_at[value] = index

        history.append({"role": "user", "content": question})
        if answer.strip():
            history.append({"role": "assistant", "content": answer})
            prior_answers.append((index, answer))
            previous_answer = answer

    # ── ISS-149: النموذج المعرفي المحفوظ جزءٌ من العقد ────────────────────────
    # نصّ الدور ليس كلّ الضرر. في ISS-149 كتب فرعُ `mastered` في الحالة الدائمة
    # `state="understood"`/`evidence="verified"` لمفهومٍ أعلن الطالبُ للتوّ أنه لم
    # يفهمه — فتُصنَّع «فجوة الوهم» التي يقول §0.6 إننا نُحسّن على تقليصها. عقدٌ
    # يفحص النصّ وحده كان ليُخضِّر ذلك حتى بعد إسكات الجملة.
    for concept, forbidden in (contract.get("final_kc_state_not") or {}).items():
        entry = (tutor_state.get("kc_progress") or {}).get(concept) or {}
        assert entry.get("state") != forbidden, (
            f"[{contract['id']}] الحالة الدائمة للمفهوم {concept!r} صارت "
            f"{forbidden!r} — النموذج المعرفي سجّل إتقاناً لم يحدث.\n"
            f"--- kc_progress ---\n{tutor_state.get('kc_progress')}"
        )


def test_every_contract_declares_an_issue() -> None:
    """القاعدة الدائمة: كل عقد يُشير إلى بلاغه — لا عقود يتيمة بلا أثر."""
    assert _CONTRACTS, "لا عقود ترانسكريبت — المجلد يجب ألّا يكون فارغاً"
    for contract in _CONTRACTS:
        assert contract.get("issue"), f"العقد {contract.get('id')!r} بلا حقل issue"
        assert contract.get("turns"), f"العقد {contract.get('id')!r} بلا أدوار"
