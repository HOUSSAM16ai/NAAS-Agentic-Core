"""اختبارات واجهة سطر الأوامر لسكربت استيعاب المعرفة.

**لماذا يوجد هذا الملفّ:** كانت وظيفة `Knowledge Ingestion` هي الوظيفة الحمراء الوحيدة على
`main`، وكان لها ثلاثة أعطاب متراكبة يُخفي بعضُها بعضاً:

1. `ModuleNotFoundError: No module named 'app'` — الـ workflow لا يضبط `PYTHONPATH`،
   فالتشغيل يموت قبل قراءة ملفّ واحد.
2. **`main()` لم تكن تقرأ `sys.argv` إطلاقاً.** الـ workflow يستدعيها بمسار ملفّ و`--url`
   و`--dry-run`، وكلّها تُهمَل بصمت ويُعاد استيعاب `data/knowledge/*.md` بدلاً منها —
   عقدٌ مُعلَن في الـ workflow بلا وجود في السكربت.
3. **الحذف الشامل كان بلا شرط**: `DELETE FROM knowledge_edges` + `DELETE FROM
   knowledge_nodes` + `DROP TABLE vectors CASCADE` في كلّ تشغيل. فلو أُصلح العطب الأوّل
   وحده وضُبِط `DATABASE_URL`، لأصبح أوّل دفعٍ إلى `knowledge_base/**` يمحو رسم المعرفة
   على الإنتاج. إصلاح الاستيراد وحده كان سيحوّل عطباً ظاهراً إلى كارثة صامتة.

القاعدة المُختبَرة هنا: **التحقّق من أصل معرفة لا يحتاج قاعدة بيانات**، و**الحذف يحتاج
تصريحاً**، و**الفشل يُرجِع رمز خروج غير صفري** (لا فشل صامت — §0).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ingest_knowledge.py"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """يشغّل السكربت في عملية فرعية نظيفة — بلا `DATABASE_URL`، كما في CI بالضبط."""
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "PYTHONPATH": str(REPO_ROOT),
        "HOME": "/tmp",
    }
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=120,
    )


# ── العقد: التحقّق الجافّ لا يحتاج قاعدة بيانات ──────────────────────────────────


def test_dry_run_validates_json_without_a_database() -> None:
    """الملفّ الذي أسقط CI فعلياً يمرّ الآن — بلا `DATABASE_URL` في البيئة."""
    target = "knowledge_base/entities/bac2024_math_experimental_subject1_ex1_ex2.entities.json"
    result = run_cli(target, "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "valid JSON" in result.stdout
    # البرهان على أنّ الاستيرادات كسولة فعلاً:
    assert "ModuleNotFoundError" not in result.stderr


def test_dry_run_validates_markdown_frontmatter() -> None:
    result = run_cli("knowledge_base/bac2024_math_experimental_subject1_ex1_ex2.md", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "frontmatter keys" in result.stdout


def test_dry_run_reads_the_paths_it_is_given(tmp_path: Path) -> None:
    """العقد الذي لم يكن موجوداً: المسار المُمرَّر هو ما يُقرأ."""
    asset = tmp_path / "only_this_one.json"
    asset.write_text(json.dumps({"marker": 1}), encoding="utf-8")

    result = run_cli(str(asset), "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "only_this_one.json" in result.stdout
    # ولا يُعاد استيعاب المجلّد الافتراضي خلسةً:
    assert "bac_2024_probability" not in result.stdout


def test_url_flag_is_accepted() -> None:
    """الـ workflow يمرّر `--url`؛ رفضها يجعل الوظيفة حمراء بسبب argparse."""
    result = run_cli(
        "knowledge_base/entities/bac2024_math_experimental_subject1_ex1_ex2.entities.json",
        "--url",
        "https://memory.example.invalid",
        "--dry-run",
    )

    assert result.returncode == 0, result.stderr


# ── العقد: الفشل يُرجِع رمزاً غير صفري ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "body", "needle"),
    [
        ("broken.json", '{"unterminated": ', "not valid JSON"),
        ("broken.md", "---\nbad: [unclosed\n---\nbody\n", "invalid frontmatter"),
        ("unclosed.md", "---\nkey: value\n", "never closed"),
        ("scalar.md", "---\njust-a-string\n---\nbody\n", "not a mapping"),
    ],
)
def test_invalid_assets_fail_loudly(tmp_path: Path, name: str, body: str, needle: str) -> None:
    asset = tmp_path / name
    asset.write_text(body, encoding="utf-8")

    result = run_cli(str(asset), "--dry-run")

    assert result.returncode == 1
    assert needle in result.stdout + result.stderr


def test_missing_file_is_a_failure(tmp_path: Path) -> None:
    result = run_cli(str(tmp_path / "absent.md"), "--dry-run")

    assert result.returncode == 1
    assert "does not exist" in result.stdout + result.stderr


def test_plain_document_without_frontmatter_is_accepted(tmp_path: Path) -> None:
    asset = tmp_path / "plain.md"
    asset.write_text("# عنوان\n\nنصّ بلا frontmatter.\n", encoding="utf-8")

    result = run_cli(str(asset), "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "plain document" in result.stdout


# ── العقد: الحذف الشامل يحتاج تصريحاً منطوقاً ────────────────────────────────────


def test_reset_is_opt_in_and_off_by_default() -> None:
    """
    `--reset` هو المفتاح الوحيد للحذف الشامل، والـ workflow لا يمرّره.

    نقرأ المصدر لا السلوك: تشغيل مسار الحذف يحتاج قاعدة بيانات حيّة، وهذا بالضبط ما
    يجب ألّا يحدث في CI. فالبرهان بنيوي — الحذف داخل `if args.reset:`.
    """
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"--reset"' in source
    reset_branch = source.index("if args.reset:")
    for destructive in (
        'text("DELETE FROM knowledge_edges")',
        'text("DELETE FROM knowledge_nodes")',
        'text("DROP TABLE IF EXISTS vectors CASCADE")',
    ):
        assert destructive in source, destructive
        assert source.index(destructive) > reset_branch, (
            f"{destructive} must sit inside the --reset branch, never run unconditionally"
        )


def test_dry_run_never_reaches_the_destructive_path(tmp_path: Path) -> None:
    """`--dry-run` مع `--reset` معاً: التحقّق الجافّ يسبق كلّ شيء فلا يُحذف شيء."""
    asset = tmp_path / "ok.json"
    asset.write_text("{}", encoding="utf-8")

    result = run_cli(str(asset), "--dry-run", "--reset")

    assert result.returncode == 0, result.stderr
    assert "Clearing existing Knowledge Graph" not in result.stdout


# ── العقد: الـ workflow يستدعي ما يفهمه السكربت ───────────────────────────────────


def test_workflow_passes_pythonpath_and_only_known_flags() -> None:
    """يمنع عودة الصنف: الـ workflow لا يمرّر علماً لا يعرفه السكربت، ويضبط `PYTHONPATH`."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "knowledge_ingestion.yml").read_text(
        encoding="utf-8"
    )
    source = SCRIPT.read_text(encoding="utf-8")

    assert "PYTHONPATH:" in workflow, "the ingest step must put the workspace on the import path"

    for flag in ("--url", "--dry-run"):
        assert flag in workflow, f"workflow no longer passes {flag}"
        assert f'"{flag}"' in source, f"script does not declare {flag}"

    assert "--reset" not in workflow, "CI must never request the destructive reset"
