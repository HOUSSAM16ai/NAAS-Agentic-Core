"""البرهان السلبي لبوّابات المرحلة الثالثة — D-270 L4/L5 · D-271 L9→L12.

بوّابة L4 حالةٌ خاصّة: هي البوّابة التي تفرض على البوّابات أن **تُثبِت أنّها تحجب**.
فلو مرّت هي نفسها بلا برهانٍ سلبي لكانت المفارقة كاملة.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_agent_skills_spec as skills_gate
import check_external_standards as external_gate
import check_gate_negative_proof as proof_gate
import check_no_magic_strings as magic_gate


def _run(gate, **overrides) -> tuple[int, str]:
    saved = {name: getattr(gate, name) for name in overrides}
    for name, value in overrides.items():
        setattr(gate, name, value)
    gate._FAILURES.clear()
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            code = gate.main()
    finally:
        for name, value in saved.items():
            setattr(gate, name, value)
        gate._FAILURES.clear()
    return code, buffer.getvalue()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# L4 — البوّابة تُثبِت أنّها تحجب
# ══════════════════════════════════════════════════════════════════════════════
_NEGATIVE_TEST = "def test_x():\n    assert code == 1\n    check_alpha\n"
_POSITIVE_TEST = "def test_x():\n    check_alpha\n    assert code == 0\n"


@pytest.fixture
def proof_tree(tmp_path: Path) -> Path:
    (tmp_path / "scripts" / "fitness").mkdir(parents=True)
    (tmp_path / "tools" / "ci").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "scripts" / "fitness" / "check_alpha.py").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "scripts" / "fitness" / "check_beta.py").write_text("b = 1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_alpha.py").write_text(_NEGATIVE_TEST, encoding="utf-8")
    _write_json(
        tmp_path / "docs" / "governance" / "NEGATIVE_PROOFS.json",
        {
            "proven": {"check_alpha.py": ["tests/test_alpha.py"]},
            "frozen_debt": {"check_beta.py": "بلا اختبار بعد"},
        },
    )
    return tmp_path


def _proof(root: Path) -> tuple[int, str]:
    return _run(
        proof_gate,
        REPO_ROOT=root,
        POLICY=root / "docs" / "governance" / "NEGATIVE_PROOFS.json",
        TESTS_ROOT=root / "tests",
    )


def test_negative_proof_green_when_ledger_matches(proof_tree: Path) -> None:
    code, out = _proof(proof_tree)
    assert code == 0, out


def test_negative_proof_rejects_gate_missing_from_ledger(proof_tree: Path) -> None:
    """بوّابةٌ بلا صفّ = غيابٌ صامت، والصمت يُقرأ نجاحاً."""
    (proof_tree / "scripts" / "fitness" / "check_gamma.py").write_text("g = 1\n", encoding="utf-8")
    code, out = _proof(proof_tree)
    assert code == 1
    assert "check_gamma.py" in out


def test_negative_proof_rejects_positive_only_test(proof_tree: Path) -> None:
    """اختبارٌ يتوقّع نجاح البوّابة يُثبِت أنّها تعمل لا أنّها تحجب."""
    (proof_tree / "tests" / "test_alpha.py").write_text(_POSITIVE_TEST, encoding="utf-8")
    code, out = _proof(proof_tree)
    assert code == 1
    assert "لا تؤكّد فشلاً" in out


def test_negative_proof_rejects_ledger_pointing_at_deleted_test(proof_tree: Path) -> None:
    """خريطةٌ تكذب أسوأ من لا خريطة (ISS-149)."""
    (proof_tree / "tests" / "test_alpha.py").unlink()
    code, out = _proof(proof_tree)
    assert code == 1
    assert "غير موجودة" in out


def test_negative_proof_rejects_stale_debt(proof_tree: Path) -> None:
    """الاتجاه الآخر: بوّابةٌ اكتسبت برهاناً وبقيت في الدَّين (D-189)."""
    (proof_tree / "tests" / "test_beta.py").write_text(
        "def test_y():\n    check_beta\n    assert code == 1\n", encoding="utf-8"
    )
    code, out = _proof(proof_tree)
    assert code == 1
    assert "check_beta.py" in out


def test_negative_proof_rejects_empty_debt_reason(proof_tree: Path) -> None:
    _write_json(
        proof_tree / "docs" / "governance" / "NEGATIVE_PROOFS.json",
        {
            "proven": {"check_alpha.py": ["tests/test_alpha.py"]},
            "frozen_debt": {"check_beta.py": ""},
        },
    )
    code, _ = _proof(proof_tree)
    assert code == 1


def test_negative_proof_green_on_real_repository() -> None:
    code, out = _run(proof_gate)
    assert code == 0, out


# ══════════════════════════════════════════════════════════════════════════════
# L5 — الحرفية السحرية ممنوعة
# ══════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def magic_tree(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "one.py").write_text('KEY = "SHARED_SECRET_NAME"\n', encoding="utf-8")
    (tmp_path / "app" / "two.py").write_text('OTHER = "SHARED_SECRET_NAME"\n', encoding="utf-8")
    _write_json(
        tmp_path / "docs" / "governance" / "MAGIC_STRINGS.json",
        {"scopes": ["app"], "frozen_debt": ["SHARED_SECRET_NAME"]},
    )
    return tmp_path


def _magic(root: Path) -> tuple[int, str]:
    return _run(
        magic_gate, REPO_ROOT=root, POLICY=root / "docs" / "governance" / "MAGIC_STRINGS.json"
    )


def test_magic_strings_green_when_debt_matches(magic_tree: Path) -> None:
    code, out = _magic(magic_tree)
    assert code == 0, out


def test_magic_strings_rejects_new_duplicate(magic_tree: Path) -> None:
    """D-191: `CANONICAL_EXERCISE_QUERY` عاش في ٧ مواضع فتعلّم الطالبُ مسألةً ليست مسألته."""
    (magic_tree / "app" / "three.py").write_text('A = "BRAND_NEW_FLAG"\n', encoding="utf-8")
    (magic_tree / "app" / "four.py").write_text('B = "BRAND_NEW_FLAG"\n', encoding="utf-8")
    code, out = _magic(magic_tree)
    assert code == 1
    assert "BRAND_NEW_FLAG" in out


def test_magic_strings_allows_single_home(magic_tree: Path) -> None:
    """الظهور في ملفٍّ واحد ليس دَيناً — هو الموطن."""
    (magic_tree / "app" / "three.py").write_text('ONLY_HERE = "ONLY_ONE_PLACE"\n', encoding="utf-8")
    code, out = _magic(magic_tree)
    assert code == 0, out


def test_magic_strings_rejects_stale_closed_debt(magic_tree: Path) -> None:
    """حرفيةٌ وُحِّدت وبقيت في القائمة كذبٌ أيضاً (D-189)."""
    (magic_tree / "app" / "two.py").write_text("from .one import KEY\n", encoding="utf-8")
    code, out = _magic(magic_tree)
    assert code == 1
    assert "SHARED_SECRET_NAME" in out


def test_magic_strings_reports_unparsable_file(magic_tree: Path) -> None:
    """⛔ `except SyntaxError: return []` كانت في ١٣ فارضاً (ISS-149 F1).

    العقد هنا هو عقد `_ast_util`: `parse_source` **ترفع** ولا تُعيد قيمةً ثالثة،
    و`run_gate` تحوّل الرفع إلى فشلٍ صريح برمز 1. فالتجربة تقيس السلوك كما يعمل
    في CI — لا `main()` عارية.
    """
    (magic_tree / "app" / "broken.py").write_text("def (\n", encoding="utf-8")
    saved = (magic_gate.REPO_ROOT, magic_gate.POLICY)
    magic_gate.REPO_ROOT = magic_tree
    magic_gate.POLICY = magic_tree / "docs" / "governance" / "MAGIC_STRINGS.json"
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            code = magic_gate.run_gate(magic_gate.main)
    finally:
        magic_gate.REPO_ROOT, magic_gate.POLICY = saved
        magic_gate._FAILURES.clear()
    assert code == 1
    assert "تعذّر تحليل" in buffer.getvalue()


def test_magic_strings_green_on_real_repository() -> None:
    code, out = _run(magic_gate)
    assert code == 0, out


# ══════════════════════════════════════════════════════════════════════════════
# L9 · L10 · L11 — معايير المهارات المفتوحة
# ══════════════════════════════════════════════════════════════════════════════
_SKILL_MD = """---
name: demo-skill
description: Repair things. Use when something breaks.
---

