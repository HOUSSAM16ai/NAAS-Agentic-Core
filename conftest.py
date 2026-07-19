"""جسر إعدادات الاختبار وتطبيق سياسات جودة نتائج الاختبارات على مستوى المستودع."""

from collections.abc import Sequence

from _pytest.config import Config
from _pytest.terminal import TerminalReporter

from tests.conftest import *  # noqa: F403

# D-172 follow-up — known-benign upstream warnings excluded from the strict
# zero-warnings gate below. `langgraph-checkpoint` 2.x (pinned for R0.2 — the
# Postgres checkpointer) emits a one-time `allowed_objects`
# LangChainPendingDeprecationWarning at import of `langgraph.checkpoint.base`.
# It is an upstream default-change notice we cannot fix, appears only because
# R0.2 requires `langgraph-checkpoint-postgres`, and — being emitted at
# import/collection time before pytest installs its ini `filterwarnings` — is
# not reliably caught by `pytest.ini` (nor by a conftest pre-import). Match it by
# message substring so it is dropped from the failing count without weakening the
# policy for any other warning. Keep this list tiny and specific.
_ALLOWED_WARNING_SUBSTRINGS: tuple[str, ...] = ("allowed_objects",)


def _count_report_items(reporter: TerminalReporter, key: str) -> int:
    """تُعيد عدد العناصر المسجلة ضمن فئة معيّنة في تقرير pytest النهائي."""

    items: Sequence[object] = reporter.stats.get(key, ())
    return len(items)


def _count_enforced_warnings(reporter: TerminalReporter) -> int:
    """عدد التحذيرات المفروضة، باستثناء تحذيرات upstream المعروفة (allowlist)."""

    items: Sequence[object] = reporter.stats.get("warnings", ())
    enforced = 0
    for item in items:
        message = str(getattr(item, "message", item))
        if any(allowed in message for allowed in _ALLOWED_WARNING_SUBSTRINGS):
            continue
        enforced += 1
    return enforced


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
    warning_count = _count_enforced_warnings(reporter_obj)
    if skipped_count == 0 and warning_count == 0:
        return

    reporter_obj.write_sep(
        "=",
        (f"تم تفعيل سياسة الجودة الصارمة: skipped={skipped_count}, warnings={warning_count}"),
        red=True,
    )
    if hasattr(session, "exitstatus"):
        session.exitstatus = 1
