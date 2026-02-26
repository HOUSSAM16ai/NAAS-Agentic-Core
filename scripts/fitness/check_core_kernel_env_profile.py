"""يتحقق أن CORE_KERNEL_URL غير موجود في compose الافتراضي ومحصور بملف legacy."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPOSE = REPO_ROOT / "docker-compose.yml"
LEGACY_COMPOSE = REPO_ROOT / "docker-compose.legacy.yml"


def main() -> int:
    default_text = DEFAULT_COMPOSE.read_text(encoding="utf-8")
    legacy_text = LEGACY_COMPOSE.read_text(encoding="utf-8")

    if "CORE_KERNEL_URL" in default_text:
        print("❌ CORE_KERNEL_URL must not exist in default docker-compose.yml")
        return 1

    if "core-kernel" not in legacy_text:
        print("❌ docker-compose.legacy.yml must retain core-kernel emergency stack")
        return 1

    if 'profiles: ["legacy"]' not in default_text:
        print("❌ core-kernel service in default compose must be behind legacy profile")
        return 1

    print("✅ CORE_KERNEL_URL removed from default compose and legacy profile enforced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
