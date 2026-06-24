"""
SemanticPropertySkill — الطبقة الدلالية العامة + Misconception Graph (الطبقة 2 من
المعمارية الإدراكية العصبية-الرمزية، D-131).

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill».

## المسؤولية الواحدة
تحويل عبارة رياضية حرّة → **خاصية canonical** (`property_id`) + تعريف حتمي ملموس، و**تشخيص
الاعتقاد الخاطئ** (misconception) الذي يحمله الطالب لاختيار التدخّل المناسب. لا تحسب الرياضيات
(الأرقام من المحرك الرمزي، الطبقة 3)، ولا تطرح السؤال (الطبقة 4)، ولا تقرّر السياسة (D-129).

## الكارثة التي تحلّها (transcript حي)
«ماذا نقصد بجداء أرقامها معدوم؟» لا يُجاب — بينما «ماذا نقصد بالحادثة A؟» تعمل. السبب: فرع
event_meaning كان **مُجمَّداً على الحادثة A** («نفس اللون»). الحل: **طبقة دلالية عامة data-driven**
(لا special-casing) تُغطّي A/B/C/D عبر سجلّ خصائص، + شبكة مفاهيم خاطئة «شخّص ثم تدخّل».

## القفزة (نقد المالك): من Concept Graph إلى Misconception Graph
ثلاثة طلاب يسألون «ماذا يعني الجداء معدوم؟» لكنهم يحملون misconceptions مختلفة (يجهل خاصية الصفر /
يجهل معنى الجداء / يجهل ربطه بالكرات) ⇒ **تدخّلات مختلفة**. كل عقدة لها `mtype` (تصنيف ثلاثي صغير) +
`probe` تشخيصي + `intervention` مُوجَّه + `bkt_concept` صريح (لا عقدة بلا أثر مقاس).

## المعمارية العصبية-الرمزية (D-131)
- **الطبقة 1 (LLM = Listener فقط)**: لغة حرّة → `property_id` من enum مُقيَّد محروس + fallback حتمي.
  ليس حَكماً خفياً ولا مصدراً للحقيقة.
- **الطبقة 3 (المحرك الرمزي)**: الأرقام (14/165/C(11,3)) من `ProbabilityCalculatorSkill`، لا من هنا.

## القياس (Prometheus)
- `cogniforge_skill_semantic_property_total{property_id,source}` (counter)
- المقاييس السلوكية الأربعة (§5، D-131): انظر `app.services.skills.tutor_metrics`.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.doctrine import SEMANTIC_PROPERTY_DOCTRINE_VERSION

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _normalize(text: str) -> str:
    return (text or "").translate(_AR_DIGITS).strip().lower()


# ── الطبقة 2 (بذرة الشبكة): شبكة المفاهيم (data، قابلة للتوسّع) ──────────────────────
CONCEPT_GRAPH: dict[str, tuple[str, ...]] = {
    "probability": ("event", "sample_space", "favorable_cases", "conditional", "random_variable"),
    "arithmetic_property": ("product_odd", "product_even", "product_zero"),
}


# ── سجلّ الخصائص (data-driven — لا special-casing) ──────────────────────────────────
@dataclass(frozen=True)
class PropertySpec:
    """مواصفات خاصية رياضية: markers + تعريف حتمي ملموس + ربط canonical/BKT."""

    property_id: str
    markers: tuple[str, ...]
    title: str
    definition: str
    concept_id: str  # canonical / BKT concept
    domain: str  # probability_event | arithmetic_property
    #: D-136: مثال ملموس حتمي مُؤصَّل بأرقام التمرين (للأسئلة «اعطني مثال» — واعٍ بالمفهوم).
    example: str = ""
    #: D-138 (Understanding Signal): علامات **أثر فهم المفهوم** في رسائل الطالب (آلية لا تقليد
    #: عبارة). وجودها ⇒ المصفوفة التصعيدية تتوقّف (mastered) بدل التصعيد — التصعيد على الأثر لا العدّ.
    evidence_markers: tuple[str, ...] = ()


#: إضافة خاصية جديدة = مدخل هنا، **لا فرع كود**.
PROPERTY_REGISTRY: dict[str, PropertySpec] = {
    "same_color": PropertySpec(
        property_id="same_color",
        markers=("نفس اللون", "نفس لون", "ذات اللون", "اللون نفسه", "الحادثة a", "الحدث a"),
        title="ماذا نقصد بالحادثة A؟",
        definition=(
            "الحادثة A هي الحصول على **3 كرات من نفس اللون** عند سحب 3 دفعةً واحدة — "
            "كلها حمراء، أو كلها خضراء، أو كلها بيضاء. لاحظ: عدد البيضاء 2 فقط، فلا يمكن سحب "
            "3 بيضاء — إذن A تتحقّق باللون الأحمر أو الأخضر."
        ),
        concept_id="event_meaning",
        domain="probability_event",
        example=(
            "مثال ملموس: لو سحبتَ 3 كرات خضراء (كلها خضراء) ⇒ تحقّقت A؛ أمّا لو سحبتَ كرتين حمراوين "
            "وكرة خضراء (لونان مختلفان) ⇒ **لم** تتحقّق A، لأن A تتطلّب لوناً واحداً للكرات الثلاث."
        ),
    ),
    "product_zero": PropertySpec(
        property_id="product_zero",
        markers=(
            "معدوم",
            "جداء معدوم",
            "ارقامها معدوم",
            "حاصل الضرب صفر",
            "جداء صفر",
            "الحادثة d",
            "الحدث d",
        ),
        title="ماذا نقصد بجداء أرقامها معدوم؟",
        definition=(
            "**حاصل ضرب الأرقام الثلاثة = 0**، ويتحقّق إذا (وفقط إذا) سُحبت **كرة واحدة على الأقل "
            "تحمل الرقم 0**؛ لأن ضرب أي عددٍ في صفر يساوي صفراً."
        ),
        concept_id="product_zero",
        domain="arithmetic_property",
        example=(
            "مثال ملموس: لو سحبتَ الكرة الحمراء التي تحمل الرقم **0** مع كرتين أخريين أرقامهما 1 و3، "
            "فالجداء = 0×1×3 = **0** ⇒ تحقّق «الجداء معدوم»؛ يكفي وجود كرة واحدة تحمل 0."
        ),
    ),
    "product_odd": PropertySpec(
        property_id="product_odd",
        markers=("فردي", "جداء فردي", "حاصل الضرب فردي", "الحادثة b", "الحدث b"),
        title="ماذا نقصد بجداء أرقامها فردي؟",
        definition=(
            "**حاصل ضرب الأرقام الثلاثة فردي**، ويتحقّق إذا كانت **الأرقام الثلاثة كلها فردية** — "
            "أي لا توجد أي كرة تحمل رقماً زوجياً ولا الرقم 0 (لأن وجود زوجي أو صفر يجعل الجداء غير فردي)."
        ),
        concept_id="product_odd",
        domain="arithmetic_property",
        example=(
            "مثال ملموس: لو سحبتَ 3 كرات أرقامها 1 و3 و1 (كلها فردية) ⇒ الجداء = 1×3×1 = 3 **فردي**. "
            "لكن لو ظهر فيها الرقم 4 أو 0 (زوجي) ⇒ يصبح الجداء زوجياً، فلا يتحقّق الشرط."
        ),
    ),
    "product_even": PropertySpec(
        property_id="product_even",
        markers=("زوجي", "جداء زوجي", "حاصل الضرب زوجي", "الحادثة c", "الحدث c"),
        title="ماذا نقصد بجداء أرقامها زوجي؟",
        definition=(
            "**حاصل ضرب الأرقام الثلاثة زوجي**، ويتحقّق إذا حملت **كرة واحدة على الأقل رقماً زوجياً** "
            "(والزوجي يشمل الرقم 0)؛ يكفي عامل زوجي واحد ليصبح الجداء كله زوجياً."
        ),
        concept_id="product_even",
        domain="arithmetic_property",
        example=(
            "مثال ملموس: لو سحبتَ الكرة الخضراء التي تحمل الرقم **4** (وهو زوجي) مع كرتين أرقامهما 1 و3، "
            "فالجداء = 4×1×3 = 12 **زوجي** — لأن وجود عامل زوجي واحد (4) يكفي ليصبح الجداء كله زوجياً."
        ),
    ),
    # D-132: مفاهيم التمرين الأخرى (تعريفات حتمية مُؤصَّلة) — جاهزية لمفاهيم التمرين كاملاً.
    "random_variable": PropertySpec(
        property_id="random_variable",
        markers=("المتغير العشوائي", "متغير عشوائي", "المتغيّر العشوائي", "المتغير العشوائي x"),
        title="ماذا نقصد بالمتغير العشوائي X؟",
        definition=(
            "المتغير العشوائي هو **قاعدة تُعطي لكل نتيجة ممكنة عدداً**. في هذا التمرين، X هو **عدد "
            "الكرات التي تحمل رقماً زوجياً** في السحب الثلاثي — فيأخذ قيمة من 0 إلى 3 حسب السحبة."
        ),
        concept_id="random_variable",
        domain="probability_concept",
        example=(
            "مثال ملموس: لو سحبتَ كرة رقمها 4 (زوجي) وكرة رقمها 0 (زوجي) وكرة رقمها 1 (فردي)، فإن "
            "عدد الكرات ذات الرقم الزوجي = 2 ⇒ X = **2**. لو كانت كلها فردية ⇒ X = 0، وهكذا."
        ),
        evidence_markers=(
            "يأخذ قيمة",
            "يأخذ القيم",
            "قاعدة تعطي",
            "لكل نتيجة عدد",
            "عدد الكرات الزوجية",
        ),
    ),
    "expected_value": PropertySpec(
        property_id="expected_value",
        markers=("الأمل الرياضي", "الامل الرياضي", "الأمل", "أمله", "e(x"),
        title="ماذا نقصد بالأمل الرياضي E(X)؟",
        definition=(
            "الأمل الرياضي E(X) هو **متوسط القيم التي يأخذها المتغير X موزوناً باحتمالاتها** — "
            "القيمة المتوقَّعة لـ X على المدى الطويل لو كرّرنا السحب كثيراً."
        ),
        concept_id="expected_value",
        domain="probability_concept",
        example=(
            "مثال ملموس على فكرة الأمل: لو كان X يأخذ القيمة 0 باحتمال النصف والقيمة 2 باحتمال النصف، "
            "فالأمل = (0 × ½) + (2 × ½) = 1 — أي **نضرب كل قيمة في احتمالها ثم نجمع**؛ نفس الطريقة تُطبَّق على قيم X هنا."
        ),
        evidence_markers=(
            "نضرب كل قيمة في احتمالها",
            "نضرب القيمة في احتمالها",
            "المتوسط المرجح",
            "متوسط القيم",
            "ثم نجمع",
        ),
    ),
    "conditional_probability": PropertySpec(
        property_id="conditional_probability",
        markers=("الاحتمال الشرطي", "احتمال شرطي", "بعلم أن", "بعلم ان", "p_a", "pa(b"),
        title="ماذا نقصد بالاحتمال الشرطي؟",
        definition=(
            "الاحتمال الشرطي هو **احتمال تحقّق حادثة بعلم أن حادثة أخرى قد وقعت**. مثلاً P_A(B) = "
            "احتمال تحقّق B بشرط أننا نعلم أن A قد تحقّقت — فنُقيّد فضاء الإمكانات بالحالات التي تحقّق A."
        ),
        concept_id="conditional_probability",
        domain="probability_concept",
        example=(
            "مثال ملموس على الفكرة: لو علمتَ أن الكرات الثلاث من **نفس اللون** (تحقّقت A)، فإننا نحسب "
            "احتمال B **داخل هذه الحالة فقط** — نُقصِر الفضاء على سحبات A ثم ننظر أيّها يحقّق B أيضاً."
        ),
        evidence_markers=(
            "تقلص الفضاء",
            "يتقلص الفضاء",
            "نقصر الفضاء",
            "نضيق الفضاء",
            "نقسم على عدد اقل",
            "داخل الحالة",
            "الفضاء المشروط",
            "بشرط ان",
            "نعرف معلومة",
        ),
    ),
    # D-137: «الحالات الملائمة» مفهوم مُسجَّل (كان غير مُسجَّل ⇒ detect_active_concept يتخطّاه
    # إلى مفهوم أقدم ⇒ «اعطني مثال» بعده يُعطي مثالاً خاطئاً). تعريف المفهوم (لا خطوة الحساب —
    # خطوة العدّ تخصّ D-135 kc_favorable_cases).
    "favorable_cases": PropertySpec(
        property_id="favorable_cases",
        markers=(
            "الحالات الملائمة",
            "الحالة الملائمة",
            "الحالات المناسبة",
            "الحالات الناجحة",
            "الحالات المؤاتية",
            "العدد الملائم",
        ),
        title="ماذا نقصد بالحالات الملائمة؟",
        definition=(
            "الحالات الملائمة لحادثةٍ هي **عدد النتائج التي تُحقّق تلك الحادثة** من بين كل النتائج "
            "الممكنة. هي **بسط** الاحتمال: كلّما زادت الحالات الملائمة زاد احتمال الحادثة."
        ),
        concept_id="favorable_cases",
        domain="probability_concept",
        example=(
            "مثال ملموس على الفكرة: لحادثة «نفس اللون» نعدّ تأليفات كل لون على حدة — "
            "C(4,3) = (4×3×2)/(3×2×1) للحمراء، وC(5,3) = (5×4×3)/(3×2×1) للخضراء، "
            "أمّا البيضاء فمستحيلة لأن عددها أقل من المطلوب — ثم **نجمع الممكنة فقط** لنحصل على الحالات الملائمة."
        ),
        evidence_markers=(
            "البسط",
            "عدد النتائج التي تحقق",
            "عدد الحالات التي تحقق",
            "نجمع الملائمة",
            "نجمع الممكنة",
        ),
    ),
    # D-139: نمطا السحب — مفهومان مُسجَّلان (كان «ما هو السحب على التوالي» ينجرف للحادثة A).
    "sequential_without_replacement": PropertySpec(
        property_id="sequential_without_replacement",
        markers=(
            "السحب على التوالي",
            "على التوالي بدون إرجاع",
            "على التوالي وبدون إرجاع",
            "بدون إرجاع",
            "بدون ارجاع",
            "على التوالي",
        ),
        title="ماذا نقصد بالسحب على التوالي بدون إرجاع؟",
        definition=(
            "السحب على التوالي بدون إرجاع يعني سحب الكرات **واحدة تلو الأخرى**، وكل كرة مسحوبة "
            "**لا تُعاد** إلى الكيس. لذلك **يتناقص عدد الكرات** في كل سحبة، و**الترتيب يهمّ** "
            "(السحبة الأولى ثم الثانية ثم الثالثة)."
        ),
        concept_id="sequential_without_replacement",
        domain="probability_concept",
        example=(
            "مثال ملموس: كيس فيه 3 كرات (حمراء، زرقاء، خضراء). نسحب كرتين على التوالي بدون إرجاع: "
            "نأخذ الأولى ونحتفظ بها خارج الكيس، ثم نسحب الثانية من **الكرتين الباقيتين فقط**. "
            "عدد الإمكانات ينقص من 3 إلى 2 بين السحبتين."
        ),
        evidence_markers=(
            "الترتيب يهم",
            "لا نعيد",
            "بدون اعادة",
            "ينقص العدد",
            "يتناقص العدد",
            "واحدة تلو الاخرى",
        ),
    ),
    "simultaneous_draw": PropertySpec(
        property_id="simultaneous_draw",
        markers=(
            "السحب دفعة واحدة",
            "دفعة واحدة",
            "دفعةً واحدة",
            "في آن واحد",
            "في ان واحد",
            "السحب الآني",
            "الآني",
        ),
        title="ماذا نقصد بالسحب دفعة واحدة؟",
        definition=(
            "السحب دفعة واحدة (آنياً) يعني أخذ الكرات **معاً في وقت واحد** دون ترتيب — نحصل على "
            "**مجموعة** من الكرات لا تسلسلاً. لا يوجد «أوّل» و«ثانٍ»، فقط أيّ كرات اجتمعت معاً. "
            "هذا **عكس** السحب على التوالي حيث يهمّ الترتيب."
        ),
        concept_id="simultaneous_draw",
        domain="probability_concept",
        example=(
            "مثال ملموس: كيس فيه 4 كرات. السحب «دفعة واحدة» = نُدخل اليد ونأخذ 3 كرات معاً في "
            "قبضة واحدة — لا نميّز أيّها سُحبت أولاً. النتيجة **مجموعة** من 3 كرات، والترتيب لا يهمّ."
        ),
        evidence_markers=(
            "معا في وقت واحد",
            "لا يهم الترتيب",
            "مجموعة",
            "دون ترتيب",
            "دفعة واحدة معا",
        ),
    ),
}


# ── الطبقة 2 الحقيقية: Misconception Graph (شخّص ثم تدخّل) ───────────────────────────
@dataclass(frozen=True)
class MisconceptionNode:
    """عقدة اعتقاد خاطئ: نوع + إشارات + probe تشخيصي + تدخّل مُوجَّه + ربط BKT صريح."""

    id: str
    mtype: str  # rule_property | symbol_meaning | example_linking
    signals: tuple[str, ...]
    probe: str
    intervention: str
    bkt_concept: str


#: التصنيف الثلاثي الصغير المبدئي (يمنع تضخّم عقد متشابهة — نقد المالك).
MISCONCEPTION_TYPES: tuple[str, ...] = ("rule_property", "symbol_meaning", "example_linking")

#: لكل `concept_id` عقد الاعتقاد الخاطئ الممكنة — تدخّل مختلف لكل عقدة.
MISCONCEPTION_GRAPH: dict[str, tuple[MisconceptionNode, ...]] = {
    "product_zero": (
        MisconceptionNode(
            id="unknown_zero_property",
            mtype="rule_property",
            signals=("لا اعرف الصفر", "ماذا يفعل الصفر", "الصفر", "ضرب", "كيف صفر", "خاصية"),
            probe="سؤال سريع: كم يساوي 7 × 0؟ وكم يساوي 0 × 5؟",
            intervention=(
                "ضرب أي عددٍ في صفر يساوي صفراً دائماً؛ فيكفي أن تحمل **كرة واحدة الرقم 0** ليصبح "
                "حاصل الضرب كله = 0."
            ),
            bkt_concept="product_zero",
        ),
        MisconceptionNode(
            id="unknown_product_meaning",
            mtype="symbol_meaning",
            signals=("جمع", "نجمع", "الجمع", "ما معنى جداء", "ماهو الجداء", "اجمع", "نضيف"),
            probe="الجداء يعني الجمع أم الضرب؟",
            intervention=(
                "الجداء = **حاصل الضرب**: نضرب الأرقام الثلاثة بعضها في بعض (لا نجمعها)."
            ),
            bkt_concept="product_meaning",
        ),
        MisconceptionNode(
            id="unknown_ball_mapping",
            mtype="example_linking",
            signals=("اي كرة", "أي كرة", "اين الصفر", "أين الصفر", "كيف اعرف", "اي الكرات"),
            probe="أيّ الكرات في هذا الكيس تحمل الرقم 0؟",
            intervention=(
                "بعض الكرات الحمراء والخضراء تحمل الرقم 0؛ سحب إحداها يجعل حاصل الضرب = 0."
            ),
            bkt_concept="ball_number_mapping",
        ),
    ),
    "same_color": (
        MisconceptionNode(
            id="unknown_event_success",
            mtype="rule_property",
            signals=("متى تنجح", "متى تتحقق", "كيف انجح", "النجاح"),
            probe="إذا سحبت كرتين حمراوين وكرة خضراء، هل تحقّقت A؟ لماذا؟",
            intervention=(
                "A تتحقّق فقط إذا كانت الكرات الثلاث من **لونٍ واحد**؛ خليطٌ من لونين لا يحقّقها."
            ),
            bkt_concept="event_meaning",
        ),
        MisconceptionNode(
            id="unknown_white_impossible",
            mtype="example_linking",
            signals=("البيضاء", "بيضاء", "لماذا الاحمر", "لماذا الاخضر", "اللونين"),
            probe="كم كرة بيضاء في الكيس؟ وكم نحتاج لسحب 3 بيضاء؟",
            intervention=(
                "عدد البيضاء 2 فقط < 3، فسحب 3 بيضاء مستحيل؛ لذلك A تتحقّق بالأحمر أو الأخضر فقط."
            ),
            bkt_concept="color_white",
        ),
    ),
    # D-138 (Misconception Check): عقد الاحتمال الشرطي — تدخّل مُوجَّه بدل تسلّق السلّم أعمى.
    "conditional_probability": (
        MisconceptionNode(
            id="conditional_as_product",
            mtype="rule_property",
            signals=("نضرب", "ضرب الاحتمالين", "جداء الاحتمالين", "p(a) ضرب", "حاصل ضرب"),
            probe="هل الاحتمال الشرطي = ضرب احتمالين، أم إعادة حساب داخل فضاء أضيق؟",
            intervention=(
                "الاحتمال الشرطي ليس ضرب احتمالين؛ هو **إعادة حساب الاحتمال داخل فضاء تقلّص** "
                "بعد أن علمنا أن حادثة وقعت — نقسم على عدد أقل."
            ),
            bkt_concept="conditional_probability",
        ),
        MisconceptionNode(
            id="conditional_space_unchanged",
            mtype="symbol_meaning",
            signals=("نفس الفضاء", "لا يتغير", "نفس العدد", "نقسم على نفس", "الفضاء كامل"),
            probe="بعد أن نعلم أن A وقعت، هل يبقى عدد الإمكانات كما كان أم يقلّ؟",
            intervention=(
                "حين نعلم أن A وقعت، **يتقلّص فضاء الإمكانات** إلى حالات A فقط — لا نقسم على "
                "الفضاء الكامل بل على فضاء A الأصغر."
            ),
            bkt_concept="conditional_probability",
        ),
    ),
}


def concept_for(property_id: str) -> str:
    """الـ concept_id (canonical/BKT) للخاصية."""
    spec = PROPERTY_REGISTRY.get(property_id)
    return spec.concept_id if spec else "event_meaning"


# ── العقود (Pydantic) ────────────────────────────────────────────────────────
class SemanticPropertyInput(RobustBaseModel):
    """مدخلات المفسّر — typed contract."""

    question: str = Field(..., min_length=1, max_length=8000)


class SemanticPropertyOutput(RobustBaseModel):
    """مخرج المفسّر: الخاصية + تعريفها الحتمي + الربط canonical/الشبكة."""

    property_id: str
    title: str
    definition: str
    concept_id: str
    domain: str
    source: str = "deterministic"  # deterministic | llm | fallback
    example: str = ""  # D-136: مثال ملموس واعٍ بالمفهوم (لأسئلة «اعطني مثال»)


class MisconceptionOutput(RobustBaseModel):
    """مخرج التشخيص: العقدة المُشخَّصة (id + نوع + probe + تدخّل + ربط BKT)."""

    node_id: str
    mtype: str
    probe: str
    intervention: str
    bkt_concept: str
    source: str = "deterministic"


# ── Prometheus metrics ─────────────────────────────────────────────────────────────
try:
    from prometheus_client import REGISTRY, Counter

    if "cogniforge_skill_semantic_property_total" in {m.name for m in REGISTRY.collect()}:
        _sp_total = None
    else:
        _sp_total = Counter(
            "cogniforge_skill_semantic_property_total",
            "Semantic-property interpretations, labelled by property_id/source.",
            ["property_id", "source"],
        )

    def _record(property_id: str, source: str) -> None:
        with contextlib.suppress(Exception):
            if _sp_total is not None:
                _sp_total.labels(property_id=property_id, source=source).inc()

except Exception:  # pragma: no cover

    def _record(property_id: str, source: str) -> None:
        pass


#: نية تعريفية صريحة («ماذا نقصد / ما معنى / ما المقصود / كيف أفهم / ما هو X / عرّف»).
#: D-137: «ما هو X» المجرّدة كانت مفقودة ⇒ «ما هو الاحتمال الشرطي» لم تُعدّ تعريفية ⇒ سقطت
#: لـ D-135 فبثّ «14 من 165». أي سؤال «ما هو/ما هي/عرّف» نيّته تعريف.
_DEFINITIONAL_MARKERS: tuple[str, ...] = (
    "ماذا نقصد",
    "ما معنى",
    "ما المقصود",
    "ما هو معنى",
    "ما هو ",
    "ما هي ",
    "ماهو ",
    "ماهي ",
    "عرف ",
    "عرّف ",
    "كيف افهم",
    "ماذا يعني",
    "ماذا تعني",
    "شنو يقصد",
    "واش راه",
    "علاش قال",
)
#: enum مُقيَّد لمخرج الـ LLM Listener (الطبقة 1 الآمنة).
_VALID_PROPERTIES: frozenset[str] = frozenset(PROPERTY_REGISTRY)

#: D-142 (1D): علامات الحيرة — حيرة بلا تسمية مفهوم جديد تُبقي المفهوم النشط (لا تنجرف).
_CONFUSION_MARKERS: tuple[str, ...] = (
    "لم أفهم",
    "لم افهم",
    "مفهمتش",
    "ما فهمت",
    "لا أفهم",
    "لا افهم",
    "ما فهمتش",
    "صعب",
    "مش فاهم",
)
#: D-142 (1D): كلمات وظيفية تُهمَل عند فحص «هل سمّى السؤال مفهوماً جديداً؟».
_STOPWORDS_FOR_CONCEPT_NAMING: frozenset[str] = frozenset(
    {"بكلمة", "كلمة", "في", "عن", "ال", "هذا", "هذه", "ذلك", "هنا", "ب", "بـ"}
)

#: D-137: رؤوس أمثلة/تعريفات المساعد — تُتجاهَل عند كشف المفهوم النشط (markers عابرة تُضلّل).
_CONCEPT_ARTIFACT_MARKERS: tuple[str, ...] = ("## مثال", "مثال ملموس", "مثال آخر", "## ماذا نقصد")

#: D-139: علامات إفراغ التمرين + تمثيلات D-135 (الحادثة A) — يجب ألا تُحدِّد المفهوم النشط أبداً.
#: كان «ما هو السحب على التوالي» ينجرف لـ same_color من نص التمرين («نفس اللون»/«الحادثة A»).
_EXERCISE_DUMP_MARKERS: tuple[str, ...] = (
    "التمرين",
    "يحتوي كيس",
    "نسحب عشوائي",
    "احسب احتمال الحادثة",
    "كلها خضراء",  # تمثيل kc_event_meaning (D-135) — نص الحادثة A العابر
    "تخيل انك سحبت 3 كرات",
)


class SemanticPropertySkill:
    """
    الطبقة الدلالية + Misconception Graph (الطبقة 2 — D-131).

    عقد دائم (لا يُكسر بدون ADR):
    1. data-driven لا special-casing — أي خاصية/اعتقاد جديد = مدخل، لا فرع كود.
    2. الـ LLM = Listener فقط (enum مُقيَّد + fallback حتمي) — لا حقيقة رياضية، لا حَكم خفي.
    3. «شخّص ثم تدخّل» — تدخّل مختلف لكل misconception؛ كل عقدة لها bkt_concept (لا عقدة بلا أثر).
    """

    _skill_name: str = "semantic_property"
    doctrine_version: str = SEMANTIC_PROPERTY_DOCTRINE_VERSION
    _LLM_TIMEOUT_S: float = 8.0

    def interpret(self, question: str) -> SemanticPropertyOutput | None:
        """حتمي: يطابق العبارة بسجلّ الخصائص → الخاصية + تعريفها. None عند عدم التطابق."""
        norm = _normalize(question)
        if not norm:
            return None
        for spec in PROPERTY_REGISTRY.values():
            if any(m in norm for m in spec.markers):
                _record(spec.property_id, "deterministic")
                return SemanticPropertyOutput(
                    property_id=spec.property_id,
                    title=spec.title,
                    definition=spec.definition,
                    concept_id=spec.concept_id,
                    domain=spec.domain,
                    source="deterministic",
                    example=spec.example,
                )
        return None

    def detect_active_concept(
        self, question: str, history: list[dict[str, str]] | None = None
    ) -> SemanticPropertyOutput | None:
        """D-136/D-137: المفهوم النشط — من السؤال (interpret) وإلا من آخر مفهوم **سأل عنه الطالب**.

        D-137: المفهوم النشط هو ما طرحه **الطالب** (رسائل user)، لا ما ذكره المساعد عابراً في
        مثاله. كان مثال «الاحتمال الشرطي» يذكر «نفس اللون» فيُكتشَف خطأً same_color (الحادثة A)
        ⇒ «لم أفهم» يُعيد الحادثة A. الحل: نُفضّل رسائل الطالب، ونتجاهل أمثلة/تعريفات المساعد.
        يفحص آخر ~6 رسائل (الأحدث أولاً).
        """
        out = self.interpret(question)
        if out is not None:
            return out
        # D-139: سؤال تعريفي عن مفهوم **جديد** (غير مُسجَّل) ⇒ لا تنجرف لمفهوم سابق/تمرين.
        # أي «ما هو X» يُعيد ضبط المفهوم النشط؛ يُسلَّم لـ LLM Listener-Definer (D-132).
        # D-142 (1D): لكن «ماذا نقصد لم أفهم» (حيرة بلا تسمية مفهوم) **لا** تُعيد الضبط —
        # تُبقي المفهوم النشط (من تاريخ الطالب)، وإلا انجرف النظام إلى «لم أفهم أي مفهوم؟».
        if self.is_definitional(question) and not self._is_bare_confusion_definitional(question):
            return None
        # D-143: سؤال حسابي (نضرب/ضربنا/«حصلنا على»/«56») بلا مفهوم مُطابَق ⇒ لا تنجرف لمفهوم
        # سابق من التاريخ (الحادثة A المُلوِّثة). يتولّاه المسار الحسابي الحتمي، لا سُلّم الحادثة A.
        _ql = (question or "").lower()
        if any(m in _ql for m in ("نضرب", "ضربنا", "حصلنا على", "56")):
            return None
        history = history or []
        # (1) D-139: المفهوم النشط = آخر مفهوم سأل عنه **الطالب** صراحةً — كامل التاريخ (لا [-6:]).
        # يحلّ قطع النافذة في المحادثات الطويلة (كان «ما هو الاحتمال الشرطي» يخرج خارج النافذة).
        for msg in reversed(history):
            if isinstance(msg, dict) and msg.get("role") == "user":
                found = self.interpret(str(msg.get("content", "")))
                if found is not None:
                    return found
        # (2) fallback مقيّد: رسائل مساعد قصيرة (لا أمثلة/تعريفات، لا إفراغ تمرين، لا نص الحادثة A).
        for msg in reversed(history[-6:]):
            if not isinstance(msg, dict) or msg.get("role") == "user":
                continue
            raw = str(msg.get("content", ""))
            if (
                len(raw) > 400
                or any(mk in raw for mk in _CONCEPT_ARTIFACT_MARKERS)
                or any(mk in _normalize(raw) for mk in _EXERCISE_DUMP_MARKERS)
            ):
                continue
            found = self.interpret(raw)
            if found is not None:
                return found
        return None

    def is_definitional(self, question: str) -> bool:
        """هل السؤال نية تعريفية («ماذا نقصد/ما معنى»)؟"""
        norm = _normalize(question)
        return any(m in norm for m in _DEFINITIONAL_MARKERS)

    def _is_bare_confusion_definitional(self, question: str) -> bool:
        """D-142 (1D): سؤال تعريفي/حيرة **بلا تسمية مفهوم جديد** («ماذا نقصد لم أفهم»)؟

        نزع علامات التعريف والحيرة؛ إن لم يبقَ أي رمز ذي معنى ⇒ حيرة مجرّدة ⇒ نُبقي المفهوم
        النشط (لا نُعيد ضبطه). يميّز «ماذا نقصد لم أفهم» (حيرة) عن «ما هو الاحتمال الشرطي»
        (تسمية مفهوم جديد → إعادة ضبط صحيحة).
        """
        norm = _normalize(question)
        if not norm:
            return True
        residual = norm
        for m in (*_DEFINITIONAL_MARKERS, *_CONFUSION_MARKERS):
            residual = residual.replace(_normalize(m), " ")
        tokens = [
            t for t in residual.split() if len(t) > 1 and t not in _STOPWORDS_FOR_CONCEPT_NAMING
        ]
        return len(tokens) == 0

    async def interpret_or_classify(self, question: str) -> SemanticPropertyOutput | None:
        """هجين: حتمي أولاً؛ عند الغموض + نية تعريفية ⇒ LLM Listener محروس (enum مُقيَّد)."""
        out = self.interpret(question)
        if out is not None:
            return out
        if not self.is_definitional(question):
            return None
        prop_id = await self._classify_with_llm(question)
        if prop_id is None:
            return None
        spec = PROPERTY_REGISTRY[prop_id]
        _record(prop_id, "llm")
        return SemanticPropertyOutput(
            property_id=spec.property_id,
            title=spec.title,
            definition=spec.definition,
            concept_id=spec.concept_id,
            domain=spec.domain,
            source="llm",
        )

    @classmethod
    async def _classify_with_llm(cls, question: str) -> str | None:
        """الطبقة 1: Listener محروس — يُعيد property_id واحداً من الـ enum أو None.

        مخرج مُقيَّد (enum-validation) + timeout + fallback. لا رياضيات، لا تعريف — مجرّد تصنيف.
        """
        import asyncio

        try:
            from app.core.ai_gateway import get_ai_client

            system_prompt = (
                "أنت مُصنّف لغوي (لا تشرح، لا تحسب، لا تعرّف). صنّف عبارة الطالب عن خاصية الكرات "
                "المسحوبة إلى كلمة واحدة فقط من هذه القائمة بلا أي نص آخر:\n"
                "same_color (نفس اللون) | product_zero (جداء/حاصل الضرب معدوم=صفر) | "
                "product_odd (جداء فردي) | product_even (جداء زوجي).\n"
                "أعِد الكلمة الإنجليزية فقط."
            )
            raw = await asyncio.wait_for(
                get_ai_client().send_message(
                    system_prompt, question.strip()[:400], temperature=0.0
                ),
                timeout=cls._LLM_TIMEOUT_S,
            )
            if not raw or not isinstance(raw, str):
                return None
            token = raw.strip().lower().split()[0].strip(".,:;\"'`") if raw.strip() else ""
            if token in _VALID_PROPERTIES:
                return token
            low = raw.lower()
            for p in _VALID_PROPERTIES:
                if p in low:
                    return p
            return None
        except Exception:  # pragma: no cover — fail-safe
            return None

    @classmethod
    async def define_concept(cls, question: str) -> str | None:
        """D-132: الـ LLM Listener-Definer — تعريف مفاهيمي قصير لمفهوم **جديد** (محروس).

        جوهر «الجاهزية للأسئلة الجديدة»: المفهوم غير الموجود في السجلّ. الـ LLM يُنتج **تعريفاً
        عاماً** (معرفة عامة) لا حقيقة محسوبة. تحت سقف صارم قابل للتحقق: لا حساب، لا كشف نتيجة نهائية،
        عربية فصحى، جملة أو جملتان. أي فشل/شكّ ⇒ None (لا تدهور).
        """
        import asyncio

        try:
            from app.core.ai_gateway import get_ai_client

            system_prompt = (
                "أنت مُعرِّف مفاهيم تعليمي (Listener-Definer). عرّف المفهوم الذي يسأل عنه الطالب "
                "في درس الاحتمالات **تعريفاً عاماً قصيراً** (جملة أو جملتان)، عربية فصحى. "
                "**لا تحسب، لا تحلّ التمرين، ولا تذكر أي نتيجة نهائية أو كسر (مثل 14/165). "
                "عرّف المفهوم فقط — ما هو؟**"
            )
            raw = await asyncio.wait_for(
                get_ai_client().send_message(
                    system_prompt, question.strip()[:400], temperature=0.2
                ),
                timeout=cls._LLM_TIMEOUT_S,
            )
            if not raw or not isinstance(raw, str) or not raw.strip():
                return None
            text = raw.strip()

            # ── الحراسة (طبقات قائمة، سقف صارم قابل للتحقق) ──────────────────────
            import re as _re

            from app.services.skills.answer_redaction_skill import redact_final_answers
            from app.services.skills.arabic_stream_guard import is_probably_non_arabic
            from app.services.skills.content_integrity_skill import _strip_garbage_markers

            text = _strip_garbage_markers(text)
            text, _ = redact_final_answers(text, support_level=5)
            text = text.strip()
            if not text or is_probably_non_arabic(text):
                return None
            # شبكة أمان: لا كشف نتيجة نهائية رغم الحجب.
            if _re.search(r"14\s*/\s*165|56\s*/\s*165", text):
                return None
            return text
        except Exception:  # pragma: no cover — fail-safe
            return None

    async def interpret_or_define(self, question: str) -> SemanticPropertyOutput | None:
        """D-132: حتمي أولاً (السجلّ)؛ ثم الـ LLM-Definer للأسئلة الجديدة؛ ثم None.

        هذا يجعل المنصة **جاهزة لأي مفهوم جديد**: المفاهيم المعروفة تعريفها حتمي ملموس؛ المفهوم
        الجديد يُعرَّف عبر الـ Listener-Definer المحروس. لا default مُجمَّد لمفهوم واحد.
        """
        out = self.interpret(question)
        if out is not None:
            return out
        if not self.is_definitional(question):
            return None
        definition = await self.define_concept(question)
        if not definition:
            return None
        _record("novel", "llm")
        return SemanticPropertyOutput(
            property_id="novel",
            title="تعريف",
            definition=definition,
            concept_id="novel",
            domain="probability_concept",
            source="llm",
        )

    def diagnose_misconception(
        self,
        concept_id: str,
        student_text: str,
        history: list[dict[str, str]] | None = None,
    ) -> MisconceptionOutput | None:
        """يُشخّص الاعتقاد الخاطئ من رد الطالب (signals حتمية). None ⇒ يُصدَر probe أولاً.

        «شخّص ثم تدخّل»: نفس المفهوم بإجابات مختلفة ⇒ عقد مختلفة ⇒ تدخّلات مختلفة.
        """
        nodes = MISCONCEPTION_GRAPH.get(concept_id)
        if not nodes:
            return None
        norm = _normalize(student_text)
        if not norm:
            return None
        best: MisconceptionNode | None = None
        best_hits = 0
        for node in nodes:
            hits = sum(1 for s in node.signals if _normalize(s) in norm)
            if hits > best_hits:
                best_hits = hits
                best = node
        if best is None or best_hits == 0:
            return None
        return MisconceptionOutput(
            node_id=best.id,
            mtype=best.mtype,
            probe=best.probe,
            intervention=best.intervention,
            bkt_concept=best.bkt_concept,
            source="deterministic",
        )

    def first_probe(self, concept_id: str) -> str | None:
        """الـ probe التشخيصي الأول للمفهوم (يُصدَر عند الغموض قبل التدخّل)."""
        nodes = MISCONCEPTION_GRAPH.get(concept_id)
        return nodes[0].probe if nodes else None


_semantic_property_singleton: SemanticPropertySkill | None = None


def get_semantic_property_skill() -> SemanticPropertySkill:
    """يُرجع نسخة مفردة (lazy singleton)."""
    global _semantic_property_singleton
    if _semantic_property_singleton is None:
        _semantic_property_singleton = SemanticPropertySkill()
    return _semantic_property_singleton


__all__ = [
    "CONCEPT_GRAPH",
    "MISCONCEPTION_GRAPH",
    "MISCONCEPTION_TYPES",
    "PROPERTY_REGISTRY",
    "MisconceptionNode",
    "MisconceptionOutput",
    "PropertySpec",
    "SemanticPropertyInput",
    "SemanticPropertyOutput",
    "SemanticPropertySkill",
    "concept_for",
    "get_semantic_property_skill",
]
