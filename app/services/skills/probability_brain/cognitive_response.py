"""D-127 (الطبقة 4) — الاستجابة المدفوعة بالمفهوم + التصعيد السقراطي المضاد للتكرار — مستخرَج حرفياً من `probability_tutor_brain.py` (D-168).

جزء من تركيبة `ProbabilityTutorBrain` (mixin) — كل `cls._x` تُحل عبر الـ MRO المُركَّب.
**ممنوع** الاستيراد من `microservices/` هنا؛ والأرقام من المحرك الرمزي حصراً.
"""

from __future__ import annotations

import logging

# نفس اسم الـ logger القديم عمداً — استمرارية السجلات وصفر تغيير رصدي (D-163/D-168).
logger = logging.getLogger("orchestrator-client")


class CognitiveResponseMixin:
    @classmethod
    def _build_cognitive_response(
        cls,
        concept: str,
        misconception: str,
        question: str,
        history_messages: list[dict[str, str]] | None,
    ) -> str | None:
        """D-127: الطبقة 4 — استجابة مدفوعة بالمفهوم + تصعيد سقراطي (شرح→سؤال→تشخيص).

        المستوى من عدد المرّات السابقة لنفس المفهوم (`_count_prior_concept`): مرّة1 شرح،
        مرّة2 سؤال سقراطي (حسب `misconception`)، مرّة3+ إعادة توجيه. الأرقام رمزية (الطبقة 3).
        يَنجو من حجب D-113. يُرجِع None لغير الاحتمالات أو مفهوم غير مدعوم.
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
        groups = list(combo.groups)
        possible = [g for g in groups if g.is_possible]
        favs_lines = "\n".join(
            (
                f"- {g.label}: {cls._fmt_comb(g.count, k, g.favorable_combinations)}"
                if g.is_possible
                else f"- {g.label}: مستحيل (العدد {g.count} أصغر من {k})"
            )
            for g in groups
        )
        favs_sum = " + ".join(str(g.favorable_combinations) for g in possible)
        level = cls._count_prior_concept(concept, history_messages)

        # ── numerator (البسط/14) ──────────────────────────────────────────────
        if concept == "numerator":
            if level == 0:
                return (
                    "## ما هو البسط؟\n\n"
                    "البسط هو عدد الطرق التي **تحقق الشرط المطلوب** (3 كرات من نفس اللون). "
                    "نعدّها لكل لون ممكن:\n\n"
                    f"{favs_lines}\n\n"
                    f"فالبسط = {favs_sum} = {same}: الحالات التي «تنجح» من بين كل الإمكانات."
                )
            if level == 1:
                if misconception == "sample_space_confusion":
                    return (
                        "شرحنا أن البسط هو الحالات التي تحقق الشرط. لنفرّقه عن المقام بسؤال:\n\n"
                        f"من بين كل الطرق الـ{total}، كم طريقة فقط تعطي 3 كرات من **نفس اللون**؟ "
                        "(لا تحسب — فكّر: أيّ الألوان يكفي عددها لذلك؟)"
                    )
                return (
                    "بدل أن أعيد الشرح، سؤال لك:\n\n"
                    "من الألوان الثلاثة (حمراء/خضراء/بيضاء)، أيّها يمكن أن يعطيك 3 كرات من نفس "
                    "اللون، وأيّها مستحيل؟ ولماذا؟"
                )
            return (
                "شرحنا البسط مرّتين — لنحدّد أين تحديداً تتعثّر. اختر حرفاً واحداً:\n\n"
                "(أ) معنى «الحالات الملائمة» نفسها\n"
                "(ب) لماذا اللون الأبيض مستحيل\n"
                f"(ج) لماذا نجمع {favs_sum} لنحصل على {same}\n\n"
                "أخبرني بالحرف وسأركّز معك على تلك النقطة وحدها."
            )

        # ── denominator (المقام/165) ──────────────────────────────────────────
        if concept == "denominator":
            if level == 0:
                return (
                    "## ما هو المقام؟\n\n"
                    f"المقام هو عدد **كل** الطرق الممكنة لسحب {k} كرات من {n} مهما كان لونها:\n\n"
                    f"{cls._fmt_comb(n, k, total)}\n\n"
                    "إنه ساحة كل ما يمكن أن يحدث — القاسم الذي نقسم عليه."
                )
            if level == 1:
                return (
                    "سؤال لك حتى نتأكّد من فهم المقام:\n\n"
                    f"عندما نسحب {k} كرات من {n}، هل عدد كل الاختيارات الممكنة يعتمد على "
                    "**ألوان** الكرات أم على **عددها** فقط؟"
                )
            return (
                "شرحنا المقام مرّتين. لنحدّد العقدة — اختر: (أ) لماذا نختار بالتوافيق لا "
                "بالترتيب، أم (ب) معنى «كل الطرق الممكنة»؟ أخبرني بالحرف."
            )

        # ── ratio (العلاقة/الفرق) ─────────────────────────────────────────────
        if concept == "ratio":
            if level == 0:
                return cls._format_conceptual_relationship(question, n, k, total, same, groups)
            if level == 1:
                return (
                    "شرحنا العلاقة. سؤال لك:\n\n"
                    f"لو كان البسط {same} والمقام {total}، فهل يكبر الاحتمال كلما كبر **البسط** "
                    "أم كلما كبر **المقام**؟ ولماذا؟"
                )
            return (
                "لنحدّد العقدة في معنى النسبة — اختر: (أ) معنى «من بين»، (ب) لماذا البسط فوق "
                "والمقام تحت، (ج) ماذا يعني أن الاحتمال بين 0 و1؟ أخبرني بالحرف."
            )

        # ── الألوان ───────────────────────────────────────────────────────────
        if concept in ("color_red", "color_green", "color_white"):
            color = {"color_red": "red", "color_green": "green", "color_white": "white"}[concept]
            g = next((x for x in groups if (x.color or "") == color), None)
            if g is not None:
                if level == 0:
                    if g.is_possible:
                        return (
                            f"## تأليفات {g.label}\n\n"
                            f"عدد {g.label}: {g.count}، نختار منها {k}:\n\n"
                            f"{cls._fmt_comb(g.count, k, g.favorable_combinations)}\n\n"
                            f"أي {g.favorable_combinations} طريقة — إحدى مكوّنات البسط."
                        )
                    return (
                        f"## لماذا {g.label} مستحيلة؟\n\n"
                        f"عددها {g.count} فقط، ونحتاج اختيار {k}. بما أن {g.count} أصغر من {k}، "
                        "لا يمكن سحب 3 منها معاً — لذلك لا تساهم في البسط."
                    )
                if level == 1:
                    return (
                        f"سؤال لك عن {g.label}: لماذا نستخدم التوافيق C لا الترتيب عند عدّ "
                        f"اختيار {k} كرات منها؟ (تلميح: هل يهمّنا ترتيب سحبها؟)"
                    )
                return (
                    f"شرحنا {g.label} مرّتين. أين العقدة — في الصيغة C أم في معنى «اختيار دون "
                    "ترتيب»؟ أخبرني."
                )

        # ── event_meaning (معنى الحادثة A/B/C/D) — D-131/D-132: الطبقة الدلالية العامة ──
        # نداء واحد للطبقة الدلالية (data-driven، لا special-casing لكل حادثة). يُغطّي
        # «جداء معدوم/فردي/زوجي» + «نفس اللون» عبر PROPERTY_REGISTRY.
        # D-132: لا default مُجمَّد لـ same_color — الافتراض A فقط لسؤال «الحادثة» الصريح؛
        # المفاهيم غير الحدثية (المتغير العشوائي/الأمل/...) يلتقطها preempt التعريف في
        # chat_with_agent عبر interpret_or_define قبل الوصول هنا.
        if concept == "event_meaning":
            if level == 0:
                from app.services.skills.semantic_property_skill import (
                    PROPERTY_REGISTRY,
                    get_semantic_property_skill,
                )
                from app.services.skills.tutor_metrics import record_definitional_answer

                _sp = get_semantic_property_skill().interpret(question)
                if _sp is not None:
                    record_definitional_answer(_sp.concept_id, resolved=True)
                    return f"## {_sp.title}\n\n{_sp.definition}"
                # D-132: الافتراض A **فقط** عند سؤال حدثي صريح (الحادثة/الحدث/A).
                _q = (question or "").lower()
                if any(m in _q for m in ("الحادثة", "الحدث", "a", "نفس اللون")):
                    _spec = PROPERTY_REGISTRY["same_color"]
                    record_definitional_answer(_spec.concept_id, resolved=True)
                    return f"## {_spec.title}\n\n{_spec.definition}"
                return None  # مفهوم غير معروف غير حدثي ⇒ لا نُقحمه في الحادثة A
            # level >= 1 ⇒ يُستبدَل بالسرد السقراطي المُولَّد (chat_with_agent)؛ هذا fallback.
            return (
                "الحادثة A تعني «3 كرات من نفس اللون». سؤال لك: لو سحبت 3 كرات، متى تقول إنها "
                "«نجحت» وحقّقت A، ومتى تقول إنها فشلت؟ أعطني مثالاً من عندك."
            )

        # ── combinations (معنى الرمز C نفسه) — D-185 (ISS-138) ────────────────
        # القيمة `combinations` موجودة في enum المفاهيم و`PROPERTY_REGISTRY` منذ D-162،
        # لكن لم يكن لها فرع هنا إطلاقاً ⇒ `return None` صامتة (قيمة enum ميتة) ⇒ الدور
        # يسقط إلى إفراغ الحل الكامل. التعريف **ليس إجابة**: نشرح الرمز بمثال محايد
        # ولا نكشف أرقام التمرين الجاري (D-113).
        if concept == "combinations":
            from app.services.skills.notation_skill import get_notation_skill
            from app.services.skills.tutor_metrics import record_definitional_answer

            _entry = get_notation_skill().define("C(n,k)")
            if _entry is not None:
                record_definitional_answer("combinations", resolved=True)
                if level == 0:
                    return f"## {_entry.title}\n\n{_entry.definition}\n\n{_entry.example}"
                return (
                    f"{_entry.example}\n\nسؤال لك حتى نتأكّد أنّ الفكرة رسخت: لو كان "
                    "الترتيب **يهمّ** (سحبنا الكرات واحدةً تلو الأخرى)، هل تتوقّع عدد "
                    "الطرق أكبر أم أصغر؟ ولماذا؟"
                )

        # ── full_solution / حيرة عامة ─────────────────────────────────────────
        if concept == "full_solution":
            if level == 0:
                return (
                    "## الحل الكامل خطوة بخطوة\n\n"
                    f"1) فضاء العينة — نسحب {k} كرات من {n} دفعةً واحدة:\n\n"
                    f"   {cls._fmt_comb(n, k, total)}\n\n"
                    "2) الحالات الملائمة (3 كرات من نفس اللون) — لكل لون:\n\n"
                    f"{favs_lines}\n\n"
                    f"3) نجمع الممكنة: {favs_sum} = {same}\n\n"
                    f"4) الاحتمال = {same} من كل {total}."
                )
            # level >= 1 ⇒ يُستبدَل بالسرد السقراطي المُولَّد (chat_with_agent)؛ هذا fallback.
            #
            # D-186 (ISS-139، مكشوف بالتحقّق الحيّ E2E): كانت بنود القائمة تحمل **قيم
            # التمرين** (`{total}` = 165 و`{same}` = 14). فسؤالٌ غرضه *تحديد موضع
            # التعثّر* كان يُسلّم الطالبَ الجوابَ الذي يُفترض أن يشتقّه — تسريب D-113
            # من باب التشخيص نفسه. البنود الآن تُسمّي الأجزاء بلا أي قيمة.
            #
            # ولا نزعم «شرحنا الحل كاملاً»: قد نصل هنا دون أن يكون الحل عُرض أصلاً
            # (ما حدث حيّاً)، وادّعاء شرحٍ لم يقع يُشعر الطالب بأن التقصير منه.
            return (
                "لنحدّد أين تحديداً تعثّرت بدل إعادة الشرح كلّه — اختر حرفاً:\n\n"
                "(أ) فضاء العينة — كيف نعدّ **كل** الطرق الممكنة\n"
                "(ب) الحالات الملائمة — كيف نعدّ الطرق التي تحقّق الحادثة\n"
                "(ج) معنى الاحتمال نفسه — البسط على المقام\n\n"
                "أخبرني بالحرف وسأركّز على تلك النقطة وحدها."
            )

        return None
