"""اختبارات بوّابة تكافؤ التقاط السرّ — D-268 (ISS-191).

بوّابةٌ لا تُختبَر على **انتهاكٍ مزروع** لا يُعرَف أنّها تفشل أصلاً — وهذا بالضبط
«الثمن الثاني» في `ENGINEERING_DOCTRINE.md` (فارضٌ بلا مرمى). فكلّ بندٍ من البنود
الخمسة له هنا تجربةٌ سلبية، ويُتحقَّق أنّ الفشل **للسبب الصحيح** لا لأيّ سبب.

⚠️ الاختبارات تعمل على **نسخةٍ من الشجرة** في مجلّدٍ مؤقّت — فلا تلمس المستودع.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_secret_capture_parity as gate

#: الأشجار التي تلمسها البوّابة. نسخُ الشجرة كاملةً لا يلزم، ونسخُ أقلّ منها يُنتج
#: أساساً أحمر — وقد وقع ذلك فعلاً أثناء بناء هذه الاختبارات (نُسي `scripts/`)، فبدا
#: كلُّ شيءٍ «يفشل بنجاح». الأساسُ الأخضر شرطُ صحّة كلّ تجربةٍ سلبية بعده.
_TREES = ("config", ".devcontainer", "scripts", "app", ".github/workflows")
_FILES = (".env.example", ".env.codespaces.example", "docker-compose.codespaces.yml")


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """نسخةٌ عاملة من الشجرة الملموسة."""
    for rel in _TREES:
        src = REPO_ROOT / rel
        if src.is_dir():
            shutil.copytree(
                src,
                tmp_path / rel,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
    for name in _FILES:
        shutil.copy(REPO_ROOT / name, tmp_path / name)
    return tmp_path


def _run(root: Path) -> tuple[int, str]:
    """يشغّل البوّابة على جذرٍ بديل ويُعيد (رمز الخروج، المخرَج)."""
    saved = (
        gate.REPO_ROOT,
        gate.CATALOG,
        gate.SETTINGS,
        gate.COMMITTED_SECRETS_GATE,
        gate.APP_TREE,
    )
    gate.REPO_ROOT = root
    gate.CATALOG = root / "config" / "secret_catalog.json"
    gate.SETTINGS = root / "app" / "core" / "settings" / "base.py"
    gate.COMMITTED_SECRETS_GATE = root / "scripts" / "fitness" / "check_no_committed_secrets.py"
    gate.APP_TREE = root / "app"
    gate._FAILURES.clear()
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            code = gate.main()
    finally:
        (
            gate.REPO_ROOT,
            gate.CATALOG,
            gate.SETTINGS,
            gate.COMMITTED_SECRETS_GATE,
            gate.APP_TREE,
        ) = saved
        gate._FAILURES.clear()
    return code, buffer.getvalue()


def _catalog(root: Path) -> dict:
    return json.loads((root / "config" / "secret_catalog.json").read_text(encoding="utf-8"))


def _write_catalog(root: Path, data: dict) -> None:
    (root / "config" / "secret_catalog.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ─────────────────────────────────────────────────────────────────────────────
# الأساس — بلا هذا لا معنى لأيّ تجربةٍ سلبية بعده
# ─────────────────────────────────────────────────────────────────────────────
def test_repository_is_green(sandbox: Path) -> None:
    code, out = _run(sandbox)
    assert code == 0, f"الأساس أحمر — كلّ ما بعده بلا معنى:\n{out}"


def test_every_door_classified_for_every_secret() -> None:
    """كلّ خانةٍ (سرّ × باب) مُصنَّفة — الفراغ يُقرأ نجاحاً (D-206 L11)."""
    catalog = json.loads((REPO_ROOT / "config" / "secret_catalog.json").read_text(encoding="utf-8"))
    doors = set(catalog["doors"])
    for secret in catalog["secrets"]:
        classified = set(secret["doors"]) | set(secret.get("doors_not_applicable", {}))
        assert classified == doors, (
            f"{secret['name']}: خانات بلا تصنيف {sorted(doors - classified)}"
        )


def test_honcho_is_captured_and_readable() -> None:
    """الطلب الأصلي: `HONCHO_API_KEY` مُلتقَطٌ وله قارئٌ قانوني."""
    catalog = json.loads((REPO_ROOT / "config" / "secret_catalog.json").read_text(encoding="utf-8"))
    honcho = next(s for s in catalog["secrets"] if s["name"] == "HONCHO_API_KEY")
    assert honcho["lawful_reader"] == "HONCHO_API_KEY"
    assert honcho["value_pattern"], "بلا نمطٍ يبقى التزامُ المفتاح ممكناً"
    for required in (
        "devcontainer_remote_env",
        "supervisor_inject",
        "app_settings",
        "live_e2e_env",
    ):
        assert required in honcho["doors"], f"باب {required} مفقود"


# ─────────────────────────────────────────────────────────────────────────────
# التجارب السلبية — بندٌ بندٌ
# ─────────────────────────────────────────────────────────────────────────────
def test_missing_door_is_red(sandbox: Path) -> None:
    """البند 1: سرٌّ سقط من بابٍ يُصرِّحه."""
    path = sandbox / ".devcontainer" / "devcontainer.json"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            '"HONCHO_API_KEY": "${localEnv:HONCHO_API_KEY}",', ""
        ),
        encoding="utf-8",
    )
    code, out = _run(sandbox)
    assert code == 1
    assert "HONCHO_API_KEY غائبٌ عن الباب «devcontainer_remote_env»" in out


def test_uncatalogued_external_key_is_red(sandbox: Path) -> None:
    """البند 2: مفتاحٌ خارجي عند بابٍ بلا صفٍّ في الكتالوج (التغطية عكسياً)."""
    path = sandbox / ".env.codespaces.example"
    path.write_text(path.read_text(encoding="utf-8") + "\nCOHERE_API_KEY=x\n", encoding="utf-8")
    code, out = _run(sandbox)
    assert code == 1
    assert "COHERE_API_KEY" in out


def test_declared_alias_is_not_flagged(sandbox: Path) -> None:
    """البند 2 عكساً: الرديف المُعلَن ليس سرّاً جديداً — وإلّا صار البند ضجيجاً."""
    path = sandbox / ".env.example"
    path.write_text(
        path.read_text(encoding="utf-8") + "\nPLANNING_OPENROUTER_API_KEY=x\n", encoding="utf-8"
    )
    code, out = _run(sandbox)
    assert code == 0, out


def test_missing_door_file_is_red(sandbox: Path) -> None:
    """البند 3: بابٌ مُعلَن يشير إلى ملفٍّ غير موجود (ISS-149)."""
    catalog = _catalog(sandbox)
    catalog["doors"]["ghost"] = {"path": "no/such.yml", "form": "yaml_key", "why_ar": "x"}
    _write_catalog(sandbox, catalog)
    code, out = _run(sandbox)
    assert code == 1
    assert "ghost" in out


def test_unknown_door_form_is_red(sandbox: Path) -> None:
    """البند 3: شكلٌ لا تعرف البوّابة فحصه — لا يُتخطّى بصمت."""
    catalog = _catalog(sandbox)
    catalog["doors"]["odd"] = {"path": ".env.example", "form": "telepathy", "why_ar": "x"}
    _write_catalog(sandbox, catalog)
    code, out = _run(sandbox)
    assert code == 1
    assert "غير معروفٍ لهذه البوّابة" in out


def test_wrong_lawful_reader_is_red(sandbox: Path) -> None:
    """البند 4: قارئٌ مُعلَن لا وجود له في AppSettings."""
    catalog = _catalog(sandbox)
    for secret in catalog["secrets"]:
        if secret["name"] == "HONCHO_API_KEY":
            secret["lawful_reader"] = "HONCHO_KEY_TYPO"
    _write_catalog(sandbox, catalog)
    code, out = _run(sandbox)
    assert code == 1
    assert "HONCHO_KEY_TYPO" in out


def test_os_environ_read_in_app_is_red(sandbox: Path) -> None:
    """البند 4: قراءةُ سرٍّ مُكتلَج بـ`os.environ` داخل `app/` (CLAUDE.md §6)."""
    path = sandbox / "app" / "core" / "db_health.py"
    path.write_text(
        path.read_text(encoding="utf-8") + '\nimport os\n_x = os.environ.get("HONCHO_API_KEY")\n',
        encoding="utf-8",
    )
    code, out = _run(sandbox)
    assert code == 1
    assert "os.environ` داخل `app/" in out


def test_settings_package_is_exempt(sandbox: Path) -> None:
    """البند 4 عكساً: حزمة الإعدادات هي القارئ بالتعريف — استثناءٌ منطوق لا صامت."""
    path = sandbox / "app" / "core" / "settings" / "helpers.py"
    path.write_text(
        path.read_text(encoding="utf-8") + '\n_y = os.environ.get("HONCHO_API_KEY")\n',
        encoding="utf-8",
    )
    code, out = _run(sandbox)
    assert code == 0, out


def test_hand_typed_pattern_is_red(sandbox: Path) -> None:
    """البند 5: نمطٌ مكتوبٌ حرفياً في البوّابة بدل اشتقاقه من الكتالوج (D-192)."""
    path = sandbox / "scripts" / "fitness" / "check_no_committed_secrets.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "GENERIC_PATTERNS: tuple[tuple[str, str], ...] = (",
            "GENERIC_PATTERNS: tuple[tuple[str, str], ...] = (\n    "
            '(r"hch-v[0-9]-(?P<secret>[A-Za-z0-9]{32,})", "x"),',
        ),
        encoding="utf-8",
    )
    code, out = _run(sandbox)
    assert code == 1
    assert "مكتوبٌ **حرفياً**" in out


def test_blank_not_applicable_reason_is_red(sandbox: Path) -> None:
    """L9: بابٌ غير منطبقٍ بلا سبب — الغياب يُعلَن ولا يُقرأ نجاحاً."""
    catalog = _catalog(sandbox)
    for secret in catalog["secrets"]:
        if secret["name"] == "HONCHO_API_KEY":
            secret["doors_not_applicable"]["env_example"] = "   "
    _write_catalog(sandbox, catalog)
    code, out = _run(sandbox)
    assert code == 1
    assert "بلا سبب" in out


# ─────────────────────────────────────────────────────────────────────────────
# اشتقاق الأنماط — الجانب الآخر من البند 5
# ─────────────────────────────────────────────────────────────────────────────
def test_committed_secrets_gate_knows_the_honcho_shape() -> None:
    """قبل D-268 كان مفتاح `hch-v3-…` يمرّ من بوّابة الالتزام بلا اعتراض."""
    import check_no_committed_secrets as committed

    patterns = [pattern for pattern, _ in committed._secret_patterns()]
    assert any("hch-v" in pattern for pattern in patterns), "شكلُ مفتاح Honcho غير معروفٍ للبوّابة"


def test_committed_secrets_gate_refuses_to_run_blind(tmp_path: Path) -> None:
    """⛔ بوّابةٌ فقدت مصدرها تُبرِّئ شجرةً لم تفحصها — فترفع بدل أن تُرجِع قائمةً فارغة."""
    import check_no_committed_secrets as committed

    saved = committed.CATALOG_PATH
    committed.CATALOG_PATH = tmp_path / "absent.json"
    try:
        with pytest.raises(committed.CatalogUnreadableError):
            committed._catalog_patterns()
    finally:
        committed.CATALOG_PATH = saved
