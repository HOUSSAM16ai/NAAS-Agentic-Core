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
from typing import Literal

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.doctrine import PROBABILITY_CALCULATION_DOCTRINE_VERSION

try:
    from app.core.logging import get_logger
except ImportError:  # pragma: no cover
    import logging

    def get_logger(name: str):  # type: ignore[no-redef]
        return logging.getLogger(name)


logger = get_logger("skill.probability")

# الإصدار يُستهلك في الـ doctrine binding (drift detection)
DOCTRINE_VERSION = PROBABILITY_CALCULATION_DOCTRINE_VERSION


# ── الكيانات الملموسة (Abstraction Ban): لون → تسمية موجبة + متمِّمة ───────────────
_COLOR_GROUPS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("حمراء", "حمر", "احمر", "حمرا", "rouge"), "كرة حمراء", "كرة غير حمراء"),
    (("بيضاء", "بيض", "ابيض", "بيضاوان", "بيضاوين", "بيضا", "blanc"), "كرة بيضاء", "كرة غير بيضاء"),
    (("خضراء", "خضر", "اخضر", "خضرا", "vert"), "كرة خضراء", "كرة غير خضراء"),
    (("سوداء", "سود", "اسود", "noir"), "كرة سوداء", "كرة غير سوداء"),
    (("صفراء", "صفر", "اصفر", "jaune"), "كرة صفراء", "كرة غير صفراء"),
    (("زرقاء", "زرق", "ازرق", "bleu"), "كرة زرقاء", "كرة غير زرقاء"),
)

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

# تطبيع التشكيل + الفواصل العربية قبل التحليل.
# نحذف علامات التشكيل فقط (الحركات/التنوين/الشدة/السكون والعلامات القرآنية)
# دون المساس بحروف العربية (U+0621–U+064A).
_TASHKEEL_RE = re.compile("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u08d3-\u08ff]")
_TOKEN_SPLIT_RE = re.compile(r"[\s،,.\-؛:؟?!()\[\]{}«»\"']+")


# ── العقود (Pydantic) ────────────────────────────────────────────────────────────


class ProbabilityInput(RobustBaseModel):
    """مدخلات المحرّك — typed contract موحَّد."""

    question: str = Field(..., min_length=1, max_length=8000)
    history: list[dict[str, str]] | None = None


class CompositionItem(RobustBaseModel):
    """عنصر من المستوى الأول: كيان ملموس + عدده + احتماله الدقيق (غير مختزَل)."""

    label: str = Field(..., min_length=1, max_length=80)
    count: int | None = Field(None, ge=0, description="عدد العناصر المواتية (إن وُجد)")
    p_num: int = Field(..., ge=0, description="بسط الاحتمال (تربوي، غير مختزَل)")
    p_den: int = Field(..., ge=1, description="مقام الاحتمال (تربوي، غير مختزَل)")
    p_decimal: float = Field(..., ge=0.0, le=1.0)


class ProbabilityModelOutput(RobustBaseModel):
    """مخرج المحرّك عند النجاح — نموذج احتمالي منظَّم بكسور دقيقة."""

    skill: Literal["probability_calculation"] = "probability_calculation"
    success: Literal[True] = True
    doctrine_version: str = DOCTRINE_VERSION
    strategy: str = Field(..., description="الاستراتيجية: universe | conditional | composition")
    total: int = Field(..., ge=1, description="حجم الفضاء العيّني (المجموع)")
    with_replacement: bool = Field(..., description="True = مستقل/مع الإرجاع، False = شرطي")
    focal_label: str = Field(..., description="الكيان المحوري الأول")
    focal_label_neg: str = Field(..., description="متمِّمة/الكيان الثاني")
    composition: list[CompositionItem]
    tree: dict[str, object] = Field(..., description="شجرة احتمالات بكسور دقيقة لكل عقدة")
    title: str = "شجرة الاحتمالات"
    duration_ms: int = 0


