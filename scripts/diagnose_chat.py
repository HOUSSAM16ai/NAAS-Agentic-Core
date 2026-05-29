#!/usr/bin/env python3
"""
CogniForge — Live Chat Diagnostic (run inside the GitHub Codespaces terminal).

أداة تشخيص ذاتية لكارثة «تأرجح متصل/غير متصل + لا يرد + طرد». تلتقط السبب الحقيقي
من بيئتك الحيّة (Supabase + الحزمة الكاملة) لأن السبب لا يظهر خارج Codespaces.

التشغيل في ترمينال Codespaces:
    python scripts/diagnose_chat.py
    # اختياري للاختبار الكامل (login + WS):
    DIAG_EMAIL=houssamannaba963@gmail.com DIAG_PASSWORD=1111 python scripts/diagnose_chat.py

ثم انسخ كامل المخرجات والصقها هنا. لا يطبع أي أسرار (الـ token وكلمة مرور DB مُخفاة).
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

APP_PORT = int(os.environ.get("APP_PORT", "8000"))
FRONTEND_PORT = int(os.environ.get("FRONTEND_PORT", "5000"))
BACKEND = f"http://127.0.0.1:{APP_PORT}"


def hr(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def run(cmd: str, timeout: int = 15) -> str:
    try:
        out = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout, check=False
        )
        return (out.stdout + out.stderr).strip()
    except Exception as exc:
        return f"(command failed: {exc})"


def http(
    method: str, url: str, token: str | None = None, body: dict | None = None, timeout: int = 12
):
    """Returns (status_code:int|None, body_text:str, elapsed_ms:int)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), int((time.time() - t0) * 1000)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), int((time.time() - t0) * 1000)
    except Exception as e:
        return None, f"{type(e).__name__}: {e}", int((time.time() - t0) * 1000)


def port_listening(port: int) -> bool:
    s = socket.socket()
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        s.close()


# ─────────────────────────────── A. Deployment ───────────────────────────────
def section_deployment() -> None:
    hr("A. DEPLOYMENT — هل الكود الأحدث يعمل؟")
    print("branch :", run("git rev-parse --abbrev-ref HEAD"))
    print("HEAD   :", run("git log --oneline -1"))
    print("recent :")
    print(run("git log --oneline -6"))
    # هل إصلاحات ISS-100 موجودة في الكود الذي يعمل؟
    checks = {
        "WsActor (DB-free connect)": "grep -rl 'class WsActor' app/api/routers/ws_auth.py",
        "decode_token_payload": "grep -rl 'def decode_token_payload' app/services/auth/token_decoder.py",
        "customer connect DB-free": "grep -c 'WsActor(id=' app/api/routers/customer_chat.py",
        "_app_is_alive (health)": "grep -c '_app_is_alive' .devcontainer/supervisor.sh",
        "turn keepalive": "grep -c '_run_turn_keepalive' app/api/routers/customer_chat.py",
        "fetchUser cache (D-WS-KICK-002)": "grep -c 'cogniforge_user' frontend/app/components/CogniForgeApp.jsx",
    }
    print("\nfixes present in the deployed code:")
    for name, cmd in checks.items():
        res = run(cmd)
        present = res and res not in ("0", "") and "No such file" not in res
        print(f"  [{'YES' if present else 'NO '}] {name}  ({res or 'missing'})")


# ─────────────────────────────── B. Environment ───────────────────────────────
def section_env() -> None:
    hr("B. ENVIRONMENT (.env — مُخفّى الأسرار)")
    for key in (
        "ENVIRONMENT",
        "DATABASE_URL",
        "APP_DATABASE_URL",
        "OPENROUTER_API_KEY",
        "SECRET_KEY",
    ):
        # process env first
        pv = os.environ.get(key, "")
        if key in ("DATABASE_URL", "APP_DATABASE_URL"):
            pv = pv.split("@")[-1] if "@" in pv else pv  # hide creds, keep host
        elif key in ("OPENROUTER_API_KEY", "SECRET_KEY"):
            pv = f"<set:{len(pv)} chars>" if pv else ""
        print(f"  process env  {key} = {pv or '(unset)'}")
    env_dump = run(
        "grep -E '^(ENVIRONMENT|DATABASE_URL|APP_DATABASE_URL)=' .env 2>/dev/null "
        "| sed -E 's#(://[^:]+:)[^@]+@#\\1***@#; s#(OPENROUTER_API_KEY|SECRET_KEY)=.*#\\1=<hidden>#'"
    )
    print("\n.env (redacted):")
    print(env_dump or "  (.env not found)")


