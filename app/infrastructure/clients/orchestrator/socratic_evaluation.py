"""Socratic-evaluation streaming mixin (D-166 Slice 5 — extracted verbatim from the God-file).

Single responsibility: the active-listening turn (D-130/D-142) — evaluating the student's
free-form answer to a pending Socratic question (symbolic verification first, guarded LLM
evaluator second), acknowledging, and streaming the next graded symbolic step with the
no-repeat alternatives chain.

Mixed into `OrchestratorClient`; every `self._x` resolves through the MRO — behaviour is
byte-identical to the pre-extraction God-file (D-164 pattern: verbatim move, zero rewrite).
"""

from __future__ import annotations

import logging

# نفس اسم الـ logger القديم عمداً — استمرارية السجلات وصفر تغيير رصدي (نمط D-163/D-164).
logger = logging.getLogger("orchestrator-client")


class SocraticEvaluationMixin:
    """Active listening: evaluate the student's answer, acknowledge, advance (D-130/D-142)."""

    async def _stream_socratic_evaluation(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None,
        tutor_state: dict | None = None,
    ):
        """D-130: يُقيّم إجابة الطالب الحرّة ويبثّ المكافأة + التسليم الرمزي المتدرّج.

        understood=true ⇒ تشجيع (LLM محروس) + خطوة رمزية حتمية + سؤال المتابعة.
        understood=false ⇒ اعتراف لطيف + تلميح. **لا إعادة طباعة للتمرين مهما حدث.**

        D-142 Phase 2: ``tutor_state`` (الحالة الدائمة) يُغذّي حارس التكرار بمرساة
        ``last_step_emitted`` (تنجو من نافذة التاريخ)، ويُستشار ``DialogueManagerSkill``
        (خلف العلم ``SEMANTIC_TUTOR_ENABLED``، fail-open) لقرار التقدّم/التصعيد/عدم القفز.
        """
        try:
            from app.services.skills.concept_diagnosis_skill import (
                ConceptDiagnosisInput,
                get_concept_diagnosis_skill,
            )
            from app.services.skills.semantic_property_skill import get_semantic_property_skill
            from app.services.skills.socratic_evaluator_skill import (
                SocraticEvaluatorInput,
                get_socratic_evaluator_skill,
            )
            from app.services.skills.tutor_metrics import (
                record_intervention,
                record_progress,
                record_repetition_avoided,
            )

            combo = self._load_canonical_combinations(question, history_messages)
            if combo is None:
                return  # غير احتمالات ⇒ لا نلتقط (المسار يُكمل)
            # قياس 1 (D-131 §5): التقطنا إجابة الطالب بدل إعادة طباعة التمرين.
            record_repetition_avoided()

            # المفهوم الحالي: من السؤال السقراطي السابق + إجابة الطالب (الطبقة 1، D-127).
            prior_socratic = ""
            for msg in reversed(history_messages or []):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    prior_socratic = str(msg.get("content", ""))[:600]
                    break
            _diag = await get_concept_diagnosis_skill().diagnose(
                ConceptDiagnosisInput(
                    question=f"{prior_socratic} {question}".strip(),
                    history=history_messages,
                )
            )
            concept = _diag.concept if _diag.concept != "unknown" else "event_meaning"

            facts = self._symbolic_facts_brief(combo)
            # ISS-122 (D-155): الحقيقة الرمزية تحكم إجابة الطالب **الرقمية** أولاً —
            # السؤال المعلّق يُشتق من قوالبنا في أحدث رسالة مساعد، والأرقام من
            # combo حصراً. كارثة الترانسكريبت: «هل هي 14 من 165» أُعيد سؤالها.
            _pending = self._pending_focus_from_history(history_messages)
            _numeric = self._verify_numeric_answer(question, combo, _pending)
            # D-142 (1A): السلطة الرمزية — تحقّق صحة الإجابة مقابل المحرك الرمزي (combo).
            _verified = self._verify_answer_against_combo(question, combo) or _numeric is not None

            _mtype = ""
            result = None
            if _numeric == "final_ratio":
                # ISS-122 (D-155): اعتراف صريح + تقدّم للسؤال الفرعي التالي — بلا
                # أرقام (يَنجو من حجب D-113 بنيوياً؛ تأكيد ما ولّده الطالب ليس كشفاً).
                text = (
                    "أحسنت! ✅ إجابتك صحيحة تماماً — ركّبت احتمال الحادثة A بنفسك: "
                    "الحالات الملائمة على كل الحالات الممكنة.\n\n"
                    "ننتقل للسؤال التالي في التمرين — **الحادثة B**: جداء الأرقام "
                    "عدد فردي. قبل أي حساب، سؤال واحد: متى يكون جداء ثلاثة أعداد فردياً؟"
                )
                record_progress("advanced")
            elif _numeric in ("step_correct", "direction"):
                # ISS-122 (D-155): خطوة جزئية صحيحة ⇒ اعتراف + **الخطوة التالية غير
                # المُجابة** (لا إعادة سؤال ما أُجيب، لا reveal superset).
                if _pending == "denominator" or _numeric == "direction":
                    text = self._build_symbolic_step(combo, "ratio", acknowledge=True)
                else:
                    text = (
                        "أحسنت — هذا هو عدد الحالات الملائمة (البسط). "
                        f"والآن: كم عدد **كل** الطرق الممكنة لسحب {combo.k} كرات من {combo.n}؟"
                    )
                record_progress("advanced")
            else:
                result = await get_socratic_evaluator_skill().evaluate(
                    SocraticEvaluatorInput(
                        student_answer=question,
                        concept=concept,
                        facts=facts,
                        history=history_messages,
                        verified_correct=_verified,
                    )
                )

                if result.understood:
                    body = self._build_symbolic_step(combo, result.next_focus, acknowledge=True)
                    # نُسبق التشجيع المُولَّد (إن وُجد ولم يكن مكرّراً للاعتراف القياسي).
                    enc = (result.encouragement or "").strip()
                    text = f"{enc}\n\n{body}" if enc and "الطريق الصحيح" not in enc else body
                    record_progress("advanced")  # قياس 4: تقدّم لخطوة جديدة
                else:
                    # D-131 «شخّص ثم تدخّل»: نشخّص الاعتقاد الخاطئ من رد الطالب ⇒ تدخّل مُوجَّه
                    # (مختلف لكل misconception)، لا تلميح موحَّد. عند الغموض نُصدر probe تشخيصياً.
                    enc = (result.encouragement or "فكرة جيدة — لنقترب أكثر.").strip()
                    _mc = get_semantic_property_skill().diagnose_misconception(
                        concept, question, history_messages
                    )
                    if _mc is not None:
                        _mtype = _mc.mtype
                        record_intervention(_mc.mtype)  # قياس 3: تدخّل مُصنَّف بنوع الاعتقاد
                        record_progress("advanced")
                        text = f"{enc}\n\n{_mc.intervention}"
                    else:
                        _probe = get_semantic_property_skill().first_probe(concept)
                        record_progress("repeated")
                        text = (
                            f"{enc} {_probe}"
                            if _probe
                            else (
                                f"{enc} لاحظ نوع كل كرة: أيّ الألوان يكفي عددها لسحب 3 منها "
                                "معاً؟ ابدأ بعدّ الألوان الممكنة فقط."
                            )
                        )

            # D-142 Phase 2: سلطة قرار الدور (DialogueManager) خلف العلم، fail-open. تُعيد
            # تشكيل القرار بإشارات حيّة (دليل + قدرة BKT + ميزانية المفهوم الدائمة + منع تكرار).
            _dm_reason = ""
            _ts = tutor_state if isinstance(tutor_state, dict) else {}
            _last_step = str(_ts.get("last_step_emitted") or "")
            # ISS-148: دفتر ما سُلِّم للطالب — يُمرَّر لكل تفريغ رمزي في هذه الدالّة.
            from app.services.skills.kc_progress_schema import delivered_steps

            _delivered = delivered_steps(_ts)
            # ISS-122 (D-155): الحكم الرقمي الحتمي نهائي — لا يُعاد تشكيله بالـ DM.
            if self._semantic_tutor_enabled() and _numeric is None and result is not None:
                _dm = self._dialogue_decision(
                    question=question,
                    concept=concept,
                    verified_correct=_verified,
                    understood=result.understood,
                    tutor_state=_ts,
                    candidate_text=text,
                )
                if _dm is not None:
                    _dm_reason = _dm.reason
                    _action = _dm.action
                    if _action == "acknowledge_advance":
                        text = self._build_symbolic_step(combo, _dm.focus, acknowledge=True)
                    elif _action == "intermediate_scaffold":
                        text = self._build_symbolic_step(combo, "numerator", acknowledge=True)
                    elif _action == "symbolic_reveal":
                        _rv = self._build_symbolic_reveal(
                            question, history_messages, acknowledge=True, delivered=_delivered
                        )
                        if _rv:
                            text = _rv
                    record_progress("advanced")

            # D-142 (1B) + ISS-121 (D-154): «ممنوع بثّ مكرَّر» بنيوياً — التطبيع صار
            # محايداً للحجب (أرقام/«؟» ⇒ #) فلا يَعمى عن النسخة المحفوظة المحجوبة؛
            # وعند التكرار نجرّب سلسلة بدائل بالترتيب (إنقاذ ⇒ خطوات السُّلّم بؤرةً
            # بؤرة ⇒ مُوجّه توليد قصير) ونبثّ **أول غير مكرَّر** — كل دور يقدّم جديداً.
            def _is_dup(t: str) -> bool:
                return self._recently_emitted(t, history_messages) or (
                    _last_step and self._near_dup(t, _last_step)
                )

            if _is_dup(text):
                # ISS-122 (D-155): «الخطوة التالية غير المُجابة» أولاً (من السؤال
                # المعلّق)، والإنقاذ الكامل (reveal superset) **أخيراً** — كان أول
                # البدائل فيعيد طباعة المعروض (تكرار مُقنَّع، الدور 4 في الترانسكريبت).
                _first, _second = (
                    ("ratio", "numerator") if _pending == "denominator" else ("numerator", "ratio")
                )
                _alternatives = (
                    self._build_symbolic_step(combo, _first, acknowledge=True),
                    self._build_symbolic_step(combo, _second, acknowledge=True),
                    "أنت تملك الآن كل المعطيات — جرّب بنفسك: ركّب البسط على المقام، "
                    "وأخبرني ما قيمة P(A) التي حصلت عليها، وسأخبرك إن أصبت.",
                    self._build_symbolic_reveal(
                        question, history_messages, acknowledge=True, delivered=_delivered
                    ),
                )
                for _cand in _alternatives:
                    if _cand and not _is_dup(_cand):
                        text = _cand
                        record_progress("advanced")
                        break

            logger.info(
                "socratic_evaluation",
                extra={
                    "concept": concept,
                    "understood": bool(_numeric) or bool(result and result.understood),
                    "source": (result.source if result else f"numeric:{_numeric}"),
                    "next_focus": (result.next_focus or "") if result else "",
                    "misconception_mtype": _mtype,
                    "verified_correct": _verified,
                    "numeric_verdict": _numeric or "",
                    "pending_focus": _pending or "",
                    "dialogue_manager_reason": _dm_reason,
                },
            )

            async for chunk in self._stream_markdown_typing(text):
                yield chunk
        except Exception:
            logger.warning("_stream_socratic_evaluation_failed", exc_info=True)
            return
