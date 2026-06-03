#!/usr/bin/env python3
"""db_bridge.py — run SQL against Supabase via the ``claude-admin`` Edge Function.

The sandbox/Codespaces network firewall blocks raw TCP to Postgres ports
(5432/6543), so direct DB access is impossible from this environment. This helper
sends SQL over HTTPS (port 443) to a Supabase Edge Function that executes it and
returns JSON. See CLAUDE.md §6.83.

Uses only the Python standard library (``urllib``) so it works in degraded
environments with no third-party deps installed — same portable pattern as
``scripts/diagnose_chat.py``.

Configuration (read from the process environment — never hardcode the secret):
    SUPABASE_EDGE_FUNCTION_URL   public endpoint (falls back to the known URL)
    SUPABASE_EDGE_FUNCTION_KEY   bearer token (REQUIRED — git-ignored secrets.env)

Usage:
    # load env first (git-ignored secrets.env)
    set -a && . .devcontainer/secrets.env && set +a

    python3 scripts/db_bridge.py --version           # SELECT version();
    python3 scripts/db_bridge.py "SELECT 1;"         # inline SQL
    echo "SELECT now();" | python3 scripts/db_bridge.py   # SQL from stdin

Exit codes: 0 = HTTP 2xx, 1 = HTTP error / network error, 2 = bad usage / no token.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

# Public endpoint (not a secret). Overridable via env; documented in CLAUDE.md §6.83.
_DEFAULT_URL = "https://aocnuqhxrhxgbfcgbxfy.supabase.co/functions/v1/claude-admin"


def _resolve_config() -> tuple[str, str]:
    url = (os.environ.get("SUPABASE_EDGE_FUNCTION_URL") or "").strip() or _DEFAULT_URL
    key = (os.environ.get("SUPABASE_EDGE_FUNCTION_KEY") or "").strip()
    return url, key


def run_sql(sql: str, timeout: float = 30.0) -> tuple[int, str, float]:
    """POST ``{"sql_query": sql}`` to the Edge Function; return (status, body, ms)."""
    url, key = _resolve_config()
    if not key:
        print(
            "ERROR: SUPABASE_EDGE_FUNCTION_KEY is not set.\n"
            "  Fix: set -a && . .devcontainer/secrets.env && set +a\n"
            "  (or configure it as a Codespaces/Gitpod secret). See CLAUDE.md §6.83.",
            file=sys.stderr,
        )
        sys.exit(2)

    payload = json.dumps({"sql_query": sql}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")

    started = time.time()
    try:
        # Trusted owner-controlled HTTPS endpoint (Supabase Edge Function).
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        print(f"ERROR: request to {url} failed: {exc}", file=sys.stderr)
        sys.exit(1)
    elapsed_ms = (time.time() - started) * 1000.0
    return status, body, elapsed_ms


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run SQL against Supabase via the claude-admin Edge Function.",
    )
    parser.add_argument("sql", nargs="?", help="SQL to run (or pipe via stdin).")
    parser.add_argument(
        "--version",
        action="store_true",
        help="Convenience: run SELECT version(); to verify the bridge.",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout (s).")
    args = parser.parse_args()

    if args.version:
        sql = "SELECT version();"
    elif args.sql:
        sql = args.sql
    elif not sys.stdin.isatty():
        sql = sys.stdin.read().strip()
    else:
        parser.error("provide SQL as an argument, via stdin, or use --version")
        return  # unreachable; for type-checkers

    if not sql:
        print("ERROR: no SQL provided.", file=sys.stderr)
        sys.exit(2)

    status, body, elapsed_ms = run_sql(sql, timeout=args.timeout)

    try:
        rendered = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        rendered = body
    print(rendered)
    print(f"\n[HTTP {status} · {elapsed_ms:.0f}ms]", file=sys.stderr)
    sys.exit(0 if 200 <= status < 300 else 1)


if __name__ == "__main__":
    main()
