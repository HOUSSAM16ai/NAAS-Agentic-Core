"""Shard: دوال مساعدة نقية للحزمة الاختبارية (D-258، CodeScene X-Ray).
**لماذا هذه الشريحة موجودة:** كان `_should_skip_db_fixtures` و`_run_async` و
`_count_enforced_warnings` و`_ALLOWED_WARNING_SUBSTRINGS` و`_db_dependencies_available`
متناثرةً في رأس `tests/conftest.py` حول منطق المخطّط والمحرك والسياسات — hotspot
بتردد تغييرٍ عالٍ (churn=2–12 عبر CodeScene) وقوّة ارتباط داخلية مرتفعة.
فُصِلت كل دالةٍ مساعدة نقية إلى هذه الشريحة — **صفر تغيير سلوكي** (القشرة في
`conftest.py` تفوض حرفيًا — قانون late-binding من D-252).
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Coroutine

import pytest

# D-172 follow-up — benign upstream warnings excluded from the strict
# zero-warnings gate. `langgraph-checkpoint` 2.x (pinned for R0.2 — the Postgres
# checkpointer) emits a one-time `allowed_objects` LangChainPendingDeprecationWarning
# at import of `langgraph.checkpoint.base`. It is not a `PendingDeprecationWarning`
# subclass (so the module-level filter and pytest.ini do not catch it) and fires at
# import/collection time before pytest applies its ini filters. Match by message
# substring so it is dropped from the failing count without weakening the policy
# for any other warning. Kept in sync with the repo-root ``conftest.py``.
_ALLOWED_WARNING_SUBSTRINGS: tuple[str, ...] = ("allowed_objects",)


def _db_dependencies_available() -> bool:
    """يتحقق من توفر اعتمادات قاعدة البيانات قبل تهيئة أي موارد اختبارية."""
    return (
        importlib.util.find_spec("sqlalchemy") is not None
        and importlib.util.find_spec("sqlmodel") is not None
    )


def _should_skip_db_fixtures(request: pytest.FixtureRequest) -> bool:
    """يتحقق من تعطيل تجهيز قاعدة البيانات فقط لنطاقات الاختبارات المعزولة."""
    if os.environ.get("SKIP_DB_FIXTURES") != "1":
        return False

    isolated_paths = (
        "tests/unit/overmind/knowledge_graph/",
        "tests/unit/overmind/langgraph/",
        "tests/api_gateway/test_trace_propagation.py",
    )
    request_path = str(request.path).replace("\\", "/")
    return any(path in request_path for path in isolated_paths)


def _run_async[TResult](
    loop,
    coroutine: Coroutine[object, object, TResult],
) -> TResult:
    """تشغيل Coroutine داخل الحلقة المستخدمة في الاختبارات."""
    return loop.run_until_complete(coroutine)


def _count_enforced_warnings(terminal_reporter: object) -> int:
    """عدد التحذيرات المفروضة، باستثناء تحذيرات upstream المعروفة (allowlist)."""

    items = terminal_reporter.stats.get("warnings", ())
    return sum(
        1
        for item in items
        if not any(
            allowed in str(getattr(item, "message", item))
            for allowed in _ALLOWED_WARNING_SUBSTRINGS
        )
    )
