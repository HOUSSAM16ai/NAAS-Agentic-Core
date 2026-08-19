"""طبقة الهوية المعرفية المحيطة — D-269 (§0.21).

المرحلة الحالية: **التقاطُ المفتاح ومسبارُ توفّرٍ حيّ فقط**.
⛔ صفر بيانات طالبٍ تغادر المنصّة — مسارُ الكتابة `SEAM` مُعلَنة بصفر كود.

القانون: ``.memory/ambient_identity_constitution.md`` ·
الحالة: ``.memory/ambient_identity_truth.md`` ·
الفارض: ``scripts/fitness/check_ambient_identity.py``.
"""

from __future__ import annotations

from shared.ambient_memory.contract import (
    DEFAULT_PROBE_TIMEOUT_SECONDS,
    AmbientMemoryConfig,
    AmbientMemoryProbeResult,
    ProbeState,
)
from shared.ambient_memory.probe import probe_ambient_memory

__all__ = [
    "DEFAULT_PROBE_TIMEOUT_SECONDS",
    "AmbientMemoryConfig",
    "AmbientMemoryProbeResult",
    "ProbeState",
    "probe_ambient_memory",
]
