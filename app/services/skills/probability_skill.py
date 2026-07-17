"""
ProbabilityCalculatorSkill — محرّك حساب الاحتمالات الحتمي العام (D-075/D-076).

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill — وحدة مستقلة قابلة
للقياس والاختبار والاستبدال. لا Prompt Spaghetti».

## المسؤولية الواحدة
تحويل نص مسألة احتمالات عربي (أيّاً كانت مفرداته) إلى **نموذج احتمالي منظَّم
بكسور حقيقية**. الخلفية تحسب P(الحدث) ديناميكياً من بنية المسألة، لا تُخرج
HTML ولا قيماً وهمية (Protocol V14.0 §3).

## التعميم (Protocol V15.0 — Anti-Overfitting)
المحرّك ليس مخصّصاً لـ«الكرات في الكيس». يعمل عبر **أنماط معمّمة** (Total
Universe, Sub-events, Conditional Branches) بصرف النظر عن المفردات:

- **فضاء متساوي الاحتمال** (نرد، قطعة نقدية): يقسّم الفضاء (زوجي/فردي، وجه/ظهر).
- **شجرة شرطية بالنِّسَب** (مصنع/آلات/Bayesian): فرع رئيسي بنسب + فرع فرعي شرطي
  (معيب/سليم) — كل نسبة كسر دقيق.
- **تركيبة عددية معمّمة** (كرات، بطاقات، قطع، أرقام): يستخرج (عدد + كيان ملموس)
  لأي اسم — لون، رقم بطاقة، صنف — ويبني شجرة سحب بـ/بدون إرجاع.

أنماط حتمية أولاً (deterministic-first)؛ ومحرّك LLM معمّم (`extract_with_llm`)
احتياطٌ للمفردات غير المعروفة — يبقى الـ Skill قابلاً للاختبار بـ pytest عادي.

## العقد (Pydantic)
- Input:  `ProbabilityInput(question, history)`
- Output: `ProbabilityModelOutput | ProbabilityFailure`

## الكسور تربوية لا مختزَلة
نُخرج الكسر كما يُشتق من المسألة (4/11، 3/6، 60/100، 3/8) — أوضح للطالب من
الصورة المختزَلة. الواجهة تُصيّره تماماً عبر (p_num/p_den).

## الاستقلالية
- النواة حتمية تماماً — لا LLM، لا عشوائية، لا I/O. قابل للاختبار بـ pytest.
- لا يستورد من Skills أخرى ولا من microservices.
- يستهلك `PROBABILITY_CALCULATION_DOCTRINE` من doctrine module (single source).

## القياس (Prometheus عبر التيليمتري الموحَّد)
- `cogniforge_skill_probability_invocations_total{status,strategy}` (counter)
- `cogniforge_skill_probability_duration_seconds` (histogram)
"""

from __future__ import annotations

import contextlib
import re
import time

from app.core.schemas import RobustBaseModel  # noqa: F401 — re-export خلفي
from app.services.skills.probability_models import (
    DOCTRINE_VERSION,
    CombinationGroup,
    CombinationsModelOutput,
    CompositionItem,
    ExerciseStep,
    FullExerciseStoryOutput,
    ImpossibleCaseOutput,
    ImpossibleNumericalState,
    ImpossibleVisualDirectives,
    ProbabilityFailure,
    ProbabilityInput,
    ProbabilityModelOutput,
)

try:
    from app.core.logging import get_logger
except ImportError:  # pragma: no cover
    import logging

    def get_logger(name: str):  # type: ignore[no-redef]
        return logging.getLogger(name)


logger = get_logger("skill.probability")

# الإصدار يُستهلك في الـ doctrine binding (drift detection)


# ── الكيانات الملموسة (Abstraction Ban): لون → تسمية موجبة + متمِّمة ───────────────
_COLOR_GROUPS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("حمراء", "حمر", "احمر", "حمرا", "rouge"), "كرة حمراء", "كرة غير حمراء"),
    (("بيضاء", "بيض", "ابيض", "بيضاوان", "بيضاوين", "بيضا", "blanc"), "كرة بيضاء", "كرة غير بيضاء"),
    (("خضراء", "خضر", "اخضر", "خضرا", "vert"), "كرة خضراء", "كرة غير خضراء"),
    (("سوداء", "سود", "اسود", "noir"), "كرة سوداء", "كرة غير سوداء"),
    (("صفراء", "صفر", "اصفر", "jaune"), "كرة صفراء", "كرة غير صفراء"),
    (("زرقاء", "زرق", "ازرق", "bleu"), "كرة زرقاء", "كرة غير زرقاء"),
)

# تسمية اللون الموجبة → رمز CSS (يُغذّي أنيميشن الواجهة في السيناريو المستحيل).
_COLOR_CSS_TOKEN: dict[str, str] = {
    "كرة حمراء": "red",
    "كرة بيضاء": "white",
    "كرة خضراء": "green",
    "كرة سوداء": "black",
    "كرة صفراء": "gold",
    "كرة زرقاء": "blue",
}

# كلمات الأعداد العربية (مفردة + جمع) → قيمة.
_ARABIC_CARDINALS: dict[str, int] = {
    "صفر": 0,
    "واحدة": 1,
    "واحد": 1,
    "اثنتان": 2,
    "اثنتين": 2,
    "اثنان": 2,
    "اثنين": 2,
    "ثلاث": 3,
    "ثلاثة": 3,
    "اربع": 4,
    "اربعة": 4,
    "خمس": 5,
    "خمسة": 5,
    "ست": 6,
    "ستة": 6,
    "سبع": 7,
    "سبعة": 7,
    "ثمان": 8,
    "ثماني": 8,
    "ثمانية": 8,
    "تسع": 9,
    "تسعة": 9,
    "عشر": 10,
    "عشرة": 10,
}

# صيغ المثنى التي تحمل العدد 2 بذاتها.
_DUAL_NOUNS: tuple[str, ...] = (
    "كرتان",
    "كرتين",
    "قطعتان",
    "قطعتين",
    "حبتان",
    "حبتين",
    "بطاقتان",
    "بطاقتين",
)

# أسماء العناصر الشائعة (مفرد ⇐ جمع) — تُستخدم لتسمية الكيانات المعمّمة.
_ITEM_SINGULAR: dict[str, str] = {
    "كرات": "كرة",
    "كرة": "كرة",
    "بطاقات": "بطاقة",
    "بطاقة": "بطاقة",
    "قطع": "قطعة",
    "قطعة": "قطعة",
    "كريات": "كرية",
    "كرية": "كرية",
    "حبات": "حبة",
    "حبة": "حبة",
    "اوراق": "ورقة",
    "ورقة": "ورقة",
    "عناصر": "عنصر",
    "عنصر": "عنصر",
    "اجهزة": "جهاز",
    "جهاز": "جهاز",
}

# D-081 (ISS-083): كلمات تدل على كيان مرقّم *صريح* (بطاقة رقم 1 / تحمل الرقم 2).
# تُطابق الأسماء المستقلّة فقط («رقم»/«الرقم»/«ارقام») وتستبعد صيغ الصفة
# «مرقمة»/«مرقمتان»/«مرقم» (تعني «مُعلَّمة بـ» وتصف ترقيم العناصر لا نوعها).
# الخلط بينهما كان يُنتج كيانات زائفة («كرة رقم 0») تُفسد المجموع والكسور.
_NUMBERED_ENTITY_MARKERS: frozenset[str] = frozenset(
    {"رقم", "الرقم", "ارقام", "الارقام", "رقمها", "ارقامها"}
)

