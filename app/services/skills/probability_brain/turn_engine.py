"""D-158/D-159 — محرّك الدور المعرفي متعدد العُقد (_cognitive_turn + event_b + parity loader) — مستخرَج حرفياً من `probability_tutor_brain.py` (D-168).

جزء من تركيبة `ProbabilityTutorBrain` (mixin) — كل `cls._x` تُحل عبر الـ MRO المُركَّب.
**ممنوع** الاستيراد من `microservices/` هنا؛ والأرقام من المحرك الرمزي حصراً.
"""

from __future__ import annotations

import contextlib
import logging

# نفس اسم الـ logger القديم عمداً — استمرارية السجلات وصفر تغيير رصدي (D-163/D-168).
logger = logging.getLogger("orchestrator-client")


class CognitiveTurnEngineMixin:
    #: ISS-149 — سقف كلمات «الإقرار المجرّد». على سابقة `_is_bare_confusion`
    #: (D-153): العلامة وحدها لا تكفي، لأن «اها فهمت، تقلص الفضاء فنقسم على عدد
    #: اقل» تحمل العلامة **وهي برهان آلية** لا ادّعاء. القِصَر هو ما يُميّز
    #: الإقرارَ الفارغ من الإقرار المُسنَد.
    _BARE_ACK_MAX_WORDS: int = 4

    @classmethod
    def _is_bare_acknowledgement(cls, question: str) -> bool:
        """هل الرسالة إقرارٌ بالفهم بلا برهان؟ (علامة من `shared/intent` + قِصَر)."""
        try:
            from shared.intent import matches, normalize

            norm = normalize(question or "")
            if not norm or len(norm.split()) > cls._BARE_ACK_MAX_WORDS:
                return False
            return matches(norm, "acknowledgement")
        except Exception:  # pragma: no cover - fail-safe
            return False

    @classmethod
    def _cognitive_turn(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
        tutor_state: dict | None,
        _policy_decision=None,  # D-158 Phase 1: محجوز (القرار من kc_progress، لا policy بعد)
    ) -> tuple[str | None, dict | None]:
        """D-158/D-159: طبقة القرار الموحَّدة فوق ``tutor_state`` المُخزَّن (حتمية، صفر LLM).

        المصدر الوحيد للقرار = ``kc_progress`` الدائم (لا مسح نصّ) عبر المخطط المُهيكَل
        `kc_progress_schema` (D-159 WP-A — لا dict literals يدوية بعد اليوم). تقتل
        الأعراض الثلاثة بنيوياً وعبر الكتل:
        - **S2** (أعلى أولوية): إجابة رقمية صحيحة ⇒ اعتراف + تقدّم — على المستوى الأعلى،
          لا تمرّ عبر `_in_socratic_dialogue` فينكسر سجن الـ600-حرف (رسالة سابقة طويلة لم
          تعد تُخفي إجابة الطالب الصحيحة).
        - **S3**: أول تفاعل مع المكوّن ⇒ سؤال تشخيصي (لا تفريغ) — مقاد بالحالة الدائمة
          لا بقوائم علامات هشّة («كيف نحسب» = «كيف افهم»).
        - **S1**: غير ذلك ⇒ خطوة **واحدة** لم تُعرَض بعد (``representations_delivered``)
          عبر `_build_symbolic_step`؛ التفريغ الكامل غير ممكن (السجل الدائم يمنع التكرار).

        D-159 (WP-E): المحرّك **متعدد العُقد** — بعد إتقان `prob_event_a` ينتقل تلقائياً
        إلى `prob_event_b` (جداء الأرقام فردي؛ الأرقام من `number_parity_counts` الحتمي
        D-143) — آلة حالات معرفية حقيقية لا عقدة واحدة مُجمَّدة.

        يُرجِع ``(text, kc_progress_delta)`` أو ``(None, None)`` (تسليم للكتل القائمة).
        يحقن الدلتا أيضاً في ``tutor_state["kc_progress_delta"]`` (dict مشترك) ليحفظها
        customer_chat عبر ``record_turn``.
        """
        try:
            if not isinstance(tutor_state, dict):
                return None, None
            # D-159 (ISS-125 lesson): بوّابة سياق الاحتمالات **قبل** أي تحميل — مع التفعيل
            # الافتراضي كان المحرّك يختطف أسئلة عامة (قانون نيوتن!) لأن مُحمّل التمرين
            # الرسمي يتعرّف دائماً. المحرّك يعمل فقط حين يكون السؤال/الحوار احتمالياً فعلاً.
            # ISS-131 (D-169 — قاعدة D-102): رسائل system لا تدخل الكاشف — برومبت الإدمن
            # (21K حرف يحوي «كرة/احتمال») كان يجعل كل سؤال إدمن «سياق احتمالات» فيُختطف
            # بالـ probe. الكاشف يقرأ رسائل الطالب/المساعد حصراً.
            _ct_hist = " ".join(
                str(m.get("content", ""))
                for m in (history_messages or [])
                if isinstance(m, dict) and m.get("role") in ("user", "assistant")
            )
            if not cls._is_prob_context(f"{question} {_ct_hist}"):
                return None, None
            # طلب محتوى/تمرين جديد صريح ⇒ ليس تفاعل تدريس (تسليم للاسترجاع).
            _low = (question or "").strip().lower()
            if any(m in _low for m in ("اعطني", "أعطني", "اعطيني", "هات", "اكتب", "ارسم", "درس")):
                return None, None
            # حارس تبديل الموضوع (D-101): سؤال غير احتمالي ⇒ تسليم للكتل.
            # D-266 (ISS-159): الحاسم الواحد — يقرأ المنهاج كلّه لا ثلاثة مواضيع.
            with contextlib.suppress(Exception):
                from app.services.capabilities.topic_authority import is_foreign_to_probability

                if is_foreign_to_probability(question):
                    return None, None
            combo = cls._load_canonical_combinations(question, history_messages)
            if combo is None:
                return None, None

            from app.services.skills.kc_progress_schema import (
                PENDING_KEY,
                delivered_steps,
                make_pending,
                parse_kc_entry,
                pending_of,
            )

            kc_progress = tutor_state.get("kc_progress")
            kc_progress = kc_progress if isinstance(kc_progress, dict) else {}
            pending = pending_of(kc_progress)
            entry_a = parse_kc_entry(kc_progress.get(cls._KC_PROB_A))
            turn_no = int(tutor_state.get("turn_count") or 0) + 1

            # D-159 (WP-E): اختيار العقدة النشطة — إتقان A ينقل المحرّك للحادثة B تلقائياً.
            active_kc = cls._KC_PROB_A
            parity: dict[str, int] | None = None
            if entry_a.state == "understood":
                parity = cls._load_canonical_parity(question, history_messages)
                if parity and int(parity.get("odd", 0)) >= int(combo.k):
                    active_kc = cls._KC_PROB_B
            entry = (
                entry_a
                if active_kc == cls._KC_PROB_A
                else parse_kc_entry(kc_progress.get(cls._KC_PROB_B))
            )

            def _finish(
                text: str,
                *,
                advance_state: str | None = None,
                clear_pending: bool = False,
                add_step: str | None = None,
                new_pending: str | None = None,
            ) -> tuple[str, dict]:
                if add_step:
                    entry.mark_delivered(add_step)
                if advance_state:
                    entry.state = advance_state
                entry.updated_turn = turn_no
                entry.last_emitted_hash = cls._norm_for_dedup(text)[:120]
                delta: dict = {active_kc: entry.to_dict()}
                if clear_pending:
                    delta[PENDING_KEY] = {}
                elif new_pending:
                    delta[PENDING_KEY] = make_pending(active_kc, new_pending)
                tutor_state["kc_progress_delta"] = delta
                return text, delta

            # ── D-165 (ISS-129): سؤال «غاية التمرين» («ماذا نستفيد من هذا التمرين؟»)
            #    يُجاب حتمياً من المكوّنات المعرفية (data-driven من combo — عقد ملايير
            #    التمارين) قبل أي probe/سُلّم — كان يُختطف بالـ probe التشخيصي متجاهلاً
            #    السؤال كلياً. dedup-محروس؛ فشل البناء ⇒ هروب لطبقات الإجابة (D-112). ──
            if cls._detect_exercise_purpose_question(question):
                _purpose = cls._build_exercise_purpose_answer(combo)
                if _purpose and not cls._recently_emitted(_purpose, history_messages):
                    entry.attempts += 1
                    with contextlib.suppress(Exception):
                        from app.services.skills.tutor_metrics import record_definitional_answer

                        record_definitional_answer("exercise_purpose", True, source="deterministic")
                    return _finish(_purpose, add_step="exercise_purpose")
                return None, None

            if active_kc == cls._KC_PROB_B:
                return cls._cognitive_turn_event_b(
                    question, history_messages, combo, parity, entry, _finish
                )

            # ── F2 (D-160/ISS-126): طلب شرح اشتقاق خطوة/قيمة («كيف حسبنا 4») ⇒ يُعلّم
            #    اشتقاق تلك الجزئية (يُعيد استخدام _build_probability_direct_explanation،
            #    forced_subpart)، dedup-محروس. يقتل الكارثة الجذرية: كان «كيف حسبنا 4»
            #    يسقط للإنقاذ النهائي المكرَّر «ركّب بنفسك» لأن لا فرع يشرح اشتقاق قيمة.
            #    **قبل S2**: طلب الشرح الصريح (بعلامة) يهزم تحقّق الإجابة الرقمية — «كيف
            #    حسبنا 14» شرحٌ لا إجابةَ «14» (لا اختطاف). الإجابة بلا علامة تبقى لـ S2.
            _explain_part = cls._detect_step_explanation(question, combo)
            if _explain_part is not None:
                # ISS-148: هذا هو المسار الذي أنتج الرسالة 4615 في الإنتاج —
                # «كيف حسبنا 165» ⇒ `forced_subpart="total"` ⇒ إعادة اشتقاق ما
                # كُشِف في الدور السابق تحت الاسم `ratio`. الاسمان **فكرة واحدة**
                # (المقام)، وحارس التكرار النصّي لا يراها لأنه يُقنّع الأرقام.
                # الدفتر يحوّل الإعادة إلى تبريرٍ مفاهيمي — زاويةٌ جديدة لا نسخة.
                _teach = cls._build_probability_direct_explanation(
                    question,
                    history_messages,
                    forced_subpart=_explain_part,
                    delivered=delivered_steps(kc_progress),
                )
                if _teach and not cls._recently_emitted(_teach, history_messages):
                    entry.attempts += 1
                    return _finish(_teach, add_step=_explain_part)

            # السؤال المعلّق (D-155/D-158): kc_progress الدائم أولاً ثم اشتقاق التاريخ.
            _pending_focus = (
                pending[1] if pending and pending[0] == cls._KC_PROB_A else None
            ) or cls._pending_focus_from_history(history_messages)

            # ── F2b (D-162/ISS-128): سؤال التسمية («ماذا نسمي حساب 4 و 10؟») يُجاب
            #    بالاسم (التوافيق — data-driven من combo) + إعادة طرح السؤال المعلّق،
            #    مع إبقاء pending كما هو (لا تقدّم زائف). حتمي، صفر LLM. ──
            _is_q = cls._is_question_not_answer(question)
            if _is_q and cls._detect_naming_question(question, combo):
                _name_text = cls._build_naming_answer(combo, _pending_focus)
                if _name_text and not cls._recently_emitted(_name_text, history_messages):
                    entry.attempts += 1
                    return _finish(_name_text)

            # ── S2: إجابة رقمية صحيحة ⇒ اعتراف + تقدّم (المستوى الأعلى — لا سجن 600-حرف) ──
            _numeric = cls._verify_numeric_answer(question, combo, _pending_focus)
            if _numeric == "final_ratio":
                entry.attempts += 1
                entry.evidence = "verified"
                text = (
                    "أحسنت! ✅ إجابتك صحيحة تماماً — ركّبت احتمال الحادثة A بنفسك: "
                    "الحالات الملائمة على كل الحالات الممكنة.\n\n"
                    "ننتقل للسؤال التالي في التمرين — **الحادثة B**: جداء الأرقام "
                    "عدد فردي. قبل أي حساب، سؤال واحد: متى يكون جداء ثلاثة أعداد فردياً؟"
                )
                text, delta = _finish(text, advance_state="understood", clear_pending=True)
                # D-159 (WP-E): بذر عقدة الحادثة B — سؤالها التشخيصي طُرح في النصّ نفسه،
                # فتُسجَّل الحالة صادقةً: probe مُسلَّم + السؤال المعلّق صار على B.
                entry_b = parse_kc_entry(kc_progress.get(cls._KC_PROB_B))
                entry_b.mark_delivered("diagnostic_probe")
                entry_b.state = "explained"
                entry_b.updated_turn = turn_no
                delta[cls._KC_PROB_B] = entry_b.to_dict()
                delta[PENDING_KEY] = make_pending(cls._KC_PROB_B, "parity")
                return text, delta
            if _numeric in ("step_correct", "direction"):
                text = cls._build_symbolic_step(combo, "ratio", acknowledge=True)
                if not cls._recently_emitted(text, history_messages):
                    entry.attempts += 1
                    entry.evidence = "verified"
                    return _finish(text, add_step="ratio", new_pending="ratio")

            # ── D-162 (ISS-128) + D-165 (ISS-129): سؤال لم تُجبه F2/التسمية/الغاية ⇒
            #    يهرب لطبقات الإجابة (D-124/D-125/D-132 ثم LLM المحروس) — سُلّم S1
            #    الأعمى للأدوار غير الاستفهامية حصراً (كان سيكشف 165 متجاهلاً السؤال).
            #    أسئلة «كيف/كيفاش» الإجرائية تبقى للتشخيص/السُّلّم (D-155/D-160).
            #    D-165 Fix A: البوّابة **قبل** probe S3 (كانت بعده — فكان أول سؤال
            #    غير-كيف يُختطف بالـ probe متجاهلاً السؤال؛ port الخدمة المصغرة كان
            #    أصلاً يضعها قبل الـ probe — افتراق split-brain حي أُنهي هنا). ──
            _qg = (question or "").strip().lower()
            if _qg.startswith("و "):
                _qg = _qg[2:].lstrip()
            if _is_q and not _qg.startswith(("كيف", "كيفاش")):
                return None, None

            entry.attempts += 1

            # ── D-186 (ISS-139): البؤرة اللاصقة تسبق probe الافتتاح ──
            # «لم أفهم» تعني «لم أفهم ما شرحتَه للتوّ» (قانون D-184)، لا «ابدأ التمرين
            # من أوّله». كان الطالب يسأل عن الرمز `C` فيُعرَّف له، ثم يقول «لم أفهم»
            # فيُقذَف إلى السؤال الافتتاحي عن الألوان — تصفيرٌ كامل للموضوع.
            #
            # حين تكون هناك بؤرة مفهومية حيّة (مفهومٌ طرحه **الطالب** نفسه في أدوار
            # سابقة) نُسلّم الدور لمصفوفة التصعيد: هي المصمَّمة لـ«حيرة + مفهوم نشط ⇒
            # الرُّتبة التالية». الـ probe يبقى لما هو له: أول تفاعل مع التمرين.
            if cls._has_live_concept_focus(question, history_messages):
                return None, None

            # ── S3: أول تفاعل ⇒ التشخيص قبل الشرح ──
            if "diagnostic_probe" not in entry.representations_delivered:
                text = cls._build_diagnostic_probe(combo)
                return _finish(
                    text,
                    advance_state="explained",
                    add_step="diagnostic_probe",
                    new_pending="numerator",
                )

            # ── S1: كشف تدريجي — خطوة واحدة لم تُعرَض بعد (لا تفريغ كامل) ──
            for step in ("numerator", "ratio"):
                if step in entry.representations_delivered:
                    continue
                # ISS-148: سؤالُ الطالب عن الإجراء («كيف نحسب الحادثة A») يستحقّ
                # الإجراء لا ناتجه. التسليم الرمزي الكامل يبقى للمحاولة المُعترَف بها.
                #
                # ISS-149: و«فهمت» المجرّدة ليست محاولةً أيضاً — هي **ادّعاء** فهم.
                # كانت تستنفد الميزانية فتُسلّم `4 + 10 = 14` كاملاً، أي أنّ قولَ
                # «فهمت» يشتري الحلّ. فيتعلّم الطالب أن يدّعي الفهم بدل أن يحسب،
                # وتُصنَّع فجوة الوهم التي نُحسّن على تقليصها (§0.6). الادّعاء
                # يُختبَر بالطريقة: خذ الخطوات واحسب أنت.
                text = cls._build_symbolic_step(
                    combo, step, method_only=_is_q or cls._is_bare_acknowledgement(question)
                )
                if cls._recently_emitted(text, history_messages):
                    continue
                # D-162 (ISS-128): pending = بؤرة **السؤال المطروح فعلاً** في نصّ
                # الخطوة، لا اسم الخطوة المُسلَّمة — خطوة البسط تسأل عن المقام
                # («كم عدد كل الطرق الممكنة؟»)؛ تخزين "numerator" جعل {4,10} في
                # سؤالٍ لاحق تُعترف step_correct (favs ⊆ nums) — كارثة الترانسكريبت.
                return _finish(
                    text,
                    add_step=step,
                    new_pending=("denominator" if step == "numerator" else step),
                )

            # ── F1 (D-160): الإنقاذ النهائي محروس ضد التكرار (كان يُرجَع بلا حارس ⇒
            #    كارثة الترانسكريبت ×3). حين لا يكون مكرَّراً ⇒ يُبَثّ. ──
            text = cls._build_symbolic_reveal(
                question,
                history_messages,
                acknowledge=bool(_numeric),
                delivered=set(entry.representations_delivered),
            )
            if text and not cls._recently_emitted(text, history_messages):
                return _finish(text, new_pending="ratio")

            # ── F3 (D-160): الإنقاذ مكرَّر ⇒ الطالب العالق يتعلّم لا يدور: علّم اشتقاق
            #    أصغر جزئية ملموسة لم تُعرَض بعد (لا كشف P(A) النهائي — يحترم M6/M8). ──
            for _part in ("red", "green", "white", "total", "sum"):
                if _part in entry.representations_delivered:
                    continue
                _t = cls._build_probability_direct_explanation(
                    question,
                    history_messages,
                    forced_subpart=_part,
                    delivered=delivered_steps(kc_progress),  # ISS-148
                )
                if _t and not cls._recently_emitted(_t, history_messages):
                    return _finish(_t, add_step=_part)

            # كل شيء عُلِّم ومكرَّر ⇒ تسليم للكتل (fail-open) بدل إعادة نصّ مكرَّر.
            return None, None
        except Exception:  # pragma: no cover - fail-safe (never abort a turn)
            logger.warning("_cognitive_turn_failed", exc_info=True)
            return None, None

    @classmethod
    def _cognitive_turn_event_b(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
        combo,
        parity: dict[str, int] | None,
        entry,
        _finish,
    ) -> tuple[str | None, dict | None]:
        """D-159 (WP-E): دور الحادثة B (جداء الأرقام فردي) — حتمي من المحرك الرمزي.

        الأرقام من `number_parity_counts` (D-143) حصراً: عدد الكرات الفردية o ⇒ الحالات
        الملائمة C(o,k)؛ المقام نفسه من الجزء A. صفر LLM؛ النصوص تَنجو من حجب D-113
        (نمط `_fmt_comb` LaTeX + أسئلة توليد — النسبة النهائية لا تُطبع أبداً D-154).
        """
        import math

        if not parity:
            return None, None
        odd = int(parity.get("odd", 0))
        k = int(combo.k)
        total = int(combo.total_combinations)
        n = int(combo.n)
        fav_b = math.comb(odd, k) if odd >= k else 0
        if fav_b <= 0:
            return None, None

        # ── S2-B: إجابة رقمية صحيحة على B ⇒ اعتراف + إقفال العقدة ──
        nums = cls._extract_answer_numbers(question)
        if fav_b in nums and total in nums:
            entry.attempts += 1
            entry.evidence = "verified"
            text = (
                "أحسنت! ✅ ركّبت احتمال الحادثة B بنفسك — الحالات الملائمة على كل "
                "الحالات الممكنة.\n\n"
                "أنجزت الحادثتين A و B بيديك. حين تريد نتابع بقية أجزاء التمرين "
                "(الحادثة C أو المتغيّر العشوائي) بنفس الطريقة — أيّها تختار؟"
            )
            return _finish(text, advance_state="understood", clear_pending=True)
        if nums and (fav_b in nums or odd in nums):
            # خطوة صحيحة (وجد عدد الفرديات أو الحالات الملائمة) ⇒ اعتراف + خطوة النسبة.
            text = (
                "إجابتك في الطريق الصحيح — هذا بالضبط ما نحتاجه للحادثة B.\n\n"
                f"وكل الطرق الممكنة لم تتغيّر عن الجزء السابق (نفس الكيس ونفس السحب): "
                f"{cls._fmt_comb(n, k, total)}\n\n"
                "الآن لديك البسط والمقام — كيف تُكوّن منهما احتمال الحادثة B؟"
            )
            if not cls._recently_emitted(text, history_messages):
                entry.attempts += 1
                entry.evidence = "verified"
                return _finish(text, add_step="ratio", new_pending="ratio")

        entry.attempts += 1

        # ── S3-B: التشخيص قبل الشرح (يُبذَر عادةً من نهاية الجزء A) ──
        if "diagnostic_probe" not in entry.representations_delivered:
            text = (
                "ننتقل للحادثة B: **جداء الأرقام الثلاثة عدد فردي**.\n\n"
                "سؤال واحد قبل أي حساب: متى يكون جداء ثلاثة أعداد فردياً؟ "
                "وأيّ كرات الكيس تحمل أرقاماً فردية؟"
            )
            return _finish(
                text,
                advance_state="explained",
                add_step="diagnostic_probe",
                new_pending="parity",
            )

        # ── S1-B: كشف تدريجي — خطوة واحدة لم تُعرَض بعد ──
        if "numerator" not in entry.representations_delivered:
            text = (
                "الجداء يكون فردياً فقط إذا كانت **كل** الأرقام الثلاثة فردية — "
                f"فنقتصر على الكرات ذات الأرقام الفردية وعددها {odd}.\n\n"
                f"الحالات الملائمة للحادثة B: {cls._fmt_comb(odd, k, fav_b)}\n\n"
                "والآن سؤالٌ يقودنا للخطوة التالية: كم عدد **كل** الطرق الممكنة للسحب؟"
            )
            if not cls._recently_emitted(text, history_messages):
                return _finish(text, add_step="numerator", new_pending="numerator")
        if "ratio" not in entry.representations_delivered:
            text = (
                f"**كل الطرق الممكنة** لم تتغيّر عن الجزء السابق: "
                f"{cls._fmt_comb(n, k, total)}\n\n"
                "الآن لديك البسط والمقام — كيف تُكوّن منهما احتمال الحادثة B؟"
            )
            if not cls._recently_emitted(text, history_messages):
                return _finish(text, add_step="ratio", new_pending="ratio")

        # كل الخطوات عُرضت ⇒ مُوجّه توليد (لا كشف للنسبة النهائية — D-113/D-154).
        text = (
            "أمامك الآن كل المكوّنات — ركّب احتمال الحادثة B **بنفسك**: "
            "الحالات الملائمة على كل الحالات الممكنة. فما النسبة التي تحصل عليها؟"
        )
        if cls._recently_emitted(text, history_messages):
            return None, None  # تسليم للكتل القائمة بدل بثّ مكرَّر (قاعدة D-154).
        return _finish(text, new_pending="ratio")
