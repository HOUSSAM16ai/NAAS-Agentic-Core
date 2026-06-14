"""AdaptivePedagogySkill — طبقة البيداغوجيا التكيفية (D-104).

«المعيار الأعلى ليس الانبهار اللحظي، بل الاستقلال المعرفي» — فلسفة E-TAALEEM.

هذا الـ Skill يُغلق حلقة BKT: حتى الآن كانت العين الاحتمالية (D-074) تكتب
الإتقان ولا أحد يقرأه — الطالب المتمكن (mastery 0.9) والضائع (0.1) يتلقيان
نفس أسلوب الشرح حرفياً. الآن: قراءة الإتقان تُحدِّد عمق التدريس حتمياً:

- **socratic** (إتقان ≥ 0.7): قُد بأسئلة — لا تكشف الحل مباشرة.
- **guided** (0.35 ≤ إتقان < 0.7): تلميح موجّه ثم خطوات بفجوات يكملها الطالب.
- **scaffolded** (إتقان < 0.35 أو مجهول): شرح كامل بسقالات، ثبّت الأساس أولاً.
- حِمل معرفي مرتفع ⇒ تخفيض درجة («دع العقل يعمل، لكن لا تحرقه بالحمل الزائد»).

+ وكيل التقاط المفاهيم الخاطئة قبل أن تتجذر: markers حتمية لكل مفهوم
(تكامل الجداء = جداء التكاملين، ضرب الاحتمالات بلا استقلال...) — التصحيح
«على مستوى الفكر، لا على مستوى الحكم».

حتمي بالكامل: لا LLM، لا I/O — نفس المدخلات ⇒ نفس التوجيه (قابل لـ pytest).
"""

from __future__ import annotations

import logging
import time

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.doctrine import (
    ADAPTIVE_PEDAGOGY_DOCTRINE_VERSION,
)

logger = logging.getLogger("cogniforge.skills.adaptive_pedagogy")

# ── عتبات السياسة الحتمية (لا تُعدَّل بدون ترقية doctrine) ────────────────────
SOCRATIC_THRESHOLD: float = 0.7
GUIDED_THRESHOLD: float = 0.35
DIRECTIVE_MAX_CHARS: int = 400

GuidanceLevel = str  # "socratic" | "guided" | "scaffolded"

# ── سُلّم الدعم الخماسي (D-113 — worked-example fading, Renkl & Atkinson) ──────
# درجة 1 = أثقل دعم (مثال محلول كامل) ... درجة 5 = بلا دعم (unaided — العتبة
# الذهبية للإتقان الحقيقي). البحث «وَهْم الإتقان»: السقالة التي لا تتلاشى تصير
# قفصاً — يجب أن يتلاشى الدعم مع نموّ الإتقان حتى يولّد الطالب الحلّ وحده.
_SUPPORT_LADDER_LABELS: dict[int, str] = {
    1: "worked_example",
    2: "completion",
    3: "backward_fading",
    4: "prompted",
    5: "unaided",
}
_SUPPORT_LADDER_CLAUSES: dict[int, str] = {
    1: " مستوى الدعم: مثال محلول كامل، واطلب «لماذا؟» قبل كل خطوة.",
    2: " مستوى الدعم: اعرض الحل بفجوات يملؤها الطالب.",
    3: " مستوى الدعم: احذف الخطوات الأخيرة ليُكملها الطالب بنفسه.",
    4: " مستوى الدعم: لا تعرض خطوات؛ تلميح أدنى عند التعثّر فقط.",
    5: " مستوى الدعم: بلا مساعدة — اطلب حلّاً كاملاً غير مدعوم.",
}

