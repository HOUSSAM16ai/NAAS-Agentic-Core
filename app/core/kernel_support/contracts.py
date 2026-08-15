"""شريحة العقود (D-260 — تفكيك hotspot `app/kernel.py` — CodeScene X-Ray).

يفكّ `_validate_contract_alignment` (radon B(7) · 35 LOC · Complex Method)
إلى دالةٍ نقيةٍ تبني قائمة المخالفات (`build_contract_violations`) ودالة
تطبيقٍ تتحقق منها — بلا تفرّع متداخل (nesting) وتبليغٌ متسلسلٌ واضح،
والقرار النهائي (soft للـ OpenAPI · hard للـ AsyncAPI) يبقى في القشرة.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app.core.asyncapi_contracts import (
    default_asyncapi_contract_path,
    validate_asyncapi_contract_structure,
)
from app.core.openapi_contracts import (
    compare_contract_to_runtime,
    default_contract_path,
    load_contract_operations,
)

logger = logging.getLogger(__name__)


def build_contract_violations(app: FastAPI) -> list[str]:
    """يبني قائمة مخالفات العقد المفتوح (OpenAPI) مقابل مخطط التشغيل — نقية.

    لا تُسجِّل ولا ترمي — فقط تحول التقرير إلى نصوص قابلةٍ للاستهلاك:
    المسارات الناقصة ثم العمليات الناقصة، مرتّبةً لأجل قابلية المقارنة
    في الاختبارات والبوابات النصية.
    """
    spec_path = default_contract_path()
    contract_operations = load_contract_operations(spec_path)
    if not contract_operations:
        return []

    report = compare_contract_to_runtime(
        contract_operations=contract_operations,
        runtime_schema=app.openapi(),
    )
    if report.is_clean():
        return []

    violations: list[str] = []
    if report.missing_paths:
        missing_paths = sorted(report.missing_paths)
        violations.append(f"missing_paths={missing_paths}")
    if report.missing_operations:
        summary = {path: sorted(methods) for path, methods in report.missing_operations.items()}
        violations.append(f"missing_operations={summary}")
    return violations


def _validate_contract_alignment(app: FastAPI) -> None:
    """يتحقق من تطابق مخطط التشغيل مع عقد OpenAPI الأساسي."""
    violations = build_contract_violations(app)
    if not violations:
        spec_path = default_contract_path()
        if load_contract_operations(spec_path):
            logger.info("✅ Contract alignment verified against runtime schema.")
        else:
            logger.warning("⚠️ لم يتم العثور على عقد OpenAPI للتحقق من التوافق.")
    else:
        for violation in violations:
            if violation.startswith("missing_paths="):
                logger.error("❌ مسارات العقد غير موجودة في التشغيل: %s", violation)
            else:
                logger.error("❌ عمليات العقد غير موجودة في التشغيل: %s", violation)
        logger.warning("⚠️ OpenAPI contract validation failed: %s", "; ".join(violations))

    asyncapi_report = validate_asyncapi_contract_structure(default_asyncapi_contract_path())
    if not asyncapi_report.is_clean():
        raise ValueError(
            "AsyncAPI contract validation failed: " + "; ".join(asyncapi_report.errors)
        )
