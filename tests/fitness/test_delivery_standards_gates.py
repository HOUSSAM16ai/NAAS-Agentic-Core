"""البرهان السلبي لبوّابات معايير التسليم — D-270 (L6 · L7 · L8).

**لماذا هذا الملفّ:** ISS-148 علّمت هذا المستودع أنّ **فارضاً بلا مرمى** أخطر من غيابه:
عقود ترانسكريبت كانت خضراء بينما مسار التسريب خارج مرماها كلّها. فبوّابةٌ لا يُثبَت
أنّها **تحجب** ليست بوّابة — هي نصٌّ يُقرأ حمايةً. كلّ فحصٍ هنا يكسر مُدخَلاً اصطناعياً
ويؤكّد أنّ البوّابة تخرج بـ≠ 0، ثمّ يؤكّد أنّها تخرج بـ0 على الشجرة الحقيقية.

⚠️ كلّ التجارب على شجرةٍ مؤقّتة صغيرة — لا تُلمَس شجرة المستودع.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_config_credibility as credibility_gate
import check_governance_registry as governance_gate
import check_supply_chain as supply_gate


def _run(gate, **overrides) -> tuple[int, str]:
    """يشغّل `main()` تحت جذرٍ بديل ويُعيد (رمز الخروج، المخرَج)."""
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


# ══════════════════════════════════════════════════════════════════════════════
# L6 — سلسلة التوريد
# ══════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def supply_tree(tmp_path: Path) -> Path:
    """شجرةٌ صغيرة تحاكي الواقع: منظومتان حقيقيتان وتبعياتٌ مُثبَّتة كلّها."""
    (tmp_path / ".github").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "docs" / "governance").mkdir(parents=True)

    (tmp_path / "requirements.txt").write_text("fastapi==0.115.0\nruff==0.14.0\n", encoding="utf-8")
    (tmp_path / "frontend" / "package.json").write_text(
        json.dumps({"dependencies": {"next": "14.2.35"}, "devDependencies": {"eslint": "8.57.0"}}),
        encoding="utf-8",
    )
    (tmp_path / ".github" / "dependabot.yml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "updates": [
                    {
                        "package-ecosystem": "pip",
                        "directory": "/",
                        "cooldown": {"default-days": 7},
                        "groups": {"web": {"patterns": ["fastapi"]}},
                    },
                    {
                        "package-ecosystem": "npm",
                        "directory": "/frontend",
                        "cooldown": {"default-days": 7},
                        "groups": {"next": {"patterns": ["next"]}},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "docs" / "governance" / "SUPPLY_CHAIN.json").write_text(
        json.dumps(
            {
                "dependabot": {
                    "config_path": ".github/dependabot.yml",
                    "required_cooldown_days": 7,
                    "deprecated_keys": ["reviewers", "assignees"],
                    "required_ecosystems": {"pip": "…", "npm": "…"},
                },
                "pin_debt": {"python": {}, "npm": {"frontend/package.json": []}},
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def _supply(root: Path) -> tuple[int, str]:
    return _run(
        supply_gate,
        REPO_ROOT=root,
        POLICY=root / "docs" / "governance" / "SUPPLY_CHAIN.json",
        FRONTEND_PKG=root / "frontend" / "package.json",
    )


def _mutate_dependabot(root: Path, mutate) -> None:
    path = root / ".github" / "dependabot.yml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(config)
    path.write_text(yaml.safe_dump(config), encoding="utf-8")


def test_supply_chain_green_on_healthy_tree(supply_tree: Path) -> None:
    code, out = _supply(supply_tree)
    assert code == 0, out


def test_supply_chain_rejects_missing_cooldown(supply_tree: Path) -> None:
    """نسخةٌ رُفعت قبل ساعة تُدمَج آلياً — باب الحزمة المُختطَفة."""
    _mutate_dependabot(supply_tree, lambda c: c["updates"][0].pop("cooldown"))
    code, out = _supply(supply_tree)
    assert code == 1
    assert "cooldown" in out


def test_supply_chain_rejects_ghost_directory(supply_tree: Path) -> None:
    """`/ai_service` كان مُستهدَفاً وهو غير موجود — تغطيةٌ موعودة لا تحدث."""
    _mutate_dependabot(supply_tree, lambda c: c["updates"][0].update(directory="/ai_service"))
    code, out = _supply(supply_tree)
    assert code == 1
    assert "ai_service" in out


def test_supply_chain_rejects_pattern_matching_nothing(supply_tree: Path) -> None:
    """`flask*` و`chromadb*` كانتا مجموعتين لحزمٍ لا وجود لها في المستودع."""
    _mutate_dependabot(
        supply_tree, lambda c: c["updates"][0]["groups"].update(ghost={"patterns": ["flask*"]})
    )
    code, out = _supply(supply_tree)
    assert code == 1
    assert "flask*" in out


def test_supply_chain_rejects_deprecated_keys(supply_tree: Path) -> None:
    """`reviewers` يتجاهله Dependabot بصمت — يُقرأ حمايةً وليس حماية."""
    _mutate_dependabot(supply_tree, lambda c: c["updates"][0].update(reviewers=["someone"]))
    code, out = _supply(supply_tree)
    assert code == 1
    assert "reviewers" in out


def test_supply_chain_rejects_uncovered_ecosystem(supply_tree: Path) -> None:
    """أخطر فجوة: تغطيةٌ تبدو شاملة وليست كذلك، فلا يسألها أحد."""
    _mutate_dependabot(supply_tree, lambda c: c["updates"].pop(1))
    code, out = _supply(supply_tree)
    assert code == 1
    assert "npm" in out


def test_supply_chain_rejects_new_unpinned_dependency(supply_tree: Path) -> None:
    """الدَّين يتقلّص فقط: تبعيةٌ جديدة بلا `==` ⇒ أحمر."""
    (supply_tree / "requirements.txt").write_text(
        "fastapi==0.115.0\nruff==0.14.0\nredis>=5.0.0\n", encoding="utf-8"
    )
    code, out = _supply(supply_tree)
    assert code == 1
    assert "redis" in out


def test_supply_chain_rejects_stale_closed_debt(supply_tree: Path) -> None:
    """الاتجاه الآخر: دَينٌ أُغلق بلا حذفه من السجلّ كذبٌ أيضاً (D-189)."""
    policy_path = supply_tree / "docs" / "governance" / "SUPPLY_CHAIN.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["pin_debt"]["python"] = {"requirements.txt": ["redis"]}
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    code, out = _supply(supply_tree)
    assert code == 1
    assert "redis" in out


def test_supply_chain_reports_unparsable_config(supply_tree: Path) -> None:
    """⛔ ملفٌّ لم يُحلَّل لا يُعَدّ نظيفاً (D-208 §6)."""
    (supply_tree / ".github" / "dependabot.yml").write_text("updates: [", encoding="utf-8")
    code, out = _supply(supply_tree)
    assert code == 1
    assert "YAML" in out or "صالح" in out


def test_supply_chain_green_on_real_repository() -> None:
    """الاتجاه الموجب: الشجرة الحقيقية تمرّ — وإلّا فالبوّابة تحجب الجميع."""
    code, out = _run(supply_gate)
    assert code == 0, out


# ══════════════════════════════════════════════════════════════════════════════
# L8 — حدّ المصداقية على ما يُشحَن
# ══════════════════════════════════════════════════════════════════════════════
_MIRROR_SOURCE = '_UNFALSIFIABLE = (\n    "صفر أخطاء",\n    "يغيّر البشرية",\n)\n'


@pytest.fixture
def credibility_tree(tmp_path: Path) -> Path:
    (tmp_path / ".github").mkdir()
    (tmp_path / "docs" / "governance").mkdir(parents=True)
    (tmp_path / "scripts" / "fitness").mkdir(parents=True)

    (tmp_path / ".github" / "workflow.yml").write_text("# a plain workflow\n", encoding="utf-8")
    (tmp_path / "scripts" / "fitness" / "check_mirror.py").write_text(
        _MIRROR_SOURCE, encoding="utf-8"
    )
    (tmp_path / "docs" / "governance" / "CREDIBILITY_LIMIT.json").write_text(
        json.dumps(
            {
                "config_scopes": {
                    "directories": [".github"],
                    "directory_suffixes": [".yml"],
                    "root_globs": [],
                    "skip_fragments": [],
                },
                "claims": [
                    {"id": "superhuman", "pattern": "(?i)\\bsuperhuman\\b"},
                    {"id": "guaranteed", "pattern": "(?i)\\bguaranteed\\b"},
                ],
                "prohibition_markers": ["ممنوع", "⛔"],
                "mirrored_gate_lists": {
                    "gates": {
                        "check_mirror.py": {
                            "symbol": "_UNFALSIFIABLE",
                            "entries": ["صفر أخطاء", "يغيّر البشرية"],
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def _credibility(root: Path) -> tuple[int, str]:
    return _run(
        credibility_gate,
        REPO_ROOT=root,
        POLICY=root / "docs" / "governance" / "CREDIBILITY_LIMIT.json",
        GATE_HOME=root / "scripts" / "fitness",
    )


def test_credibility_green_on_clean_config(credibility_tree: Path) -> None:
    code, out = _credibility(credibility_tree)
    assert code == 0, out


def test_credibility_rejects_claim_in_shipped_config(credibility_tree: Path) -> None:
    """«SUPERHUMAN» عاشت في `dependabot.yml` و`pre-commit` حتى D-270."""
    (credibility_tree / ".github" / "workflow.yml").write_text(
        "# SUPERHUMAN dependency management\n", encoding="utf-8"
    )
    code, out = _credibility(credibility_tree)
    assert code == 1
    assert "superhuman" in out.lower()


def test_credibility_allows_line_that_forbids_the_claim(credibility_tree: Path) -> None:
    """درس D-206: سطرٌ يَنهى عن عبارةٍ ليس ادّعاءً بها."""
    (credibility_tree / ".github" / "workflow.yml").write_text(
        "# ⛔ كلمة superhuman ممنوعة في هذا المستودع\n", encoding="utf-8"
    )
    code, out = _credibility(credibility_tree)
    assert code == 0, out


def test_credibility_prohibition_window_spans_neighbouring_line(credibility_tree: Path) -> None:
    """اكتُشِف بالتشغيل لا بالتحليل: `ci.yml` يسرد العبارات في سطرٍ وينهى في التالي."""
    (credibility_tree / ".github" / "workflow.yml").write_text(
        '# the phrases "superhuman", "zero errors"\n# are ⛔ ممنوعة in shipped config\n',
        encoding="utf-8",
    )
    code, out = _credibility(credibility_tree)
    assert code == 0, out


def test_credibility_ignores_match_inside_identifier(credibility_tree: Path) -> None:
    """D-206 L4: العلامة القصيرة لا تختبئ داخل كلمة أخرى."""
    (credibility_tree / ".github" / "workflow.yml").write_text(
        "# see SUPERHUMAN_SIMPLICITY_GUIDE.md\n", encoding="utf-8"
    )
    code, out = _credibility(credibility_tree)
    assert code == 0, out


def test_credibility_rejects_silent_mirror_drift(credibility_tree: Path) -> None:
    """قائمةٌ رابعة تولد حين تتفرّق القوائم بصمت — نفس صنف ISS-139."""
    (credibility_tree / "scripts" / "fitness" / "check_mirror.py").write_text(
        '_UNFALSIFIABLE = (\n    "صفر أخطاء",\n    "يغيّر البشرية",\n    "guaranteed",\n)\n',
        encoding="utf-8",
    )
    code, out = _credibility(credibility_tree)
    assert code == 1
    assert "guaranteed" in out


def test_credibility_reports_unparsable_gate(credibility_tree: Path) -> None:
    """⛔ بوّابةٌ لم تُقرأ لا يُشهَد لها بالتكافؤ (D-208 §6)."""
    (credibility_tree / "scripts" / "fitness" / "check_mirror.py").write_text(
        "_UNFALSIFIABLE = (\n", encoding="utf-8"
    )
    code, out = _credibility(credibility_tree)
    assert code == 1
    assert "تحليل" in out


def test_credibility_rejects_scope_matching_nothing(credibility_tree: Path) -> None:
    """نطاقٌ خاطئ يُقرأ نجاحاً — وهو أسوأ من انتهاكٍ صريح."""
    policy_path = credibility_tree / "docs" / "governance" / "CREDIBILITY_LIMIT.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["config_scopes"]["directory_suffixes"] = [".nothing"]
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    code, _ = _credibility(credibility_tree)
    assert code == 1


def test_credibility_green_on_real_repository() -> None:
    code, out = _run(credibility_gate)
    assert code == 0, out


# ══════════════════════════════════════════════════════════════════════════════
# L7 — الفارض المحلّي مطابقٌ لـCI أو مُعلَنٌ ميتاً
# ══════════════════════════════════════════════════════════════════════════════
_REGISTRY_STUB = {
    "local_enforcers": {
        "configs": {
            ".pre-commit-config.yaml": {
                "mirrors": [
                    {"tool": "ruff", "repo": "astral-sh/ruff-pre-commit"},
                    {"tool": "mypy", "repo": "pre-commit/mirrors-mypy"},
                ],
                "forbidden_tools": {"black": "مُنسِّقٌ ثانٍ يناقض ruff format"},
                "local_only_repos": {"pre-commit/pre-commit-hooks": "نظافة ملفّات"},
            }
        },
        "unenforced_local_debt": {},
    }
}


@pytest.fixture
def enforcer_tree(tmp_path: Path) -> Path:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        'run: pip install "ruff==0.14.0" "mypy==1.8.0"\n', encoding="utf-8"
    )
    (tmp_path / ".pre-commit-config.yaml").write_text(
        yaml.safe_dump(
            {
                "repos": [
                    {
                        "repo": "https://github.com/pre-commit/pre-commit-hooks",
                        "rev": "v5.0.0",
                        "hooks": [{"id": "end-of-file-fixer"}],
                    },
                    {
                        "repo": "https://github.com/astral-sh/ruff-pre-commit",
                        "rev": "v0.14.0",
                        "hooks": [{"id": "ruff"}, {"id": "ruff-format"}],
                    },
                    {
                        "repo": "https://github.com/pre-commit/mirrors-mypy",
                        "rev": "v1.8.0",
                        "hooks": [{"id": "mypy"}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def _enforcers(root: Path, registry: dict) -> tuple[int, str]:
    saved = (governance_gate.REPO_ROOT, governance_gate.CI_WORKFLOW)
    governance_gate.REPO_ROOT = root
    governance_gate.CI_WORKFLOW = root / ".github" / "workflows" / "ci.yml"
    governance_gate._FAILURES.clear()
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            governance_gate._check_local_enforcers(registry)
        failures = len(governance_gate._FAILURES)
    finally:
        governance_gate.REPO_ROOT, governance_gate.CI_WORKFLOW = saved
        governance_gate._FAILURES.clear()
    return failures, buffer.getvalue()


def _stub(**patch) -> dict:
    registry = json.loads(json.dumps(_REGISTRY_STUB))
    registry["local_enforcers"]["configs"][".pre-commit-config.yaml"].update(patch)
    return registry


def _rewrite_precommit(root: Path, mutate) -> None:
    path = root / ".pre-commit-config.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(config)
    path.write_text(yaml.safe_dump(config), encoding="utf-8")


def test_local_enforcer_green_when_mirroring_ci(enforcer_tree: Path) -> None:
    failures, out = _enforcers(enforcer_tree, _stub())
    assert failures == 0, out


def test_local_enforcer_rejects_pin_drift(enforcer_tree: Path) -> None:
    """أداةٌ تختلف بين الفارضين ليست فارضاً بل مصيدة."""
    _rewrite_precommit(enforcer_tree, lambda c: c["repos"][1].update(rev="v0.15.8"))
    failures, out = _enforcers(enforcer_tree, _stub())
    assert failures == 1
    assert "0.15.8" in out and "0.14.0" in out


def test_local_enforcer_rejects_second_formatter(enforcer_tree: Path) -> None:
    """`black`@88 مقابل `ruff format`@100: 7917 سطراً متضارباً في المستودع الحقيقي."""
    _rewrite_precommit(
        enforcer_tree,
        lambda c: c["repos"].append(
            {"repo": "https://github.com/psf/black", "rev": "24.10.0", "hooks": [{"id": "black"}]}
        ),
    )
    failures, out = _enforcers(enforcer_tree, _stub())
    assert failures >= 1
    assert "black" in out


def test_local_enforcer_rejects_undeclared_hook_repo(enforcer_tree: Path) -> None:
    """كل فارضٍ محلّي إمّا مرآةٌ لـCI وإمّا مُعلَنٌ بسببه (D-206 L11)."""
    _rewrite_precommit(
        enforcer_tree,
        lambda c: c["repos"].append(
            {"repo": "https://github.com/PyCQA/bandit", "rev": "1.7.6", "hooks": [{"id": "bandit"}]}
        ),
    )
    failures, out = _enforcers(enforcer_tree, _stub())
    assert failures == 1
    assert "PyCQA/bandit" in out


def test_local_enforcer_rejects_missing_mirror(enforcer_tree: Path) -> None:
    """CI يفرضها والفارض المحلّي لا — فجوةٌ في الاتجاه المعاكس."""
    _rewrite_precommit(enforcer_tree, lambda c: c["repos"].pop(2))
    failures, out = _enforcers(enforcer_tree, _stub())
    assert failures == 1
    assert "mypy" in out


def test_local_enforcer_rejects_empty_debt_reason(enforcer_tree: Path) -> None:
    """الخانة الفارغة تُقرأ نجاحاً (D-206 L11)."""
    registry = _stub()
    registry["local_enforcers"]["unenforced_local_debt"] = {"shellcheck": ""}
    failures, _ = _enforcers(enforcer_tree, registry)
    assert failures == 1


def test_local_enforcer_rejects_missing_section(enforcer_tree: Path) -> None:
    """L7 بلا قسمٍ في السجلّ = قانونٌ بلا فارض."""
    failures, out = _enforcers(enforcer_tree, {})
    assert failures == 1
    assert "local_enforcers" in out


def test_local_enforcer_reports_unparsable_config(enforcer_tree: Path) -> None:
    """⛔ إعدادٌ لم يُحلَّل لا يُشهَد له بالتطابق (D-208 §6)."""
    (enforcer_tree / ".pre-commit-config.yaml").write_text("repos: [", encoding="utf-8")
    failures, _ = _enforcers(enforcer_tree, _stub())
    assert failures == 1


def test_governance_registry_green_on_real_repository() -> None:
    """الشجرة الحقيقية تمرّ بالبوّابة كاملةً بعد توسعة L7."""
    code, out = _run(governance_gate)
    assert code == 0, out


def test_precommit_config_has_no_second_formatter() -> None:
    """حارسٌ مباشر على المستودع نفسه — لا يعتمد على السجلّ."""
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hook_ids = {hook["id"] for repo in config["repos"] for hook in repo["hooks"]}
    assert "black" not in hook_ids
    assert "isort" not in hook_ids
    assert {"ruff", "ruff-format", "mypy"} <= hook_ids


@pytest.fixture(autouse=True)
def _keep_repo_untouched() -> None:
    """يؤكّد أنّ أيّ تجربةٍ لم تُغيّر شجرة المستودع."""
    before = (REPO_ROOT / ".pre-commit-config.yaml").read_bytes()
    yield
    assert (REPO_ROOT / ".pre-commit-config.yaml").read_bytes() == before


def test_sandbox_helper_is_isolated(tmp_path: Path) -> None:
    """حارسٌ على الاختبارات نفسها: النسخ المؤقّت لا يلمس الأصل."""
    shutil.copy(REPO_ROOT / ".pre-commit-config.yaml", tmp_path / "copy.yaml")
    (tmp_path / "copy.yaml").write_text("mutated", encoding="utf-8")
    assert (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8") != "mutated"
