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
    tail = client.split(marker, 1)[1][:2600]
    # D-154: الحارس صار سلسلة بدائل عبر `_d153_dup` (يستدعي _recently_emitted داخلياً).
    has_guard = "_recently_emitted(_direct" in tail or "_d153_dup(_direct)" in tail
    if not has_guard or "last_step_emitted" not in tail:
        _fail("repetition guard incomplete (needs dedup check + last_step_emitted anchor)")
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


# ── D-154 (ISS-121): الكشف التدريجي + حارس تكرار محايد للحجب + عرض سليم ────────
def check_progressive_disclosure() -> None:
    """القانون الرابع «التلميح قبل الحل» مُنفَّذ بنيوياً (roadmap §7: صفر كشف)."""
    client = _read("app/infrastructure/clients/orchestrator_client.py")
    ok = True
    if "فاحتمال الحادثة A هو {same} من كل {total}" in client:
        _fail("symbolic reveal still prints the final ratio (answer dump)")
        ok = False
    if "ركّب الاحتمال **بنفسك**" not in client:
        _fail("reveal generation-question tail missing")
        ok = False
    proc = client.split("else:  # procedure — ISS-121 (D-154): سُلّم لا تفريغ", 1)
    if len(proc) != 2 or "_build_symbolic_step(_proc_combo, None)" not in proc[1][:1300]:
        _fail("procedure intent must enter the ladder (step), not the full reveal")
        ok = False
    # ISS-122 (D-155): «التشخيص قبل الشرح» — probe التشخيص يسبق الخطوة المحسوبة.
    if len(proc) == 2:
        tail = proc[1][:1300]
        probe_i = tail.find("_build_diagnostic_probe(_proc_combo)")
        step_i = tail.find("_build_symbolic_step(_proc_combo, None)")
        if probe_i < 0 or step_i < 0 or probe_i > step_i:
            _fail("diagnostic probe must come before the computed step (D-155)")
            ok = False
    if ok:
        _pass("progressive disclosure enforced (no final-answer dump; procedure → ladder)")


def check_redaction_neutral_dedup() -> None:
    """حارس التكرار محايد لتحويل الحجب (المحفوظ «؟» ≡ المبثوث بالأرقام) + سلسلة بدائل."""
    client = _read("app/infrastructure/clients/orchestrator_client.py")
    dm = _read("app/services/skills/dialogue_manager_skill.py")
    ok = True
    if 'r"[\\d؟?]+"' not in client:
        _fail("_norm_for_dedup lacks redaction-neutral placeholder normalization")
        ok = False
    if 'r"[\\d؟?]+"' not in dm:
        _fail("dialogue_manager _norm lacks redaction-neutral normalization")
        ok = False
    if (
        "def _is_dup(t: str) -> bool:" not in client
        or "def _d153_dup(t: str) -> bool:" not in client
    ):
        _fail("never-emit-dup alternative ladders missing")
        ok = False
    if ok:
        _pass("dedup guard is redaction-neutral + never emits a duplicate (alternative ladders)")


def check_math_display_integrity() -> None:
    """الصيغ الحتمية LaTeX (LTR-معزولة — لا بعثرة bidi) + لا نسخ مضاعف على الموبايل."""
    client = _read("app/infrastructure/clients/orchestrator_client.py")
    css = _read("frontend/app/globals.css")
    ok = True
    if "C_{{{c}}}^{{{k}}}" not in client:
        _fail("_fmt_comb no longer emits LaTeX (bidi scrambling returns)")
        ok = False
    mathml_rule = css.split(".katex-mathml {", 1)
    if len(mathml_rule) != 2 or "display: none !important" not in mathml_rule[1].split("}")[0]:
        _fail(".katex-mathml must be display:none (mobile copy duplication)")
        ok = False
    if ok:
        _pass("deterministic math renders as LaTeX; katex-mathml hidden (no copy doubling)")


def check_probability_tutor_port() -> None:
    """M10-S2.1: الـ port مستقل داخل الـ orchestrator وخلف علم (FLAGGED صادق)."""
    port_path = "microservices/orchestrator_service/src/services/overmind/probability_tutor.py"
    port = _read(port_path)
    search = _read("microservices/orchestrator_service/src/services/overmind/graph/search.py")
    ok = True
    if not port:
        return
    if "from app" in port or "import app" in port:
        _fail("probability_tutor port must not import from app.* (independence)")
        ok = False
    if "ORCHESTRATOR_PROB_TUTOR_ENABLED" not in search:
        _fail("SynthesizerNode hook for probability_tutor missing / not flag-gated")
        ok = False
    if "من كل {" in port:
        _fail("orchestrator port leaks the final ratio")
        ok = False
    if ok:
        _pass("M10-S2.1 probability_tutor port independent + flag-gated in SynthesizerNode")


