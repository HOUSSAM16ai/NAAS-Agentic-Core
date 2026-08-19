"""البرهان السلبي لفوارض العملية — D-270 (L1 · L2 · L3).

بوّابةٌ تحكم **دخول** التغيير أخطر من بوّابةٍ تفحص المستودع الساكن: إن كانت متساهلة
مرّرت كلّ شيء، وإن كانت عمياء حجبت كلّ شيء. فكلّ قاعدةٍ هنا لها تجربتان — واحدة تُثبت
أنّها تحجب عند الخرق، وأخرى تُثبت أنّها تمرّ على مُدخَلٍ سليم.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_governance_registry as governance_gate
import validate_issue_readiness as issue_gate
import validate_pr_description as pr_gate

#: متغيّرات تُحقَن في **كل** وظيفة GitHub Actions، ويقرؤها المُتحقِّقان كمصدرٍ احتياطي.
_ACTIONS_ENV = ("GITHUB_EVENT_PATH", "GITHUB_TOKEN", "GITHUB_REPOSITORY")


@pytest.fixture(autouse=True)
def _isolate_actions_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """يعزل التجارب عن بيئة Actions.

    ⚠️ **اكتُشِف بالتشغيل في CI لا بالتحليل** (PR #25): تجربة «لا عنوان مُتاحاً» كانت
    خضراء محلياً وحمراء في CI، لأنّ ``GITHUB_EVENT_PATH`` مُعرَّفٌ دائماً داخل Actions —
    فسقط المُتحقِّق إلى حمولة الحدث والتقط **عنوان الـPR الحقيقي**، وهو ليس Conventional
    Commits. أي أنّ الاختبار كان يقيس بيئته لا سلوكه.

    وهذا نفس صنف D-105 (نظافة الاختبارات): اختبارٌ يعتمد على بيئةٍ لا يُصرِّح بها ليس
    اختباراً بل مقياسَ حظّ. العزل هنا بـ``monkeypatch`` لا بكتابةٍ وقت الجمع — تلك
    تحرسها ``check_test_hygiene``.
    """
    for name in _ACTIONS_ENV:
        monkeypatch.delenv(name, raising=False)


# ══════════════════════════════════════════════════════════════════════════════
# L1 · L3 — وصف الدفعة
# ══════════════════════════════════════════════════════════════════════════════
GOOD_TITLE = "feat(governance): add process gates"

GOOD_BODY = """HUMAN:

شغّلتُ البوّابات بنفسي على 3.12 ورأيتها خضراء، وكسرتُ الإعداد يدوياً للتأكّد من الحجب.

AGENT:

---

## Why
القالب كان بلا فارض.

## Summary
- إضافة بوّابتَي عملية.

## Issue Number
Fixes #1

## How to Test
```bash
python scripts/run_fitness_gates.py
```

## Change Type
- [x] governance / documentation

## Risk & Rollback
- **Risk level:** low

## Validation Evidence
```
30 passed
```
"""


def _run_pr(
    body: str, *, title: str | None = GOOD_TITLE, files: list[str] | None = None, tmp_path: Path
) -> tuple[int, str]:
    body_file = tmp_path / "body.md"
    body_file.write_text(body, encoding="utf-8")
    argv = ["--body-file", str(body_file)]
    if title is not None:
        argv += ["--title", title]
    if files is not None:
        files_file = tmp_path / "files.txt"
        files_file.write_text("\n".join(files), encoding="utf-8")
        argv += ["--files-file", str(files_file)]
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = pr_gate.main(argv)
    return code, buffer.getvalue()


def test_pr_accepts_complete_description(tmp_path: Path) -> None:
    code, out = _run_pr(GOOD_BODY, tmp_path=tmp_path)
    assert code == 0, out


def test_pr_rejects_non_conventional_title(tmp_path: Path) -> None:
    """العنوان هو ما يُقرأ في `git log` بعد سنة."""
    code, out = _run_pr(GOOD_BODY, title="added some stuff", tmp_path=tmp_path)
    assert code == 1
    assert "Conventional Commits" in out


@pytest.mark.parametrize("section", ["Why", "Summary", "How to Test"])
def test_pr_rejects_missing_required_section(section: str, tmp_path: Path) -> None:
    body = GOOD_BODY.replace(f"## {section}", f"## {section}-removed")
    code, out = _run_pr(body, tmp_path=tmp_path)
    assert code == 1
    assert section in out


def test_pr_rejects_missing_human_section(tmp_path: Path) -> None:
    """⛔ الموضع الوحيد الذي يشهد فيه إنسان — لا يكتبه وكيل."""
    code, out = _run_pr(GOOD_BODY.replace("HUMAN:", "NOTES:"), tmp_path=tmp_path)
    assert code == 1
    assert "HUMAN" in out


def test_pr_rejects_token_human_note(tmp_path: Path) -> None:
    body = GOOD_BODY.replace(
        "شغّلتُ البوّابات بنفسي على 3.12 ورأيتها خضراء، وكسرتُ الإعداد يدوياً للتأكّد من الحجب.",
        "ok",
    )
    code, out = _run_pr(body, tmp_path=tmp_path)
    assert code == 1
    assert "HUMAN" in out


def test_pr_rejects_claim_without_command_output(tmp_path: Path) -> None:
    """«تشغيل اختبارات الوحدة لا يكفي»: يُطلَب الأمر ومخرَجه."""
    body = GOOD_BODY.replace("```bash\npython scripts/run_fitness_gates.py\n```", "ran the tests")
    body = body.replace("```\n30 passed\n```", "all green")
    code, out = _run_pr(body, tmp_path=tmp_path)
    assert code == 1
    assert "دليل تنفيذ" in out


def test_pr_rejects_bugfix_without_reproduction(tmp_path: Path) -> None:
    """يمدّ D-186: العقد يُثبَت أحمر قبل الإصلاح — مرفوعاً من الاختبار إلى الدفعة."""
    body = GOOD_BODY.replace("- [x] governance / documentation", "- [x] bug fix")
    body = body.replace("```bash\npython scripts/run_fitness_gates.py\n```", "see below")
    body = body.replace("```\n30 passed\n```", "fixed")
    code, out = _run_pr(body, tmp_path=tmp_path)
    assert code == 1
    assert "إعادة إنتاج" in out


def test_pr_rejects_frontend_change_without_media(tmp_path: Path) -> None:
    """ما يراه الطالب يُرى في المراجعة."""
    code, out = _run_pr(GOOD_BODY, files=["frontend/app/page.jsx"], tmp_path=tmp_path)
    assert code == 1
    assert "الواجهة" in out


def test_pr_accepts_frontend_change_with_screenshot(tmp_path: Path) -> None:
    body = GOOD_BODY + "\n## Video/Screenshots\n![after](https://example.invalid/a.png)\n"
    code, out = _run_pr(body, files=["frontend/app/page.jsx"], tmp_path=tmp_path)
    assert code == 0, out


def test_pr_rejects_missing_linked_issue(tmp_path: Path) -> None:
    code, out = _run_pr(GOOD_BODY.replace("Fixes #1", "TBD"), tmp_path=tmp_path)
    assert code == 1
    assert "بلاغ مرتبط" in out


def test_pr_rejects_empty_body(tmp_path: Path) -> None:
    code, _ = _run_pr("   \n", tmp_path=tmp_path)
    assert code == 1


def test_pr_skips_title_rule_when_title_unknown(tmp_path: Path) -> None:
    """ما لا يُقرأ لا يُشهَد عليه: تشغيلٌ محلّي بلا `--title` لا يخترع حكماً."""
    code, out = _run_pr(GOOD_BODY, title=None, tmp_path=tmp_path)
    assert code == 0, out


def test_pr_template_itself_fails_until_filled() -> None:
    """القالب كما هو **يجب** أن يسقط — قالبٌ يمرّ فارغاً ليس عقداً."""
    template = (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = pr_gate.main(
            [
                "--title",
                GOOD_TITLE,
                "--body-file",
                str(REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"),
            ]
        )
    assert code == 1
    assert "HUMAN" in template


def test_pr_required_sections_exist_in_template() -> None:
    """كل قسمٍ يفرضه المُتحقِّق موجودٌ في القالب — وإلّا استحال إرضاؤه."""
    template = (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    for section in pr_gate.REQUIRED_SECTIONS:
        assert f"## {section}" in template, section


# ══════════════════════════════════════════════════════════════════════════════
# L2 — جاهزية البلاغ
# ══════════════════════════════════════════════════════════════════════════════
GOOD_BUG = """### Summary
gate stays green while the rule is broken

### Reproduction steps
1) break the config
2) run the gate

