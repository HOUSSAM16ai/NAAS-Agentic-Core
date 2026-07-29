from __future__ import annotations

r"""M0 — بطارية الهجوم على مُنفِّذ الأوامر (`roadmap.md §6.5.ب`).

## لماذا هذا الملف موجود

`app/services/agent_tools/shell_tool.py` كان ينفّذ بـ`shell=True` وحارسُه **قائمة منع**
نصّية، بينما `ALLOWED_COMMANDS` (28 أمراً) **مُعرَّفة ولا تُستخدَم إطلاقاً** — قائمة سماح
ميتة. وقد أُثبت ذلك بالتشغيل قبل الإصلاح: الثمانية كلّها **نُفِّذت بنجاح**:

| الهجوم | ما حدث قبل الإصلاح |
|---|---|
| `echo A ; echo PWNED` | نُفِّذ الأمران معاً |
| `echo A \| tr a-z A-Z` | الأنبوب نُفِّذ |
| `echo $(id -u)` | أعاد `0` — أي تنفيذ أوامر عشوائية بصلاحية root |
| `` echo `id -u` `` | أعاد `0` |
| `echo A\necho PWNED2` | سطر جديد ⇒ أمر ثانٍ |
| `awk 'BEGIN{print 42}'` | نُفِّذ رغم أن `awk` **ليس** في قائمة السماح |
| `cat ../../../../etc/hostname` | قرأ خارج جذر المشروع |
| `curl https://example.com` | خرج إلى الشبكة (HTTP 200) |

اليوم يُبنى الأمر داخليّاً فلا مسار حقن من طالب، **لكن `architect.py` يُخبر الـLLM صراحةً
أنه يجوز له استعمال `run_shell` مع curl/wget**. فالمسافة بين «آمن اليوم» و«RCE» هي قرار
توصيل واحد — ولذلك يُغلق الباب **قبل** توصيل أي مُخطِّط (P2: القدرة ≠ الأمان).

كل اختبار هنا كان **أحمر على الكود السابق** (تجربة سلبية إلزامية).
"""

import asyncio
import os
from pathlib import Path

import pytest

from app.services.agent_tools.sandbox import (
    ALLOWED_COMMANDS,
    SandboxDeniedError,
    run_sandboxed,
)
from app.services.agent_tools.shell_tool import execute_shell

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(command: str, cwd: str | None = None, timeout: int = 10) -> dict[str, object]:
    """يُشغّل الأداة العامّة كما يستدعيها المتّصل الحقيقي."""
    return asyncio.run(execute_shell(command=command, cwd=cwd or str(REPO_ROOT), timeout=timeout))


def _assert_refused(result: dict[str, object], *, marker: str | None = None) -> None:
    """الرفض عقدٌ صريح: `success=False` + سبب مكتوب — لا تنفيذ صامت ولا نجاح كاذب."""
    assert result.get("success") is False, f"لم يُرفض: {result}"
    assert str(result.get("error") or "").strip(), "رُفض بلا سبب مكتوب"
    if marker is not None:
        assert marker not in str(result.get("stdout") or ""), f"تسرّب أثر التنفيذ: {marker}"


# ── حقن الميتاحروف ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("label", "command", "marker"),
    [
        ("semicolon", "echo A ; echo PWNED", "PWNED"),
        ("pipe", "echo A | tr a-z A-Z", "A"),
        ("and", "echo A && echo PWNED", "PWNED"),
        ("or", "false || echo PWNED", "PWNED"),
        ("substitution", "echo $(id -u)", "0"),
        ("backticks", "echo `id -u`", "0"),
        ("newline", "echo A\necho PWNED2", "PWNED2"),
        ("redirect", "echo PWNED > /tmp/m0_probe_should_not_exist", "PWNED"),
        ("background", "echo A & echo PWNED", "PWNED"),
    ],
)
def test_metacharacter_injection_is_refused(label: str, command: str, marker: str) -> None:
    """أي ميتاحرف صدفة يُرفض — لا يُهرَّب ولا يُنفَّذ (كان الثمانية تمرّ)."""
    _assert_refused(_run(command), marker=marker)


def test_redirect_attack_left_no_file_behind() -> None:
    """الرفض حقيقي لا تجميلي: لا أثر على القرص."""
    probe = Path("/tmp/m0_probe_should_not_exist")
    probe.unlink(missing_ok=True)
    _run("echo PWNED > /tmp/m0_probe_should_not_exist")
    assert not probe.exists(), "نُفِّذت إعادة التوجيه فعلاً — الرفض كان تجميلياً"


