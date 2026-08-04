"""طبقة فجوة الوهم — تحويل المقياس الداخلي إلى مخرَجٍ للوليّ (D-212).

فجوة الوهم هي **مقياس النجاح الوحيد** للمنصّة (CLAUDE.md §0.6): الأداء المدعوم ناقص
القدرة غير المدعومة المؤجَّلة. هذه الوحدة تجعلها شيئاً يُعرَض ويُقاس ويُختبَر، لا رقماً
يُحسَب ثمّ يُرمى.
"""

from __future__ import annotations

from .engine import (
    classify,
    dangerous_concepts,
    durable_after_decay,
    illusion_gap_index,
    quadrant_counts,
)
from .model import (
    MIN_OBS,
    REGISTRY_VERSION,
    ConceptIllusion,
    IllusionError,
    Quadrant,
    quadrant_for,
)

__all__ = [
    "MIN_OBS",
    "REGISTRY_VERSION",
    "ConceptIllusion",
    "IllusionError",
    "Quadrant",
    "classify",
    "dangerous_concepts",
    "durable_after_decay",
    "illusion_gap_index",
    "quadrant_counts",
    "quadrant_for",
]
