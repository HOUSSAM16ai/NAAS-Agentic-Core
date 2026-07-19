"""جسر إعدادات الاختبار وتطبيق سياسات جودة نتائج الاختبارات على مستوى المستودع."""

# D-172 follow-up: langgraph-checkpoint 2.x (pinned for R0.2) emits a one-time
# `allowed_objects` LangChainPendingDeprecationWarning at import of
# langgraph.checkpoint.base. pytest.ini's filterwarnings do NOT catch this
# import/collection-time emission (same reason the repo added a conftest
# pre-import for conversation_service — D-042). This is the earliest user code
# loaded in every pytest session (both `test-monolith` and `test-microservices`
# resolve this repo-root conftest before any test-module collection), so consume
# the once-per-process warning here under suppression. That keeps the strict
# zero-warnings policy (pytest_sessionfinish below) green without touching the
# R0.2 pins. Guarded so jobs that don't install langgraph (e.g. contracts) skip it.
import warnings as _warnings

with _warnings.catch_warnings():
    _warnings.simplefilter("ignore")
    try:
        import langgraph.checkpoint.base
        import langgraph.checkpoint.postgres.aio  # noqa: F401
    except Exception:  # pragma: no cover - optional dep in some CI jobs
        pass

from collections.abc import Sequence

from _pytest.config import Config
from _pytest.terminal import TerminalReporter

from tests.conftest import *  # noqa: F403


def _count_report_items(reporter: TerminalReporter, key: str) -> int:
    """تُعيد عدد العناصر المسجلة ضمن فئة معيّنة في تقرير pytest النهائي."""

    items: Sequence[object] = reporter.stats.get(key, ())
    return len(items)


def pytest_sessionfinish(session: object, exitstatus: int) -> None:
    """يفرض فشل جلسة الاختبار إذا وُجدت اختبارات متخطّاة أو تحذيرات."""

    del exitstatus
    config: Config | None = getattr(session, "config", None)
    if config is None:
        return

    reporter_obj: object | None = config.pluginmanager.getplugin("terminalreporter")
    if not isinstance(reporter_obj, TerminalReporter):
        return

    skipped_count = _count_report_items(reporter_obj, "skipped")
    warning_count = _count_report_items(reporter_obj, "warnings")
    if skipped_count == 0 and warning_count == 0:
        return

    reporter_obj.write_sep(
        "=",
        (f"تم تفعيل سياسة الجودة الصارمة: skipped={skipped_count}, warnings={warning_count}"),
        red=True,
    )
    if hasattr(session, "exitstatus"):
        session.exitstatus = 1