# ── قائمة السماح (كانت ميتة) ────────────────────────────────────────────────────


def test_allowlist_is_enforced_not_merely_declared() -> None:
    """`awk` نُفِّذ سابقاً رغم غيابه عن القائمة — القائمة الميتة صارت الحارس."""
    assert "awk" not in ALLOWED_COMMANDS
    _assert_refused(_run("awk 'BEGIN{print 42}'"), marker="42")


def test_allowed_command_still_runs() -> None:
    """الحارس لا يشلّ الأداة: أمر مسموح ببنية سليمة ينجح."""
    result = _run("echo hello")
    assert result.get("success") is True, result
    assert "hello" in str(result.get("stdout"))


def test_network_commands_are_not_allowed_by_default() -> None:
    """صفر شبكة افتراضاً — `curl` خرج فعلاً إلى الإنترنت قبل الإصلاح."""
    assert "curl" not in ALLOWED_COMMANDS
    assert "wget" not in ALLOWED_COMMANDS
    _assert_refused(_run("curl -s -m 2 https://example.com"))


# ── سجن المسارات ────────────────────────────────────────────────────────────────


def test_working_directory_outside_the_project_is_refused() -> None:
    """`cwd` خارج جذر المشروع مرفوض — لا تنفيذ في `/etc` ولا في `/`."""
    _assert_refused(_run("echo x", cwd="/etc"))


def test_path_traversal_in_arguments_is_refused() -> None:
    """قراءة خارج الجذر عبر `../` — قرأ `/etc/hostname` قبل الإصلاح."""
    _assert_refused(_run("cat ../../../../etc/hostname"))


def test_symlink_escape_is_refused(tmp_path: Path) -> None:
    """رابط رمزي يهرب خارج الجذر لا يلتفّ على السجن (`resolve` لا `abspath`)."""
    escape = tmp_path / "escape"
    try:
        escape.symlink_to("/etc")
    except OSError:  # pragma: no cover - بيئة بلا صلاحية روابط
        pytest.skip("symlinks unavailable in this environment")
    _assert_refused(_run("echo x", cwd=str(escape)))


# ── حدود الموارد ────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not hasattr(os, "fork"), reason="POSIX rlimits only")
def test_fork_bomb_is_contained_structurally() -> None:
    """`RLIMIT_NPROC` يقتل الانفجار بنيويّاً — لا بمطابقة نصّ `:(){` الهشّة."""
    _assert_refused(_run(":(){ :|:& };:", timeout=8))


def test_memory_exhaustion_is_capped() -> None:
    """`RLIMIT_AS` يمنع ابتلاع ذاكرة المضيف."""
    result = run_sandboxed(
        ["python", "-c", "b'x' * (4 * 1024 ** 3)"],
        cwd=str(REPO_ROOT),
        timeout=15,
    )
    assert result["success"] is False, "التهم الذاكرة بلا حدّ"


def test_runaway_time_is_killed() -> None:
    """الزمن محدود — عملية لا تنتهي لا تُعلّق الدور."""
    result = run_sandboxed(["python", "-c", "while True: pass"], cwd=str(REPO_ROOT), timeout=3)
    assert result["success"] is False
    assert "timed out" in str(result.get("error", "")).lower()


def test_output_flood_is_capped_without_reading_it_all() -> None:
    """سقف المخرَج يُطبَّق أثناء القراءة — لا نقرأ جيغابايت ثم نقتطع."""
    result = run_sandboxed(
        ["python", "-c", "print('x' * 50_000_000)"],
        cwd=str(REPO_ROOT),
        timeout=20,
    )
    assert len(str(result.get("stdout", ""))) <= 20_000


# ── العقد الأساسي للمُنفِّذ ──────────────────────────────────────────────────────


def test_executor_takes_argv_not_a_string() -> None:
    """`argv` قائمة لا سلسلة — هذا ما يجعل الحقن مستحيلاً بنيويّاً لا بالفلترة."""
    with pytest.raises((SandboxDeniedError, TypeError)):
        run_sandboxed("echo hello", cwd=str(REPO_ROOT))  # type: ignore[arg-type]


def test_executor_never_uses_a_shell() -> None:
    """لا صدفة إطلاقاً: الميتاحروف تصل كوسائط حرفية لا كصياغة."""
    result = run_sandboxed(["echo", "$(id -u)"], cwd=str(REPO_ROOT), timeout=10)
    assert result["success"] is True
    assert "$(id -u)" in str(result["stdout"]), "الصدفة فسّرت الاستبدال"