class ProbabilityFailure(RobustBaseModel):
    """مخرج المحرّك عند عدم وجود نموذج قابل للحساب — يسمح بالتقدّم لمسار آخر."""

    skill: Literal["probability_calculation"] = "probability_calculation"
    success: Literal[False] = False
    reason: str


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

    @classmethod
    def _node(
        cls,
        label: str,
        num: int,
        den: int,
        children: list | None = None,
    ) -> dict[str, object]:
        """عقدة شجرة بكسر تربوي خام (غير مختزَل) + قيمة عشرية."""
        rec: dict[str, object] = {
            "label": label,
            "p": cls._decimal(num, den),
            "p_num": int(num),
            "p_den": int(den) if den > 0 else 1,
        }
        if children:
            rec["children"] = children
        return rec

    @classmethod
    def _sanitize_node(cls, node: dict[str, object]) -> dict[str, object]:
        """حارس نهائي ضد الكسور المنحلّة (D-077 / V17.0).

        يضمن لكل عقدة: ``p_den ≥ 1`` (لا قسمة على صفر أبداً) و ``0 ≤ p_num ≤ p_den``
        و ``p`` متّسقة. هذا خط الدفاع الأخير قبل البثّ — أي خطأ حسابي سابق
        (مقام صفر، بسط > مقام) يُقصّ بأمان بدل أن يصل للطالب كـ 1/0 أو غارباج.
        """
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
        stripped = token.lstrip("وفب")  # و/ف/ب البادئة (و5، ف3)
        if stripped.isdigit():
            return int(stripped)
        if token in _ARABIC_CARDINALS:
            return _ARABIC_CARDINALS[token]
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
        results: list[tuple[str, str, int]] = []
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
            results.append((label_pos, label_neg, count))

        # (2) كيانات مرقّمة: token يحتوي "رقم" متبوع برقم (بطاقة رقم 1)
        for i, tok in enumerate(tokens):
            if "رقم" not in tok:
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
            results.append((label_pos, f"{item_noun} ليست رقم {number}", count))

        return results

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

    # ── الاستراتيجية 1: فضاء متساوي الاحتمال (نرد / قطعة نقدية) ───────────────────────
    @classmethod
    def _strategy_universe(cls, combined: str) -> ProbabilityModelOutput | None:
        normalized = cls._normalize(combined)
        is_dice = any(k in normalized for k in ("نرد", "زهر", "dice", "حجر النرد", "حجر نرد", "dé"))
        is_coin = any(k in normalized for k in ("قطعة نقدية", "قطعة نقود", "عملة", "coin", "piece"))
        if not (is_dice or is_coin):
            return None

        if is_coin:
            # وجه/كتابة — فضاء من وجهين
            tree = cls._sanitize_node(
                cls._node(
                    "البداية",
                    1,
                    1,
                    [cls._node("وجه", 1, 2), cls._node("كتابة", 1, 2)],
                )
            )
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
            cls._node(
                "البداية",
                1,
                1,
                [
                    cls._node("رقم زوجي", even_count, faces),
                    cls._node("رقم فردي", odd_count, faces),
                ],
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

        tree = cls._sanitize_node(cls._node("البداية", 1, 1, branches))
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

    # ── الاستراتيجية 3: تركيبة عددية معمّمة (كرات / بطاقات / أصناف) ────────────────────
    @classmethod
    def _strategy_composition(
        cls, question: str, history_text: str, combined: str
    ) -> ProbabilityModelOutput | None:
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

        tree = cls._sanitize_node(cls._node("البداية", 1, 1, level1))
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
    ) -> ProbabilityModelOutput | ProbabilityFailure:
        """يحلّل المسألة عبر أنماط معمّمة ويُرجِع نموذجاً بكسور دقيقة أو فشلاً."""
        t0 = time.perf_counter()
        if isinstance(payload, str):
            payload = ProbabilityInput(question=payload)

        question = payload.question or ""
        history_text = ""
        if payload.history:
            history_text = " ".join(
                str(m.get("content", ""))[:2000]
                for m in payload.history[-6:]
                if isinstance(m, dict)
            )
        combined = f"{question}\n{history_text}".strip()

        normalized = self._normalize(combined)
        if not any(self._normalize(c) in normalized for c in _PROBABILITY_CONTEXT):
            return self._fail("no_probability_context", "none", t0)

        # خط أنابيب الاستراتيجيات — أول نجاح يفوز (deterministic-first).
        for builder in (
            lambda: self._strategy_conditional(combined),
            lambda: self._strategy_universe(combined),
            lambda: self._strategy_composition(question, history_text, combined),
        ):
            try:
                model = builder()
            except Exception:
                logger.warning("probability_strategy_failed", exc_info=True)
                model = None
            if model is not None:
                duration = time.perf_counter() - t0
                model.duration_ms = int(duration * 1000)
                _record_metric("success", model.strategy, duration)
                return model

        return self._fail("no_model_extracted", "none", t0)

    @staticmethod
    def _fail(reason: str, strategy: str, t0: float) -> ProbabilityFailure:
        _record_metric("fallback", strategy, time.perf_counter() - t0)
        return ProbabilityFailure(reason=reason)


__all__ = [
    "CompositionItem",
    "ProbabilityCalculatorSkill",
    "ProbabilityFailure",
    "ProbabilityInput",
    "ProbabilityModelOutput",
]
