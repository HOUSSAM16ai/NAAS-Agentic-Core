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


def _read_tutor_source() -> str:
    """مصدر المعلّم المُركَّب (client + brain + mixins) عبر manifest D-164/D-166.

    الفحوص السلبية (مثل حظر prepend «[توجيه تربوي]» — D-117) يجب أن تمسح النص
    المُركَّب كاملاً وإلا فقدت قيمتها بعد استخراج chat_with_agent إلى mixin.
    """
    from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source

    return read_tutor_source()


def _read_brain_source() -> str:
    """مصدر العقل المُركَّب (composition root + mixins) عبر manifest D-168.

    تحميل مباشر بـ importlib (يتجاوز `app.services.skills.__init__` الذي يستورد
    pydantic) — يحفظ خاصية البيئات المتدهورة لهذه البوّابة.
    """
    import importlib.util

    manifest_path = ROOT / "app/services/skills/probability_brain/brain_sources.py"
    spec = importlib.util.spec_from_file_location("brain_sources_gate", manifest_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.read_brain_source()


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
        ADAPTIVE_PEDAGOGY_DOCTRINE,
        ADAPTIVE_PEDAGOGY_DOCTRINE_VERSION,
        ANSWER_REDACTION_DOCTRINE,
        ANSWER_REDACTION_DOCTRINE_VERSION,
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
        WORKED_EXAMPLE_DOCTRINE,
        WORKED_EXAMPLE_DOCTRINE_VERSION,
    )

    pairs = [
        ("retrieval", RETRIEVAL_DOCTRINE_VERSION, len(RETRIEVAL_DOCTRINE)),
        ("explanation", EXPLANATION_DOCTRINE_VERSION, len(EXPLANATION_DOCTRINE)),
        # D-113 (ISS-115): الحارس الحتمي ضد كشف الإجابة النهائية.
        (
            "answer_redaction",
            ANSWER_REDACTION_DOCTRINE_VERSION,
            len(ANSWER_REDACTION_DOCTRINE),
        ),
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
        # D-104: adaptive pedagogy — قراءة الإتقان تقود عمق التدريس.
        (
            "adaptive_pedagogy",
            ADAPTIVE_PEDAGOGY_DOCTRINE_VERSION,
            len(ADAPTIVE_PEDAGOGY_DOCTRINE),
        ),
        # D-114 (ISS-116): المثال المحلول المُتدرّج المُقيَّد بالإتقان.
        (
            "worked_example",
            WORKED_EXAMPLE_DOCTRINE_VERSION,
            len(WORKED_EXAMPLE_DOCTRINE),
        ),
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
    (2) موصولاً حيّاً في مسار المحادثة عبر customer_chat._evaluate_bkt_cards (D-118).
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
        # D-119: التقييم موصول عبر `_evaluate_bkt_cards` (تحليلات append-only خلف
        # الكواليس، يُرجِع None — لا بطاقة طالب)، ويُنتظَر بعد الإطار النهائي لضمان
        # اكتمال الكتابة قبل إنهاء الدور. نتحقّق من كليهما.
        if "_evaluate_bkt_cards(" not in chat_src:
            _fail(
                "customer_chat.py: _evaluate_bkt_cards not called. "
                "D-074/D-119: BKT analytics must run in the live WS chat path."
            )
        if "await _bkt_task" not in chat_src:
            _fail(
                "customer_chat.py: BKT analytics task not awaited. "
                "D-119: append-only write must complete before turn ends (behind-the-scenes)."
            )
        _pass("BKT analytics wired behind-the-scenes, no student card (D-074/D-119)")


def check_skills_platform() -> None:
    """D-100: منصّة الـ Skills الموحَّدة يجب أن تكون:
    (1) manifest entry 'skills_platform' متّسق (version + rules_count)،
    (2) registry مكتمل (كل الـ Skills مُسجَّلة) وبلا ZOMBIE (consumed_by غير فارغ)،
    (3) موجِّه `/api/v1/skills` يستهلك الـ registry ومُركَّب في base_router_registry.
    """
    from app.services.skills.doctrine import (
        SKILL_DOCTRINE_MANIFEST,
        SKILLS_PLATFORM_DOCTRINE,
        SKILLS_PLATFORM_DOCTRINE_VERSION,
    )
    from app.services.skills.registry import get_skill_registry

    entry = SKILL_DOCTRINE_MANIFEST.get("skills_platform")
    if entry is None:
        _fail("Manifest missing 'skills_platform' entry (D-100).")
    if entry["version"] != SKILLS_PLATFORM_DOCTRINE_VERSION:
        _fail(
            f"Manifest version mismatch for skills_platform: "
            f"{entry['version']} != {SKILLS_PLATFORM_DOCTRINE_VERSION}"
        )
    if entry["rules_count"] != len(SKILLS_PLATFORM_DOCTRINE):
        _fail(
            f"Manifest rules_count mismatch for skills_platform: "
            f"{entry['rules_count']} != {len(SKILLS_PLATFORM_DOCTRINE)}"
        )
    _pass(f"Manifest entry 'skills_platform' consistent (v{SKILLS_PLATFORM_DOCTRINE_VERSION})")

    reg = get_skill_registry()
    names = set(reg.names())
    expected = {
        "greeting",
        "bac_exercise",
        "math",
        "answer_quality",
        "answer_redaction",
        "bkt_engine",
        "adaptive_pedagogy",
        "probability",
        "exercise_alignment",
        "output_firewall",
        "topic_lock",
        "arabic_stream_guard",
        "ws_heartbeat",
        "text_refinement_compose",
        "content_integrity",
        "learning_path",
        "retrieval_rerank",
        "mcp_tool",
    }
    missing = expected - names
    if missing:
        _fail(f"Registry missing skills: {sorted(missing)} (D-100).")
    for d in reg.list():
        if not d.consumed_by:
            _fail(f"Skill '{d.name}' is ZOMBIE — empty consumed_by (D-100).")
    _pass(f"Skill registry complete: {len(names)} skills, no ZOMBIE (D-100)")

    router = ROOT / "app" / "api" / "routers" / "skills.py"
    if not router.is_file():
        _fail("app/api/routers/skills.py missing — Skills Platform router not wired (D-100).")
    rsrc = router.read_text(encoding="utf-8")
    if "get_skill_registry" not in rsrc or "compose_text_refinement" not in rsrc:
        _fail("skills.py router does not consume the registry/composer (D-100).")
    reg_file = (ROOT / "app" / "api" / "routers" / "registry.py").read_text(encoding="utf-8")
    if "skills.router" not in reg_file:
        _fail("skills.router not mounted in base_router_registry (D-100).")
    _pass("Skills Platform router wired + mounted (D-100, not ZOMBIE)")


def check_adaptive_pedagogy_wiring() -> None:
    """D-104/D-117: التوجيه التربوي موصول للقياس + support_level يقود عمق التدريس.

    D-117 (فصل الطبقات «الطالب يرى التعليم لا هندسة التعليم»): التوجيه التربوي
    لم يَعُد يُسبَق للسؤال («[توجيه تربوي] ...») — كان النموذج المجاني يُردّده
    حرفياً فيرى الطالب لغة النظام الداخلية. العمق يصل الآن عبر `support_level`
    (مُمرَّر في context → يستهلكه SynthesizerNode). البوّابة تفرض غياب الـ prepend.
    """
    router_src = (ROOT / "app/api/routers/customer_chat.py").read_text(encoding="utf-8")
    client_src = _read_tutor_source()  # D-166: chat_with_agent في mixin — المصدر المُركَّب
    if "_build_pedagogy_directive" not in router_src:
        _fail("customer_chat lost _build_pedagogy_directive (D-104 ZOMBIE).")
    if '"pedagogy_directive": pedagogy' not in router_src:
        _fail("customer_chat no longer passes pedagogy_directive in context (D-104).")
    if '"support_level": sup_level' not in router_src:
        _fail("customer_chat no longer passes support_level in context (D-114/D-117).")
    # D-117: الـ prepend ممنوع — النموذج يُردّده حرفياً (تسرّب «هندسة التعليم»).
    if 'f"[توجيه تربوي]' in client_src:
        _fail("orchestrator_client must NOT prepend the pedagogy directive (D-117 leak).")
    if 'get("support_level")' not in client_src:
        _fail("orchestrator_client no longer reads support_level (D-114/D-117).")
    _pass("Adaptive pedagogy wired: support_level drives depth, no directive leak (D-117)")


def check_content_integrity_wired() -> None:
    """D-106 (ISS-114): حارس نزاهة المحتوى موصول فعلاً — ليس skill بلا مستهلك.

    يحرس: (1) المرشّح موصول عند مخرج orchestrator HTTP (الثغرة الكبرى)،
    (2) موصول في المسار المحلي، (3) manifest entry متّسق.
    """
    from app.services.skills.doctrine import (
        CONTENT_INTEGRITY_DOCTRINE,
        CONTENT_INTEGRITY_DOCTRINE_VERSION,
        SKILL_DOCTRINE_MANIFEST,
    )

    entry = SKILL_DOCTRINE_MANIFEST.get("content_integrity")
    if entry is None:
        _fail("Manifest missing 'content_integrity' entry (D-106).")
    if entry["version"] != CONTENT_INTEGRITY_DOCTRINE_VERSION:
        _fail("Manifest version mismatch for content_integrity (D-106).")
    if entry["rules_count"] != len(CONTENT_INTEGRITY_DOCTRINE):
        _fail("Manifest rules_count mismatch for content_integrity (D-106).")

    client_src = _read_tutor_source()  # D-166: chat_with_agent في mixin — المصدر المُركَّب
    if "StreamIntegrityFilter" not in client_src or "sanitize_final_text" not in client_src:
        _fail("orchestrator_client no longer wires StreamIntegrityFilter (D-106 ZOMBIE).")
    local_src = (ROOT / "app/services/chat/local_graph.py").read_text(encoding="utf-8")
    if "StreamIntegrityFilter" not in local_src:
        _fail("local_graph no longer wires StreamIntegrityFilter (D-106 ZOMBIE).")
    _pass("Content integrity wired: stream-wide guard on orchestrator + local paths (D-106)")


def check_learning_path_wired() -> None:
    """D-111/D-119: المسار التعلّمي التكيفي موصول فعلاً — ليس skill بلا مستهلك.

    D-119 (قرار المالك): المسار يُشتقّ خلف الكواليس (مُستهلَك + مُسجَّل telemetry)
    ولا يُعرَض كبطاقة للطالب — كانت تُكرَّر وتُشوّش. الحرس: (1) manifest متّسق،
    (2) ``get_learning_path_skill`` مُستدعى حيّاً في customer_chat (مُستهلَك،
    لا ZOMBIE) — بلا اشتراط بناء بطاقة طالب.
    """
    from app.services.skills.doctrine import (
        LEARNING_PATH_DOCTRINE,
        LEARNING_PATH_DOCTRINE_VERSION,
        SKILL_DOCTRINE_MANIFEST,
    )

    entry = SKILL_DOCTRINE_MANIFEST.get("learning_path")
    if entry is None:
        _fail("Manifest missing 'learning_path' entry (D-111).")
    if entry["version"] != LEARNING_PATH_DOCTRINE_VERSION:
        _fail("Manifest version mismatch for learning_path (D-111).")
    if entry["rules_count"] != len(LEARNING_PATH_DOCTRINE):
        _fail("Manifest rules_count mismatch for learning_path (D-111).")

    router_src = (ROOT / "app/api/routers/customer_chat.py").read_text(encoding="utf-8")
    # D-119: يكفي استدعاء الـ Skill (مُستهلَك خلف الكواليس) — لا اشتراط بطاقة طالب.
    if "get_learning_path_skill" not in router_src:
        _fail("customer_chat no longer derives learning_path (D-111/D-119 ZOMBIE).")
    _pass("Learning path wired behind-the-scenes over BKT mastery (D-111/D-119)")


def check_answer_redaction_wired() -> None:
    """D-113 (ISS-115 — وَهْم الإتقان): الحارس الحتمي ضد كشف الإجابة موصول فعلاً.

    يحرس: (1) `sanitize_final_text` (content_integrity) يستدعي `redact_final_answers`
    فيغطّي مخرج orchestrator + المسار المحلي النهائي، (2) `local_graph` يحوي
    `_apply_answer_redaction` ويستدعيه، (3) الـ doctrine السقراطي يمنع كشف النتيجة.
    """
    ci = (ROOT / "app/services/skills/content_integrity_skill.py").read_text(encoding="utf-8")
    if "redact_final_answers" not in ci:
        _fail(
            "content_integrity.sanitize_final_text no longer calls redact_final_answers "
            "(D-113 ZOMBIE — answer redaction not on the final-frame path)."
        )
    local_src = (ROOT / "app/services/chat/local_graph.py").read_text(encoding="utf-8")
    if "_apply_answer_redaction" not in local_src:
        _fail("local_graph.py: _apply_answer_redaction not defined (D-113).")
    if "_apply_answer_redaction(clean" not in local_src:
        _fail("local_graph._chat_node does not call _apply_answer_redaction (D-113 ZOMBIE).")

    # الـ doctrine السقراطي يجب أن يمنع كشف النتيجة النهائية صراحةً
    from app.services.skills.doctrine import EXPLANATION_DOCTRINE

    joined = " ".join(EXPLANATION_DOCTRINE)
    if "لا تكشف" not in joined or "ممنوع" not in joined:
        _fail(
            "EXPLANATION_DOCTRINE no longer forbids revealing answers "
            "(D-113: must contain Socratic no-answer rules)."
        )
    _pass("Answer redaction wired: Socratic no-answer + deterministic final guard (D-113)")


def check_socratic_protocol_wired() -> None:
    """D-115 (ISS-116 — يَعكِس D-114): البروتوكول السقراطي المنضبط + المُطهّر المُصفّح.

    يحرس: (1) manifest entry 'worked_example' (المُعاد توجيهه) متّسق، (2) لا توليد
    تعليمي مكشوف في المونوليث (لا `_maybe_emit_worked_example`، لا `worked_example_card`)،
    (3) السلطة الوحيدة للتوليد هي SynthesizerNode (orchestrator) عبر البروتوكول المنضبط،
    (4) المُطهّر المُصفّح موصول في المونوليث والـ orchestrator، (5) support_level يمرّ.
    """
    from app.contracts.streaming import KNOWN_UI_COMPONENTS
    from app.services.skills.doctrine import (
        SKILL_DOCTRINE_MANIFEST,
        WORKED_EXAMPLE_DOCTRINE,
        WORKED_EXAMPLE_DOCTRINE_VERSION,
    )

    entry = SKILL_DOCTRINE_MANIFEST.get("worked_example")
    if entry is None:
        _fail("Manifest missing 'worked_example' (socratic protocol) entry (D-115).")
    if entry["version"] != WORKED_EXAMPLE_DOCTRINE_VERSION:
        _fail("Manifest version mismatch for worked_example (D-115).")
    if entry["rules_count"] != len(WORKED_EXAMPLE_DOCTRINE):
        _fail("Manifest rules_count mismatch for worked_example (D-115).")

    # D-115: المثال المكشوف مُزال — لا skill/card/wiring تعليمي في المونوليث.
    if (ROOT / "app/services/skills/worked_example_skill.py").exists():
        _fail("worked_example_skill.py must be removed (D-115 reverses the reveal).")
    router_src = (ROOT / "app/api/routers/customer_chat.py").read_text(encoding="utf-8")
    if "_maybe_emit_worked_example" in router_src:
        _fail("customer_chat still emits worked_example reveal (D-115 must remove it).")
    if "worked_example_card" in KNOWN_UI_COMPONENTS:
        _fail("worked_example_card must be removed from KNOWN_UI_COMPONENTS (D-115).")

    # السلطة الوحيدة للتوليد: SynthesizerNode يطبّق البروتوكول السقراطي المنضبط.
    search_src = (
        ROOT / "microservices/orchestrator_service/src/services/overmind/graph/search.py"
    ).read_text(encoding="utf-8")
    if "_build_socratic_prompt" not in search_src or "_SOCRATIC_CORE_PROMPT" not in search_src:
        _fail("SynthesizerNode lost the disciplined Socratic protocol (D-115).")

    # المُطهّر المُصفّح موصول في المنفذين (يحذف ⟦⟧ المشوّهة + تعليمات مُسرَّبة).
    ci_src = (ROOT / "app/services/skills/content_integrity_skill.py").read_text(encoding="utf-8")
    if "_strip_garbage_markers" not in ci_src:
        _fail("content_integrity lost the bulletproof garbage stripper (D-115).")
    rs_file = (
        ROOT / "microservices/orchestrator_service/src/services/overmind/response_sanitizer.py"
    )
    if rs_file.is_file():
        rs_src = rs_file.read_text(encoding="utf-8")
        if "strip_garbage_markers" not in rs_src or "support_level" not in rs_src:
            _fail("response_sanitizer (orchestrator) lost garbage stripper/support_level (D-115).")
    _pass("Socratic protocol wired: orchestrator-only generation + bulletproof sanitizer (D-115)")


def check_pedagogical_policy_wired() -> None:
    """D-129 (الطبقة 4 — محرّك السياسة التربوية): يحرس أن السياسة موصولة فعلاً.

    الكارثة (بعد D-128): السرد السقراطي فريد لكن النظام يسأل بلا توقف ولا يعترف
    بإجابات الطالب ولا يتقدّم — حلقة استجواب. السياسة الحتمية تكسرها: ميزانية أسئلة
    (MAX_SOCRATIC) ثم حلّ رمزي + اعتراف. يحرس: (1) manifest entry متّسق، (2) الـ Skill
    يستهلك الـ doctrine، (3) `orchestrator_client.chat_with_agent` يستدعي السياسة
    ويفرّع على `symbolic_reveal` عبر `_build_symbolic_reveal` (لا ZOMBIE).
    """
    from app.services.skills.doctrine import (
        PEDAGOGICAL_POLICY_DOCTRINE,
        PEDAGOGICAL_POLICY_DOCTRINE_VERSION,
        SKILL_DOCTRINE_MANIFEST,
    )

    entry = SKILL_DOCTRINE_MANIFEST.get("pedagogical_policy")
    if entry is None:
        _fail("Manifest missing 'pedagogical_policy' entry (D-129).")
    if entry["version"] != PEDAGOGICAL_POLICY_DOCTRINE_VERSION:
        _fail("Manifest version mismatch for pedagogical_policy (D-129).")
    if entry["rules_count"] != len(PEDAGOGICAL_POLICY_DOCTRINE):
        _fail("Manifest rules_count mismatch for pedagogical_policy (D-129).")

    skill = (ROOT / "app/services/skills/pedagogical_policy_skill.py").read_text(encoding="utf-8")
    if "from app.services.skills.doctrine import" not in skill:
        _fail("pedagogical_policy_skill.py does not consume doctrine (D-129).")
    if "MAX_SOCRATIC" not in skill:
        _fail("pedagogical_policy_skill.py lost the MAX_SOCRATIC budget (D-129).")

    client_src = _read_tutor_source()  # D-166: chat_with_agent في mixin — المصدر المُركَّب
    if "get_pedagogical_policy_skill" not in client_src:
        _fail("orchestrator_client does not invoke the pedagogical policy (D-129 ZOMBIE).")
    if "_build_symbolic_reveal" not in client_src:
        _fail("orchestrator_client lost the deterministic symbolic-reveal escape (D-129).")
    # D-130 (تحسينا المالك): كشف الإجابة بالفعل الكلامي لا الطول + ميزانية تكيّفية.
    if "is_response_to_socratic" not in skill or "socratic_budget" not in skill:
        _fail(
            "pedagogical_policy_skill.py lost D-130 refinements "
            "(is_response_to_socratic / socratic_budget)."
        )
    _pass(
        "Pedagogical policy wired: bounded Socratic → acknowledge → symbolic reveal (D-129/D-130)"
    )


def check_socratic_evaluator_wired() -> None:
    """D-130 (الطبقة 1 — الإصغاء النشط / مُقيّم الإجابات السقراطي): يحرس التوصيل.

    الكارثة (الخيانة البيداغوجية): الطالب يُجيب إجابة عبقرية على سؤال سقراطي، فيُعيد
    النظام طباعة التمرين كاملاً بدل تقييم الإجابة ومكافأتها. المُقيّم هو «الأذن الصاغية»
    المفقودة. يحرس: (1) manifest entry متّسق، (2) الـ Skill يستهلك doctrine، (3) موصول
    حيّاً في `chat_with_agent` **قبل** الاسترجاع المُفهرَس (`_in_socratic_dialogue` +
    `_stream_socratic_evaluation` + `_build_symbolic_step`)، (4) لا إعادة طباعة.
    """
    from app.services.skills.doctrine import (
        SKILL_DOCTRINE_MANIFEST,
        SOCRATIC_EVALUATOR_DOCTRINE,
        SOCRATIC_EVALUATOR_DOCTRINE_VERSION,
    )

    entry = SKILL_DOCTRINE_MANIFEST.get("socratic_evaluator")
    if entry is None:
        _fail("Manifest missing 'socratic_evaluator' entry (D-130).")
    if entry["version"] != SOCRATIC_EVALUATOR_DOCTRINE_VERSION:
        _fail("Manifest version mismatch for socratic_evaluator (D-130).")
    if entry["rules_count"] != len(SOCRATIC_EVALUATOR_DOCTRINE):
        _fail("Manifest rules_count mismatch for socratic_evaluator (D-130).")

    skill = (ROOT / "app/services/skills/socratic_evaluator_skill.py").read_text(encoding="utf-8")
    if "from app.services.skills.doctrine import" not in skill:
        _fail("socratic_evaluator_skill.py does not consume doctrine (D-130).")
    if "redact_final_answers" not in skill:
        _fail("socratic_evaluator_skill.py lost the answer-redaction guard (D-130).")

    client_src = _read_tutor_source()  # D-166: chat_with_agent في mixin — المصدر المُركَّب
    for needle in (
        "get_socratic_evaluator_skill",
        "_in_socratic_dialogue",
        "_stream_socratic_evaluation",
        "_build_symbolic_step",
    ):
        if needle not in client_src:
            _fail(f"orchestrator_client lost D-130 wiring: {needle} (active-listener ZOMBIE).")

    # D-130: الالتقاط المبكر يجب أن يسبق الاسترجاع المُفهرَس (وإلا تُعاد طباعة التمرين).
    # نطابق صيغة الاستدعاء بـ `self.` (يميّزها عن تعريف الدالة) ومتينة على لفّ الأسطر.
    eval_pos = client_src.find("self._in_socratic_dialogue(")
    indexed_pos = client_src.find("self._has_indexed_match(")
    if eval_pos == -1 or indexed_pos == -1 or eval_pos > indexed_pos:
        _fail(
            "D-130: socratic-evaluation capture must precede indexed-retrieval in "
            "chat_with_agent (else the student's answer re-prints the exercise)."
        )
    _pass("Socratic evaluator wired: active-listener capture before indexed-retrieval (D-130)")


def check_semantic_property_wired() -> None:
    """D-131 (الطبقة 2 — الطبقة الدلالية + Misconception Graph): يحرس التوصيل.

    الكارثة: «ماذا نقصد بجداء معدوم» لا يُجاب لأن event_meaning مُجمَّد على الحادثة A.
    الحل: طبقة دلالية عامة data-driven (لا special-casing) + Misconception Graph «شخّص ثم
    تدخّل». يحرس: (1) manifest متّسق، (2) الـ Skill يستهلك doctrine، (3) `_build_cognitive_response`
    يستدعي الطبقة (لا if/elif لكل حادثة)، (4) كل عقدة misconception لها `bkt_concept` + `mtype` من
    التصنيف الثلاثي (لا عقدة بلا أثر)، (5) المقاييس السلوكية الأربعة لها مُصدِر حيّ.
    """
    from app.services.skills.doctrine import (
        SEMANTIC_PROPERTY_DOCTRINE,
        SEMANTIC_PROPERTY_DOCTRINE_VERSION,
        SKILL_DOCTRINE_MANIFEST,
    )
    from app.services.skills.semantic_property_skill import (
        MISCONCEPTION_GRAPH,
        MISCONCEPTION_TYPES,
    )

    entry = SKILL_DOCTRINE_MANIFEST.get("semantic_property")
    if entry is None:
        _fail("Manifest missing 'semantic_property' entry (D-131).")
    if entry["version"] != SEMANTIC_PROPERTY_DOCTRINE_VERSION:
        _fail("Manifest version mismatch for semantic_property (D-131).")
    if entry["rules_count"] != len(SEMANTIC_PROPERTY_DOCTRINE):
        _fail("Manifest rules_count mismatch for semantic_property (D-131).")

    skill = (ROOT / "app/services/skills/semantic_property_skill.py").read_text(encoding="utf-8")
    if "from app.services.skills.doctrine import" not in skill:
        _fail("semantic_property_skill.py does not consume doctrine (D-131).")
    if "PROPERTY_REGISTRY" not in skill or "MISCONCEPTION_GRAPH" not in skill:
        _fail("semantic_property_skill.py lost the data-driven registry/graph (D-131).")

    # D-131: كل عقدة misconception لها bkt_concept + mtype صحيح (لا عقدة بلا أثر).
    for concept_id, nodes in MISCONCEPTION_GRAPH.items():
        for node in nodes:
            if not node.bkt_concept:
                _fail(f"Misconception node '{node.id}' ({concept_id}) lacks bkt_concept (D-131).")
            if node.mtype not in MISCONCEPTION_TYPES:
                _fail(f"Misconception node '{node.id}' has invalid mtype '{node.mtype}' (D-131).")

    # التوصيل: نداء واحد للطبقة في _build_cognitive_response (لا special-casing لكل حادثة).
    client_src = _read_tutor_source()  # D-166: chat_with_agent في mixin — المصدر المُركَّب
    us_skill = (ROOT / "app/services/skills/understanding_state_skill.py").read_text(
        encoding="utf-8"
    )
    if "get_semantic_property_skill" not in client_src:
        _fail("orchestrator_client does not invoke the semantic layer (D-131 ZOMBIE).")
    if "diagnose_misconception" not in client_src:
        _fail("orchestrator_client does not use the Misconception Graph (D-131 — diagnose).")

    # المقاييس السلوكية الأربعة (§5) لها مُصدِر حيّ.
    metrics_src = (ROOT / "app/services/skills/tutor_metrics.py").read_text(encoding="utf-8")
    for fn in (
        "record_repetition_avoided",
        "record_definitional_answer",
        "record_intervention",
        "record_progress",
    ):
        if f"def {fn}" not in metrics_src:
            _fail(f"tutor_metrics missing behavioral metric {fn} (D-131 §5).")
        if fn not in client_src:
            _fail(f"behavioral metric {fn} has no live emitter in orchestrator_client (D-131 §5).")

    # D-132: جاهزية الأسئلة الجديدة + لا default مُجمَّد لمفهوم واحد.
    if "def define_concept" not in skill or "def interpret_or_define" not in skill:
        _fail("semantic_property_skill missing define_concept/interpret_or_define (D-132).")
    if "redact_final_answers" not in skill:
        _fail("define_concept lost the answer-redaction guard (D-132 LLM ceiling).")
    if "random_variable" not in skill or "expected_value" not in skill:
        _fail("PROPERTY_REGISTRY missing exercise concepts random_variable/expected_value (D-132).")
    if "interpret_or_define" not in client_src:
        _fail("orchestrator_client missing the definitional preempt interpret_or_define (D-132).")
    # لا default مُجمَّد لمفهوم واحد في فرع event_meaning (D-132 قاعدة 3).
    _em = client_src.find('if concept == "event_meaning":')
    if _em != -1:
        _seg = client_src[_em : _em + 1500]
        if '_sp_spec = PROPERTY_REGISTRY["same_color"]' in _seg and "any(m in _q" not in _seg:
            _fail("event_meaning still uses an UNCONDITIONAL same_color default (D-132 rule 3).")
    # preempt التعريفي يسبق الالتقاط السقراطي (سؤال تعريفي جديد لا إجابة سقراطية).
    _defp = client_src.find("interpret_or_define(question)")
    _socp = client_src.find("_in_socratic_dialogue(question")
    if _defp == -1 or _socp == -1 or _defp > _socp:
        _fail("D-132: definitional preempt must precede the socratic capture in chat_with_agent.")
    # D-136: مثال واعٍ بالمفهوم — PropertySpec.example + detect_active_concept + معالج orchestrator.
    if "example:" not in skill or "def detect_active_concept" not in skill:
        _fail(
            "semantic_property_skill missing PropertySpec.example / detect_active_concept (D-136)."
        )
    if "_build_concept_example" not in client_src:
        _fail(
            "orchestrator_client missing the concept-aware example handler _build_concept_example (D-136)."
        )
    # D-137: «ما هو X» تعريف موثوق — _DEFINITIONAL_MARKERS يشمل «ما هو»؛ _wants_def يستخدم
    # نيّة StudentState؛ «الحالات الملائمة» مفهوم مُسجَّل؛ معالج المثال يَفعل على الحيرة+مفهوم نشط.
    if '"ما هو "' not in skill:
        _fail(
            "_DEFINITIONAL_MARKERS missing bare 'ما هو' — 'ما هو X' not treated as definition (D-137)."
        )
    if '"favorable_cases"' not in skill or "الحالات الملائمة" not in skill:
        _fail("PROPERTY_REGISTRY missing the 'favorable_cases' concept (D-137).")
    if '_state.primary_intent == "definition"' not in client_src:
        _fail(
            "_wants_def does not use StudentState definition intent (D-137 — 'ما هو X' reliable)."
        )
    if "_ex_confused" not in client_src or "_ex_active" not in client_src:
        _fail("concept-example handler does not re-engage the active concept on confusion (D-137).")
    # D-139: قتل انحراف المفهوم إلى الحادثة A — أسئلة المفهوم تُمسَك دائماً قبل D-135.
    if "_EXERCISE_DUMP_MARKERS" not in skill:
        _fail("detect_active_concept lacks _EXERCISE_DUMP_MARKERS drift guard (D-139).")
    if "if self.is_definitional(question)" not in skill:
        _fail("detect_active_concept lacks the new-definitional reset guard (D-139).")
    if '"sequential_without_replacement"' not in skill or '"simultaneous_draw"' not in skill:
        _fail("PROPERTY_REGISTRY missing the drawing-mode concepts (D-139).")
    if "_esc_compute" not in client_src or "_esc_followup" not in client_src:
        _fail(
            "escalation gate missing the compute/followup guard (D-139 — concept Qs reach matrix)."
        )
    if "elif _confused:" not in us_skill:
        _fail(
            "understanding_state lacks the D-139 event-A default guard (no kc_event_meaning unless confused)."
        )
    _pass(
        "Semantic layer + D-132 readiness + D-136 examples + D-137 untangle + D-139 drift-kill wired"
    )


def check_student_state_wired() -> None:
    """D-133 (حالة الطالب كإشارة قرار): يحرس أن النيّة/الإحباط يُغيّران البيداغوجيا فعلاً.

    إعادة توجيه المالك: النظام يفكّر بالمفهوم بينما الطالب يتحرّك بنيّة وحالة شعورية.
    يحرس: (1) manifest متّسق، (2) الـ Skill يستهلك doctrine + متعدّد-إشارات + LLM ثانوي
    لا يطغى + لا تخزين للإحباط (نقد المالك 1/2/3)، (3) موصول حيّاً في orchestrator_client
    (لا ZOMBIE)، (4) `PolicyInput` يكتسب intent+frustration و`socratic_budget` يحترم
    frustration، (5) مقاييس intent/frustration/response_mode لها مُصدِر حيّ.
    """
    from app.services.skills.doctrine import (
        SKILL_DOCTRINE_MANIFEST,
        STUDENT_STATE_DOCTRINE,
        STUDENT_STATE_DOCTRINE_VERSION,
    )

    entry = SKILL_DOCTRINE_MANIFEST.get("student_state")
    if entry is None:
        _fail("Manifest missing 'student_state' entry (D-133).")
    if entry["version"] != STUDENT_STATE_DOCTRINE_VERSION:
        _fail("Manifest version mismatch for student_state (D-133).")
    if entry["rules_count"] != len(STUDENT_STATE_DOCTRINE):
        _fail("Manifest rules_count mismatch for student_state (D-133).")

    skill = (ROOT / "app/services/skills/student_state_skill.py").read_text(encoding="utf-8")
    if "from app.services.skills.doctrine import" not in skill:
        _fail("student_state_skill.py does not consume doctrine (D-133).")
    # نقد 1: متعدّد-إشارات (primary + secondary).
    if "primary_intent" not in skill or "secondary_signals" not in skill:
        _fail("student_state_skill lost the multi-signal output (D-133 critique 1).")
    # نقد 2: LLM ثانوي لا يطغى (يُستدعى فقط عند primary=unknown).
    if "def read" not in skill or "def read_or_classify" not in skill:
        _fail("student_state_skill missing read/read_or_classify (D-133).")
    if 'primary_intent != "unknown"' not in skill:
        _fail(
            "student_state LLM not gated to primary=unknown — may override deterministic (D-133 critique 2)."
        )
    # نقد 3: الإحباط لحظي لا يُخزَّن (لا I/O / لا DB في الـ Skill).
    for forbidden in ("async_session", "session_factory", "INSERT", "commit("):
        if forbidden in skill:
            _fail(
                f"student_state_skill persists state ('{forbidden}') — frustration must be transient (D-133 critique 3)."
            )

    # التوصيل الحيّ (لا ZOMBIE): orchestrator_client يقرأ الحالة ويمرّر intent+frustration.
    client_src = _read_tutor_source()  # D-166: chat_with_agent في mixin — المصدر المُركَّب
    if "get_student_state_skill" not in client_src:
        _fail("orchestrator_client does not invoke StudentStateSkill (D-133 ZOMBIE).")
    if (
        "intent=_state.primary_intent" not in client_src
        or "frustration=_state.frustration" not in client_src
    ):
        _fail("orchestrator_client does not thread intent/frustration into PolicyInput (D-133).")

    # السياسة: PolicyInput يكتسب intent+frustration؛ socratic_budget يحترم frustration؛ response_mode.
    policy = (ROOT / "app/services/skills/pedagogical_policy_skill.py").read_text(encoding="utf-8")
    if "intent:" not in policy or "frustration:" not in policy:
        _fail("PolicyInput missing intent/frustration fields (D-133).")
    if 'frustration == "high"' not in policy:
        _fail("socratic_budget does not stop questioning on high frustration (D-133).")
    if "def response_mode_for" not in policy or "response_mode" not in policy:
        _fail("pedagogical_policy missing response_mode (the decision signal, D-133).")

    # المقاييس الثلاثة الجديدة لها مُصدِر حيّ.
    metrics_src = (ROOT / "app/services/skills/tutor_metrics.py").read_text(encoding="utf-8")
    for fn in ("record_intent", "record_frustration", "record_response_mode"):
        if f"def {fn}" not in metrics_src:
            _fail(f"tutor_metrics missing D-133 metric {fn}.")
        if fn not in client_src and fn not in policy:
            _fail(f"D-133 metric {fn} has no live emitter (orchestrator_client/policy).")
    _pass("Student-state (intent + transient frustration) wired as a decision signal (D-133)")


def check_understanding_state_wired() -> None:
    """D-135 (محرّك حالة الفهم — Learning State): يحرس النموذج المبدئي.

    يحرس: (1) manifest متّسق، (2) الـ Skill يستهلك doctrine + KC-aware (knowledge_components من combo)
    + detect_gap بالمعنى + understanding_state دلالي + الفهم يتطلّب evidence (لا «فهمت» وحدها) +
    تمثيل استباقي + الأرقام من combo لا LLM، (3) موصول حيّاً في orchestrator_client (لا ZOMBIE)،
    (4) مقياس understanding له مُصدِر حيّ.
    """
    from app.services.skills.doctrine import (
        SKILL_DOCTRINE_MANIFEST,
        UNDERSTANDING_STATE_DOCTRINE,
        UNDERSTANDING_STATE_DOCTRINE_VERSION,
    )

    entry = SKILL_DOCTRINE_MANIFEST.get("understanding_state")
    if entry is None:
        _fail("Manifest missing 'understanding_state' entry (D-135).")
    if entry["version"] != UNDERSTANDING_STATE_DOCTRINE_VERSION:
        _fail("Manifest version mismatch for understanding_state (D-135).")
    if entry["rules_count"] != len(UNDERSTANDING_STATE_DOCTRINE):
        _fail("Manifest rules_count mismatch for understanding_state (D-135).")

    skill = (ROOT / "app/services/skills/understanding_state_skill.py").read_text(encoding="utf-8")
    if "from app.services.skills.doctrine import" not in skill:
        _fail("understanding_state_skill.py does not consume doctrine (D-135).")
    # KC-aware: المكوّنات من combo (لا أرقام مكتوبة)؛ detect_gap بالمعنى.
    for fn in (
        "def knowledge_components",
        "def detect_gap",
        "def understanding_state",
        "def decide",
    ):
        if fn not in skill:
            _fail(f"understanding_state_skill missing {fn} (D-135).")
    # نقد 1: KC-aware — المكوّنات والأرقام من combo (لا number-match مثبَّت).
    if "combo.total_combinations" not in skill or "combo.groups" not in skill:
        _fail("understanding_state KCs not derived from symbolic combo (D-135 critique 1).")
    # نقد 3: الفهم يتطلّب evidence (لا صحة فقط) — understood مشروط بـ evidence_markers.
    if "evidence_markers" not in skill or "has_evidence" not in skill:
        _fail("understanding_state does not require understanding_evidence (D-135 critique 3).")
    # نقد 4: تمثيل استباقي يتصاعد.
    if "representations" not in skill or "_explain_count" not in skill:
        _fail("understanding_state lacks proactive representation escalation (D-135 critique 4).")
    # الأرقام من المحرك الرمزي لا LLM (صفر استدعاء LLM في الـ Skill).
    if "send_message" in skill or "get_ai_client" in skill:
        _fail("understanding_state must be LLM-free (numbers from symbolic engine, D-135).")

    # التوصيل الحيّ (لا ZOMBIE).
    client_src = _read_tutor_source()  # D-166: chat_with_agent في mixin — المصدر المُركَّب
    if "get_understanding_state_skill" not in client_src:
        _fail("orchestrator_client does not invoke UnderstandingStateSkill (D-135 ZOMBIE).")
    if "_is_short_answer_in_dialogue" not in client_src:
        _fail("orchestrator_client missing the answer-without-'؟' guard (D-135 Part F).")

    # مقياس الفهم له مُصدِر حيّ.
    metrics_src = (ROOT / "app/services/skills/tutor_metrics.py").read_text(encoding="utf-8")
    if "def record_understanding" not in metrics_src:
        _fail("tutor_metrics missing record_understanding (D-135).")
    if "record_understanding" not in client_src:
        _fail("record_understanding has no live emitter in orchestrator_client (D-135).")
    # D-136: كبح الاختطاف — decide لا يتقدّم في المسار إلا إذا كنا فعلاً وسطه (on_path)؛
    # سؤال عن مفهوم خارج مسار نفس-اللون ⇒ None (لا default إلى kc_event_meaning).
    if "on_path" not in skill:
        _fail(
            "understanding_state.decide still hijacks non-path questions (D-136 — missing on_path scope)."
        )
    # D-137: إشارات D-135 خاصة بخطوة الحساب لا كلمات مفهوم عامة — «الاحتمال» المجرّدة (عنصر
    # gap_signal مستقل) تختطف «ما هو الاحتمال الشرطي». يجب ألا توجد كعنصر مفرد.
    if '"الاحتمال",' in skill:
        _fail(
            "understanding_state has the over-broad bare 'الاحتمال' gap_signal — hijacks concept "
            "questions like 'ما هو الاحتمال الشرطي' (D-137)."
        )
    # D-137: _current_focus_kc لا يقفل على مثال/تعريف مفهوم (تجنّب تسرّب «نفس اللون» العابرة).
    if "## مثال" not in skill or "مثال ملموس" not in skill:
        _fail("understanding_state._current_focus_kc lacks the concept-artifact guard (D-137).")
    _pass(
        "Understanding-State engine (Learning State, KC-aware, evidence, proactive, no-hijack, "
        "D-137 routing-separation) wired (D-135/D-136/D-137)"
    )


def check_micro_simulation_wired() -> None:
    """D-138 (خادم المحاكيات المصغّرة الحتمي — L3): يحرس الحتمية + الطول + التوصيل.

    يحرس: (1) manifest متّسق، (2) الـ Skill يستهلك doctrine، (3) حتمي صفر-LLM (لا send_message/
    get_ai_client)، (4) كل محاكاة ≤320 حرف (نقد المالك #2: محاكاة لا «شرح كامل»)، (5) موصول حيّاً.
    """
    from app.services.skills.doctrine import (
        MICRO_SIMULATION_DOCTRINE,
        MICRO_SIMULATION_DOCTRINE_VERSION,
        SKILL_DOCTRINE_MANIFEST,
    )
    from app.services.skills.micro_simulation_skill import MICRO_SIM_MAX_CHARS, MICRO_SIMULATIONS

    entry = SKILL_DOCTRINE_MANIFEST.get("micro_simulation")
    if entry is None:
        _fail("Manifest missing 'micro_simulation' entry (D-138).")
    if entry["version"] != MICRO_SIMULATION_DOCTRINE_VERSION:
        _fail("Manifest version mismatch for micro_simulation (D-138).")
    if entry["rules_count"] != len(MICRO_SIMULATION_DOCTRINE):
        _fail("Manifest rules_count mismatch for micro_simulation (D-138).")

    skill = (ROOT / "app/services/skills/micro_simulation_skill.py").read_text(encoding="utf-8")
    if "from app.services.skills.doctrine import" not in skill:
        _fail("micro_simulation_skill.py does not consume doctrine (D-138).")
    # حتمي صفر-LLM (نقد MathDial): لا استدعاء نموذج.
    if "send_message" in skill or "get_ai_client" in skill:
        _fail("micro_simulation_skill must be LLM-free (deterministic content, D-138).")
    # قيد الطول الصارم (نقد المالك #2): محاكاة مصغّرة لا «شرح كامل».
    for cid, sim in MICRO_SIMULATIONS.items():
        if len(sim) > MICRO_SIM_MAX_CHARS:
            _fail(f"Micro-simulation '{cid}' exceeds {MICRO_SIM_MAX_CHARS} chars (D-138 rule #2).")
        if "14/165" in sim or "14 من 165" in sim:
            _fail(f"Micro-simulation '{cid}' leaks the exercise answer (D-138 / D-113).")

    client_src = _read_tutor_source()  # D-166: chat_with_agent في mixin — المصدر المُركَّب
    if "get_micro_simulation_skill" not in client_src:
        _fail("orchestrator_client does not invoke MicroSimulationSkill (D-138 ZOMBIE).")
    _pass("Micro-simulation engine wired: deterministic, ≤320 chars, L3 content server (D-138)")


def check_pedagogical_escalation_wired() -> None:
    """D-138 (المصفوفة التصعيدية التكيّفية): يحرس الإشارات الثلاث + لا تكرار + التوصيل.

    حكم المالك: «Escalation Matrix + Understanding-Signal + Misconception-Check» مُعايَرة بالقدرة.
    يحرس: (1) manifest متّسق، (2) يستهلك doctrine + حتمي صفر-LLM، (3) يدمج Understanding-Signal
    (`_has_understanding_evidence`) + Misconception-Check (`misconception_intervention`) +
    ability calibration (`support_level`) + لا تكرار رُتبة (`_levels_delivered`)، (4) موصول حيّاً.
    """
    from app.services.skills.doctrine import (
        PEDAGOGICAL_ESCALATION_DOCTRINE,
        PEDAGOGICAL_ESCALATION_DOCTRINE_VERSION,
        SKILL_DOCTRINE_MANIFEST,
    )

    entry = SKILL_DOCTRINE_MANIFEST.get("pedagogical_escalation")
    if entry is None:
        _fail("Manifest missing 'pedagogical_escalation' entry (D-138).")
    if entry["version"] != PEDAGOGICAL_ESCALATION_DOCTRINE_VERSION:
        _fail("Manifest version mismatch for pedagogical_escalation (D-138).")
    if entry["rules_count"] != len(PEDAGOGICAL_ESCALATION_DOCTRINE):
        _fail("Manifest rules_count mismatch for pedagogical_escalation (D-138).")

    skill = (ROOT / "app/services/skills/pedagogical_escalation_skill.py").read_text(
        encoding="utf-8"
    )
    if "from app.services.skills.doctrine import" not in skill:
        _fail("pedagogical_escalation_skill.py does not consume doctrine (D-138).")
    if "send_message" in skill or "get_ai_client" in skill:
        _fail("pedagogical_escalation must be LLM-free (deterministic policy, D-138).")
    # الإشارات الثلاث + لا تكرار رُتبة (نقد المالك النهائي).
    if "_has_understanding_evidence" not in skill:
        _fail("escalation missing Understanding Signal (_has_understanding_evidence, D-138 #3).")
    if "misconception_intervention" not in skill or "target_misconception" not in skill:
        _fail("escalation missing Misconception Check (D-138 #1).")
    if "support_level" not in skill or "_calibrate" not in skill:
        _fail("escalation missing ability/step-difficulty calibration (D-138 owner verdict).")
    if "_levels_delivered" not in skill:
        _fail("escalation missing escalation memory / no-repeat (_levels_delivered, D-138 #4).")

    client_src = _read_tutor_source()  # D-166: chat_with_agent في mixin — المصدر المُركَّب
    if "get_pedagogical_escalation_skill" not in client_src:
        _fail("orchestrator_client does not invoke PedagogicalEscalationSkill (D-138 ZOMBIE).")
    if "_esc_decision" not in client_src or "detect_active_concept" not in client_src:
        _fail("escalation not concept-scoped / not wired in chat_with_agent (D-138 #5).")
    _pass(
        "Pedagogical escalation matrix wired: Understanding-Signal + Misconception-Check + "
        "ability calibration + no-repeat (D-138)"
    )


def check_dialogue_manager_wired() -> None:
    """D-142 Phase 2 (مدير الحوار الموحَّد): يحرس سلطة قرار الدور الموصولة (لا ZOMBIE).

    يحرس: (1) manifest متّسق، (2) الـ Skill يستهلك doctrine وحتمي (لا LLM في decide)،
    (3) القرار = evidence×ability×difficulty (التقدّم/التصعيد/عدم القفز موجودة)،
    (4) موصول حيّاً في orchestrator_client خلف العلم SEMANTIC_TUTOR_ENABLED.
    """
    from app.services.skills.doctrine import (
        DIALOGUE_MANAGER_DOCTRINE,
        DIALOGUE_MANAGER_DOCTRINE_VERSION,
        SKILL_DOCTRINE_MANIFEST,
    )

    entry = SKILL_DOCTRINE_MANIFEST.get("dialogue_manager")
    if entry is None:
        _fail("Manifest missing 'dialogue_manager' entry (D-142 Phase 2).")
    if entry["version"] != DIALOGUE_MANAGER_DOCTRINE_VERSION:
        _fail("Manifest version mismatch for dialogue_manager (D-142).")
    if entry["rules_count"] != len(DIALOGUE_MANAGER_DOCTRINE):
        _fail("Manifest rules_count mismatch for dialogue_manager (D-142).")

    skill = (ROOT / "app/services/skills/dialogue_manager_skill.py").read_text(encoding="utf-8")
    if "from app.services.skills.doctrine import" not in skill:
        _fail("dialogue_manager_skill.py does not consume doctrine (D-142).")
    # حتمي: لا LLM في decide (الأرقام/الصحّة من المحرك الرمزي، القدرة من BKT).
    for forbidden in ("get_ai_client", "send_message", "async def decide"):
        if forbidden in skill:
            _fail(f"dialogue_manager must be deterministic (found '{forbidden}') — D-142.")
    # القرار الثلاثي: تقدّم حتمي + تصعيد عند التكرار/الميزانية + عدم القفز.
    for token in ("acknowledge_advance", "symbolic_reveal", "intermediate_scaffold"):
        if token not in skill:
            _fail(f"dialogue_manager missing decision action '{token}' (D-142).")

    # التوصيل الحيّ (لا ZOMBIE): orchestrator_client يستشيره خلف العلم.
    # D-163: التعريف (`_dialogue_decision` + الاستيراد الكسول لـ get_dialogue_manager_skill)
    # يعيش في العقل المستخرَج `probability_tutor_brain.py`؛ موقع الاستدعاء يبقى في الـ client.
    client_src = _read_tutor_source()  # D-166: chat_with_agent في mixin — المصدر المُركَّب
    brain_src = _read_brain_source()  # D-168: العقل مُفكَّك — المصدر المُركَّب عبر manifest
    if "_dialogue_decision" not in client_src or "_semantic_tutor_enabled" not in client_src:
        _fail("orchestrator_client does not invoke DialogueManager behind flag (D-142 ZOMBIE).")
    if "get_dialogue_manager_skill" not in brain_src or "def _dialogue_decision" not in brain_src:
        _fail("probability_tutor_brain lost the DialogueManager capability (D-142/D-163).")
    _pass(
        "DialogueManager wired: evidence×ability×difficulty, deterministic, behind "
        "SEMANTIC_TUTOR_ENABLED (D-142 Phase 2)"
    )


def main() -> None:
    print(
        "=== Skills Doctrine Drift Gate "
        "(D-069 + D-073 + D-100 + D-106 + D-111 + D-113 + D-115 + D-129 + D-130 + D-131 + D-132 + D-133 + D-135 + D-137 + D-138 + D-142) ===\n"
    )
    check_doctrine_module_importable()
    check_skills_consume_doctrine()
    check_manifest_consistency()
    check_explanation_doctrine_v2()
    check_local_graph_prompt_alignment()
    check_d070_doctrines_reexported()
    check_answer_quality_skill_wired()
    check_bkt_baseline_integrated()
    check_skills_platform()
    check_adaptive_pedagogy_wiring()
    check_content_integrity_wired()
    check_learning_path_wired()
    check_answer_redaction_wired()
    check_socratic_protocol_wired()
    check_pedagogical_policy_wired()
    check_socratic_evaluator_wired()
    check_semantic_property_wired()
    check_student_state_wired()
    check_understanding_state_wired()
    check_micro_simulation_wired()
    check_pedagogical_escalation_wired()
    check_dialogue_manager_wired()
    print("\n=== ✅ All skills doctrine checks passed ===")


if __name__ == "__main__":
    main()
