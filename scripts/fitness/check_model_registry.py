#!/usr/bin/env python3
"""بوّابة سجلّ النماذج — D-067 مفروضاً لا موصوفاً (D-202).

لماذا بوّابة
------------
كانت قاعدة «لا نموذج تفكير-فقط في الصدارة» تعليقاً في رأس ملفّ. التعليق لم يمنع
ISS-079: نموذجٌ يُرجِع `content=None` تصدّر السلسلة، فقرأ طالبٌ حقيقي «pepepe aaaa».
البوّابة تجعل الحالة **غير قابلة للوصول** بدل أن تكون مرصودة.

تفحص ثلاثة أشياء:
1. كلّ نموذج في `MODEL_CHAIN` له إدخالٌ بقدراتٍ ودليلٍ مؤرَّخ.
2. لا نموذج **محظورٍ كلّياً** داخل السلسلة.
3. الصدارة مؤهّلة: قدرات `REQUIRED_FOR_PRIMARY` كلّها مُتحقَّقة.

الاستعمال:
    python scripts/fitness/check_model_registry.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from shared.ai_models.model_chain import MODEL_CHAIN, PRIMARY_MODEL
from shared.ai_models.registry import (
    MODEL_REGISTRY,
    ModelRegistryError,
    assert_chain_is_registered,
    assert_primary_is_eligible,
)


def main() -> int:
    problems: list[str] = []

    try:
        assert_chain_is_registered(MODEL_CHAIN)
    except ModelRegistryError as exc:
        problems.append(str(exc))

    try:
        assert_primary_is_eligible(PRIMARY_MODEL)
    except ModelRegistryError as exc:
        problems.append(str(exc))

    # سجلٌّ بلا دليلٍ مؤرَّخ ادّعاءٌ لا معرفة — والادّعاء هو ما نحاربه (§0).
    for model_id, record in MODEL_REGISTRY.items():
        if not record.evidence.strip():
            problems.append(f"{model_id}: registry entry carries no live evidence")

    if problems:
        print("❌ سجلّ النماذج مخروق (D-202):")
        for problem in problems:
            print(f"   • {problem}")
        return 1

    banned = sum(1 for record in MODEL_REGISTRY.values() if record.is_banned)
    print(
        f"✅ model registry: chain {len(MODEL_CHAIN)} نموذجاً مُسجَّلاً · "
        f"PRIMARY={PRIMARY_MODEL} مؤهّل · {banned} محظوراً مُصرَّحاً."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
