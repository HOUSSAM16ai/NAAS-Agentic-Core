"""بوّابة تكافؤ الواجهة التوليدية تفشل فعلاً (D-230 · ISS-145).

⛔ بوّابةٌ خضراء دائماً ليست بوّابة. كل بندٍ يُثبَت بإفسادٍ متعمَّد.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts/fitness/check_ui_component_parity.py"
BACKEND = REPO_ROOT / "app/contracts/streaming.py"
FRONTEND = REPO_ROOT / "frontend/app/components/generative/GenerativeUIRenderer.jsx"
EMITTER = REPO_ROOT / "app/infrastructure/clients/orchestrator/probability_ui.py"


def _run() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE)], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


@pytest.fixture
def restore():
    saved: list[tuple[Path, str]] = []

    def _save(path: Path) -> None:
        saved.append((path, path.read_text(encoding="utf-8")))

    yield _save
    for path, original in reversed(saved):
        path.write_text(original, encoding="utf-8")


def test_gate_is_green_on_truth() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr


def test_backend_only_component_is_red(restore) -> None:
    """عقدٌ مُعلَنٌ بنصفه: سيصل الطالبَ نصٌّ بديل بدل الكائن (D-192)."""
    restore(BACKEND)
    text = BACKEND.read_text(encoding="utf-8")
    BACKEND.write_text(
        text.replace('"probability_tree",', '"probability_tree",\n        "ghost_card",', 1),
        encoding="utf-8",
    )
    result = _run()
    assert result.returncode == 1
    assert "غائبٌ عن سجلّ التصيير" in result.stdout


def test_frontend_only_component_is_red(restore) -> None:
    """سيرفضه المُطبِّع فلا يصل أبداً — نفس عطب math_explanation_card."""
    restore(FRONTEND)
    text = FRONTEND.read_text(encoding="utf-8")
    FRONTEND.write_text(
        text.replace(
            "    probability_tree: (props) =>",
            "    orphan_card: (props) => <ProbabilityTree props={props} />,\n"
            "    probability_tree: (props) =>",
            1,
        ),
        encoding="utf-8",
    )
    result = _run()
    assert result.returncode == 1
    assert "غائبٌ عن عقد الخادم" in result.stdout


def test_banned_component_is_red_on_either_side(restore) -> None:
    """D-115: المثال المكشوف يخرق القاعدة الذهبية (D-113) — محظورٌ في الطرفين."""
    restore(BACKEND)
    text = BACKEND.read_text(encoding="utf-8")
    BACKEND.write_text(
        text.replace(
            '"probability_tree",', '"probability_tree",\n        "worked_example_card",', 1
        ),
        encoding="utf-8",
    )
    result = _run()
    assert result.returncode == 1
    assert "محظور" in result.stdout


def test_declared_without_emitter_is_red(restore) -> None:
    """إعلانٌ زومبي: يُقرأ قدرةً قائمة وهو ليس كذلك (§6.6 · D-016)."""
    restore(BACKEND)
    restore(FRONTEND)
    BACKEND.write_text(
        BACKEND.read_text(encoding="utf-8").replace(
            '"probability_tree",', '"probability_tree",\n        "unemitted_card",', 1
        ),
        encoding="utf-8",
    )
    FRONTEND.write_text(
        FRONTEND.read_text(encoding="utf-8").replace(
            "    probability_tree: (props) =>",
            "    unemitted_card: (props) => <ProbabilityTree props={props} />,\n"
            "    probability_tree: (props) =>",
            1,
        ),
        encoding="utf-8",
    )
    result = _run()
    assert result.returncode == 1
    assert "إعلانٌ زومبي" in result.stdout


def test_closed_debt_left_in_the_map_is_red(restore) -> None:
    """الدَّين يتقلّص في الاتجاهين: باعثٌ وُصِل ودَينٌ بقي مكتوباً كذبٌ صامت (D-189)."""
    restore(EMITTER)
    text = EMITTER.read_text(encoding="utf-8")
    EMITTER.write_text(
        text.replace(
            '"component": "probability_tree",',
            '"component": "bkt_hint_display",',
            1,
        ),
        encoding="utf-8",
    )
    result = _run()
    assert result.returncode == 1
    assert "_EMITTER_DEBT" in result.stdout


def test_broken_import_in_renderer_is_red(restore) -> None:
    """استيرادٌ مكسور يُسقِط الحزمة كلّها لا مكوّناً واحداً."""
    restore(FRONTEND)
    text = FRONTEND.read_text(encoding="utf-8")
    FRONTEND.write_text(
        text.replace(
            "import { ProbabilityTree } from './ProbabilityTree';",
            "import { ProbabilityTree } from './DeletedComponent';",
            1,
        ),
        encoding="utf-8",
    )
    result = _run()
    assert result.returncode == 1
    assert "غير موجود" in result.stdout
