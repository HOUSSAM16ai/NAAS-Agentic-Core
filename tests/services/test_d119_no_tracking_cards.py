"""D-119 — التتبّع المعرفي خلف الكواليس (لا بطاقات تتبّع للطالب).

قرار المالك (transcript حي): بطاقتا «تتبّع المعرفة» (bkt_hint_display) و«ترسيخ
المهارة» (learning_path_card) كانتا تظهران بعد كل دور فتُكرَّران وتُشوّشان. يجب
أن تكونا **خلف الكواليس، لا في سطح الطالب**. سطح الطالب = تعليم نظيف فقط:
نص التمرين → كتلة بصرية واحدة → خطوة تعليمية → جواب.

D-119: `_evaluate_bkt_cards` يُبقي كتابة BKT التحليلية append-only (D-074 — تغذّي
support_level) + اشتقاق المسار (D-111) ويُسجِّلهما (telemetry) ويُرجِع None —
صفر بطاقة طالب. لا إصدار/حفظ بطاقات تتبّع. البطاقات البصرية للاحتمالات تبقى.

stdlib + source-inspection — يعمل في الـ sandbox بلا pydantic/DB.
"""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# D-173 Stage 2: customer_chat.py فُكِّك إلى حزمة customer_chat_support/ — نقرأ المصدر
# **المُركَّب** عبر المانيفست (`_evaluate_bkt_cards` انتقل إلى pedagogy.py).
_spec = _ilu.spec_from_file_location(
    "_cc_sources_d119", REPO_ROOT / "app/api/routers/customer_chat_support/_sources.py"
)
_ccsrc = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_ccsrc)
CHAT_SRC = _ccsrc.read_customer_chat_source()


def _eval_body() -> str:
    seg = CHAT_SRC[CHAT_SRC.index("async def _evaluate_bkt_cards(") :]
    return seg[: seg.index("\n\n\n")] if "\n\n\n" in seg else seg


# ── 1. لا بطاقات تتبّع تُبنى للطالب ────────────────────────────────────────────
class TestNoTrackingCardsBuilt:
    def test_eval_builds_no_student_tracking_cards(self) -> None:
        body = _eval_body()
        assert '"component": "bkt_hint_display"' not in body, (
            "D-119: BKT tracking card must NOT be built — behind-the-scenes only."
        )
        assert '"component": "learning_path_card"' not in body, (
            "D-119: learning-path card must NOT be built — behind-the-scenes only."
        )

    def test_eval_returns_none_not_cards(self) -> None:
        # D-119: التتبّع خلف الكواليس — الدالة لا تُرجِع بطاقات.
        head = CHAT_SRC[CHAT_SRC.index("async def _evaluate_bkt_cards(") :]
        sig = head[: head.index(":\n")]
        assert "-> None" in sig, "D-119: _evaluate_bkt_cards must return None (no cards)."
        assert "return cards" not in _eval_body()


# ── 2. التحليلات + المسار يبقيان خلف الكواليس (لا ZOMBIE) ──────────────────────
class TestBehindTheScenesConsumption:
    def test_bkt_append_only_write_kept(self) -> None:
        body = _eval_body()
        assert "BKTAnalyticsService(" in body and "evaluate_and_record(" in body, (
            "D-074: append-only BKT analytics write must remain (feeds support_level)."
        )

    def test_learning_path_derived_and_logged(self) -> None:
        body = _eval_body()
        assert "get_learning_path_skill()" in body and ".derive(" in body, (
            "D-111: learning path must still be derived (consumed, not ZOMBIE)."
        )
        # مُسجَّل خلف الكواليس (telemetry) — استهلاك حقيقي بلا بطاقة طالب.
        assert "learning_path" in body and "logger.info(" in body

    def test_bkt_mastery_logged_not_carded(self) -> None:
        body = _eval_body()
        assert "bkt_tracking" in body and "behind-the-scenes" in body


# ── 3. لا إصدار بطاقات تتبّع في التنسيق (await فقط لاكتمال التحليلات) ───────────
class TestNoEmissionInOrchestration:
    def test_bkt_task_awaited_for_analytics(self) -> None:
        # ضمان اكتمال الكتابة append-only قبل إنهاء الدور (D-074).
        # D-252: في دورة الدور المفككة التسمية ``await bkt_task``.
        assert "await _bkt_task" in CHAT_SRC or "await bkt_task" in CHAT_SRC

    def test_no_tracking_card_emission_block(self) -> None:
        # D-119: لا كتلة إصدار/حفظ بطاقات تتبّع بعد terminal (حُذفت كتلة D-118).
        anchor = "await _bkt_task" if "await _bkt_task" in CHAT_SRC else "await bkt_task"
        post = CHAT_SRC[CHAT_SRC.index(anchor) :]
        end = post.find("# Close path-aware span")
        block = post[:end] if end > 0 else post
        assert '"type": "ui_component", "payload": _card' not in block, (
            "D-119: tracking cards must NOT be emitted after terminal frame."
        )
        assert "_persist_ui_component_cards(" not in block, (
            "D-119: tracking cards must NOT be persisted."
        )


# ── 4. البطاقات البصرية للاحتمالات تبقى (محتوى تعليمي) ─────────────────────────
class TestVisualCardsPreserved:
    def test_known_components_still_whitelisted(self) -> None:
        # البصريات تبقى في القائمة البيضاء (المحتوى التعليمي الذي يريده المالك).
        # source-inspection (sandbox-safe — لا استيراد pydantic).
        streaming_src = (REPO_ROOT / "app/contracts/streaming.py").read_text(encoding="utf-8")
        for comp in ("full_exercise_story", "combinations_visualizer", "probability_tree"):
            assert f'"{comp}"' in streaming_src, f"visual component dropped: {comp}"
