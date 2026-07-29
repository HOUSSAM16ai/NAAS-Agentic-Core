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

يُشغَّل **المقطع الحتمي** من السلسلة (حتى `_stage_concept_example`). هذه هي المراحل
التي تُنتج جواب المعلّم بلا LLM ولا شبكة — وهي بالضبط المراحل التي وقعت فيها الكوارث
الثلاث. المراحل اللاحقة (الاسترجاع/الـ fallback/الـ LLM) خارج نطاق العقد عمداً: عقدٌ
يعتمد على LLM ليس عقداً.
"""

import asyncio
from pathlib import Path
from typing import Any

import pytest
import yaml

TRANSCRIPTS_DIR = Path(__file__).parent / "transcripts"

#: المقطع الحتمي من سلسلة المراحل (بترتيب `chat_turn.py` — الترتيب هو العقد).
_DETERMINISTIC_STAGES = (
    "_stage_policy_gate",
    "_stage_greeting",
    "_stage_question_only",
    "_stage_computational",
    "_stage_escalation_matrix",
    "_stage_definitional",
    "_stage_concept_example",
)


def _load_contracts() -> list[dict[str, Any]]:
    """يقرأ كل عقود الترانسكريبت المُلتزَمة."""
    return [
        yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(TRANSCRIPTS_DIR.glob("*.yaml"))
    ]


_CONTRACTS = _load_contracts()


async def _run_turn(client: Any, question: str, history: list[dict[str, str]]) -> str:
    """يُشغّل المقطع الحتمي لدورٍ واحد ويُعيد نصّ المعلّم كما يصل الطالب."""
    from app.infrastructure.clients.orchestrator.turn_context import TurnContext

    ctx = TurnContext(
        question=question,
        user_id=1,
        conversation_id=1,
        history_messages=list(history),
        context={},
    )
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
    return "".join(chunks)


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
    for index, turn in enumerate(contract["turns"], start=1):
        question = turn["student"]
        answer = asyncio.run(_run_turn(client, question, history))
        where = f"[{contract['id']} turn {index}] {question!r}"

        if turn.get("must_answer"):
            assert answer.strip(), f"{where}: الدور لم يُنتج جواباً حتمياً إطلاقاً"

        for needle in turn.get("must_contain", ()):
            assert needle in answer, f"{where}: غاب {needle!r} عن الجواب.\n--- الجواب ---\n{answer}"

        for needle in turn.get("must_not_contain", ()):
            assert needle not in answer, (
                f"{where}: ظهر الممنوع {needle!r}.\n--- الجواب ---\n{answer}"
            )

        if turn.get("must_differ_from_previous") and previous_answer:
            assert answer.strip() != previous_answer.strip(), (
                f"{where}: الجواب نسخة حرفية من الدور السابق — «صفر تكرار حرفي»."
                f"\n--- الجواب ---\n{answer}"
            )

        forbidden_head = turn.get("must_not_start_with")
        if forbidden_head:
            assert not answer.strip().startswith(forbidden_head), (
                f"{where}: الجواب بدأ بـ {forbidden_head!r} — "
                f"سؤال تعريفي لا يُجاب بمثالٍ عارٍ.\n--- الجواب ---\n{answer}"
            )

        history.append({"role": "user", "content": question})
        if answer.strip():
            history.append({"role": "assistant", "content": answer})
            previous_answer = answer


def test_every_contract_declares_an_issue() -> None:
    """القاعدة الدائمة: كل عقد يُشير إلى بلاغه — لا عقود يتيمة بلا أثر."""
    assert _CONTRACTS, "لا عقود ترانسكريبت — المجلد يجب ألّا يكون فارغاً"
    for contract in _CONTRACTS:
        assert contract.get("issue"), f"العقد {contract.get('id')!r} بلا حقل issue"
        assert contract.get("turns"), f"العقد {contract.get('id')!r} بلا أدوار"
