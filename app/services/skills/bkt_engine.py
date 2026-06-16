"""
BKTEngine — Skill رسمي لتتبّع المعرفة البايزي (Bayesian Knowledge Tracing).

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill — وحدة مستقلة قابلة
للقياس والاختبار والاستبدال».

## المسؤولية الواحدة
تحويل تفاعل طالب (سؤال نصّي + إتقان سابق) إلى تقييم معرفي منظَّم:
1. تصنيف المفهوم (`concept_id`) — احتمالات شرطية، تكامل، اشتقاق...
2. تقدير الحِمل المعرفي (`cognitive_load_estimate`) — low/medium/high
3. تحديث احتمال الإتقان (`student_mastery_probability`) عبر معادلات BKT

## نموذج BKT
أربع معاملات قياسية:
- `p_L0` (الإتقان المسبق الأولي)
- `p_T`  (معدّل الانتقال/التعلّم بعد التفاعل)
- `p_S`  (الزلّة slip — يعرف لكن يخطئ)
- `p_G`  (التخمين guess — لا يعرف لكن يصيب)

التحديث البايزي (بعد ملاحظة evidence):
- صحيح:  P(L|c)  = P(L)(1-p_S) / [P(L)(1-p_S) + (1-P(L))·p_G]
- خاطئ:  P(L|¬c) = P(L)·p_S    / [P(L)·p_S    + (1-P(L))(1-p_G)]
ثم الانتقال: P(L') = P(L|evidence) + (1 - P(L|evidence))·p_T

في سياق المحادثة لا تتوفّر إشارة «صحيح/خاطئ» صريحة، لذا نشتق إشارة evidence
لينة من نوع التفاعل: سؤال استيضاح/حيرة («ماذا نقصد»، «لا أفهم») → evidence ضعيف
(يُعامَل كخطأ)؛ محاولة تتضمّن استدلالاً/نتيجة → evidence أقوى (يُعامَل كصحيح).
الإشارة موثَّقة وحتمية — لا LLM، لا عشوائية.

## العقد (Pydantic)
- Input:  `BKTEvaluationInput(question, prior_mastery, history)`
- Output: `BKTEvaluation`

## الاستقلالية
- لا يستورد من Skills أخرى ولا من microservices
- حتمي تماماً (قابل للاختبار بـ pytest عادي)

## القياس (Prometheus)
- `cogniforge_skill_bkt_invocations_total{concept_id,cognitive_load}` (counter)
- `cogniforge_skill_bkt_duration_seconds` (histogram)
"""

from __future__ import annotations

import contextlib
import re
import time

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.doctrine import BKT_COGNITIVE_DOCTRINE_VERSION

# ── معاملات BKT الافتراضية ───────────────────────────────────────────────────────
DEFAULT_P_L0: float = 0.25  # الإتقان المسبق الأولي
DEFAULT_P_T: float = 0.12  # معدّل التعلّم بعد التفاعل
DEFAULT_P_S: float = 0.10  # الزلّة
DEFAULT_P_G: float = 0.20  # التخمين

CognitiveLoad = str  # "low" | "medium" | "high"


