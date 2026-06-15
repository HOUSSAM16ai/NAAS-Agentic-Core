"""WorkedExampleSkill — المثال المحلول المُتدرّج المُقيَّد بالإتقان (D-114).

«المبتدئ يحتاج مثالاً محلولاً كاملاً أولاً» — Sweller worked-example effect.

ISS-116 (الإفلاس البيداغوجي): طالب بإتقان 14% (مبتدئ مطلق) حار وسأل «لو جاء
يوم الامتحان لا أستطيع حله؟» فردّ النظام بحلقة أسئلة سقراطية لا نهائية بلا أي
مثال محلول — فغرق ورسب. D-113 («لا تكشف أبداً») طُبِّق بإفراط فحرم المبتدئ من
المخطط الذهني الذي يحتاجه.

هذا الـ Skill يحلّ التناقض: عند المبتدئ المطلق (support_level==1) أو الحيرة
المتكرّرة، يُولِّد:
  1. **خريطة منهجية حتمية** (subgoal labels) — المهارة المُتحوِّلة («كيف أحلّ
     أي تمرين مهما تغيّر يوم الامتحان» — سؤال الطالب الحرفي). تُعرَض كبطاقة
     بصرية تُفرز الدوبامين.
  2. **توجيه الـ LLM** لتوليد مثال محلول كامل على مسألة *مماثلة* (isomorphic —
     أرقام/سياق مختلف، لا تمرين الطالب المُقيَّم)، ملفوف بالفواصل الحارسة
     فيُعفى من الحجب — راجع `redact_final_answers`.

التوفيق مع أطروحة المنصّة (illusion_gap = assisted − unaided_delayed): المثال
على مسألة مماثلة يبني المخطط دون وهم طلاقة؛ تمرين الطالب يبقى محجوباً ويُقاس
وحده. حتمي بالكامل: لا LLM، لا I/O — نفس المدخلات ⇒ نفس المخرجات (قابل لـ pytest).
"""

from __future__ import annotations

import logging
import time

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.doctrine import (
    WORKED_EXAMPLE_CLOSE,
    WORKED_EXAMPLE_DOCTRINE_VERSION,
    WORKED_EXAMPLE_OPEN,
)

logger = logging.getLogger("cogniforge.skills.worked_example")

# ── بوّابة الكشف (D-114) ──────────────────────────────────────────────────────
# المثال المحلول الكامل يُكشف فقط للمبتدئ المطلق (support_level==1) أو عند حيرة
# متكرّرة (2+ «لم أفهم»). غير ذلك يبقى السُلّم السقراطي المتدرّج.
_REVEAL_SUPPORT_LEVEL: int = 1
_REVEAL_CONFUSION_THRESHOLD: int = 2

# ── لوحة ألوان شارات الأهداف الفرعية (subgoal label badges) ───────────────────
_SUBGOAL_COLORS: tuple[str, ...] = (
    "#6366f1",  # indigo
    "#0ea5e9",  # sky
    "#10b981",  # emerald
    "#f59e0b",  # amber
    "#ec4899",  # pink
    "#8b5cf6",  # violet
)


# ── كتالوج المنهجيات المُتحوِّلة (transfer-aware methodologies) ─────────────────
# لكل مفهوم: الخطوات الثابتة (invariant) التي تعمل لأي تباين من المسألة. هذه هي
# «المهارة المُتحوِّلة» — يحفظها الطالب فيحلّ أي صياغة يوم الامتحان. كل خطوة:
# (subgoal_label, self_explanation_prompt). حتمية، عربية بسيطة، بلا LaTeX.
_DEFAULT_METHODOLOGY: tuple[tuple[str, str], ...] = (
    ("افهم المعطى", "لماذا نبدأ دائماً بقراءة كل معطى قبل أي حساب؟"),
    ("حدّد المطلوب", "ما الذي يطلبه السؤال بالضبط — قيمة، إثبات، أم دراسة؟"),
    ("اختر الأداة", "أي قاعدة أو طريقة تناسب هذا النوع من المطلوب، ولماذا؟"),
    ("طبّق خطوة بخطوة", "لماذا ترتيب الخطوات بهذا الشكل وليس عشوائياً؟"),
    ("تحقّق من النتيجة", "كيف تتأكد أن جوابك منطقي قبل أن تكتبه؟"),
)