# ── كتالوج المفاهيم الخاطئة الشائعة (BAC الجزائر) ─────────────────────────────
# marker في سؤال الطالب ⇒ المفهوم الخاطئ ربما يتجذر — وجّه التصحيح للفكرة.
_MISCONCEPTION_CATALOG: dict[str, tuple[tuple[str, str], ...]] = {
    "probability": (
        (
            "جداء الاحتمالين",
            "ضرب الاحتمالات يصح فقط عند الاستقلال — تحقق من استقلال الحادثتين أولاً",
        ),
        (
            "مجموع الاحتمالين",
            "جمع الاحتمالات يصح فقط عند التنافي — تحقق من عدم التقاطع أولاً",
        ),
    ),
    "conditional_probability": (
        (
            "p(a) ضرب p(b)",
            "الاحتمال الشرطي ليس جداء الاحتمالين — القاعدة قسمة احتمال التقاطع على احتمال الشرط",
        ),
    ),
    "integration": (
        (
            "تكامل الجداء",
            "تكامل الجداء ليس جداء التكاملين — استخدم التكامل بالتجزئة أو تعويضاً مناسباً",
        ),
        (
            "جداء التكاملين",
            "تكامل الجداء ليس جداء التكاملين — استخدم التكامل بالتجزئة أو تعويضاً مناسباً",
        ),
    ),
    "derivatives": (
        (
            "مشتق الجداء",
            "مشتق الجداء ليس جداء المشتقين — القاعدة: مشتق الأول في الثاني زائد الأول في مشتق الثاني",
        ),
    ),
    "limits": (
        (
            "مالانهاية على مالانهاية",
            "نهاية شكل غير محدد لا تساوي 1 تلقائياً — حلل البسط والمقام أو استخدم قاعدة مناسبة",
        ),
    ),
    "exponential": (
        (
            "اس سالب",
            "الدالة الأسية موجبة تماماً دائماً حتى مع أس سالب — لا توجد قيم سالبة لها",
        ),
    ),
}

# نصوص التوجيه لكل مستوى — عربي بسيط، بلا LaTeX وبلا رموز box-drawing (D-067).
_DIRECTIVE_TEXTS: dict[GuidanceLevel, str] = {
    "socratic": (
        "الطالب متمكن من هذا المفهوم. قُده بأسئلة سقراطية قصيرة، "
        "اطلب محاولته أولاً قبل أي خطوة، ولا تكشف الحل مباشرة — "
        "أعطه فرصة الاستقلال."
    ),
    "guided": (
        "الطالب في منتصف الطريق لهذا المفهوم. ابدأ بتلميح موجّه، "
        "ثم خطوات فيها فجوات صغيرة يكملها بنفسه، وأكّد كل خطوة قبل التالية."
    ),
    "scaffolded": (
        "الطالب ما زال يبني هذا المفهوم. اشرح شرحاً كاملاً متدرجاً بسقالات: "
        "ثبّت الفكرة الأساسية والمعنى أولاً، ثم خطوات صغيرة مفصّلة بلغة بسيطة."
    ),
}

_HIGH_LOAD_SUFFIX = " السؤال ثقيل معرفياً: قسّم الحمل إلى أجزاء صغيرة جداً."


class PedagogyInput(RobustBaseModel):
    """مدخل التوجيه التربوي — صورة المتعلم اللحظية لمفهوم السؤال."""

    question: str = Field(..., min_length=1, max_length=8000)
    concept_id: str = Field(default="general", max_length=120)
    mastery: float | None = Field(default=None, ge=0.0, le=1.0)
    interaction_count: int = Field(default=0, ge=0)
    cognitive_load: str = Field(default="medium")


class PedagogyDirective(RobustBaseModel):
    """مخرج التوجيه — يُسبق في prompt الـ LLM ليُكيِّف عمق التدريس."""

    guidance_level: GuidanceLevel
    directive_text: str = Field(..., max_length=DIRECTIVE_MAX_CHARS)
    misconception_alerts: tuple[str, ...] = ()
    mastery_used: float | None = None
    # D-113: درجة سُلّم الدعم 1..5 (1=مثال محلول كامل ← 5=بلا دعم/unaided).
    support_level: int = Field(default=1, ge=1, le=5)
    ladder_label: str = "worked_example"
    doctrine_version: str = ADAPTIVE_PEDAGOGY_DOCTRINE_VERSION


def _detect_misconceptions(question: str, concept_id: str) -> tuple[str, ...]:
    """يلتقط markers المفاهيم الخاطئة في سؤال الطالب — حتمي، لكل مفهوم كتالوجه."""
    normalized = question.strip().lower()
    alerts: list[str] = []
    for marker, correction in _MISCONCEPTION_CATALOG.get(concept_id, ()):
        if marker in normalized:
            alerts.append(correction)
    return tuple(alerts)


def _classify_guidance(mastery: float | None, cognitive_load: str) -> GuidanceLevel:
    """سياسة العتبات الحتمية + تخفيض درجة عند الحِمل المرتفع."""
    if mastery is None or mastery < GUIDED_THRESHOLD:
        level: GuidanceLevel = "scaffolded"
    elif mastery < SOCRATIC_THRESHOLD:
        level = "guided"
    else:
        level = "socratic"

    if cognitive_load == "high":
        # «لا تحرقه بالحمل الزائد» — درجة أعمق من السقالات
        if level == "socratic":
            level = "guided"
        elif level == "guided":
            level = "scaffolded"
    return level