# ── تصنيف المفاهيم (concept_id) ────────────────────────────────────────────────────
# ترتيب القائمة مهم: الأكثر تحديداً أولاً.
_CONCEPT_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    (
        "conditional_probability",
        ("احتمال شرط", "احتمال مشروط", "شجرة الاحتمال", "شجرة احتمال", "بشرط", "conditional"),
    ),
    ("probability", ("احتمال", "احتمالات", "عشوائي", "حادثة", "probabilit", "variable aléatoire")),
    (
        "integration",
        ("تكامل", "بالتجزئة", "intégrale", "integral", "primitive", "دالة أصلية", "أصلية"),
    ),
    ("derivatives", ("مشتق", "اشتقاق", "dérivée", "derivative", "نهاية المشتق")),
    ("limits", ("نهاية", "نهايات", "limite", "limit", "لوبيتال", "l'hopital", "lhopital")),
    (
        "complex_numbers",
        (
            "عقدي",
            "عقدية",
            "complexe",
            "complex number",
            "عدد مركب",
            # ISS-112: الصيغ المعرَّفة/الجمع — «الأعداد المركبة» ليست سلسلة فرعية
            # من «عدد مركب» (درس ISS-109: أداة التعريف تكسر مطابقة ثنائية الكلمات)
            "أعداد مركبة",
            "اعداد مركبة",
            "الأعداد المركبة",
            "الاعداد المركبة",
            "العدد المركب",
            # ISS-114 (D-106): «الدوال المركبة» صياغة طلابية للأعداد المركبة —
            # تُصنَّف complex_numbers لا numerical_functions (BKT header الخاطئ).
            "دوال مركبة",
            "الدوال المركبة",
            "دالة مركبة",
            "الدالة المركبة",
            "z =",
        ),
    ),
    (
        "numerical_functions",
        ("دالة", "دوال", "fonction", "function", "تغيرات", "مجال التعريف", "اتجاه التغير"),
    ),
    (
        "sequences",
        ("متتالية", "متتاليات", "suite", "sequence", "حسابية", "هندسية", "متتالية حسابية"),
    ),
    ("trigonometry", ("مثلثات", "جيب", "جيب التمام", "trigonom", "sin", "cos", "tan")),
    ("logarithm", ("لوغاريتم", "logarithme", "logarithm", "ln", "log")),
    ("exponential", ("أسية", "exponentielle", "exponential", "e^", "نشر أسي")),
]


def classify_concept(question: str) -> str:
    """يصنّف المفهوم التعليمي من نص السؤال. الافتراضي 'general' لغير الرياضي."""
    if not question:
        return "general"
    normalized = question.strip().lower()
    for concept_id, keywords in _CONCEPT_PATTERNS:
        if any(kw in normalized for kw in keywords):
            return concept_id
    return "general"


