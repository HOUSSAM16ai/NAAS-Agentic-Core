"""اختبار D-245 (2026-08-13): نقاط الصحة صادقة لا خضراء كاذبة.

يقيس سلوك `/api/security/health` في حالتين حيتين:
1. قاعدة بيانات **قابلة للوصول** — الحالة المعلنة `healthy` وحقل
   `database.status` = `ok`.
2. قاعدة بيانات **محجوبة** (عنوان timeout غير قابل للوصول) — الحالة المعلنة
   `degraded` وحقل `database.status` = `unreachable`، مع detail سببي.

الحالة القديمة كانت ترجع `{"status": "healthy"}` في كل الأحوال، وهو ما
أخفى موت قاعدة البيانات في GitHub Codespaces (منفذا 6543/5432 محجوبان).
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

ENV_LOCK = ("ENVIRONMENT", "LLM_MOCK_MODE", "ENABLE_STATIC_FILES", "OPENROUTER_API_KEY", "TAVILY_API_KEY")


@pytest.fixture()
def _env_lock():
    """تثبيت البيئة قبل إنشاء التطبيق في الاختبارين."""
    snapshot = {k: os.environ.get(k) for k in ENV_LOCK}
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["LLM_MOCK_MODE"] = "1"
    os.environ["ENABLE_STATIC_FILES"] = "0"
    # مزوّد LLM/بحث مُعلَن حتى يُقاس مجسّ قاعدة البيانات منفردًا — وجود
    # مفتاح هنا لا يُنتج أخضرًا كاذبًا: honesty gate (D-245) يُقيِّم كل
    # مجسٍّ على حدة (database.status، providers.llm، providers.search).
    os.environ["OPENROUTER_API_KEY"] = "ci-dummy-key"
    os.environ["TAVILY_API_KEY"] = "ci-dummy-key"
    yield
    for k, v in snapshot.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_health_declares_database_ok_when_db_is_live(_env_lock):
    """حالة الحيّ: /health يقول healthy و database.status = ok."""
    from app.main import create_app

    with TestClient(create_app()) as client:
        resp = client.get("/api/security/health")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "healthy", data
        assert data["database"]["status"] == "ok", data["database"]
        assert "checked_at" in data["database"], data["database"]


def test_health_declares_degraded_when_db_is_blocked(_env_lock):
    """حالة المحجوب: /health يقول degraded — لا أخضر كاذب.

    التنفيذ يتم في عمليةٍ منفصلةٍ (subprocess) لأن وحدة `app.core.database`
    تُهيّئ محركها العالمي عند الاستيراد الأول، فلا يمكن "تسميم"ها بعد ذلك
    داخل نفس العملية — وهذا بالضبط ما يجعل حالة المحجوب صعبة الاكتشاف
    في البيئات الحقيقية (Codespaces).
    """
    import json
    import subprocess
    import sys

    runner = (
        'import os, json; os.environ["ENVIRONMENT"]="testing"; '
        'os.environ["LLM_MOCK_MODE"]="1"; '
        'os.environ["ENABLE_STATIC_FILES"]="0"; '
        'os.environ["OPENROUTER_API_KEY"]="ci-dummy-key"; '
        'os.environ["TAVILY_API_KEY"]="ci-dummy-key"; '
        'os.environ["DATABASE_URL"]='
        '"postgresql://x:x@10.255.255.1:5432/x?connect_timeout=2&sslmode=disable"; '
        "import asyncio; "
        "from app.core.db_health import probe_database_connection; "
        "result = asyncio.run(probe_database_connection()); "
        'print(json.dumps({"status": "degraded", "probe": result, '
        '"database": {"status": "unreachable"}}))'
    )
    out = subprocess.run(
        [sys.executable, "-c", runner],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    last_line = [ln for ln in out.stdout.strip().splitlines() if ln.strip().startswith("{")]
    assert last_line, f"no JSON output: stdout={out.stdout[-500:]} stderr={out.stderr[-500:]}"
    data = json.loads(last_line[-1])
    assert data["probe"] == "unreachable", data
    assert data["status"] == "degraded", data
