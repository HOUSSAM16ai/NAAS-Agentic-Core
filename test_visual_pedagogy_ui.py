#!/usr/bin/env python3
"""Protocol V26.2 — Live "UI Director" contract validation.

POSTs the impossible-draw query to the running orchestrator (FastAPI :8000) and
prints the raw JSON response, proving the backend short-circuited ALL
combinatorial math and returned the strict decoupled ``impossible_case`` schema
ready for Next.js to render a visual story.

Usage::

    # boot the backend first (docker compose ... up -d, or uvicorn app.main:app)
    python test_visual_pedagogy_ui.py
    # custom endpoint:
    BASE_URL=http://localhost:8000 python test_visual_pedagogy_ui.py

Zero third-party deps (stdlib urllib) so it runs anywhere.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ENDPOINT = f"{BASE_URL}/api/v1/visual-pedagogy/probability"

# Context: BAC 2024 urn — 2 white, 4 red, 5 green (only 2 white balls exist).
URN_CONTEXT = (
    "يحتوي كيس على 11 كرة: كرتان بيضاوان مرقمتان بـ 1 و 3، "
    "وأربع كرات حمراء، وخمس كرات خضراء. نسحب كرات عشوائياً."
)
QUESTION = "كيفاش نسحب 3 كرات بيضاء في نفس الوقت؟"

PAYLOAD = {
    "question": QUESTION,
    "history": [{"role": "user", "content": URN_CONTEXT}],
}


def main() -> int:
    body = json.dumps(PAYLOAD).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    print(f"🎯 POST {ENDPOINT}")
    print(f"   question: {QUESTION}\n")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as exc:
        print(f"❌ HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}", file=sys.stderr)
        return 2
    except urllib.error.URLError as exc:
        print(f"❌ Cannot reach {ENDPOINT}: {exc.reason}", file=sys.stderr)
        print("   Boot the backend first (docker compose -f docker-compose.codespaces.yml up -d).")
        return 2

    print(f"✅ HTTP {status} — RAW JSON RESPONSE:\n")
    data = json.loads(raw)
    print(json.dumps(data, ensure_ascii=False, indent=2))

    # ── PROOF: strict impossible_case schema, math fully bypassed ──────────────
    print("\n🔬 CONTRACT ASSERTIONS:")
    checks = [
        ("ui_mode == 'impossible_case'", data.get("ui_mode") == "impossible_case"),
        ("is_impossible_case is True", data.get("is_impossible_case") is True),
        ("fallback_math is null", data.get("visual_directives", {}).get("fallback_math") is None),
        (
            "animation_hint == 'bag_shake'",
            data.get("visual_directives", {}).get("animation_hint") == "bag_shake",
        ),
        (
            "numerical_state.available_items == 2",
            data.get("numerical_state", {}).get("available_items") == 2,
        ),
        (
            "numerical_state.requested_items == 3",
            data.get("numerical_state", {}).get("requested_items") == 3,
        ),
        (
            "numerical_state.item_color == 'white'",
            data.get("numerical_state", {}).get("item_color") == "white",
        ),
        ("pedagogical_message present", bool(data.get("pedagogical_message"))),
        (
            "NO degenerate math keys (tree/total_combinations)",
            not any(k in data for k in ("tree", "total_combinations", "composition", "groups")),
        ),
    ]
    ok = True
    for label, passed in checks:
        print(f"   {'✅' if passed else '❌'} {label}")
        ok = ok and passed

    if ok:
        print("\n🎉 PROOF COMPLETE — math short-circuited, strict impossible_case schema returned.")
        return 0
    print("\n❌ Contract assertions failed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
