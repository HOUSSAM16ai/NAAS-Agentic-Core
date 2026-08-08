"""ميزانيات التجربة — أرقامٌ مُصرَّحة لا مُذابة في الكود (D-230).

`shared/` لا يستورد `app` ولا خدمةً شقيقة (D-189). هذه الوحدة stdlib خالصة.
"""

from __future__ import annotations

from shared.ux.budgets import (
    ATTENTION_LIMIT_S,
    FIRST_OBJECT_PAINT_MS,
    FLOW_LIMIT_S,
    INSTANT_LIMIT_MS,
    LatencyVerdict,
    classify_latency,
)

__all__ = [
    "ATTENTION_LIMIT_S",
    "FIRST_OBJECT_PAINT_MS",
    "FLOW_LIMIT_S",
    "INSTANT_LIMIT_MS",
    "LatencyVerdict",
    "classify_latency",
]
