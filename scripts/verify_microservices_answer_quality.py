"""تحقق حي سريع لجودة إجابات الخدمات المصغرة في مسارات الدردشة الأساسية.

يشغّل فحصين عمليين:
1) smoke journeys على `/api/chat/message`.
2) سيناريو واجهة الاحتمالات التلقائي (auto UI trigger).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], timeout_s: int = 120) -> int:
    print(f"\n$ {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        print(f"❌ timeout after {timeout_s}s")
        return 124
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)
    return proc.returncode


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    print("=== Microservices Answer Quality Live Verification ===")
    print(f"repo={repo_root}")
    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
    has_postgres = bool(os.getenv("DATABASE_URL", "").startswith("postgres"))
    print(
        "secrets_status:",
        f"OPENROUTER_API_KEY={'set' if has_openrouter else 'missing'}",
        f"DATABASE_URL(postgres)={'yes' if has_postgres else 'no'}",
    )

    checks: list[tuple[list[str], int]] = [
        ([sys.executable, "-m", "pytest", "-q", "tests/governance/test_smoke_journeys.py"], 300),
        ([sys.executable, "scripts/test_auto_ui_trigger.py"], 180),
    ]

    failed = 0
    for cmd, timeout_s in checks:
        rc = _run(cmd, timeout_s=timeout_s)
        if rc != 0:
            failed += 1

    if failed:
        print(f"\n❌ verification failed: {failed} check(s) failed")
        return 1
    print("\n✅ verification passed: all checks succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
