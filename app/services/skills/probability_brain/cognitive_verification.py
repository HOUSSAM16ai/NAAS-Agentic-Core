"""D-127 (الطبقات 3/5) — السياق/dedup/التحقق الرمزي/بوّابة الفعل الكلامي/الأعلام/dialogue/canonical — مستخرَج حرفياً من `probability_tutor_brain.py` (D-168).

جزء من تركيبة `ProbabilityTutorBrain` (mixin) — كل `cls._x` تُحل عبر الـ MRO المُركَّب.
**ممنوع** الاستيراد من `microservices/` هنا؛ والأرقام من المحرك الرمزي حصراً.
"""

from __future__ import annotations

import logging
import re

# نفس اسم الـ logger القديم عمداً — استمرارية السجلات وصفر تغيير رصدي (D-163/D-168).
logger = logging.getLogger("orchestrator-client")


class CognitiveVerificationMixin:
    # ─────────────────────────────────────────────────────────────────────────
    # D-127 — المعمارية الإدراكية العصبية-الرمزية (Layers 3/4/5):
    # استجابة مدفوعة بالمفهوم (لا بالصياغة) + تصعيد سقراطي مضاد للتكرار. كل صياغات
    # المفهوم الواحد → استجابة واحدة؛ نفس المفهوم مرّتين → سؤال سقراطي لا تكرار.
    # الأرقام من المحرك الرمزي (الطبقة 3، صفر LLM). التشخيص من الطبقة 1 (ConceptDiagnosisSkill).
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _is_prob_context(text: str) -> bool:
        """سياق احتمالات (لتقييد استدعاء LLM التشخيص على الاحتمالات فقط)."""
        t = text or ""
        return any(
            m in t
            for m in (
                "كرات",
                "كرة",
                "كيس",
                "احتمال",
                "سحب",
                "نسحب",
                "البسط",
                "المقام",
                "p(a",
                "p(b",
                "165",
                "14",
                # D-159: مفردات تمرين الاحتمالات (أسئلة الحادثة A/B بلا ذكر الكيس صراحةً).
                "الحادثة",
                "الفردية",
            )
        )

    @staticmethod
    def _norm_for_dedup(text: str) -> str:
        """D-142 (1B) + ISS-121 (D-154): تطبيع نصّ للمقارنة على التكرار — محايد للحجب.

        النسخة المحفوظة (history + `last_step_emitted`) تمرّ عبر حجب D-113
        («14» ⇒ «؟») بينما المبثوثة كاملة الأرقام ⇒ حارس التكرار كان يَعمى عن
        تحويل الحجب فيبثّ الحل المكرَّر (كارثة الترانسكريبت). نستبدل مقاطع
        الأرقام و«؟/?» بعنصر نائب موحّد فتتطابق النسختان بنيوياً.
        """
        try:
            from app.services.capabilities.arabic_normalize import normalize_ar

            base = normalize_ar(text or "")
        except Exception:  # pragma: no cover - fail-safe
            base = (text or "").strip().lower()
        return re.sub(r"[\d؟?]+", "#", base)

    @classmethod
    def _recently_emitted(
        cls,
        candidate: str,
        history_messages: list[dict[str, str]] | None,
        *,
        lookback: int = 6,
        threshold: float = 0.8,
    ) -> bool:
        """D-142 (1B): هل بُثّ نصّ شبيه بـ ``candidate`` في رسائل المساعد الأخيرة؟

        حارس تكرار عام: احتواء أو تداخل رموز ≥ ``threshold`` مع رسالة مساعد سابقة ⇒ True،
        فيُصعّد المُنادي إلى الرُّتبة التالية بدل الإعادة الحرفية (يكسر كارثة التكرار ×3).
        """
        cand = cls._norm_for_dedup(candidate)
        cand_tokens = set(cand.split())
        if not cand_tokens:
            return False
        seen = 0
        for msg in reversed(history_messages or []):
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue
            seen += 1
            if seen > lookback:
                break
            prev = cls._norm_for_dedup(str(msg.get("content", "")))
            if not prev:
                continue
            if cand in prev or prev in cand:
                return True
            # D-185 (ISS-138): نسبة متماثلة — «تكرار + إضافة» كان يهرب من العتبة.
            if cls._overlap_ratio(cand_tokens, set(prev.split())) >= threshold:
                return True
        return False

    @classmethod
    def _verify_answer_against_combo(cls, answer: str, combo) -> bool:
        """D-142 (1A): تحقّق رمزي من صحة إجابة الطالب مقابل المحرك الرمزي (combo).

        صحيحة حتمياً حين تُسمّي لوناً ممكناً (عدده ≥ k) أو تُقرّ باستحالة لون (عدده < k).
        مستقلّ عن تشخيص المفهوم ⇒ يُكرّم الإجابة الصحيحة حتى لو أخطأ التشخيص (السلطة الرمزية).
        """
        try:
            from app.services.capabilities.arabic_normalize import normalize_ar

            norm = normalize_ar(answer or "")
            if not norm:
                return False
            possible = [
                normalize_ar(getattr(g, "label", ""))
                for g in getattr(combo, "groups", [])
                if getattr(g, "is_possible", True)
            ]
            possible_words = {p.split()[-1] for p in possible if p.split()}
            mentions_possible = any(w and w in norm for w in possible_words)
            raw = answer or ""
            mentions_impossible = any(
                w in raw for w in ("مستحيل", "لا يمكن", "فقط", "لونين", "غير كاف", "2 فقط")
            )
            return mentions_possible or mentions_impossible
        except Exception:  # pragma: no cover - fail-safe
            return False

    #: ISS-122 (D-155): قوالب أسئلة الخطوات التي نطرحها نحن — تُعرِّف «السؤال
    #: المعلّق» المشتق من أحدث رسالة مساعد (لا حالة دائمة جديدة). أي قالب سؤال
    #: جديد في البُناة الحتمية يجب أن يُسجَّل هنا وإلا صار سؤاله غير مرئي للتحقّق.
    _STEP_QUESTION_MARKERS: tuple[tuple[str, str], ...] = (
        ("كم عدد **كل** الطرق الممكنة", "denominator"),
        ("كم عدد كل الطرق الممكنة", "denominator"),
        ("كيف تُكوّن منهما الاحتمال", "ratio"),
        ("فما قيمة P(A)", "ratio"),
        ("ما قيمة P(A) التي حصلت عليها", "ratio"),
        ("أيّ الألوان يمكن أن تعطينا", "colors"),
    )

    #: ISS-122 (D-155): علامات «خطوة تدريس سابقة» — وجود أيٍّ منها في رسائل
    #: المساعد يعني أن الحوار التدريسي بدأ (فلا يُعاد probe التشخيص الأول).
    _TUTORING_STEP_MARKERS: tuple[str, ...] = (
        "الحالات الملائمة",
        "كم عدد **كل** الطرق",
        "كيف تُكوّن منهما الاحتمال",
        "أيّ الألوان يمكن أن تعطينا",
        "لنُكمل معاً خطوة بخطوة",
        "فما قيمة P(A)",
    )

    #: ISS-122 (D-155) + ISS-128 (D-162): بادئات استفهامية تجعل الرسالة سؤالاً لا
    #: إجابةً تُقيَّم — تسقط لطبقات الإجابة (F2/التسمية/D-124/D-125). «هل» ليست هنا
    #: عمداً: «هل هي 14 من 165» إجابة تطلب تأكيداً. D-162 وسّعها بعد كارثة
    #: «ماذا نسمي حساب 4 و 10 لم افهمها؟» التي اعتُرفت «إجابة في الطريق الصحيح».
    _QUESTION_OPENERS_NOT_ANSWERS: tuple[str, ...] = (
        "لماذا",
        "ليش",
        "علاش",
        "كيف",
        "كيفاش",
        "ماذا",
        "ما هو",
        "ما هي",
        "ماهو",
        "ماهي",
        "ما اسم",
        "ما الفرق",
        "ما معنى",
        "ما المقصود",
        "متى",
        "أين",
        "اين",
        "من أين",
        "من اين",
        "شنو",
        "واش",
    )

    #: D-162 (ISS-128): علامات نية التسمية («ماذا **نسمي** حساب 4 و 10؟») — الطالب
    #: يطلب **اسم** العملية (التوافيق)، لا نتيجتها. كانت عمياء عنها كل الطبقات.
    _NAMING_MARKERS: tuple[str, ...] = (
        "نسمي",
        "ما اسم",
        "ما إسم",
        "يسمى",
        "تسمى",
        "تسميه",
        "تسمية",
    )

    @classmethod
    def _is_question_not_answer(cls, message: str) -> bool:
        """D-162 (ISS-128): بوّابة الفعل الكلامي — سؤال الطالب لا يُقيَّم كإجابة أبداً.

        الكارثة: «ماذا نسمي حساب 4 و 10 لم افهمها؟» احتوت أرقاماً تطابق قيم
        combo فاعتُرفت ``step_correct`` وكُشف جواب السؤال المعلّق (165). السؤال
        والإجابة يجب أن يتمايزا **قبل** أي مطابقة رقمية. «هل» مستثناة عمداً
        (قاعدة D-155 الثابتة: «هل هي 14 من 165» إجابة تطلب تأكيداً).
        """
        try:
            q = (message or "").strip().lower()
            if not q:
                return False
            # «و ماذا نسمي...» — واو العطف لا تحجب البادئة (دون مسّ «واش» الدارجة).
            if q.startswith("و "):
                q = q[2:].lstrip()
            if q.startswith(cls._QUESTION_OPENERS_NOT_ANSWERS):
                return True
            return any(m in q for m in cls._NAMING_MARKERS)
        except Exception:  # pragma: no cover - fail-safe
            return False

    @classmethod
    def _pending_focus_from_history(
        cls, history_messages: list[dict[str, str]] | None
    ) -> str | None:
        """ISS-122 (D-155): السؤال المعلّق — أيّ خطوة سألنا عنها الطالب آخر مرة؟

        حتمي: يطابق قوالبنا نحن في أحدث رسالة مساعد (القوالب بلا أرقام فتنجو من
        حجب D-113 في النسخة المحفوظة). ``denominator``/``ratio``/``colors``/None.
        """
        last_assistant = ""
        for msg in reversed(history_messages or []):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                last_assistant = str(msg.get("content", ""))
                break
        if not last_assistant:
            return None
        for marker, focus in cls._STEP_QUESTION_MARKERS:
            if marker in last_assistant:
                return focus
        return None

    @staticmethod
    def _extract_answer_numbers(text: str) -> set[int]:
        """ISS-122 (D-155): أعداد رسالة الطالب (أرقام عربية ⇒ لاتينية أولاً)."""
        digits = (text or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        return {int(m) for m in re.findall(r"\d+", digits)}

    @classmethod
    def _verify_numeric_answer(cls, answer: str, combo, pending_focus: str | None) -> str | None:
        """ISS-122 (D-155): الحقيقة الرمزية تحكم إجابة الطالب **الرقمية**.

        كارثة الترانسكريبت: «هل هي 14 من 165» (الإجابة الصحيحة!) كانت غير مرئية
        لكل طبقات التحقّق (ألوان فقط) ⇒ أُعيد سؤال ما أُجيب للتو. الأرقام من
        ``combo`` حصراً (صفر hardcoding). يُرجِع:
        ``"final_ratio"`` (النسبة النهائية بأي صياغة) | ``"step_correct"``
        (خطوة السؤال المعلّق) | ``"direction"`` (اتجاه صحيح — «نفس الشئ مع 11»)
        | ``None`` (غير مؤكَّدة ⇒ تُترك للمُقيّم).
        """
        try:
            # D-162 (ISS-128): بوّابة الفعل الكلامي أولاً — «ماذا نسمي حساب 4 و 10
            # لم افهمها؟» سؤالٌ يحمل أرقاماً تطابق favs فكان يُعترف step_correct
            # ويُكشف جواب السؤال المعلّق. السؤال ليس إجابة أبداً (عدا «هل» — D-155).
            if cls._is_question_not_answer(answer):
                return None
            nums = cls._extract_answer_numbers(answer)
            if not nums:
                return None
            same = int(combo.same_group_favorable)
            total = int(combo.total_combinations)
            n = int(combo.n)
            favs = {
                int(g.favorable_combinations)
                for g in getattr(combo, "groups", [])
                if getattr(g, "is_possible", False)
            }
            # النسبة النهائية صحيحة بأي صياغة («14/165»، «14 من 165»، «14 على 165»)
            # وفي أي سؤال معلّق — تأكيد ما ولّده الطالب ليس كشفاً.
            if same in nums and total in nums:
                return "final_ratio"
            if pending_focus == "denominator":
                if total in nums:
                    return "step_correct"
                if n in nums:  # «نفس الشئ مع 11» — الاتجاه صحيح، نُكمل الحساب معاً.
                    return "direction"
                return None
            if pending_focus in (None, "numerator") and (same in nums or (favs and favs <= nums)):
                return "step_correct"
            return None
        except Exception:  # pragma: no cover - fail-safe
            return None

    @classmethod
    def _has_prior_tutoring_step(cls, history_messages: list[dict[str, str]] | None) -> bool:
        """ISS-122 (D-155): هل بُثّت أي خطوة تدريس (probe/سُلّم/إنقاذ) سابقاً؟"""
        for msg in history_messages or []:
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue
            content = str(msg.get("content", ""))
            if any(m in content for m in cls._TUTORING_STEP_MARKERS):
                return True
        return False

    @classmethod
    def _has_live_concept_focus(
        cls, question: str, history_messages: list[dict[str, str]] | None
    ) -> bool:
        """D-186 (ISS-139): هل للحوار بؤرة مفهومية حيّة يجب ألّا يُصفّرها probe الافتتاح؟

        شرطان معاً: (1) الدور الحالي **حيرة مجرّدة** («لم أفهم») — لا سؤال جديد ولا
        إجابة؛ (2) هناك مفهوم نشط طرحه **الطالب** نفسه في أدوار سابقة
        (`detect_active_concept` — D-137: نيّة الطالب لا نثر المساعد).

        عندها يُسلَّم الدور لمصفوفة التصعيد (حيرة + مفهوم نشط ⇒ الرُّتبة التالية) بدل
        السؤال الافتتاحي عن الألوان. `fail-open`: أي خطأ ⇒ `False` فيبقى السلوك القديم.
        """
        try:
            from shared.intent import classify

            if classify(question) != "confusion":
                return False
            from app.services.skills.semantic_property_skill import get_semantic_property_skill

            return (
                get_semantic_property_skill().detect_active_concept(question, history_messages)
                is not None
            )
        except Exception:  # pragma: no cover - fail-open: لا نكسر الدور أبداً
            return False

    @classmethod
    def _build_diagnostic_probe(cls, combo) -> str:
        """ISS-122 (D-155): سؤال تشخيصي واحد قبل أي محتوى محسوب — «التشخيص قبل الشرح».

        صفر قيم محسوبة (لا C، لا مجاميع) — الطالب يولّد بصيرة «البيضاء مستحيلة»
        بنفسه (generation effect). يَنجو من حجب D-113 بنيوياً (لا «=»، لا نتيجة).
        """
        comp = "، ".join(
            f"{g.count} {str(g.label).replace('كرة ', '')}" for g in getattr(combo, "groups", [])
        )
        k = int(combo.k)
        return (
            f"لنبدأ من فهمك أنت — نسحب {k} كرات دفعة واحدة من كيس فيه: {comp}.\n\n"
            f"سؤال واحد قبل أي حساب: أيّ الألوان يمكن أن تعطينا {k} كرات "
            f"من نفس اللون؟ ولماذا؟"
        )

    @staticmethod
    def _is_first_help_request(question: str) -> bool:
        """ISS-122 (D-155): أول طلب مساعدة عام («كيف افهم التمرين»/«من أين أبدأ»)."""
        try:
            from app.services.capabilities.arabic_normalize import normalize_ar

            norm = normalize_ar(question or "")
        except Exception:  # pragma: no cover - fail-safe
            norm = (question or "").strip()
        markers = (
            "كيف افهم",
            "كيف نفهم",
            "كيف احل",
            "كيف نحل",
            "من اين ابدا",
            "من اين نبدا",
            "كيف ابدا",
            "كيف نبدا",
        )
        return any(m in norm for m in markers)

    @classmethod
    def _near_dup(cls, a: str, b: str, *, threshold: float = 0.8) -> bool:
        """D-142 (1B/Phase2): تداخل رموز/احتواء بين نصّين (حارس التكرار ضد مرساة الحالة).

        D-185 (ISS-138): النسبة **متماثلة** — انظر :meth:`_overlap_ratio`.
        """
        na, nb = cls._norm_for_dedup(a), cls._norm_for_dedup(b)
        if not na or not nb:
            return False
        if na in nb or nb in na:
            return True
        return cls._overlap_ratio(set(na.split()), set(nb.split())) >= threshold

    @staticmethod
    def _overlap_ratio(cand_tokens: set[str], prev_tokens: set[str]) -> float:
        """D-185 (ISS-138): نسبة تداخل **متماثلة** — القسمة على الأصغر لا على المرشَّح.

        الكارثة: الدور الثالث بثّ كتلة قصيرة (`C(4,3)=4` · `C(5,3)=10` · المجموع)، ثم
        رشّح الدور الرابع نصّاً **مجموعةً فائقة** منها (نفس الأسطر + فضاء العينة + خاتمة
        مختلفة). القسمة القديمة على `len(cand_tokens)` جعلت المقام يكبر بالنصّ المضاف
        فتهبط النسبة تحت العتبة ⇒ الحارس يعمى ⇒ يُعاد على الطالب اشتقاقٌ لم يفهمه
        **مع تسريب النتائج**. القسمة على الأصغر تجعل «تكرار + إضافة» تكراراً كما هو حقاً.
        """
        if not cand_tokens or not prev_tokens:
            return 0.0
        return len(cand_tokens & prev_tokens) / min(len(cand_tokens), len(prev_tokens))

    @staticmethod
    def _semantic_tutor_enabled() -> bool:
        """D-142/D-158: علم تحميل+كتابة `tutor_state` — قارئ موحَّد (افتراض True).

        D-158: يُفوَّض إلى `app.core.feature_flags` — يُنهي الافتراض المتعارض (كان False هنا
        و True في customer_chat) الذي كان يُعطِّل سلطة `DialogueManagerSkill` في الإنتاج.
        """
        from app.core.feature_flags import semantic_tutor_enabled

        return semantic_tutor_enabled()

    @staticmethod
    def _cognitive_turn_enabled() -> bool:
        """D-158/D-159: علم طبقة القرار الموحَّدة `_cognitive_turn` (افتراض True منذ D-159)."""
        from app.core.feature_flags import cognitive_turn_enabled

        return cognitive_turn_enabled()

    @classmethod
    def _dialogue_decision(
        cls,
        *,
        question: str,
        concept: str,
        verified_correct: bool,
        understood: bool,
        tutor_state: dict,
        candidate_text: str,
    ):
        """D-142 Phase 2: يستشير DialogueManagerSkill بإشارات الدور — fail-open (None عند الخطأ)."""
        try:
            from app.services.skills.dialogue_manager_skill import (
                DialogueInput,
                get_dialogue_manager_skill,
            )

            budget_map = tutor_state.get("socratic_count_by_concept") or {}
            socratic_count = int(budget_map.get(concept, 0)) if isinstance(budget_map, dict) else 0
            return get_dialogue_manager_skill().decide(
                DialogueInput(
                    question=question,
                    concept=concept,
                    verified_correct=bool(verified_correct),
                    understood=bool(understood),
                    ability=float(tutor_state.get("ability_snapshot") or 0.0),
                    socratic_count=socratic_count,
                    last_step_emitted=str(tutor_state.get("last_step_emitted") or ""),
                    candidate_text=candidate_text or "",
                )
            )
        except Exception:  # pragma: no cover - fail-safe
            return None

    @staticmethod
    def _concept_of_text(text: str) -> str:
        """D-127: المفهوم الحتمي لرسالة طالب (incl. confusion→full_solution).

        D-186: كشف الحيرة من `shared/intent` لا من قائمة محلّية سادسة — كانت هذه
        القائمة تجهل «مش فاهم» و«حاير» و«لا أعرف» فتُصنَّف `unknown`.
        """
        from app.services.skills.concept_diagnosis_skill import ConceptDiagnosisSkill
        from shared.intent import matches

        c = ConceptDiagnosisSkill.diagnose_deterministic(text).concept
        if c == "unknown":
            low = (text or "").strip().lower()
            if matches(low, "confusion") or low in ("؟", "?"):
                return "full_solution"
        return c

    @classmethod
    def _count_prior_concept(
        cls, concept: str, history_messages: list[dict[str, str]] | None
    ) -> int:
        """عدد رسائل الطالب السابقة التي تخصّ نفس المفهوم (سُلّم التصعيد السقراطي)."""
        count = 0
        for msg in history_messages or []:
            if (
                isinstance(msg, dict)
                and msg.get("role") == "user"
                and cls._concept_of_text(str(msg.get("content", ""))) == concept
            ):
                count += 1
        return count

    @classmethod
    def _load_canonical_combinations(
        cls, question: str, history_messages: list[dict[str, str]] | None
    ):
        """D-127: يحمّل تركيبة التمرين الرسمي (CombinationsModelOutput) — مناعة D-123.

        يُرجِع None لغير الاحتمالات (topic-safe) أو عند تعذّر الحساب.
        ISS-120 (D-153): يقرأ **أسئلة-فقط** — تغذية الملف الكامل (مع الحل النموذجي)
        كانت تولِّد كياناً وهمياً «بطاقة رقم 0 (العدد 3)» من نثر الحل («…لا تحمل
        الرقم 0 … سحب 3 كرات») ⇒ n=14 و C(14,3)=364 بدل 11/165 — كارثة الطالب.
        """
        try:
            from app.services.capabilities.arabic_normalize import primary_canonical_topic
            from app.services.capabilities.exercise_retrieval import (
                ExerciseRetrievalRequest,
                detect_exercise_retrieval,
                load_exercise_questions_only,
            )
            from app.services.skills.probability_skill import (
                CombinationsModelOutput,
                ProbabilityCalculatorSkill,
                ProbabilityInput,
            )

            _canonical = primary_canonical_topic(question)
            if _canonical is not None and _canonical.canonical_id != "probability":
                return None
            _decision = detect_exercise_retrieval(
                ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024"),
                history_messages=history_messages,
            )
            if not (_decision.recognized and _decision.matched_entry):
                return None
            _official = load_exercise_questions_only(_decision.matched_entry)
            if not _official:
                return None
            result = ProbabilityCalculatorSkill().analyze(
                ProbabilityInput(question=_official, history=None)
            )
            return result if isinstance(result, CombinationsModelOutput) else None
        except Exception:
            logger.warning("_load_canonical_combinations_failed", exc_info=True)
            return None
