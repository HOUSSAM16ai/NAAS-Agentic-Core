"""طبقة تحليلات المنتج — أسماء الأحداث القانونية وحساب الاحتفاظ (D-197)."""

from __future__ import annotations

from .events import (
    CANONICAL_EVENTS,
    AnalyticsError,
    EventName,
    is_canonical,
    validate_event_name,
)
from .retention import (
    DEFAULT_HORIZONS,
    CohortRetention,
    FunnelStep,
    RetentionReport,
    cohort_retention,
    funnel,
    retention_report,
)

__all__ = [
    "CANONICAL_EVENTS",
    "DEFAULT_HORIZONS",
    "AnalyticsError",
    "CohortRetention",
    "EventName",
    "FunnelStep",
    "RetentionReport",
    "cohort_retention",
    "funnel",
    "is_canonical",
    "retention_report",
    "validate_event_name",
]
