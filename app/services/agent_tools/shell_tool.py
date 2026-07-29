"""
أداة تنفيذ أوامر Shell.
========================

تنفّذ برنامجاً واحداً بوسائطه داخل صندوق رملي (`agent_tools.sandbox`):
- `argv` + `shell=False` — **لا صدفة إطلاقاً**
- قائمة سماح مفروضة على البرنامج
- سجن مسارات داخل جذر المشروع
- حدود زمن/ذاكرة/عمليات وسقف مخرَج

## M0 — لماذا أُعيدت كتابة هذا الملف

كان ينفّذ `subprocess.run(command, shell=True)` وحارسُه **قائمة منع** نصّية، بينما
`ALLOWED_COMMANDS` (28 أمراً) **مُعرَّفة ولا تُستخدَم إطلاقاً**. أثبت التشغيل الحيّ قبل
الإصلاح أن الثمانية تمرّ: `;` · `|` · `$( )` · `` ` `` · سطر جديد · `awk` (خارج القائمة) ·
`cat ../../../../etc/hostname` · `curl` إلى الإنترنت. أي أن `echo $(id -u)` أعاد `0`.

قائمة المنع خاطئة **بنيويّاً**: لا يمكن تعدادُ كل صياغة خطرة. الصواب أن يكون الحقن غير
مُمثَّل أصلاً — وهو ما يفعله `argv` + `shell=False`.

المعايير:
- CS50 2025: توثيق عربي، صرامة في الأنواع
- SICP: Abstraction Barriers
"""

import asyncio
import logging

from app.services.agent_tools.sandbox import (
    ALLOWED_COMMANDS,
    SandboxDeniedError,
    run_sandboxed,
    split_command,
)

logger = logging.getLogger(__name__)

#: مُعاد تصديرها للتوافق — والآن **مفروضة فعلاً** في `sandbox.policy`.
__all__ = ["ALLOWED_COMMANDS", "execute_shell", "register_shell_tool"]


async def execute_shell(
    command: str,
    cwd: str | None = None,
    timeout: int = 30,
    check_safety: bool = True,
) -> dict[str, object]:
    """
    تنفيذ أمر داخل الصندوق الرملي.

    Args:
        command: الأمر — برنامج واحد بوسائطه. أي ميتاحرف صدفة يُرفض برسالة.
        cwd: مسار العمل (يجب أن يقع داخل جذر المشروع)
        timeout: المهلة الزمنية بالثواني
        check_safety: محفوظ للتوافق. **لا يُعطّل الصندوق** — الأمان ليس اختيارياً
            (P2: القدرة ≠ الأمان). تمريره `False` يُسجَّل ويُتجاهَل.

    Returns:
        dict: {success, stdout, stderr, return_code, error}
    """
    if not check_safety:
        logger.warning(
            "shell_tool: check_safety=False is ignored — sandboxing is not optional (M0)"
        )

    logger.info(f"Shell: Executing command: {command[:100]}...")
    try:
        argv = split_command(command)
    except SandboxDeniedError as exc:
        logger.warning(f"Shell: Refused unsafe command: {command[:100]} — {exc}")
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "return_code": -1,
            "error": str(exc),
        }

    return await asyncio.to_thread(run_sandboxed, argv, cwd=cwd, timeout=timeout)


def register_shell_tool(registry: dict) -> None:
    """
    تسجيل أداة shell في سجل الأدوات.

    Args:
        registry: سجل الأدوات
    """
    registry["shell"] = execute_shell
    registry["execute_shell"] = execute_shell
    registry["run_command"] = execute_shell
    registry["run_shell"] = execute_shell
    logger.info("Shell tool registered successfully")
