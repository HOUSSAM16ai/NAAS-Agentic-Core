"""السجلّ القانوني لمنهاج البكالوريا — المصدر الوحيد للحقيقة (D-193).

لماذا هذا الملفّ موجود
----------------------
كلمة «مفهوم» كان لها **ثلاثة تعاريف متنافرة** في المستودع، ولا تتّفق أيّ اثنين منها:

1. `app/services/skills/bkt_engine.py:_CONCEPT_PATTERNS` — ١٤ مُعرَّفاً بعلامات نصّية.
   هذه هي المُعرَّفات **المُخزَّنة فعلاً** في `student_bkt_analytics.concept_id`.
2. `app/services/skills/learning_path_skill.py` — `_CURRICULUM_SEQUENCE` (١١ حافّة) +
   `_CONCEPT_LABELS` (١٥ تسمية). يُقدِّم الطالب إلى `differential_equations` و`geometry`
   و`statistics` — وهي **مُعرَّفات لا يستطيع BKT تصنيفها أبداً**، فالتقدّم يقود إلى
   مفهوم لا يُقاس إتقانه.
3. `microservices/memory_agent/src/domain/concept_graph.py:DEFAULT_CONCEPTS` — ٢٠ مفهوماً
   بمُعرَّفات **مختلفة** (`conditional_prob` مقابل `conditional_probability`،
   `prob_basics` مقابل `probability`). أي جسرٍ بين الاثنين كان سيفشل بصمت.

وفوق ذلك: `classify_concept` تُرجِع `"general"` لكلّ سؤال فيزياء أو علوم طبيعية — أي أنّ
تتبّع المعرفة (الطبقة المعرفية الأساس، D-074) **لا يقيس شيئاً** خارج الرياضيات، بينما
العلوم الطبيعية معاملها **٦** في شعبة العلوم التجريبية (أعلى من الرياضيات).

القانون الذي يُرسيه هذا الملفّ
------------------------------
**تعريفُ المفهوم واحد.** كلّ مُعرَّف يُخزَّن أو يُصنَّف أو يُجدوَل أو يُعرَض يأتي من هنا.
تفرضه بوّابة `scripts/fitness/check_topic_authority_single_source.py` (دَين مُجمَّد يتقلّص
فقط، وهو **فارغ**).

⚠️ **تصحيح إحالة (D-266 · ISS-186):** كان هذا السطر يسمّي `check_curriculum_single_source`
— **وهي غير موجودة على القرص، ولم تُكتب قطّ**. أي أنّ قانون «تعريف المفهوم واحد» بقي بلا
فارضٍ منذ D-193، وهو بالضبط لماذا أمكن لثلاثة تصنيفاتٍ للموضوع أن تتفرّق حتى وقعت ISS-159.
والإحالة الوهمية أخطر من غيابها: تُقرأ حمايةً قائمة فيُبنى عليها.

**استقرار المُعرَّفات عقدٌ مع البيانات المُخزَّنة.** `concept_id` قيمةٌ دائمة في
`student_bkt_analytics` و`tutor_state.kc_progress`؛ تغييرها يتيّم تاريخ الطلاب. لذلك
المُعرَّفات القانونية هنا هي **مُعرَّفات BKT** حرفياً، وتُستوعَب صيغ الوحدات الأخرى
كـ`aliases` تُحَلّ إليها — لا العكس.

عقد الموقع (dep-free)
---------------------
stdlib فقط. لا استيراد من `app/` ولا من أيّ خدمة (قانون الحدود §6.7.و). التطبيع من
`shared/textnorm.py`.

مصدر المعاملات
--------------
`STREAM_COEFFICIENTS` هي معاملات شهادة البكالوريا الرسمية للشعب التي تخدمها المنصّة.
أيّ تصحيح = سطر واحد هنا، ويحرسه اختبار تماسك (كلّ مادة يدرسها مفهومٌ في شعبةٍ ما يجب
أن يكون لها معامل في تلك الشعبة).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final

from shared.textnorm import normalize

#: نسخة السجلّ — تُبَثّ في `/health` فيُعرَف أيّ منهاج يخدم الطلب.
REGISTRY_VERSION: Final = "1.0.0"


class CurriculumError(ValueError):
    """خرق لمجال المنهاج — مُعرَّف مجهول أو شعبة مجهولة.

    نرفع ولا نُرجِع قيمةً افتراضية: مفهومٌ مجهول يُعامَل صامتاً كـ«عام» هو بالضبط العطب
    الذي جعل BKT يكتب صفوف إتقان على المفهوم الخطأ (ISS-112).
    """


# ─────────────────────────────────────────────────────────────────────────────
# الشُّعب والمواد والمعاملات
# ─────────────────────────────────────────────────────────────────────────────

CANONICAL_STREAMS: Final[tuple[str, ...]] = (
    "experimental_sciences",  # علوم تجريبية
    "mathematics",  # رياضيات
    "technical_mathematics",  # تقني رياضي
    "management_economics",  # تسيير واقتصاد
)

CANONICAL_SUBJECTS: Final[tuple[str, ...]] = (
    "mathematics",
    "physics",
    "natural_sciences",
)

STREAM_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "experimental_sciences": "علوم تجريبية",
        "mathematics": "رياضيات",
        "technical_mathematics": "تقني رياضي",
        "management_economics": "تسيير واقتصاد",
    }
)

SUBJECT_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "mathematics": "الرياضيات",
        "physics": "العلوم الفيزيائية",
        "natural_sciences": "علوم الطبيعة والحياة",
    }
)

#: معامل كلّ مادة في كلّ شعبة. المعامل يقود الأولوية: مادة بمعامل ٦ تستحقّ من وقت
#: الطالب ثلاثة أضعاف مادة بمعامل ٢، وهذا ما يجعل الجدولة والتقارير ذات معنى.
STREAM_COEFFICIENTS: Final[Mapping[str, Mapping[str, int]]] = MappingProxyType(
    {
        "experimental_sciences": MappingProxyType(
            {"mathematics": 5, "physics": 5, "natural_sciences": 6}
        ),
        "mathematics": MappingProxyType({"mathematics": 7, "physics": 6, "natural_sciences": 2}),
        "technical_mathematics": MappingProxyType(
            {"mathematics": 6, "physics": 6, "natural_sciences": 0}
        ),
        "management_economics": MappingProxyType(
            {"mathematics": 2, "physics": 0, "natural_sciences": 0}
        ),
    }
)

_SCIENCE_STREAMS: Final[tuple[str, ...]] = (
    "experimental_sciences",
    "mathematics",
    "technical_mathematics",
)
_ALL_STREAMS: Final[tuple[str, ...]] = CANONICAL_STREAMS


# ─────────────────────────────────────────────────────────────────────────────
# عقد الإدخال
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CurriculumConcept:
    """مفهومٌ واحد في المنهاج: هويّته، موقعه، كيف يُكتشَف، وكم يزن في الامتحان."""

    concept_id: str
    title_ar: str
    title_fr: str
    subject: str
    #: `"unit"` وحدة منهاج قائمة بذاتها · `"micro"` مفهوم دقيق داخل وحدة (طبقة سوء الفهم).
    kind: str = "unit"
    #: الوحدة الأمّ — تساوي `concept_id` للوحدات نفسها.
    unit: str = ""
    #: علامات الكشف (فصحى · دارجة · فرنسية) — **يجب أن تكون مُطبَّعة مسبقاً**.
    markers: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()
    #: صعوبة ذاتية ٠..١ — تُغذّي صعوبة العنصر في المُجدوِل ومُوَلِّد التمارين.
    difficulty: float = 0.5
    #: تواتر الظهور في مواضيع البكالوريا السابقة ٠..١ — هذا نصف الخندق.
    bac_frequency: float = 0.0
    streams: tuple[str, ...] = _SCIENCE_STREAMS
    #: مُعرَّفات قديمة من الوحدات المُوحَّدة، تُحَلّ إلى `concept_id`.
    aliases: tuple[str, ...] = field(default_factory=tuple)
    #: أولوية الكشف عند تطابق أكثر من مفهوم. الأعلى يفوز **قبل** طول العلامة.
    #:
    #: يلزم لأنّ بعض الوحدات تحمل علامات **حاوية عامّة**: «دالة»/`fonction` تظهر داخل
    #: كلّ سؤال اشتقاق أو تكامل تقريباً، وطولها يفوق «مشتق»/`derivee` فتخطفها بالطول
    #: لا بالمعنى («dérivée de la fonction» كانت تُصنَّف «دوال عددية»). الترتيب اليدوي
    #: في `_CONCEPT_PATTERNS` القديمة كان يمنع ذلك ضمنياً؛ هنا يصير **مُصرَّحاً**.
    specificity: int = 0

    def __post_init__(self) -> None:
        if not 0.0 <= self.difficulty <= 1.0:
            raise CurriculumError(f"{self.concept_id}: difficulty must be in [0,1]")
        if not 0.0 <= self.bac_frequency <= 1.0:
            raise CurriculumError(f"{self.concept_id}: bac_frequency must be in [0,1]")
        if self.subject not in CANONICAL_SUBJECTS:
            raise CurriculumError(f"{self.concept_id}: unknown subject {self.subject!r}")
        if self.kind not in ("unit", "micro"):
            raise CurriculumError(f"{self.concept_id}: kind must be 'unit' or 'micro'")
        for stream in self.streams:
            if stream not in CANONICAL_STREAMS:
                raise CurriculumError(f"{self.concept_id}: unknown stream {stream!r}")
        object.__setattr__(self, "unit", self.unit or self.concept_id)


def _c(**kwargs: object) -> CurriculumConcept:
    return CurriculumConcept(**kwargs)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# الرياضيات — المُعرَّفات القانونية هي مُعرَّفات BKT (مُخزَّنة، لا تُغيَّر)
# ─────────────────────────────────────────────────────────────────────────────

_MATHEMATICS: Final[tuple[CurriculumConcept, ...]] = (
    _c(
        concept_id="sequences",
        title_ar="المتتاليات العددية",
        title_fr="Suites numériques",
        subject="mathematics",
        markers=(
            "متتاليه",
            "متتاليات",
            "suite",
            "sequence",
            "متتاليه حسابيه",
            "متتاليه هندسيه",
            "حسابيه",
            "هندسيه",
        ),
        difficulty=0.45,
        bac_frequency=0.85,
    ),
    _c(
        concept_id="limits",
        title_ar="النهايات",
        title_fr="Limites",
        subject="mathematics",
        markers=("نهايه", "نهايات", "limite", "limit", "لوبيتال", "lhopital", "l'hopital"),
        prerequisites=("sequences",),
        difficulty=0.5,
        bac_frequency=0.7,
    ),
    _c(
        concept_id="derivatives",
        title_ar="الاشتقاق",
        title_fr="Dérivation",
        subject="mathematics",
        markers=("مشتق", "اشتقاق", "derivee", "derivative", "نهايه المشتق"),
        prerequisites=("limits",),
        difficulty=0.5,
        bac_frequency=0.8,
    ),
    _c(
        concept_id="numerical_functions",
        title_ar="الدوال العددية",
        title_fr="Fonctions numériques",
        subject="mathematics",
        markers=("داله", "دوال", "fonction", "function", "تغيرات", "مجال التعريف", "اتجاه التغير"),
        # وحدة حاوية: «دالة»/`fonction` ترد في كلّ سؤال اشتقاق/تكامل/نهايات.
        specificity=-1,
        prerequisites=("derivatives",),
        difficulty=0.55,
        bac_frequency=0.95,
    ),
    _c(
        concept_id="exponential",
        title_ar="الدالة الأسية",
        title_fr="Fonction exponentielle",
        subject="mathematics",
        markers=("اسيه", "exponentielle", "exponential", "e^", "نشر اسي"),
        prerequisites=("numerical_functions",),
        difficulty=0.6,
        bac_frequency=0.75,
    ),
    _c(
        concept_id="logarithm",
        title_ar="الدالة اللوغاريتمية",
        title_fr="Fonction logarithme",
        subject="mathematics",
        markers=("لوغاريتم", "logarithme", "logarithm", "ln", "log"),
        prerequisites=("exponential",),
        difficulty=0.6,
        bac_frequency=0.7,
    ),
    _c(
        concept_id="integration",
        title_ar="التكامل",
        title_fr="Intégration",
        subject="mathematics",
        markers=("تكامل", "بالتجزيه", "integrale", "integral", "primitive", "داله اصليه", "اصليه"),
        prerequisites=("numerical_functions",),
        difficulty=0.65,
        bac_frequency=0.8,
    ),
    _c(
        concept_id="differential_equations",
        title_ar="المعادلات التفاضلية",
        title_fr="Équations différentielles",
        subject="mathematics",
        markers=("معادله تفاضليه", "معادلات تفاضليه", "equation differentielle", "y' ="),
        prerequisites=("integration",),
        difficulty=0.7,
        bac_frequency=0.4,
        streams=("mathematics", "technical_mathematics"),
    ),
    _c(
        concept_id="trigonometry",
        title_ar="المثلثات",
        title_fr="Trigonométrie",
        subject="mathematics",
        markers=("مثلثات", "جيب", "جيب التمام", "trigonom", "sin", "cos", "tan"),
        difficulty=0.5,
        bac_frequency=0.45,
    ),
    _c(
        concept_id="complex_numbers",
        title_ar="الأعداد المركبة",
        title_fr="Nombres complexes",
        subject="mathematics",
        markers=(
            "عقدي",
            "عقديه",
            "complexe",
            "complex number",
            "عدد مركب",
            # ISS-112: الصيغ المعرَّفة/الجمع ليست سلاسل فرعية من المفرد.
            "اعداد مركبه",
            "الاعداد المركبه",
            "العدد المركب",
            # ISS-114 (D-106): «الدوال المركبة» صياغة طلابية للأعداد المركبة.
            "دوال مركبه",
            "الدوال المركبه",
            "داله مركبه",
            "الداله المركبه",
            "z =",
        ),
        prerequisites=("trigonometry",),
        difficulty=0.65,
        bac_frequency=0.9,
    ),
    _c(
        concept_id="geometry",
        title_ar="الهندسة في الفضاء",
        title_fr="Géométrie dans l'espace",
        subject="mathematics",
        # ⚠️ لا علامة قصيرة تظهر داخل كلمةٍ أخرى: «شعاع» كانت تُطابِق «الإشعاعي» فتخطف
        # «التناقص الإشعاعي» إلى الهندسة (كارثة مُثبَتة وقت البناء). العلامات الطويلة فقط.
        markers=("هندسه في الفضا", "مستقيم ومستوي", "vecteur", "شعاع الاتجاه", "المعلم المتعامد"),
        prerequisites=("complex_numbers",),
        difficulty=0.6,
        bac_frequency=0.55,
    ),
    _c(
        concept_id="arithmetic",
        title_ar="الحساب وقابلية القسمة",
        title_fr="Arithmétique",
        subject="mathematics",
        markers=("قابليه القسمه", "قاسم مشترك", "بيزو", "congruence", "موافقه", "arithmetique"),
        difficulty=0.6,
        bac_frequency=0.35,
        streams=("mathematics",),
    ),
    _c(
        concept_id="probability",
        title_ar="الاحتمالات",
        title_fr="Probabilités",
        subject="mathematics",
        markers=("احتمال", "احتمالات", "عشوايي", "حادثه", "probabilit", "variable aleatoire"),
        difficulty=0.5,
        bac_frequency=1.0,
    ),
    _c(
        concept_id="conditional_probability",
        title_ar="الاحتمال الشرطي",
        title_fr="Probabilité conditionnelle",
        subject="mathematics",
        markers=(
            "احتمال شرط",
            "احتمال مشروط",
            "شجره الاحتمال",
            "شجره احتمال",
            "بشرط",
            "conditional",
        ),
        prerequisites=("probability",),
        difficulty=0.65,
        bac_frequency=0.75,
        aliases=("conditional_prob",),
    ),
    _c(
        concept_id="combinations",
        title_ar="التوافيق",
        title_fr="Combinaisons",
        subject="mathematics",
        markers=("توافيق", "التوافيق", "تاليفه", "تاليفات", "combinaison"),
        prerequisites=("probability",),
        difficulty=0.55,
        bac_frequency=0.7,
    ),
    _c(
        concept_id="permutations",
        title_ar="التراتيب",
        title_fr="Permutations",
        subject="mathematics",
        markers=("ترتيبه", "تراتيب", "permutation", "arrangement", "ترتيبات"),
        prerequisites=("probability",),
        difficulty=0.55,
        bac_frequency=0.5,
    ),
    _c(
        concept_id="random_variable",
        title_ar="المتغير العشوائي",
        title_fr="Variable aléatoire",
        subject="mathematics",
        markers=(
            "متغير عشوايي",
            "المتغير العشوايي",
            "الامل الرياضياتي",
            "esperance",
            "قانون الاحتمال",
        ),
        prerequisites=("probability",),
        difficulty=0.6,
        bac_frequency=0.8,
    ),
    _c(
        concept_id="statistics",
        title_ar="الإحصاء",
        title_fr="Statistiques",
        subject="mathematics",
        markers=("احصا", "الاحصا", "statistique", "الوسط الحسابي", "الانحراف المعياري"),
        prerequisites=("probability",),
        difficulty=0.4,
        bac_frequency=0.3,
    ),
    # ── مفاهيم دقيقة (طبقة سوء الفهم — D-131) ────────────────────────────────
    _c(
        concept_id="product_zero",
        title_ar="الجداء المعدوم",
        title_fr="Produit nul",
        subject="mathematics",
        kind="micro",
        unit="probability",
        markers=("جدا معدوم", "حاصل الضرب معدوم", "ارقامها معدوم", "جدا صفر", "معدوم"),
        prerequisites=("probability",),
        difficulty=0.55,
        bac_frequency=0.15,
    ),
    _c(
        concept_id="product_odd",
        title_ar="الجداء الفردي",
        title_fr="Produit impair",
        subject="mathematics",
        kind="micro",
        unit="probability",
        markers=("جدا فردي", "حاصل الضرب فردي", "ارقامها فردي"),
        prerequisites=("probability",),
        difficulty=0.55,
        bac_frequency=0.12,
    ),
    _c(
        concept_id="product_even",
        title_ar="الجداء الزوجي",
        title_fr="Produit pair",
        subject="mathematics",
        kind="micro",
        unit="probability",
        markers=("جدا زوجي", "حاصل الضرب زوجي", "ارقامها زوجي"),
        prerequisites=("probability",),
        difficulty=0.55,
        bac_frequency=0.12,
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# العلوم الفيزيائية — كانت كلّها تُصنَّف "general" فلا يُقاس منها شيء
# ─────────────────────────────────────────────────────────────────────────────

_PHYSICS: Final[tuple[CurriculumConcept, ...]] = (
    _c(
        concept_id="chemical_kinetics",
        title_ar="المتابعة الزمنية لتحول كيميائي",
        title_fr="Suivi temporel d'une transformation chimique",
        subject="physics",
        markers=(
            "تحول كيميايي",
            "المتابعه الزمنيه",
            "سرعه التفاعل",
            "زمن نصف التفاعل",
            "cinetique",
        ),
        difficulty=0.55,
        bac_frequency=0.8,
    ),
    _c(
        concept_id="chemical_equilibrium",
        title_ar="تطور جملة كيميائية نحو التوازن",
        title_fr="Évolution vers l'équilibre chimique",
        subject="physics",
        markers=(
            "حاله التوازن",
            "نحو التوازن",
            "توازن كيميايي",
            "كسر التفاعل",
            "ثابت التوازن",
            "equilibre chimique",
            "quotient",
        ),
        prerequisites=("chemical_kinetics",),
        difficulty=0.65,
        bac_frequency=0.7,
    ),
    _c(
        concept_id="acid_base",
        title_ar="المحاليل الحمضية والقاعدية",
        title_fr="Solutions acido-basiques",
        subject="physics",
        markers=("حمض", "قاعده", "معايره", "ph", "acide", "base forte", "dosage"),
        prerequisites=("chemical_equilibrium",),
        difficulty=0.6,
        bac_frequency=0.65,
    ),
    _c(
        concept_id="rc_circuit",
        title_ar="ثنائي القطب RC",
        title_fr="Dipôle RC",
        subject="physics",
        markers=(
            "ثنايي القطب rc",
            "مكثفه",
            "شحن المكثفه",
            "ثابت الزمن",
            "condensateur",
            "dipole rc",
        ),
        difficulty=0.55,
        bac_frequency=0.7,
    ),
    _c(
        concept_id="rl_circuit",
        title_ar="ثنائي القطب RL",
        title_fr="Dipôle RL",
        subject="physics",
        markers=("ثنايي القطب rl", "وشيعه", "ذاتيه", "bobine", "dipole rl"),
        prerequisites=("rc_circuit",),
        difficulty=0.6,
        bac_frequency=0.55,
    ),
    _c(
        concept_id="rlc_circuit",
        title_ar="الدارة RLC",
        title_fr="Circuit RLC",
        subject="physics",
        markers=("داره rlc", "rlc", "تذبذب", "الدور الخاص", "oscillation"),
        prerequisites=("rl_circuit",),
        difficulty=0.7,
        bac_frequency=0.45,
    ),
    _c(
        concept_id="mechanics_newton",
        title_ar="قوانين نيوتن والحركة",
        title_fr="Lois de Newton et mouvement",
        subject="physics",
        markers=("نيوتن", "قوانين نيوتن", "حركه", "تسارع", "newton", "mouvement", "acceleration"),
        difficulty=0.6,
        bac_frequency=0.85,
    ),
    _c(
        concept_id="projectile_motion",
        title_ar="حركة المقذوفات",
        title_fr="Mouvement des projectiles",
        subject="physics",
        markers=("مقذوف", "المقذوفات", "قذيفه", "projectile", "chute libre", "سقوط حر"),
        prerequisites=("mechanics_newton",),
        difficulty=0.65,
        bac_frequency=0.6,
    ),
    _c(
        concept_id="electric_field_motion",
        title_ar="الحركة في حقل كهربائي",
        title_fr="Mouvement dans un champ électrique",
        subject="physics",
        markers=("حقل كهربايي", "champ electrique", "انحراف الجسيمات"),
        prerequisites=("mechanics_newton",),
        difficulty=0.7,
        bac_frequency=0.4,
    ),
    _c(
        concept_id="nuclear_decay",
        title_ar="التناقص الإشعاعي",
        title_fr="Décroissance radioactive",
        subject="physics",
        markers=("تناقص اشعاعي", "نشاط اشعاعي", "زمن نصف العمر", "radioactivite", "decroissance"),
        difficulty=0.55,
        bac_frequency=0.75,
    ),
    _c(
        concept_id="nuclear_transformations",
        title_ar="التحولات النووية والطاقة",
        title_fr="Transformations nucléaires et énergie",
        subject="physics",
        markers=("تحول نووي", "التحولات النوويه", "طاقه الربط", "انشطار", "اندماج", "fission"),
        prerequisites=("nuclear_decay",),
        difficulty=0.65,
        bac_frequency=0.6,
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# علوم الطبيعة والحياة — معاملها ٦ في العلوم التجريبية، وكانت غائبة تماماً
# ─────────────────────────────────────────────────────────────────────────────

_NATURAL_SCIENCES: Final[tuple[CurriculumConcept, ...]] = (
    _c(
        concept_id="protein_synthesis",
        title_ar="تركيب البروتين",
        title_fr="Synthèse des protéines",
        subject="natural_sciences",
        markers=("تركيب البروتين", "استنساخ", "ترجمه", "arn", "adn", "الحمض النووي", "بروتين"),
        difficulty=0.6,
        bac_frequency=0.85,
        streams=("experimental_sciences",),
    ),
    _c(
        concept_id="enzymatic_activity",
        title_ar="النشاط الإنزيمي",
        title_fr="Activité enzymatique",
        subject="natural_sciences",
        markers=("انزيم", "الانزيم", "النشاط الانزيمي", "enzyme", "التخصص الوظيفي"),
        prerequisites=("protein_synthesis",),
        difficulty=0.6,
        bac_frequency=0.7,
        streams=("experimental_sciences",),
    ),
    _c(
        concept_id="immunology",
        title_ar="المناعة",
        title_fr="Immunologie",
        subject="natural_sciences",
        markers=("مناعه", "المناعه", "مستضد", "جسم مضاد", "لمفاويه", "immunit", "anticorps"),
        prerequisites=("protein_synthesis",),
        difficulty=0.65,
        bac_frequency=0.9,
        streams=("experimental_sciences",),
    ),
    _c(
        concept_id="energy_metabolism",
        title_ar="استقلاب الطاقة",
        title_fr="Métabolisme énergétique",
        subject="natural_sciences",
        markers=(
            "التنفس الخلوي",
            "التخمر",
            "atp",
            "الميتوكوندري",
            "استقلاب",
            "respiration cellulaire",
        ),
        difficulty=0.65,
        bac_frequency=0.75,
        streams=("experimental_sciences",),
    ),
    _c(
        concept_id="geodynamics",
        title_ar="الجيولوجيا والظواهر الجيولوجية",
        title_fr="Géodynamique",
        subject="natural_sciences",
        markers=("جيولوجيا", "الصفايح", "زلزال", "البنيه الداخليه", "tectonique", "subduction"),
        difficulty=0.6,
        bac_frequency=0.7,
        streams=("experimental_sciences",),
    ),
)


CURRICULUM_REGISTRY: Final[tuple[CurriculumConcept, ...]] = (
    _MATHEMATICS + _PHYSICS + _NATURAL_SCIENCES
)


# ─────────────────────────────────────────────────────────────────────────────
# الفهارس المُشتقّة (تُبنى مرّة واحدة وقت الاستيراد)
# ─────────────────────────────────────────────────────────────────────────────

_BY_ID: Final[Mapping[str, CurriculumConcept]] = MappingProxyType(
    {item.concept_id: item for item in CURRICULUM_REGISTRY}
)

_ALIAS_TO_ID: Final[Mapping[str, str]] = MappingProxyType(
    {alias: item.concept_id for item in CURRICULUM_REGISTRY for alias in item.aliases}
)


def _build_marker_index() -> tuple[tuple[str, str], ...]:
    """يرتّب علامات الكشف: الأولوية المُصرَّحة أوّلاً، ثمّ الطول — الأخصّ يفوز.

    («احتمال شرطي» يجب أن تسبق «احتمال»، وإلّا ابتلع العامُّ الخاصَّ — وهو العطب الذي
    كان ترتيبُ القائمة اليدوي في `_CONCEPT_PATTERNS` يمنعه بالحظّ لا بالبناء.)
    """
    ranked = sorted(
        (-item.specificity, -len(marker), marker, item.concept_id)
        for item in CURRICULUM_REGISTRY
        for marker in item.markers
    )
    return tuple((marker, concept_id) for _, _, marker, concept_id in ranked)


_MARKER_INDEX: Final[tuple[tuple[str, str], ...]] = _build_marker_index()

_LEADS_TO: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        item.concept_id: tuple(
            other.concept_id
            for other in CURRICULUM_REGISTRY
            if item.concept_id in other.prerequisites
        )
        for item in CURRICULUM_REGISTRY
    }
)


# ─────────────────────────────────────────────────────────────────────────────
# السطح العامّ
# ─────────────────────────────────────────────────────────────────────────────


def resolve_alias(concept_id: str) -> str:
    """يُحوِّل مُعرَّفاً قديماً (`conditional_prob`) إلى المُعرَّف القانوني، أو يُعيده كما هو."""
    return _ALIAS_TO_ID.get(concept_id, concept_id)


def concept(concept_id: str) -> CurriculumConcept:
    """يُرجِع المفهوم، أو يرفع `CurriculumError` — لا صمت ولا افتراضي مضلِّل."""
    resolved = resolve_alias(concept_id)
    try:
        return _BY_ID[resolved]
    except KeyError:
        raise CurriculumError(f"unknown concept_id: {concept_id!r}") from None


def label(concept_id: str) -> str:
    """تسمية عربية للعرض؛ تتحمّل المجهول لأنها تخدم واجهةً لا قراراً."""
    try:
        return concept(concept_id).title_ar
    except CurriculumError:
        return concept_id or "المفهوم"


def _strip_articles(haystack: str) -> str:
    """
    يحذف أداة التعريف «ال» من بداية كلّ كلمة.

    **صنفُ عطبٍ متكرّر ثلاث مرّات** (ISS-109 · ISS-112 · ISS-114): علامة من كلمتين مثل
    «احتمال شرط» لا تُطابِق «الاحتمال الشرطي» أبداً، لأنّ أداة التعريف تفصل بينهما.
    كلّ إصلاحٍ سابق أضاف الصيغة المُعرَّفة يدوياً إلى القائمة التي أخطأت — فشُفي العَرَض
    وبقي الصنف. هذا يقتل الصنف: صورةٌ ثانية من النصّ بلا أدوات تعريف، تُجرَّب مع الأولى.

    حدّ الطول ٤ يحمي الكلمات التي «ال» جزءٌ أصيل منها (الله · الان).
    """
    return " ".join(
        token[2:] if token.startswith("ال") and len(token) > 4 else token
        for token in haystack.split(" ")
    )


def classify(text: str) -> str | None:
    """
    يُصنِّف نصّاً إلى مُعرَّف مفهوم قانوني، أو `None` إن لم يُطابِق شيئاً.

    `None` **وليس** `"general"`: «عام» مُعرَّفٌ كاذب كان يُخزَّن في
    `student_bkt_analytics` فيُلوِّث تاريخ الطالب بصفوف لا تعني شيئاً. الغياب يُعبَّر عنه
    بالغياب (§0: «المجهول أفضل من يقين زائف»).

    الأخصّ يفوز: تُجرَّب العلامات من الأطول إلى الأقصر **عبر الصورتين معاً**، فلا تسبق
    علامةٌ قصيرة في الصورة الأولى علامةً أطول في الصورة الثانية.
    """
    if not text:
        return None
    haystack = normalize(text)
    if not haystack:
        return None
    stripped = _strip_articles(haystack)
    for marker, concept_id in _MARKER_INDEX:
        if marker in haystack or marker in stripped:
            return concept_id
    return None


def prerequisites_of(concept_id: str) -> tuple[str, ...]:
    """المتطلّبات المباشرة."""
    return concept(concept_id).prerequisites


def next_concepts(concept_id: str) -> tuple[str, ...]:
    """المفاهيم التي يفتحها هذا المفهوم (مُشتقّة من `prerequisites`، لا مُعلَنة مرّتين)."""
    return _LEADS_TO[concept(concept_id).concept_id]


def subject_coefficient(subject: str, stream: str) -> int:
    """معامل المادة في الشعبة. يرفع على شعبةٍ مجهولة."""
    try:
        by_subject = STREAM_COEFFICIENTS[stream]
    except KeyError:
        raise CurriculumError(f"unknown stream: {stream!r}") from None
    if subject not in CANONICAL_SUBJECTS:
        raise CurriculumError(f"unknown subject: {subject!r}")
    return by_subject.get(subject, 0)


def exam_weight(concept_id: str, stream: str) -> float:
    """
    وزن المفهوم في امتحان شعبةٍ ما = المعامل × تواتر الظهور.

    هذا هو الرقم الذي يجب أن يرتّب المراجعة: مفهومٌ متواتر في مادة عالية المعامل يسبق
    مفهوماً نادراً في مادة منخفضة. يُرجِع ٠ إذا كانت الشعبة لا تدرس المفهوم أصلاً.
    """
    item = concept(concept_id)
    if stream not in CANONICAL_STREAMS:
        raise CurriculumError(f"unknown stream: {stream!r}")
    if stream not in item.streams:
        return 0.0
    return subject_coefficient(item.subject, stream) * item.bac_frequency


# ─────────────────────────────────────────────────────────────────────────────
# طبقة إشارة المادة (D-266 · ISS-159)
# ─────────────────────────────────────────────────────────────────────────────
#
# **لماذا طبقةٌ ثانية فوق `classify`؟** لأنّ `classify` تُجيب عن سؤالٍ آخر: «أيّ **وحدة
# منهاج** هذه؟» — ومُعرَّفاتها عقدٌ دائم مع `student_bkt_analytics` (D-193)، فلا تُوسَّع
# لكل مفردةٍ من مفردات المادة.
#
# والسؤال الذي كسر النظام في ISS-159 مختلف: «هل هذا السؤال **من مادةٍ غير الرياضيات**؟»
# — وقياسُه أثبت أنّ `classify("اشرح لي قانون أوم") is None`، وكذلك أرخميدس والتناضح
# الخلوي، لأنّ أيّاً منها ليس **وحدةَ** منهاج قائمة بذاتها. فكان الحارس في ستّة مواضع
# مكتوباً `_canonical is not None and ... != "probability"` فيسقط عند ساقه الأولى
# **فلا يعمل أصلاً**، ويمضي سؤال الفيزياء إلى العقل الاحتمالي.
#
# ⛔ **وموطن هذه المفردات هنا لا في `app/`**: قائمةُ مواضيع ثانية في مسار الدور هي
# بالضبط ما وُلد منه ISS-139 (ثلاث قوائم لنيّةٍ واحدة لا تتّفق أيّ اثنتين). المفردة
# تُعلَن مرّةً، ويقرأها الجميع.
#
# المطابقة على **حدود الكلمات** بعد التطبيع وحذف أدوات التعريف: «شعاع» يجب ألّا تختبئ
# داخل «الإشعاعي» (D-193)، و«جهد» ألّا تختبئ داخل «مجهود».
SUBJECT_MARKERS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "physics": (
            # اسم المادة نفسه — أقوى إشارةٍ ممكنة، وكان غيابها عطباً مقيساً:
            # «ما معنى الرمز Ω **في الفيزياء**» بقيت `None` فتلقّى الطالب فضاء العيّنة.
            # من يسمّي مادته لا يحتاج إلى أن نستنتجها من مفرداتها.
            "فيزياء",
            "physique",
            "physics",
            "كيمياء",
            "chimie",
            "chemistry",
            # كهرباء
            "اوم",
            "ohm",
            "جهد",
            "توتر",
            "تيار",
            "مقاومه",
            "ناقل اومي",
            "شده التيار",
            "دارة كهربائيه",
            "مكثفه",
            "وشيعه",
            "فولط",
            "امبير",
            "volt",
            "ampere",
            # ميكانيك
            "ارخميدس",
            "archimede",
            "archimedes",
            "دافعه",
            "نيوتن",
            "newton",
            "جاذبيه",
            "ثقل",
            "سرعه",
            "تسارع",
            "قذيفه",
            "كتله",
            "قوه",
            "طاقه حركيه",
            "طاقه كامنه",
            "شغل",
            "عزم",
            "احتكاك",
            # كيمياء / نووي
            "تفاعل كيميائي",
            "حمض",
            "اساس",
            "ph",
            "معايره",
            "تركيز موليّ",
            "مول",
            "نشاط اشعاعي",
            "نظير",
            "نواه",
            "اندماج",
            "انشطار",
        ),
        "natural_sciences": (
            # اسم المادة نفسه (انظر تعليق الفيزياء أعلاه).
            "علوم الطبيعه",
            "علوم طبيعيه",
            "علوم الحياه",
            "بيولوجيا",
            "biologie",
            "biology",
            "svt",
            "جيولوجيا",
            "geologie",
            "تناضح",
            "osmose",
            "osmosis",
            "خليه",
            "غشاء",
            "بروتين",
            "انزيم",
            "مناعه",
            "جسم مضاد",
            "مستضد",
            "لمفاويه",
            "adn",
            "arn",
            "حمض نووي",
            "استنساخ",
            "ترجمه",
            "ايض",
            "تنفس خلوي",
            "تخمر",
            "ضوئي",
            "صفيحه",
            "زلزال",
            "بركان",
            "صخره",
        ),
    }
)


#: `SUBJECT_MARKERS` مُطبَّعةً **عند الاستيراد**، لا اعتماداً على انضباط الكاتب.
#:
#: علاماتُ `CurriculumConcept.markers` عقدُها «مُطبَّعة مسبقاً»، وهو عقدٌ يُخالَف بصمت:
#: «فيزياء» تُطبَّع إلى «فيزيا» (تحذف `normalize` الهمزة)، فعلامةٌ مكتوبة بالهمزة **لا
#: تطابق شيئاً أبداً** — وهو ما حدث فعلاً في أوّل تشغيلٍ لهذه الطبقة: «ما معنى الرمز Ω
#: في الفيزياء» بقيت `None` فتلقّى الطالب شرح فضاء العيّنة. الاشتقاق هنا يجعل الخطأ
#: **غير مُمثَّل** بدل أن يكون مُنضبَطاً به.
_SUBJECT_MARKER_INDEX: Final[tuple[tuple[str, str], ...]] = tuple(
    sorted(
        (
            (normalize(marker), subject)
            for subject, markers in SUBJECT_MARKERS.items()
            for marker in markers
            if normalize(marker)
        ),
        key=lambda pair: (-len(pair[0]), pair[0]),
    )
)


def _word_markers(text: str) -> set[str]:
    """كلمات النصّ مُطبَّعةً وبلا أدوات تعريف — الوحدة التي تُطابَق عليها إشارة المادة."""
    haystack = normalize(text or "")
    if not haystack:
        return set()
    words = set(haystack.split(" "))
    words |= set(_strip_articles(haystack).split(" "))
    return {word for word in words if word}


def classify_subject(text: str) -> str | None:
    """
    يُرجِع مادة السؤال (`mathematics` · `physics` · `natural_sciences`) أو `None`.

    الترتيب مقصود: **المفهوم أوّلاً** (الأخصّ يفوز — نفس قانون `classify`)، ثمّ مفردات
    المادة. فسؤالٌ يذكر «التناقص الإشعاعي» يُحسَم بوحدته لا بمفردةٍ عابرة.

    `None` **وليس** `"general"`: الغياب يُعبَّر عنه بالغياب (§0) — ومن يقرأ `None` هنا
    يقرأ «لم أتعرّف»، لا «رياضيات».
    """
    concept_id = classify(text)
    if concept_id is not None:
        return _BY_ID[concept_id].subject

    return _match_subject_marker(text)


def _marker_hits(marker: str, haystack: str, stripped: str, words: set[str]) -> bool:
    """هل تُطابِق هذه العلامة النصَّ؟ — عبارةٌ للمركَّبة، وحدُّ كلمةٍ للمفردة.

    المفردة تُطابَق على **حدود الكلمة** وإلّا اختبأت «شعاع» داخل «الإشعاعي» و«جهد»
    داخل «مجهود» — صنفُ عطبٍ حرسه D-193 صراحةً.
    """
    if " " in marker:
        return marker in haystack or marker in stripped
    return marker in words


def _match_subject_marker(text: str) -> str | None:
    """أوّل مادةٍ تُطابِق مفرداتها — الأطول يفوز (الأخصّ)، كقانون `_MARKER_INDEX`."""
    words = _word_markers(text)
    if not words:
        return None
    haystack = normalize(text or "")
    stripped = _strip_articles(haystack)
    for marker, subject in _SUBJECT_MARKER_INDEX:
        if _marker_hits(marker, haystack, stripped, words):
            return subject
    return None


def concepts_for_stream(stream: str) -> tuple[CurriculumConcept, ...]:
    """كلّ مفاهيم شعبةٍ ما، مرتّبة بوزن الامتحان تنازلياً."""
    if stream not in CANONICAL_STREAMS:
        raise CurriculumError(f"unknown stream: {stream!r}")
    selected = [item for item in CURRICULUM_REGISTRY if stream in item.streams]
    return tuple(
        sorted(selected, key=lambda item: (-exam_weight(item.concept_id, stream), item.concept_id))
    )
