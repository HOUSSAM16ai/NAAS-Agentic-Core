#!/usr/bin/env python3
"""check_openapi_parity — بوّابة API-first: كل خدمة لها عقد OpenAPI ملتزَم يغطّي
مساراتها الفعلية (D-173 Stage 4).

**دلالية لا بايتية**: تقارن مجموعة العمليات ``(METHOD, path)`` بين ``app.openapi()``
الحيّ والعقد الملتزَم — فإضافة/حذف endpoint يُكشَف، بينما اختلافات تصيير المخطط بين
إصدارات pydantic **لا** تُسبّب فشلاً كاذباً (بوّابة byte-exact هشّة عبر الإصدارات).

يُعيد استخدام ``scripts/contracts/export_openapi.py`` (SSOT للخدمات + المولِّد).
الخدمة التي يتعذّر استيرادها تُبلَّغ خطأً صلباً (CI يملك كل تبعيات requirements-ci.txt).

الاستخدام:
    python scripts/fitness/check_openapi_parity.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "docs" / "contracts" / "openapi"
_HTTP_METHODS = frozenset({"get", "post", "put", "delete", "patch", "options", "head"})

sys.path.insert(0, str(REPO_ROOT / "scripts" / "contracts"))
from export_openapi import SERVICES, render_spec_isolated


def _operations(spec: dict) -> set[tuple[str, str]]:
    """مجموعة العمليات ``(METHOD, path)`` من مخطط OpenAPI."""
    ops: set[tuple[str, str]] = set()
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method in item:
            if method.lower() in _HTTP_METHODS:
                ops.add((method.upper(), path))
    return ops


def main() -> int:
    failures: list[str] = []
    checked = 0
    for name, module_path, app_attr in SERVICES:
        contract = CONTRACTS_DIR / f"{name}-openapi.json"
        if not contract.exists():
            failures.append(f"{name}: عقد OpenAPI مفقود ({contract.relative_to(REPO_ROOT)})")
            continue
        try:
            # D-231: عملية منفصلة لكل تطبيق — استيراد أكثر من تطبيقٍ في عمليةٍ
            # واحدة يرفع تصادم `MetaData` في SQLAlchemy (نفس منطق عزل D-105).
            live = json.loads(render_spec_isolated(module_path, app_attr))
        except Exception as exc:  # pragma: no cover - CI يملك كل التبعيات
            failures.append(f"{name}: تعذّر الاستيراد — {type(exc).__name__}: {exc}")
            continue
        committed = json.loads(contract.read_text(encoding="utf-8"))
        live_ops = _operations(live)
        committed_ops = _operations(committed)
        missing = live_ops - committed_ops  # في التطبيق الحيّ لا في العقد
        extra = committed_ops - live_ops  # في العقد لا في التطبيق
        if missing or extra:
            detail = []
            if missing:
                detail.append(f"live-only={sorted(missing)[:6]}")
            if extra:
                detail.append(f"contract-only={sorted(extra)[:6]}")
            failures.append(
                f"{name}: OpenAPI endpoint drift ({'; '.join(detail)}) — "
                "regenerate: python scripts/contracts/export_openapi.py"
            )
        checked += 1

    if failures:
        print("❌ OpenAPI parity violations:")
        for f in failures:
            print(f"   • {f}")
        return 1
    print(f"✅ OpenAPI parity: {checked} خدمة — كل عقد يغطّي مسارات تطبيقها الفعلية (API-first)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