def classify_concept_with_context(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    """تصنيف واعٍ بالسياق — يحل عمى المتابعات (ISS-112).

    «اشرح السؤال رقم 2 من هذا التمرين» لا يحمل كلمة المفهوم ⇒ كان يسقط لـ
    'general' فتُقرأ/تُكتب صفوف إتقان على المفهوم الخاطئ («تتبّع المعرفة:
    general» في الفضيحة الحية). عند فشل تصنيف السؤال وحده، نُصنِّف آخر رسائل
    الحوار (user/assistant فقط — درس D-102: رسائل system ليست دليلاً).
    """
    concept = classify_concept(question)
    if concept != "general" or not history:
        return concept
    # D-115 (قفل المفهوم — ضد تسمّم السياق): السؤال بلا مفهوم (متابعة/حيرة مثل
    # «لم أفهم»). الكارثة الحية: المسح كان يشمل رسائل المساعد، فإذا هلوس المساعد
    # «متتالية»/«معادلة» تسمّم التصنيف ودخل حلقة مفهوم خاطئ. الإصلاح: ثبّت المفهوم
    # من رسائل الطالب (user) حصراً — هي مصدر الحقيقة عن التمرين، مناعة ضد الهلوسة.
    # أحدث مفهوم ذكره الطالب صراحةً يفوز (يحترم تبديل الموضوع الذي يقرره الطالب).
    for msg in reversed(history[-12:]):
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        c = classify_concept(str(msg.get("content", "")))
        if c != "general":
            return c
    # احتياط أخير: لو لم يذكر الطالب أي مفهوم صريح، جرّب آخر رسالة مساعد.
    for msg in reversed(history[-6:]):
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        c = classify_concept(str(msg.get("content", "")))
        if c != "general":
            return c
    return concept


# ── تقدير الحِمل المعرفي ───────────────────────────────────────────────────────────
_ADVANCED_TERMS: tuple[str, ...] = (
    "لوبيتال",
    "داربو",
    "بالتجزئة",
    "معادلة تفاضلية",
    "مبرهنة",
    "نظرية",
    "intégration par parties",
    "théorème",
)
_DETAIL_TERMS: tuple[str, ...] = ("تفصيل", "مفصل", "بالتفصيل", "خطوة بخطوة", "détaill", "detailed")
_SUBPART_RE = re.compile(
    r"(?:^|\s)(?:[أابجدهـ١٢٣٤٥]|[1-5])\s*[)\-.]|الجزء\s+[أابجدهـ]|partie\s+[ivx]"
)


def estimate_cognitive_load(question: str) -> CognitiveLoad:
    """يقدّر الحِمل المعرفي (low/medium/high) من تعقيد السؤال — حتمي."""
    if not question:
        return "low"
    normalized = question.strip().lower()
    score = 0

    length = len(normalized)
    if length > 400:
        score += 2
    elif length > 160:
        score += 1

    subparts = len(_SUBPART_RE.findall(normalized))
    if subparts >= 2:
        score += 2
    elif subparts == 1:
        score += 1

    if any(term in normalized for term in _ADVANCED_TERMS):
        score += 2
    if any(term in normalized for term in _DETAIL_TERMS):
        score += 1

    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


# ── إشارة evidence اللينة من نوع التفاعل ────────────────────────────────────────────
_CONFUSION_PATTERNS: tuple[str, ...] = (
    "ماذا نقصد",
    "ما المقصود",
    "ما معنى",
    "لا أفهم",
    "لم أفهم",
    "مش فاهم",
    "ما فهمت",
    "اشرح",
    "وضح",
    "ما هو",
    "ما هي",
    "كيف",
    "لماذا",
    "je ne comprends",
    "c'est quoi",
    "explique",
)
_MASTERY_PATTERNS: tuple[str, ...] = (
    "أعتقد أن",
    "حليت",
    "حللت",
    "الحل هو",
    "النتيجة هي",
    "أظن أن",
    "وجدت أن",
    "إذن",
    "j'ai trouvé",
    "donc",
    "la réponse est",
)


def infer_correctness_signal(question: str) -> bool:
    """يشتق إشارة evidence لينة: True (إتقان ظاهر) أو False (حيرة/استيضاح).

    الافتراضي False — السؤال المجرّد بلا إشارة إتقان يُعامَل كطلب مساعدة
    (evidence ضعيف) لأن غالبية تفاعلات الطلاب استفسارية.
    """
    if not question:
        return False
    normalized = question.strip().lower()
    if any(p in normalized for p in _MASTERY_PATTERNS):
        return True
    if any(p in normalized for p in _CONFUSION_PATTERNS):
        return False
    return False


def update_mastery(
    prior: float,
    correct: bool,
    *,
    p_s: float = DEFAULT_P_S,
    p_g: float = DEFAULT_P_G,
    p_t: float = DEFAULT_P_T,
) -> float:
    """تحديث BKT بايزي: يُرجع P(L') بعد ملاحظة evidence. مُقيَّد إلى [0, 1]."""
    prior = min(max(prior, 0.0), 1.0)
    if correct:
        numerator = prior * (1.0 - p_s)
        denominator = numerator + (1.0 - prior) * p_g
    else:
        numerator = prior * p_s
        denominator = numerator + (1.0 - prior) * (1.0 - p_g)
    posterior = numerator / denominator if denominator > 0 else prior
    transitioned = posterior + (1.0 - posterior) * p_t
    return round(min(max(transitioned, 0.0), 1.0), 4)


# ── Prometheus metrics ─────────────────────────────────────────────────────────────
try:
    from prometheus_client import REGISTRY, Counter, Histogram

    if "cogniforge_skill_bkt_invocations_total" in {m.name for m in REGISTRY.collect()}:
        _bkt_invocations = None  # already registered in this process
        _bkt_duration = None
    else:
        _bkt_invocations = Counter(
            "cogniforge_skill_bkt_invocations_total",
            "Total invocations of BKTEngine, labelled by concept_id and cognitive_load.",
            ["concept_id", "cognitive_load"],
        )
        _bkt_duration = Histogram(
            "cogniforge_skill_bkt_duration_seconds",
            "Duration of BKTEngine evaluations in seconds.",
        )

    def _record_invocation(concept_id: str, cognitive_load: str, duration: float) -> None:
        with contextlib.suppress(Exception):
            if _bkt_invocations is not None:
                _bkt_invocations.labels(concept_id=concept_id, cognitive_load=cognitive_load).inc()
            if _bkt_duration is not None:
                _bkt_duration.observe(duration)

except Exception:  # pragma: no cover

    def _record_invocation(concept_id: str, cognitive_load: str, duration: float) -> None:
        pass


# ── Pydantic contracts ──────────────────────────────────────────────────────────────
class BKTEvaluationInput(RobustBaseModel):
    """مدخلات تقييم BKT — typed contract موحَّد."""

    question: str = Field(..., min_length=1, max_length=8000)
    prior_mastery: float | None = Field(default=None, ge=0.0, le=1.0)
    history: list[dict[str, str]] | None = None


class BKTEvaluation(RobustBaseModel):
    """مخرج التقييم — الكائن الذي يُبثّ كـ bkt_tracking ويُخزَّن في DB."""

    concept_id: str
    cognitive_load_estimate: CognitiveLoad
    student_mastery_probability: float = Field(..., ge=0.0, le=1.0)
    prior_mastery: float = Field(..., ge=0.0, le=1.0)
    evidence_correct: bool


# ── Skill ─────────────────────────────────────────────────────────────────────────
class BKTEngine:
    """
    Skill حتمي لتتبّع المعرفة البايزي.

    عقد دائم (لا يُكسر بدون ADR):
    1. صفر تبعيات على Skills أخرى أو microservices — استقلالية إلزامية
    2. حتمي تماماً — نفس المدخلات → نفس المخرجات (قابل للاختبار)
    3. كل تقييم يُسجَّل في Prometheus
    4. student_mastery_probability دائماً في [0, 1]
    5. typed contract — لا تمرير dicts خام
    """

    _skill_name: str = "bkt"
    #: إصدار الـ doctrine الذي يلتزم به هذا الـ Skill (D-074). يُربط بـ
    #: doctrine.BKT_COGNITIVE_DOCTRINE_VERSION — single source of truth.
    doctrine_version: str = BKT_COGNITIVE_DOCTRINE_VERSION

    def evaluate(self, payload: BKTEvaluationInput) -> BKTEvaluation:
        """يُقيّم تفاعلاً ويُرجع تقييماً منظَّماً. لا يرفع استثناءات منطقية."""
        t0 = time.perf_counter()
        # ISS-112: تصنيف واعٍ بالسياق — المتابعات («اشرح السؤال 2») تلتصق بمفهوم الحوار
        concept_id = classify_concept_with_context(payload.question, payload.history)
        cognitive_load = estimate_cognitive_load(payload.question)
        correct = infer_correctness_signal(payload.question)
        prior = payload.prior_mastery if payload.prior_mastery is not None else DEFAULT_P_L0
        new_mastery = update_mastery(prior, correct)

        _record_invocation(concept_id, cognitive_load, time.perf_counter() - t0)

        return BKTEvaluation(
            concept_id=concept_id,
            cognitive_load_estimate=cognitive_load,
            student_mastery_probability=new_mastery,
            prior_mastery=round(min(max(prior, 0.0), 1.0), 4),
            evidence_correct=correct,
        )


_bkt_engine_singleton: BKTEngine | None = None


def get_bkt_engine() -> BKTEngine:
    """يُرجع نسخة مفردة من BKTEngine (lazy singleton)."""
    global _bkt_engine_singleton
    if _bkt_engine_singleton is None:
        _bkt_engine_singleton = BKTEngine()
    return _bkt_engine_singleton


__all__ = [
    "BKTEngine",
    "BKTEvaluation",
    "BKTEvaluationInput",
    "classify_concept",
    "classify_concept_with_context",
    "estimate_cognitive_load",
    "get_bkt_engine",
    "infer_correctness_signal",
    "update_mastery",
]
