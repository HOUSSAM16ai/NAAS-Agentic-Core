"""D-128/D-129/D-130 — السرد المُولَّد المحروس + reveal/step الرمزيان + الحوار السقراطي — مستخرَج حرفياً من `probability_tutor_brain.py` (D-168).

جزء من تركيبة `ProbabilityTutorBrain` (mixin) — كل `cls._x` تُحل عبر الـ MRO المُركَّب.
**ممنوع** الاستيراد من `microservices/` هنا؛ والأرقام من المحرك الرمزي حصراً.
"""

from __future__ import annotations

import logging
from typing import ClassVar

# نفس اسم الـ logger القديم عمداً — استمرارية السجلات وصفر تغيير رصدي (D-163/D-168).
logger = logging.getLogger("orchestrator-client")


class SocraticNarrativeMixin:
    # ─────────────────────────────────────────────────────────────────────────
    # D-128 — السرد السقراطي المُولَّد بالـ LLM (الطبقة 4 — الـ LLM كجهاز عصبي):
    # عند التصعيد (التكرار) يُولّد الـ LLM **تدخّلاً سقراطياً فريداً** — الـ LLM يُنتج
    # **الفهم/التربية** (السؤال السقراطي) لا **الحقيقة** (الأرقام تُحقن من المحرك الرمزي).
    # محروس: عربي فقط + لا كشف جواب + لا garbage + timeout + fallback حتمي. يُلغي التكرار.
    # ─────────────────────────────────────────────────────────────────────────
    _CONCEPT_AR: ClassVar[dict[str, str]] = {
        "numerator": "البسط (الحالات الملائمة)",
        "denominator": "المقام (كل الطرق الممكنة)",
        "ratio": "النسبة بين البسط والمقام",
        "combinations": "التوافيق (الاختيار دون ترتيب)",
        "color_red": "تأليفات الكرات الحمراء",
        "color_green": "تأليفات الكرات الخضراء",
        "color_white": "استحالة 3 كرات بيضاء",
        "event_meaning": "معنى الحادثة A (3 من نفس اللون)",
        "full_solution": "الحل الكامل خطوة بخطوة",
    }
    _MISCONCEPTION_AR: ClassVar[dict[str, str]] = {
        "sample_space_confusion": "يخلط بين البسط (الحالات الملائمة) والمقام (كل الطرق)",
        "fraction_meaning_confusion": "لا يفهم معنى النسبة (البسط مقسوم على المقام)",
        "order_vs_selection_confusion": "يظن أن ترتيب السحب مهمّ بينما هو اختيار فقط",
        "favourable_outcomes_confusion": "لا يفهم ما الذي «ينجح» ويحقّق الشرط",
        "none": "غير محدّد",
    }

    @staticmethod
    def _symbolic_facts_brief(combo) -> str:
        """D-128: حقائق رمزية مُختصرة (المعطيات + تعريف الحدث) — بلا الجواب النهائي.

        نحقن المعطيات (عدد كل لون) + تعريف الحادثة A فقط؛ **لا** نحقن 14/165 (النتائج
        المحسوبة) كي لا يكشفها الـ LLM — الطالب يُقاد لاكتشافها سقراطياً.
        """
        parts = [f"الكيس فيه {combo.n} كرة، نسحب {combo.k} دفعةً واحدة"]
        for g in combo.groups:
            parts.append(f"{g.label}: {g.count}")
        parts.append("الحادثة A = 3 كرات من نفس اللون")
        return "؛ ".join(parts)

    @staticmethod
    def _balls_brief(combo) -> str:
        """D-133: معطيات الكيس **محايدة للمفهوم** (ألوان + أعداد بلا تعريف الحادثة A).

        تُستخدم لإثراء رد الحيرة وللمثال الملموس لأي مفهوم — لا A-bias (تعميم لا special-casing).
        """
        colors = "، ".join(f"{g.label}: {g.count}" for g in combo.groups)
        return f"الكيس فيه {combo.n} كرة (نسحب {combo.k} دفعةً واحدة): {colors}"

    @classmethod
    async def _generate_guiding_question(
        cls,
        concept: str,
        balls: str,
    ) -> str | None:
        """D-133: سؤال موجِّه واحد محروس **عام لأي مفهوم** (لإثراء رد الحيرة).

        الـ LLM = مُفسِّر/موجِّه لا حَكَم: يولّد سؤالاً يقود الطالب لتطبيق المفهوم على معطيات
        الكيس — لا يحسب، لا يكشف نتيجة. محروس بنفس طبقات D-128 + timeout + fallback ⇒ None.
        """
        try:
            import asyncio
            import re as _re

            from app.core.ai_gateway import get_ai_client

            system_prompt = (
                "أنت معلّم تربوي جزائري. ولّد **سؤالاً واحداً** يقود الطالب لتطبيق المفهوم على "
                "معطيات الكيس — لا تشرح، لا تحسب، لا تكشف أي نتيجة نهائية أو كسر (مثل 14/165). "
                "عربية فصحى، جملة واحدة قصيرة تنتهي بعلامة استفهام."
            )
            user = (
                f"المفهوم: {cls._CONCEPT_AR.get(concept, concept)}.\n"
                f"معطيات الكيس (استخدمها فقط): {balls}\n"
                "ولّد سؤالاً واحداً يطبّق المفهوم على هذه المعطيات."
            )
            raw = await asyncio.wait_for(
                get_ai_client().send_message(system_prompt, user, temperature=0.5),
                timeout=10.0,
            )
            if not raw or not isinstance(raw, str) or not raw.strip():
                return None

            from app.services.skills.answer_redaction_skill import redact_final_answers
            from app.services.skills.arabic_stream_guard import is_probably_non_arabic
            from app.services.skills.content_integrity_skill import _strip_garbage_markers

            text = _strip_garbage_markers(raw.strip())
            text, _ = redact_final_answers(text, support_level=5)
            text = text.strip()
            if not text or is_probably_non_arabic(text):
                return None
            if _re.search(r"14\s*/\s*165|56\s*/\s*165", text):
                return None
            return text
        except Exception:  # pragma: no cover — fail-safe
            return None

    @classmethod
    def _build_concrete_example(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
    ) -> str | None:
        """D-133 (intent=example_request): **مثال ملموس قبل النظرية** — حتمي.

        المعطيات الملموسة من المحرك الرمزي (الكيس الفعلي) لا LLM. يَنجو من حجب D-113
        (لا نتيجة نهائية). يُرجِع None لغير الاحتمالات.
        """
        combo = cls._load_canonical_combinations(question, history_messages)
        if combo is None:
            return None
        balls = cls._balls_brief(combo)
        return (
            f"لنبدأ بمثال ملموس من هذا التمرين قبل أي قاعدة:\n\n"
            f"{balls}.\n\n"
            f"تخيّل سحبة واحدة: نأخذ {combo.k} كرات معاً وننظر إلى ألوانها وأرقامها — "
            f"هذا هو الموقف الذي نعمل عليه. أيّ حالة تريد أن نتتبّعها معاً خطوة بخطوة؟"
        )

    @classmethod
    async def _build_concept_example(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
    ) -> str | None:
        """D-136: مثال **واعٍ بالمفهوم النشط** (لا مثال الحادثة A الأعمى الافتراضي).

        المفهوم من السياق (`detect_active_concept`): «اعطني مثال» بعد تعريف product_even ⇒ مثال
        product_even. deterministic أولاً (`PropertySpec.example`)؛ إن عُرِض المثال already ⇒ زاوية
        مختلفة (LLM محروس) — لا تكرار. يُرجِع None إن لا مفهوم نشط (يسقط للمعالج العام).
        """
        try:
            from app.services.skills.semantic_property_skill import get_semantic_property_skill

            concept = get_semantic_property_skill().detect_active_concept(
                question, history_messages
            )
            if concept is None or not concept.example:
                return None
            shown = " ".join(
                str(m.get("content", ""))
                for m in (history_messages or [])
                if isinstance(m, dict) and m.get("role") == "assistant"
            )
            already = concept.example[:40] in shown  # نفس المثال عُرِض already؟
            if not already:
                return f"## مثال ملموس\n\n{concept.example}"
            # تكرار ⇒ زاوية مختلفة (LLM محروس)؛ fallback للمثال الحتمي خير من مثال أعمى.
            alt = await cls._generate_concept_example_llm(concept, question, history_messages)
            return alt or f"مثال آخر للتوضيح:\n\n{concept.example}"
        except Exception:  # pragma: no cover — fail-safe
            return None

    @classmethod
    async def _generate_concept_example_llm(
        cls,
        concept,
        question: str,
        history_messages: list[dict[str, str]] | None,
    ) -> str | None:
        """D-136: مثال بديل (زاوية مختلفة) للمفهوم — LLM محروس. LLM = التدريس، symbolic = الأرقام.

        يُستدعى فقط عند تكرار المثال الحتمي. محروس بنفس طبقات D-128 + timeout + fallback ⇒ None.
        """
        try:
            import asyncio
            import re as _re

            from app.core.ai_gateway import get_ai_client

            combo = cls._load_canonical_combinations(question, history_messages)
            facts = cls._balls_brief(combo) if combo is not None else ""
            system_prompt = (
                "أنت معلّم رياضيات جزائري. أعطِ **مثالاً ملموساً واحداً مختلفاً** يوضّح المفهوم "
                "باستخدام معطيات هذا التمرين. لا تشرح القاعدة، لا تحسب نتيجة نهائية، ولا تذكر أي "
                "كسر نهائي (مثل 14/165). عربية فصحى، جملتان كحدّ أقصى."
            )
            user = (
                f"المفهوم: {concept.title}\n"
                f"تعريفه: {concept.definition}\n"
                f"معطيات التمرين (استخدمها): {facts}\n"
                f"مثال سبق عرضه (لا تُكرّره — غيّر الزاوية): {concept.example}\n"
                "أعطِ مثالاً ملموساً مختلفاً."
            )
            raw = await asyncio.wait_for(
                get_ai_client().send_message(system_prompt, user, temperature=0.5),
                timeout=10.0,
            )
            if not raw or not isinstance(raw, str) or not raw.strip():
                return None

            from app.services.skills.answer_redaction_skill import redact_final_answers
            from app.services.skills.arabic_stream_guard import is_probably_non_arabic
            from app.services.skills.content_integrity_skill import _strip_garbage_markers

            text = _strip_garbage_markers(raw.strip())
            text, _ = redact_final_answers(text, support_level=5)
            text = text.strip()
            if not text or is_probably_non_arabic(text):
                return None
            if _re.search(r"14\s*/\s*165|56\s*/\s*165", text):
                return None
            return f"مثال آخر:\n\n{text}"
        except Exception:  # pragma: no cover — fail-safe
            return None

    @classmethod
    async def _generate_socratic_narrative(
        cls,
        concept: str,
        misconception: str,
        question: str,
        history_messages: list[dict[str, str]] | None,
    ) -> str | None:
        """D-128: تدخّل سقراطي فريد مُولَّد بالـ LLM (محروس). يُرجِع None ⇒ القالب الحتمي.

        D-129: يُستدعى عندما تقرّر السياسة التربوية `socratic` (هي البوّابة الوحيدة الآن —
        لا بوّابة level داخلية). الـ LLM يُنتج الفهم (سؤال يقود الطالب)؛ الأرقام من المحرك
        الرمزي (محقونة). محروس بطبقات قائمة + timeout + fallback. أي فشل/كشف/garbage ⇒ None.
        """
        try:
            import asyncio
            import re as _re

            combo = cls._load_canonical_combinations(question, history_messages)
            if combo is None:
                return None

            facts = cls._symbolic_facts_brief(combo)
            prior_qs = " | ".join(
                str(m.get("content", ""))[:80]
                for m in (history_messages or [])[-8:]
                if isinstance(m, dict) and m.get("role") == "user"
            )
            from app.core.ai_gateway import get_ai_client

            system_prompt = (
                "أنت معلّم سقراطي تربوي جزائري. مهمتك توليد **سؤال واحد** يقود الطالب — لا الحل. "
                "ممنوع منعاً باتاً كشف الجواب النهائي أو أي كسر نهائي (مثل 14/165 أو 56/165). "
                "ممنوع الحساب. استخدم الأرقام المعطاة في «الحقائق» فقط ولا تخترع غيرها. الطالب "
                "عالق وكرّر سؤاله — غيّر الزاوية ولا تُعِد ما قيل. عربية فصحى فقط، جملة أو جملتان، "
                "أقل من 50 كلمة، وتنتهي بعلامة استفهام."
            )
            user = (
                f"المفهوم: {cls._CONCEPT_AR.get(concept, concept)}.\n"
                f"المفهوم الخاطئ عند الطالب: {cls._MISCONCEPTION_AR.get(misconception, '')}.\n"
                f"الحقائق (لا تُغيّرها ولا تتجاوزها): {facts}\n"
                f"أسئلة الطالب السابقة: {prior_qs}\n"
                "ولّد سؤالاً سقراطياً واحداً جديداً يكشف النقطة العالقة (لا تكرار)."
            )
            raw = await asyncio.wait_for(
                get_ai_client().send_message(system_prompt, user, temperature=0.6),
                timeout=12.0,
            )
            if not raw or not isinstance(raw, str) or not raw.strip():
                return None
            text = raw.strip()

            # ── الحراسة (طبقات قائمة) ──────────────────────────────────────────
            from app.services.skills.answer_redaction_skill import redact_final_answers
            from app.services.skills.arabic_stream_guard import is_probably_non_arabic
            from app.services.skills.content_integrity_skill import _strip_garbage_markers

            text = _strip_garbage_markers(text)
            text, _ = redact_final_answers(text, support_level=5)
            text = text.strip()
            if not text or is_probably_non_arabic(text):
                return None
            # رفض إن كشف الكسر النهائي رغم الحجب (شبكة أمان أخيرة).
            if _re.search(r"14\s*/\s*165|56\s*/\s*165", text):
                return None
            return text
        except Exception:
            logger.warning("_generate_socratic_narrative_failed", exc_info=True)
            return None

    @classmethod
    def _build_symbolic_reveal(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
        *,
        acknowledge: bool = False,
        delivered: set[str] | None = None,
    ) -> str | None:
        """D-129: الحلّ الرمزي المتدرّج — الإنقاذ التربوي بعد استنفاد السقراطية (الطبقة 4).

        حتمي تماماً (من المحرك الرمزي). يُسبَق باعتراف عند ``acknowledge``. يَنجو من حجب
        D-113 (نمط ``_fmt_comb`` + «من كل»). يُرجِع None لغير الاحتمالات.

        D-158: ``delivered`` (اختياري) — مجموعة مفاتيح الخطوات المعروضة سابقاً (من
        ``kc_progress.representations_delivered`` الدائم). عند تمريرها، تُحذف الكتلة
        المعروضة مسبقاً (numerator/denominator) فلا يُعاد التفريغ عبر الأدوار (يقتل S1
        بنيوياً). الافتراضي (None) مطابق بايتياً للسلوك السابق (كل الكتل).
        """
        combo = cls._load_canonical_combinations(question, history_messages)
        if combo is None:
            return None
        n, k, total, same = (
            combo.n,
            combo.k,
            combo.total_combinations,
            combo.same_group_favorable,
        )
        favs_lines = "\n".join(
            (
                f"- {g.label} (العدد {g.count}): {cls._fmt_comb(g.count, k, g.favorable_combinations)}"
                if g.is_possible
                else f"- {g.label} (العدد {g.count}): مستحيلة (أقل من {k})"
            )
            for g in combo.groups
        )
        favs_sum = " + ".join(str(g.favorable_combinations) for g in combo.groups if g.is_possible)
        prefix = "إجابتك في الطريق الصحيح — " if acknowledge else ""
        # ISS-121 (D-154): صفر كشف للنتيجة النهائية (roadmap §7) — الإنقاذ يقدّم
        # كل المكوّنات (scaffold مشروع — D-129) لكن **تركيب النسبة النهائية يولّده
        # الطالب بنفسه** (generation effect؛ «التلميح قبل الحل»). ممنوع طباعة
        # «فاحتمال الحادثة A هو X من كل Y».
        _d = delivered or set()
        num_block = (
            f"**الحالات الملائمة** (3 كرات من نفس اللون) — لكل لون:\n\n"
            f"{favs_lines}\n\n"
            f"نجمع الحالات الممكنة فقط: ${favs_sum} = {same}$\n\n"
        )
        den_block = f"**كل الطرق الممكنة** لسحب {k} من {n}:\n\n{cls._fmt_comb(n, k, total)}\n\n"
        body = f"{prefix}لنُكمل معاً خطوة بخطوة حتى النهاية:\n\n"
        if "numerator" not in _d:
            body += num_block
        if "ratio" not in _d and "denominator" not in _d:
            body += den_block
        body += (
            "الآن أمامك كل المكوّنات — ركّب الاحتمال **بنفسك**: البسط على المقام. "
            "فما قيمة P(A) التي تحصل عليها؟"
        )
        return body

    @classmethod
    def _in_socratic_dialogue(
        cls, question: str, history_messages: list[dict[str, str]] | None
    ) -> bool:
        """D-130: هل نحن وسط حوار سقراطي والطالب يُجيب سؤالنا السقراطي؟

        قفل الحالة عبر التاريخ (لا حقل دائم): أحدث رسالة مساعد سؤال سقراطي طرحناه
        (تنتهي بـ«؟»، ليست إفراغ تمرين)، ضمن سياق احتمالات، ورسالة الطالب الحالية
        إجابة (فعل كلامي لا طول — `is_response_to_socratic`، تحسين A). حارس تبديل
        الموضوع (D-101) داخل `is_response_to_socratic`.
        """
        try:
            from app.services.skills.pedagogical_policy_skill import is_response_to_socratic

            # أحدث رسالة مساعد يجب أن تكون سؤالاً سقراطياً (لا إفراغ تمرين).
            last_assistant = None
            for msg in reversed(history_messages or []):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    last_assistant = str(msg.get("content", "")).strip()
                    break
            if not last_assistant:
                return False
            # D-137: السؤال السقراطي قد ينتهي بأمر («...A؟ أعطني مثالاً») — نكشف «؟» في أي
            # موضع (لا endswith فقط) وإلا تُهمَل إجابة الطالب (كارثة الخيانة البيداغوجية).
            if "؟" not in last_assistant and "?" not in last_assistant:
                return False
            # تمييز السؤال السقراطي من إفراغ تمرين يحوي صدفةً «؟».
            if len(last_assistant) > 600 or any(
                m in last_assistant
                for m in ("التمرين الأول", "يحتوي كيس على", "احسب احتمال الحادثة")
            ):
                return False
            # سياق احتمالات (الحوار عن تمرين الاحتمالات).
            _hist_text = " ".join(
                str(m.get("content", "")) for m in (history_messages or []) if isinstance(m, dict)
            )
            if not cls._is_prob_context(question + " " + _hist_text):
                return False
            # رسالة الطالب الحالية إجابة (مستقل عن الطول، حارس تبديل الموضوع داخله).
            return is_response_to_socratic(question, history_messages)
        except Exception:  # pragma: no cover - fail-safe
            logger.warning("_in_socratic_dialogue_failed", exc_info=True)
            return False

    @classmethod
    def _is_short_answer_in_dialogue(
        cls, question: str, history_messages: list[dict[str, str]] | None
    ) -> bool:
        """D-135: إجابة قصيرة وسط حوار تمرين نشط (تلميح/شرح سابق، **لا «؟» شرط**)؟

        يمنع إعادة طباعة التمرين على إجابة الطالب الصحيحة («اللون الأحمر والأخضر فقط») — تُترَك
        لمحرّك حالة الفهم (D-135) ليُقيّمها كبرهان فهم ويتقدّم. حارس تبديل الموضوع (D-101) داخله.
        """
        try:
            norm = (question or "").strip()
            if not norm or len(norm.split()) > 8:  # الإجابات قصيرة؛ الطلبات الجديدة أطول
                return False
            _low = norm.lower()
            if any(
                m in _low
                for m in (
                    "اعطني",
                    "أعطني",
                    "اعطيني",
                    "هات",
                    "اكتب",
                    "ارسم",
                    "تمرين",
                    "مسألة",
                    "درس",
                )
            ):
                return False  # طلب محتوى/تمرين جديد صريح — ليس إجابة
            last_assistant = None
            for msg in reversed(history_messages or []):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    last_assistant = str(msg.get("content", "")).strip()
                    break
            if not last_assistant:
                return False
            if len(last_assistant) > 600 or "يحتوي كيس على" in last_assistant:
                return False  # آخر رسالة كانت إفراغ التمرين نفسه — ليست حوار تدريس
            _hist_text = " ".join(
                str(m.get("content", "")) for m in (history_messages or []) if isinstance(m, dict)
            )
            if not cls._is_prob_context(question + " " + _hist_text):
                return False
            from app.services.capabilities.arabic_normalize import primary_canonical_topic

            _topic = primary_canonical_topic(question)
            return not (_topic is not None and _topic.canonical_id != "probability")
        except Exception:  # pragma: no cover - fail-safe
            return False

    @classmethod
    def _build_symbolic_step(cls, combo, focus: str | None, *, acknowledge: bool = False) -> str:
        """D-130: الخطوة الرمزية المتدرّجة (التسليم الرمزي) — حتمية من المحرك الرمزي.

        عند فهم الطالب: نكشف **خطوة المفهوم الحالي** + سؤال المتابعة، لا الحل كاملاً
        (يُبقي السُّلّم السقراطي حياً، يحترم مثال المالك «C(4,3)+C(5,3)=14»). يَنجو من
        حجب D-113 (نمط `_fmt_comb` + «من كل»).
        """
        prefix = "إجابتك في الطريق الصحيح — " if acknowledge else ""
        n, k, total = combo.n, combo.k, combo.total_combinations
        # خطوة البسط (الحالات الملائمة): الافتراضي والأكثر شيوعاً بعد فهم «نفس اللون».
        if focus in (None, "denominator", "numerator", "event_meaning"):
            favs_lines = "\n".join(
                (
                    f"- {g.label}: {cls._fmt_comb(g.count, k, g.favorable_combinations)}"
                    if g.is_possible
                    else f"- {g.label}: مستحيلة (أقل من {k})"
                )
                for g in combo.groups
            )
            favs_sum = " + ".join(
                str(g.favorable_combinations) for g in combo.groups if g.is_possible
            )
            same = combo.same_group_favorable
            return (
                f"{prefix}بما أننا اقتصرنا على الألوان الممكنة، نحسب **الحالات الملائمة**:\n\n"
                f"{favs_lines}\n\n"
                f"نجمعها: {favs_sum} = {same}\n\n"
                f"والآن سؤالٌ يقودنا للخطوة التالية: كم عدد **كل** الطرق الممكنة لسحب {k} كرات من {n}؟"
            )
        # خطوة المقام (كل الطرق).
        if focus == "ratio":
            return (
                f"{prefix}**كل الطرق الممكنة** لسحب {k} من {n}:\n\n"
                f"{cls._fmt_comb(n, k, total)}\n\n"
                f"الآن لديك البسط والمقام — كيف تُكوّن منهما الاحتمال؟"
            )
        # افتراضي: الحلّ الرمزي الكامل المتدرّج (fallback).
        return cls._build_symbolic_reveal("", None, acknowledge=acknowledge) or (
            f"{prefix}لنُكمل معاً خطوةً بخطوة."
        )

    #: D-158: مُعرّف المكوّن المعرفي لمسار الحادثة A (نفس اللون) في tutor_state.kc_progress.
    _KC_PROB_A: str = "prob_event_a"
    #: D-159 (WP-E): مُعرّف مكوّن الحادثة B (جداء الأرقام فردي) — المحرّك متعدد العُقد.
    _KC_PROB_B: str = "prob_event_b"

    @classmethod
    def _load_canonical_parity(
        cls, _question: str, history_messages: list[dict[str, str]] | None
    ) -> dict[str, int] | None:
        """D-159 (WP-E): توزيع أرقام كرات التمرين الرسمي (odd/even/zero/total) — حتمي.

        يقرأ **أسئلة-فقط** (مناعة ISS-120) ويستخدم `number_parity_counts` (D-143) —
        صفر LLM؛ يُغذّي عقدة الحادثة B في محرّك الدور. None عند تعذّر أي خطوة (fail-open).
        """
        try:
            from app.services.capabilities.exercise_retrieval import (
                ExerciseRetrievalRequest,
                detect_exercise_retrieval,
                load_exercise_questions_only,
            )
            from app.services.skills.probability_skill import ProbabilityCalculatorSkill

            _decision = detect_exercise_retrieval(
                ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024"),
                history_messages=history_messages,
            )
            if not (_decision.recognized and _decision.matched_entry):
                return None
            _official = load_exercise_questions_only(_decision.matched_entry)
            if not _official:
                return None
            return ProbabilityCalculatorSkill.number_parity_counts(_official)
        except Exception:  # pragma: no cover - fail-safe
            logger.warning("_load_canonical_parity_failed", exc_info=True)
            return None