# body
"""


def _skills_policy(**overrides) -> dict:
    policy = {
        "glossary_ar": {
            "base_skill": {"meaning_ar": "قدرةٌ برمجية", "home": "app"},
            "agent_skill": {"meaning_ar": "مجلّد SKILL.md", "home": ".claude/skills"},
            "rule_ar": "نظامان متمايزان",
        },
        "agent_skills": {
            "home": ".claude/skills",
            "required_frontmatter": ["name", "description"],
            "allowed_frontmatter": ["name", "description", "license"],
            "trigger_markers": ["Use when"],
        },
        "skill_evaluation": {"evaluated": {}, "unevaluated": {"demo-skill": "بلا تقييمٍ بعد"}},
    }
    policy.update(overrides)
    return policy


@pytest.fixture
def skills_tree(tmp_path: Path) -> Path:
    skill = tmp_path / ".claude" / "skills" / "demo-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(_SKILL_MD, encoding="utf-8")
    (tmp_path / "app" / "services" / "skills").mkdir(parents=True)
    (tmp_path / "app" / "services" / "skills" / "registry.py").write_text("", encoding="utf-8")
    _write_json(tmp_path / "docs" / "governance" / "AGENT_SKILLS.json", _skills_policy())
    return tmp_path


def _skills(root: Path) -> tuple[int, str]:
    return _run(
        skills_gate,
        REPO_ROOT=root,
        POLICY=root / "docs" / "governance" / "AGENT_SKILLS.json",
        BASE_SKILL_REGISTRY=root / "app" / "services" / "skills" / "registry.py",
    )


def test_skills_green_on_conformant_skill(skills_tree: Path) -> None:
    code, out = _skills(skills_tree)
    assert code == 0, out


def test_skills_rejects_name_mismatch(skills_tree: Path) -> None:
    """`name` يطابق المجلّد — وإلّا استُدعيت مهارةٌ غير التي تُقرأ."""
    path = skills_tree / ".claude" / "skills" / "demo-skill" / "SKILL.md"
    path.write_text(_SKILL_MD.replace("name: demo-skill", "name: other-skill"), encoding="utf-8")
    code, out = _skills(skills_tree)
    assert code == 1
    assert "لا يطابق" in out


def test_skills_rejects_description_without_trigger(skills_tree: Path) -> None:
    """الوصف هو سطح الاستدعاء كلّه."""
    path = skills_tree / ".claude" / "skills" / "demo-skill" / "SKILL.md"
    path.write_text(
        _SKILL_MD.replace("Repair things. Use when something breaks.", "Repairs things."),
        encoding="utf-8",
    )
    code, out = _skills(skills_tree)
    assert code == 1
    assert "شرط تشغيل" in out


def test_skills_rejects_field_outside_spec(skills_tree: Path) -> None:
    path = skills_tree / ".claude" / "skills" / "demo-skill" / "SKILL.md"
    path.write_text(
        _SKILL_MD.replace("---\n\n# body", "secret: yes\n---\n\n# body"), encoding="utf-8"
    )
    code, out = _skills(skills_tree)
    assert code == 1
    assert "خارج المواصفة" in out


def test_skills_rejects_missing_skill_file(skills_tree: Path) -> None:
    (skills_tree / ".claude" / "skills" / "demo-skill" / "SKILL.md").unlink()
    code, out = _skills(skills_tree)
    assert code == 1
    assert "SKILL.md" in out


def test_skills_rejects_skill_without_declared_evaluation(skills_tree: Path) -> None:
    """الساق السادسة: الخانة الفارغة تُقرأ نجاحاً (D-206 L11)."""
    policy = _skills_policy()
    policy["skill_evaluation"]["unevaluated"] = {}
    _write_json(skills_tree / "docs" / "governance" / "AGENT_SKILLS.json", policy)
    code, out = _skills(skills_tree)
    assert code == 1
    assert "حالة تقييم" in out


def test_skills_rejects_evaluated_claim_without_evidence(skills_tree: Path) -> None:
    """⛔ الدليل قبل الادّعاء (D-266) — دعوى قياسٍ بلا تاريخٍ ولا دليل."""
    policy = _skills_policy()
    policy["skill_evaluation"] = {
        "evaluated": {"demo-skill": {"verified_on": "2026-01-01"}},
        "unevaluated": {},
    }
    _write_json(skills_tree / "docs" / "governance" / "AGENT_SKILLS.json", policy)
    code, out = _skills(skills_tree)
    assert code == 1
    assert "evidence" in out


def test_skills_rejects_glossary_without_rule(skills_tree: Path) -> None:
    """كلمةٌ بمعنيين بلا إعلان = سُلَّم ثانٍ خفيّ (D-209)."""
    policy = _skills_policy()
    policy["glossary_ar"]["rule_ar"] = ""
    _write_json(skills_tree / "docs" / "governance" / "AGENT_SKILLS.json", policy)
    code, _ = _skills(skills_tree)
    assert code == 1


def test_skills_green_on_real_repository() -> None:
    code, out = _run(skills_gate)
    assert code == 0, out


# ══════════════════════════════════════════════════════════════════════════════
# L12 — التبنّي بقرارٍ مكتوب
# ══════════════════════════════════════════════════════════════════════════════
def _source(**overrides) -> dict:
    row = {
        "id": "demo",
        "repo": "https://example.invalid/demo",
        "verified_on": "2026-08-19",
        "verification_method": "git ls-remote",
        "read_ar": "لم يُقرأ",
        "adopted_ar": "لا شيء",
        "rejected_ar": "سببٌ منطوق",
        "status": "ABSENT",
        "upgrade_condition_ar": "ADR",
        "enforcers": [],
        "no_enforcer_reason_ar": "لا تبنّي",
        "code_paths": [],
    }
    row.update(overrides)
    return row


@pytest.fixture
def external_tree(tmp_path: Path) -> Path:
    (tmp_path / "scripts" / "fitness").mkdir(parents=True)
    _write_json(
        tmp_path / "docs" / "governance" / "EXTERNAL_STANDARDS_REGISTRY.json",
        {"sources": [_source()]},
    )
    return tmp_path


def _external(root: Path, sources: list[dict] | None = None) -> tuple[int, str]:
    if sources is not None:
        _write_json(
            root / "docs" / "governance" / "EXTERNAL_STANDARDS_REGISTRY.json", {"sources": sources}
        )
    return _run(
        external_gate,
        REPO_ROOT=root,
        REGISTRY=root / "docs" / "governance" / "EXTERNAL_STANDARDS_REGISTRY.json",
    )


def test_external_green_on_declared_absence(external_tree: Path) -> None:
    code, out = _external(external_tree)
    assert code == 0, out


def test_external_rejects_absent_with_code(external_tree: Path) -> None:
    """⛔ الفحص في الاتجاهين: كودٌ حيّ بلا حارسٍ أسوأ من الغياب المُعلَن."""
    (external_tree / "scripts" / "fitness" / "adopted.py").write_text("x = 1\n", encoding="utf-8")
    code, out = _external(external_tree, [_source(code_paths=["scripts/fitness/adopted.py"])])
    assert code == 1
    assert "adopted.py" in out


def test_external_rejects_phantom_enforcer(external_tree: Path) -> None:
    code, out = _external(external_tree, [_source(status="ACTIVE", enforcers=["check_nowhere.py"])])
    assert code == 1
    assert "check_nowhere.py" in out


def test_external_rejects_status_outside_ladder(external_tree: Path) -> None:
    """⛔ لا سُلَّم ثانٍ (D-209)."""
    code, out = _external(external_tree, [_source(status="MAYBE")])
    assert code == 1
    assert "سُلَّم" in out


def test_external_rejects_missing_upgrade_condition(external_tree: Path) -> None:
    """الطموح يُصنَّف ولا يُكتَم."""
    code, _ = _external(external_tree, [_source(upgrade_condition_ar="")])
    assert code == 1


def test_external_rejects_silent_absence_of_enforcer(external_tree: Path) -> None:
    code, _ = _external(external_tree, [_source(no_enforcer_reason_ar="")])
    assert code == 1


def test_external_rejects_unverified_source(external_tree: Path) -> None:
    """الوجود يُتحقَّق منه لا يُنقَل عن منشور."""
    code, out = _external(external_tree, [_source(verified_on="")])
    assert code == 1
    assert "verified_on" in out


def test_external_green_on_real_repository() -> None:
    code, out = _run(external_gate)
    assert code == 0, out