# ─────────────────────────────── C. Service ports ───────────────────────────────
def section_ports() -> None:
    hr("C. SERVICE PORTS — أي خدمة تستمع؟")
    ports = {
        APP_PORT: "monolith (FastAPI/uvicorn)",
        FRONTEND_PORT: "frontend (server.js WS proxy)",
        8003: "conversation-service",
        8006: "orchestrator-service",
        8007: "research-agent",
        8008: "reasoning-agent",
    }
    for p, name in ports.items():
        print(f"  [{'UP ' if port_listening(p) else 'DOWN'}] :{p}  {name}")


# ─────────────────────────────── D. Health (intermittent?) ───────────────────────────────
def section_health() -> None:
    hr("D. /health — هل يتعثّر (503) بشكل متقطّع؟")
    bad = 0
    for i in range(8):
        code, body, ms = http("GET", f"{BACKEND}/health")
        short = body.replace("\n", " ")[:120]
        flag = "" if code == 200 else "  <-- غير صحّي"
        if code != 200:
            bad += 1
        print(f"  #{i + 1}: HTTP {code} ({ms}ms) {short}{flag}")
        time.sleep(1.5)
    if bad:
        print(f"\n  ⚠️  {bad}/8 فحوصات /health فشلت → تعثّر Supabase محتمل (يُفسّر إعادة تشغيل/تأرجح).")
    else:
        print("\n  ✅ /health مستقر (200 في كل المرات).")


# ─────────────────────────────── E. Auth + /me (intermittent?) ───────────────────────────────
def section_auth() -> str | None:
    hr("E. LOGIN + /me — هل المصادقة متقطّعة؟")
    email = os.environ.get("DIAG_EMAIL")
    pwd = os.environ.get("DIAG_PASSWORD")
    if not email or not pwd:
        print("  (تخطّي — مرّر DIAG_EMAIL و DIAG_PASSWORD لتشغيل اختبار المصادقة الكامل)")
        return None
    code, body, ms = http(
        "POST", f"{BACKEND}/api/security/login", body={"email": email, "password": pwd}
    )
    if code != 200:
        print(f"  ❌ login فشل: HTTP {code} ({ms}ms) {body[:200]}")
        return None
    try:
        token = json.loads(body)["access_token"]
    except Exception:
        print(f"  ❌ login لم يُرجِع token: {body[:200]}")
        return None
    print(f"  ✅ login OK ({ms}ms)")
    # decode exp without verifying signature
    try:
        import base64

        payload_b64 = token.split(".")[1] + "=="
        claims = json.loads(base64.urlsafe_b64decode(payload_b64))
        mins = (claims.get("exp", 0) - time.time()) / 60
        print(
            f"  token: sub={claims.get('sub')} is_admin={claims.get('is_admin')} "
            f"عمر متبقٍ={mins:.0f} دقيقة"
        )
        if mins < 60:
            print("  ⚠️  عمر الـ token قصير (<60 دقيقة) → ENVIRONMENT ليس development؟")
    except Exception as e:
        print(f"  (تعذّر فك الـ token: {e})")
    # /me 6x — detect intermittent 401/5xx
    bad = 0
    for i in range(6):
        code, _b, ms = http("GET", f"{BACKEND}/api/security/user/me", token=token)
        if code != 200:
            bad += 1
        print(f"  /me #{i + 1}: HTTP {code} ({ms}ms)")
        time.sleep(1)
    if bad:
        print(f"  ⚠️  {bad}/6 من /me فشلت → سبب محتمل للطرد/التأرجح.")
    else:
        print("  ✅ /me مستقر (200 في كل المرات).")
    return token


