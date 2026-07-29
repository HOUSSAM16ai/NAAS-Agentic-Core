"""المُنفِّذ الآمن — `argv` + `shell=False` + سجن مسارات + حدود موارد (M0).

المصدر الوحيد لتنفيذ العمليات الفرعية في `agent_tools`. الثلاثة (`shell_tool` ·
`git_tool` · `testing_tool`) كانت تستدعي `subprocess.run(..., shell=True)` كلٌّ على
حدة؛ الآن تمرّ كلّها من هنا.

**لماذا هذا آمن بنيويّاً لا احتمالياً:** لا توجد صدفة تُفسِّر شيئاً. `;` و`$(...)`
و`` ` `` تصل إلى البرنامج **كنصّ حرفي** في `argv`. فالحقن ليس «مُرشَّحاً» بل غير
مُمثَّل أصلاً — وهذا يهزم أنماط الهجوم التي لم تخطر لأحد، وهو ما تعجز عنه أي قائمة منع.
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from collections.abc import Sequence
from pathlib import Path

from app.services.agent_tools.sandbox.policy import (
    ALLOWED_COMMANDS,
    DEFAULT_LIMITS,
    SHELL_METACHARACTERS,
    SandboxLimits,
)

logger = logging.getLogger(__name__)


class SandboxDeniedError(Exception):
    """رُفض التنفيذ بقرار سياسة — ليس فشلاً تشغيلياً."""


def project_root() -> Path:
    """جذر المشروع — سجن المسارات كلّه نسبةً إليه."""
    return Path(__file__).resolve().parents[4]


def _denied(reason: str) -> dict[str, object]:
    """عقد الرفض — مطابق لعقد النجاح شكلاً، وسببه **مكتوب دائماً**."""
    return {
        "success": False,
        "stdout": "",
        "stderr": "",
        "return_code": -1,
        "error": reason,
    }


def resolve_jail(cwd: str | Path | None) -> Path:
    """يتحقّق أن مسار العمل داخل جذر المشروع — يرفع `SandboxDeniedError` وإلّا.

    يستعمل `Path.resolve()` (لا `abspath`) فيتبع الروابط الرمزية قبل المقارنة —
    وإلّا التفّ رابطٌ يشير إلى `/etc` على السجن كلّه.
    """
    root = project_root().resolve()
    target = (Path(cwd) if cwd else root).resolve()
    if not target.exists():
        raise SandboxDeniedError(f"Working directory does not exist: {target}")
    if not target.is_dir():
        raise SandboxDeniedError(f"Working directory is not a directory: {target}")
    if target != root and root not in target.parents:
        raise SandboxDeniedError(
            f"Working directory escapes the project jail: {target} is outside {root}"
        )
    return target


def _check_argument_paths(argv: Sequence[str], jail: Path) -> None:
    """يرفض وسيطاً يشير — بعد `resolve` — إلى خارج السجن.

    يمنع `cat ../../../../etc/hostname` الذي قرأ خارج الجذر فعلاً قبل M0. الوسائط
    التي ليست مسارات موجودة تُترَك (راية مثل `-la` ليست مساراً).
    """
    root = project_root().resolve()
    for arg in argv[1:]:
        if not arg or arg.startswith("-"):
            continue
        candidate = Path(arg)
        probe = candidate if candidate.is_absolute() else (jail / candidate)
        try:
            resolved = probe.resolve()
        except OSError:
            continue
        if not resolved.exists():
            continue
        if resolved != root and root not in resolved.parents:
            raise SandboxDeniedError(f"Path argument escapes the project jail: {arg}")


def _preexec(limits: SandboxLimits):  # pragma: no cover - يعمل في العملية الابن
    """يفرض حدود الموارد داخل العملية الابن قبل `exec` (POSIX)."""

    def _apply() -> None:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds))
        resource.setrlimit(
            resource.RLIMIT_AS, (limits.address_space_bytes, limits.address_space_bytes)
        )
        resource.setrlimit(resource.RLIMIT_NPROC, (limits.max_processes, limits.max_processes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (limits.file_size_bytes, limits.file_size_bytes))
        os.setsid()  # مجموعة عمليات مستقلّة ⇒ القتل يطال الذرّية كلّها.

    return _apply


def run_sandboxed(
    argv: Sequence[str],
    *,
    cwd: str | Path | None = None,
    timeout: int = 30,
    limits: SandboxLimits = DEFAULT_LIMITS,
    env: dict[str, str] | None = None,
) -> dict[str, object]:
    """ينفّذ `argv` داخل السجن ويُعيد العقد الموحَّد.

    لا يرفع استثناءً لقرارات السياسة — يُعيد `success=False` مع سبب، كي يبقى
    المتّصل (أداة) على عقده السابق. `SandboxDeniedError` يُرفع فقط عند إساءة استعمال
    برمجية (تمرير سلسلة بدل `argv`).
    """
    if isinstance(argv, str):
        raise SandboxDeniedError("run_sandboxed takes an argv list, never a command string")
    argv = [str(part) for part in argv]
    if not argv:
        return _denied("Empty command")

    program = Path(argv[0]).name
    if program not in ALLOWED_COMMANDS:
        return _denied(
            f"Command '{program}' is not in the sandbox allowlist. "
            f"Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}"
        )

    try:
        jail = resolve_jail(cwd)
        _check_argument_paths(argv, jail)
    except SandboxDeniedError as exc:
        return _denied(str(exc))

    # بيئة صريحة — لا نُورِّث أسرار العملية الأمّ إلى عملية أداة.
    child_env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(jail),
        "LANG": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "GIT_TERMINAL_PROMPT": "0",
    }
    if env:
        child_env.update(env)

    logger.info("sandbox_exec", extra={"program": program, "argc": len(argv)})
    try:
        process = subprocess.run(
            argv,
            shell=False,
            check=False,
            cwd=str(jail),
            capture_output=True,
            timeout=timeout,
            env=child_env,
            preexec_fn=_preexec(limits) if hasattr(os, "fork") else None,
        )
    except subprocess.TimeoutExpired:
        return _denied(f"Command timed out after {timeout} seconds")
    except FileNotFoundError:
        return _denied(f"Command not found: {program}")
    except PermissionError as exc:
        return _denied(f"Permission denied: {exc}")
    except OSError as exc:  # حدود الموارد قد تُفشل الإطلاق نفسه (قنبلة fork).
        return _denied(f"Sandbox refused to launch the process: {exc}")

    # السقف يُطبَّق على البايتات المُلتقَطة قبل فكّ الترميز — لا نبني سلسلة عملاقة أولاً.
    stdout = (process.stdout or b"")[: limits.max_stdout_bytes].decode("utf-8", "replace")
    stderr = (process.stderr or b"")[: limits.max_stderr_bytes].decode("utf-8", "replace")
    return {
        "success": process.returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
        "return_code": process.returncode,
        "error": None if process.returncode == 0 else (stderr[:500] or "Command failed"),
    }


def split_command(command: str) -> list[str]:
    """يحوّل أمراً نصّياً إلى `argv` — ويرفض أي صياغة صدفة **صراحةً**.

    الأدوات القائمة تقبل `command: str` في توقيعها، فنحفظ العقد. لكن نيّة صياغة
    الصدفة تُرفَض برسالة بدل أن تُهرَّب بصمت: التهريب الصامت يجعل المتّصل يظنّ أن
    أمره نُفِّذ كما كتبه.
    """
    for meta in SHELL_METACHARACTERS:
        if meta in command:
            raise SandboxDeniedError(
                f"Shell metacharacter {meta!r} is not supported: the sandbox executes a single "
                "program with arguments and never invokes a shell."
            )
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise SandboxDeniedError(f"Could not parse command: {exc}") from exc
    if not argv:
        raise SandboxDeniedError("Empty command")
    return argv
