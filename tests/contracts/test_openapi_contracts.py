"""API-first (D-173 Stage 4): كل خدمة مصغرة لها عقد OpenAPI ملتزَم وصالح.

تغطية خفيفة بلا تبعيات ثقيلة — تتحقق من وجود العقود الإحدى عشرة وصلاحيتها بنيوياً.
التكافؤ الدلالي الحيّ (endpoints التطبيق ↔ العقد) يفرضه
``scripts/fitness/check_openapi_parity.py`` في job test-microservices (حيث كل
تبعيات requirements-ci.txt موجودة لاستيراد التطبيقات).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OPENAPI_DIR = _REPO_ROOT / "docs" / "contracts" / "openapi"

# الخدمات الإحدى عشرة — SSOT في المولِّد؛ هنا نُثبّتها كعقد اختبار مستقل عن التبعيات.
_SERVICES = (
    "orchestrator_service",
    "user_service",
    "planning_agent",
    "memory_agent",
    "observability_service",
    "content_retrieval_skill",
    "conversation_service",
    "reasoning_agent",
    "research_agent",
    "api_gateway",
    # D-174: API-first 11/11 — auditor_service now carries a committed contract.
    "auditor_service",
)


@pytest.mark.parametrize("service", _SERVICES)
def test_service_has_valid_openapi_contract(service: str) -> None:
    path = _OPENAPI_DIR / f"{service}-openapi.json"
    assert path.exists(), f"عقد OpenAPI مفقود: {path.relative_to(_REPO_ROOT)} (API-first)"
    spec = json.loads(path.read_text(encoding="utf-8"))
    assert spec.get("openapi", "").startswith("3."), f"{service}: نسخة OpenAPI غير صالحة"
    assert spec.get("paths"), f"{service}: العقد بلا مسارات"
    assert spec.get("info", {}).get("title"), f"{service}: العقد بلا عنوان"


def test_generator_and_gate_exist() -> None:
    assert (_REPO_ROOT / "scripts" / "contracts" / "export_openapi.py").exists()
    assert (_REPO_ROOT / "scripts" / "fitness" / "check_openapi_parity.py").exists()


def test_generator_service_list_matches_committed_contracts() -> None:
    """قائمة المولِّد (SSOT) تطابق العقود الملتزَمة — لا خدمة بلا عقد ولا عكس."""
    gen_src = (_REPO_ROOT / "scripts" / "contracts" / "export_openapi.py").read_text(
        encoding="utf-8"
    )
    for service in _SERVICES:
        assert f'"{service}"' in gen_src, f"{service} مفقودة من قائمة المولِّد SERVICES"
    committed = {p.stem.replace("-openapi", "") for p in _OPENAPI_DIR.glob("*-openapi.json")}
    assert set(_SERVICES) <= committed, f"عقود مفقودة: {set(_SERVICES) - committed}"
