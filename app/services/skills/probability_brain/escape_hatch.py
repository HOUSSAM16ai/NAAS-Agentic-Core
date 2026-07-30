"""D-124/D-125/D-160/D-162/D-165 — مخرج الطوارئ الحتمي: الكواشف + الشرح المباشر + المسار الحسابي — مستخرَج حرفياً من `probability_tutor_brain.py` (D-168).

جزء من تركيبة `ProbabilityTutorBrain` (mixin) — كل `cls._x` تُحل عبر الـ MRO المُركَّب.
**ممنوع** الاستيراد من `microservices/` هنا؛ والأرقام من المحرك الرمزي حصراً.
"""

from __future__ import annotations

import contextlib
import logging
import re
from typing import ClassVar

from shared.intent import markers_for

# نفس اسم الـ logger القديم عمداً — استمرارية السجلات وصفر تغيير رصدي (D-163/D-168).
logger = logging.getLogger("orchestrator-client")


class EscapeHatchMixin:
    """عقل الاحتمالات الحتمي المشترك — يُستهلك حصراً بوراثة `OrchestratorClient`."""

    # D-124 — مخرج الطوارئ الحتمي (Deterministic Escape Hatch):
    # كسر «حلقة الموت اللانهائية». بعد D-116/D-123 صار كل سؤال احتمالات يُنهي
    # دائماً إلى الكاروسيل البصري (terminate=True، صفر LLM). النتيجة الكارثية:
    # سؤال محدّد («كيف وجدنا 4 الحمراء؟») أو حيرة متكررة («لم أفهم»×N) يُعيدان
    # طباعة **نفس الكاروسيل** بلا تقدّم ولا إجابة — الطالب محاصَر. الحل (تشخيص
    # المالك CTO-grade): عداد محاولات + مخرج طوارئ ⇒ سؤال محدّد (فوراً) أو حيرة
    # ≥ 2 يكسران الكاروسيل ويقدّمان **شرحاً رياضياً مباشراً حتمياً** (محسوباً من
    # التمرين الرسمي عبر ProbabilityCalculatorSkill، history=None — D-123 — صفر
    # LLM، صفر هلوسة). استثناء مقصود ومُصرَّح من المالك لِـ doctrine السقراطي
    # (D-113/D-115): الطالب العالق يستحق المثال المحلول لكسر الحلقة.
    # ─────────────────────────────────────────────────────────────────────────

    #: D-124: علامات الحيرة المتكررة — **بلا «كيف» المجرّدة** (تكسر «كيف افهم
    #: السؤال الأول» الأولى، وهي سؤال عام يستحق الكاروسيل لا الشرح المباشر).
    #: D-186: من المصدر القانوني الواحد — الحيرة **∪** طلب الشرح الصريح («أعد الشرح»
    #: أمرٌ لا حيرة، لكن هذا المسار يخدم الاثنين معاً كما كان تماماً).
    _PROBABILITY_CONFUSION_MARKERS: tuple[str, ...] = (
        *markers_for("confusion"),
        *markers_for("explanation_request"),
    )

    @classmethod
    def _count_probability_confusion(
        cls, question: str, history_messages: list[dict[str, str]] | None
    ) -> int:
        """يَعُدّ رسائل الطالب الدالة على حيرة متكررة (السؤال الحالي + سجل المحادثة).

        حتمي، بلا I/O — نمط ``customer_chat._count_confusion_signals``. تكرار
        الحيرة (≥2) ⇒ الطالب عالق بعد رؤية الكاروسيل ⇒ مخرج الطوارئ. **بلا «كيف»
        المجرّدة** (D-124) كي لا يُحسب «كيف افهم السؤال الأول» الأول كحيرة. الرسالة
        التي هي علامة استفهام صرفة («؟») تُحسب حيرةً (الطالب يكرّرها أمام الكاروسيل).

        ISS-140 — **الدور الحاضر لا يُحسَب مرّتين.** المونوليث يحفظ رسالة الطالب في
        قاعدة البيانات **قبل** بناء الدور (§6.5: الكاتب واحد عند مدخل الـWS)، فالتاريخ
        المُمرَّر هنا يحتوي نسخةً من ``question`` نفسه. فكان سؤالٌ واحد يُعَدّ **2** ⇒
        يجتاز شرط «الحيرة المتكررة (≥2)» في **أول رسالة**، فيُقسَر
        ``concept = full_solution`` ويُسحَب أي موضوع (فيزياء · كيمياء) إلى قائمة تشخيص
        الاحتمالات. بُرهن حياً: «اشرح لي قانون أوم» على حساب جديد ⇒ عدّاد 2 وردٌّ عن
        فضاء العينة. الشرط يعني «تكراراً» فعليّاً، فلا يجوز أن يستوفيه دورٌ واحد.
        """
        texts: list[str] = [str(question or "")]
        _current = str(question or "").strip()
        _seen_current = False
        for msg in history_messages or []:
            if isinstance(msg, dict) and msg.get("role") == "user":
                _content = str(msg.get("content") or "")
                # نتجاوز **نسخةً واحدة** من الدور الحاضر (المحفوظة قبل قليل)، ونُبقي أي
                # تكرار حقيقي سابق — فالطالب الذي يكتب «لم أفهم» مرّتين يجب أن يُعَدّ 2.
                if not _seen_current and _content.strip() == _current:
                    _seen_current = True
                    continue
                texts.append(_content)
        count = 0
        for text in texts:
            low = text.strip()
            if low in ("؟", "?", "؟؟", "??", "؟!", "!؟"):
                count += 1
                continue
            if any(marker in low for marker in cls._PROBABILITY_CONFUSION_MARKERS):
                count += 1
        return count

    @staticmethod
    def _detect_subpart_question(question: str) -> str | None:
        """يكشف سؤالاً محدّداً عن جزئية حسابية في تمرين الاحتمالات.

        يُرجِع: ``"red"``/``"green"``/``"white"`` (لون) | ``"total"`` (فضاء العينة
        C(11,3)) | ``"sum"`` (مجموع الحالات الملائمة 14) | ``None``. السؤال العام
        («كيف افهم السؤال الأول») ⇒ ``None`` (يبقى للكاروسيل البصري). D-124.
        """
        q = (question or "").lower()
        if any(m in q for m in ("حمراء", "الحمراء", "احمر", "الأحمر", "الاحمر", "حمر")):
            return "red"
        if any(m in q for m in ("خضراء", "الخضراء", "اخضر", "الأخضر", "الاخضر", "خضر")):
            return "green"
        if any(m in q for m in ("بيضاء", "البيضاء", "ابيض", "الأبيض", "الابيض", "بيض")):
            return "white"
        if any(m in q for m in ("165", "فضاء العينة", "العدد الكلي", "الفضاء", "c(11", "الكلي")):
            return "total"
        if any(
            m in q for m in ("14", "الملائمة", "الملاءمة", "نجمع", "لماذا نجمع", "الحالات الملائمة")
        ):
            return "sum"
        return None

    #: D-160 (ISS-126): علامات طلب شرح اشتقاق قيمة/خطوة («كيف حسبنا 4»، «اشرح كيف
    #: وصلنا لـ 10»، «من أين جاءت»). تُفرّق طلب الشرح عن محاولة الإجابة الرقمية.
    _STEP_EXPLAIN_MARKERS: tuple[str, ...] = (
        "كيف حسبنا",
        "كيف حسبت",
        "كيف نحسب",
        "كيف وجدنا",
        "كيف وصلنا",
        "كيف جاء",
        "من اين",
        "من أين",
        "اشرح",
        "اشرح لي",
        "وضح",
        "وضّح",
        "بين",
        "بيّن",
        "كيفاش",
        "علاش",
    )

    @classmethod
    def _detect_step_explanation(cls, question: str, combo) -> str | None:
        """D-160 (ISS-126): يكشف طلب شرح اشتقاق **خطوة/قيمة** ويربطه بجزئية.

        يحلّ الكارثة: «كيف حسبنا 4» (كيف اشتُقّت ``C(4,3)=4``) كان يسقط للإنقاذ النهائي
        المكرَّر لأن `_detect_subpart_question` يربط الألوان و14/165 **فقط** — لا القيم
        الملائمة 4/10. هذا الكاشف **data-driven** (يقرأ ``combo``، لا أرقاماً مُصلَّبة):
        يطابق أرقام السؤال ضد ``total_combinations``/``same_group_favorable`` وكل مجموعة
        (``favorable_combinations`` أو ``count``) ⇒ يعمل لأي تمرين لا هذا وحده.

        يُرجِع ``"red"``/``"green"``/``"white"``/``"total"``/``"sum"`` | ``None``. يشترط
        علامة شرح صريحة (`_STEP_EXPLAIN_MARKERS`) كي لا تُلتقَط محاولة إجابة رقمية
        («14 على 165» تبقى للتحقّق الرقمي S2، لا للشرح).
        """
        try:
            q = (question or "").lower()
            if not any(m in q for m in cls._STEP_EXPLAIN_MARKERS):
                return None
            # (أ) الكلمات اللونية / 14 / 165 — يعالجها الكاشف القائم مباشرةً.
            word_part = cls._detect_subpart_question(question)
            if word_part is not None:
                return word_part
            # (ب) مطابقة data-driven لأرقام السؤال ضد قيم combo.
            nums = {int(n) for n in re.findall(r"\d+", q)}
            if not nums:
                return None
            if int(getattr(combo, "total_combinations", -1)) in nums:
                return "total"
            if int(getattr(combo, "same_group_favorable", -1)) in nums:
                return "sum"
            for g in getattr(combo, "groups", []) or []:
                gfav = int(getattr(g, "favorable_combinations", -1))
                gcount = int(getattr(g, "count", -1))
                if gfav in nums or gcount in nums:
                    color = getattr(g, "color", None)
                    if color in ("red", "green", "white"):
                        return color
            return None
        except Exception:  # pragma: no cover - fail-safe
            return None

    @classmethod
    def _detect_naming_question(cls, question: str, combo) -> bool:
        """D-162 (ISS-128): يكشف سؤال التسمية عن قيم خطوات التمرين — data-driven.

        «ماذا نسمي حساب 4 و 10 لم افهمها؟» يطلب **اسم** العملية (التوافيق C(n,k))،
        لا نتيجتها. الشرط: علامة تسمية (`_NAMING_MARKERS`) **+** (أرقام السؤال ⊆
        قيم خطوات ``combo`` — favs/same/total/n/k/counts — **أو** ذكر الحساب/العملية).
        الأرقام من المحرك الرمزي حصراً ⇒ يعمل لأي تمرين (ملايير التمارين).
        """
        try:
            q = (question or "").lower()
            if not any(m in q for m in cls._NAMING_MARKERS):
                return False
            nums = cls._extract_answer_numbers(q)
            if nums:
                values = {
                    int(getattr(combo, "total_combinations", -1)),
                    int(getattr(combo, "same_group_favorable", -1)),
                    int(getattr(combo, "n", -1)),
                    int(getattr(combo, "k", -1)),
                }
                for g in getattr(combo, "groups", []) or []:
                    values.add(int(getattr(g, "favorable_combinations", -1)))
                    values.add(int(getattr(g, "count", -1)))
                return nums <= values
            return any(w in q for w in ("حساب", "الحساب", "العملية", "الطريقة", "c("))
        except Exception:  # pragma: no cover - fail-safe
            return False

    @classmethod
    def _build_naming_answer(cls, combo, pending_focus: str | None) -> str | None:
        """D-162 (ISS-128): يُجيب سؤال التسمية بالاسم — حتمي، صفر LLM.

        تعريف **التوافيق** من ``PROPERTY_REGISTRY["combinations"]`` (مصدر واحد —
        D-131 data-not-code) + ربط بقيمة واحدة عبر ``_fmt_comb`` (LaTeX، يَنجو من
        حجب D-113 بنيوياً — D-154) + **إعادة طرح السؤال المعلّق** (نصّه يطابق
        `_STEP_QUESTION_MARKERS` فيبقى pending مشتقاً صحيحاً) — لا تقدّم زائف.
        """
        try:
            definition = None
            with contextlib.suppress(Exception):
                from app.services.skills.semantic_property_skill import PROPERTY_REGISTRY

                _spec = PROPERTY_REGISTRY.get("combinations")
                definition = getattr(_spec, "definition", None) if _spec else None
            if not definition:
                definition = (
                    "هذا الحساب نسمّيه **التوافيق** (Combinations) ويُرمز له $C_{n}^{k}$: "
                    "عدد طرق اختيار k عناصر من بين n عنصراً **دون اهتمام بالترتيب**."
                )
            parts = [definition]
            _groups = [
                g for g in (getattr(combo, "groups", []) or []) if getattr(g, "is_possible", False)
            ]
            if _groups:
                _g0 = _groups[0]
                parts.append(
                    "مثلاً القيمة التي وجدناها لهذه المجموعة هي عدد التوافيق: "
                    + cls._fmt_comb(
                        int(_g0.count),
                        int(getattr(combo, "k", 3)),
                        int(_g0.favorable_combinations),
                    )
                )
            if pending_focus == "denominator":
                parts.append(
                    "والآن نعود لسؤالنا: كم عدد كل الطرق الممكنة لسحب "
                    f"{int(getattr(combo, 'k', 3))} كرات من {int(getattr(combo, 'n', 0))}؟"
                )
            elif pending_focus == "ratio":
                parts.append("والآن نعود لسؤالنا: لديك البسط والمقام — كيف تُكوّن منهما الاحتمال؟")
            return "\n\n".join(parts)
        except Exception:  # pragma: no cover - fail-safe
            return None

    #: D-125: أفعال إجرائية — «لماذا/ليش» معها تبقى سؤالاً حسابياً (قوالب D-124)،
    #: لا مفاهيمياً («لماذا نجمع»، «لماذا لا نحسب الأبيض»). تحفّظ المالك رقم 3.
    _PROCEDURAL_VERBS: tuple[str, ...] = (
        "نجمع",
        "نحسب",
        "نحسبها",
        "نضرب",
        "نستخرج",
        "نستخدم",
        "لا نحسب",
        "كيف وجدنا",
        "كيف حصلنا",
        "كيف نحسب",
    )

    @classmethod
    def _detect_conceptual_question(cls, question: str) -> bool:
        """D-125: هل السؤال مفاهيمي/مقارنة (يطلب المعنى/العلاقة لا خطوات الحساب)؟

        يحل «متلازمة الردود المعلبة»: «ما الفرق بين 165 و 14» يطلب العلاقة (البسط
        مقابل المقام)، لا حساب 165. أوسع من الكلمات الحرفية (تحفّظ المالك 1): يشمل
        الدارجة «ليش»/«علاش»، و«نفسر»/«المقصود»/«الناتج»/«نقسم/النسبة». «لماذا/ليش»
        + فعل إجرائي ⇒ ليس مفاهيمياً (تحفّظ 3)؛ أي علامة قوية ⇒ مفاهيمي حتى مع فعل
        إجرائي (الهجين، تحفّظ 2).
        """
        q = (question or "").lower()
        # علامات مفاهيمية قوية ⇒ مفاهيمي دائماً (تهزم حتى الأفعال الإجرائية — الهجين).
        strong = (
            "الفرق",
            "الاختلاف",
            "العلاقة",
            "الرابط",
            "مقارنة",
            "قارن",
            "ما يميز",
            "الهدف",
            "الغرض",
            "الغاية",
            "الفائدة",
            "ما فائدة",
            "فائدة",
            "ما معنى",
            "معنى",
            "ماذا يعني",
            "ماذا تعني",
            "المقصود",
            "ما المقصود",
            "نفسر",
            "التفسير",
            "كيف نفسر",
            "النسبة",
            "نقسم",
            "القسمة",
            "البسط والمقام",
            "بسط ومقام",
            # D-162 (ISS-128): نية التسمية («ماذا نسمي حساب 4 و 10؟») مفاهيمية —
            # الطالب يطلب اسم العملية (التوافيق)، لا خطوات الحساب.
            "نسمي",
            "ما اسم",
            "تسمية",
            # D-185 (ISS-138): صيغة الفعل «نقصد» كانت مفقودة بينما «معنى»/«المقصود»
            # حاضرتان — فسؤال الطالب الحرفي «ماذا نقصد بحرف C» لم يُعدّ مفاهيمياً هنا
            # بينما عدّته `_DEFINITIONAL_MARKERS` كذلك. اختلاف القوائم هو ما أسقط الدور.
            "نقصد",
            "ماذا نقصد",
            "يقصد",
        )
        if any(m in q for m in strong):
            return True
        # «ليش/لماذا» + رقم/مفهوم وبلا فعل إجرائي ⇒ مفاهيمي («ليش 14؟»). تحفّظ 3.
        why = ("ليش", "لماذا", "علاش", "وعلاش", "علاه")
        if any(w in q for w in why):
            if any(p in q for p in cls._PROCEDURAL_VERBS):
                return False
            concept_ref = ("14", "165", "الناتج", "البسط", "المقام")
            if any(c in q for c in concept_ref):
                return True
        return False

    #: D-165 (ISS-129): أفعال «الاستفادة/التعلّم» — غير ملتبسة، تكفي وحدها في سياق
    #: احتمالات («ماذا نستفيد من هذا التمرين؟» — transcript الكارثة الحرفي). صور
    #: مُطبَّعة عبر normalize_ar (ال محذوفة، الهمزات موحَّدة).
    _PURPOSE_VERB_MARKERS: ClassVar[tuple[str, ...]] = (
        "نستفيد",
        "استفيد",
        "نستافد",
        "يستفيد",
        "نتعلم",
        "اتعلم",
        "يعلمنا",
        "تعلمنا",
    )
    #: أسماء الغاية الملتبسة — تتطلب مرجع تمرين صريحاً («ما الهدف من التمرين»)؛
    #: بدونه تبقى لطبقة D-125 المفاهيمية («ما الهدف من 14» = علاقة البسط/المقام).
    _PURPOSE_NOUN_MARKERS: ClassVar[tuple[str, ...]] = (
        "هدف",
        "غرض",
        "غايه",
        "فايده",
        "اهميه",
    )
    _PURPOSE_EXERCISE_REFS: ClassVar[tuple[str, ...]] = ("تمرين", "درس")

    @classmethod
    def _detect_exercise_purpose_question(cls, question: str) -> bool:
        """D-165 (ISS-129): هل السؤال عن **غاية التمرين** («ماذا نستفيد/نتعلم منه؟»)؟

        سؤال meta عن الغاية التعليمية — كان يُختطف بالـ probe التشخيصي (S3) متجاهلاً
        السؤال كلياً (transcript الكارثة). حتمي: فعل استفادة/تعلّم يكفي وحده؛ اسم
        الغاية (هدف/فائدة/غرض) يتطلب مرجع «تمرين/درس» كي لا يبتلع أسئلة D-125
        المفاهيمية («ما الهدف من 14»).
        """
        try:
            from app.services.capabilities.arabic_normalize import normalize_ar

            norm = normalize_ar(question or "")
        except Exception:  # pragma: no cover - fail-safe
            norm = (question or "").strip().lower()
        if not norm:
            return False
        if any(v in norm for v in cls._PURPOSE_VERB_MARKERS):
            return True
        if any(n in norm for n in cls._PURPOSE_NOUN_MARKERS):
            return any(ref in norm for ref in cls._PURPOSE_EXERCISE_REFS)
        return False

    @classmethod
    def _build_exercise_purpose_answer(cls, combo) -> str | None:
        """D-165 (ISS-129): إجابة «غاية التمرين» الحتمية — من المكوّنات المعرفية.

        يفوّض إلى `UnderstandingStateSkill.exercise_purpose_summary` (DRY — الـ KCs
        تعيش هناك، D-135): غاية التمرين = مكوّناته المعرفية، مشتقة من combo الرمزي
        (data-driven — تعمل لأي تمرين). صفر LLM، بلا أي نسبة نهائية (تَنجو من حجب
        D-113 بنيوياً). fail-open ⇒ None (السؤال يهرب للـ LLM المحروس — D-112).
        """
        try:
            from app.services.skills.understanding_state_skill import (
                get_understanding_state_skill,
            )

            return get_understanding_state_skill().exercise_purpose_summary(combo)
        except Exception:  # pragma: no cover - fail-safe
            return None

    @staticmethod
    def _fmt_comb(c: int, k: int, fav: int) -> str:
        r"""يبني توسيع المضروب الحتمي بصيغة LaTeX (ISS-121 / D-154).

        مثال: ``_fmt_comb(4, 3, 4)`` ⇒ ``"$C_{4}^{3} = \dfrac{4\times 3\times 2}{3\times 2\times 1} = 4$"``.
        LaTeX ⇒ KaTeX يُصيّرها LTR-معزولة داخل فقرات RTL (يقتل بعثرة bidi التي
        شوّهت «(5×4×3)/(3×2×1)» على الهاتف)، وصيغة ``C_{n}^{k}`` (بلا قوسين بعد C)
        تَنجو بنيوياً من حجب D-113 (`_FINAL_RESULT_RE` يتطلب ``C(...)=عدد``).
        """
        if k < 1 or c < k:
            return f"$C_{{{c}}}^{{{k}}} = {fav}$"
        num = r"\times ".join(str(c - i) for i in range(k))
        den = r"\times ".join(str(k - i) for i in range(k))
        return f"$C_{{{c}}}^{{{k}}} = \\dfrac{{{num}}}{{{den}}} = {fav}$"

    @classmethod
    def _build_probability_direct_explanation(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
        *,
        forced_subpart: str | None = None,
    ) -> str | None:
        """D-124: شرح رياضي مباشر حتمي لتمرين الاحتمالات (يكسر حلقة الكاروسيل).

        D-160 (ISS-126): ``forced_subpart`` (اختياري) — يتجاوز `_detect_subpart_question`
        فيسمح لِـ `_cognitive_turn` بتوجيه الشرح لجزئية كشفها كاشف data-driven من قيمة
        السؤال (مثل «كيف حسبنا 4» ⇒ «red»)؛ يُعيد استخدام هذا الكود التعليمي كما هو.

        يُحمّل التمرين الرسمي المُفهرَس (D-123: ``history=None`` ⇒ مناعة من تلوّث
        الـ history)، يحلّله عبر ``ProbabilityCalculatorSkill`` (مخرَج
        ``CombinationsModelOutput``)، ثم يُنسِّق الجزئية المطلوبة (لون/فضاء/مجموع)
        أو الاشتقاق الكامل — **صفر LLM، صفر هلوسة**. يُرجِع ``None`` إن لم يكن تمرين
        احتمالات معروفاً (topic-safe) أو تعذّر الحساب. النصّ مُصمَّم لِيَنجو من حجب
        الإجابة (D-113): يتجنّب ``P(...)=عدد``/``\\boxed``/«النتيجة/إذن … = عدد».
        """
        # D-185 (ISS-138): **الرمز قبل كل شيء.** «ماذا نقصد بحرف C» سؤال عن معنى رمز،
        # فلا يجوز أن يُجاب باشتقاق ولا بعلاقة «165 و 14» ولا بشرح لونٍ مستحيل. التحقّق
        # الحيّ أثبت أنّ هذا المسار كان يُجيب عنه بجزئية اللون تارةً وبعلاقة الأرقام تارة
        # (وكلتاهما تسريب). الفحص هنا **قبل** تحميل التمرين وقبل كل الكاشفات، وحتمي بلا
        # أرقام التمرين إطلاقاً — فيبقى العقد السقراطي سليماً (D-113).
        try:
            from app.services.skills.notation_skill import get_notation_skill

            _symbol = get_notation_skill().resolve(question)
            if _symbol is not None:
                return f"## {_symbol.title}\n\n{_symbol.definition}\n\n{_symbol.example}"
        except Exception:  # pragma: no cover - fail-open: الرموز لا تكسر الدور
            pass

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

            # topic-safe: طلب موضوع آخر صريح (دوال/أعداد مركبة) ⇒ لا شرح احتمالات.
            _canonical = primary_canonical_topic(question)
            if _canonical is not None and _canonical.canonical_id != "probability":
                return None

            # تحميل التمرين الرسمي المُفهرَس (history-immune — D-123).
            # ISS-120 (D-153): أسئلة-فقط — نثر الحل النموذجي («تحمل الرقم 0 …
            # وعددها 3 كرات») يولِّد كياناً وهمياً يُفسد فضاء العينة (14 بدل 11).
            _decision = detect_exercise_retrieval(
                ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024"),
                history_messages=history_messages,
            )
            if not (_decision.recognized and _decision.matched_entry):
                return None
            _official = load_exercise_questions_only(_decision.matched_entry)
            if not _official:
                return None

            # تحليل حتمي من المحتوى الرسمي وحده (بلا سؤال الطالب ⇒ غير حائر ⇒
            # CombinationsModelOutput بالمجموعات، لا قصة بصرية deep_dive).
            skill = ProbabilityCalculatorSkill()
            result = skill.analyze(ProbabilityInput(question=_official, history=None))
            if not isinstance(result, CombinationsModelOutput):
                return None

            n = result.n
            k = result.k
            total = result.total_combinations
            groups = list(result.groups)
            same = result.same_group_favorable

            # D-125: السؤال المفاهيمي/المقارنة («ما الفرق بين 165 و 14»، «ما الهدف
            # من 14») يطلب **العلاقة** لا خطوات الحساب. يُفحَص **قبل** مطابقة الأرقام
            # كي لا يطبع قالب الحساب (متلازمة الردود المعلبة). يهزم مطابقة الأرقام دائماً.
            if cls._detect_conceptual_question(question):
                return cls._format_conceptual_relationship(question, n, k, total, same, groups)

            subpart = forced_subpart or cls._detect_subpart_question(question)

            def _group_for_color(color: str) -> object | None:
                for g in groups:
                    if (g.color or "") == color:
                        return g
                return None

            # ── جزئية لون واحد ────────────────────────────────────────────────
            if subpart in ("red", "green", "white"):
                g = _group_for_color(subpart)
                if g is not None:
                    if g.is_possible:
                        return (
                            f"## كيف نحسب تأليفات {g.label}\n\n"
                            f"عدد {g.label} في الكيس: {g.count}، ونريد اختيار {k} منها "
                            f"دفعةً واحدة (اختيار غير مرتّب). نطبّق قانون التوافيق:\n\n"
                            f"{cls._fmt_comb(g.count, k, g.favorable_combinations)}\n\n"
                            f"أي توجد {g.favorable_combinations} طريقة لاختيار {k} كرات "
                            f"من نفس هذا اللون — وهي إحدى مكوّنات الحالات الملائمة."
                        )
                    return (
                        f"## لماذا هذا اللون مستحيل\n\n"
                        f"عدد {g.label} في الكيس: {g.count}، ونحتاج اختيار {k}. بما أن "
                        f"{g.count} أصغر من {k}، لا يمكن سحب {k} كرات من هذا اللون معاً — "
                        f"لذلك عدد تأليفاته صفر، وهذا اللون لا يساهم في الحالات الملائمة."
                    )

            # ── فضاء العينة C(n,k) ────────────────────────────────────────────
            if subpart == "total":
                return (
                    f"## فضاء العينة C({n},{k})\n\n"
                    f"نسحب {k} كرات من {n} دفعةً واحدة. السحب الآني = اختيار غير مرتّب، "
                    f"فعدد كل الإمكانات هو:\n\n"
                    f"{cls._fmt_comb(n, k, total)}\n\n"
                    f"أي يوجد {total} طريقة مختلفة لاختيار {k} كرات من الكيس — وهو مقام الاحتمال."
                )

            # ── مجموع الحالات الملائمة + الاحتمال ─────────────────────────────
            possible = [g for g in groups if g.is_possible]
            favs = " + ".join(str(g.favorable_combinations) for g in possible)
            if subpart == "sum":
                lines = "\n".join(
                    (
                        f"- {g.label}: {cls._fmt_comb(g.count, k, g.favorable_combinations)}"
                        if g.is_possible
                        else f"- {g.label}: مستحيل (العدد {g.count} أصغر من {k})"
                    )
                    for g in groups
                )
                return (
                    f"## كيف نجمع لنحصل على الحالات الملائمة\n\n"
                    f"الحدث «{k} كرات من نفس اللون» يتحقق بأيّ لون ممكن:\n\n"
                    f"{lines}\n\n"
                    f"نجمع الحالات الممكنة فقط: ${favs} = {same}$\n\n"
                    # ISS-121 (D-154): صفر كشف للنتيجة — الطالب يركّب النسبة بنفسه.
                    f"وبهذا أصبح لديك البسط. ركّب الاحتمال **بنفسك**: البسط على "
                    f"المقام {total} — فما قيمة P(A)؟"
                )

            # ── الاشتقاق الكامل (حيرة متكررة، بلا جزئية محدّدة) ────────────────
            full_lines = "\n".join(
                (
                    f"   - {g.label}: {cls._fmt_comb(g.count, k, g.favorable_combinations)}"
                    if g.is_possible
                    else f"   - {g.label}: مستحيل (العدد {g.count} أصغر من {k})"
                )
                for g in groups
            )
            return (
                f"## الحل الكامل خطوة بخطوة\n\n"
                f"1) فضاء العينة — نسحب {k} كرات من {n} دفعةً واحدة:\n\n"
                f"   {cls._fmt_comb(n, k, total)}\n\n"
                f"2) الحالات الملائمة (الحدث: {k} كرات من نفس اللون) — لكل لون على حدة:\n\n"
                f"{full_lines}\n\n"
                f"3) نجمع الحالات الممكنة فقط: ${favs} = {same}$\n\n"
                # ISS-121 (D-154): صفر كشف للنتيجة — الخطوة الأخيرة توليد لا تلقين.
                f"4) والآن الخطوة الأخيرة **لك**: ركّب الاحتمال بنفسك — البسط على "
                f"المقام. فما قيمة P(A) التي تحصل عليها؟"
            )
        except Exception:
            logger.warning("_build_probability_direct_explanation_failed", exc_info=True)
            return None

    @classmethod
    async def _build_probability_computational_answer(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
    ) -> tuple[str, str] | None:
        """D-143: إجابة حتمية مباشرة لأسئلة الاحتمالات الحسابية — صفر LLM، topic-safe.

        يُجيب صراحةً (قبل سُلّم الحادثة A): (1) «لماذا نضرب 11×10×9» ⇒ مبدأ العدّ + القسمة
        على !3 ؛ (2) «كيف حصلنا على 56» / الحادثة B (جداء فردي) ⇒ C(عدد الفردية,k)/C(n,k)
        من أرقام الكرات الرسمية ؛ (3) الحوادث غير المنمذجة بعد (C/D/X/الأمل/الشرطي) ⇒
        **تأجيل حتمي صادق** يسمّي الحدث ويُبعده صراحةً عن الحادثة A — **بلا أيّ رقم من LLM
        وبلا أرقام الحادثة A**. يُرجِع ``(text, event)`` أو ``None`` (فيتولّى المسار القائم
        الحادثة A / الحيرة / التحية). نقد المالك #1: لا باب LLM في مسار الرياضيات.
        """
        try:
            from math import comb

            from app.services.capabilities.arabic_normalize import primary_canonical_topic
            from app.services.capabilities.exercise_retrieval import (
                ExerciseRetrievalRequest,
                detect_exercise_retrieval,
                load_exercise_content,
                load_exercise_questions_only,
            )
            from app.services.skills.probability_skill import (
                CombinationsModelOutput,
                ProbabilityCalculatorSkill,
                ProbabilityInput,
            )

            raw = (question or "").strip()
            # حارس اللصق/الاسترجاع: سؤال الطالب قصير؛ لصق التمرين كامل (يحوي «56/فردي/زوجي»)
            # يجب أن يتولّاه الاسترجاع المُفهرَس، لا هذا المسار.
            if len(raw) > 300:
                return None
            q = raw.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).lower()

            # topic-safe: طلب موضوع آخر صريح (دوال/أعداد مركبة) ⇒ لا شرح احتمالات.
            _canonical = primary_canonical_topic(question)
            if _canonical is not None and _canonical.canonical_id != "probability":
                return None

            # تصنيف السؤال الحسابي (حوادث الجداء قبل مبدأ العدّ لمنع التباس «نضرب»).
            is_event_b = (
                "56" in q
                or "p(b" in q
                or "الحادثة b" in q
                or ("جداء" in q and ("فردي" in q or "الفردي" in q))
            )

            # D-143 Phase 1.5: لا نعترض الأسئلة التعريفية/الاستفسارية ("ما هو"، "لم أفهم") لكي تلتقطها
            # الطبقة الدلالية (D-132) ولا تُختطَف كإجابات حسابية مؤجلة.
            from app.services.skills.semantic_property_skill import get_semantic_property_skill
            from app.services.skills.student_state_skill import (
                StudentStateInput,
                get_student_state_skill,
            )

            _sps = get_semantic_property_skill()
            _state = get_student_state_skill().read(
                StudentStateInput(question=question, history=history_messages)
            )
            _confused = (
                _state.primary_intent == "confusion" or "confusion" in _state.secondary_signals
            )
            _wants_def = (
                _sps.is_definitional(question)
                or _state.primary_intent == "definition"
                or (_confused and _sps.interpret(question) is not None)
            )

            _compute = any(
                m in q
                for m in (
                    "احسب",
                    "أحسب",
                    "كم ",
                    "اوجد",
                    "أوجد",
                    "بين ان",
                    "بيّن أن",
                    "استنتج",
                    "كيف",
                    "لماذا",
                )
            ) or any(
                m in q
                for m in (
                    "56",
                    "p(b",
                    "الحادثة b",
                    "جداء",
                    "معدوم",
                    "بدون ارجاع",
                    "التوالي",
                    "p(c",
                    "p_a",
                    "e(x",
                )
            )

            if _wants_def and not _compute:
                return None

            uncovered: tuple[str, str] | None = None
            if ("جداء" in q and ("زوجي" in q or "الزوجي" in q)) or "p(c" in q or "الحادثة c" in q:
                uncovered = ("event_c", "الحادثة C (جداء أرقامها زوجي)")
            elif (
                "معدوم" in q
                or "الحادثة d" in q
                or "بدون ارجاع" in q
                or "بدون إرجاع" in q
                or ("التوالي" in q and "ارجاع" in q)
            ):
                uncovered = ("event_d", "الحادثة D (السحب على التوالي بدون إرجاع — جداء معدوم)")
            elif "المتغير العشوائي" in q or "قانون الاحتمال" in q or "قانون احتمال" in q:
                uncovered = ("random_var", "المتغير العشوائي X")
            elif "الامل" in q or "الأمل" in q or "e(x" in q:
                uncovered = ("expected", "الأمل الرياضي E(X)")
            elif "الشرطي" in q or "شرطي" in q or "p_a" in q or "pa(" in q:
                uncovered = ("conditional", "الاحتمال الشرطي P_A(B)")
            # مبدأ العدّ: «نضرب/ضربنا/الترتيب/ثلاثة أرقام» وليس عن جداء أرقام الكرات (B/C/D).
            mult_markers = (
                "نضرب",
                "ضربنا",
                "نضربها",
                "11×10×9",
                "11x10x9",
                "الترتيب",
                "ثلاثة ارقام",
                "ثلاثة أرقام",
                "ثلاث ارقام",
            )
            is_combinations = any(m in q for m in mult_markers) and "جداء" not in q

            if not (is_event_b or is_combinations or uncovered is not None):
                return None

            # تحميل التمرين الرسمي المُفهرَس (history-immune — D-123).
            _decision = detect_exercise_retrieval(
                ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024"),
                history_messages=history_messages,
            )
            if not (_decision.recognized and _decision.matched_entry):
                return None
            # ISS-120 (D-153): الاستخراج/التكافؤ من أسئلة-فقط؛ الحل الكامل
            # (`_official`) يبقى حصراً لمرجع RAG-Grounded LLM أدناه (D-145).
            _official = load_exercise_content(_decision.matched_entry)
            _official_qonly = load_exercise_questions_only(_decision.matched_entry)
            if not _official or not _official_qonly:
                return None
            _combo = ProbabilityCalculatorSkill().analyze(
                ProbabilityInput(question=_official_qonly, history=None)
            )
            if not isinstance(_combo, CombinationsModelOutput):
                return None
            n, k, total = _combo.n, _combo.k, _combo.total_combinations

            # (1) الحادثة B — حتمي من أرقام الكرات الرسمية (Stage 1).
            if is_event_b:
                parity = ProbabilityCalculatorSkill.number_parity_counts(_official_qonly)
                if parity is None or parity.get("total", 0) != n:
                    return None
                odd = parity["odd"]
                fav = comb(odd, k)
                text = (
                    "## الحالات الملائمة للحادثة B (جداء الأرقام فردي)\n\n"
                    "جداء ثلاثة أعداد يكون **فردياً** فقط إذا كان كلّ عددٍ منها فردياً — يكفي "
                    "عددٌ زوجيّ واحد ليُصبح الجداء زوجياً. إذن نختار الكرات الثلاث من الكرات ذات "
                    f"الأرقام الفردية فقط.\n\nعدد الكرات ذات رقمٍ فردي في الكيس: {odd}، نختار "
                    f"منها {k}:\n\n{cls._fmt_comb(odd, k, fav)}\n\nوفضاء العيّنة هو كلّ طرق سحب "
                    f"{k} من {n}:\n\n{cls._fmt_comb(n, k, total)}\n\nفعدد الحالات الملائمة "
                    f"للحادثة B هو {fav} من أصل {total}."
                )
                return (text, "event_b")

            # (2) مبدأ العدّ (لماذا نضرب 11×10×9) — حتمي.
            if is_combinations:
                num = "×".join(str(n - i) for i in range(k))
                den = "×".join(str(k - i) for i in range(k))
                prod = 1
                for i in range(k):
                    prod *= n - i
                text = (
                    f"## لماذا نضرب {num}\n\n"
                    f"عند سحب {k} كرات من {n}، نَعُدّ بمبدأ الضرب: للكرة الأولى {n} احتمالاً، "
                    f"وبعد سحبها تبقى {n - 1} للثانية، ثمّ {n - 2} للثالثة — فعدد الترتيبات هو "
                    f"{num} = {prod}.\n\nلكنّ السحب **دفعةً واحدة** لا يهتمّ بالترتيب (نفس الكرات "
                    f"الثلاث بأيّ ترتيب = سحبةٌ واحدة)، وكلّ مجموعة من {k} كرات تُرتَّب بـ {den} "
                    f"طريقة، لذلك نقسم عليها:\n\n{cls._fmt_comb(n, k, total)}\n\nفنحصل على عدد "
                    f"المجموعات غير المرتّبة، وهو مقام الاحتمال. (لاحظ: هذا عدّ طرق السحب، وهو "
                    f"يختلف عن **جداء أرقام** الكرات في الحوادث B وC وD.)"
                )
                return (text, "combinations")

            # (3) حوادث غير منمذجة (C/D/X/E(X)/Conditional) ⇒ RAG-Grounded LLM
            # D-145: بدلاً من التأجيل، نمرر التمرين والحل النموذجي للـ LLM ليشرحه بيداغوجياً دون هلوسة.
            ev_id, ev_label = uncovered  # type: ignore[misc]

            try:
                import asyncio

                from app.core.ai_gateway import get_ai_client

                system_prompt = (
                    "أنت معلّم رياضيات جزائري متميز تشرح لطلبة البكالوريا. "
                    "مهمتك: الإجابة على سؤال الطالب بالاستناد **حصرياً** على النص المرفق (التمرين مع الإجابة النموذجية المرجعية). "
                    "ممنوع منعاً باتاً اختراع أرقام أو كسور غير موجودة في الحل النموذجي. "
                    "اقرأ الإجابة الخاصة بالحدث الذي يسأل عنه الطالب (مثلا الحادثة D أو المتغير X أو الأمل الرياضي)، واشرح خطواتها بتفصيل بيداغوجي. "
                    "استخدم LaTeX للمعادلات. لا تبدأ بكلمات مثل 'حسنا' أو 'أفهمك'. أعط الشرح مباشرة بصيغة المخاطب."
                )
                user_prompt = (
                    f"المرجع (التمرين والحل النموذجي):\n{_official}\n\n"
                    f"سؤال الطالب يخص: {ev_label}\n"
                    f"السؤال الفعلي: {question}\n\n"
                    "اشرح هذا الجزء للطالب خطوة بخطوة بالاستناد للمرجع فقط."
                )

                ai_client = get_ai_client()
                raw = await asyncio.wait_for(
                    ai_client.send_message(system_prompt, user_prompt, temperature=0.2),
                    timeout=15.0,
                )
                if raw and isinstance(raw, str) and raw.strip():
                    from app.services.skills.content_integrity_skill import _strip_garbage_markers

                    text = _strip_garbage_markers(raw.strip())
                    # Apply optional pedagogical redaction if needed, but for mathematical explanations of new parts,
                    # we often want to show the steps.
                    # text, _ = redact_final_answers(text, support_level=5)

                    if text:
                        return (text, ev_id)
            except Exception as llm_err:
                import logging

                logging.getLogger("orchestrator-client").warning(
                    f"RAG LLM fallback failed: {llm_err}", exc_info=True
                )

            # Fallback to the old deferral message if LLM fails
            text = (
                f"## {ev_label}\n\n"
                f"سؤالك يخصّ {ev_label}. حسابها دقيق ويحتاج للتركيز. لنبدأ: ما المُعطى الذي تريد أن نُوضّحه أولاً فيها؟"
            )
            return (text, ev_id)
        except Exception:
            logger.warning("_build_probability_computational_answer_failed", exc_info=True)
            return None

    @classmethod
    def _probability_computational_variant(
        cls, event: str, history_messages: list[dict[str, str]] | None
    ) -> str | None:
        """D-143 (RC-4): تمثيلٌ حتميّ **مختلف** للسؤال الحسابي نفسه عند تكراره — تخصيصٌ
        بيداغوجي لا إعادة حرفية (نقد المالك #2). صفر LLM. يُرجِع None عند أيّ تعذّر.
        """
        try:
            # الحوادث المؤجَّلة: خطوةٌ عمليّة مختلفة (لا تحتاج تحميل الأرقام).
            if event not in ("combinations", "event_b"):
                return (
                    "## لنبدأ خطوةً عمليّة\n\n"
                    "لنحسب هذه الحادثة بدقّة نحتاج أوّلاً تحديد الكرات المعنيّة بها (حسب أرقامها "
                    "أو نوع السحب). أخبرني: هل نبدأ بعدّ الكرات التي تُحقّق الشرط، أم بفضاء العيّنة "
                    "(كلّ طرق السحب)؟"
                )

            from math import comb

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

            _decision = detect_exercise_retrieval(
                ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024"),
                history_messages=history_messages,
            )
            if not (_decision.recognized and _decision.matched_entry):
                return None
            # ISS-120 (D-153): أسئلة-فقط قبل استخراج الكيانات.
            official = load_exercise_questions_only(_decision.matched_entry)
            if not official:
                return None
            combo = ProbabilityCalculatorSkill().analyze(
                ProbabilityInput(question=official, history=None)
            )
            if not isinstance(combo, CombinationsModelOutput):
                return None
            n, k, total = combo.n, combo.k, combo.total_combinations

            if event == "combinations":
                return (
                    "## بمثالٍ ملموس\n\n"
                    "لنُسمِّ ثلاث كرات: أ، ب، ج. ترتيبُها يُعطي 6 صفوف: (أ،ب،ج)، (أ،ج،ب)، "
                    "(ب،أ،ج)، (ب،ج،أ)، (ج،أ،ب)، (ج،ب،أ) — أي 3×2×1=6 ترتيباتٍ لنفس المجموعة "
                    "الواحدة. لكنّ السحب دفعةً واحدة لا يميّز بينها فهي سحبةٌ واحدة. لذلك بعد عدّ "
                    f"الترتيبات {n}×{n - 1}×{n - 2} نقسم على 3!=6 لنُلغي تكرار الترتيب، فيتبقّى عدد "
                    f"المجموعات {cls._fmt_comb(n, k, total)}."
                )

            # event_b — صياغةٌ بديلة (تركيز على «لا رقم زوجي»).
            parity = ProbabilityCalculatorSkill.number_parity_counts(official)
            if parity is None or parity.get("total", 0) != n:
                return None
            odd = parity["odd"]
            fav = comb(odd, k)
            return (
                "## بطريقةٍ أخرى للحادثة B\n\n"
                "جداء الأرقام فردي ⟺ لا يدخل فيه أيّ رقمٍ زوجي (رقمٌ زوجيٌّ واحد يجعل الجداء "
                f"زوجياً). فننظر فقط إلى الكرات ذات الأرقام الفردية وعددها {odd}، ونعدّ طرق "
                f"اختيار {k} منها: {cls._fmt_comb(odd, k, fav)}؛ وكلّ طرق السحب "
                f"{cls._fmt_comb(n, k, total)}. فالحالات الملائمة {fav} من {total}."
            )
        except Exception:
            logger.warning("_probability_computational_variant_failed", exc_info=True)
            return None

    @staticmethod
    def _probability_computational_advance_prompt() -> str:
        """D-143 (RC-4): مُوجِّه تقدّمٍ نهائيّ حين تُستنفَد التمثيلات — لا إعادة حرفية."""
        return (
            "## لنُطبّق معاً\n\n"
            "شرحنا الفكرة بأكثر من طريقة — لِنُثبّتها بالحساب على جزءٍ محدّد. أيّهما تريد أن "
            "نُفصّل الآن: عدّ كلّ طرق السحب (المقام)، أم عدّ الحالات الملائمة لحادثةٍ بعينها؟"
        )

    @classmethod
    def _format_conceptual_relationship(
        cls,
        question: str,
        n: int,
        k: int,
        total: int,
        same: int,
        groups: list,
    ) -> str:
        """D-125: شرح العلاقة الحواري القصير (المقام مقابل البسط) — حتمي، لا حساب.

        يحل «متلازمة الردود المعلبة»: «ما الفرق بين 165 و 14» يطلب المعنى. المخرج
        ≤3 أسطر جوهرية (تحفّظ المالك 4 — لا فقرة فلسفية). الهجين (وُجد فعل حسابي
        «كيف حصلنا/نحسب/وجدنا») ⇒ سطر حسابي **واحد** منفصل عبر ``_fmt_comb`` (يَنجو
        من حجب D-113). redaction-safe: لا «P(...)=عدد»/«\\boxed»/«خلاصة … = عدد».
        """

        def _bare(label: str) -> str:
            return label.replace("كرة ", "", 1).strip() or label

        possible = [g for g in groups if getattr(g, "is_possible", True)]
        impossible = [g for g in groups if not getattr(g, "is_possible", True)]
        favs_parts = " + ".join(f"{g.favorable_combinations} لل{_bare(g.label)}" for g in possible)
        imp_note = ""
        if impossible:
            names = " و".join(f"ال{_bare(g.label)}" for g in impossible)
            imp_note = f"؛ و{names} مستحيلة (عددها أقل من {k})"

        body = (
            f"## العلاقة بين {total} و {same} (المقام والبسط)\n\n"
            f"**{total}** هو عدد كل الطرق الممكنة لسحب {k} كرات مهما كان لونها — "
            f"هذا هو **المقام** (ساحة كل ما يمكن أن يحدث).\n\n"
            f"**{same}** هو عدد الطرق التي تحقق «{k} من نفس اللون» فقط "
            f"({favs_parts}{imp_note}) — هذا هو **البسط** (الحالات التي تنجح).\n\n"
            f"فالاحتمال هو نسبة البسط إلى المقام: {same} من كل {total}."
        )

        # الهجين (تحفّظ المالك 2): إن طلب الطالب الحساب أيضاً، سطر حسابي واحد فقط.
        ql = (question or "").lower()
        if any(v in ql for v in ("كيف حصلنا", "كيف نحسب", "كيف وجدنا", "احسب", "الحساب")):
            favs_sum = " + ".join(str(g.favorable_combinations) for g in possible)
            body += (
                f"\n\nوللتذكير بالحساب فقط: {cls._fmt_comb(n, k, total)}، و {favs_sum} = {same}."
            )
        return body
