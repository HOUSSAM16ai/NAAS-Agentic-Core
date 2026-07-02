#!/usr/bin/env python3
"""
D-153 / ISS-120 — Pedagogical OS Constitution Gate (mandatory-existence + wiring).

يحوّل أمر المالك «يجب التأكد من وجود كل هذه التقنيات بشكل إجباري» إلى قانون CI:

1. **الدستور موجود ومكتمل**: `.memory/pedagogical_os.md` يحوي السلسلة القانونية
   + القوانين السبعة + مصفوفة الطبقات الـ16.
2. **مكوّنات الـ Core موجودة فعلاً** (ملفات حقيقية — لا ادّعاء): Routing /
   Diagnosis / TutorState / Policy / Symbolic Truth / Response Guard /
   Learning Analytics / Micro-Simulation.
3. **قواعد D-153 الدائمة مُسلَّكة** (نصياً — static، بلا استيراد app):
   a. الاستخراج لا يرى نثر الحل: `load_exercise_questions_only` في كل مسارات
      المحرك الرمزي بالـ orchestrator_client (≥ 6 مواقع) + المُحمِّل معرَّف.
   b. بوّابة المقامات تقرأ LaTeX: `_stated_denominators` + نمط `\\frac`.
   c. حارس الكيان الوهمي في التركيبة المختلطة (probability_skill).
   d. الحيرة المجرّدة ليست إجابة: `_is_bare_confusion` في
      pedagogical_policy_skill **و** socratic_evaluator_skill.
   e. حارس التكرار على مسار محرّك حالة الفهم (`_recently_emitted` + مرساة
      `last_step_emitted`).
   f. `inert` boolean-only في الواجهة (لا صيغة نصية "true"/"false").

Exit codes: 0 — clean | 1 — violation.
Usage: python scripts/fitness/check_pedagogical_os.py

ملاحظة تصميمية: هذه البوّابة **static-text صرفة** (لا تستورد من app/) كي تعمل
حتى في البيئات المتدهورة (sandbox بلا pydantic) — نمط `db_bridge.py`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _pass(msg: str) -> None:
    print(f"✅ {msg}")


def _read(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        _fail(f"missing file: {rel}")
        return ""
    return p.read_text(encoding="utf-8")


# ── 1) الدستور موجود ومكتمل ─────────────────────────────────────────────────
def check_constitution_document() -> None:
    doc = _read(".memory/pedagogical_os.md")
    if not doc:
        return
    required = [
        "الطالب لا يرسل سؤالاً إلى النظام",  # الجملة الدستورية
        "Pedagogical Policy",  # السلسلة القانونية
        "Response Guard",
        "Learning Update",
        "القوانين السبعة",  # القوانين
        "التعليم قبل الإجابة",
        "الحقيقة الرمزية قبل اللغة",
        "التوسعة تخدم العقل",
        "مصفوفة التقنيات الإلزامية",  # مصفوفة الطبقات
        "قاعدة المليارات",
        "load_exercise_questions_only",
    ]
    missing = [r for r in required if r not in doc]
    if missing:
        _fail(f"pedagogical_os.md incomplete — missing: {missing}")
    else:
        _pass("constitution document present and complete (.memory/pedagogical_os.md)")


# ── 2) مكوّنات الـ Core موجودة فعلاً (الطبقات الـ16 — الملفات الحقيقية) ─────────
_CORE_FILES: dict[str, str] = {
    "Routing/SupervisorNode": "app/services/chat/graph/nodes/supervisor.py",
    "Routing/OrchestratorClient": "app/infrastructure/clients/orchestrator_client.py",
    "Routing/local_graph": "app/services/chat/local_graph.py",
    "Diagnosis/ConceptDiagnosisSkill": "app/services/skills/concept_diagnosis_skill.py",
    "Diagnosis/SemanticProperty+MisconceptionGraph": "app/services/skills/semantic_property_skill.py",
    "Diagnosis/StudentStateSkill": "app/services/skills/student_state_skill.py",
    "Diagnosis/SocraticEvaluatorSkill": "app/services/skills/socratic_evaluator_skill.py",
    "TutorState/ORM": "app/core/domain/tutor_state.py",
    "TutorState/Service": "app/services/analytics/tutor_state_service.py",
    "TutorState/UnderstandingState": "app/services/skills/understanding_state_skill.py",
    "Policy/Engine": "app/services/skills/pedagogical_policy_engine.py",
    "Policy/Skill": "app/services/skills/pedagogical_policy_skill.py",
    "Policy/EscalationMatrix": "app/services/skills/pedagogical_escalation_skill.py",
    "Policy/DialogueManager": "app/services/skills/dialogue_manager_skill.py",
    "Policy/AdaptivePedagogy": "app/services/skills/adaptive_pedagogy_skill.py",
    "SymbolicTruth/ProbabilityCalculator": "app/services/skills/probability_skill.py",
    "MicroSimulation": "app/services/skills/micro_simulation_skill.py",
    "Guard/AnswerRedaction": "app/services/skills/answer_redaction_skill.py",
    "Guard/ContentIntegrity": "app/services/skills/content_integrity_skill.py",
    "Guard/OutputFirewall": "app/services/skills/output_firewall.py",
    "Guard/TopicLock": "app/services/skills/topic_lock.py",
    "Guard/ArabicStreamGuard": "app/services/skills/arabic_stream_guard.py",
    "Analytics/BKT": "app/services/skills/bkt_engine.py",
    "Analytics/LearningPath": "app/services/skills/learning_path_skill.py",
    "Analytics/TutorMetrics": "app/services/skills/tutor_metrics.py",
    "Memory/routing_philosophy": ".memory/routing_philosophy.md",
    "Memory/decisions": ".memory/decisions.md",
    "Memory/issues": ".memory/issues.md",
    "Memory/roadmap": ".memory/roadmap.md",
}


def check_core_components_exist() -> None:
    missing = [f"{name} ({rel})" for name, rel in _CORE_FILES.items() if not (ROOT / rel).exists()]
    if missing:
        _fail(f"mandatory Core components missing: {missing}")
    else:
        _pass(f"all {len(_CORE_FILES)} mandatory Core components exist on disk")


# ── 3a) الاستخراج لا يرى نثر الحل ────────────────────────────────────────────
def check_questions_only_extraction() -> None:
    retrieval = _read("app/services/capabilities/exercise_retrieval.py")
    if "def load_exercise_questions_only(" not in retrieval:
        _fail("load_exercise_questions_only missing from exercise_retrieval.py")
        return
    client = _read("app/infrastructure/clients/orchestrator_client.py")
    calls = client.count("load_exercise_questions_only(")
    if calls < 6:
        _fail(
            f"orchestrator_client uses load_exercise_questions_only only {calls}×"
            " (expected ≥ 6 — solution prose must never feed entity extraction)"
        )
        return
    # مرجع RAG-Grounded (D-145) يبقى بالمحتوى الكامل — مقصود.
    if "load_exercise_content(_decision.matched_entry)" not in client:
        _fail("D-145 RAG reference no longer loads full official content (should stay full)")
        return
    _pass(f"entity extraction is solution-free ({calls} questions-only call sites; RAG keeps full)")


# ── 3b) بوّابة المقامات تقرأ LaTeX ───────────────────────────────────────────
def check_latex_aware_denominator_gate() -> None:
    skill = _read("app/services/skills/probability_skill.py")
    if "_stated_denominators" not in skill:
        _fail("_stated_denominators missing from probability_skill.py")
        return
    if r"frac\{(\d+)\}\{(\d+)\}" not in skill:
        _fail("denominator gate is blind to LaTeX \\frac (D-152 regression)")
        return
    if skill.count("cls._stated_denominators(combined)") < 2:
        _fail("both combination builders must call the shared _stated_denominators gate")
        return
    _pass("denominator validation gate parses bare N/M AND LaTeX \\frac (both builders)")


# ── 3c) حارس الكيان الوهمي ───────────────────────────────────────────────────
def check_phantom_entity_guard() -> None:
    skill = _read("app/services/skills/probability_skill.py")
    if "حارس الكيان الوهمي في التركيبة المختلطة" not in skill:
        _fail("mixed-composition phantom-entity guard missing from _extract_count_entities")
        return
    if "stated_total == color_sum" not in skill:
        _fail("phantom guard logic (stated_total == color_sum) missing")
        return
    _pass("mixed-composition phantom-entity guard wired (numbered entities dropped)")


# ── 3d) الحيرة المجرّدة ليست إجابة ───────────────────────────────────────────
def check_confusion_never_an_answer() -> None:
    policy = _read("app/services/skills/pedagogical_policy_skill.py")
    evaluator = _read("app/services/skills/socratic_evaluator_skill.py")
    ok = True
    if "_is_bare_confusion" not in policy or "_BARE_CONFUSION_MARKERS" not in policy:
        _fail("pedagogical_policy_skill: bare-confusion guard missing")
        ok = False
    elif "_is_bare_confusion(t)" not in policy.split("def is_response_to_socratic", 1)[-1]:
        _fail("is_response_to_socratic does not consult _is_bare_confusion")
        ok = False
    if "_is_bare_confusion" not in evaluator:
        _fail("socratic_evaluator_skill: bare-confusion guard missing")
        ok = False
    if ok:
        _pass("bare confusion is never an answer (policy + evaluator both guarded)")


# ── 3e) حارس التكرار على مسار محرّك حالة الفهم ────────────────────────────────
def check_understanding_state_repetition_guard() -> None:
    client = _read("app/infrastructure/clients/orchestrator_client.py")
    marker = "حارس التكرار على مسار محرّك حالة الفهم"
    if marker not in client:
        _fail("understanding-state emit path lacks the ISS-120 repetition guard")
        return
    tail = client.split(marker, 1)[1][:1800]
    if "_recently_emitted(_direct" not in tail or "last_step_emitted" not in tail:
        _fail("repetition guard incomplete (needs _recently_emitted + last_step_emitted anchor)")
        return
    us_skill = _read("app/services/skills/understanding_state_skill.py")
    if "rep_snippets" not in us_skill:
        _fail("_explain_count does not count representation snippets (level stuck → repeats)")
        return
    _pass("understanding-state path guarded against verbatim repetition + level progresses")


# ── 3f) inert boolean-only ───────────────────────────────────────────────────
def check_inert_boolean_only() -> None:
    string_inert = re.compile(r"inert=\{[^}]*['\"](?:true|false)['\"]")
    offenders: list[str] = []
    frontend_app = ROOT / "frontend" / "app"
    for path in frontend_app.rglob("*.jsx"):
        if string_inert.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(ROOT)))
    for path in frontend_app.rglob("*.js"):
        if string_inert.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(ROOT)))
    if offenders:
        _fail(f"string-form inert found (React 19 boolean attribute): {offenders}")
    else:
        _pass("inert is boolean-only across the frontend")


def main() -> None:
    print("=== Pedagogical OS Constitution Gate (D-153 / ISS-120) ===")
    check_constitution_document()
    check_core_components_exist()
    check_questions_only_extraction()
    check_latex_aware_denominator_gate()
    check_phantom_entity_guard()
    check_confusion_never_an_answer()
    check_understanding_state_repetition_guard()
    check_inert_boolean_only()
    if _FAILURES:
        print(f"\n=== ❌ {len(_FAILURES)} Pedagogical OS violation(s) ===")
        sys.exit(1)
    print("\n=== ✅ All Pedagogical OS constitution checks passed ===")


if __name__ == "__main__":
    main()
