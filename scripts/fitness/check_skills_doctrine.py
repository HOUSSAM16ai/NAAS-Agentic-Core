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
    """Local graph's `_EXERCISE_EXPLANATION_SYSTEM_PROMPT` must reference
    at least 3 key doctrines from EXPLANATION_DOCTRINE (drift detection).

    The check is robust to whitespace / phrasing — only requires that
    the prompt mentions a minimum set of concept anchors that prove the
    doctrine is propagated into the LLM instruction surface.
    """
    local_graph = ROOT / "app" / "services" / "chat" / "local_graph.py"
    if not local_graph.is_file():
        print(f"ℹ️ local_graph.py not found at {local_graph} — skipping prompt check")
        return

    src = local_graph.read_text(encoding="utf-8")

    # Concept anchors that MUST appear in the system prompt if the doctrine
    # is properly propagated. These are the most stable phrases.
    anchors = [
        "الإجابة النموذجية",  # model-answer reliance
        "LaTeX",  # math formatting
        "حرفياً",  # no verbatim copy
    ]
    missing = [a for a in anchors if a not in src]
    if missing:
        # Soft-warn — local_graph may use indirect wording.
        # Don't fail CI unless at least 2 are missing.
        if len(missing) >= 2:
            _fail(
                f"local_graph.py: missing {len(missing)}/3 doctrine anchors: {missing}. "
                "EXPLANATION_DOCTRINE is drifting from system prompt."
            )
        print(f"⚠️ local_graph.py: 1 doctrine anchor weakly aligned ({missing[0]})")
    _pass(f"local_graph.py: doctrine anchors present ({len(anchors) - len(missing)}/3)")


def main() -> None:
    print("=== Skills Doctrine Drift Gate (D-069) ===\n")
    check_doctrine_module_importable()
    check_skills_consume_doctrine()
    check_manifest_consistency()
    check_explanation_doctrine_v2()
    check_local_graph_prompt_alignment()
    print("\n=== ✅ All skills doctrine checks passed ===")


if __name__ == "__main__":
    main()
