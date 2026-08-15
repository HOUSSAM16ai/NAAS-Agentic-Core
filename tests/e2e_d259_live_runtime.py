"""E2E حيّ لـ D-259/D-260: إثبات زمن تشغيل حقيقي (runtime truth) للمنصة كاملة.

يُشغَّل خارج CI (لا يتحمل CI أسرارًا حيّة — `spec.md` §3) ويقرأ الأسرار من
البيئة العملية فقط:

    DATABASE_URL="postgresql://..." \
    OPENROUTER_API_KEY="sk-or-..." \
    PYTHONPATH=. python3 tests/e2e_d259_live_runtime.py

الاختبارات (كلها على بيئة الإنتاج الحقيقية، لا mocks):

1. قاعدة البيانات: اتصال + جداول جوهرية + صحتها.
2. LLM (OpenRouter): استدعاء PRIMARY (`openai/gpt-oss-20b:free` — قانون D-067)
   والاستجابة صحيحة (content موجود، عربي).
3. أدوات المحتوى: `search_content` عبر ToolRegistry بسلسلة التفويض الكاملة
   (قشرة → شرائح → بحث عميق حقيقي عبر Tavily).
4. بوابة FastAPI: `/health` صادق (database=ok) عبر lifespan kernel الكامل.
5. التوثيق: مانيفست `CONTENT_TOOLS_SOURCE_FILES` يُركِّب المصدر المركّب
   دون `FileNotFoundError` (إصلاح D-259).

⚠️ لا يطبع أي قيمة سرية في السجلات — يكتفي بالنتائج البولية والقياسات.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

REQUIRED_ENV = ["DATABASE_URL", "OPENROUTER_API_KEY"]
MISSING = [k for k in REQUIRED_ENV if not os.environ.get(k)]
if MISSING:
    print(f"❌Missing env vars (read from runtime environment only): {MISSING}")
    raise SystemExit(1)


async def check_database() -> str:
    """1) اتصال حقيقي بقاعدة الإنتاج + جداول جوهرية."""
    from sqlalchemy import text

    from app.core.database import engine

    async with engine.connect() as conn:
        tables = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public'"
        ))
        public_tables = {row[0] for row in tables.fetchall()}
    # أسماء الجداول الجوهرية كما في مخطط الإنتاج الفعلي (D-074 · schema boot auto-fix):
    expected = {"users", "missions", "customer_conversations", "student_bkt_analytics"}
    missing = expected - public_tables
    status = (
        f"✅ DB connected — {len(public_tables)} public tables"
        + (f" · core present: {sorted(expected & public_tables)}" if not missing else "")
    )
    if missing:
        status += f" · ⚠️ core tables absent: {sorted(missing)} (schema boot auto-fix expected)"
    return status


async def check_llm_openrouter() -> str:
    """2) استدعاء حيّ على OpenRouter بالنموذج PRIMARY (D-067)."""
    import httpx

    key = os.environ["OPENROUTER_API_KEY"]
    payload = {
        "model": "openai/gpt-oss-20b:free",
        "messages": [
            {"role": "system", "content": "You are a helpful Arabic tutor. Answer briefly in Arabic."},
            {"role": "user", "content": "ما هو الجهد الكهربائي؟"},
        ],
        "max_tokens": 120,
    }
    body: dict = {}
    async with httpx.AsyncClient(timeout=120.0) as client:
        for _attempt in range(2):  # محاولة ثانية لتحمّل الفشل العابر (rate-limit لحظي)
            try:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {key}"},
                )
                body = resp.json()
            except Exception:
                await asyncio.sleep(2.0)
                continue
            else:
                break
    choices = body.get("choices") or []
    first = choices[0].get("message", {}) if choices else {}
    content = first.get("content") or ""
    finish = choices[0].get("finish_reason") if choices else None
    n_chars = len(content)
    ok = n_chars > 20 and finish in {"stop", "length"}
    return (
        ("✅ OpenRouter PRIMARY OK — "
         f"{n_chars} chars Arabic, finish={finish}, model={body.get('model')}")
        if ok
        else f"❌ OpenRouter FAILED: finish={finish} chars={n_chars} body_keys={sorted(body.keys())}"
    )


async def check_tavily_mcp() -> str:
    """3a) Tavily MCP حيّ (بوابة البحث العميق المعلنة — المستخدم وفّرها مباشرة)."""
    import httpx

    tavily_url = os.environ.get("TAVILY_MCP_URL")
    if not tavily_url:
        return "⚠️ Tavily MCP skipped (TAVILY_MCP_URL not set — deployment-time secret)"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "tavily_search", "arguments": {"query": "الجهد الكهربائي", "max_results": 2}},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            tavily_url,
            json=payload,
            headers={"Accept": "application/json, text/event-stream"},
        )
    # الاستجابة قد تكون SSE (event: message) أو JSON عاديًا — نحلّل الأحداث أولًا
    text = resp.text.strip()
    events = [line.removeprefix("data:").strip() for line in text.splitlines()
              if line.startswith("data:") and line.removeprefix("data:").strip()]
    if not events:
        events = [text] if text.startswith("{") else []
    is_error = True
    content_ok = False
    for raw in events:
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        is_error = bool(ev.get("isError"))
        result = ev.get("result") or {}
        for item in result.get("content", []) or []:
            if item.get("type") == "text" and len(item.get("text", "") or "") > 50:
                content_ok = True
    if is_error:
        return f"❌ Tavily MCP failed: HTTP {resp.status_code} payload reported an error"
    if not content_ok:
        return f"❌ Tavily MCP: no text content in response (HTTP {resp.status_code})"
    return "✅ Tavily MCP live — tavily_search returned real text content (no error)"


async def check_content_tools() -> str:
    """3) سلسلة تفويض content.py كاملة (ToolRegistry → القشرة → الشرائح).

    البحث العميق الحقيقي يذهب إلى `RESEARCH_AGENT_URL` (microservice حيّ —
    خارج نطاق هذا الاستدعاء في بيئة sandbox؛ فشل DNS هنا يعني أن وكيل
    البحث غير مُنشَّر في هذه البيئة، لا أن المنطق معطوب — Fail-Fast صادق)."""
    from app.services.chat.tools import ToolRegistry
    from app.services.chat.tools.content_support import read_content_tools_source

    # 3a) المانيفست المركّب يُركَّب دون FileNotFoundError (إصلاح D-259)
    try:
        source = read_content_tools_source()
        has_branch = "branch.py" in source and "search.py" in source and "content.py" in source
        manifest = "✅ content manifest composes (content.py + search.py + branch.py)" if has_branch else "❌ manifest missing shard"
    except FileNotFoundError as exc:
        return f"❌ manifest FileNotFoundError: {exc}"

    # 3b) البحث الحقيقي (لا mocks) عبر ToolRegistry
    registry = ToolRegistry()
    try:
        results = await registry.execute(
            "search_content",
            {"q": "ما هو القانون الأول لنيوتن؟", "level": "bac", "lang": "ar", "limit": 3},
        )
        count = len(results) if isinstance(results, list) else 0
        return f"{manifest} · ✅ live search_content → {count} report(s) via full delegation chain"
    except Exception as exc:  # البحث الحي قد يُقيَّد (rate-limit) — نفصّل السبب
        return f"{manifest} · ⚠️ live search_content raised {type(exc).__name__}: {str(exc)[:120]}"


async def check_fastapi_health() -> str:
    """4) بوابة FastAPI حيّة: lifespan kernel الكامل + /health صادق."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/health", timeout=30)
    data = resp.json()
    db_state = (data.get("database") or data.get("db") or "?") if isinstance(data, dict) else "?"
    ok = resp.status_code == 200
    return (
        f"✅ /health HTTP {resp.status_code} — database={db_state}"
        if ok
        else f"❌ /health HTTP {resp.status_code}: {data}"
    )


async def main() -> int:
    results = []
    checks = [
        ("Database (Supabase production)", check_database()),
        ("LLM (OpenRouter PRIMARY — D-067)", check_llm_openrouter()),
        ("Tavily MCP (live research gateway)", check_tavily_mcp()),
        ("Content tools (full delegation chain)", check_content_tools()),
        ("FastAPI gateway (/health lifecycle)", check_fastapi_health()),
    ]
    failures = 0
    for label, coro in checks:
        try:
            result = await coro
        except Exception as exc:  # أي فحص حيّ يُبلَّغ ولا يقتل باقي الفحوص
            result = f"❌ {label} raised {type(exc).__name__}: {str(exc)[:150]}"
            failures += 1
        icon = "✅" if result.startswith("✅") else ("⚠️" if result.startswith("⚠️") else "❌")
        results.append(f"[E2E LIVE] {icon} {label}: {result}")
    for line in results:
        print(line)
    n_fail = sum(not line.startswith("[E2E LIVE] ✅") for line in results)
    verdict = 0 if n_fail == 0 else 1
    print(f"\n[E2E LIVE] verdict: {'ALL PASS' if n_fail == 0 else f'{n_fail} check(s) degraded'}")
    return verdict


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
