#!/usr/bin/env python3
"""verify_d159_live.py — التحقق الحي من الهياكل المعرفية الحقيقية (D-159).

يستدعي **الكود الحقيقي** (لا stubs): محرّك الدور متعدد العُقد فوق المخطط المُهيكَل +
FSM التصعيد الدائم + سلطة الحالة الدائمة في understanding_state + اجتياز الجذر عبر
حواف الـ graph — مقابل تمرين BAC-2024 الرسمي (المحرك الرمزي، صفر LLM).

Usage (تُضبط env الاختبار تلقائياً إن غابت):
    python3 scripts/verify_d159_live.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-pipeline-secure-length")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("LLM_MOCK_MODE", "1")
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_ROLE_KEY", "dummy")

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f" — {detail}" if detail and not cond else ""))


def _apply_delta(tutor_state: dict, delta: dict | None) -> None:
    """يحاكي دمج record_turn (مفتاح-مفتاح) + تقدّم turn_count — دورة حياة حقيقية."""
    kcp = tutor_state.setdefault("kc_progress", {})
    for key, val in (delta or {}).items():
        kcp[key] = val
    tutor_state["turn_count"] = int(tutor_state.get("turn_count") or 0) + 1
    tutor_state.pop("kc_progress_delta", None)


def main() -> None:
    from app.infrastructure.clients.orchestrator_client import (
        OrchestratorClient as TutorClient,
    )
    from app.services.skills.answer_redaction_skill import redact_final_answers
    from app.services.skills.kc_progress_schema import (
        KCEntry,
        escalation_levels_of,
        parse_kc_entry,
        pending_of,
    )
    from app.services.skills.pedagogical_escalation_skill import (
        EscalationInput,
        get_pedagogical_escalation_skill,
    )
    from app.services.skills.semantic_property_skill import (
        MISCONCEPTION_EDGES,
        diagnose_root,
    )
    from app.services.skills.understanding_state_skill import get_understanding_state_skill

    print("== A) المخطط المُهيكَل (WP-A) ==")
    legacy = {"state": "explained", "attempts": 2, "evidence": "weak"}
    entry = parse_kc_entry(legacy)
    check("A1 dict قديم (قبل D-159) يُقرأ بأمان", entry.state == "explained" and entry.attempts == 2)
    check(
        "A2 قيم فاسدة تُطبَّع للافتراض",
        parse_kc_entry({"state": "garbage"}).state == "not_addressed",
    )
    round_trip = parse_kc_entry(KCEntry(state="understood", attempts=3).to_dict())
    check(
        "A3 to_dict/parse round-trip", round_trip.state == "understood" and round_trip.attempts == 3
    )
    check(
        "A4 escalation_levels تُقرأ كأعداد مرتّبة",
        escalation_levels_of({"c": {"escalation_levels": ["L3", "L1"]}}, "c") == [1, 3],
    )

    print("== B) محرّك الدور متعدد العُقد A→B (WP-A/WP-E) ==")
    tutor_state: dict = {"kc_progress": {}, "turn_count": 0}
    history: list[dict[str, str]] = []
    emitted: list[str] = []

    def turn(question: str) -> str | None:
        text, delta = TutorClient._cognitive_turn(question, history, tutor_state)
        if text:
            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": text})
            emitted.append(text)
            _apply_delta(tutor_state, delta)
        return text

    t1 = turn("كيف نحسب الحادثة A")
    check(
        "B1 أول تفاعل ⇒ سؤال تشخيصي (لا تفريغ)",
        bool(t1) and "سؤال واحد قبل أي حساب" in (t1 or ""),
    )
    check("B1b لا أرقام محسوبة في الـ probe", t1 is not None and "165" not in t1 and "14" not in t1)

    t2 = turn("هل هي 14 على 165")
    check(
        "B2 الإجابة الصحيحة ⇒ اعتراف + تقدّم للحادثة B",
        bool(t2) and "أحسنت" in (t2 or "") and "الحادثة B" in (t2 or ""),
    )
    kcp = tutor_state["kc_progress"]
    check(
        "B2b عقدة A صارت understood",
        parse_kc_entry(kcp.get("prob_event_a")).state == "understood",
    )
    check(
        "B2c عقدة B بُذرت (probe مُسلَّم)",
        "diagnostic_probe" in parse_kc_entry(kcp.get("prob_event_b")).representations_delivered,
    )
    pend = pending_of(kcp)
    check("B2d السؤال المعلّق صار على B", pend is not None and pend[0] == "prob_event_b")

    t3 = turn("الكرات الفردية عددها 8")
    check(
        "B3 خطوة B صحيحة (odd=8) ⇒ اعتراف + خطوة النسبة",
        bool(t3) and "الحادثة B" in (t3 or ""),
    )

    t4 = turn("هل هي 56 من 165")
    check("B4 إجابة B النهائية ⇒ اعتراف + إقفال العقدة", bool(t4) and "أحسنت" in (t4 or ""))
    check(
        "B4b عقدة B صارت understood",
        parse_kc_entry(kcp.get("prob_event_b")).state == "understood",
    )
    check("B5 صفر تكرار حرفي عبر الأدوار", len(set(emitted)) == len(emitted))
    check(
        "B6 كل نصوص B تَنجو من حجب D-113",
        redact_final_answers(t3 or "")[0] == (t3 or "")
        and redact_final_answers(t4 or "")[0] == (t4 or ""),
    )

    print("== C) FSM التصعيد الدائم (WP-B) ==")
    esk = get_pedagogical_escalation_skill()
    base = {
        "concept_id": "conditional_probability",
        "title": "الاحتمال الشرطي",
        "definition": "الاحتمال الشرطي هو إعادة حساب داخل فضاء تقلّص بعد علمنا بوقوع حادثة.",
        "example": "مثال: 10 طلاب، 6 بنظّارة — بعلم النادي العلمي يتقلّص الفضاء.",
        "micro_sim": "محاكاة: 5 أعضاء 3 بنظّارة ⇒ 3 من 5.",
        "intent": "confusion",
        "history": [],  # نافذة فارغة — «إعادة تشغيل» — الذاكرة من الحالة الدائمة فقط
    }
    d_no_mem = esk.decide(EscalationInput(**base))
    d_mem = esk.decide(EscalationInput(**base, delivered_levels=[1]))
    check(
        "C1 بلا ذاكرة دائمة ⇒ L1؛ معها ([L1]) ⇒ L2 (رغم نافذة فارغة)",
        d_no_mem.strategy_level == 1 and d_mem.strategy_level == 2,
        f"no_mem=L{d_no_mem.strategy_level} mem=L{d_mem.strategy_level}",
    )
    d_exh = esk.decide(EscalationInput(**base, delivered_levels=[1, 2, 3]))
    check("C2 كل الرُّتب مُسلَّمة دائمياً ⇒ exhausted/apply (لا تكرار)", d_exh.action == "exhausted")

    print("== D) سلطة الحالة الدائمة في understanding_state (WP-C) ==")
    combo = TutorClient._load_canonical_combinations("كيف نحسب الحادثة A", [])
    check(
        "D0 المحرك الرمزي حمّل التمرين الرسمي",
        combo is not None and int(combo.total_combinations) == 165,
    )
    uss = get_understanding_state_skill()
    kcs = uss.knowledge_components(combo)
    first_kc = sorted(kcs, key=lambda c: c.order)[0]
    states_no_mem = uss.understanding_state([], kcs)
    states_mem = uss.understanding_state(
        [], kcs, kc_progress={first_kc.kc_id: {"state": "understood"}}
    )
    check(
        "D1 السجل الدائم يرفع الحالة رغم نافذة فارغة",
        states_no_mem.get(first_kc.kc_id) == "not_addressed"
        and states_mem.get(first_kc.kc_id) == "understood",
    )
    dec = uss.decide(
        question="لم أفهم",
        history=[
            {"role": "assistant", "content": first_kc.representations[0]},
            {"role": "user", "content": "لم أفهم"},
        ],
        combo=combo,
        kc_progress={first_kc.kc_id: {"state": "explained"}},
    )
    check("D2 decide يقبل kc_progress ويعمل", dec is None or bool(dec.text))

    print("== E) اجتياز الجذر عبر الحواف (WP-D) ==")
    check("E0 الحواف موجودة (graph حقيقي لا dict)", len(MISCONCEPTION_EDGES) >= 10)
    weak_kcp = {"product_meaning": {"state": "explained", "evidence": "weak"}}
    root = diagnose_root("product_zero", weak_kcp)
    check(
        "E1 جذر product_zero الضعيف = product_meaning",
        root is not None and root.root_concept_id == "product_meaning",
    )
    check(
        "E2 نصّ تدخّل الجذر يَنجو من حجب D-113",
        root is not None
        and redact_final_answers(root.intervention_text)[0] == root.intervention_text,
    )
    check("E3 بلا سجل دائم ⇒ لا تدخّل أعمى (None)", diagnose_root("product_zero", {}) is None)
    deep_kcp = {
        "product_meaning": {"state": "explained", "evidence": "weak"},
        "ball_number_mapping": {"state": "explained", "evidence": "weak"},
    }
    root2 = diagnose_root("product_zero", deep_kcp)
    check("E4 الاجتياز يجد جذراً (deterministic DFS)", root2 is not None)

    print()
    print(f"== RESULT: {len(PASS)} PASS / {len(FAIL)} FAIL ==")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
        sys.exit(1)


if __name__ == "__main__":
    main()
