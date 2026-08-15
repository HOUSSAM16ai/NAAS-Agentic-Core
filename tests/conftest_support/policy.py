"""Shard: سياسات جودة نتائج الاختبارات على مستوى الجلسة (D-258، CodeScene X-Ray).
**لماذا هذه الشريحة موجودة:** كان `pytest_sessionfinish` (23 سطرًا) و`pytest_pyfunc_call`
(13 سطرًا) — أعلى churn للجلسة — يتناثران مع منطق DB والعقائد في `conftest.py`.
فُصِلا إلى هذه الشريحة مع مصادرات `pytest_addoption`/`pytest_configure`/
`pytest_collection_modifyitems` لأن جميعها «سياسة جلسة» لا «بنية تحتية DB» —
**صفر تغيير سلوكي** (التوقيعات العامة قشور تفويض حرفية).
"""

from __future__ import annotations

import asyncio

import pytest

from .helpers import _count_enforced_warnings


def pytest_addoption(parser: pytest.Parser) -> None:
    """تسجيل إعدادات ini المطلوبة لمنع تحذيرات PytestConfigWarning."""
    parser.addini("asyncio_mode", "وضع تشغيل asyncio", default="auto")
    parser.addini("env", "بيئة الاختبارات", type="linelist")


def pytest_configure(config: pytest.Config) -> None:
    """تسجيل وسم asyncio لاختبارات غير متزامنة."""
    config.addinivalue_line("markers", "asyncio: تشغيل اختبارات غير متزامنة")


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """يعيد ترتيب الاختبارات لضمان تشغيل اختبارات الخدمات المصغرة في نهاية الجلسة."""

    def _priority(item: pytest.Item) -> tuple[int, str]:
        path_text = str(item.fspath)
        is_microservice_test = "/microservices/" in path_text
        return (1 if is_microservice_test else 0, path_text)

    items.sort(key=_priority)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """يفرض نجاحًا كاملًا عبر فشل الجلسة عند وجود تخطٍ أو تحذيرات اختبارية."""
    terminal_reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if terminal_reporter is None:
        return

    forbidden_outcomes = {
        "skipped": "توجد اختبارات مُتخطاة",
        "xfailed": "توجد اختبارات xfailed",
        "xpassed": "توجد اختبارات xpassed",
    }

    violations = [
        message for key, message in forbidden_outcomes.items() if terminal_reporter.stats.get(key)
    ]

    if _count_enforced_warnings(terminal_reporter):
        violations.append("توجد تحذيرات أثناء التشغيل")

    if violations:
        joined_violations = "، ".join(violations)
        terminal_reporter.write_line(f"[tests-policy] فشل سياسة الجودة: {joined_violations}.")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    """تشغيل الاختبارات غير المتزامنة بدون الاعتماد على pytest-asyncio."""
    if asyncio.iscoroutinefunction(pyfuncitem.obj):
        loop = pyfuncitem.funcargs.get("event_loop")
        if not isinstance(loop, asyncio.AbstractEventLoop):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            pyfuncitem.funcargs["event_loop"] = loop
        arg_names = pyfuncitem._fixtureinfo.argnames
        kwargs = {name: pyfuncitem.funcargs[name] for name in arg_names}
        loop.run_until_complete(pyfuncitem.obj(**kwargs))
        return True
    return None
