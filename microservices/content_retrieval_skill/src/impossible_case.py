"""
impossible_case.py — منطق الحالة المستحيلة (D-082).

المسؤولية الوحيدة:
  تحديد ما إذا كانت العملية الاحتمالية مستحيلة رياضياً،
  وإنتاج contract بصري واضح للـ frontend.

المبدأ التربوي:
  - لا رياضيات قبل الفهم الحدسي
  - 4 مراحل فقط: مشهد → سؤال → حركة → رسالة
  - الشرح الرياضي اختياري (زر "اشرح لي أكثر")

Contract (backend → frontend):
  {
    "is_impossible": bool,
    "case_type": "draw_exceeds_bag" | "none",
    "stage_1": { "bag_count": int, "requested": int },
    "stage_2": { "question": str },
    "stage_3": { "animation": "shake" | "freeze" | "none" },
    "stage_4": { "message": str },
    "deep_dive": { "formula": str, "explanation": str } | null
  }

قواعد صارمة (D-082):
  - لا شجرة احتمالات في الحالة المستحيلة
  - لا معادلات في stage_1/2/3
  - لا أكثر من فكرة واحدة في كل مرحلة
  - deep_dive يُعرض فقط عند طلب المستخدم
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Stage1Scene:
    """المرحلة 1: مشهد الكيس — بيانات فقط، لا شرح."""

    bag_count: int
    requested: int
    bag_label: str  # مثال: "كيس يحتوي على 2 كرة"
    request_label: str  # مثال: "تريد سحب 3 كرات"


@dataclass(frozen=True)
class Stage2Question:
    """المرحلة 2: سؤال حدسي بسيط — بدون معادلة."""

    question: str  # مثال: "هل يمكن أخذ 3 من 2؟"


@dataclass(frozen=True)
class Stage3Animation:
    """المرحلة 3: حركة بصرية قصيرة تُوضح الاستحالة."""

    animation: str  # "shake" | "freeze" | "none"
    duration_ms: int  # مدة الحركة بالمللي ثانية


@dataclass(frozen=True)
class Stage4Message:
    """المرحلة 4: رسالة تربوية واحدة — واضحة ولطيفة."""

    message: str
    tone: str  # "gentle" دائماً


@dataclass(frozen=True)
class DeepDive:
    """الشرح الرياضي العميق — يُعرض فقط عند طلب المستخدم."""

    formula: str  # مثال: "C(n,k) = 0 إذا k > n"
    explanation: str
    why_zero: str  # شرح لماذا النتيجة صفر


@dataclass(frozen=True)
class ImpossibleCaseResult:
    """
    نتيجة تحليل الحالة المستحيلة — contract كامل للـ frontend.

    is_impossible=True → frontend يعرض 4 مراحل فقط
    is_impossible=False → frontend يكمل الحساب الطبيعي
    """

    is_impossible: bool
    case_type: str  # "draw_exceeds_bag" | "none"
    stage_1: Stage1Scene | None
    stage_2: Stage2Question | None
    stage_3: Stage3Animation | None
    stage_4: Stage4Message | None
    deep_dive: DeepDive | None  # null حتى يطلب المستخدم


def analyze_impossible_case(
    bag_count: int,
    requested: int,
    item_name: str = "كرة",
) -> ImpossibleCaseResult:
    """
    يحلل ما إذا كانت عملية السحب مستحيلة.

    المنطق:
      - إذا requested > bag_count → مستحيل (لا يمكن سحب أكثر مما في الكيس)
      - إذا requested <= 0 أو bag_count <= 0 → مستحيل (قيم غير صالحة)
      - غير ذلك → ممكن

    المبدأ: لا حسابات رياضية هنا — فقط تحديد الحالة وبناء الـ contract.
    """
    # ── تحديد نوع الاستحالة ───────────────────────────────────────────────────
    if bag_count <= 0 or requested <= 0:
        return _build_invalid_input_case(bag_count, requested, item_name)

    if requested > bag_count:
        return _build_draw_exceeds_bag(bag_count, requested, item_name)

    # ── الحالة الممكنة ────────────────────────────────────────────────────────
    return ImpossibleCaseResult(
        is_impossible=False,
        case_type="none",
        stage_1=None,
        stage_2=None,
        stage_3=None,
        stage_4=None,
        deep_dive=None,
    )


def _build_draw_exceeds_bag(
    bag_count: int,
    requested: int,
    item_name: str,
) -> ImpossibleCaseResult:
    """يبني contract الحالة المستحيلة: السحب أكبر من الكيس."""
    plural_item = _pluralize_arabic(item_name, bag_count)
    plural_req = _pluralize_arabic(item_name, requested)

    return ImpossibleCaseResult(
        is_impossible=True,
        case_type="draw_exceeds_bag",
        stage_1=Stage1Scene(
            bag_count=bag_count,
            requested=requested,
            bag_label=f"كيس يحتوي على {bag_count} {plural_item}",
            request_label=f"تريد سحب {requested} {plural_req}",
        ),
        stage_2=Stage2Question(
            question=f"هل يمكن أخذ {requested} من {bag_count}؟",
        ),
        stage_3=Stage3Animation(
            animation="shake",
            duration_ms=600,
        ),
        stage_4=Stage4Message(
            message=(
                f"لا يمكن سحب {requested} {plural_req} من كيس يحتوي على "
                f"{bag_count} {plural_item} فقط. هذه العملية مستحيلة."
            ),
            tone="gentle",
        ),
        deep_dive=DeepDive(
            formula=f"C({bag_count}, {requested}) = 0  لأن  {requested} > {bag_count}",
            explanation=(
                "في الرياضيات، C(n, k) تُحسب عدد طرق اختيار k عنصر من n عنصر. "
                "عندما يكون k > n، لا توجد أي طريقة ممكنة، لذا النتيجة = 0."
            ),
            why_zero=(
                f"C({bag_count}, {requested}) = {bag_count}! / ({requested}! × "
                f"({bag_count}-{requested})!) — لكن ({bag_count}-{requested}) = "
                f"{bag_count - requested} < 0، وهذا غير معرَّف في الرياضيات."
            ),
        ),
    )


def _build_invalid_input_case(
    bag_count: int,
    requested: int,
    item_name: str,
) -> ImpossibleCaseResult:
    """يبني contract حالة المدخلات غير الصالحة."""
    return ImpossibleCaseResult(
        is_impossible=True,
        case_type="draw_exceeds_bag",
        stage_1=Stage1Scene(
            bag_count=max(bag_count, 0),
            requested=max(requested, 0),
            bag_label=f"كيس يحتوي على {max(bag_count, 0)} {item_name}",
            request_label=f"تريد سحب {max(requested, 0)} {item_name}",
        ),
        stage_2=Stage2Question(
            question="هل يمكن السحب من كيس فارغ أو بعدد صفر؟",
        ),
        stage_3=Stage3Animation(
            animation="freeze",
            duration_ms=400,
        ),
        stage_4=Stage4Message(
            message="القيم المُدخَلة غير صالحة. يجب أن يكون عدد العناصر والمطلوب أكبر من صفر.",
            tone="gentle",
        ),
        deep_dive=None,
    )


def _pluralize_arabic(word: str, count: int) -> str:
    """
    تصريف بسيط للجمع العربي للكلمات الشائعة في مسائل الاحتمالات.
    يعود إلى الكلمة الأصلية إذا لم تُعرَّف.
    """
    _plurals: dict[str, tuple[str, str]] = {
        "كرة": ("كرة", "كرات"),
        "قلم": ("قلم", "أقلام"),
        "ورقة": ("ورقة", "أوراق"),
        "بطاقة": ("بطاقة", "بطاقات"),
        "قطعة": ("قطعة", "قطع"),
        "عنصر": ("عنصر", "عناصر"),
    }
    if word in _plurals:
        singular, plural = _plurals[word]
        return singular if count == 1 else plural
    return word
