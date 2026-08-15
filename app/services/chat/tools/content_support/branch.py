"""شريحة توحيد اسم الشعبة (D-255 — شريحة مستقلة منفصلة عن search.py).

منطق التوحيد في شريحةٍ نقية واحدة بلا حالة: خريطة `BRANCH_MAP` من الثوابت
الموحدة (`app.domain.constants`) + ترجمة canonical ⇒ تسمية عربية معروضة
(`_BRANCH_LABELS`) + سلسلة قرار واحدة (تطابق حرفي ⇒ أقرب مطابقة ⇒ احتواء
⇒ الأصل).

**صفر تغيير سلوكي**: النصوص والعتبات (`_CLOSE_MATCH_CUTOFF = 0.6` ·
`_MIN_VARIANT_LENGTH = 3`) مطابقة حرفًا للسلالة الأصلية في
`search_shard.normalize_branch`.
"""

from __future__ import annotations

import difflib

from app.domain.constants import BRANCH_MAP

# ترجمة المفاتيح canonical إلى تسميات عربية معروضة (سلالة D-255 حرفًا).
_BRANCH_LABELS: dict[str, str] = {
    "experimental_sciences": "علوم تجريبية",
    "math_tech": "تقني رياضي",
    "mathematics": "رياضيات",
    "foreign_languages": "لغات أجنبية",
    "literature_philosophy": "آداب وفلسفة",
}

# عتبة القرب الأدنى لقبول أقرب مطابقة (نفس عتبة الدستور الأصلية).
_CLOSE_MATCH_CUTOFF: float = 0.6

# الحد الأدنى لطول البديل ليعتبر احتواءه في المدخل مطابقة (نفس القاعدة الأصلية).
_MIN_VARIANT_LENGTH: int = 3


def _build_reverse_index() -> tuple[dict[str, str], list[str]]:
    """الفهرس العكسي (بديل -> مفتاح canonical) وقائمة البدائل بالترتيب الأصلي."""
    reverse_map: dict[str, str] = {}
    all_variants: list[str] = []
    for key, variants in BRANCH_MAP.items():
        for variant in variants:
            reverse_map[variant] = key
            all_variants.append(variant)
    return reverse_map, all_variants


def _fallback_resolve(normalized: str) -> str | None:
    """أقرب مطابقة (cutoff 0.6) أو احتواء بديل بطول > 3 — مسار خروج واحد."""
    reverse_map, all_variants = _build_reverse_index()
    close_matches = difflib.get_close_matches(
        normalized, all_variants, n=1, cutoff=_CLOSE_MATCH_CUTOFF
    )
    if close_matches:
        canonical = reverse_map[close_matches[0]]
        return _BRANCH_LABELS.get(canonical, canonical)
    for variant in all_variants:
        if len(variant) > _MIN_VARIANT_LENGTH and variant in normalized:
            canonical = reverse_map[variant]
            return _BRANCH_LABELS.get(canonical, canonical)
    return None


def normalize_branch(value: str | None) -> str | None:
    """توحيد اسم الشعبة: تطابق حرفي ⇒ أقرب مطابقة ⇒ احتواء ⇒ الأصل.

    شريحة مستقلة في `branch.py` (D-255): كانت مكرَّرة داخل `search.py`
    فيجعل وجودها في شريحتين ازدواجية (Code Duplication — CodeScene).
    """
    if not value:
        return None
    normalized = value.strip().lower()
    for key, variants in BRANCH_MAP.items():
        if normalized in variants:
            return _BRANCH_LABELS.get(key, key)
    return _fallback_resolve(normalized) or value
