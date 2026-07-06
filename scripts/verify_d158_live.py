#!/usr/bin/env python3
"""
D-158 sandbox live-proof of the Cognitive Turn Engine decision logic (ISS-124).

The sandbox blocks pip (no pydantic/fastapi/sqlalchemy) so `orchestrator_client`
cannot be imported wholesale. This harness executes the **actual source** of the
relevant OrchestratorClient methods (line-sliced from the file, indentation
preserved — not a paraphrase) against a faithful BAC-2024 combo, and replays the
exact catastrophe transcript to prove the three symptoms are dead:

  S1  no numerator+denominator dump (one step per turn)
  S2  a correct "14 على 165" is CONFIRMED even after a >600-char prior message
      (the 600-char socratic-dialogue prison is bypassed)
  S3  first "كيف نحسب الحادثة A" yields a diagnostic question, not a dump

Full uvicorn+WS+Supabase E2E runs in Codespaces (see scripts/verify_d158_e2e.py).
"""

from __future__ import annotations

import ast
import contextlib
import logging
import re
import sys
from pathlib import Path
from types import SimpleNamespace

logger = logging.getLogger("d158.harness")

SRC = Path("app/infrastructure/clients/orchestrator_client.py").read_text(encoding="utf-8")
_LINES = SRC.splitlines(keepends=True)

_METHODS = (
    "_norm_for_dedup",
    "_recently_emitted",
    "_fmt_comb",
    "_extract_answer_numbers",
    "_pending_focus_from_history",
    "_verify_numeric_answer",
    "_build_symbolic_reveal",
    "_build_symbolic_step",
    "_build_diagnostic_probe",
    "_cognitive_turn",
)
_CONSTS = ("_KC_PROB_A", "_STEP_QUESTION_MARKERS")


def _slice(node: ast.AST) -> str:
    start = node.lineno
    if getattr(node, "decorator_list", None):
        start = min(d.lineno for d in node.decorator_list)
    return "".join(_LINES[start - 1 : node.end_lineno])


def _build_harness_class() -> type:
    tree = ast.parse(SRC)
    cls_node = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "OrchestratorClient"
    )
    wanted: dict[str, str] = {}
    for n in cls_node.body:
        if isinstance(n, ast.FunctionDef) and n.name in _METHODS:
            wanted[n.name] = _slice(n)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            if n.target.id in _CONSTS:
                wanted[n.target.id] = _slice(n)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id in _CONSTS:
                    wanted[t.id] = _slice(n)
    missing = (set(_METHODS) | set(_CONSTS)) - set(wanted)
    if missing:
        raise SystemExit(f"FATAL: could not extract from source: {sorted(missing)}")
    body = "".join(wanted[name] for name in (*_CONSTS, *_METHODS))
    module_src = "class harness:\n" + body
    ns: dict = {"re": re, "contextlib": contextlib, "logging": logging, "logger": logger}
    exec(compile(module_src, "<d158-harness>", "exec"), ns)
    return ns["harness"]


def _bac2024_combo():
    g = [
        SimpleNamespace(label="كرة حمراء", count=4, is_possible=True, favorable_combinations=4),
        SimpleNamespace(label="كرة خضراء", count=5, is_possible=True, favorable_combinations=10),
        SimpleNamespace(label="كرة بيضاء", count=2, is_possible=False, favorable_combinations=0),
    ]
    return SimpleNamespace(n=11, k=3, total_combinations=165, same_group_favorable=14, groups=g)


def main() -> int:
    harness = _build_harness_class()
    harness._load_canonical_combinations = classmethod(lambda cls, q, h: _bac2024_combo())  # noqa: ARG005

    fails: list[str] = []

    def check(cond: bool, msg: str) -> None:
        print(("✅ " if cond else "❌ ") + msg)
        if not cond:
            fails.append(msg)

    # Persisted state that evolves across turns (mimics tutor_state row + record_turn merge).
    state: dict = {"kc_progress": {}, "turn_count": 0}
    history: list[dict] = []

    def turn(question: str, prior_assistant: str | None = None) -> str:
        if prior_assistant is not None:
            history.append({"role": "assistant", "content": prior_assistant})
        text, delta = harness._cognitive_turn(question, list(history), state, None)
        # mimic customer_chat persistence: merge kc_progress_delta into state, bump turn_count
        merged = dict(state.get("kc_progress") or {})
        for k, v in (delta or {}).items():
            merged[k] = v
        state["kc_progress"] = merged
        state["turn_count"] = int(state.get("turn_count") or 0) + 1
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": text or ""})
        return text or ""

    print("=== D-158 Cognitive Turn Engine — sandbox live replay (BAC-2024) ===\n")

    # ── Turn 1 (S3): first "how do I compute event A" ⇒ diagnostic probe, NOT a dump.
    t1 = turn("كيف نحسب الحادثة A")
    print(f"--- Turn 1 «كيف نحسب الحادثة A» ---\n{t1}\n")
    check("أيّ الألوان يمكن أن تعطينا" in t1, "S3: first help → diagnostic question")
    check("نجمع الحالات الممكنة فقط" not in t1 and "= 14" not in t1, "S3: no numerator dump")
    check("كل الطرق الممكنة" not in t1, "S3: no denominator dump")

    # ── Turn 2 (S1): student names the colours ⇒ ONE step (numerator only, not both).
    t2 = turn("الحمراء و الخضراء فقط")
    print(f"--- Turn 2 «الحمراء و الخضراء فقط» ---\n{t2}\n")
    check("الحالات الملائمة" in t2 and "14" in t2, "S1: numerator step emitted")
    check("كل الطرق الممكنة" not in t2, "S1: denominator NOT dumped in same turn (progressive)")

    # ── Turn 3 (S2): correct final ratio AFTER a >600-char prior message.
    long_dump = "لنُكمل معاً خطوة بخطوة حتى النهاية: " + ("الحالات الملائمة والمقام " * 60)
    assert len(long_dump) > 600
    t3 = turn("14 على 165", prior_assistant=long_dump)
    print(f"--- Turn 3 «14 على 165» (prior msg {len(long_dump)} chars) ---\n{t3}\n")
    check("أحسنت" in t3, "S2: correct ratio CONFIRMED despite >600-char prior (prison bypassed)")
    check("الحادثة B" in t3, "S2: advance to next sub-question")
    check("نجمع الحالات الممكنة فقط" not in t3, "S2: no re-dump of the calculation")

    # ── Cross-turn: no step key delivered twice.
    delivered = list(
        (state["kc_progress"].get(harness._KC_PROB_A) or {}).get("representations_delivered", [])
    )
    print(f"delivered ledger: {delivered}")
    check(len(delivered) == len(set(delivered)), "cross-block: no step emitted twice")

    print("\n" + ("=" * 60))
    if fails:
        print(f"❌ {len(fails)} FAIL(S): {fails}")
        return 1
    print("✅ ALL D-158 sandbox live checks passed (real method source executed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
