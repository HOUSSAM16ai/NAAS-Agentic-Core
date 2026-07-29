"""عميل HTTP صادر مُصحَّح بالتتبّع — المصدر القانوني الوحيد (D-189 · دَين D4).

يُعاد تصدير السطح العام فقط؛ التفصيل في :mod:`shared.http_client.correlated`.
"""

from __future__ import annotations

from shared.http_client.correlated import (
    CORRELATION_HEADER,
    TRACEPARENT_HEADER,
    correlated_client,
    correlation_headers,
    current_correlation_id,
    set_correlation_provider,
)

__all__ = [
    "CORRELATION_HEADER",
    "TRACEPARENT_HEADER",
    "correlated_client",
    "correlation_headers",
    "current_correlation_id",
    "set_correlation_provider",
]
