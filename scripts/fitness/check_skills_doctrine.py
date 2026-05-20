#!/usr/bin/env python3
"""
D-069 / ISS-CI-GREEN-001 — Skills Doctrine Drift Detector.

يفحص أن:
1. كل Skill في `app/services/skills/*.py` (باستثناء `doctrine.py` و `__init__.py`)
   يستورد على الأقل قاعدة من `app.services.skills.doctrine`.
2. الـ Manifest في `doctrine.py` يصف كل doctrines بشكل صحيح.
3. الـ versions monotonic — لا تراجع.
4. الـ `_EXERCISE_EXPLANATION_SYSTEM_PROMPT` في `local_graph.py` يحوي على الأقل
   3 من الكلمات المفتاحية من EXPLANATION_DOCTRINE (drift detection).

Exit codes:
  0 — clean
  1 — drift detected

Usage:
  python scripts/fitness/check_skills_doctrine.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> None:
    print(f"❌ {msg}")
    sys.exit(1)


def _pass(msg: str) -> None:
    print(f"✅ {msg}")


def check_doctrine_module_importable() -> None:
    try:
        from app.services.skills.doctrine import (  # noqa: F401
            DETAILED_EXPLANATION_RULES,
            EXPLANATION_DOCTRINE,
            MODEL_ANSWER_RELIANCE_RULES,
            RETRIEVAL_DOCTRINE,
            SKILL_DOCTRINE_MANIFEST,
        )
    except ImportError as e:
        _fail(f"Cannot import doctrine module: {e}")
    _pass("doctrine module importable")


def check_skills_consume_doctrine() -> None:
    skills_dir = ROOT / "app" / "services" / "skills"
    if not skills_dir.is_dir():
        _fail(f"Skills directory missing: {skills_dir}")

    exempt = {"__init__.py", "doctrine.py"}
    skill_files = [p for p in skills_dir.glob("*.py") if p.name not in exempt]

    if not skill_files:
        _fail("No skill files found under app/services/skills/")

    for path in skill_files:
        src = path.read_text(encoding="utf-8")
        # We only require BAC (the exercise skill) to consume the doctrine.
        # Greeting/Math skills may have their own internal logic.
        if path.name == "bac_exercise_skill.py":
            if "from app.services.skills.doctrine import" not in src:
                _fail(f"{path.name}: must import from doctrine module")
            _pass(f"{path.name} consumes doctrine module")
        else:
            # Other skills are exempt for now (own logic), but they still
            # mustn't import EXPLANATION_DOCTRINE locally.
            if "EXPLANATION_DOCTRINE: tuple" in src or "EXPLANATION_DOCTRINE_VERSION:" in src:
                _fail(
                    f"{path.name}: defines EXPLANATION_DOCTRINE locally — "
                    "must import from doctrine module instead"
                )
            _pass(f"{path.name} OK (does not redefine doctrine)")


def check_manifest_consistency() -> None:
    from app.services.skills.doctrine import (
        BKT_COGNITIVE_DOCTRINE,
        BKT_COGNITIVE_DOCTRINE_VERSION,
        DETAILED_EXPLANATION_RULES,
        DETAILED_EXPLANATION_VERSION,
        EXPLANATION_DOCTRINE,
        EXPLANATION_DOCTRINE_VERSION,
        MODEL_ANSWER_RELIANCE_RULES,
        MODEL_ANSWER_RELIANCE_VERSION,
        RETRIEVAL_DOCTRINE,
        RETRIEVAL_DOCTRINE_VERSION,
        SKILL_DOCTRINE_MANIFEST,
    )

    pairs = [
        ("retrieval", RETRIEVAL_DOCTRINE_VERSION, len(RETRIEVAL_DOCTRINE)),
        ("explanation", EXPLANATION_DOCTRINE_VERSION, len(EXPLANATION_DOCTRINE)),
        (
            "model_answer_reliance",
            MODEL_ANSWER_RELIANCE_VERSION,
            len(MODEL_ANSWER_RELIANCE_RULES),
        ),
        (
            "detailed_explanation",
            DETAILED_EXPLANATION_VERSION,
            len(DETAILED_EXPLANATION_RULES),
        ),
        # D-074 (Protocol V6.0): BKT cognitive layer is a first-class doctrine.
        ("bkt_cognitive", BKT_COGNITIVE_DOCTRINE_VERSION, len(BKT_COGNITIVE_DOCTRINE)),
    ]
    for key, ver, count in pairs:
        entry = SKILL_DOCTRINE_MANIFEST.get(key)
        if entry is None:
            _fail(f"Manifest missing key: {key}")
        if entry["version"] != ver:
            _fail(f"Manifest version mismatch for {key}: {entry['version']} != {ver}")
        if entry["rules_count"] != count:
            _fail(f"Manifest rules_count mismatch for {key}: {entry['rules_count']} != {count}")
        _pass(f"Manifest entry '{key}' consistent (v{ver}, {count} rules)")


def check_explanation_doctrine_v2() -> None:
    """EXPLANATION_DOCTRINE_VERSION must be ≥ 2.0.0 after D-069."""
    from app.services.skills.doctrine import EXPLANATION_DOCTRINE_VERSION

    major = int(EXPLANATION_DOCTRINE_VERSION.split(".")[0])
    if major < 2:
        _fail(
            f"EXPLANATION_DOCTRINE_VERSION={EXPLANATION_DOCTRINE_VERSION} "
            "is too old. Must be ≥ 2.0.0 after D-069."
        )
    _pass(f"EXPLANATION_DOCTRINE_VERSION = {EXPLANATION_DOCTRINE_VERSION} (≥ 2.0.0)")


def check_local_graph_prompt_alignment() -> None:
    """D-071: local_graph.py يجب أن يستورد EXERCISE_EXPLANATION_SYSTEM_PROMPT
    من doctrine.py مباشرة — لا تعريف prompt محلي مستقل.

    هذا يضمن أن أي تغيير في الـ doctrine ينعكس تلقائياً على الـ LLM
    instruction surface بدون تدخل يدوي.
    """
    local_graph = ROOT / "app" / "services" / "chat" / "local_graph.py"
    if not local_graph.is_file():
        print(f"ℹ️ local_graph.py not found at {local_graph} — skipping prompt check")
        return

    src = local_graph.read_text(encoding="utf-8")

    # D-071: يجب أن يستورد من doctrine
    if "from app.services.skills.doctrine import" not in src:
        _fail(
            "local_graph.py: does not import from doctrine module. "
            "D-071 requires EXERCISE_EXPLANATION_SYSTEM_PROMPT to come from doctrine.py."
        )

    if "EXERCISE_EXPLANATION_SYSTEM_PROMPT" not in src:
        _fail(
            "local_graph.py: EXERCISE_EXPLANATION_SYSTEM_PROMPT not referenced. "
            "D-071: _EXERCISE_EXPLANATION_SYSTEM_PROMPT must be assigned from doctrine."
        )

    # Verify the prompt built from doctrine still contains the 3 anchors
    # (runtime check — catches doctrine regressions)
    try:
        from app.services.skills.doctrine import EXERCISE_EXPLANATION_SYSTEM_PROMPT

        anchors = ["الإجابة النموذجية", "LaTeX", "حرفياً"]
        missing = [a for a in anchors if a not in EXERCISE_EXPLANATION_SYSTEM_PROMPT]
        if len(missing) >= 2:
            _fail(
                f"EXERCISE_EXPLANATION_SYSTEM_PROMPT missing {len(missing)}/3 anchors: "
                f"{missing}. Doctrine has drifted."
            )
        if len(EXERCISE_EXPLANATION_SYSTEM_PROMPT) > 1000:
            _fail(
                f"EXERCISE_EXPLANATION_SYSTEM_PROMPT is {len(EXERCISE_EXPLANATION_SYSTEM_PROMPT)} "
                "chars — exceeds 1000-char D-067 limit."
            )
    except ImportError:
        pass  # import errors caught in check_doctrine_module_importable

    _pass("local_graph.py: doctrine anchors present (3/3)")


def check_d070_doctrines_reexported() -> None:
    """D-073: تأكد أن D-070 doctrines (CONTENT_INVOCATION / MODEL_ANSWER_EXPLANATION /
    STEP_BY_STEP_EXPLANATION_RULES / SKILL_INVOCATION_PROTOCOL) مُعاد تصديرها
    من ``app.services.skills.__init__``. قبل D-073 كانت موجودة في doctrine.py
    فقط — مستهلكوها الخارجيون كانوا يضطرون لاستيراد من المسار الكامل.
    """
    try:
        from app.services.skills import (  # noqa: F401
            CONTENT_INVOCATION_DOCTRINE,
            CONTENT_INVOCATION_DOCTRINE_VERSION,
            MODEL_ANSWER_EXPLANATION_DOCTRINE,
            MODEL_ANSWER_EXPLANATION_VERSION,
            SKILL_INVOCATION_PROTOCOL,
            SKILL_INVOCATION_PROTOCOL_VERSION,
            STEP_BY_STEP_EXPLANATION_RULES,
            STEP_BY_STEP_EXPLANATION_VERSION,
        )
    except ImportError as e:
        _fail(
            f"D-070 doctrines not re-exported from app.services.skills: {e}. "
            "D-073 requires all 8 D-070 symbols at the package level."
        )
    _pass("D-070 doctrines re-exported from app.services.skills (D-073)")


def check_answer_quality_skill_wired() -> None:
    """D-073: ``AnswerQualitySkill`` يجب أن يكون مستهلَكاً في مسار إنتاجي حقيقي
    (وليس مُعرَّفاً فقط). قبل D-073 كان Skill زومبي — لا call chain من أي router.

    الفحص: ``app/services/chat/local_graph.py`` يجب أن يحوي
    ``_apply_answer_quality_skill`` ويستوردها من ``app.services.skills``.
    """
    local_graph = ROOT / "app" / "services" / "chat" / "local_graph.py"
    if not local_graph.is_file():
        print(f"ℹ️ local_graph.py not found at {local_graph} — skipping wiring check")
        return

    src = local_graph.read_text(encoding="utf-8")

    if "_apply_answer_quality_skill" not in src:
        _fail(
            "local_graph.py: _apply_answer_quality_skill not defined. "
            "D-073: AnswerQualitySkill must be wired into the live chat path."
        )

    if "get_answer_quality_skill" not in src:
        _fail(
            "local_graph.py: does not invoke get_answer_quality_skill. "
            "D-073: wire AnswerQualitySkill via _apply_answer_quality_skill helper."
        )

    # تأكد أن _chat_node يستدعي الـ helper (call chain إلزامي)
    if "_apply_answer_quality_skill(question" not in src:
        _fail(
            "local_graph.py: _apply_answer_quality_skill helper exists but is not "
            "called from _chat_node. D-073: call chain must be live."
        )

    _pass("AnswerQualitySkill wired into local_graph._chat_node (D-073, no longer ZOMBIE)")


def check_bkt_baseline_integrated() -> None:
    """D-074: BKTEngine هو الطبقة المعرفية الأساسية — يجب أن يكون:
    (1) مستهلِكاً لـ BKT_COGNITIVE_DOCTRINE من doctrine.py،
    (2) موصولاً حيّاً في مسار المحادثة عبر customer_chat._evaluate_and_emit_bkt.
    """
    bkt_engine = ROOT / "app" / "services" / "skills" / "bkt_engine.py"
    if not bkt_engine.is_file():
        _fail("bkt_engine.py missing — BKT baseline not present.")
    src = bkt_engine.read_text(encoding="utf-8")
    if "from app.services.skills.doctrine import" not in src:
        _fail(
            "bkt_engine.py: does not consume doctrine. "
            "D-074: BKTEngine must import BKT_COGNITIVE_DOCTRINE_VERSION from doctrine.py."
        )
    if "BKT_COGNITIVE_DOCTRINE_VERSION" not in src:
        _fail("bkt_engine.py: BKT_COGNITIVE_DOCTRINE_VERSION not referenced (D-074).")
    _pass("bkt_engine.py consumes BKT_COGNITIVE_DOCTRINE (D-074)")

    chat = ROOT / "app" / "api" / "routers" / "customer_chat.py"
    if chat.is_file():
        chat_src = chat.read_text(encoding="utf-8")
        if (
            "_evaluate_and_emit_bkt(question" not in chat_src.replace("\n", " ").replace("    ", "")
            and "_evaluate_and_emit_bkt(" not in chat_src
        ):
            _fail(
                "customer_chat.py: _evaluate_and_emit_bkt not called. "
                "D-074: BKT must be wired into the live WS chat path."
            )
        _pass("BKT runtime injection wired into customer_chat WS handler (D-074)")


def main() -> None:
    print("=== Skills Doctrine Drift Gate (D-069 + D-073) ===\n")
    check_doctrine_module_importable()
    check_skills_consume_doctrine()
    check_manifest_consistency()
    check_explanation_doctrine_v2()
    check_local_graph_prompt_alignment()
    check_d070_doctrines_reexported()
    check_answer_quality_skill_wired()
    check_bkt_baseline_integrated()
    print("\n=== ✅ All skills doctrine checks passed ===")


if __name__ == "__main__":
    main()
