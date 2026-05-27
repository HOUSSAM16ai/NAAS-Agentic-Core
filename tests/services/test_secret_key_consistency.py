"""
Regression test — verify SECRET_KEY consistency between monolith and user-service.

USER REPORT (verbatim):
> «اطرح سؤال لا يجيب يدخل و يخرج بسرعة و أجد نفسي في محادثة جديدة
>  مع العلم متصل تظهر»

ROOT CAUSE (D-WS-SECRET-KEY-001):
The supervisor.sh launched user-service with a DIFFERENT default SECRET_KEY
than the monolith:

  - Monolith default:   `dev-secret-change-me` (in supervisor.sh + .env)
  - Orchestrator:       `dev-secret-change-me` (matches monolith)
  - **User-service**:   `cogniforge-user-service-dev-key`  ← DIFFERENT!

When Codespaces SECRET_KEY secret was not configured (the user's case), each
service used its own default. The catastrophic flow:

  1. User → POST /api/security/login
     → monolith calls user_service_client.login_user
     → user-service signs JWT with `cogniforge-user-service-dev-key`
     → token returned to frontend
  2. User → opens chat WS
     → handshake includes the token
     → monolith decode_user_id uses `dev-secret-change-me`
     → signature mismatch → 4401 close
  3. User → frontend reconnects → 4401 again → eventually escalates
     → logout → new login → cycle continues

Verification: HTTP /me succeeded (because get_current_user tries user-service
first, which verified its own token). WS failed (only monolith decode).

THE FIX:
1. supervisor.sh user-service launch: use shared_user_secret (= monolith default)
2. Also export USER_SECRET_KEY as defensive backup
3. user-service crypto.py: env-aware ACCESS_EXPIRE_MINUTES (mirror of monolith)

This test verifies:
- supervisor.sh user-service block uses shared_user_secret pattern.
- shared_user_secret default matches monolith's shared_secret default.
- Both SECRET_KEY and USER_SECRET_KEY are exported (defensive double-coverage).
- user-service crypto.py uses env-aware ACCESS_EXPIRE_MINUTES.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")


class TestSecretKeyConsistency:
    def test_user_service_shares_monolith_secret_default(self) -> None:
        """user-service launch in supervisor.sh must use dev-secret-change-me default."""
        source = _read(".devcontainer/supervisor.sh")
        # Find the user-service launch block
        user_block_match = re.search(
            r"UserService: starting on.*?>> .*?user_service\.log",
            source,
            re.DOTALL,
        )
        assert user_block_match is not None, "user-service launch block not found"
        block = user_block_match.group(0)

        # Must use shared_user_secret (variable computed earlier in same function)
        assert "shared_user_secret" in block, (
            "D-WS-SECRET-KEY-001: user-service block MUST define a "
            "shared_user_secret variable that defaults to dev-secret-change-me "
            "(same as monolith) — NOT cogniforge-user-service-dev-key."
        )
        # Default must match monolith's `dev-secret-change-me`
        assert "dev-secret-change-me" in block, (
            "shared_user_secret default must be `dev-secret-change-me` to "
            "match monolith's SECRET_KEY default."
        )

    def test_no_distinct_user_service_secret_default(self) -> None:
        """The old `cogniforge-user-service-dev-key` default must be gone from CODE.

        (The string may appear in documentation comments — that's fine; what
        matters is that no actual variable assignment uses it as a fallback.)
        """
        source = _read(".devcontainer/supervisor.sh")
        user_block_match = re.search(
            r"UserService: starting on.*?>> .*?user_service\.log",
            source,
            re.DOTALL,
        )
        assert user_block_match is not None
        block = user_block_match.group(0)
        # Strip shell comments (lines starting with `#`) before checking
        non_comment_lines = []
        for raw_line in block.splitlines():
            stripped = raw_line.lstrip()
            if stripped.startswith("#"):
                continue
            # Drop inline trailing comments after a `#` (best-effort)
            code_part = raw_line.split("#", 1)[0] if "#" in raw_line else raw_line
            non_comment_lines.append(code_part)
        code_only = "\n".join(non_comment_lines)
        assert "cogniforge-user-service-dev-key" not in code_only, (
            "REGRESSION: the user-service block must NOT default to "
            "`cogniforge-user-service-dev-key` in actual bash code. That "
            "string caused the SECRET_KEY mismatch with monolith → all WS "
            "handshakes returned 4401. (Note: a documentation comment "
            "explaining the history is fine.)"
        )

    def test_user_service_exports_both_secret_keys(self) -> None:
        """Defensive: both SECRET_KEY and USER_SECRET_KEY are exported to user-service."""
        source = _read(".devcontainer/supervisor.sh")
        user_block_match = re.search(
            r"UserService: starting on.*?>> .*?user_service\.log",
            source,
            re.DOTALL,
        )
        assert user_block_match is not None
        block = user_block_match.group(0)
        assert "SECRET_KEY=" in block, "user-service block must export SECRET_KEY"
        assert "USER_SECRET_KEY=" in block, (
            "user-service block must ALSO export USER_SECRET_KEY (defensive — "
            "guards against pydantic-settings env_prefix vs validation_alias quirks)."
        )

    def test_orchestrator_shares_same_secret_default(self) -> None:
        """Sanity check — orchestrator's shared_secret default matches."""
        source = _read(".devcontainer/supervisor.sh")
        # Find the orchestrator launch block
        match = re.search(
            r'shared_secret\s*=\s*"\$\{SECRET_KEY:-dev-secret-change-me\}"',
            source,
        )
        assert match is not None, (
            "Orchestrator's shared_secret default must remain `dev-secret-change-me`."
        )

    def test_planning_agent_shares_canonical_secret(self) -> None:
        """planning-agent verifies X-Service-Token signed by orchestrator — must share default."""
        source = _read(".devcontainer/supervisor.sh")
        assert re.search(
            r'shared_planning_secret\s*=\s*"\$\{SECRET_KEY:-dev-secret-change-me\}"',
            source,
        ), (
            "D-WS-SECRET-KEY-001: planning-agent MUST use shared_planning_secret "
            "defaulting to `dev-secret-change-me`. Old default "
            "`super_secret_key_change_in_production` breaks Skills Pipeline JWT verification."
        )
        # Defensive double-export
        assert "PLANNING_SECRET_KEY=" in source, (
            "planning-agent launch block must export PLANNING_SECRET_KEY too "
            "(defensive double-coverage for pydantic-settings env_prefix quirks)."
        )

    def test_research_agent_shares_canonical_secret(self) -> None:
        """research-agent verifies X-Service-Token signed by orchestrator — must share default."""
        source = _read(".devcontainer/supervisor.sh")
        assert re.search(
            r'shared_research_secret\s*=\s*"\$\{SECRET_KEY:-dev-secret-change-me\}"',
            source,
        ), (
            "D-WS-SECRET-KEY-001: research-agent MUST use shared_research_secret "
            "defaulting to `dev-secret-change-me`. Old default "
            "`super_secret_key_change_in_production` breaks Skills Pipeline JWT verification."
        )
        assert "RESEARCH_SECRET_KEY=" in source, (
            "research-agent launch block must export RESEARCH_SECRET_KEY too."
        )

    def test_reasoning_agent_shares_canonical_secret(self) -> None:
        """reasoning-agent verifies X-Service-Token signed by orchestrator — must share default."""
        source = _read(".devcontainer/supervisor.sh")
        assert re.search(
            r'shared_reasoning_secret\s*=\s*"\$\{SECRET_KEY:-dev-secret-change-me\}"',
            source,
        ), (
            "D-WS-SECRET-KEY-001: reasoning-agent MUST use shared_reasoning_secret "
            "defaulting to `dev-secret-change-me`. Old default "
            "`super_secret_key_change_in_production` breaks Skills Pipeline JWT verification."
        )
        assert "REASONING_SECRET_KEY=" in source, (
            "reasoning-agent launch block must export REASONING_SECRET_KEY too."
        )

    def test_no_distinct_skills_pipeline_secret_defaults(self) -> None:
        """The catastrophic `super_secret_key_change_in_production` must be gone from CODE.

        It may appear in documentation comments — what matters is that no
        actual bash variable assignment uses it as a fallback.
        """
        source = _read(".devcontainer/supervisor.sh")
        # Strip shell comments (lines starting with `#`) before checking
        code_only_lines = []
        for raw_line in source.splitlines():
            stripped = raw_line.lstrip()
            if stripped.startswith("#"):
                continue
            code_only_lines.append(raw_line)
        code_only = "\n".join(code_only_lines)
        assert "super_secret_key_change_in_production" not in code_only, (
            "REGRESSION: planning/research/reasoning agents must NOT default to "
            "`super_secret_key_change_in_production` in actual bash code. That "
            "string caused SECRET_KEY mismatch with orchestrator → all "
            "X-Service-Token JWT verifications failed → Skills Pipeline DEGRADED → "
            "chat fell back to local_graph. (Doc comments explaining the history are fine.)"
        )


class TestUserServiceCryptoEnvAware:
    def test_access_expire_is_env_aware(self) -> None:
        """user-service crypto.py must use env-aware ACCESS_EXPIRE_MINUTES."""
        source = _read("microservices/user_service/src/services/auth/crypto.py")
        # Must contain the env-aware computation logic
        assert "_IS_DEV_LIKE" in source, (
            "user-service crypto.py must compute env-aware cap (mirror of monolith)."
        )
        assert "ALLOW_LONG_LIVED_TOKENS" in source, (
            "user-service crypto.py must support ALLOW_LONG_LIVED_TOKENS escape hatch."
        )

    def test_dev_access_cap_is_8_hours(self) -> None:
        source = _read("microservices/user_service/src/services/auth/crypto.py")
        # 480 minutes = 8 hours
        assert "480" in source, "user-service must use 480-minute cap in development."

    def test_prod_access_cap_stays_30_minutes(self) -> None:
        source = _read("microservices/user_service/src/services/auth/crypto.py")
        # 30 must remain as production cap
        assert re.search(r"ACCESS_EXPIRE_MINUTES.*else\s+30", source), (
            "user-service must keep 30-minute cap in production."
        )
