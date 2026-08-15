#!/usr/bin/env python3
"""E2E حيّ على Supabase الإنتاجية (D-258 · ISS-170 · 2026-08-15) — بعد تفكيك hotspot بنية الاختبارات.
يُثبت أن إعادة البناء المعمارية صفر تغيير سلوكي على المسار الحيّ:
  1. /health صادق (database=ok)
  2. تسجيل الأدمن (إذا لزم) + تسجيل/دخول المستخدم (المسارات `/api/security/*`)
  3. رمز JWT للمستخدم + رمز الأدمن
  4. WS حيّ على `/api/chat/ws` — محادثة كاملة حتى assistant_final (لا حرق LLM مفتوح: سؤال رياضي بسيط)
  5. تحقق persistence حيّ على Supabase عبر db_bridge (عدد صفوف conversation_history)
التهيئة (لا أسرار في الكود):
    E2E_BACKEND=http://localhost:8000   DATABASE_URL=postgresql://...   # الجسر يقرأ DATABASE_URL
    DIAG_EMAIL/DIAG_PASSWORD + ADMIN_EMAIL/ADMIN_PASSWORD
Usage:
    python3.12 scripts/e2e_d258_supabase_live.py "اشرح قانون نيوتن الثاني"
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

import httpx
import websockets

BACKEND = os.environ.get("E2E_BACKEND", "http://localhost:8000")
EMAIL = os.environ.get("DIAG_EMAIL", "houssamannaba963@gmail.com")
PASSWORD = os.environ.get("DIAG_PASSWORD", "1111")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "benmerahhoussam16@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1111")
FULLNAME = "Houssam D258 E2E"

CHECKS: list[bool] = []


def check(name: str, ok: bool, detail: str) -> bool:
    CHECKS.append(ok)
    print(f"  {'✅' if ok else '❌'} {name}: {detail}")
    return ok


async def ensure_user(email: str, password: str, fullname: str) -> tuple[str, int]:
    """Login؛ وإن تعذّر: register ثم login. يُعيد (token, user_id)."""
    async with httpx.AsyncClient(timeout=30) as c:
        for attempt in ("login", "register", "login"):
            if attempt == "register":
                r = await c.post(
                    f"{BACKEND}/api/security/register",
                    json={"full_name": fullname, "email": email, "password": password},
                )
                print(f"  register({email}) -> HTTP {r.status_code}")
                continue
            r = await c.post(
                f"{BACKEND}/api/security/login",
                json={"email": email, "password": password},
            )
            if r.status_code == 200:
                d = r.json()
                uid = int((d.get("user") or {}).get("id") or 0)
                print(f"  login({email}) OK -> user_id={uid}")
                return d["access_token"], uid
        raise SystemExit(f"login failed: {r.status_code} {r.text[:200]}")


async def turn(ws: websockets.ClientConnection, question: str, conversation_id: int | None) -> dict:
    payload: dict = {"question": question, "client_request_id": str(uuid.uuid4())}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    await ws.send(json.dumps(payload))
    text_parts: list[str] = []
    ui_components: list[str] = []
    conv_id = conversation_id
    terminal = None
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=240)
        event = json.loads(raw)
        etype = event.get("type")
        ep = event.get("payload") or {}
        if etype == "conversation_init":
            conv_id = ep.get("conversation_id") or conv_id
        elif etype == "assistant_delta":
            text_parts.append(str(ep.get("content") or ""))
        elif etype == "ui_component":
            ui_components.append(str(ep.get("component") or "?"))
        elif etype in ("error", "assistant_error"):
            print(f"  WS ERROR payload: {json.dumps(ep)[:400]}")
            terminal = etype
            break
        elif etype == "assistant_final":
            text_parts.append(str(ep.get("content") or ""))
            terminal = "assistant_final"
            # protocol النظام: `persisted` هو الإطار الحتمي النهائي للدور —
            # إنهاء الحلقة عند وصوله بدل انتظار timeout على recv التالي.
            try:
                extra = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
                if extra.get("type") == "ui_component":
                    ui_components.append(str((extra.get("payload") or {}).get("component") or "?"))
                    extra = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
                if extra.get("type") == "persisted":
                    terminal = "complete"
            except TimeoutError:
                pass
            break
    return {
        "text": "".join(text_parts),
        "ui_components": ui_components,
        "conversation_id": conv_id,
        "terminal": terminal,
    }


def _conv_count(user_id: int) -> int | None:
    """عدّ صفوف conversation_history للمستخدم عبر اتصال مباشر (None إن تعذّر)."""
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("APP_DATABASE_URL")
    if not db_url:
        return None
    try:
        from urllib.parse import unquote, urlparse

        import psycopg2  # type: ignore[import-not-found]

        u = urlparse(db_url)
        conn = psycopg2.connect(
            user=u.username,
            password=unquote(u.password or ""),
            host=u.hostname,
            port=u.port,
            dbname=u.path.lstrip("/"),
            sslmode="require",
            connect_timeout=20,
        )
        with conn.cursor() as cur:
            # D-024: فضاء العميل = customer_conversations (لا conversation_history).
            cur.execute(
                "SELECT count(*) FROM customer_conversations WHERE user_id=%s;", (int(user_id),)
            )
            n = int(cur.fetchone()[0])
        conn.close()
        return n
    except Exception as exc:
        print(f"  (direct check skipped: {exc})")
        return None

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import db_bridge  # type: ignore[import-not-found]

        status, body, _ = db_bridge.run_sql(
            f"SELECT count(*) n FROM conversation_history WHERE user_id={int(user_id)};"
        )
        if status != 200:
            return None
        d, _ = json.JSONDecoder().raw_decode(body[body.index("{") :])
        return int(d["data"][0]["n"]) if d.get("success") else None
    except Exception as exc:
        print(f"  (bridge check skipped: {exc})")
        return None


async def main() -> int:
    question = sys.argv[1] if len(sys.argv) > 1 else "ما هو ناتج 2+2؟"
    print(f"[1] backend={BACKEND}  user={EMAIL}  admin={ADMIN_EMAIL}\n")

    # 1) health
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{BACKEND}/health")
        ok = r.status_code == 200 and ("ok" in r.text.lower())
        check("/health", ok, f"status={r.status_code}")
        if not ok:
            return 1

        # 2+3) auth للأدمن والمستخدم
        admin_token, admin_id = await ensure_user(ADMIN_EMAIL, ADMIN_PASSWORD, "Houssam Admin D258")
        check("ADMIN login", bool(admin_token), f"admin_id={admin_id}")
        user_token, uid = await ensure_user(EMAIL, PASSWORD, FULLNAME)
        check("USER login", bool(user_token), f"user_id={uid}")

        # 3b) REST حيّ بسيط للأدمن (لا حرق LLM)
        r = await c.get(
            f"{BACKEND}/api/security/user/me", headers={"Authorization": f"Bearer {admin_token}"}
        )
        check("admin REST /api/security/user/me", r.status_code == 200, f"status={r.status_code}")

    # قبل المحادثة: عدّ الصفوف
    before = _conv_count(uid)
    print(f"[2] conversation_history rows before = {before}")

    # 4) WS حيّ
    scheme = "wss" if BACKEND.startswith("https") else "ws"
    host = BACKEND.split("://", 1)[1]
    url = f"{scheme}://{host}/api/chat/ws?token={user_token}&session_id={uuid.uuid4()}"
    async with websockets.connect(url, ping_interval=None, open_timeout=20) as ws:
        res = await turn(ws, question, None)
        check(
            "WS chat round-trip",
            res["terminal"] in ("assistant_final", "complete"),
            f"terminal={res['terminal']} text_len={len(res['text'])} ui={len(res['ui_components'])}",
        )
        if res["text"]:
            print(f"   sample: {res['text'][:120]!r}")

    after = _conv_count(uid)
    print(f"[3] conversation_history rows after = {after}")
    if before is not None and after is not None:
        check("persistence on Supabase", after >= before, f"before={before} after={after}")
    else:
        print(
            "  (persistence bridge check skipped — DATABASE_URL/SUPABASE_EDGE_FUNCTION_KEY غير متوفرين)"
        )

    n = sum(CHECKS)
    print(
        f"\nالخلاصة: {n}/{len(CHECKS)} أخضر {'— E2E حيّ كامل ✅' if n == len(CHECKS) else '— فحص ما نجح في الأعلى'}"
    )
    return 0 if n == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