_METHODOLOGY_CATALOG: dict[str, tuple[tuple[str, str], ...]] = {
    "probability": (
        ("حدّد المعطى", "لماذا نكتب عدد كل عنصر (لون/فئة) قبل أي شيء آخر؟"),
        ("ابنِ فضاء العينة", "لماذا نحسب كل النتائج الممكنة أولاً — ما دورها في النسبة؟"),
        ("عرّف الحدث", "كيف نصوغ المطلوب رياضياً كمجموعة من النتائج؟"),
        ("عُدّ النتائج الملائمة", "لماذا نعدّ فقط النتائج التي تحقق الشرط؟"),
        ("احسب النسبة", "لماذا الاحتمال = الملائمة ÷ الكلية، وليس العكس؟"),
        ("تحقّق", "كيف نتأكد أن الاحتمال بين 0 و1 ومنطقي؟"),
    ),
    "conditional_probability": (
        ("حدّد الحادثتين", "لماذا نميّز الحادث الشرط عن الحادث المطلوب؟"),
        ("احسب احتمال الشرط", "لماذا يصبح الشرط هو فضاء العينة الجديد؟"),
        ("احسب احتمال التقاطع", "ما معنى أن يقع الحدثان معاً؟"),
        ("طبّق قاعدة القسمة", "لماذا نقسم على احتمال الشرط لا نضرب؟"),
        ("تحقّق", "هل النتيجة منطقية مقارنة بالاحتمال غير الشرطي؟"),
    ),
    "integration": (
        ("اكتب التكامل بوضوح", "لماذا نحدّد الحدود والدالة قبل اختيار الطريقة؟"),
        ("اختر الطريقة", "كيف نقرر: تعويض، تجزئة، أم تكامل مباشر؟"),
        ("نفّذ الطريقة", "لماذا نتبع خطوات الطريقة بهذا الترتيب؟"),
        ("أعِد للمتغير الأصلي", "لماذا لا ننسى إرجاع التعويض في النهاية؟"),
        ("تحقّق بالاشتقاق", "كيف نتأكد أن التكامل صحيح بمشتقّه؟"),
    ),
    "derivatives": (
        ("حدّد بنية الدالة", "هل هي جداء، قسمة، أم مركّبة — ولماذا يهمّ ذلك؟"),
        ("اختر قاعدة الاشتقاق", "أي قاعدة تناسب البنية، ولماذا؟"),
        ("طبّق القاعدة بدقة", "لماذا ترتيب الحدود في القاعدة مهمّ؟"),
        ("بسّط النتيجة", "لماذا نبسّط قبل دراسة الإشارة؟"),
        ("فسّر المشتق", "ماذا تخبرنا إشارة المشتق عن اتجاه التغير؟"),
    ),
    "limits": (
        ("عوّض مباشرة أولاً", "لماذا نجرّب التعويض المباشر قبل أي شيء؟"),
        ("اكشف الشكل غير المحدد", "لماذا 0/0 أو ∞/∞ لا يعني أن النهاية غير موجودة؟"),
        ("اختر أداة الرفع", "متى نستخدم العامل المشترك، التعويض، أم لوبيتال؟"),
        ("احسب النهاية", "لماذا تتبع خطوات الأداة المختارة؟"),
        ("فسّر النتيجة", "ماذا تعني النهاية هندسياً (مقارب مثلاً)؟"),
    ),
    "complex_numbers": (
        ("حدّد الشكل المناسب", "متى نستخدم الشكل الجبري ومتى المثلثي؟"),
        ("اكتب المعطى بدقة", "لماذا نحدّد الجزء الحقيقي والتخيلي بوضوح؟"),
        ("طبّق العملية", "لماذا الضرب يجمع الزوايا والجمع يفصل الأجزاء؟"),
        ("بسّط وحوّل عند الحاجة", "لماذا نختار الشكل الأسهل للعملية المطلوبة؟"),
        ("فسّر هندسياً", "ماذا يمثّل العدد المركّب في المستوى؟"),
    ),
    "numerical_functions": (
        ("حدّد مجال التعريف", "لماذا نبدأ بالمجال قبل أي دراسة؟"),
        ("احسب النهايات", "لماذا النهايات تكشف سلوك الدالة عند الأطراف؟"),
        ("ادرس المشتق", "لماذا إشارة المشتق تعطي اتجاه التغير؟"),
        ("ابنِ جدول التغيرات", "كيف يلخّص الجدول كل ما عرفناه؟"),
        ("تحقّق بالرسم", "هل يطابق المنحنى ما استنتجناه؟"),
    ),
    "sequences": (
        ("حدّد نوع المتتالية", "كيف نميّز الحسابية عن الهندسية، ولماذا يهمّ؟"),
        ("استخرج العنصر والأساس", "لماذا نحتاج الحد الأول والأساس معاً؟"),
        ("اكتب الحد العام", "لماذا الحد العام يفتح كل الأسئلة اللاحقة؟"),
        ("طبّق على المطلوب", "لماذا نعوّض في الصيغة العامة بدل الحساب يدوياً؟"),
        ("تحقّق بحدّ معروف", "كيف نتأكد بحساب حد نعرفه مسبقاً؟"),
    ),
}