# سياق احتمالي يُفعِّل المحرّك (تجنّب false positives على نص عام).
_PROBABILITY_CONTEXT: tuple[str, ...] = (
    "احتمال",
    "احتمالات",
    "شجرة",
    "نسحب",
    "سحب",
    "يسحب",
    "نرمي",
    "رمي",
    "كيس",
    "صندوق",
    "علبة",
    "صف",
    "نرد",
    "زهر",
    "قطعة نقدية",
    "عملة",
    "مصنع",
    "الة",
    "ينتج",
    "تنتج",
    "probabilit",
    "proba",
    "tirage",
    "tree",
    "dice",
)

# كشف وضع السحب.
_WITHOUT_REPLACEMENT: tuple[str, ...] = (
    "بدون ارجاع",
    "دون ارجاع",
    "بدون اعادة",
    "بدون رد",
    "sans remise",
    "على التوالي وبدون",
)
_WITH_REPLACEMENT: tuple[str, ...] = (
    "مع الارجاع",
    "بارجاع",
    "مع الاعادة",
    "avec remise",
)

# D-078 (V19.0) — وضع السحب: متزامن (تأليفي/Combinatorics) مقابل تتابعي (شجرة).
# «دفعة واحدة» = سحب آني → C(n,k)، ممنوع تمثيله بشجرة تتابعية (كارثة تربوية).
_SIMULTANEOUS_MARKERS: tuple[str, ...] = (
    "دفعة واحدة",
    "دفعة وحدة",
    "في ان واحد",
    "في نفس الوقت",
    "في وقت واحد",
    "معا",
    "آنيا",
    "انيا",
    "simultan",
    "en meme temps",
    "a la fois",
)
_SEQUENTIAL_MARKERS: tuple[str, ...] = (
    "على التوالي",
    "تباعا",
    "واحدة تلو",
    "واحدة بعد",
    "بالتتابع",
    "successiv",
    "l'une apres",
    "une apres",
)

# D-078 (V19.0) — كاشف الإحباط (Frustration Detector): إشارات الحيرة تُفعِّل
# التوجيه إلى أداة بصرية بدل توليد جدران نصّية.
_CONFUSION_MARKERS: tuple[str, ...] = (
    "لم افهم",
    "لم أفهم",
    "ما فهمت",
    "مفهمتش",
    "مفهمت",
    "ما فهمتش",
    "كيفاش",
    "كيف",
    "وضح لي",
    "اشرح لي",
    "ما هو الحل",
    "صعب",
    "je ne comprends",
    "pas compris",
    "comment",
)

# ISS-114 (D-106): طلب توليد واجهة صريح — الطالب يطلب «قم بتوليد واجهة تشرح
# الحادثة» فيكتب الـ LLM HTML خاماً (كارثة). نوجّهه للأداة البصرية المُهيكلة
# بدلاً من LLM. إشارة *تفعيل* (لا متابعة خطوة) — لا تُلوَّث _PROBABILITY_CONTEXT
# (درس D-078/D-101: تلويث قائمة السياق يخلق false positives).
_VISUAL_REQUEST_MARKERS: tuple[str, ...] = (
    "توليد واجهة",
    "ولد واجهة",
    "انشئ واجهة",
    "اصنع واجهة",
    "اعمل واجهة",
    "اعمل لي واجهة",
    "صمم واجهة",
    "اريد واجهة",
    "واجهة تشرح",
    "واجهة توضح",
    "واجهة تفاعلية",
    "generate ui",
    "genere une interface",
)

# ISS-110 (D-101): إشارات متابعة احتمالية — سؤال متابعة بعد تمرين احتمالات
# (مثل «احسب الأمل الرياضي E(X)») لا يحوي كلمة احتمالية صريحة لكنه يستهدف
# خطوة من التمرين. مرآة `_detect_focus_step` في orchestrator_client.
_FOLLOWUP_PROBABILITY_INTENT: tuple[str, ...] = (
    "p(",
    "p_a",
    "نفس اللون",
    "same color",
    "فردي",
    "زوجي",
    "شرطي",
    "جداء",
    "الامل",
    "الأمل",
    "امل رياضي",
    "متغير عشوائي",
    "المتغير",
    "e(x",
    "x>1",
    "فضاء",
    "تأليف",
    "تاليف",
)

# تطبيع التشكيل + الفواصل العربية قبل التحليل.
# نحذف علامات التشكيل فقط (الحركات/التنوين/الشدة/السكون والعلامات القرآنية)
# دون المساس بحروف العربية (U+0621–U+064A).
_TASHKEEL_RE = re.compile("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u08d3-\u08ff]")
# ISS-108 (D-097): نُقسِّم أيضاً على علامات Markdown/LaTeX (`* \ $ # _ ~ | / ` `)
# لأن نص التمرين المخزَّن مُنسَّق («**أربع كرات حمراء**»، «\(1\)»). بدونها يلتصق
# العدد بالعلامة («**اربع» / «**خمس») فيفشل `_as_int` → تُفقَد الحمراء والخضراء
# ويبقى الأبيض فقط (الكيس الناقص). مؤكَّد حياً على بيانات الإنتاج (msg 3408/3412).
_TOKEN_SPLIT_RE = re.compile(r"[\s،,.\-؛:؟?!()\[\]{}«»\"'*\\$#_~`|/]+")


# ── العقود (Pydantic) — مُستخرَجة إلى probability_models (D-170 Stage C) ─────────
# الاستيراد أعلى الملف (re-export خلفي) — كل المستوردين القائمين بلا تغيير.

# ── القياس (Prometheus عبر التيليمتري الموحَّد) ────────────────────────────────────


def _record_metric(status: str, strategy: str, duration_s: float) -> None:
    with contextlib.suppress(Exception):
        from app.telemetry.unified_observability import get_unified_observability

        obs = get_unified_observability()
        obs.record_metric(
            "skill.probability.invocations.total",
            1.0,
            labels={"status": status, "strategy": strategy},
        )
        obs.record_metric("skill.probability.duration_seconds", duration_s)


# ── المحرّك ────────────────────────────────────────────────────────────────────────


