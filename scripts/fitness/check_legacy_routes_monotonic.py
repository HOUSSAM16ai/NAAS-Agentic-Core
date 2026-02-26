"""يتحقق أن عدد المسارات legacy لا يزيد عن خط الأساس المعتمد."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTES_FILE = REPO_ROOT / "config/routes_registry.json"
BASELINE_FILE = REPO_ROOT / "config/legacy_routes_baseline.txt"


def main() -> int:
    routes_data = json.loads(ROUTES_FILE.read_text(encoding="utf-8"))
    baseline = int(BASELINE_FILE.read_text(encoding="utf-8").strip())
    current = sum(1 for route in routes_data["routes"] if route.get("legacy_flag") is True)
    if current > baseline:
        print(f"❌ Legacy route count increased: current={current} baseline={baseline}")
        return 1
    print(f"✅ Legacy route count monotonic: current={current} baseline={baseline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