class WorkedExampleStep(RobustBaseModel):
    """خطوة منهجية في خريطة المثال المحلول — هدف فرعي + سؤال شرح ذاتي."""

    title: str
    subgoal_label: str
    subgoal_color: str
    self_explanation_prompt: str


class WorkedExampleInput(RobustBaseModel):
    """مدخل المثال المحلول — صورة المتعلم + تمرينه (للسياق لا للكشف المباشر)."""

    exercise_text: str = Field(default="", max_length=8000)
    concept_id: str = Field(default="general", max_length=120)
    mastery: float | None = Field(default=None, ge=0.0, le=1.0)
    support_level: int = Field(default=5, ge=1, le=5)
    confusion_count: int = Field(default=0, ge=0)


class WorkedExampleOutput(RobustBaseModel):
    """مخرج المثال المحلول — قرار الكشف + خريطة منهجية + توجيه الـ LLM."""

    should_reveal: bool
    card_title: str = ""
    steps: tuple[WorkedExampleStep, ...] = ()
    bridge_text: str = ""
    prompt_directive: str = ""
    doctrine_version: str = WORKED_EXAMPLE_DOCTRINE_VERSION


def _build_steps(concept_id: str) -> tuple[WorkedExampleStep, ...]:
    """يبني خطوات المنهجية المُتحوِّلة لمفهوم — حتمي، ألوان دوّارة."""
    methodology = _METHODOLOGY_CATALOG.get(concept_id, _DEFAULT_METHODOLOGY)
    steps: list[WorkedExampleStep] = []
    for idx, (label, prompt) in enumerate(methodology):
        steps.append(
            WorkedExampleStep(
                title=f"الخطوة {idx + 1}",
                subgoal_label=label,
                subgoal_color=_SUBGOAL_COLORS[idx % len(_SUBGOAL_COLORS)],
                self_explanation_prompt=prompt,
            )
        )
    return tuple(steps)


def _build_prompt_directive(concept_id: str, steps: tuple[WorkedExampleStep, ...]) -> str:
    """يبني توجيه الـ LLM لتوليد مثال محلول على مسألة *مماثلة* ملفوف بالفواصل.

    التوجيه يُحقن في سياق الـ orchestrator فيستخدمه SynthesizerNode. الـ LLM
    يُولِّد المثال الملموس بالأرقام (على مسألة مختلفة عن تمرين الطالب)، ملفوفاً
    بالفواصل الحارسة كي يُعفى من الحجب — تمرين الطالب يبقى محجوباً.
    """
    labels = "، ".join(s.subgoal_label for s in steps)
    return (
        f"[مثال محلول للمبتدئ] الطالب مبتدئ مطلق في «{concept_id}» ويحتاج مثالاً "
        "محلولاً كاملاً ليبني المخطط الذهني. وَلِّد مثالاً محلولاً على مسألة "
        "*مماثلة تماماً في المبدأ لكن بأرقام وسياق مختلفين* عن تمرين الطالب — "
        "لا تستخدم أرقام تمرينه أبداً. اتبع هذه المنهجية خطوةً بخطوة: "
        f"{labels}. أظهِر كل خطوة بنتيجتها الكاملة (الأرقام مكشوفة في هذا المثال "
        "المماثل)، واطرح «لماذا؟» قصيراً بعد كل خطوة ليبرّرها الطالب. "
        f"لُفّ المثال المحلول كاملاً بين {WORKED_EXAMPLE_OPEN} و{WORKED_EXAMPLE_CLOSE} "
        "بالضبط. ثم خارج الفواصل اختم بجملة: «الآن طبّق نفس المنهجية على تمرينك» — "
        "ولا تحلّ تمرين الطالب نفسه ولا تكشف أي رقم من أرقامه."
    )


