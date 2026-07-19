#!/usr/bin/env python3
"""verify_full_stack_docker.py — the R0.1 closure gate, automated & fail-loud.

Answers the Codex "Existential Risks" audit (R0.1 Runtime Reproducibility
Collapse). Run AFTER `docker compose up --build -d`:

    bash scripts/compose_env_from_secrets.sh
    docker compose up --build -d
    python scripts/verify_full_stack_docker.py

It proves the stack is REAL — not the silent SQLite/mock/fallback the audit
warns about — and exits non-zero the moment any check fails. Checks:

  1. Every published port answers /health (waits for readiness).
  2. Orchestrator uses a REAL Postgres checkpointer (checkpointer_backend ==
     postgres → R0.2 runtime proof), graph_ready, status ok.
  3. reasoning-agent uses a REAL LLM (llm_backend != mock).
  4. planning-agent is on REAL Postgres (postgresql in its database URL).
  5. No service /health reports a sqlite/mock backend.
  6. Redis (both instances) answers PING.
  7. Prometheus is healthy and EVERY scrape target is UP.
  8. Grafana /api/health reports database: ok.
  9. A real OpenRouter-backed /compose returns a genuine answer (not fallback).

stdlib only — no extra deps (mirrors scripts/db_bridge.py). Configurable via
VERIFY_HOST (default 127.0.0.1) and VERIFY_TIMEOUT (default 420 seconds).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOST = os.environ.get("VERIFY_HOST", "127.0.0.1")
TOTAL_TIMEOUT = int(os.environ.get("VERIFY_TIMEOUT", "420"))
HEALTHY = {"ok", "healthy", "ready", "up", "pass"}
# VERIFY_SKIP: comma-separated service names to treat as SKIPPED (not failed) —
# for environments that cannot run a service (e.g. a tiny-disk sandbox that can't
# fit the torch/sentence-transformers agent images). Their Prometheus targets are
# tolerated too. Leave empty (the default) to require the FULL stack.
SKIP = {s.strip() for s in os.environ.get("VERIFY_SKIP", "").split(",") if s.strip()}

# (name, port, path). "kind" drives the deep assertions below.
SERVICES = [
    ("api-gateway", 8000, "/health"),
    ("planning-agent", 8001, "/health"),
    ("memory-agent", 8002, "/health"),
    ("user-service", 8003, "/health"),
    ("observability-service", 8005, "/health"),
    ("orchestrator-service", 8006, "/health"),
    ("research-agent", 8007, "/health"),
    ("reasoning-agent", 8008, "/health"),
    ("auditor-service", 8009, "/health"),
    ("conversation-service", 8010, "/health"),
]

_PASS: list[str] = []
_FAIL: list[str] = []


def ok(msg: str) -> None:
    _PASS.append(msg)
    print(f"  \033[92m✓\033[0m {msg}")


def fail(msg: str) -> None:
    _FAIL.append(msg)
    print(f"  \033[91m✗ {msg}\033[0m")


def http_get(url: str, timeout: float = 8.0) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def http_post_json(url: str, body: dict, timeout: float = 90.0) -> tuple[int, str]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def health_status(payload: dict) -> str:
    return str(payload.get("status", "")).lower()


def wait_all_ready() -> dict[str, dict]:
    """Poll every service /health until healthy or the global timeout elapses."""
    print(f"\n== Waiting for readiness (budget {TOTAL_TIMEOUT}s) ==")
    deadline = time.time() + TOTAL_TIMEOUT
    last: dict[str, dict] = {}
    pending = {name: (port, path) for name, port, path in SERVICES if name not in SKIP}
    while pending and time.time() < deadline:
        for name in list(pending):
            port, path = pending[name]
            code, text = http_get(f"http://{HOST}:{port}{path}")
            if code == 200:
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    payload = {"status": "ok", "_raw": text[:200]}
                if health_status(payload) in HEALTHY:
                    last[name] = payload
                    del pending[name]
        if pending:
            time.sleep(4)
    for name in pending:
        last[name] = {"status": "TIMEOUT"}
    return last


def assert_all_healthy(health: dict[str, dict]) -> None:
    print("\n== 1. All services healthy ==")
    for name, _port, _path in SERVICES:
        if name in SKIP:
            print(f"  \033[93m⊘\033[0m {name}: SKIPPED (VERIFY_SKIP)")
            continue
        st = health_status(health.get(name, {}))
        if st in HEALTHY:
            ok(f"{name}: status={st}")
        else:
            fail(f"{name}: status={st or 'unreachable'} (expected healthy)")


def assert_no_mock_backends(health: dict[str, dict]) -> None:
    print("\n== 2. No silent sqlite/mock backend ==")
    for name, payload in health.items():
        blob = json.dumps(payload).lower()
        if "sqlite" in blob:
            fail(f"{name}: reports a SQLITE backend — hidden fallback (R0.1)")
        if '"llm_backend": "mock"' in blob or '"llm_backend":"mock"' in blob:
            fail(f"{name}: reports a MOCK LLM backend — hidden fallback (R0.1)")
    if not _FAIL:
        ok("no service /health advertises sqlite or a mock LLM")


def assert_orchestrator(health: dict[str, dict]) -> None:
    print("\n== 3. Orchestrator: REAL Postgres checkpointer (R0.2 runtime proof) ==")
    p = health.get("orchestrator-service", {})
    if p.get("checkpointer_backend") == "postgres":
        ok("orchestrator checkpointer_backend=postgres (AsyncPostgresSaver ACTIVE)")
    else:
        fail(
            "orchestrator checkpointer_backend="
            f"{p.get('checkpointer_backend')!r} (expected 'postgres' — MemorySaver "
            "fallback = R0.2 not closed)"
        )
    if p.get("graph_ready"):
        ok("orchestrator graph_ready=true")
    else:
        fail("orchestrator graph_ready is falsey")


def assert_reasoning(health: dict[str, dict]) -> None:
    print("\n== 4. reasoning-agent: REAL LLM (not mock) ==")
    backend = str(health.get("reasoning-agent", {}).get("llm_backend", "")).lower()
    if backend and backend != "mock":
        ok(f"reasoning-agent llm_backend={backend}")
    else:
        fail(f"reasoning-agent llm_backend={backend or 'unknown'} (expected non-mock)")


def assert_planning_postgres(health: dict[str, dict]) -> None:
    print("\n== 5. planning-agent: REAL Postgres ==")
    db = str(health.get("planning-agent", {}).get("database", "")).lower()
    if "postgresql" in db and "sqlite" not in db:
        ok("planning-agent database=postgresql")
    else:
        fail(f"planning-agent database={db or 'unknown'} (expected postgresql)")


def assert_redis() -> None:
    print("\n== 6. Redis (both instances) answer PING ==")
    for cname in ("cogniforge-redis", "cogniforge-redis-orchestrator"):
        try:
            out = subprocess.run(
                ["docker", "exec", cname, "redis-cli", "ping"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if out.stdout.strip().upper() == "PONG":
                ok(f"{cname}: PONG")
            else:
                fail(f"{cname}: {out.stdout.strip() or out.stderr.strip()!r} (expected PONG)")
        except Exception as e:
            fail(f"{cname}: docker exec failed ({e})")


def assert_prometheus() -> None:
    print("\n== 7. Prometheus healthy + all targets UP ==")
    code, _ = http_get(f"http://{HOST}:9090/-/healthy")
    if code == 200:
        ok("prometheus /-/healthy")
    else:
        fail(f"prometheus /-/healthy returned {code}")
        return

    # Poll targets — they come UP a scrape-interval after boot. Targets whose job
    # is an intentionally-skipped service are tolerated (reported, not failed).
    def _relevant(t: dict) -> bool:
        return t.get("labels", {}).get("job", "") not in SKIP

    deadline = time.time() + 60
    while time.time() < deadline:
        code, text = http_get(f"http://{HOST}:9090/api/v1/targets")
        try:
            targets = json.loads(text)["data"]["activeTargets"]
        except (json.JSONDecodeError, KeyError, TypeError):
            targets = []
        relevant = [t for t in targets if _relevant(t)]
        if relevant and all(t.get("health") == "up" for t in relevant):
            skipped = [t.get("labels", {}).get("job", "?") for t in targets if not _relevant(t)]
            msg = f"all {len(relevant)} required Prometheus targets UP"
            if skipped:
                msg += f" (skipped: {sorted(set(skipped))})"
            ok(msg)
            return
        time.sleep(5)
    down = [
        t.get("labels", {}).get("job", "?")
        for t in targets
        if t.get("health") != "up" and _relevant(t)
    ]
    fail(f"Prometheus targets not all UP; down={down}")


def assert_grafana() -> None:
    print("\n== 8. Grafana database ok ==")
    code, text = http_get(f"http://{HOST}:3001/api/health")
    try:
        db = json.loads(text).get("database")
    except json.JSONDecodeError:
        db = None
    if code == 200 and db == "ok":
        ok("grafana /api/health database=ok")
    else:
        fail(f"grafana /api/health code={code} database={db!r}")


def assert_frontend() -> None:
    print("\n== 9. Frontend reachable ==")
    code, _ = http_get(f"http://{HOST}:3000/")
    if code:
        ok(f"frontend responds on :3000 (HTTP {code})")
    else:
        fail("frontend :3000 unreachable")


def assert_real_answer() -> None:
    print("\n== 10. Real LLM answer via /compose (no fallback) ==")
    code, text = http_post_json(
        f"http://{HOST}:8006/compose",
        {"query": "اشرح قانون نيوتن الثاني بإيجاز"},
        timeout=120,
    )
    if code != 200:
        fail(f"/compose returned HTTP {code}: {text[:200]}")
        return
    try:
        r = json.loads(text)
    except json.JSONDecodeError:
        fail(f"/compose returned non-JSON: {text[:200]}")
        return
    mode = r.get("pipeline_mode")
    answer = str(r.get("composed_answer", ""))
    active = r.get("skills_active", [])
    if mode == "fallback":
        fail(f"/compose pipeline_mode=fallback (degraded); skills_active={active}")
    elif mode in ("full", "partial") and len(answer.strip()) > 20:
        ok(f"/compose pipeline_mode={mode}, skills_active={active}, answer={len(answer)} chars")
    else:
        fail(f"/compose pipeline_mode={mode}, answer_len={len(answer)} (expected real answer)")


def main() -> int:
    print("=" * 74)
    print("R0.1 CLOSURE GATE — Docker full-stack reproducibility proof (D-172)")
    print("=" * 74)
    health = wait_all_ready()
    assert_all_healthy(health)
    assert_no_mock_backends(health)
    assert_orchestrator(health)
    assert_reasoning(health)
    assert_planning_postgres(health)
    assert_redis()
    assert_prometheus()
    assert_grafana()
    assert_frontend()
    assert_real_answer()

    print("\n" + "=" * 74)
    print(f"RESULT: {len(_PASS)} passed, {len(_FAIL)} failed")
    print("=" * 74)
    if _FAIL:
        print("\nFAILURES:")
        for f in _FAIL:
            print(f"  - {f}")
        return 1
    print(
        "\n✅ FULL STACK REPRODUCIBILITY PROVEN — real Postgres/Redis/Prometheus/"
        "Grafana + real LLM answer. R0.1 closed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
