"""
أداة تشغيل الاختبارات.
======================

توفر إمكانية تشغيل pytest بشكل آمن.

المعايير:
- CS50 2025: توثيق عربي، صرامة في الأنواع
"""

import asyncio
import logging
import re
from dataclasses import replace
from pathlib import Path

from app.services.agent_tools.sandbox import DEFAULT_LIMITS, SandboxDeniedError, run_sandboxed
from app.services.agent_tools.sandbox import split_command as _split

logger = logging.getLogger(__name__)


def split_command(text: str) -> list[str]:
    """يحلّل وسائط pytest — إعادة تصدير موضعية تُبقي الاستدعاءات مقروءة."""
    return _split(text)


async def run_tests(
    path: str = "",
    options: str = "",
    cwd: str | None = None,
    timeout: int = 120,
) -> dict[str, object]:
    """
    تشغيل اختبارات pytest.

    Args:
        path: مسار الاختبارات (ملف أو مجلد)
        options: خيارات إضافية (مثلاً -v, -x, -k)
        cwd: مسار العمل
        timeout: المهلة الزمنية (دقيقتان بالافتراض)

    Returns:
        dict: {success, stdout, stderr, return_code, passed, failed, error}
    """
    logger.info(f"Tests: Running pytest {path} {options}")

    # تحديد مسار العمل
    work_dir = Path(cwd) if cwd else Path.cwd()
    if not work_dir.exists():
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "return_code": -1,
            "passed": 0,
            "failed": 0,
            "error": f"Directory does not exist: {work_dir}",
        }

    # بناء الأمر كـ argv (M0) — كان يُبنى بـf-string ثم يُنفَّذ بـ`shell=True`،
    # فـ`path`/`options` كانا متجهَي حقن مباشرَين.
    try:
        argv = ["python", "-m", "pytest"]
        if path:
            argv += split_command(path)
        if options:
            argv += split_command(options)
        if "-v" not in options:
            argv.append("-v")
        argv.append("--tb=short")
    except SandboxDeniedError as exc:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "return_code": -1,
            "passed": 0,
            "failed": 0,
            "error": f"pytest arguments rejected: {exc}",
        }

    try:
        return await asyncio.wait_for(
            _run_pytest(argv, work_dir, timeout),
            timeout=timeout,
        )

    except TimeoutError:
        logger.warning(f"Tests: Timed out after {timeout}s")
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "return_code": -1,
            "passed": 0,
            "failed": 0,
            "error": f"Tests timed out after {timeout} seconds",
        }

    except Exception as e:
        logger.error(f"Tests: Unexpected error: {e}")
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "return_code": -1,
            "passed": 0,
            "failed": 0,
            "error": str(e),
        }


async def _run_pytest(argv: list[str], cwd: Path, timeout: int) -> dict[str, object]:
    """تشغيل pytest داخل الصندوق الرملي (M0) — `argv` بلا صدفة.

    مهلة الاختبارات أطول من الافتراضية، وحدّ المعالج يُرفَع بما يناسبها: سلسلة
    اختبارات مشروعة تستهلك دقائق معالج، فحدّ عشر ثوانٍ كان سيقتلها ظلماً.
    """
    limits = replace(
        DEFAULT_LIMITS,
        cpu_seconds=max(DEFAULT_LIMITS.cpu_seconds, timeout),
        max_stdout_bytes=20_000,
    )
    result = await asyncio.to_thread(
        run_sandboxed, argv, cwd=str(cwd), timeout=timeout, limits=limits
    )

    stdout = str(result.get("stdout", ""))
    passed = failed = 0
    match = re.search(r"(\d+) passed", stdout)
    if match:
        passed = int(match.group(1))
    match = re.search(r"(\d+) failed", stdout)
    if match:
        failed = int(match.group(1))

    return {
        **result,
        "passed": passed,
        "failed": failed,
        "error": result.get("error") if not result.get("success") else None,
    }


async def run_specific_test(test_name: str, cwd: str | None = None) -> dict[str, object]:
    """تشغيل اختبار محدد بالاسم."""
    return await run_tests(options=f"-k '{test_name}'", cwd=cwd)


async def run_tests_verbose(path: str = "", cwd: str | None = None) -> dict[str, object]:
    """تشغيل الاختبارات مع مخرجات مفصلة."""
    return await run_tests(path=path, options="-vv --tb=long", cwd=cwd)


# تسجيل الأدوات
def register_test_tools(registry: dict) -> None:
    """
    تسجيل أدوات الاختبار في سجل الأدوات.
    """
    registry["run_tests"] = run_tests
    registry["pytest"] = run_tests
    registry["test"] = run_tests
    registry["run_specific_test"] = run_specific_test
    registry["run_tests_verbose"] = run_tests_verbose
    logger.info("Test tools registered successfully")