class WorkedExampleSkill:
    """Skill رسمي (§0.5): مسؤولية واحدة — قرار الكشف + بناء خريطة المثال المحلول.

    حتمي بالكامل (بلا LLM/IO). الـ LLM يُستدعى لاحقاً عبر prompt_directive في
    SynthesizerNode — هذا الـ Skill يقرّر *متى* و*كيف* فقط.
    """

    name = "worked_example"
    doctrine_version = WORKED_EXAMPLE_DOCTRINE_VERSION

    def derive(self, payload: WorkedExampleInput) -> WorkedExampleOutput:
        """يقرّر الكشف ويبني الخريطة المنهجية + توجيه الـ LLM — حتمي، fail-safe."""
        t0 = time.perf_counter()
        should_reveal = (
            payload.support_level <= _REVEAL_SUPPORT_LEVEL
            or payload.confusion_count >= _REVEAL_CONFUSION_THRESHOLD
        )
        if not should_reveal:
            self._record_metrics("withheld", time.perf_counter() - t0)
            return WorkedExampleOutput(should_reveal=False)

        steps = _build_steps(payload.concept_id)
        output = WorkedExampleOutput(
            should_reveal=True,
            card_title="مثال محلول كامل على مسألة مماثلة 🎯",
            steps=steps,
            bridge_text="الآن طبّق نفس المنهجية على تمرينك — هذه هي المهارة التي تنجح يوم الامتحان مهما تغيّرت الأرقام.",
            prompt_directive=_build_prompt_directive(payload.concept_id, steps),
        )
        self._record_metrics("revealed", time.perf_counter() - t0)
        return output

    @staticmethod
    def _record_metrics(outcome: str, duration_s: float) -> None:
        try:
            _WE_INVOCATIONS.labels(outcome=outcome).inc()
            _WE_DURATION.observe(duration_s)
        except Exception:
            pass


# ── Prometheus (registry مستقل — قاعدة §6 «لا CollectorRegistry مشترك») ───────
try:
    from prometheus_client import CollectorRegistry, Counter, Histogram

    _WE_REGISTRY = CollectorRegistry()
    _WE_INVOCATIONS = Counter(
        "cogniforge_skill_worked_example_invocations_total",
        "إجمالي اشتقاقات المثال المحلول المُتدرّج (D-114)",
        ["outcome"],
        registry=_WE_REGISTRY,
    )
    _WE_DURATION = Histogram(
        "cogniforge_skill_worked_example_duration_seconds",
        "زمن اشتقاق المثال المحلول",
        registry=_WE_REGISTRY,
    )
except Exception:  # pragma: no cover — بيئات بلا prometheus_client

    class _Noop:
        def labels(self, **_: object) -> _Noop:
            return self

        def inc(self, *_: object) -> None:
            return None

        def observe(self, *_: object) -> None:
            return None

    _WE_INVOCATIONS = _Noop()  # type: ignore[assignment]
    _WE_DURATION = _Noop()  # type: ignore[assignment]


_skill_singleton: WorkedExampleSkill | None = None


def get_worked_example_skill() -> WorkedExampleSkill:
    """Singleton — نمط بقية الـ Skills."""
    global _skill_singleton
    if _skill_singleton is None:
        _skill_singleton = WorkedExampleSkill()
    return _skill_singleton
