"""`agent_tools.sandbox` — المُنفِّذ الآمن الموحَّد لكل الأدوات (M0).

انظر `executor.py` (البنية) و`policy.py` (قائمة السماح والحدود) للعقد الكامل وسببه.
"""

from app.services.agent_tools.sandbox.executor import (
    SandboxDeniedError,
    project_root,
    resolve_jail,
    run_sandboxed,
    split_command,
)
from app.services.agent_tools.sandbox.policy import (
    ALLOWED_COMMANDS,
    DEFAULT_LIMITS,
    SHELL_METACHARACTERS,
    SandboxLimits,
)

__all__ = [
    "ALLOWED_COMMANDS",
    "DEFAULT_LIMITS",
    "SHELL_METACHARACTERS",
    "SandboxDeniedError",
    "SandboxLimits",
    "project_root",
    "resolve_jail",
    "run_sandboxed",
    "split_command",
]