def check_numeric_answer_verification() -> None:
    """ISS-122 (D-155): الحقيقة الرمزية تحكم إجابة الطالب الرقمية («هل هي 14 من 165»)."""
    client = _read("app/infrastructure/clients/orchestrator_client.py")
    ok = True
    if "def _verify_numeric_answer(" not in client:
        _fail("_verify_numeric_answer missing — numeric student answers invisible")
        ok = False
    if "def _pending_focus_from_history(" not in client:
        _fail("_pending_focus_from_history missing — no pending-question derivation")
        ok = False
    if "if same in nums and total in nums:" not in client:
        _fail("final-ratio verdict must compare combo-derived numbers (no hardcoding)")
        ok = False
    if "أحسنت! ✅ إجابتك صحيحة تماماً" not in client:
        _fail("explicit acknowledgement of a correct final answer missing")
        ok = False
    if ok:
        _pass("numeric answers judged by the symbolic engine + explicit acknowledge-and-advance")


def check_conceptual_escapes_socratic() -> None:
    """ISS-122 (D-155): سؤال مفاهيمي أثناء الحوار السقراطي ⇒ شرح العلاقة (D-125)، ليس إجابة."""
    client = _read("app/infrastructure/clients/orchestrator_client.py")
    ok = True
    gate = client.split(
        "if (\n            self._in_socratic_dialogue(question, history_messages)", 1
    )
    if len(gate) != 2 or "_detect_conceptual_question(question)" not in gate[1][:400]:
        _fail("socratic interception must exclude conceptual questions (D-155)")
        ok = False
    if "_QUESTION_OPENERS_NOT_ANSWERS" not in client:
        _fail("interrogative-opener guard missing at the socratic gate")
        ok = False
    if len(gate) == 2 and "_QUESTION_OPENERS_NOT_ANSWERS" not in gate[1][:600]:
        _fail("interrogative-opener guard must be applied at the socratic gate itself")
        ok = False
    if ok:
        _pass("conceptual/interrogative turns escape the socratic swallow (D-125 reachable)")


def check_reveal_last_in_ladders() -> None:
    """ISS-122 (D-155): الإنقاذ الكامل (reveal superset) آخر بدائل السُّلّم دائماً."""
    client = _read("app/infrastructure/clients/orchestrator_client.py")
    ok = True
    for closure in ("def _is_dup(t: str) -> bool:", "def _d153_dup(t: str) -> bool:"):
        seg = client.split(closure, 1)
        tail = seg[1][:2600] if len(seg) == 2 else ""
        rev = tail.find("_build_symbolic_reveal")
        gen = tail.find("جرّب بنفسك: ركّب البسط")  # قد تلتفّ بقية الجملة على سطر تالٍ
        if rev < 0 or gen < 0 or rev < gen:
            _fail(f"reveal must be the LAST ladder alternative after {closure!r}")
            ok = False
    if ok:
        _pass("reveal is the last ladder alternative in both dedup chains (D-155)")


def main() -> None:
    print(
        "=== Pedagogical OS Constitution Gate (D-153/ISS-120 + D-154/ISS-121 + D-155/ISS-122) ==="
    )
    check_constitution_document()
    check_core_components_exist()
    check_questions_only_extraction()
    check_latex_aware_denominator_gate()
    check_phantom_entity_guard()
    check_confusion_never_an_answer()
    check_understanding_state_repetition_guard()
    check_inert_boolean_only()
    check_progressive_disclosure()
    check_redaction_neutral_dedup()
    check_math_display_integrity()
    check_probability_tutor_port()
    check_numeric_answer_verification()
    check_conceptual_escapes_socratic()
    check_reveal_last_in_ladders()
    if _FAILURES:
        print(f"\n=== ❌ {len(_FAILURES)} Pedagogical OS violation(s) ===")
        sys.exit(1)
    print("\n=== ✅ All Pedagogical OS constitution checks passed ===")


if __name__ == "__main__":
    main()