class ProbabilityCalculatorSkill:
    """
    محرّك حساب الاحتمالات الحتمي المعمّم.

    عقد دائم (لا يُكسر بدون ADR):
    1. صفر تبعيات على Skills أخرى — استقلالية إلزامية.
    2. النواة حتمية تماماً — لا LLM، لا عشوائية، لا I/O.
    3. كسور تربوية حقيقية (count/total) — ممنوع 0.5 افتراضية مع توفّر البنية.
    4. تعميم لا overfitting — أنماط (universe/conditional/composition) لا مفردات.
    5. كل invocation يُسجَّل في Prometheus.
    """

    _skill_name: str = "probability_calculation"
    doctrine_version: str = DOCTRINE_VERSION

    # ── normalization & tokenization ──────────────────────────────────────────
    @staticmethod
    def _normalize(text: str) -> str:
        if not text or not isinstance(text, str):
            return ""
        cleaned = _TASHKEEL_RE.sub("", text)
        return cleaned.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")

    @classmethod
    def _tokenize(cls, text: str) -> list[str]:
        return [t for t in _TOKEN_SPLIT_RE.split(cls._normalize(text)) if t]

    @staticmethod
    def _decimal(num: int, den: int) -> float:
        return round(num / den, 6) if den > 0 else 0.0

    @staticmethod
    def number_parity_counts(content: str) -> dict[str, int] | None:
        """D-143: يستخرج أرقام الكرات المرقّمة من نصّ التمرين ويحسب توزيعها (حتمي، صفر LLM).

        يدعم تمارين الكرات المرقّمة («... مرقمة بـ: 0، 1، 1، 3»). يُرجِع
        ``{"odd","even","zero","total"}`` أو ``None`` إن لم توجد كرات مرقّمة. يُمكّن
        حساب الحوادث المعتمدة على أرقام الكرات (جداء فردي/زوجي/معدوم) **دون أيّ تقدير
        من LLM** — الأرقام من نصّ التمرين الرسمي حصراً.
        """
        if not content or not isinstance(content, str):
            return None
        # توحيد الأرقام العربية-الهندية إلى ASCII قبل الاستخراج.
        text = content.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        nums: list[int] = []
        # كل مجموعة مرقّمة: «... مرقم<...> ب<ـ>: <أرقام مفصولة بفواصل>».
        for match in re.finditer(r"مرقم\S*\s+ب[ـ\s]*[:：]?\s*([\d،,\s\(\)\\$]+)", text):
            nums.extend(int(d) for d in re.findall(r"\d", match.group(1)))
        if not nums:
            return None
        odd = sum(1 for x in nums if x % 2 == 1)
        return {
            "odd": odd,
            "even": len(nums) - odd,
            "zero": sum(1 for x in nums if x == 0),
            "total": len(nums),
        }

    @classmethod
    def _node(
        cls,
        label: str,
        num: int | None,
        den: int | None,
        children: list | None = None,
    ) -> dict[str, object]:
        """عقدة شجرة بكسر تربوي خام (غير مختزَل) + قيمة عشرية.

        D-078 (V19.0): الجذر يُبنى بـ num=None → بلا احتمال (يُلغى الـ 1/1 الوهمي).
        """
        rec: dict[str, object] = {"label": label}
        if num is not None and den is not None:
            rec["p"] = cls._decimal(num, den)
            rec["p_num"] = int(num)
            rec["p_den"] = int(den) if den > 0 else 1
        if children:
            rec["children"] = children
        return rec

    @classmethod
    def _root(cls, children: list) -> dict[str, object]:
        """جذر الشجرة بلا احتمال (D-078) — يُلغى الـ 1/1 الوهمي."""
        return cls._node("البداية", None, None, children)

    @classmethod
    def _sanitize_node(cls, node: dict[str, object]) -> dict[str, object]:
        """حارس نهائي ضد الكسور المنحلّة (D-077 / V17.0).

        يضمن لكل عقدة: ``p_den ≥ 1`` (لا قسمة على صفر أبداً) و ``0 ≤ p_num ≤ p_den``
        و ``p`` متّسقة. هذا خط الدفاع الأخير قبل البثّ — أي خطأ حسابي سابق
        (مقام صفر، بسط > مقام) يُقصّ بأمان بدل أن يصل للطالب كـ 1/0 أو غارباج.
        """
        # الجذر بلا احتمال (D-078) — لا نُلصق به كسراً وهمياً.
        if "p_num" in node or "p_den" in node:
            num = int(node.get("p_num", 0) or 0)
            den = int(node.get("p_den", 1) or 1)
            den = max(den, 1)
            num = max(0, min(num, den))
            node["p_num"] = num
            node["p_den"] = den
            node["p"] = cls._decimal(num, den)
        children = node.get("children")
        if isinstance(children, list):
            node["children"] = [cls._sanitize_node(c) for c in children if isinstance(c, dict)]
        return node

    # ── مساعدات استخراج العدد ─────────────────────────────────────────────────────
    @staticmethod
    def _as_int(token: str) -> int | None:
        stripped = token.lstrip("وفب")  # و/ف/ب البادئة (و5، ف3، وخمس، وأربع)
        if stripped.isdigit():
            return int(stripped)
        if token in _ARABIC_CARDINALS:
            return _ARABIC_CARDINALS[token]
        # كلمة عدد مسبوقة بحرف عطف/جر (وخمس، فأربع، بثلاث) — شائعة في نص الطلاب.
        if stripped in _ARABIC_CARDINALS:
            return _ARABIC_CARDINALS[stripped]
        return None

    @classmethod
    def _count_before(cls, tokens: list[str], idx: int, span: int = 4) -> int | None:
        """يبحث عن العدد المجاور لكيان عند الموضع idx (رجوعاً حتى span رموز)."""
        for back in range(1, span + 1):
            j = idx - back
            if j < 0:
                break
            tok = tokens[j]
            if any(dual in tok for dual in _DUAL_NOUNS):
                return 2
            value = cls._as_int(tok)
            if value is not None:
                return value
        return None

    @classmethod
    def _detect_item_noun(cls, tokens: list[str]) -> str:
        """يحدّد اسم العنصر المفرد (كرة/بطاقة/قطعة) من النص — افتراضي 'عنصر'."""
        for tok in tokens:
            if tok in _ITEM_SINGULAR:
                return _ITEM_SINGULAR[tok]
        return "عنصر"

    # ── استخراج التركيبة العددية المعمّمة ────────────────────────────────────────────
    @classmethod
    def _extract_count_entities(cls, text: str) -> list[tuple[str, str, int]]:
        """يستخرج [(label_pos, label_neg, count)] لأي كيان عددي (لون/رقم/صنف).

        يدعم: ألوان (كرة حمراء)، أرقام بطاقات (بطاقة رقم 1)، وأصناف عامة.
        """
        tokens = cls._tokenize(text)
        item_noun = cls._detect_item_noun(tokens)
        color_results: list[tuple[str, str, int]] = []
        numbered_results: list[tuple[str, str, int]] = []
        seen: set[str] = set()

        # (1) كيانات ملوّنة
        for keywords, label_pos, label_neg in _COLOR_GROUPS:
            match_idx = next(
                (i for i, tok in enumerate(tokens) if any(kw in tok for kw in keywords)),
                None,
            )
            if match_idx is None:
                continue
            count = cls._count_before(tokens, match_idx)
            if count is None or count <= 0:
                continue
            if label_pos in seen:
                continue
            seen.add(label_pos)
            color_results.append((label_pos, label_neg, count))

        # (2) كيانات مرقّمة *صريحة*: token هو الاسم المستقل «رقم/الرقم» متبوعاً
        # برقم (بطاقة رقم 1). D-081 (ISS-083): مطابقة الأسماء المستقلّة فقط —
        # تُستبعد «مرقمة/مرقمتان» (صفة تصف ترقيم العناصر لا نوعها) التي كانت
        # تُلتقَط كسلسلة فرعية فتُنتج كيانات زائفة («كرة رقم 0») وكسوراً خاطئة.
        for i, tok in enumerate(tokens):
            if tok not in _NUMBERED_ENTITY_MARKERS:
                continue
            num_tok = tokens[i + 1] if i + 1 < len(tokens) else ""
            number = cls._as_int(num_tok)
            if number is None:
                continue
            label_pos = f"{item_noun} رقم {number}"
            if label_pos in seen:
                continue
            count = cls._count_before(tokens, i, span=5)
            if count is None or count <= 0:
                continue
            seen.add(label_pos)
            numbered_results.append((label_pos, f"{item_noun} ليست رقم {number}", count))

        # ISS-120 (D-153): حارس الكيان الوهمي في التركيبة المختلطة — حين تُوجد
        # كيانات ملوّنة ويُطابق المجموع الصريح المذكور في النص («يحتوي كيس على
        # 11 كرة») مجموع الألوان وحدها، فالأرقام **صفات** للكرات الملوّنة لا
        # مجموعات مستقلة ⇒ تُسقَط الكيانات المرقّمة كلياً. نثر الحل النموذجي
        # («…تحمل الرقم 0 … وعددها 3 كرات») كان يولِّد «بطاقة رقم 0 (العدد 3)»
        # ⇒ n=14 و C(14,3)=364 بدل 11/165. تمارين البطاقات النقية (D-076) بلا
        # كيانات لون — لا تتأثر.
        if color_results and numbered_results:
            color_sum = sum(count for _, _, count in color_results)
            stated_total = cls._detect_total(text, fallback=1)
            if stated_total == color_sum:
                return color_results

        return color_results + numbered_results

    @classmethod
    def _stated_denominators(cls, text: str) -> set[int]:
        """D-152 + ISS-120 (D-153): المقامات المُصرَّح بها في النص.

        تلتقط الصيغتين: القسمة الخام (``14/165``) **و** LaTeX
        (``\\frac{56}{165}`` / ``\\dfrac{...}{...}``). بوّابة D-152 الأصلية كانت
        عمياء عن ``\\frac`` — المحتوى الرسمي يكتب كل المقامات بها، فلم تُطلَق
        البوّابة قط وتسرّب فضاء عينة وهمي (C(14,3)=364) للطالب.
        """
        denoms: set[int] = set()
        for _, den in re.findall(r"(\d+)\s*/\s*(\d+)", text):
            if int(den) > 1:
                denoms.add(int(den))
        for _, den in re.findall(r"\\d?frac\{(\d+)\}\{(\d+)\}", text):
            if int(den) > 1:
                denoms.add(int(den))
        return denoms

    @classmethod
    def _detect_total(cls, text: str, fallback: int) -> int:
        """يكشف المجموع الصريح (مثل '11 كرة'، '8 بطاقات') أو مجموع العناصر.

        D-077 (V17.0): يتجاهل الأرقام في سياق السحب — «نسحب 3 كرات» يعني عدد
        السحبات لا حجم الكيس. الخلط بينهما كان يُنتج مقاماً خاطئاً (2/3 بدل 2/2).
        المجموع الصريح يجب أن يكون ≥ مجموع المكوّنات المستخرَجة (ground truth).
        """
        normalized = cls._normalize(text)
        draw_markers = (
            "نسحب",
            "يسحب",
            "تسحب",
            "سحب",
            "ناخذ",
            "ياخذ",
            "نختار",
            "اختيار",
            "اختر",
            "سحبه",
            "tirage",
        )
        best = fallback
        for m in re.finditer(
            r"(\d{1,3})\s*(?:كرة|كرات|بطاقة|بطاقات|قطعة|قطع|عنصر|عناصر|حبة|حبات|كرية|كريات)",
            normalized,
        ):
            value = int(m.group(1))
            window = normalized[max(0, m.start() - 18) : m.start()]
            if any(dm in window for dm in draw_markers):
                continue  # عدد سحبات لا حجم كيس
            if value >= fallback >= 1:
                best = max(best, value)
        return best

    @classmethod
    def _detect_replacement(cls, text: str) -> bool:
        """True = مستقل/مع الإرجاع، False = شرطي/بدون إرجاع (افتراضي)."""
        normalized = cls._normalize(text)
        if any(cls._normalize(p) in normalized for p in _WITHOUT_REPLACEMENT):
            return False
        return any(cls._normalize(p) in normalized for p in _WITH_REPLACEMENT)

    @classmethod
    def _detect_draws(cls, text: str) -> int:
        """عدد السحبات (1 أو 2) — يكتشف المثنى/التعداد/«على التوالي»."""
        normalized = cls._normalize(text)
        two_markers = (
            "بطاقتين",
            "بطاقتان",
            "كرتين",
            "كرتان",
            "سحبتين",
            "مرتين",
            "على التوالي",
            "3 كرات",
            "ثلاث كرات",
            "بالتتابع",
            "deux",
        )
        if any(m in normalized for m in two_markers):
            return 2
        return 1

    @classmethod
    def _detect_draw_mode(cls, text: str) -> str:
        """D-078 (V19.0): «simultaneous» (دفعة واحدة) | «sequential» (على التوالي) | «single».

        المتزامن له الأولوية: «نسحب 3 كرات دفعة واحدة» تأليفي حتى لو ذُكر عدد>1.
        """
        normalized = cls._normalize(text)
        if any(cls._normalize(m) in normalized for m in _SIMULTANEOUS_MARKERS):
            return "simultaneous"
        if any(cls._normalize(m) in normalized for m in _SEQUENTIAL_MARKERS):
            return "sequential"
        return "single"

    @classmethod
    def _detect_draw_count(cls, text: str, default: int = 2) -> int:
        """عدد العناصر المسحوبة k (مثل «نسحب 3 كرات» → 3)."""
        normalized = cls._normalize(text)
        draw_verbs = ("نسحب", "يسحب", "تسحب", "سحب", "ناخذ", "نختار", "اختيار", "tirage", "tire")
        for m in re.finditer(
            r"(\d{1,2}|واحدة|كرتين|كرتان|ثلاث|ثلاثة|اربع|اربعة|خمس|خمسة)\s*"
            r"(?:كرات|كرة|بطاقات|بطاقة|قطع|قطعة|عناصر|عنصر)?",
            normalized,
        ):
            window = normalized[max(0, m.start() - 18) : m.start()]
            if not any(v in window for v in draw_verbs):
                continue
            tok = m.group(1)
            if "كرتين" in tok or "كرتان" in tok:
                return 2
            val = cls._as_int(tok)
            if val and val >= 1:
                return val
        return default

    @classmethod
    def is_confusion(cls, text: str) -> bool:
        """D-078 (V19.0): يكشف إشارات الحيرة (Frustration Detector) لتفعيل الأداة البصرية."""
        normalized = cls._normalize(text)
        return any(cls._normalize(m) in normalized for m in _CONFUSION_MARKERS)

    @classmethod
    def is_visual_request(cls, text: str) -> bool:
        """ISS-114 (D-106): هل يطلب الطالب توليد واجهة صريحاً؟ يوجّه للأداة
        البصرية المُهيكلة بدل ترك الـ LLM يكتب HTML خاماً.

        D-120: case-insensitive — «Generate UI» (حرف كبير) يطابق «generate ui».
        """
        normalized = cls._normalize(text).lower()
        return any(cls._normalize(m).lower() in normalized for m in _VISUAL_REQUEST_MARKERS)

    @classmethod
    def _has_followup_probability_intent(cls, text: str) -> bool:
        """ISS-110 (D-101): هل السؤال الحالي متابعة لخطوة احتمالية من السياق؟

        يلتقط متابعات مثل «احسب الأمل الرياضي E(X)» أو «P(A)» التي لا تحمل
        كلمة احتمالية صريحة لكنها تستهدف خطوة من تمرين الاحتمالات في الـ history.

        D-120: المطابقة case-insensitive (مرآة `_detect_focus_step` التي تُحوِّل
        لأحرف صغيرة). بدونها `"p("` لا يطابق `P(A)` (حرف كبير) فتسقط متابعات
        P(A)/P(B)/P(C)/E(X) لمسار LLM (تسرّب «determination»).
        """
        normalized = cls._normalize(text).lower()
        return any(cls._normalize(m).lower() in normalized for m in _FOLLOWUP_PROBABILITY_INTENT)

    # ── الحالة المستحيلة (Protocol V26.2) — short-circuit قبل أي حساب ─────────────────
    _DRAW_VERBS: tuple[str, ...] = (
        "نسحب",
        "يسحب",
        "تسحب",
        "سحب",
        "ناخذ",
        "ياخذ",
        "نختار",
        "اختيار",
        "اختر",
        "tirage",
        "tire",
    )

    @classmethod
    def _detect_requested_color_count(cls, question: str) -> tuple[str, str, int] | None:
        """يستخرج (label_pos, label_neg, k) من *عبارة السحب* فقط.

        يتطلّب أن يكون اللون في طلب السحب — مسبوقاً بعدد وقريباً من فعل سحب
        («نسحب 3 كرات بيضاء»). لا يكفي ذكر اللون في وصف المخزون («كيس فيه كرتان
        بيضاوان، نسحب 3 كرات») — هناك السحب عامّ لا يخصّ لوناً، فلا استحالة.
        """
        tokens = cls._tokenize(question)
        for keywords, label_pos, label_neg in _COLOR_GROUPS:
            color_idx = next(
                (i for i, tok in enumerate(tokens) if any(kw in tok for kw in keywords)),
                None,
            )
            if color_idx is None:
                continue
            # فعل سحب ضمن نافذة قبل اللون (يثبت أن اللون جزء من طلب السحب).
            window_start = max(0, color_idx - 6)
            has_draw_verb = any(
                any(v in tokens[j] for v in cls._DRAW_VERBS) for j in range(window_start, color_idx)
            )
            if not has_draw_verb:
                continue
            k = cls._count_before(tokens, color_idx, span=4)
            if k is None or k < 1:
                continue
            return (label_pos, label_neg, k)
        return None

    @classmethod
    def _available_count_for(cls, label_pos: str, text: str) -> int | None:
        """المتاح فعلاً من صنف ما داخل نص (المخزون) — أو None إن لم يُذكَر."""
        for lp, _neg, count in cls._extract_count_entities(text):
            if lp == label_pos:
                return count
        return None

    @classmethod
    def _detect_impossible_draw(
        cls, question: str, history_text: str, combined: str
    ) -> ImpossibleCaseOutput | None:
        """V26.2: يكشف طلب سحب k من صنف لا يملك إلا m<k → قصة بصرية بدل حساب.

        - الكمية المطلوبة k واللون يُقرآن من *عبارة السحب* في السؤال (binding صارم).
        - المتاح m يُقرأ من *المخزون* (التاريخ مفضّل — يحمل تركيبة الكيس الحقيقية؛
          فالعدد الملتصق باللون في عبارة السحب هو المطلوب لا المتاح).
        - مع الإرجاع: السحب ممكن دائماً (لا استحالة) → لا تفعيل.
        - إن k > m (بلا إرجاع) → short-circuit إلى الحالة المستحيلة.
        """
        # مع الإرجاع لا توجد استحالة (يمكن سحب نفس اللون مراراً).
        if cls._detect_replacement(combined):
            return None

        binding = cls._detect_requested_color_count(question)
        if binding is None:
            return None
        label_pos, _label_neg, requested = binding

        # المتاح: المخزون (التاريخ) أولاً، ثم السؤال كحلّ أخير.
        available = cls._available_count_for(label_pos, history_text)
        if available is None:
            available = cls._available_count_for(label_pos, question)
        if available is None:
            return None

        if requested <= available:
            return None  # ليس مستحيلاً — يُترك لمسار الحساب العادي.

        color_token = _COLOR_CSS_TOKEN.get(label_pos, "white")
        item_plural = label_pos.replace("كرة", "كرات", 1)
        message = (
            f"كيف نسحب {requested} {item_plural} ونحن لا نملك سوى {available} منها؟ "
            f"إذن هذه العملية مستحيلة، واحتمال حدوثها هو صفر."
        )
        return ImpossibleCaseOutput(
            numerical_state=ImpossibleNumericalState(
                available_items=available,
                requested_items=requested,
                item_color=color_token,
            ),
            pedagogical_message=message,
            item_label=label_pos,
        )

    # ── الاستراتيجية 1: فضاء متساوي الاحتمال (نرد / قطعة نقدية) ───────────────────────
    @classmethod
    def _strategy_universe(
        cls, question: str, user_history_text: str, combined: str
    ) -> ProbabilityModelOutput | None:
        # ISS-114 (D-106 · مرآة D-102): مُشغِّلات فضاء العيّنة (نرد/عملة) تُؤخذ من
        # نص الطالب فقط (السؤال + رسائله) — أمثلة المساعد التوضيحية («رمي نردٍ
        # ست وجوه») ليست دليلاً. بدون هذا القيد كان قالب النرد العام يطغى على
        # تركيبة الكيس الحقيقية حين يذكر المساعد مثالاً بالنرد (كارثة حية).
        trigger = cls._normalize(f"{question}\n{user_history_text}")
        is_dice = any(k in trigger for k in ("نرد", "زهر", "dice", "حجر النرد", "حجر نرد", "dé"))
        is_coin = any(k in trigger for k in ("قطعة نقدية", "قطعة نقود", "عملة", "coin", "piece"))
        if not (is_dice or is_coin):
            return None

        # استخراج عدد الأوجه يبقى من النص الكامل (قد يرد في نص التمرين).
        normalized = cls._normalize(combined)

        if is_coin:
            # وجه/كتابة — فضاء من وجهين
            tree = cls._sanitize_node(cls._root([cls._node("وجه", 1, 2), cls._node("كتابة", 1, 2)]))
            comp = [
                CompositionItem(label="وجه", count=1, p_num=1, p_den=2, p_decimal=0.5),
                CompositionItem(label="كتابة", count=1, p_num=1, p_den=2, p_decimal=0.5),
            ]
            return ProbabilityModelOutput(
                strategy="universe",
                total=2,
                with_replacement=True,
                focal_label="وجه",
                focal_label_neg="كتابة",
                composition=comp,
                tree=tree,
                title="فضاء العيّنة (قطعة نقدية)",
            )

        # نرد: عدد الأوجه (افتراضي 6)
        faces = 6
        m = re.search(r"من\s*1\s*(?:الى|الي|حتى|ل)\s*(\d{1,2})", normalized)
        if m:
            faces = max(2, int(m.group(1)))

        # القسمة القياسية زوجي/فردي (أوضح تربوياً، تغطّي السؤال النموذجي).
        even_count = faces // 2
        odd_count = faces - even_count
        comp = [
            CompositionItem(
                label="رقم زوجي",
                count=even_count,
                p_num=even_count,
                p_den=faces,
                p_decimal=cls._decimal(even_count, faces),
            ),
            CompositionItem(
                label="رقم فردي",
                count=odd_count,
                p_num=odd_count,
                p_den=faces,
                p_decimal=cls._decimal(odd_count, faces),
            ),
        ]
        tree = cls._sanitize_node(
            cls._root(
                [
                    cls._node("رقم زوجي", even_count, faces),
                    cls._node("رقم فردي", odd_count, faces),
                ]
            )
        )
        return ProbabilityModelOutput(
            strategy="universe",
            total=faces,
            with_replacement=True,
            focal_label="رقم زوجي",
            focal_label_neg="رقم فردي",
            composition=comp,
            tree=tree,
            title="فضاء العيّنة (حجر النرد)",
        )

    # ── الاستراتيجية 2: شجرة شرطية بالنِّسَب (مصنع / Bayesian) ──────────────────────────
    _PRIMARY_ENTITY_RE = re.compile(
        r"(الالة|الماكينة|المصنع|الفئة|الصنف|القسم|الفرع|المورد|machine)\s*([A-Zأ-يa-z\d]+)"
    )
    _DEFECT_WORDS: tuple[str, ...] = ("معيب", "معيبة", "تالف", "تالفة", "عاطل", "خربان", "défect")

    @staticmethod
    def _beautify_label(label: str) -> str:
        """يُعيد المدّة المحذوفة في التطبيع لأجل عرض تربوي أنيق (الالة → الآلة)."""
        if label.startswith("الالة"):
            return "الآلة" + label[len("الالة") :]
        return label

    @classmethod
    def _strategy_conditional(cls, combined: str) -> ProbabilityModelOutput | None:
        normalized = cls._normalize(combined)
        # كل النِّسَب المئوية مع مواضعها
        percents = [(int(m.group(1)), m.start()) for m in re.finditer(r"(\d{1,3})\s*%", normalized)]
        if len(percents) < 3:
            return None  # نحتاج فرعين رئيسيين + نسبة شرطية واحدة على الأقل

        def nearest_primary(pos: int) -> str | None:
            best_label = None
            best_dist = 10**9
            for m in cls._PRIMARY_ENTITY_RE.finditer(normalized):
                if m.start() <= pos and pos - m.start() < best_dist:
                    best_dist = pos - m.start()
                    label = m.group(0).strip()
                    best_label = label
            return best_label

        primaries: dict[str, int] = {}
        defects: dict[str, int] = {}
        order: list[str] = []
        for value, pos in percents:
            label = nearest_primary(pos)
            if label is None:
                continue
            window = normalized[max(0, pos - 45) : pos + 3]
            is_defect = any(dw in window for dw in cls._DEFECT_WORDS)
            if is_defect:
                defects[label] = value
            elif label not in primaries:
                primaries[label] = value
                order.append(label)

        if len(primaries) < 2:
            return None

        attr_word = "معيب"
        attr_neg = "سليم"
        branches: list[dict[str, object]] = []
        comp: list[CompositionItem] = []
        for label in order:
            prim = primaries[label]
            display = cls._beautify_label(label)
            comp.append(
                CompositionItem(
                    label=display,
                    count=prim,
                    p_num=prim,
                    p_den=100,
                    p_decimal=cls._decimal(prim, 100),
                )
            )
            children: list[dict[str, object]] = []
            if label in defects:
                d = defects[label]
                children = [
                    cls._node(attr_word, d, 100),
                    cls._node(attr_neg, 100 - d, 100),
                ]
            branches.append(cls._node(display, prim, 100, children or None))

        tree = cls._sanitize_node(cls._root(branches))
        return ProbabilityModelOutput(
            strategy="conditional",
            total=100,
            with_replacement=True,
            focal_label=cls._beautify_label(order[0]),
            focal_label_neg=cls._beautify_label(order[1]) if len(order) > 1 else "أخرى",
            composition=comp,
            tree=tree,
            title="شجرة الاحتمالات الشرطية",
        )

    # ── السحب الآني (Combinatorics) — Protocol V19.0 §2.B ────────────────────────────
    # V30.0 — الرسالة التربوية للمجموعة المستحيلة (بدل C_n^k = 0 المضلِّل).
    _SUBGROUP_IMPOSSIBLE_MSG: str = "مستحيل لهذا الصنف فقط (العدد المتوفر غير كافٍ لسحب المطلوب)"

    @classmethod
    def _color_for(cls, label: str) -> str:
        """رمز CSS للون من تسمية المجموعة (red/white/...) — '' إن لا لون."""
        return _COLOR_CSS_TOKEN.get(label, "")

    @classmethod
    def _build_combinations(
        cls,
        comp_raw: list[tuple[str, str, int]],
        total: int,
        combined: str,
        *,
        deep_dive: bool = False,
    ) -> CombinationsModelOutput | None:
        """يبني نموذج تأليفات للسحب الآني: C(n,k) + C(count,k) لكل مجموعة.

        «نسحب k كرات دفعة واحدة» = اختيار غير مرتَّب → فضاء العيّنة C(n,k). لكل
        مجموعة (لون/صنف) عدد تأليفاتها C(count,k) (حدث «k من نفس الصنف»). ممنوع
        تمثيل هذا بشجرة تتابعية (كارثة تربوية).

        ## V30.0 — حارس الحلقة الداخلية (Sub-Group Leak Surgery)
        حين ``k > count`` لمجموعة ما (مثل سحب 3 من كيس فيه كرتان بيضاوان فقط):
        لا نستدعي ``math.comb`` ولا نُخرِج ``C_2^3 = 0``؛ بل نضع ``is_possible=False``
        ورسالة تربوية صريحة. هكذا لا يتسرّب الصفر المضلِّل إلى الواجهة أبداً.
        """
        import math

        k = cls._detect_draw_count(combined, default=2)
        if k < 1 or k > total:
            return None
        total_comb = math.comb(total, k)
        if total_comb < 1:
            return None

        # Validation Gate (D-152 + ISS-120/D-153): رفض total_comb المتناقض مع
        # المقامات المُصرَّح بها في النص — يشمل صيغة LaTeX \frac التي كانت
        # البوّابة الأصلية عمياء عنها (فلم تُطلَق قط على المحتوى الرسمي).
        stated_denoms = cls._stated_denominators(combined)
        if stated_denoms and not any(
            (total_comb % d == 0) or (d % total_comb == 0) for d in stated_denoms
        ):
            return None

        groups: list[CombinationGroup] = []
        same_group = 0
        for label_pos, _neg, count in comp_raw:
            c = min(count, total)
            color = cls._color_for(label_pos)
            # ── الحارس: اختيار k من مجموعة فيها c < k مستحيل ──────────────────
            if k > c:
                groups.append(
                    CombinationGroup(
                        label=label_pos,
                        count=c,
                        favorable_combinations=0,
                        is_possible=False,
                        pedagogical_string=cls._SUBGROUP_IMPOSSIBLE_MSG,
                        color=color,
                    )
                )
                continue
            fav = math.comb(c, k)
            same_group += fav
            groups.append(
                CombinationGroup(
                    label=label_pos,
                    count=c,
                    favorable_combinations=fav,
                    is_possible=True,
                    pedagogical_string=f"C({c},{k}) = {fav}",
                    color=color,
                )
            )

        # ── القصة البصرية الشاملة (Deep Dive) — حالة الكيس + تحليل الأحداث ──────
        urn_state = [
            {"label": g.label, "count": g.count, "color": g.color or "muted"} for g in groups
        ]
        event_analysis = [
            {
                "label": g.label,
                "is_possible": g.is_possible,
                "pedagogical_string": g.pedagogical_string,
                "color": g.color or "muted",
                "value": g.favorable_combinations,
            }
            for g in groups
        ]

        return CombinationsModelOutput(
            n=total,
            k=k,
            total_combinations=total_comb,
            groups=groups,
            same_group_favorable=same_group,
            deep_dive=deep_dive,
            urn_state=urn_state,
            event_analysis=event_analysis,
            title=f"تأليفات السحب الآني (اختيار {k} من {total})",
        )

    @classmethod
    def _build_full_exercise_story(
        cls,
        comp_raw: list[tuple[str, str, int]],
        total: int,
        combined: str,
    ) -> FullExerciseStoryOutput | None:
        """يبني القصة التربوية الشاملة لتمرين سحب آني كامل — Protocol V31.5.

        يُولِّد سلسلة خطوات بصرية مستقلّة (Carousel) بدل مكوّن واحد، حين يكون
        الطالب حائراً. الخطوات معمّمة (لا overfitting): تُشتق من التركيبة ووضع
        السحب لا من مفردات مسألة بعينها:

          0. **المعطيات** (urn): حالة الكيس — كل صنف بعدده ولونه.
          1. **فضاء العيّنة** (combinations): C(n, k) — كل طرق السحب الآني.
          2. **الحدث «k من نفس الصنف»** (event_breakdown): لكل صنف C(count, k)؛
             المجموعة المستحيلة (count < k) تحمل ``is_possible=False`` ورسالة
             تربوية — لا C_n^k=0 ولا كسر صفري يتسرّب.
          3. **المتغيّر العشوائي X** (distribution): توزيع فوق-هندسي لعدد عناصر
             الصنف المحوري ضمن السحب — يُحسب حتمياً بـ math.comb (P(X=i) =
             C(m,i)·C(n-m,k-i) / C(n,k)). يُضاف فقط حين يكون ذا معنى (≥ صنفان).

        كل عقدة عددية (كسر) تُمرَّر مضمونةً عبر ``_sanitize_node`` ضمنياً (لا
        قسمة على صفر، لا بسط > مقام). يُرجِع None إن تعذّر بناء أي خطوة.
        """
        import math

        k = cls._detect_draw_count(combined, default=2)
        if k < 1 or k > total:
            return None
        total_comb = math.comb(total, k)
        if total_comb < 1:
            return None

        # Validation Gate (D-152 + ISS-120/D-153): رفض total_comb المتناقض مع
        # المقامات المُصرَّح بها في النص — يشمل صيغة LaTeX \frac التي كانت
        # البوّابة الأصلية عمياء عنها (فلم تُطلَق قط على المحتوى الرسمي).
        stated_denoms = cls._stated_denominators(combined)
        if stated_denoms and not any(
            (total_comb % d == 0) or (d % total_comb == 0) for d in stated_denoms
        ):
            return None

        steps: list[ExerciseStep] = []

        # ── الخطوة 0: المعطيات (urn) ──────────────────────────────────────────
        urn = [
            {"label": lp, "count": min(c, total), "color": cls._color_for(lp) or "muted"}
            for lp, _neg, c in comp_raw
        ]
        groups_summary = "، ".join(f"{lp} ({min(c, total)})" for lp, _neg, c in comp_raw)
        steps.append(
            ExerciseStep(
                step_index=0,
                step_id="data",
                title="① فهم المعطيات",
                render_kind="urn",
                visual_directives={"animation_hint": "fill_urn", "render_kind": "urn"},
                numerical_state={"total": total, "groups": urn},
                pedagogical_message=(
                    f"نبدأ بفهم ما في الكيس: {total} عنصراً موزّعة هكذا — {groups_summary}. "
                    "نسحب منها عيّنة دفعةً واحدة (الترتيب لا يهمّ)."
                ),
                interactive={
                    "question": f"نسحب {k} كرات دفعةً واحدة — هل يهمّ ترتيب سحبها؟",
                    "answer_kind": "choice",
                    "choices": ["نعم، الترتيب يهمّ", "لا، لا يهمّ الترتيب"],
                    "expected_index": 1,
                    "hint": "دفعةً واحدة = لا يوجد أوّل/ثانٍ/ثالث ⇒ الترتيب لا يهمّ.",
                },
            )
        )

        # ── الخطوة 1: فضاء العيّنة (combinations) ──────────────────────────────
        steps.append(
            ExerciseStep(
                step_index=1,
                step_id="sample_space",
                title="② فضاء العيّنة",
                render_kind="combinations",
                visual_directives={
                    "animation_hint": "count_choices",
                    "render_kind": "combinations",
                },
                numerical_state={"n": total, "k": k, "total_combinations": total_comb},
                pedagogical_message=(
                    f"بما أننا نسحب {k} دفعةً واحدة فالترتيب لا يهمّ، نستعمل التأليفات. "
                    f"عدد كل العيّنات الممكنة هو C({total},{k}) = {total_comb}."
                ),
                interactive={
                    "question": f"كم عدد طرق اختيار {k} كرات من بين {total}؟ (اكتب العدد)",
                    "answer_kind": "number",
                    "expected": total_comb,
                    "hint": f"الترتيب لا يهمّ ⇒ استعمل التأليفات: C({total},{k}).",
                },
            )
        )

        # ── الخطوة 2: الحدث «k من نفس الصنف» (event_breakdown) ─────────────────
        breakdown: list[dict[str, object]] = []
        same_group = 0
        for lp, _neg, raw_count in comp_raw:
            c = min(raw_count, total)
            color = cls._color_for(lp) or "muted"
            if k > c:
                breakdown.append(
                    {
                        "label": lp,
                        "count": c,
                        "favorable": 0,
                        "is_possible": False,
                        "pedagogical_string": cls._SUBGROUP_IMPOSSIBLE_MSG,
                        "color": color,
                    }
                )
                continue
            fav = math.comb(c, k)
            same_group += fav
            breakdown.append(
                {
                    "label": lp,
                    "count": c,
                    "favorable": fav,
                    "is_possible": True,
                    "pedagogical_string": f"C({c},{k}) = {fav}",
                    "color": color,
                }
            )
        steps.append(
            ExerciseStep(
                step_index=2,
                step_id="same_color_event",
                title="③ الحدث: العناصر من نفس الصنف",
                render_kind="event_breakdown",
                visual_directives={
                    "animation_hint": "highlight_groups",
                    "render_kind": "event_breakdown",
                },
                numerical_state={
                    "groups": breakdown,
                    "same_group_favorable": same_group,
                    "total_combinations": total_comb,
                    "p_num": same_group,
                    "p_den": total_comb,
                },
                pedagogical_message=(
                    "نحسب لكل صنف عدد طرق اختيار العناصر منه؛ الصنف الذي لا يكفي عدده "
                    "للسحب يكون مستحيلاً (لا نكتب صفراً مضلِّلاً). نجمع الممكن منها: "
                    f"الاحتمال = {same_group}/{total_comb}."
                ),
                interactive={
                    "question": f"كم عدد طرق اختيار {k} كرات من نفس اللون؟ (اجمع كل لون ممكن)",
                    "answer_kind": "number",
                    "expected": same_group,
                    "hint": (
                        f"لكل لون احسب C(عدد اللون,{k}) — اللون الذي عدده أقل من {k} مستحيل — ثم اجمع."
                    ),
                },
            )
        )

        # ── الخطوة 3: المتغيّر العشوائي X (distribution) — حتمي بـ math.comb ─────
        if len(comp_raw) >= 2:
            focal_label, _focal_neg, focal_raw = comp_raw[0]
            m = min(focal_raw, total)
            others = total - m
            distribution: list[dict[str, object]] = []
            for i in range(0, k + 1):
                if i > m or (k - i) > others:
                    continue  # حالة مستحيلة — لا تُدرَج (لا 0 مضلِّل)
                num = math.comb(m, i) * math.comb(others, k - i)
                if num <= 0:
                    continue
                distribution.append(
                    {
                        "value": i,
                        "p_num": num,
                        "p_den": total_comb,
                        "p_decimal": cls._decimal(num, total_comb),
                    }
                )
            if distribution:
                steps.append(
                    ExerciseStep(
                        step_index=3,
                        step_id="random_variable",
                        title=f"④ المتغيّر العشوائي X: عدد «{focal_label}» المسحوبة",
                        render_kind="distribution",
                        visual_directives={
                            "animation_hint": "build_distribution",
                            "render_kind": "distribution",
                        },
                        numerical_state={
                            "variable_label": "X",
                            "focal_label": focal_label,
                            "total": total_comb,
                            "distribution": distribution,
                        },
                        pedagogical_message=(
                            f"نعرّف X = عدد «{focal_label}» في السحب. لكل قيمة i نحسب "
                            f"P(X=i) = C({m},i)·C({others},{k}−i) / C({total},{k}). "
                            "مجموع الاحتمالات يساوي 1 دائماً."
                        ),
                    )
                )

        return FullExerciseStoryOutput(
            n=total,
            k=k,
            total_combinations=total_comb,
            exercise_steps=steps,
            title=f"الشرح البصري الشامل (سحب {k} من {total})",
        )

    # ── الاستراتيجية 3: تركيبة عددية معمّمة (كرات / بطاقات / أصناف) ────────────────────
    @classmethod
    def _strategy_composition(
        cls, question: str, history_text: str, combined: str
    ) -> ProbabilityModelOutput | CombinationsModelOutput | FullExerciseStoryOutput | None:
        comp_raw = cls._extract_count_entities(question)
        source = question
        if not comp_raw and history_text:
            comp_raw = cls._extract_count_entities(history_text)
            source = history_text
        if not comp_raw:
            return None

        items_total = sum(c[2] for c in comp_raw)
        total = cls._detect_total(source, items_total)
        # ground truth: المجموع لا يقل عن مجموع المكوّنات، وكل عدد ≤ المجموع.
        total = max(total, items_total)
        if total < 2:
            return None

        # D-078 (V19.0) — الموجِّه التربوي: «دفعة واحدة» = سحب آني → تأليفي
        # (Combinatorics)، ممنوع تمثيله بشجرة تتابعية.
        draw_mode = cls._detect_draw_mode(combined)
        if draw_mode == "simultaneous":
            # V31.5 (Full Exercise OS): حيرة الطالب («لم أفهم أي شيء») تُفعِّل
            # القصة التربوية الشاملة (Carousel متعدّد الخطوات يغطّي التمرين كاملاً)
            # بدل مكوّن تأليفات واحد. غير الحائر → مكوّن تأليفات مفرد.
            deep_dive = cls.is_confusion(question) or cls.is_confusion(combined)
            if deep_dive:
                story = cls._build_full_exercise_story(comp_raw, total, combined)
                if story is not None:
                    return story
            combo = cls._build_combinations(comp_raw, total, combined, deep_dive=deep_dive)
            if combo is not None:
                return combo
            # إن تعذّر بناء التأليف (k غير صالح) لا نسقط لشجرة مضلِّلة — نفشل بنظافة.
            return None

        with_replacement = cls._detect_replacement(combined)
        draws = cls._detect_draws(combined)

        composition = [
            CompositionItem(
                label=label_pos,
                count=min(count, total),
                p_num=min(count, total),
                p_den=total,
                p_decimal=cls._decimal(min(count, total), total),
            )
            for label_pos, _neg, count in comp_raw
        ]

        # المستوى الثاني يُبنى فقط حين يكون ذا معنى:
        # - مع الإرجاع: مستقل، آمن دائماً.
        # - بدون إرجاع: يتطلّب total ≥ 3 (denom2 = total-1 ≥ 2) لتفادي كسور
        #   منحلّة (0/1، 1/1) أو قسمة على صفر — D-077 (V17.0).
        expand_second = draws >= 2 and (with_replacement or total >= 3)

        level1: list[dict[str, object]] = []
        for label_pos, _neg, count in comp_raw:
            children: list[dict[str, object]] = []
            if expand_second:
                if with_replacement:
                    children = [cls._node(lp, cnt, total) for lp, _n, cnt in comp_raw]
                else:
                    denom2 = total - 1  # ≥ 2 (مضمون بـ expand_second)
                    for lp, _n, cnt in comp_raw:
                        sub = cnt - 1 if lp == label_pos else cnt
                        children.append(cls._node(lp, max(sub, 0), denom2))
            level1.append(cls._node(label_pos, min(count, total), total, children or None))

        tree = cls._sanitize_node(cls._root(level1))
        focal_pos, focal_neg, _ = comp_raw[0]
        return ProbabilityModelOutput(
            strategy="composition",
            total=total,
            with_replacement=with_replacement,
            focal_label=focal_pos,
            focal_label_neg=focal_neg,
            composition=composition,
            tree=tree,
            title="شجرة الاحتمالات",
        )

    # ── نقطة الدخول الرئيسية (حتمية، بلا LLM) ─────────────────────────────────────────
    def analyze(
        self, payload: ProbabilityInput | str
    ) -> (
        ProbabilityModelOutput
        | CombinationsModelOutput
        | FullExerciseStoryOutput
        | ImpossibleCaseOutput
        | ProbabilityFailure
    ):
        """يحلّل المسألة عبر أنماط معمّمة ويُرجِع نموذجاً (شجرة/تأليفات/مستحيل) أو فشلاً."""
        t0 = time.perf_counter()
        if isinstance(payload, str):
            payload = ProbabilityInput(question=payload)

        question = payload.question or ""
        history_text = ""
        user_history_text = ""
        if payload.history:
            recent = [m for m in payload.history[-6:] if isinstance(m, dict)]
            history_text = " ".join(str(m.get("content", ""))[:2000] for m in recent)
            # ISS-114 (D-106): نص الطالب فقط لمُشغِّلات فضاء العيّنة (لا رسائل المساعد).
            user_history_text = " ".join(
                str(m.get("content", ""))[:2000] for m in recent if m.get("role") == "user"
            )
        combined = f"{question}\n{history_text}".strip()

        normalized = self._normalize(combined)
        question_norm = self._normalize(question)
        # ISS-114 (D-106): طلب توليد واجهة صريح + إشارة احتمالية في السؤال نفسه
        # («قم بتوليد واجهة تشرح الحادثة P(A)») يمرّ بوابة السياق حتى في محادثة
        # جديدة بلا history — وإلا يسقط للـ LLM فيكتب HTML خاماً.
        _visual_q = self.is_visual_request(question) and (
            "p(" in question_norm or "حادث" in question_norm or "احتمال" in question_norm
        )
        if (
            not any(self._normalize(c) in normalized for c in _PROBABILITY_CONTEXT)
            and not _visual_q
        ):
            return self._fail("no_probability_context", "none", t0)

        # ISS-110 (D-101): سياق الاحتمالات من الـ history وحده لا يكفي.
        # السؤال الحالي نفسه يجب أن يحمل نية احتمالية: سياق صريح، أو حيرة
        # (متابعة بيداغوجية)، أو إشارة خطوة متابعة (E(X)/جداء/نفس اللون...)،
        # أو طلب توليد واجهة صريح (ISS-114).
        # بدون هذه البوابة: «اعطني تمرين الدوال العددية» بعد تمرين احتمالات
        # كان يُولِّد combinations_visualizer من كيس التمرين السابق (كارثة حية).
        q_has_context = any(self._normalize(c) in question_norm for c in _PROBABILITY_CONTEXT)
        if (
            not q_has_context
            and not _visual_q
            and history_text
            and not (self.is_confusion(question) or self._has_followup_probability_intent(question))
        ):
            return self._fail("no_probability_intent_in_question", "none", t0)

        # خط أنابيب الاستراتيجيات — أول نجاح يفوز (deterministic-first).
        # V26.1: الحالة المستحيلة لها الأولوية القصوى — short-circuit قبل أي حساب.
        # ISS-114 (D-106): التركيبة الحقيقية المستخرَجة من نص التمرين تسبق فضاء
        # العيّنة العام (نرد/عملة). سؤال نرد حقيقي بلا تركيبة → composition تُرجع
        # None → universe يعمل؛ لكن كيس 11 كرة في الـ history يهزم قالب النرد.
        for builder in (
            lambda: self._detect_impossible_draw(question, history_text, combined),
            lambda: self._strategy_conditional(combined),
            lambda: self._strategy_composition(question, history_text, combined),
            lambda: self._strategy_universe(question, user_history_text, combined),
        ):
            try:
                model = builder()
            except Exception:
                logger.warning("probability_strategy_failed", exc_info=True)
                model = None
            if model is not None:
                duration = time.perf_counter() - t0
                model.duration_ms = int(duration * 1000)
                strategy_label = (
                    getattr(model, "strategy", None)
                    or getattr(model, "draw_mode", None)
                    or getattr(model, "ui_mode", "unknown")
                )
                _record_metric("success", strategy_label, duration)
                return model

        return self._fail("no_model_extracted", "none", t0)

    @staticmethod
    def _fail(reason: str, strategy: str, t0: float) -> ProbabilityFailure:
        _record_metric("fallback", strategy, time.perf_counter() - t0)
        return ProbabilityFailure(reason=reason)


__all__ = [
    "CombinationGroup",
    "CombinationsModelOutput",
    "CompositionItem",
    "ExerciseStep",
    "FullExerciseStoryOutput",
    "ImpossibleCaseOutput",
    "ImpossibleNumericalState",
    "ImpossibleVisualDirectives",
    "ProbabilityCalculatorSkill",
    "ProbabilityFailure",
    "ProbabilityInput",
    "ProbabilityModelOutput",
]
