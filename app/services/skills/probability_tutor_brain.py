"""عقل الاحتمالات الحتمي — ProbabilityTutorBrain (D-163 / M13).

الوحدة المستخرَجة من God-file «orchestrator_client.py» (كان 6,154 سطراً — D-160/D-162
أجّلا التفكيك مرتين بسبب نصف قطر الانفجار الاختباري؛ D-163 نفّذه): كل منطق المعلّم
الحتمي للاحتمالات — الكشف (`_detect_*`)، التحقق الرمزي (`_verify_*`)، البُناة
(`_build_*`)، محرّك الدور المعرفي (`_cognitive_turn`)، dedup، والثوابت الصفّية —
**نقل حرفي verbatim** بنفس الأسماء (صفر إعادة صياغة، صفر تغيير سلوكي).

العقد المعماري (لا يُكسر بدون ADR):
- `OrchestratorClient` يرث هذه الفئة (mixin) — كل `cls._x` تُحل عبر الـ MRO كما كانت.
- **ممنوع** الاستيراد من `microservices/` هنا (الحدود المعمارية — HTTP فقط).
- **ممنوع** إعادة أي من هذه الدوال إلى `orchestrator_client.py` (عودة الـ God-file).
- هذه الوحدة هي «عقل المونوليث» في بوّابة تكافؤ split-brain
  (`scripts/fitness/check_pedagogical_os.py:check_split_brain_parity`) مقابل port
  الخدمة المصغرة `microservices/orchestrator_service/src/services/overmind/probability_tutor.py`.
- وحدة محرّك داخلية (سابقة `kc_progress_schema.py`) — ليست Skill مُسجَّلاً في الـ registry؛
  مستهلكها الحي الوحيد `OrchestratorClient` (لا ZOMBIE — import + call chain + runtime).
- الأرقام من المحرك الرمزي حصراً (صفر LLM في مسار الأرقام)؛ الدوال `_generate_*` الوحيدة
  التي تلمس LLM محروسة (redaction + garbage-strip + timeout + fail-open) — D-128.
"""

from __future__ import annotations

import contextlib
import logging
import re
from typing import ClassVar

# نفس اسم الـ logger القديم عمداً — استمرارية السجلات وصفر تغيير رصدي (D-163).
logger = logging.getLogger("orchestrator-client")


class ProbabilityTutorBrain:
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
    _PROBABILITY_CONFUSION_MARKERS: tuple[str, ...] = (
        "لم أفهم",
        "لم افهم",
        "مفهمتش",
        "ما فهمت",
        "مافهمت",
        "ما افهم",
        "لا أفهم",
        "لا افهم",
        "مازلت",
        "ما زلت",
        "اشرح لي",
        "اشرحلي",
        "وضح لي",
        "وضحلي",
        "أين الشرح",
        "اين الشرح",
        "لا أعرف",
        "لا اعرف",
        "ماعرفت",
        "ما عرفت",
        "صعب",
        "أعد الشرح",
        "اعد الشرح",
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
        """
        texts: list[str] = [str(question or "")]
        for msg in history_messages or []:
            if isinstance(msg, dict) and msg.get("role") == "user":
                texts.append(str(msg.get("content") or ""))
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
            prev_tokens = set(prev.split())
            if prev_tokens and len(cand_tokens & prev_tokens) / len(cand_tokens) >= threshold:
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
        """D-142 (1B/Phase2): تداخل رموز/احتواء بين نصّين (حارس التكرار ضد مرساة الحالة)."""
        na, nb = cls._norm_for_dedup(a), cls._norm_for_dedup(b)
        if not na or not nb:
            return False
        if na in nb or nb in na:
            return True
        ta = set(na.split())
        if not ta:
            return False
        return len(ta & set(nb.split())) / len(ta) >= threshold

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
        """D-127: المفهوم الحتمي لرسالة طالب (incl. confusion→full_solution)."""
        from app.services.skills.concept_diagnosis_skill import ConceptDiagnosisSkill

        c = ConceptDiagnosisSkill.diagnose_deterministic(text).concept
        if c == "unknown":
            low = (text or "").strip().lower()
            if any(
                m in low for m in ("لم أفهم", "لم افهم", "مفهمتش", "ما فهمت", "لا أفهم", "لا افهم")
            ) or low in ("؟", "?"):
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
            return (
                "شرحنا الحل كاملاً. بدل تكراره، لنحدّد أين تحديداً تعثّرت — اختر حرفاً:\n\n"
                f"(أ) فضاء العينة ({total} — كل الطرق)\n"
                f"(ب) عدّ الحالات الملائمة ({same})\n"
                "(ج) معنى الاحتمال نفسه (البسط على المقام)\n\n"
                "أخبرني بالحرف وسأركّز على تلك النقطة وحدها."
            )

        return None

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
            _ct_hist = " ".join(
                str(m.get("content", "")) for m in (history_messages or []) if isinstance(m, dict)
            )
            if not cls._is_prob_context(f"{question} {_ct_hist}"):
                return None, None
            # طلب محتوى/تمرين جديد صريح ⇒ ليس تفاعل تدريس (تسليم للاسترجاع).
            _low = (question or "").strip().lower()
            if any(m in _low for m in ("اعطني", "أعطني", "اعطيني", "هات", "اكتب", "ارسم", "درس")):
                return None, None
            # حارس تبديل الموضوع (D-101): سؤال غير احتمالي ⇒ تسليم للكتل.
            with contextlib.suppress(Exception):
                from app.services.capabilities.arabic_normalize import primary_canonical_topic

                _topic = primary_canonical_topic(question)
                if _topic is not None and _topic.canonical_id != "probability":
                    return None, None
            combo = cls._load_canonical_combinations(question, history_messages)
            if combo is None:
                return None, None

            from app.services.skills.kc_progress_schema import (
                PENDING_KEY,
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
                _teach = cls._build_probability_direct_explanation(
                    question, history_messages, forced_subpart=_explain_part
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
                text = cls._build_symbolic_step(combo, step)
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
                    question, history_messages, forced_subpart=_part
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