def _classify_support_level(mastery: float | None, cognitive_load: str) -> int:
    """D-113: درجة سُلّم الدعم الخماسي (1..5) — أدق من guidance_level الثلاثي.

    1=worked_example (إتقان منخفض/مجهول) ... 5=unaided (إتقان عالٍ). الحِمل
    المرتفع يزيد الدعم (يُنقص الدرجة بمقدار 1، بحدّ أدنى 1). حتمي.
    """
    if mastery is None or mastery < 0.2:
        level = 1
    elif mastery < 0.4:
        level = 2
    elif mastery < 0.6:
        level = 3
    elif mastery < 0.8:
        level = 4
    else:
        level = 5
    if cognitive_load == "high":
        level = max(1, level - 1)  # حِمل مرتفع ⇒ دعم أكثر
    return level


class AdaptivePedagogySkill:
    """Skill رسمي (§0.5): مسؤولية واحدة — تحويل صورة المتعلم إلى توجيه تدريسي."""

    name = "adaptive_pedagogy"
    doctrine_version = ADAPTIVE_PEDAGOGY_DOCTRINE_VERSION

    def derive(self, payload: PedagogyInput) -> PedagogyDirective:
        """يشتق التوجيه التربوي حتمياً — لا يرفع أبداً نحو المسار الحي."""
        t0 = time.perf_counter()
        level = _classify_guidance(payload.mastery, payload.cognitive_load)
        support_level = _classify_support_level(payload.mastery, payload.cognitive_load)
        text = _DIRECTIVE_TEXTS[level]
        if payload.cognitive_load == "high":
            text = (text + _HIGH_LOAD_SUFFIX)[:DIRECTIVE_MAX_CHARS]

        alerts = _detect_misconceptions(payload.question, payload.concept_id)
        if alerts:
            correction = " انتبه: " + alerts[0] + " — صحّح الفكرة بلطف دون لوم."
            text = (text + correction)[:DIRECTIVE_MAX_CHARS]

        # D-113: clause سُلّم الدعم يُلحق أخيراً (يُقتطع أولاً عند التجاوز فيبقى
        # «انتبه» المفهومي محفوظاً قبله).
        text = (text + _SUPPORT_LADDER_CLAUSES[support_level])[:DIRECTIVE_MAX_CHARS]

        directive = PedagogyDirective(
            guidance_level=level,
            directive_text=text,
            misconception_alerts=alerts,
            mastery_used=payload.mastery,
            support_level=support_level,
            ladder_label=_SUPPORT_LADDER_LABELS[support_level],
        )
        self._record_metrics(level, time.perf_counter() - t0)
        return directive

    @staticmethod
    def _record_metrics(level: GuidanceLevel, duration_s: float) -> None:
        try:
            _PEDAGOGY_INVOCATIONS.labels(guidance_level=level).inc()
            _PEDAGOGY_DURATION.observe(duration_s)
        except Exception:
            pass


# ── Prometheus (registry مستقل — قاعدة §6 «لا CollectorRegistry مشترك») ───────
try:
    from prometheus_client import CollectorRegistry, Counter, Histogram

    _PEDAGOGY_REGISTRY = CollectorRegistry()
    _PEDAGOGY_INVOCATIONS = Counter(
        "cogniforge_skill_pedagogy_invocations_total",
        "إجمالي اشتقاقات التوجيه التربوي التكيفي (D-104)",
        ["guidance_level"],
        registry=_PEDAGOGY_REGISTRY,
    )
    _PEDAGOGY_DURATION = Histogram(
        "cogniforge_skill_pedagogy_duration_seconds",
        "زمن اشتقاق التوجيه التربوي",
        registry=_PEDAGOGY_REGISTRY,
    )
except Exception:  # pragma: no cover — بيئات بلا prometheus_client

    class _Noop:
        def labels(self, **_: object) -> _Noop:
            return self

        def inc(self, *_: object) -> None:
            return None

        def observe(self, *_: object) -> None:
            return None

    _PEDAGOGY_INVOCATIONS = _Noop()  # type: ignore[assignment]
    _PEDAGOGY_DURATION = _Noop()  # type: ignore[assignment]


_skill_singleton: AdaptivePedagogySkill | None = None


def get_adaptive_pedagogy_skill() -> AdaptivePedagogySkill:
    """Singleton — نمط بقية الـ Skills."""
    global _skill_singleton
    if _skill_singleton is None:
        _skill_singleton = AdaptivePedagogySkill()
    return _skill_singleton
