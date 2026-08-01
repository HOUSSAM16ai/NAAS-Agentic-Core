"""اختبارات المُطبِّع النصّي المشترك — D-193.

المُطبِّع هو ما تعتمد عليه كلّ مطابقة علامات في `shared/`. عطبٌ فيه لا يُسقط شيئاً بل
يجعل السجلّات **تصمت** — وهذا بالضبط ما حدث في ISS-133 حين مسح مُطبِّعُ الكاش كلَّ حرف
عربي فتحوّل `recall`/`memorize` إلى لا-عملية صامتة لكلّ مستخدمي المنصّة.
"""

from __future__ import annotations

import pytest

from shared.textnorm import normalize, strip_marks


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # تشكيل عربي
        ("مُشَتَقّ", "مشتق"),
        # همزات — تتفكّك تحت NFKD فتُطوى بلا جدول يدوي
        ("أصلية", "اصليه"),
        ("إحصاء", "احصا"),
        ("آمن", "امن"),
        ("مؤشر", "موشر"),
        ("مسائل", "مسايل"),
        # تاء مربوطة وألف مقصورة وتطويل
        ("حادثة", "حادثه"),
        ("مستوى", "مستوي"),
        ("كــتــاب", "كتاب"),
        # لكنات فرنسية — نفس الخطوة تطويها
        ("dérivée", "derivee"),
        ("intégrale", "integrale"),
        ("Équation", "equation"),
        # أرقام عربية-هندية وفارسية
        ("١٢٣", "123"),
        ("۴۵۶", "456"),
        # المسافات
        ("  a   b  ", "a b"),
        ("a\t\nb", "a b"),
    ],
)
def test_normalize_folds_as_specified(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_normalize_is_idempotent() -> None:
    """شرطٌ لازم: العلامات تُكتَب مُطبَّعة، فلا بدّ أن تُطبِّع نفسها إلى نفسها."""
    for raw in ("مُشَتَقّ", "dérivée", "الأعداد المركبة", "١٢٣", "e^", "z ="):
        once = normalize(raw)
        assert normalize(once) == once


def test_normalize_preserves_latin_and_mathematical_symbols() -> None:
    """
    حذف اللاتينية أو الرموز يُعمي المطابقة: كثير من العلامات القانونية `ln` أو `e^`.
    """
    assert normalize("e^") == "e^"
    assert normalize("z =") == "z ="
    assert normalize("ln(x)") == "ln(x)"
    assert normalize("C(n,k)") == "c(n,k)"


def test_normalize_lowercases() -> None:
    assert normalize("LIMITE") == "limite"


@pytest.mark.parametrize("empty", ["", None])
def test_normalize_handles_empty_input(empty: str | None) -> None:
    assert normalize(empty) == ""  # type: ignore[arg-type]


def test_strip_marks_removes_combining_marks_only() -> None:
    assert strip_marks("مُشَتَقّ") == "مشتق"
    assert strip_marks("dérivée") == "derivee"
    # لا يمسّ ما ليس علامةً مُركِّبة
    assert strip_marks("ة") == "ة"
