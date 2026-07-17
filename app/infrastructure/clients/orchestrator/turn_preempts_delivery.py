"""D-170 Stage A3: مرحلتا التسليم — الواجهة المحسوبة والشرح بسياق التمرين.

`_stage_calculated_ui` يبثّ مكوّن الواجهة ويقرّر MODE_A/MODE_B (V38.0)؛
`_stage_explanation_context` يحسم الشرح بسياق (D-052) ويحقن محتوى التمرين
نحو الـ orchestrator (D-103) أو يبثّ الشرح المحلي (رافعة الرجوع)."""

from __future__ import annotations

import contextlib
import logging
import time
import uuid
from collections.abc import AsyncGenerator

from app.infrastructure.clients.orchestrator.turn_context import TurnContext
from app.services.capabilities.exercise_retrieval import (
    ExerciseRetrievalRequest,
    detect_explanation_with_context,
)

# نفس اسم الـ logger القديم عمداً — استمرارية السجلات (نمط D-163/D-164).
logger = logging.getLogger("orchestrator-client")


class TurnPreemptsDeliveryMixin:
    """مرحلتا التسليم: الواجهة المحسوبة (MODE_A/B) والشرح بسياق التمرين."""

    async def _stage_calculated_ui(self, ctx: TurnContext) -> AsyncGenerator[dict | str, None]:
        """الواجهة المحسوبة + توجيه MODE_A/MODE_B (V38.0/D-085/D-116)."""
        question = ctx.question
        history_messages = ctx.history_messages
        obs = ctx.obs
        _root_ctx = ctx.root_ctx
        _t0 = ctx.t0
        # ─────────────────────────────────────────────────────────────────────
        # Generative UI Streaming (probability tree / impossible_case):
        # عند طلب يتضمن شجرة احتمالات، نبثّ حدث ui_component فوراً (incremental).
        #
        # V28.0 — قانون الكبح النصي (Text-Wall Muzzle):
        # إذا كان المكوّن impossible_draw_animation (terminate_pipeline=True)،
        # نبثّ المكوّن + companion_text (جملة واحدة ≤ 120 حرف) ثم نُنهي المسار
        # فوراً — لا LLM، لا شجرة، لا synthesizer، لا جدار نص.
        # للمكوّنات الأخرى (probability_tree / combinations_visualizer): نسقط
        # للمسار النصي العادي كما كان (لا return).
        # ─────────────────────────────────────────────────────────────────────
        # D-078 (V19.0 → V28.0): الموجِّه التربوي يختار المكوّن الصحيح.
        # كاشف الإحباط (مفهمتش/كيفاش) يُفعِّل الأداة بصرياً عبر سياق المحادثة.
        # V38.0: hoisted so the fallback chain can read the routing decision
        # even when _ui_event is None (no probability context detected).
        _is_mode_b: bool = False

        try:
            _ui_event = self._build_calculated_ui(question, history_messages=history_messages)
        except Exception:
            _ui_event = None

        if _ui_event is not None:
            # ─────────────────────────────────────────────────────────────────
            # Protocol V38.0 — Dual-Mode Routing (replaces V34.0 Contextual Unmuzzle)
            # ─────────────────────────────────────────────────────────────────
            # _build_calculated_ui already encoded the routing decision:
            #   MODE_A → terminate_pipeline=True  (direct question, muzzle after UI)
            #   MODE_B → terminate_pipeline=False (confusion, keep pipeline alive)
            #
            # We read the decision directly from the event — no second confusion
            # check needed here. This keeps the routing logic in one place.
            _routing_mode = _ui_event.get("routing_mode", "MODE_A")
            _is_mode_b = _routing_mode == "MODE_B"  # hoisted — readable by fallback chain
            # terminate_pipeline is already False for MODE_B (set in _build_calculated_ui)
            _is_impossible = _ui_event.get("terminate_pipeline") is True

            logger.info(
                "generative_ui_emit",
                extra={
                    "request_id": str(uuid.uuid4()),
                    "component": _ui_event.get("component"),
                    "routing_mode": _routing_mode,
                    "terminate_pipeline": _is_impossible,
                    "question_len": len(question),
                },
            )
            yield self._normalize_stream_event({"type": "ui_component", "payload": _ui_event})

            # MODE_A — Text-Wall Muzzle: terminate immediately after UI component.
            # Emit companion_text (≤ 120 chars) as the sole text output, then return.
            # MODE_B falls through to the LLM path below for deep pedagogical narrative.
            if _is_impossible:
                _companion = str(
                    _ui_event.get("companion_text")
                    or "إليك تفصيل التمرين في واجهتك التفاعلية الخيالية أدناه 🪄"
                )
                yield self._normalize_stream_event(
                    {"type": "assistant_delta", "payload": {"content": _companion}}
                )
                yield self._normalize_stream_event(
                    {"type": "assistant_final", "payload": {"content": ""}}
                )
                if _root_ctx:
                    with contextlib.suppress(Exception):
                        obs.end_span(
                            _root_ctx.span_id,
                            status="OK",
                            metrics={
                                "duration_ms": (time.perf_counter() - _t0) * 1000,
                                "fallback_path": 0.1,
                                "stream_chars": float(len(_companion)),
                            },
                        )
                ctx.turn_complete = True
                return
            # MODE_B: UI emitted, pipeline continues — LLM will provide deep narrative.
            if _is_mode_b:
                logger.info(
                    "deep_pedagogy_mode_active",
                    extra={"component": _ui_event.get("component"), "question_len": len(question)},
                )
        ctx.is_mode_b = _is_mode_b

    async def _stage_explanation_context(
        self, ctx: TurnContext
    ) -> AsyncGenerator[dict | str, None]:
        """الشرح بسياق التمرين (D-052/D-103) — حقن المحتوى نحو الـ orchestrator أو البثّ المحلي."""
        question = ctx.question
        history_messages = ctx.history_messages
        conversation_id = ctx.conversation_id
        obs = ctx.obs
        _root_ctx = ctx.root_ctx
        _t0 = ctx.t0
        # ─────────────────────────────────────────────────────────────────────
        # ISS-058 (D-052 — Explanation-with-Context):
        # عند طلب شرح/استفسار مرتبط بتمرين بكالوريا (صريحاً أو ضمن السياق).
        #
        # ISS-059 (D-053): نحسب القرار **مرة واحدة** ونمرِّره للـ stream
        # بدل إعادة حسابه — يوفِّر ~10-20ms + file I/O مكرَّر.
        #
        # D-103: افتراضياً نمرّر الشرح عبر orchestrator (الرسم الـ13-node) مع
        # **حقن** محتوى التمرين الدقيق في context — الرسم يتجاوز retriever-ه
        # كلياً ويستخدم المحقون كمصدر وحيد، فيُحيَّد سبب منع D-052 الأصلي
        # (خلط تمارين vector DB + tags خام) بالبناء. الشرح المحلي يبقى fallback
        # كاملاً. رافعة رجوع فورية: EXPLANATION_VIA_ORCHESTRATOR=0.
        # ─────────────────────────────────────────────────────────────────────
        _explanation_decision = detect_explanation_with_context(
            ExerciseRetrievalRequest(question=question),
            history_messages=history_messages,
        )
        _exercise_injection: dict[str, str] = {}
        if _explanation_decision.recognized and _explanation_decision.matched_entry is not None:
            logger.info(
                "explanation_context_preempt reason=%s matched_file=%s history_len=%s",
                _explanation_decision.reason,
                _explanation_decision.matched_entry.file_path,
                len(history_messages or []),
                extra={
                    "request_id": str(uuid.uuid4()),
                    "reason": _explanation_decision.reason,
                    "matched_file": _explanation_decision.matched_entry.file_path,
                },
            )
            _exp_full_content = str(getattr(_explanation_decision, "full_content", "") or "")
            if self._explanation_via_orchestrator_enabled() and _exp_full_content.strip():
                # D-103: حقن المحتوى والمتابعة إلى orchestrator — لا بثّ محلي هنا.
                _exercise_injection = {
                    "exercise_content": _exp_full_content,
                    "exercise_ref": str(_explanation_decision.matched_entry.file_path),
                }
                logger.info(
                    "explanation_via_orchestrator file=%s chars=%s",
                    _explanation_decision.matched_entry.file_path,
                    len(_exp_full_content),
                )
            else:
                exp_streamed_chars = 0
                try:
                    async for chunk in self._stream_exercise_explanation_response(
                        question=question,
                        conversation_id=conversation_id,
                        history_messages=history_messages,
                        precomputed_decision=_explanation_decision,  # ISS-059
                    ):
                        if not chunk:
                            continue
                        exp_streamed_chars += len(chunk)
                        yield self._normalize_stream_event(
                            {"type": "assistant_delta", "payload": {"content": chunk}}
                        )
                except Exception:
                    logger.warning("explanation_context_preempt_failed", exc_info=True)

                if exp_streamed_chars > 0:
                    if _root_ctx:
                        with contextlib.suppress(Exception):
                            obs.end_span(
                                _root_ctx.span_id,
                                status="OK",
                                metrics={
                                    "duration_ms": (time.perf_counter() - _t0) * 1000,
                                    "fallback_path": 0.75,  # explanation preempt
                                    "stream_chars": float(exp_streamed_chars),
                                },
                            )
                    yield self._normalize_stream_event(
                        {"type": "assistant_final", "payload": {"content": ""}}
                    )
                    ctx.turn_complete = True
                    return
                # إذا فشل البث → نُكمل المسار العادي
        ctx.explanation_decision = _explanation_decision
        ctx.exercise_injection = _exercise_injection
