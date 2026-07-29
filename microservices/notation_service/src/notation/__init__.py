"""نسخة مُوَرَّدة من سجلّ الرموز القانوني — استقلال الخدمة (D-185).

القاعدة 97/98 من دستور الخدمات المصغّرة: **لا مكتبة منطق مشتركة**؛ التكرار مقبول لحفظ
الاستقلال. المصدر القانوني `shared/notation/registry.py`، وهذه نسخة حرفية منه تُثبت
`scripts/fitness/check_notation_parity.py` تطابقها بايتاً ببايت — فلا انجراف صامت.
"""

from __future__ import annotations

from microservices.notation_service.src.notation.registry import (
    NOTATION_REGISTRY,
    REGISTRY_VERSION,
    NotationEntry,
    all_symbols,
    define,
    normalize,
    resolve,
)

__all__ = [
    "NOTATION_REGISTRY",
    "REGISTRY_VERSION",
    "NotationEntry",
    "all_symbols",
    "define",
    "normalize",
    "resolve",
]
