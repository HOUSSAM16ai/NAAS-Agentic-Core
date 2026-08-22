"""خطّ الأساس: بطاريةٌ إنجليزية تفحص المخرَج النهائي — **للمقارنة لا للحكم** (L4).

هذا ما تفعله مجموعةُ اختبارٍ أمنيةٌ نمطية: تُشغِّل مُدخَلاتٍ إنجليزية وتحكم على
**النتيجة النهائية**. وهي بذلك تجمع قصورين مستقلّين:

1. **قصورٌ لغويّ** — لا تُشغِّل العربية أصلاً، فالأصناف المشروطة باللغة لا تظهر لها.
2. **قصورٌ في العمق** — تقرأ `final outcome` وحده، فالنمط `lucky` (نتيجةٌ صحيحة بخطوةٍ
   مكسورة) يمرّ عندها بعلامةٍ كاملة.

⛔ **ليس حَكَماً.** يُشغَّل ليُقاس الفارق، ولا يُصدر حكماً على وكيلٍ تحت الاختبار.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from naas_verifier.targets.reference import run_target

__all__ = ["BASELINE_ID", "detection_count", "detects"]

BASELINE_ID = "english_only_final_outcome_v1"


def detects(entry: Mapping[str, Any], variant: str) -> bool:
    """هل يكتشف الأساسُ العطبَ في هذا الصنف؟ (المخرَج النهائي بالإنجليزية وحده)."""
    trajectory = run_target(entry["probe"], variant, language="en")
    expected = bool(entry["probe"]["expect_control_fires"])
    fired = bool(trajectory.metadata.get("control_fired"))
    return fired is not expected


def detection_count(classes: Sequence[Mapping[str, Any]], variant: str) -> int:
    return sum(1 for entry in classes if detects(entry, variant))
