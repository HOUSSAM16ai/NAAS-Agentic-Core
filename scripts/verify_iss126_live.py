#!/usr/bin/env python3
"""verify_iss126_live.py — التحقق الحي من إصلاح كارثة تدريس الاحتمالات (D-160).

يستدعي **الكود الحقيقي** (لا stubs): محرّك الدور المعرفي `_cognitive_turn` +
`_detect_step_explanation` + `_build_probability_direct_explanation` مقابل تمرين
BAC-2024 الرسمي (المحرك الرمزي، صفر LLM). يُثبت أن الكارثة (المرّة الـ47) مقتولة:

  «كيف حسبنا 4» ×3 ⇒ يُعلّم اشتقاق الحمراء ثم لا يُكرِّر أبداً (كان يُعيد النصّ نفسه).

يُشغَّل في Codespaces/CI حيث التبعيات متاحة (sandbox يحجب pip/Postgres — نمط §6.55):
    python3 scripts/verify_iss126_live.py

للتحقق الحي الكامل عبر WS + المتصفح + Supabase: بعد `bash .devcontainer/supervisor.sh`،
سجِّل الدخول (houssamannaba963@gmail.com / 1111) وأعد التسلسل في واجهة الدردشة.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-pipeline-secure-length")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("LLM_MOCK_MODE", "1")
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_ROLE_KEY", "dummy")

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f" — {detail}" if detail and not cond else ""))


def _apply(tutor_state: dict, delta: dict | None) -> None:
    kcp = tutor_state.setdefault("kc_progress", {})
    for key, val in (delta or {}).items():
        kcp[key] = val
    tutor_state["turn_count"] = int(tutor_state.get("turn_count") or 0) + 1
    tutor_state.pop("kc_progress_delta", None)


def main() -> None:
    from app.infrastructure.clients.orchestrator_client import (
        OrchestratorClient as TutorClient,
    )

    combo = TutorClient._load_canonical_combinations("اعطني تمرين الاحتمالات 2024", None)
    if combo is None:
        print("❌ canonical BAC-2024 combo unavailable — knowledge_base missing?")
        sys.exit(1)
    print(
        f"combo: n={combo.n} k={combo.k} total={combo.total_combinations} "
        f"same={combo.same_group_favorable}"
    )

    print("\n=== 1) detector (data-driven, marker-gated) ===")
    check(
        "«كيف حسبنا 4» ⇒ red", TutorClient._detect_step_explanation("كيف حسبنا 4", combo) == "red"
    )
    check(
        "«اشرح كيف وصلنا لـ 10» ⇒ green",
        TutorClient._detect_step_explanation("اشرح كيف وصلنا لـ 10", combo) == "green",
    )
    check(
        "«14 على 165» (إجابة، بلا علامة) ⇒ None",
        TutorClient._detect_step_explanation("14 على 165", combo) is None,
    )

    print("\n=== 2) TRANSCRIPT: «كيف حسبنا 4» ×3 (كل الخطوات مُسلَّمة) ===")
    tutor_state = {
        "kc_progress": {
            "prob_event_a": {
                "state": "explained",
                "representations_delivered": ["diagnostic_probe", "numerator", "ratio"],
            }
        },
        "turn_count": 3,
    }
    history = [
        {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
        {"role": "assistant", "content": "كيس فيه 11 كرة (حمراء/خضراء/بيضاء)، نسحب 3 دفعة واحدة."},
        {"role": "assistant", "content": TutorClient._build_symbolic_step(combo, None)},
        {"role": "assistant", "content": TutorClient._build_symbolic_step(combo, "ratio")},
    ]
    outs: list[str] = []
    for i in range(1, 4):
        text, delta = TutorClient._cognitive_turn("كيف حسبنا 4", history, tutor_state, None)
        outs.append(text or "")
        print(f"  Turn {i}: {(text or '')[:70]!r}...")
        if text:
            history.append({"role": "assistant", "content": text})
        _apply(tutor_state, delta)

    non_empty = [o for o in outs if o]
    check("أول ردّ يُعلّم اشتقاق الحمراء", bool(non_empty) and "C_{4}^{3}" in non_empty[0])
    check("صفر تكرار حرفي عبر الأدوار الثلاثة", len(set(non_empty)) == len(non_empty))
    check("لا كشف للنسبة النهائية P(A)", all("14/165" not in o for o in outs))

    print("\n=== 3) F2-قبل-S2: الشرح يهزم تحقّق الإجابة الرقمية ===")
    ts2 = {
        "kc_progress": {
            "prob_event_a": {
                "state": "explained",
                "representations_delivered": ["diagnostic_probe"],
                "_pending": {"kc": "prob_event_a", "focus": "numerator"},
            },
            "_pending": {"kc": "prob_event_a", "focus": "numerator"},
        },
        "turn_count": 2,
    }
    t2, _ = TutorClient._cognitive_turn(
        "اشرح كيف حسبنا 14", [{"role": "user", "content": "احتمالات"}], ts2, None
    )
    check("«اشرح كيف حسبنا 14» يُعلّم (لا «أحسنت»/الحادثة B)", bool(t2) and "أحسنت" not in (t2 or ""))

    ts3 = {
        "kc_progress": {
            "prob_event_a": {
                "state": "explained",
                "representations_delivered": ["diagnostic_probe", "numerator", "ratio"],
                "_pending": {"kc": "prob_event_a", "focus": "ratio"},
            },
            "_pending": {"kc": "prob_event_a", "focus": "ratio"},
        },
        "turn_count": 4,
    }
    t3, _ = TutorClient._cognitive_turn(
        "14 على 165", [{"role": "user", "content": "احتمالات"}], ts3, None
    )
    check(
        "«14 على 165» (بلا علامة) ⇒ S2 اعتراف + الحادثة B", bool(t3) and "الحادثة B" in (t3 or "")
    )

    print(f"\n{'=' * 60}")
    print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
    if FAIL:
        print("❌ FAILURES:", ", ".join(FAIL))
        sys.exit(1)
    print("✅ ALL PASS — ISS-126 catastrophe killed (D-160)")


if __name__ == "__main__":
    main()