# ─────────────────────────────── F. WebSocket probe (the smoking gun) ───────────────────────────────
def section_ws(token: str | None) -> None:
    hr("F. WEBSOCKET — connect/close codes (السبب المباشر للتأرجح)")
    try:
        import asyncio

        import websockets
    except Exception:
        print("  (websockets غير مثبّت في هذا الـ python — جرّب: python -m pip install websockets")
        print("   أو استخدم python بيئة المشروع. تخطّي اختبار WS.)")
        return
    if not token:
        print("  (تخطّي — يحتاج token؛ مرّر DIAG_EMAIL/DIAG_PASSWORD)")
        return

    async def probe(base_port: int, label: str, rounds: int = 3) -> None:
        import uuid

        url = f"ws://127.0.0.1:{base_port}/api/chat/ws?token={token}&session_id={uuid.uuid4()}"
        for r in range(rounds):
            t0 = time.time()
            frames: list[str] = []
            close_code = None
            answered = False
            try:
                async with websockets.connect(
                    url, ping_interval=None, max_size=10_000_000, open_timeout=15
                ) as ws:
                    await ws.send(
                        json.dumps(
                            {"question": "السلام عليكم", "client_request_id": str(uuid.uuid4())}
                        )
                    )
                    while time.time() - t0 < 45:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=20)
                        except TimeoutError:
                            frames.append("RECV_TIMEOUT")
                            break
                        ev = json.loads(raw)
                        t = ev.get("type")
                        if t in ("assistant_delta", "delta"):
                            answered = True
                            if "delta" not in frames:
                                frames.append("delta…")
                        elif t == "assistant_final":
                            frames.append("assistant_final")
                            break
                        elif t not in frames:
                            frames.append(str(t))
            except websockets.exceptions.ConnectionClosed as e:
                close_code = e.code
                frames.append(f"CLOSED:{e.code}")
            except Exception as e:
                frames.append(f"EXC:{type(e).__name__}")
            dur = time.time() - t0
            verdict = "OK answered" if answered else "NO ANSWER"
            print(
                f"  [{label}] round {r + 1}: {verdict}  dur={dur:.1f}s close={close_code} frames={frames}"
            )

    async def main() -> None:
        if port_listening(APP_PORT):
            print(f"\n  -- direct backend :{APP_PORT} (no proxy) --")
            await probe(APP_PORT, f"direct:{APP_PORT}")
        if port_listening(FRONTEND_PORT):
            print(f"\n  -- via frontend :{FRONTEND_PORT} (server.js proxy, the browser path) --")
            await probe(FRONTEND_PORT, f"proxy:{FRONTEND_PORT}")

    asyncio.run(main())


# ─────────────────────────────── G. Logs (errors / restarts / WS close) ───────────────────────────────
def section_logs() -> None:
    hr("G. LOGS — إعادة تشغيل / استثناءات / إغلاق WS")
    candidates = [
        ".superhuman_bootstrap.log",
        ".uvicorn.log",
        ".frontend_launcher.log",
        "/tmp/uvicorn_live.log",
    ]
    found = False
    for f in candidates:
        if os.path.exists(f):
            found = True
            print(f"\n--- {f} (آخر أسطر ذات صلة) ---")
            print(
                run(
                    f"grep -iE 'restart|traceback|error|exception|websocket|disconnect|1013|4401|"
                    f"degraded|health|secret_key|connection' {f} 2>/dev/null | tail -25"
                )
            )
    if not found:
        print("  (لم أجد ملفات log معروفة — جرّب: ls -la *.log .*.log)")


def main() -> None:
    print("CogniForge live chat diagnostic — run in the Codespaces terminal.")
    print(f"time: {time.strftime('%Y-%m-%d %H:%M:%S')}  cwd: {os.getcwd()}")
    section_deployment()
    section_env()
    section_ports()
    section_health()
    token = section_auth()
    section_ws(token)
    section_logs()
    hr("DONE — انسخ كل ما فوق والصقه في المحادثة")
    print("ملاحظة: لا توجد أسرار في المخرجات (token/كلمة مرور DB مُخفاة).")


if __name__ == "__main__":
    sys.exit(main())