### Logs / traces / screenshots
```
exit 0 (expected 1)
```

### Acceptance criteria
- [ ] البوّابة تخرج بـ1 عند الخرق
"""

GOOD_FEATURE = """### Problem statement
no gate for X

### Proposed solution
add check_x.py

### Acceptance criteria
- [ ] برهانٌ سلبي مُثبَت
"""


def _run_issue(body: str, labels: str, tmp_path: Path) -> tuple[int, str]:
    body_file = tmp_path / "issue.md"
    body_file.write_text(body, encoding="utf-8")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = issue_gate.main(["--body-file", str(body_file), "--labels", labels])
    return code, buffer.getvalue()


def test_issue_accepts_complete_bug(tmp_path: Path) -> None:
    code, out = _run_issue(GOOD_BUG, "type:bug", tmp_path)
    assert code == 0, out


def test_issue_accepts_complete_feature(tmp_path: Path) -> None:
    code, out = _run_issue(GOOD_FEATURE, "type:feature", tmp_path)
    assert code == 0, out


def test_issue_rejects_untyped(tmp_path: Path) -> None:
    """النوع المجهول لا يُقاس عليه شيء."""
    code, out = _run_issue(GOOD_BUG, "", tmp_path)
    assert code == 1
    assert "نوع" in out


def test_issue_rejects_bug_without_acceptance_criteria(tmp_path: Path) -> None:
    """ISS-145: من لا يكتب شرط النجاح مُسبَقاً يخترعه بعد الإصلاح."""
    body = GOOD_BUG.split("### Acceptance criteria")[0]
    code, out = _run_issue(body, "type:bug", tmp_path)
    assert code == 1
    assert "Acceptance criteria" in out


def test_issue_rejects_acceptance_prose_without_checklist(tmp_path: Path) -> None:
    body = GOOD_BUG.replace("- [ ] البوّابة تخرج بـ1 عند الخرق", "سنعرف حين نراه")
    code, out = _run_issue(body, "type:bug", tmp_path)
    assert code == 1
    assert "مؤشَّرة" in out


def test_issue_rejects_bug_without_evidence(tmp_path: Path) -> None:
    body = GOOD_BUG.replace("```\nexit 0 (expected 1)\n```", "it just fails")
    code, out = _run_issue(body, "type:bug", tmp_path)
    assert code == 1
    assert "دليل ملموس" in out


def test_issue_treats_no_response_as_empty(tmp_path: Path) -> None:
    """`_No response_` هو ما يكتبه GitHub لحقلٍ فارغ — لا يُقرأ محتوى."""
    body = GOOD_BUG.replace("1) break the config\n2) run the gate", "_No response_")
    code, out = _run_issue(body, "type:bug", tmp_path)
    assert code == 1
    assert "Reproduction steps" in out


def test_issue_rejects_feature_without_acceptance(tmp_path: Path) -> None:
    body = GOOD_FEATURE.split("### Acceptance criteria")[0]
    code, _ = _run_issue(body, "type:feature", tmp_path)
    assert code == 1


def test_issue_json_shape_is_machine_readable(tmp_path: Path) -> None:
    """الـworkflow يقرأ هذا المخرَج — فشكله عقد."""
    body_file = tmp_path / "issue.md"
    body_file.write_text(GOOD_BUG, encoding="utf-8")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        issue_gate.main(["--body-file", str(body_file), "--labels", "type:bug", "--json"])
    payload = json.loads(buffer.getvalue())
    assert payload == {"ready": True, "reasons": []}


def test_issue_templates_expose_every_required_field() -> None:
    """كل حقلٍ يفرضه المُتحقِّق موجودٌ في القالب — وإلّا استحال إرضاؤه."""
    bug = (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").read_text(encoding="utf-8")
    feature = (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml").read_text(
        encoding="utf-8"
    )
    for label, _ in issue_gate.BUG_FIELDS:
        assert label in bug, label
    for label, _ in issue_gate.FEATURE_FIELDS:
        assert label in feature, label


# ══════════════════════════════════════════════════════════════════════════════
# تسجيل فوارض العملية — موطنٌ مُعلَن لا مُكتشَف
# ══════════════════════════════════════════════════════════════════════════════
def _run_process(root: Path, registry: dict) -> tuple[int, str]:
    saved = governance_gate.REPO_ROOT
    governance_gate.REPO_ROOT = root
    governance_gate._FAILURES.clear()
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            governance_gate._check_process_enforcers(registry)
        failures = len(governance_gate._FAILURES)
    finally:
        governance_gate.REPO_ROOT = saved
        governance_gate._FAILURES.clear()
    return failures, buffer.getvalue()


@pytest.fixture
def process_tree(tmp_path: Path) -> Path:
    (tmp_path / ".github" / "scripts").mkdir(parents=True)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "scripts" / "validate_x.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows" / "x.yml").write_text(
        "run: python .github/scripts/validate_x.py\n", encoding="utf-8"
    )
    return tmp_path


_PROCESS_STUB = {
    "process_enforcers": {
        "home": ".github/scripts",
        "enforcers": {"validate_x.py": {"law": "L?", "workflow": ".github/workflows/x.yml"}},
    }
}


def test_process_enforcer_green_when_workflow_runs_it(process_tree: Path) -> None:
    failures, out = _run_process(process_tree, _PROCESS_STUB)
    assert failures == 0, out


def test_process_enforcer_rejects_workflow_that_never_calls_it(process_tree: Path) -> None:
    """نفس صنف ISS-186: فارضٌ على القرص بلا مرمى."""
    (process_tree / ".github" / "workflows" / "x.yml").write_text(
        "run: echo hi\n", encoding="utf-8"
    )
    failures, out = _run_process(process_tree, _PROCESS_STUB)
    assert failures == 1
    assert "لا يستدعيه" in out


def test_process_enforcer_rejects_undeclared_script(process_tree: Path) -> None:
    """موطنٌ بلا إعلانٍ يعني فارضاً غير مرئي (D-266)."""
    (process_tree / ".github" / "scripts" / "validate_y.py").write_text("y = 1\n", encoding="utf-8")
    failures, out = _run_process(process_tree, _PROCESS_STUB)
    assert failures == 1
    assert "validate_y.py" in out


def test_process_enforcer_rejects_missing_section(process_tree: Path) -> None:
    failures, out = _run_process(process_tree, {})
    assert failures == 1
    assert "process_enforcers" in out


def test_governance_registry_green_on_real_repository() -> None:
    governance_gate._FAILURES.clear()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = governance_gate.main()
    governance_gate._FAILURES.clear()
    assert code == 0, buffer.getvalue()
