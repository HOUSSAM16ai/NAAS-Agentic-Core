"""عقود Pydantic لمحرّك الاحتمالات الحتمي (D-170 Stage C — مُستخرَجة حرفياً).

كانت تعيش داخل `probability_skill.py` (1,685 سطراً). فصلُها يفصل **العقد** عن
**المحرّك** (SRP): الواجهة (GenerativeUIRenderer) والاختبارات تعتمد العقود؛
المحرّك يعتمدها وينتجها. `probability_skill` يُعيد تصديرها — كل المستوردين
القائمين بلا تغيير (نمط re-export الخلفي في D-166/D-168).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.doctrine import PROBABILITY_CALCULATION_DOCTRINE_VERSION

# نفس الاسم المختصر الذي كان في probability_skill — العقود تختم إصدار الـ doctrine.
DOCTRINE_VERSION = PROBABILITY_CALCULATION_DOCTRINE_VERSION


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
    component: Literal["probability_tree"] = "probability_tree"
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


class CombinationGroup(RobustBaseModel):
    """مجموعة (لون/صنف) في مسألة سحب متزامن: عددها وعدد تأليفاتها C(count, k).

    ## V30.0 — حارس الحلقة الداخلية (Sub-Group Leak Guardrail)
    حين يكون عدد المجموعة ``count`` أقل من عدد السحب ``k`` (مثل سحب 3 كرات
    من مجموعتين بيضاوين فقط)، يكون اختيار k منها **مستحيلاً رياضياً**. في هذه
    الحالة:
      • لا نُنفِّذ ``math.comb`` (الذي يُرجِع 0 مضلِّلاً).
      • لا نُخرِج ``C_2^3 = 0`` (يُربك الطالب — يبدو خطأً حسابياً).
      • نضع ``is_possible=False`` + ``pedagogical_string`` تربوية صريحة.
    الواجهة تعرض ``pedagogical_string`` حين ``is_possible=False`` بدل أي صيغة.
    """

    label: str = Field(..., min_length=1, max_length=80)
    count: int = Field(..., ge=0, description="عدد عناصر هذه المجموعة")
    favorable_combinations: int = Field(
        ..., ge=0, description="C(count, k) — تأليفات اختيار k منها (0 إن مستحيل)"
    )
    is_possible: bool = Field(
        default=True, description="False إن k > count (اختيار مستحيل — لا تأليف)"
    )
    pedagogical_string: str = Field(
        default="",
        max_length=160,
        description="رسالة تربوية حين الاستحالة (بدل C_n^k = 0 المضلِّل)",
    )
    color: str = Field(default="", description="رمز CSS للون (red/white/...) لرسم العنصر")


class CombinationsModelOutput(RobustBaseModel):
    """مخرج السحب المتزامن (Combinatorics) — Protocol V19.0 §2.B.

    «دفعة واحدة» = سحب آني → فضاء العيّنة C(n, k)، لا شجرة تتابعية. هذا النموذج
    يُغذّي مكوّن ``combinations_visualizer`` (مجموعات + صيغة C_n^k)، وهو ممنوع
    منعاً باتاً من استخدام شجرة الاحتمالات (كارثة تربوية حين تُفرَض على مسألة آنية).
    """

    skill: Literal["probability_calculation"] = "probability_calculation"
    success: Literal[True] = True
    component: Literal["combinations_visualizer"] = "combinations_visualizer"
    doctrine_version: str = DOCTRINE_VERSION
    draw_mode: Literal["simultaneous"] = "simultaneous"
    n: int = Field(..., ge=1, description="حجم الفضاء (عدد العناصر الكلي)")
    k: int = Field(..., ge=1, description="عدد العناصر المسحوبة دفعةً واحدة")
    total_combinations: int = Field(..., ge=1, description="C(n, k) — عدد تأليفات الفضاء")
    groups: list[CombinationGroup]
    same_group_favorable: int = Field(
        ..., ge=0, description="مجموع C(count, k) لكل المجموعات (حدث «k من نفس الصنف»)"
    )
    formula: str = Field(default="C(n, k) = n! / (k!·(n-k)!)")
    # V30.0 — وضع الغوص العميق (Deep Dive Generative UI): يُفعَّل حين يعبّر
    # الطالب عن حيرة كاملة («لم أفهم أي شيء»). يُغذّي القصة البصرية كاملةً
    # (urn_state + total_draw_visual + event_analysis) بدل جدار نصّي.
    deep_dive: bool = Field(default=False, description="True = قصة بصرية شاملة (الطالب حائر)")
    urn_state: list[dict[str, object]] = Field(
        default_factory=list,
        description="حالة الكيس البصرية: [{label, count, color}] لرسم العناصر",
    )
    event_analysis: list[dict[str, object]] = Field(
        default_factory=list,
        description="تحليل بصري للأحداث: [{label, is_possible, pedagogical_string, color, value}]",
    )
    title: str = "تأليفات السحب الآني"
    duration_ms: int = 0


class ExerciseStep(RobustBaseModel):
    """خطوة واحدة في القصة التربوية الشاملة (Protocol V31.5 — Full Exercise OS).

    عقد مُفكَّك صارم (strict decoupled) — مطابق لعقد ImpossibleCaseOutput: كل
    خطوة تفصل المنطق (``numerical_state``) عن التلميحات البصرية
    (``visual_directives``) عن الرسالة التربوية (``pedagogical_message``).
    لا تُخرج الخلفية HTML/SVG — الواجهة (RSC) تُصيّر كل خطوة حسب ``render_kind``.
    """

    step_index: int = Field(..., ge=0, description="ترتيب الخطوة (0-based)")
    step_id: str = Field(..., min_length=1, max_length=48, description="معرّف الخطوة الدلالي")
    title: str = Field(..., min_length=1, max_length=120, description="عنوان الخطوة بالعربية")
    render_kind: Literal["urn", "combinations", "event_breakdown", "distribution"] = Field(
        ..., description="نوع التصيير البصري للخطوة"
    )
    visual_directives: dict[str, object] = Field(
        default_factory=dict, description="تلميحات بصرية (animation_hint, render_kind ...)"
    )
    numerical_state: dict[str, object] = Field(
        default_factory=dict, description="الأرقام الخام لهذه الخطوة (منفصلة عن العرض)"
    )
    pedagogical_message: str = Field(
        ..., min_length=1, max_length=400, description="شرح تربوي قصير لهذه الخطوة"
    )
    # D-116 (المُعلّم التفاعلي): سؤال واحد حتمي + إجابة متوقَّعة + تلميح — يُمكّن
    # الواجهة من «اسأل → الطالب يحاول → تحقق → اكشف الخطوة». فارغ ⇒ كشف مباشر.
    # العقد: {question, answer_kind: "choice"|"number", choices?, expected_index?,
    #         expected?, hint}. حتمي بلا LLM — الطالب يبني الجواب بنفسه (لا تلقين).
    interactive: dict[str, object] = Field(
        default_factory=dict, description="عقد السؤال الواحد التفاعلي الحتمي (D-116)"
    )


class FullExerciseStoryOutput(RobustBaseModel):
    """القصة التربوية الشاملة لتمرين كامل — Protocol V31.5 (Full Exercise OS).

    حين يعبّر الطالب عن حيرة كاملة («لم أفهم أي شيء») في مسألة سحب آني، لا نكتفي
    بمكوّن تأليفات واحد، بل نُولِّد **سلسلة خطوات بصرية** تغطّي التمرين بأكمله:
    فهم المعطيات → فضاء العيّنة → الحدث المركّب → المتغيّر العشوائي. كل خطوة
    مستقلّة بعقدها الثلاثي (visual/numerical/pedagogical) فتُصيّرها الواجهة
    كـ Carousel تربوي.

    ## التعميم (Anti-Overfitting — D-076)
    الخطوات تُشتق ديناميكياً من التركيبة المُكتشَفة + وضع السحب، لا من مفردات
    مسألة بعينها. المتغيّر العشوائي (توزيع فوق-هندسي) يُحسب حتمياً بـ math.comb.

    ## قانون الكبح النصي (Text-Wall Muzzle — V28.0)
    ``companion_text`` (≤ 120 حرف) هو النص الوحيد المرافق. أي جدار نصّي من LLM
    محظور — القصة البصرية تُعلِّم 100% بدون مقالات رياضية.
    """

    skill: Literal["probability_calculation"] = "probability_calculation"
    success: Literal[True] = True
    component: Literal["full_exercise_story"] = "full_exercise_story"
    ui_mode: Literal["deep_dive_story"] = "deep_dive_story"
    doctrine_version: str = DOCTRINE_VERSION
    n: int = Field(..., ge=1, description="حجم الفضاء (عدد العناصر الكلي)")
    k: int = Field(..., ge=1, description="عدد العناصر المسحوبة دفعةً واحدة")
    total_combinations: int = Field(..., ge=1, description="C(n, k) — فضاء العيّنة")
    exercise_steps: list[ExerciseStep] = Field(
        ..., min_length=1, description="خطوات القصة التربوية بالترتيب"
    )
    companion_text: str = Field(
        default="إليك الشرح البصري المفصل لكل أجزاء التمرين خطوة بخطوة 🪄",
        max_length=120,
        description="نص مرافق مكبوت (≤ 120 حرف) — يُبثّ بدلاً من LLM pipeline",
    )
    title: str = "الشرح البصري الشامل للتمرين"
    duration_ms: int = 0


class ImpossibleVisualDirectives(RobustBaseModel):
    """التوجيهات البصرية للواجهة — منفصلة عن المنطق والحساب (decoupled)."""

    animation_hint: str = Field(default="bag_shake", description="تلميح الأنيميشن")
    fallback_math: None = Field(default=None, description="لا حساب — مقصود (null)")


class ImpossibleNumericalState(RobustBaseModel):
    """الحالة العددية المجرّدة — الواجهة ترسم منها القصة (بلا حساب تأليفي)."""

    available_items: int = Field(..., ge=0, description="عدد العناصر المتاحة فعلاً")
    requested_items: int = Field(..., ge=1, description="عدد العناصر المطلوب سحبها")
    item_color: str = Field(..., description="رمز اللون (white/red/...) لرسم العنصر")


class ImpossibleCaseOutput(RobustBaseModel):
    """مخرج «الحالة المستحيلة» — Protocol V28.0 (محرّك البيداغوجيا البصرية).

    عقد مُفكَّك صارم (strict decoupled): يفصل المنطق (``numerical_state``) عن
    التلميحات البصرية (``visual_directives``) عن الرسالة التربوية
    (``pedagogical_message``). حين يطلب الطالب سحب k عنصراً من صنف لا يملك إلا
    m < k (بلا إرجاع)، نُقصِّر الدائرة (short-circuit) فوراً قبل أي عقدة حساب
    أو شجرة أو synthesizer: لا C(2,3)=0، لا صفر مجرّد، لا كسر منحلّ — بل حمولة
    تربوية نظيفة تُرجَع مباشرة للواجهة.

    ## قانون الكبح النصي (Text-Wall Muzzle — Protocol V28.0)
    ``companion_text`` هو النص الوحيد المسموح به مرافقاً للمكوّن البصري.
    يجب أن يكون جملة واحدة أو جملتين فقط (≤ 120 حرف). أي نص إضافي من LLM
    محظور تماماً — الواجهة البصرية تُعلِّم 100% بدون نص مطوَّل.
    """

    skill: Literal["probability_calculation"] = "probability_calculation"
    success: Literal[True] = True
    component: Literal["impossible_draw_animation"] = "impossible_draw_animation"
    ui_mode: Literal["impossible_case"] = "impossible_case"
    visual_directives: ImpossibleVisualDirectives = Field(
        default_factory=ImpossibleVisualDirectives
    )
    numerical_state: ImpossibleNumericalState
    pedagogical_message: str = Field(..., min_length=1, description="رسالة تربوية لطيفة بالعربية")
    # V28.0: النص المرافق المكبوت — جملة واحدة أو جملتان فقط (≤ 120 حرف).
    # يُبثّ بدلاً من LLM pipeline الكامل — يمنع كارثة جدار النص.
    companion_text: str = Field(
        default="إليك تفصيل التمرين في واجهتك التفاعلية الخيالية أدناه 🪄",
        max_length=120,
        description="نص مرافق مكبوت (≤ 120 حرف) — يُبثّ بدلاً من LLM pipeline",
    )
    # حقول ملموسة إضافية (Abstraction Ban) — لا تكسر العقد الصارم أعلاه.
    item_label: str = Field(..., min_length=1, description="التسمية العربية الملموسة")
    container: str = Field(default="كيس", description="الوعاء (كيس/صندوق/علبة)")
    doctrine_version: str = DOCTRINE_VERSION
    title: str = "عملية مستحيلة"
    duration_ms: int = 0


class ProbabilityFailure(RobustBaseModel):
    """مخرج المحرّك عند عدم وجود نموذج قابل للحساب — يسمح بالتقدّم لمسار آخر."""

    skill: Literal["probability_calculation"] = "probability_calculation"
    success: Literal[False] = False
    reason: str
