#!/usr/bin/env python3.12
"""D-171 (ISS-132) live E2E: admin tool question crosses the 13-node graph.

Before D-171 the tool was EXECUTED (`TOOL EXECUTED → N files`) but then rejected
by `ValidateAccessNode` with `ADMIN_ACCESS_DENIED`, because AgentState dropped
the admin identity and the handler ignored `_jwt_payload`. This drives the real
orchestrator `/api/chat/messages` endpoint with an admin JWT and asserts the tool
answer actually reaches the client.

Env: ORCH (default http://localhost:8006) · SECRET_KEY must match the running
orchestrator (the e2e stack shares one).

Usage:
    source scratchpad/e2e_env.sh
    python3.12 scripts/verify_d171_live.py
"""

from __future__ import annotations

import json
import os
import sys
import time

import httpx
import jwt

ORCH = os.environ.get("ORCH", "http://localhost:8006")
SECRET = os.environ["SECRET_KEY"]

_RESULTS: list[tuple[str, bool, str]] = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    _RESULTS.append((name, ok, detail))
    print(f"{'✅' if ok else '❌'} {name}" + (f" — {detail[:110]}" if detail else ""))


def _mint(sub: str, *, admin: bool) -> str:
    claims: dict[str, object] = {"sub": sub, "exp": int(time.time()) + 600}
    if admin:
        claims["role"] = "admin"
        claims["is_admin"] = True
        claims["scope"] = "admin:tools"
    else:
        claims["roles"] = ["USER"]
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _ask(token: str, question: str) -> tuple[str, list[str]]:
    """POST /api/chat/messages, collect assistant_delta text + event types."""
    body = {"question": question, "user_id": 1, "context": {}}
    headers = {"Authorization": f"Bearer {token}"}
    text_parts: list[str] = []
    types: list[str] = []
    with httpx.Client(timeout=120) as c:
        with c.stream("POST", f"{ORCH}/api/chat/messages", json=body, headers=headers) as r:
            if r.status_code != 200:
                return f"__HTTP_{r.status_code}__", []
            for line in r.iter_lines():
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = ev.get("type", "")
                types.append(t)
                if t in ("assistant_delta", "assistant_final"):
                    # HTTP path puts the full answer in assistant_final.content when
                    # streamed_chars==0 (deterministic tool result, no LLM token stream).
                    text_parts.append((ev.get("payload") or {}).get("content", ""))
    return "".join(text_parts), types


def main() -> int:
    # ── admin tool question — the exact ISS-132 catastrophe scenario ──────────
    admin_tok = _mint("1", admin=True)
    ans, types = _ask(admin_tok, "كم عدد ملفات بايثون في المشروع؟")
    denied = "ADMIN_ACCESS_DENIED" in ans or "غير مصرّح" in ans or "صلاحية" in ans
    has_number = any(ch.isdigit() for ch in ans)
    _check(
        "admin tool crosses ValidateAccessNode (no ADMIN_ACCESS_DENIED)",
        bool(ans) and not denied and not ans.startswith("__HTTP_"),
        ans.strip() or f"types={types[:6]}",
    )
    _check(
        "admin tool answer carries a real count",
        has_number and not denied,
        ans.strip(),
    )

    # ── general question by a regular user — backbone answers everything ──────
    user_tok = _mint("7", admin=False)
    gans, gtypes = _ask(user_tok, "ما هي الجاذبية الأرضية؟")
    _check(
        "general question answered by the backbone (regular user)",
        len(gans) > 40 and "assistant_final" in gtypes and not gans.startswith("__HTTP_"),
        f"len={len(gans)} terminal={'assistant_final' in gtypes}",
    )

    ok = all(r[1] for r in _RESULTS)
    print()
    print(f"=== D-171 LIVE E2E: {'ALL PASS ✅' if ok else 'FAILURES ❌'} ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
