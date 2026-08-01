"""اختبارات بوّابة رموز التصميم وميزانية الحزمة — D-199.

البوّابة التي تحرس التباين يجب أن تُختبَر على **حساب التباين نفسه**: بوّابةٌ تحسب
النسبة خطأً أسوأ من غيابها، لأنّها تمنح ثقةً زائفة.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_bundle_budget as budget_gate
import check_design_tokens as gate

# ── حساب التباين ───────────────────────────────────────────────────────────────


def test_contrast_of_black_on_white_is_the_known_maximum() -> None:
    """قيمةٌ مرجعية معروفة: ٢١:١ هو أقصى تباينٍ ممكن في WCAG."""
    assert gate.contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)


def test_contrast_of_identical_colours_is_one() -> None:
    assert gate.contrast_ratio("#3c3c3c", "#3c3c3c") == pytest.approx(1.0, abs=1e-9)


def test_contrast_is_symmetric() -> None:
    """النسبة خاصيّة الزوج لا ترتيبه."""
    assert gate.contrast_ratio("#1f5fa8", "#fbfaf7") == pytest.approx(
        gate.contrast_ratio("#fbfaf7", "#1f5fa8")
    )


def test_a_known_mid_grey_matches_the_published_value() -> None:
    """#767676 على الأبيض هو المثال القياسي لأدنى AA — ٤٫٥٤:١."""
    assert gate.contrast_ratio("#767676", "#ffffff") == pytest.approx(4.54, abs=0.02)


# ── العقد على الرموز الحقيقية ───────────────────────────────────────────────────


def test_every_shipped_theme_meets_wcag_aa() -> None:
    """
    العقد الحيّ: لا لون نصّ أو دلالة ينزل تحت AA فوق ورقه، في أيّ سمة.

    التباين ينزلق بتعديلٍ صغير على لون؛ اكتشافُه من مستخدمٍ يقرأ ساعات متأخّرٌ جداً.
    """
    assert gate.check_contrast() == []


def test_the_token_scales_are_present() -> None:
    assert gate.check_tokens_exist() == []


def test_the_gate_passes_on_the_current_tree() -> None:
    assert gate.main() == 0


def test_the_frozen_debt_matches_reality() -> None:
    """
    الدَّين المُجمَّد يجب أن يساوي الواقع بالضبط.

    رقمٌ أعلى من الواقع يسمح بالنموّ خلسةً؛ وأدنى يجعل البوّابة حمراء دائماً فتُتجاهَل.
    """
    assert gate.check_raw_colours() == []
    assert gate.check_inline_px() == []


def test_tokens_file_is_the_only_place_with_theme_colours() -> None:
    """كتل السمات تعيش في `tokens.css` وحدها — وإلّا فلا معنى لـ«مصدر واحد»."""
    blocks = gate._theme_blocks(gate.TOKENS_FILE.read_text(encoding="utf-8"))
    assert len(blocks) >= 2, "expected at least a light and a dark theme block"
    for block in blocks:
        assert "--ink" in block
        assert "--accent" in block


def test_the_render_blocking_font_import_is_gone() -> None:
    """
    `@import` من نطاقٍ ثالث يحجب أوّل رسم — أغلى تأخيرٍ منفرد على 3G.

    عودتُه انحدارٌ صامت لا يظهر في أيّ اختبارٍ وظيفي.
    """
    globals_css = (REPO_ROOT / "frontend" / "app" / "globals.css").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in globals_css
    assert "cdnjs.cloudflare.com" not in globals_css


def test_reduced_motion_is_declared_universally() -> None:
    """
    القائمة الصريحة القديمة غطّت ٩ محدِّدات من نحو ٤٥ حركة.

    من يطلب تقليل الحركة — ومنهم من تُصيبه بدوارٍ حقيقي — كان يتلقّى معظمها كما هي.
    """
    globals_css = (REPO_ROOT / "frontend" / "app" / "globals.css").read_text(encoding="utf-8")
    block_start = globals_css.index("@media (prefers-reduced-motion: reduce)")
    block = globals_css[block_start : block_start + 400]
    assert "*," in block
    assert "*::before" in block
    assert "animation-duration" in block
    assert "transition-duration" in block


# ── ميزانية الحزمة ─────────────────────────────────────────────────────────────


def test_the_budget_is_a_positive_ceiling() -> None:
    assert budget_gate.BUDGET_KB > 0


def test_the_budget_gate_reports_a_missing_build_rather_than_passing(monkeypatch) -> None:
    """
    بناءٌ غائب يجب أن يُفشِل البوّابة لا أن يمرّ بصفر.

    «صفر كيلوبايت» يقرأ كنجاحٍ باهر بينما الحقيقة أنّ شيئاً لم يُبنَ أصلاً (§0).
    """
    monkeypatch.setattr(budget_gate, "CHUNKS_DIR", REPO_ROOT / "frontend" / ".next" / "absent")
    assert budget_gate.main() == 1
