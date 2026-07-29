"""
أداة تنفيذ أوامر Git.
======================

توفر إمكانية تنفيذ أوامر Git الشائعة بشكل آمن:
- status, log, diff, branch, commit, push, pull

المعايير:
- CS50 2025: توثيق عربي، صرامة في الأنواع
"""

import asyncio
import logging
from pathlib import Path

from app.services.agent_tools.sandbox import SandboxDeniedError, run_sandboxed, split_command

logger = logging.getLogger(__name__)

# أوامر Git المسموحة
ALLOWED_GIT_COMMANDS = frozenset(
    {
        "status",
        "log",
        "diff",
        "branch",
        "show",
        "blame",
        "fetch",
        "pull",
        "push",
        "commit",
        "add",
        "reset",
        "checkout",
        "merge",
        "rebase",
        "stash",
        "tag",
        "remote",
        "init",
        "clone",
        "config",
    }
)


async def execute_git(
    subcommand: str,
    args: str = "",
    cwd: str | None = None,
    timeout: int = 30,
    args_list: list[str] | None = None,
) -> dict[str, object]:
    """
    تنفيذ أمر Git.

    Args:
        subcommand: الأمر الفرعي (status, log, commit, etc.)
        args: الوسائط الإضافية كنصّ (تُحلَّل بـ`shlex`؛ الميتاحروف مرفوضة)
        cwd: مسار العمل (المستودع)
        timeout: المهلة الزمنية
        args_list: وسائط **جاهزة** تتخطّى التحليل النصّي — للمحتوى الحرّ الذي قد
            يحوي ميتاحروف مشروعة (رسالة commit مثلاً). آمنة لأنها تصل كوسائط
            حرفية في `argv` ولا تُفسَّر أبداً.

    Returns:
        dict: {success, stdout, stderr, return_code, error}
    """
    subcommand = subcommand.strip().lower()

    logger.info(f"Git: Executing 'git {subcommand} {args}'")

    # 1. التحقق من صحة الأمر
    if subcommand not in ALLOWED_GIT_COMMANDS:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "return_code": -1,
            "error": f"Git subcommand '{subcommand}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_GIT_COMMANDS))}",
        }

    # 2. تحديد مسار العمل
    work_dir = Path(cwd) if cwd else Path.cwd()
    if not work_dir.exists():
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "return_code": -1,
            "error": f"Directory does not exist: {work_dir}",
        }

    # 3. التحقق من وجود Git repo
    git_dir = work_dir / ".git"
    if not git_dir.exists() and subcommand not in ("init", "clone"):
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "return_code": -1,
            "error": f"Not a git repository: {work_dir}",
        }

    # 4. بناء الأمر كـ argv (M0)
    #
    # كان يُبنى بـf-string ثم يُنفَّذ بـ`shell=True`، و`args` **لم يكن مُتحقَّقاً منه
    # إطلاقاً** — بينما `subcommand` وحده يمرّ بقائمة السماح. فـ`execute_git("status",
    # "; rm -rf ~")` حقنٌ كامل من الباب الخلفي. الآن تُحلَّل الوسائط إلى قائمة، ولا
    # تُفسَّر الميتاحروف لأن الصدفة غير موجودة أصلاً.
    try:
        if args_list is not None:
            extra = [str(part) for part in args_list]
        else:
            extra = split_command(args) if args.strip() else []
        argv = ["git", subcommand, *extra]
    except SandboxDeniedError as exc:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "return_code": -1,
            "error": f"Git arguments rejected: {exc}",
        }

    # 5. تنفيذ الأمر
    try:
        return await asyncio.wait_for(
            _run_git_command(argv, work_dir, timeout),
            timeout=timeout,
        )

    except TimeoutError:
        logger.warning(f"Git: Command timed out after {timeout}s")
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "return_code": -1,
            "error": f"Git command timed out after {timeout} seconds",
        }

    except Exception as e:
        logger.error(f"Git: Unexpected error: {e}")
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "return_code": -1,
            "error": str(e),
        }


async def _run_git_command(argv: list[str], cwd: Path, timeout: int) -> dict[str, object]:
    """تشغيل أمر Git داخل الصندوق الرملي (M0) — `argv` بلا صدفة."""
    return await asyncio.to_thread(run_sandboxed, argv, cwd=str(cwd), timeout=timeout)


# أدوات مختصرة للأوامر الشائعة
async def git_status(cwd: str | None = None) -> dict[str, object]:
    """الحصول على حالة المستودع."""
    return await execute_git("status", "--short", cwd)


async def git_log(cwd: str | None = None, count: int = 10) -> dict[str, object]:
    """عرض سجل الـ commits."""
    return await execute_git("log", f"--oneline -n {count}", cwd)


async def git_diff(cwd: str | None = None, file: str = "") -> dict[str, object]:
    """عرض التغييرات."""
    return await execute_git("diff", file, cwd)


async def git_branch(cwd: str | None = None) -> dict[str, object]:
    """عرض الفروع."""
    return await execute_git("branch", "-a", cwd)


async def git_add(files: str = ".", cwd: str | None = None) -> dict[str, object]:
    """إضافة ملفات للـ staging."""
    return await execute_git("add", files, cwd)


async def git_commit(message: str, cwd: str | None = None) -> dict[str, object]:
    """إنشاء commit.

    M0: الرسالة تُمرَّر **وسيطاً حرفياً** في `argv` بدل حشوها في سلسلة أوامر. الهروب
    اليدوي السابق (`message.replace('"', '\\"')`) كان يغطّي علامة الاقتباس وحدها
    ويترك `` ` `` و`$(...)` — أي أن رسالة commit كانت متجهاً للحقن.
    """
    return await execute_git("commit", cwd=cwd, args_list=["-m", message])


# تسجيل الأدوات
def register_git_tools(registry: dict) -> None:
    """
    تسجيل أدوات Git في سجل الأدوات.
    """
    registry["git"] = execute_git
    registry["git_status"] = git_status
    registry["git_log"] = git_log
    registry["git_diff"] = git_diff
    registry["git_branch"] = git_branch
    registry["git_add"] = git_add
    registry["git_commit"] = git_commit
    logger.info("Git tools registered successfully")
