#!/usr/bin/env python3
"""export_openapi — مولِّد عقود OpenAPI للخدمات المصغرة (D-173 Stage 4, API-first 100%).

يستورد تطبيق FastAPI لكل خدمة ويُفرّغ ``app.openapi()`` إلى
``docs/contracts/openapi/<service>-openapi.json`` بنفس اصطلاح الملفات القائمة
(indent=2، ensure_ascii=True، ترتيب مفاتيح طبيعي، بلا سطر جديد ختامي).

الاستخدام:
    python scripts/contracts/export_openapi.py            # يكتب كل العقود
    python scripts/contracts/export_openapi.py --check    # لا يكتب؛ يفشل عند أي انحراف

يقرأ ``check_openapi_parity`` هذا نفسه (SSOT) لتوليد العقود في الذاكرة ومقارنتها
بالملتزَم. أي خدمة يتعذّر استيرادها (تبعيات غير موجودة في البيئة) تُبلَّغ بوضوح؛
في CI كل التبعيات موجودة (requirements-ci.txt) فتُولَّد كل العقود.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "docs" / "contracts" / "openapi"

# (اسم ملف العقد، مسار وحدة تطبيق FastAPI، اسم كائن التطبيق)
SERVICES: tuple[tuple[str, str, str], ...] = (
    ("orchestrator_service", "microservices.orchestrator_service.main", "app"),
    ("user_service", "microservices.user_service.main", "app"),
    ("planning_agent", "microservices.planning_agent.main", "app"),
    ("memory_agent", "microservices.memory_agent.main", "app"),
    ("observability_service", "microservices.observability_service.main", "app"),
    # D-173 Stage 4: العقود الخمسة الناقصة (API-first 100%).
    ("content_retrieval_skill", "microservices.content_retrieval_skill.main", "app"),
    ("conversation_service", "microservices.conversation_service.main", "app"),
    ("reasoning_agent", "microservices.reasoning_agent.main", "app"),
    ("research_agent", "microservices.research_agent.main", "app"),
    ("api_gateway", "microservices.api_gateway.main", "app"),
    # D-174: API-first 11/11 — auditor_service brought under the parity gate.
    ("auditor_service", "microservices.auditor_service.src.main", "app"),
)


def render_spec(module_path: str, app_attr: str) -> str:
    """يستورد التطبيق ويُرجع تمثيل OpenAPI JSON (نفس اصطلاح الملفات القائمة)."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    module = importlib.import_module(module_path)
    app = getattr(module, app_attr)
    spec = app.openapi()
    return json.dumps(spec, indent=2, ensure_ascii=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="لا تكتب؛ افشل عند أي انحراف عن الملتزَم."
    )
    parser.add_argument("--only", default="", help="تولِيد خدمة واحدة فقط (اسم العقد) — للتشخيص.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    drift = False
    errors: list[str] = []
    for name, module_path, app_attr in SERVICES:
        if args.only and args.only != name:
            continue
        try:
            rendered = render_spec(module_path, app_attr)
        except Exception as exc:  # pragma: no cover - بيئة CI تملك كل التبعيات
            errors.append(f"{name}: import failed — {type(exc).__name__}: {exc}")
            continue
        target = OUT_DIR / f"{name}-openapi.json"
        if args.check:
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            if current != rendered:
                drift = True
                print(f"❌ OpenAPI drift: {target.relative_to(REPO_ROOT)}")
        else:
            target.write_text(rendered, encoding="utf-8")
            print(f"✅ wrote {target.relative_to(REPO_ROOT)} ({len(rendered)} bytes)")

    if errors:
        for e in errors:
            print(f"⚠️  {e}")
        # الاستيراد الفاشل خطأ صلب فقط عند --check (CI يملك كل التبعيات).
        if args.check:
            print("❌ some services failed to import (missing deps?)")
            return 1
    if args.check and drift:
        print("Regenerate with: python scripts/contracts/export_openapi.py")
        return 1
    if args.check and not drift and not errors:
        print("✅ all committed OpenAPI contracts match generated output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
