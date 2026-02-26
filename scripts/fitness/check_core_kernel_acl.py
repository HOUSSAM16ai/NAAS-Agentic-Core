"""يتحقق أن استخدام CORE_KERNEL_URL محصور في Legacy ACL فقط ضمن كود التشغيل."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {
    "microservices/api_gateway/config.py",
    "microservices/api_gateway/legacy_acl/adapter.py",
}


EXCLUDED_TOP_LEVEL = {"tests", "scripts"}


def main() -> int:
    violations: list[str] = []
    for path in REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.split("/", 1)[0] in EXCLUDED_TOP_LEVEL:
            continue
        text = path.read_text(encoding="utf-8")
        if "CORE_KERNEL_URL" in text and rel not in ALLOWED:
            violations.append(rel)
    if violations:
        print("❌ CORE_KERNEL_URL usage outside ACL:")
        for item in violations:
            print(f" - {item}")
        return 1
    print("✅ CORE_KERNEL_URL usage constrained to ACL module.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
