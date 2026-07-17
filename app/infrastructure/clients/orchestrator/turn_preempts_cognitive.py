"""D-170 Stage A2: مخرج الطوارئ الحتمي + المحركات المعرفية (الطبقات 1-5).

تشخيص المفهوم (D-127) + حالة الطالب (D-133) + محرّك حالة الفهم (D-135/D-159)
+ السياسة التربوية (D-129) + السرد السقراطي (D-128) + سلاسل «ممنوع مكرَّر»
(D-153/D-154/D-155). كتلة واحدة متماسكة منقولة حرفياً من `chat_with_agent`."""

from __future__ import annotations

import contextlib
import logging
import time
import uuid
from collections.abc import AsyncGenerator

from app.infrastructure.clients.orchestrator.turn_context import TurnContext

# نفس اسم الـ logger القديم عمداً — استمرارية السجلات (نمط D-163/D-164).
logger = logging.getLogger("orchestrator-client")


class TurnPreemptsCognitiveMixin:
    """مخرج الطوارئ الحتمي والمحركات المعرفية — أكبر مرحلة في الدور."""

    async def _stage_escape_hatch(self, ctx: TurnContext) -> AsyncGenerator[dict | str, None]:
        """مخرج الطوارئ + المحركات المعرفية (D-124→D-135/D-155/D-160) — طبقات العصبي-الرمزي."""
        question = ctx.question
        history_messages = ctx.history_messages
        context = ctx.context
        obs = ctx.obs
        _root_ctx = ctx.root_ctx
        _t0 = ctx.t0
        tutor_state = ctx.tutor_state
        # ─────────────────────────────────────────────────────────────────────
        # D-124 — مخرج الطوارئ الحتمي (Deterministic Escape Hatch):
        # كسر «حلقة الموت اللانهائية» في تمرين الاحتمالات. بعد D-116/D-123 صار كل
        # سؤال احتمالات يُنهي دائماً إلى الكاروسيل (صفر LLM) ⇒ سؤال محدّد («كيف
        # وجدنا 4 الحمراء؟») أو حيرة متكررة («لم أفهم»×N) يُعيدان طباعة نفس
        # الكاروسيل بلا تقدّم. الحل (تشخيص المالك): سؤال محدّد (فوراً) أو عداد
        # الحيرة ≥ 2 ⇒ شرح رياضي **مباشر حتمي** (من التمرين الرسمي، history=None،
        # صفر LLM) يكسر حلقة الكاروسيل. يقع **قبل** _build_calculated_ui. topic-safe:
        # _build_probability_direct_explanation يُرجِع None لغير الاحتمالات.
        # ─────────────────────────────────────────────────────────────────────
        # D-127 — المعمارية الإدراكية العصبية-الرمزية (الطبقة 1: فهم → مفهوم):
        # نُشخّص المفهوم (حتمي أولاً، LLM محروس عند unknown في سياق احتمالات فقط)،
        # ثم نبني استجابة مدفوعة بالمفهوم + تصعيد سقراطي مضاد للتكرار (الطبقة 4).
        # كل صياغات «البسط/14» → numerator → تعريف؛ نفس المفهوم مرّتين → سؤال سقراطي.
        # D-125: المفاهيمي/المقارنة لا يزال مدعوماً عبر concept=ratio.
        _conceptual = self._detect_conceptual_question(question)
        _subpart = self._detect_subpart_question(question)
        _confusion_count = self._count_probability_confusion(question, history_messages)

        from app.services.skills.concept_diagnosis_skill import ConceptDiagnosisSkill

        _det = ConceptDiagnosisSkill.diagnose_deterministic(question)
        _concept = _det.concept
        _misconception = _det.misconception
        # ISS-131 (D-169 — قاعدة D-102): رسائل system لا تدخل كواشف الـ history —
        # برومبت النظام (خصوصاً برومبت الإدمن الذي يحوي «كرة/احتمال») كان يُفعِّل
        # «سياق الاحتمالات» زوراً لكل سؤال. الكاشف يقرأ رسائل الطالب/المساعد حصراً.
        _history_text = " ".join(
            str(m.get("content", ""))
            for m in (history_messages or [])
            if isinstance(m, dict) and m.get("role") in ("user", "assistant")
        )
        # الطبقة 1 LLM فقط عند unknown + سياق احتمالات (لا هدر على غير الاحتمالات).
        if _concept == "unknown" and self._is_prob_context(question + " " + _history_text):
            with contextlib.suppress(Exception):
                from app.services.skills.concept_diagnosis_skill import (
                    ConceptDiagnosisInput,
                    get_concept_diagnosis_skill,
                )

                _diag = await get_concept_diagnosis_skill().diagnose(
                    ConceptDiagnosisInput(question=question, history=history_messages)
                )
                _concept = _diag.concept
                _misconception = _diag.misconception
        # حيرة عامة بلا مفهوم محدّد ⇒ full_solution (مع تصعيد سقراطي عند التكرار).
        if _concept == "unknown" and _confusion_count >= 2:
            _concept, _misconception = "full_solution", "none"

        # D-133: حالة الطالب (نيّة + إحباط) — إشارة قرار تُغيّر نوع الرد + ميزانية السقراطية.
        # حتمي أولاً (رخيص)؛ LLM ثانوي **فقط** عند primary=unknown + سياق احتمالات (نقد المالك 2،
        # لا هدر LLM على غير الاحتمالات — يُحاكي بوّابة concept_diagnosis).
        from app.services.skills.student_state_skill import (
            StudentStateInput,
            get_student_state_skill,
        )

        _state = get_student_state_skill().read(
            StudentStateInput(question=question, history=history_messages)
        )
        if _state.primary_intent == "unknown" and self._is_prob_context(
            question + " " + _history_text
        ):
            with contextlib.suppress(Exception):
                _state = await get_student_state_skill().read_or_classify(
                    StudentStateInput(question=question, history=history_messages)
                )
        try:  # BKT/الإتقان هي السلطة (نقد 2): support_level من context (D-104/D-126).
            _sup_level = int((context or {}).get("support_level") or 5)
        except (TypeError, ValueError):
            _sup_level = 5

        # ISS-122 (D-155): أول طلب مساعدة عام («كيف افهم للتمرين»/«من أين أبدأ»)
        # في سياق احتمالات وقبل أي خطوة تدريس ⇒ probe تشخيصي حتمي (كان يسقط
        # للـ LLM fallback العام فيُنتج جملة عامة بلا تشخيص).
        _first_help = (
            self._is_first_help_request(question)
            and self._is_prob_context(question + " " + _history_text)
            and not self._has_prior_tutoring_step(history_messages)
        )

        if (
            _concept != "unknown"
            or _conceptual
            or _subpart is not None
            or _confusion_count >= 2
            or _state.primary_intent in ("example_request", "procedure")
            or _first_help
            # D-135: إجابة قصيرة وسط حوار تمرين ⇒ ادخل ليُقيّمها محرّك حالة الفهم (اعتراف+تقدّم).
            or self._is_short_answer_in_dialogue(question, history_messages)
        ):
            # D-127: الاستجابة المدفوعة بالمفهوم أولاً؛ fallback إلى منطق D-124/D-125.
            _direct = None
            # ISS-122 (D-155): سؤال مفاهيمي («العلاقة/لماذا/الفرق») ⇒ شرح العلاقة
            # (D-125) مباشرةً — لا يعالجه محرّك حالة الفهم ولا السياسة (كانا
            # يختطفانه لتمثيل مكرَّر). قاعدة D-125: الفحص المفاهيمي يسبق كل شيء.
            if _conceptual:
                _direct = self._build_probability_direct_explanation(question, history_messages)
            # ISS-122 (D-155): «التشخيص قبل الشرح» — أول طلب مساعدة ⇒ سؤال تشخيصي
            # واحد بلا أي قيم محسوبة، ثم ننتظر محاولة الطالب.
            if _direct is None and _first_help:
                with contextlib.suppress(Exception):
                    _fh_combo = self._load_canonical_combinations(question, history_messages)
                    if _fh_combo is not None:
                        _direct = self._build_diagnostic_probe(_fh_combo)
                        from app.services.skills.tutor_metrics import record_response_mode

                        record_response_mode("diagnostic_probe")
            # D-135: محرّك حالة الفهم (Learning State) — الأولوية: يُجيب الفجوة المعرفية المحدّدة،
            # يتقدّم على برهان الفهم، ويُصعّد التمثيل استباقياً (لا تكرار دلالي). الأرقام من المحرك
            # الرمزي (combo)، صفر LLM. يحلّ الكارثة: «كيف وصلنا ل 10»⇒kc_combination، «لماذا قسمنا
            # على 3!»⇒kc_factorial (بلا رقم)، «لم أفهم»×2⇒تمثيل مختلف لا تكرار، إجابة⇒اعتراف+تقدّم.
            # ISS-122 (D-155): مُقيَّد بـ `_direct is None` — المفاهيمي/probe التشخيص لهما الأولوية.
            with contextlib.suppress(Exception):
                _us_combo = (
                    self._load_canonical_combinations(question, history_messages)
                    if _direct is None
                    else None
                )
                if _us_combo is not None:
                    from app.services.skills.tutor_metrics import (
                        record_progress,
                        record_understanding,
                    )
                    from app.services.skills.understanding_state_skill import (
                        get_understanding_state_skill,
                    )

                    # D-159 (WP-C): الحالة الدائمة (tutor_state.kc_progress) هي سلطة حالة
                    # المكوّنات — تقاعد إعادة البناء من مسح النصّ (يبقى fallback).
                    _us_kcp = (
                        tutor_state.get("kc_progress") if isinstance(tutor_state, dict) else None
                    )
                    _us_kcp = _us_kcp if isinstance(_us_kcp, dict) else {}
                    _us = get_understanding_state_skill().decide(
                        question=question,
                        history=history_messages,
                        combo=_us_combo,
                        intent=_state.primary_intent,
                        frustration=_state.frustration,
                        kc_progress=_us_kcp,
                    )
                    if _us is not None and _us.text:
                        _direct = _us.text
                        record_understanding(_us.kc_id, _us.action)
                        record_progress(
                            "advanced"
                            if _us.action in ("advance", "mastered")
                            else ("re_represented" if _us.action == "re_represent" else "explained")
                        )
                        logger.info(
                            "understanding_state",
                            extra={
                                "kc": _us.kc_id,
                                "action": _us.action,
                                "representation_level": _us.representation_level,
                            },
                        )
                        # D-159 (WP-C): كتابة قرار المحرّك في الحالة الدائمة — المكوّن
                        # المُبرهَن يصير understood والمشروح explained (دلتا kc_progress
                        # يحفظها customer_chat عبر record_turn). fail-open مطلق.
                        with contextlib.suppress(Exception):
                            from app.services.skills.kc_progress_schema import parse_kc_entry

                            _us_delta = (
                                tutor_state.setdefault("kc_progress_delta", {})
                                if isinstance(tutor_state, dict)
                                else {}
                            )
                            if isinstance(_us_delta, dict):
                                if _us.understood_kc_id:
                                    _u_entry = parse_kc_entry(_us_kcp.get(_us.understood_kc_id))
                                    _u_entry.state = "understood"
                                    _u_entry.evidence = "verified"
                                    _u_entry.attempts += 1
                                    _us_delta[_us.understood_kc_id] = _u_entry.to_dict()
                                if _us.kc_id and _us.kc_id != _us.understood_kc_id:
                                    _t_entry = parse_kc_entry(_us_kcp.get(_us.kc_id))
                                    if _t_entry.state == "not_addressed":
                                        _t_entry.state = "explained"
                                    _t_entry.attempts += 1
                                    _t_entry.mark_delivered(f"rep{_us.representation_level}")
                                    _us_delta[_us.kc_id] = _t_entry.to_dict()
            # D-133: النيّة تُحدّد نوع الرد قبل السياسة (إشارة قرار، لا تصنيف):
            #   example_request ⇒ مثال قبل النظرية؛ procedure ⇒ خطوات رمزية متدرّجة.
            if _direct is None and _state.primary_intent in ("example_request", "procedure"):
                from app.services.skills.tutor_metrics import record_response_mode

                if _state.primary_intent == "example_request":
                    _direct = self._build_concrete_example(question, history_messages)
                    if _direct:
                        record_response_mode("example_first")
                else:  # procedure — ISS-121 (D-154): سُلّم لا تفريغ
                    # «كيف» تدخل السُّلّم من خطوة البسط **المنتهية بسؤال** («كم عدد
                    # كل الطرق؟») — التفريغ الكامل (`_build_symbolic_reveal`) محجوز
                    # حصراً لإنقاذ استنفاد الميزانية (D-129). القانون الرابع:
                    # «التلميح قبل الحل» + مقياس roadmap §7 (صفر كشف للنتيجة).
                    _proc_combo = self._load_canonical_combinations(question, history_messages)
                    if _proc_combo is not None:
                        # ISS-122 (D-155): «التشخيص قبل الشرح» — أول طلب إجراء في
                        # التمرين يتلقى probe تشخيصياً واحداً (صفر قيم محسوبة) ثم
                        # ننتظر محاولة الطالب؛ الخطوة المحسوبة بعد أول تفاعل فقط.
                        if not self._has_prior_tutoring_step(history_messages):
                            _direct = self._build_diagnostic_probe(_proc_combo)
                            record_response_mode("diagnostic_probe")
                        else:
                            _direct = self._build_symbolic_step(_proc_combo, None)
                            record_response_mode("steps")
            if _direct is None and _concept != "unknown":
                # D-129: محرّك السياسة التربوية (الطبقة 4) يقرّر التدخّل: تعريف →
                # سؤال سقراطي محدود → اعتراف + تقدّم → حلّ رمزي عند نفاد الميزانية.
                # يكسر الاستجواب اللانهائي ويعترف بإجابات الطالب.
                from app.services.skills.pedagogical_policy_skill import (
                    PolicyInput,
                    get_pedagogical_policy_skill,
                )

                _policy = get_pedagogical_policy_skill().decide(
                    PolicyInput(
                        concept=_concept,
                        misconception=_misconception,
                        question=question,
                        history=history_messages,
                        # D-133: إشارة القرار — النيّة + الإحباط + الإتقان (BKT) تُغيّر التدخّل.
                        intent=_state.primary_intent,
                        frustration=_state.frustration,
                        support_level=_sup_level,
                    )
                )
                _ack = "إجابتك في الطريق الصحيح — " if _policy.acknowledge else ""
                if _policy.action == "symbolic_reveal":
                    # D-129: الإنقاذ التربوي الحتمي بعد استنفاد السقراطية.
                    _direct = self._build_symbolic_reveal(
                        question, history_messages, acknowledge=_policy.acknowledge
                    )
                elif _policy.action == "socratic":
                    # D-128: سرد سقراطي مُولَّد فريد (محروس)؛ اعتراف بإجابة الطالب.
                    with contextlib.suppress(Exception):
                        _narr = await self._generate_socratic_narrative(
                            _concept, _misconception, question, history_messages
                        )
                        if _narr:
                            _direct = (_ack + _narr) if _ack else _narr
                    if not _direct:  # fallback: قالب حتمي
                        _det = self._build_cognitive_response(
                            _concept, _misconception, question, history_messages
                        )
                        if _det:
                            _direct = (_ack + _det) if _ack else _det
                else:  # definition
                    _direct = self._build_cognitive_response(
                        _concept, _misconception, question, history_messages
                    )
                logger.info(
                    "pedagogical_policy",
                    extra={
                        "concept": _concept,
                        "action": _policy.action,
                        "acknowledge": _policy.acknowledge,
                        "socratic_count": _policy.socratic_count,
                        # D-133: إشارة القرار — يُثبت أن النيّة/الإحباط غيّرا البيداغوجيا.
                        "intent": _state.primary_intent,
                        "frustration": _state.frustration,
                        "response_mode": _policy.response_mode,
                    },
                )
            # F4 (D-160/ISS-126): نفس نيّة «اشرح اشتقاق هذه القيمة» في الكتلة القديمة
            # (defense-in-depth: لو عمل هذا المسار — cognitive_turn مُعطَّل أو أرجع None —
            # يظلّ «كيف حسبنا 4» يُعلّم اشتقاق الحمراء بدل الاشتقاق الكامل العام).
            if not _direct:
                with contextlib.suppress(Exception):
                    _sc_combo = self._load_canonical_combinations(question, history_messages)
                    _sc_part = (
                        self._detect_step_explanation(question, _sc_combo)
                        if _sc_combo is not None
                        else None
                    )
                    if _sc_part is not None:
                        _direct = self._build_probability_direct_explanation(
                            question, history_messages, forced_subpart=_sc_part
                        )
            if not _direct:
                _direct = self._build_probability_direct_explanation(question, history_messages)
            # ISS-120 (D-153): حارس التكرار على مسار محرّك حالة الفهم — كان هذا
            # المسار يتجاوز `_recently_emitted` و`last_step_emitted` فيبثّ نفس
            # التمثيل («تخيّل أنك سحبت 3 كرات…») حرفياً كل دور («لم أفهم»×2 ⇒
            # نفس النص). عند التكرار ⇒ تصعيد للحلّ الرمزي المتدرّج؛ وإن كان هو
            # الآخر مكرَّراً ⇒ إسقاط النص فيتولّى الكاروسيل/المسار التالي.
            if _direct:
                with contextlib.suppress(Exception):
                    _d153_ts = (
                        (context or {}).get("tutor_state") if isinstance(context, dict) else None
                    )
                    _d153_last = (
                        str(_d153_ts.get("last_step_emitted") or "")
                        if isinstance(_d153_ts, dict)
                        else ""
                    )

                    def _d153_dup(t: str) -> bool:
                        return self._recently_emitted(t, history_messages) or (
                            _d153_last and self._near_dup(t, _d153_last)
                        )

                    if _d153_dup(_direct):
                        # ISS-121 (D-154): سلسلة بدائل — أول غير مكرَّر يُبثّ؛ وإلا
                        # يسقط النص فيتولّى الكاروسيل/المسار التالي. صفر بثّ مكرَّر.
                        # ISS-122 (D-155): «الخطوة التالية غير المُجابة» أولاً (من
                        # السؤال المعلّق) والإنقاذ الكامل (reveal superset) أخيراً.
                        _lad_combo = self._load_canonical_combinations(question, history_messages)
                        _lad_pending = self._pending_focus_from_history(history_messages)
                        _lf, _ls = (
                            ("ratio", "numerator")
                            if _lad_pending == "denominator"
                            else ("numerator", "ratio")
                        )
                        _alts: tuple[str | None, ...] = (
                            (
                                self._build_symbolic_step(_lad_combo, _lf)
                                if _lad_combo is not None
                                else None
                            ),
                            (
                                self._build_symbolic_step(_lad_combo, _ls)
                                if _lad_combo is not None
                                else None
                            ),
                            "أنت تملك الآن كل المعطيات — جرّب بنفسك: ركّب البسط على "
                            "المقام، وأخبرني ما قيمة P(A) التي حصلت عليها، وسأخبرك إن أصبت.",
                            self._build_symbolic_reveal(question, history_messages),
                        )
                        _direct = None
                        for _cand in _alts:
                            if _cand and not _d153_dup(_cand):
                                _direct = _cand
                                break
            if _direct:
                logger.info(
                    "probability_direct_explanation_escape_hatch",
                    extra={
                        "request_id": str(uuid.uuid4()),
                        "concept": _concept,
                        "misconception": _misconception,
                        "subpart": _subpart or "",
                        "confusion_count": _confusion_count,
                        "reason": (
                            f"concept:{_concept}"
                            if _concept != "unknown"
                            else (
                                "conceptual_question"
                                if _conceptual
                                else ("subpart_question" if _subpart else "repeated_confusion")
                            )
                        ),
                    },
                )
                _direct_chars = 0
                try:
                    async for _chunk in self._stream_markdown_typing(_direct):
                        if not _chunk:
                            continue
                        _direct_chars += len(_chunk)
                        yield self._normalize_stream_event(
                            {"type": "assistant_delta", "payload": {"content": _chunk}}
                        )
                except Exception:
                    logger.warning("probability_direct_explanation_stream_failed", exc_info=True)
                if _direct_chars > 0:
                    if _root_ctx:
                        with contextlib.suppress(Exception):
                            obs.end_span(
                                _root_ctx.span_id,
                                status="OK",
                                metrics={
                                    "duration_ms": (time.perf_counter() - _t0) * 1000,
                                    # بين preempt (0.5) والكاروسيل المحسوب
                                    "fallback_path": 0.45,
                                    "stream_chars": float(_direct_chars),
                                },
                            )
                    yield self._normalize_stream_event(
                        {"type": "assistant_final", "payload": {"content": ""}}
                    )
                    ctx.turn_complete = True
                    return
                # إن فشل البث (نادر) → نُكمل إلى الكاروسيل العادي أدناه
