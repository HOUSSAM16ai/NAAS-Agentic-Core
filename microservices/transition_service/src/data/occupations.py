"""أطلس المهن والمهارات — بيانات تأسيسية رصينة علمياً.

هذا الملف هو **مصدر الحقيقة الوحيد** لمهن المنظومة ومهامها ومهاراتها. لا تُختلق أي
أرقام خارج هذا الملف: كل مؤشر تعرض أو تعزيز أو فجوة مهارات يُشتق حتمياً من البيانات
هنا أو من مخرجات المدخلات (requests) — المحرك اللغوي **يسرد الفهم ولا يقرر الحقيقة**
(مبدأ الأرقام الحتمية من دستور المشروع، مطابقاً لممارسة `probability_brain` في
المونوليث، ولفصل «القدرة النظرية» عن «الاستخدام المرصود» في
Anthropic, *Labor market impacts of AI: A new measure and early evidence*, 2026).

المرساة العلمية:
- تصنيف المهن والتوزيع الزمني للمهام مستوحى من بنية **O*NET** (~800 مهنة أمريكية،
  time-fraction measures) ومن **ILO Global Index of Occupational Exposure** (2025).
- مؤشر التعرض النظري للمهام (β ∈ {0, 0.5, 1}) مستنسخ لمعيار
  **Eloundou et al. (2023), *Science* «GPTs are GPTs»**.
- أوزان الاستخدام المرصود مستوحاة من **Anthropic Economic Index** (الاستخدام الآلي
  الكامل = وزن كامل، الاستخدام المعزز = نصف وزن) — فجوة «القدرة النظرية مقابل
  التغطية المرصودة» موثقة: الحاسوب والرياضيات 94% نظرياً مقابل 33% مرصوداً.
- إحصاءات سوق العمل التأسيسية (22% من الأدوار تتلاشى أو تتغير كلياً بحلول 2030،
  59% من القوى العاملة تحتاج إعادة تأهيل) من **WEF Future of Jobs Report 2025**.
"""

from __future__ import annotations

from dataclasses import dataclass

# β: 1 = الأتمتة ممكنة بنموذج لغوي وحده · 0.5 = يحتاج أدوات مبنية فوقه · 0 = غير ممكن
# source: Eloundou, Manning, Mishkin & Rock (2023), Science.
TASK_AUTO = "auto_full"  # β = 1 — أتمتة كاملة للمهمة
TASK_AUTO_TOOLS = "auto_tools"  # β = 0.5 — أتمتة بأدوات مبنية على LLM
TASK_AUGMENT = "augment"  # تعزيز بشري بالذكاء الاصطناعي (لا استبدال)
TASK_HUMAN = "human_only"  # مهام غير قابلة للاستبدال بسهولة (قيادة أخلاقية،
# تفاوض، رعاية إنسانية، إبداع مركب، عمل ميداني معقد)

# وزن الاستخدام المرصود (Anthropic Economic Index convention):
# الأتمتة الكاملة = 1.0 · المعزز = 0.5 · الإنساني = 0.0
OBSERVED_WEIGHT: dict[str, float] = {
    TASK_AUTO: 1.0,
    TASK_AUTO_TOOLS: 0.75,
    TASK_AUGMENT: 0.5,
    TASK_HUMAN: 0.0,
}


@dataclass(frozen=True)
class Task:
    """مهمة مهنية واحدة ضمن مهنة."""

    code: str
    label_ar: str
    label_en: str
    category: str  # auto_full | auto_tools | augment | human_only
    time_fraction: float  # حصة الوقت في المهنة (مجموع المهام ≈ 1.0)


@dataclass(frozen=True)
class Skill:
    """مهارة مدرجة في أطلس المهارات."""

    code: str
    label_ar: str
    label_en: str
    kind: str  # digital | domain | human | governance


@dataclass(frozen=True)
class Occupation:
    """مهنة كاملة: مهام + مهارات حالية + مهارات مستقبلية + مجاورات انتقال."""

    code: str
    label_ar: str
    label_en: str
    sector: str
    tasks: tuple[Task, ...]
    current_skills: tuple[str, ...]  # أكواد Skill
    future_skills: tuple[str, ...]  # المهارات التي سيطلبها السوق خلال ~3 سنوات
    adjacent_occupations: tuple[str, ...]  # أكواد مهن قريبة للانتقال
    demand_signal: float = 0.0  # مؤشر اتجاه الطلب: -1 تراجع حاد … +1 نمو حاد
    wage_reference: float = 0.0  # مرجع أجر نسبي (1.0 = متوسط السوق)
    demographics_notes: str = ""  # ملاحظات توزّع (جنس/عمر/منطقة) لتقارير العدالة


@dataclass
class TrainingUnit:
    """وحدة تدريب قصيرة (microcredential) — وثيقة المشروع §5.6: شهادات قصيرة متراكمة.

    تصميمها يقابل معيار DigComp 3.0 ووثيقة WEF 2025 (محو الأمية الذكية أولوية)
    ووثيقة المشروع §9.4 (تأهيل المعلم أولاً).
    """

    code: str
    label_ar: str
    duration_weeks: int
    skills: tuple[str, ...]
    target_occupations: tuple[str, ...]
    level: str  # foundational | intermediate | advanced

    @classmethod
    def all(cls) -> dict[str, TrainingUnit]:
        return {
            code: cls(
                code=entry["code"],
                label_ar=entry["label_ar"],
                duration_weeks=entry["duration_weeks"],
                skills=entry["skills"],
                target_occupations=entry["target_occupations"],
                level=entry["level"],
            )
            for code, entry in TRAINING_UNITS.items()
        }


SKILLS: dict[str, Skill] = {
    "s_data_entry": Skill("s_data_entry", "إدخال البيانات", "Data entry", "domain"),
    "s_doc_sort": Skill("s_doc_sort", "فرز وتصنيف المستندات", "Document sorting", "domain"),
    "s_ai_tools": Skill(
        "s_ai_tools", "تشغيل أدوات الذكاء الاصطناعي", "Operating AI tools", "digital"
    ),
    "s_ai_prompt": Skill("s_ai_prompt", "هندسة الحوار مع النماذج", "Prompt engineering", "digital"),
    "s_responsible_ai": Skill(
        "s_responsible_ai", "الاستخدام المسؤول للذكاء الاصطناعي", "Responsible AI use", "governance"
    ),
    "s_ai_lit": Skill("s_ai_lit", "محو الأمية الذكية", "AI literacy", "digital"),
    "s_data_analytics": Skill("s_data_analytics", "تحليل البيانات", "Data analytics", "digital"),
    "s_data_quality": Skill(
        "s_data_quality", "ضمان جودة البيانات", "Data quality assurance", "digital"
    ),
    "s_bi": Skill("s_bi", "ذكاء الأعمال", "Business intelligence", "digital"),
    "s_process_automation": Skill(
        "s_process_automation", "أتمتة العمليات", "Process automation", "digital"
    ),
    "s_ops_coord": Skill("s_ops_coord", "تنسيق العمليات", "Operations coordination", "domain"),
    "s_qa": Skill("s_qa", "إدارة الجودة", "Quality management", "domain"),
    "s_cx": Skill("s_cx", "إدارة تجربة العملاء", "Customer experience management", "domain"),
    "s_care_basic": Skill(
        "s_care_basic", "خدمة العملاء الأساسية", "Basic customer service", "domain"
    ),
    "s_care_advanced": Skill(
        "s_care_advanced",
        "خدمة عملاء متقدمة ومعالجة شكاوى",
        "Advanced CX & complaint handling",
        "domain",
    ),
    "s_emotional_comm": Skill(
        "s_emotional_comm", "التواصل العاطفي", "Emotional communication", "human"
    ),
    "s_negotiation": Skill("s_negotiation", "التفاوض", "Negotiation", "human"),
    "s_critical_thinking": Skill(
        "s_critical_thinking", "التفكير النقدي", "Critical thinking", "human"
    ),
    "s_creative_composite": Skill(
        "s_creative_composite", "الإبداع المركب", "Composite creativity", "human"
    ),
    "s_ethical_leadership": Skill(
        "s_ethical_leadership", "القيادة الأخلاقية", "Ethical leadership", "human"
    ),
    "s_fieldwork_complex": Skill(
        "s_fieldwork_complex", "العمل الميداني المعقد", "Complex fieldwork", "human"
    ),
    "s_clinical_judgment": Skill(
        "s_clinical_judgment", "الحكم السريري", "Clinical judgment", "human"
    ),
    "s_privacy_security": Skill(
        "s_privacy_security", "الخصوصية وأمن البيانات", "Privacy & data security", "governance"
    ),
    "s_digital_systems": Skill(
        "s_digital_systems", "إدارة الأنظمة الرقمية", "Digital systems administration", "digital"
    ),
    "s_support_systems": Skill(
        "s_support_systems", "دعم الأنظمة التقنية", "Technical systems support", "digital"
    ),
    "s_hr_digital": Skill("s_hr_digital", "الموارد البشرية الرقمية", "Digital HR", "domain"),
    "s_green_tech": Skill("s_green_tech", "التقنيات الخضراء", "Green technologies", "digital"),
    "s_care_economy": Skill(
        "s_care_economy", "اقتصاد الرعاية المدعوم بالتقنية", "Tech-assisted care economy", "domain"
    ),
    "s_sme_digital": Skill(
        "s_sme_digital", "رقمنة المنشآت الصغيرة", "SME digitalization", "digital"
    ),
    "s_freelance_org": Skill(
        "s_freelance_org", "العمل الحر المنظم", "Organized freelancing", "domain"
    ),
    "s_teaching": Skill(
        "s_teaching", "التدريس وإدارة الصف", "Teaching & classroom management", "human"
    ),
    "s_curriculum_design": Skill(
        "s_curriculum_design", "تصميم المناهج", "Curriculum design", "domain"
    ),
    "s_teacher_training": Skill(
        "s_teacher_training", "تدريب المعلمين", "Teacher training", "domain"
    ),
    "s_assessment_design": Skill(
        "s_assessment_design", "تصميم التقييم", "Assessment design", "domain"
    ),
    "s_microcredential": Skill(
        "s_microcredential", "الشهادات القصيرة واعتماداتها", "Microcredentials", "domain"
    ),
    "s_policy_analysis": Skill("s_policy_analysis", "تحليل السياسات", "Policy analysis", "domain"),
    "s_simulation": Skill(
        "s_simulation", "المحاكاة والتحليل البديل", "Simulation & scenario analysis", "domain"
    ),
    "s_compliance": Skill(
        "s_compliance", "الامتثال والتدقيق", "Compliance & auditing", "governance"
    ),
    "s_algorithm_audit": Skill(
        "s_algorithm_audit", "تدقيق الخوارزميات", "Algorithm auditing", "governance"
    ),
    "s_social_dialogue": Skill("s_social_dialogue", "الحوار الاجتماعي", "Social dialogue", "human"),
    "s_monitoring_eval": Skill(
        "s_monitoring_eval", "التقييم والمساءلة", "Monitoring & evaluation", "domain"
    ),
    "s_health_assistant": Skill(
        "s_health_assistant", "المساندة الصحية", "Health assistance", "domain"
    ),
    "s_renewable": Skill("s_renewable", "الطاقة المتجددة", "Renewable energy", "digital"),
    "s_ai_ml_spec": Skill(
        "s_ai_ml_spec", "تخصص الذكاء الاصطناعي وتعلم الآلة", "AI & ML specialization", "digital"
    ),
    "s_software_dev": Skill("s_software_dev", "تطوير البرمجيات", "Software development", "digital"),
    "s_cybersecurity": Skill("s_cybersecurity", "الأمن السيبراني", "Cybersecurity", "digital"),
    "s_bigdata": Skill("s_bigdata", "البيانات الضخمة", "Big data", "digital"),
}


def _t(code: str, label_ar: str, label_en: str, category: str, frac: float) -> Task:
    return Task(code, label_ar, label_en, category, frac)


# ── الأطلس المهني (مهن حقيقية مستهدفة من وثيقة المشروع) ───────────────────────
# التوزيع الزمني للمهام مصمم ليعكس الأدلة: المهن الكتابية الرتيبة ≈ 40% أتمتة
# كاملة (يصلها مؤشر WEF 2025: 22% من الأدوار تتلاشى/تتغير كلياً)، بينما المهن
# الإنسانية والميدانية تبقى غالبية مهامها human_only (Eloundou β = 0).

OCCUPATIONS: dict[str, Occupation] = {
    "o_data_entry": Occupation(
        code="o_data_entry",
        label_ar="مُدخل بيانات",
        label_en="Data Entry Keyer",
        sector="services",
        tasks=(
            _t(
                "t1",
                "قراءة المستندات المصدر وإدخال البيانات",
                "Read source documents and enter data",
                TASK_AUTO,
                0.55,
            ),
            _t("t2", "التحقق من صحة المدخلات", "Input validation", TASK_AUTO_TOOLS, 0.2),
            _t("t3", "تنسيق التقارير البسيطة", "Simple report formatting", TASK_AUGMENT, 0.15),
            _t(
                "t4", "التنسيق مع المشرفين حول الشواذ", "Coordination on anomalies", TASK_HUMAN, 0.1
            ),
        ),
        current_skills=("s_data_entry", "s_doc_sort"),
        future_skills=("s_data_quality", "s_ai_tools", "s_data_analytics", "s_privacy_security"),
        adjacent_occupations=("o_data_quality", "o_ops_analyst", "o_system_support"),
        demand_signal=-0.8,
        wage_reference=0.6,
        demographics_notes="تركّز تاريخي لدى النساء والفئات متوسطة الدخل في المدن",
    ),
    "o_admin_support": Occupation(
        code="o_admin_support",
        label_ar="دعم إداري روتيني",
        label_en="Routine Administrative Support",
        sector="services",
        tasks=(
            _t(
                "t1",
                "جدولة المواعيد والمراسلات النمطية",
                "Routine scheduling & correspondence",
                TASK_AUTO,
                0.45,
            ),
            _t(
                "t2",
                "إعداد الاجتماعات والمحاضر",
                "Meeting preparation & minutes",
                TASK_AUTO_TOOLS,
                0.25,
            ),
            _t("t3", "إدارة ملفات المنظمة", "Records & file management", TASK_AUGMENT, 0.15),
            _t(
                "t4",
                "التنسيق البشري بين الأقسام",
                "Human inter-department coordination",
                TASK_HUMAN,
                0.15,
            ),
        ),
        current_skills=("s_doc_sort", "s_ops_coord"),
        future_skills=("s_process_automation", "s_ops_coord", "s_ai_tools", "s_qa"),
        adjacent_occupations=("o_ops_analyst", "o_hr_digital", "o_cx_advanced"),
        demand_signal=-0.6,
        wage_reference=0.7,
        demographics_notes="غالبية نسائية؛ فجوة العمر أكبر لدى 45+",
    ),
    "o_cx_basic": Occupation(
        code="o_cx_basic",
        label_ar="خدمة عملاء نصية بسيطة",
        label_en="Basic Text-based Customer Service",
        sector="services",
        tasks=(
            _t(
                "t1",
                "الرد على الاستفسارات المتكررة نصياً",
                "Repetitive text inquiries",
                TASK_AUTO,
                0.5,
            ),
            _t("t2", "توجيه الطلبات بين الأنظمة", "Ticket routing", TASK_AUTO_TOOLS, 0.2),
            _t("t3", "معالجة شكاوى غير نمطية", "Non-routine complaint handling", TASK_AUGMENT, 0.2),
            _t("t4", "التعاطف وإدارة الغضب", "Empathy & de-escalation", TASK_HUMAN, 0.1),
        ),
        current_skills=("s_care_basic", "s_doc_sort"),
        future_skills=("s_care_advanced", "s_emotional_comm", "s_ai_tools", "s_data_analytics"),
        adjacent_occupations=("o_cx_advanced", "o_data_quality", "o_care_assistant"),
        demand_signal=-0.4,
        wage_reference=0.65,
        demographics_notes="الشباب 18–29 أعلى تمثيلاً؛ أول من يظهر فيه تباطؤ التوظيف",
    ),
    "o_data_quality": Occupation(
        code="o_data_quality",
        label_ar="أخصائي جودة بيانات",
        label_en="Data Quality Specialist",
        sector="data",
        tasks=(
            _t("t1", "فحص جودة مجموعات البيانات", "Dataset quality inspection", TASK_AUGMENT, 0.3),
            _t(
                "t2",
                "تحديد وإصلاح الشواذ بالأنظمة الذكية",
                "AI-assisted anomaly resolution",
                TASK_AUGMENT,
                0.3,
            ),
            _t(
                "t3",
                "تصميم قواعد الجودة والسياسات",
                "Quality rules & policy design",
                TASK_HUMAN,
                0.25,
            ),
            _t("t4", "التنسيق مع فرق الأعمال", "Business team coordination", TASK_HUMAN, 0.15),
        ),
        current_skills=("s_data_quality", "s_data_analytics"),
        future_skills=("s_data_quality", "s_ai_tools", "s_privacy_security", "s_compliance"),
        adjacent_occupations=("o_ops_analyst", "o_bi_analyst", "o_compliance"),
        demand_signal=0.7,
        wage_reference=1.0,
    ),
    "o_ops_analyst": Occupation(
        code="o_ops_analyst",
        label_ar="محلل عمليات رقمية",
        label_en="Digital Operations Analyst",
        sector="data",
        tasks=(
            _t("t1", "تحليل بيانات العمليات", "Operations data analysis", TASK_AUGMENT, 0.35),
            _t(
                "t2", "اقتراح تحسينات العمليات", "Process improvement proposals", TASK_AUGMENT, 0.25
            ),
            _t(
                "t3",
                "تفسير النتائج للقيادات",
                "Results interpretation for leadership",
                TASK_HUMAN,
                0.25,
            ),
            _t("t4", "مراقبة مؤشرات الأداء", "KPI monitoring", TASK_AUGMENT, 0.15),
        ),
        current_skills=("s_data_analytics", "s_ops_coord", "s_bi"),
        future_skills=("s_data_analytics", "s_process_automation", "s_critical_thinking"),
        adjacent_occupations=("o_bi_analyst", "o_data_quality", "o_policy_analysis"),
        demand_signal=0.6,
        wage_reference=1.1,
    ),
    "o_bi_analyst": Occupation(
        code="o_bi_analyst",
        label_ar="محلل ذكاء أعمال",
        label_en="Business Intelligence Analyst",
        sector="data",
        tasks=(
            _t("t1", "بناء لوحات المؤشرات", "Dashboard building", TASK_AUGMENT, 0.3),
            _t("t2", "نمذجة وتحليل الأعمال", "Business modeling & analysis", TASK_AUGMENT, 0.3),
            _t("t3", "تقديم توصيات قرار", "Decision recommendation", TASK_HUMAN, 0.25),
            _t("t4", "حوكمة البيانات", "Data governance", TASK_HUMAN, 0.15),
        ),
        current_skills=("s_bi", "s_data_analytics"),
        future_skills=("s_data_analytics", "s_ai_tools", "s_privacy_security"),
        adjacent_occupations=("o_ops_analyst", "o_policy_analysis"),
        demand_signal=0.65,
        wage_reference=1.2,
    ),
    "o_system_support": Occupation(
        code="o_system_support",
        label_ar="أخصائي دعم أنظمة",
        label_en="Systems Support Specialist",
        sector="data",
        tasks=(
            _t(
                "t1",
                "دعم المستخدمين وتشخيص الأعطال",
                "User support & troubleshooting",
                TASK_AUGMENT,
                0.35,
            ),
            _t("t2", "توثيق الحلول وقواعد المعرفة", "Solution documentation", TASK_AUTO_TOOLS, 0.2),
            _t("t3", "صيانة الأنظمة والوصوليات", "System maintenance & access", TASK_HUMAN, 0.25),
            _t("t4", "تدريب الزملاء على الأنظمة", "Colleague system training", TASK_HUMAN, 0.2),
        ),
        current_skills=("s_support_systems", "s_digital_systems"),
        future_skills=("s_support_systems", "s_ai_tools", "s_teaching"),
        adjacent_occupations=("o_ops_analyst", "o_hr_digital"),
        demand_signal=0.4,
        wage_reference=0.95,
    ),
    "o_hr_digital": Occupation(
        code="o_hr_digital",
        label_ar="مساعد موارد بشرية رقمي",
        label_en="Digital HR Assistant",
        sector="hr",
        tasks=(
            _t("t1", "فرز السير الذاتية النمطي", "Routine CV screening", TASK_AUTO, 0.3),
            _t("t2", "إدارة مسارات التوظيف", "Recruitment pipeline management", TASK_AUGMENT, 0.3),
            _t(
                "t3",
                "التواصل الإنساني مع المرشحين",
                "Human candidate communication",
                TASK_HUMAN,
                0.25,
            ),
            _t(
                "t4",
                "التدقيق في عدالة قرارات التوظيف",
                "Hiring fairness auditing",
                TASK_HUMAN,
                0.15,
            ),
        ),
        current_skills=("s_hr_digital", "s_ops_coord"),
        future_skills=("s_hr_digital", "s_compliance", "s_ai_tools", "s_algorithm_audit"),
        adjacent_occupations=("o_ops_analyst", "o_compliance"),
        demand_signal=0.35,
        wage_reference=0.95,
        demographics_notes="يجب مراقبة التمييز الخوارزمي في أدوات الفرز التي يستخدمها",
    ),
    "o_cx_advanced": Occupation(
        code="o_cx_advanced",
        label_ar="ممثل خدمة عملاء متقدم",
        label_en="Advanced Customer Experience Representative",
        sector="services",
        tasks=(
            _t("t1", "معالجة الشكاوى المعقدة", "Complex complaint resolution", TASK_HUMAN, 0.4),
            _t(
                "t2",
                "تحليل مشاعر العملاء واتجاهاتهم",
                "Customer sentiment analysis (AI-assisted)",
                TASK_AUGMENT,
                0.25,
            ),
            _t("t3", "التفاوض على التعويضات", "Compensation negotiation", TASK_HUMAN, 0.2),
            _t("t4", "إثراء قاعدة المعرفة", "Knowledge base enrichment", TASK_AUGMENT, 0.15),
        ),
        current_skills=("s_care_basic", "s_emotional_comm"),
        future_skills=("s_care_advanced", "s_data_analytics", "s_emotional_comm", "s_ai_tools"),
        adjacent_occupations=("o_data_quality", "o_care_assistant"),
        demand_signal=0.3,
        wage_reference=0.85,
    ),
    "o_care_assistant": Occupation(
        code="o_care_assistant",
        label_ar="مساعد رعاية مدعوم بالتقنية",
        label_en="Tech-Assisted Care Assistant",
        sector="care",
        tasks=(
            _t("t1", "الرعاية الإنسانية المباشرة", "Direct human care", TASK_HUMAN, 0.55),
            _t(
                "t2",
                "مراقبة المؤشرات الحيوية بالأجهزة الذكية",
                "Smart vital monitoring",
                TASK_AUGMENT,
                0.2,
            ),
            _t(
                "t3", "توثيق حالة المريض رقمياً", "Digital patient documentation", TASK_AUGMENT, 0.15
            ),
            _t("t4", "التنسيق مع الفريق الطبي", "Medical team coordination", TASK_HUMAN, 0.1),
        ),
        current_skills=("s_care_economy", "s_emotional_comm"),
        future_skills=(
            "s_care_economy",
            "s_digital_systems",
            "s_emotional_comm",
            "s_health_assistant",
        ),
        adjacent_occupations=("o_cx_advanced", "o_health_assistant"),
        demand_signal=0.8,
        wage_reference=0.8,
        demographics_notes="قطاع نمو رئيسي في تقارير WEF/ILO — نموذج «الفرص الجديدة»",
    ),
    "o_health_assistant": Occupation(
        code="o_health_assistant",
        label_ar="مساعد صحي",
        label_en="Health Assistant",
        sector="care",
        tasks=(
            _t(
                "t1",
                "المساندة السريرية تحت إشراف",
                "Supervised clinical assistance",
                TASK_HUMAN,
                0.5,
            ),
            _t(
                "t2",
                "تشغيل أدوات التشخيص المساندة",
                "Operating diagnostic support tools",
                TASK_AUGMENT,
                0.25,
            ),
            _t("t3", "توعية المرضى", "Patient education", TASK_HUMAN, 0.15),
            _t("t4", "إدارة السجلات الصحية", "Health records management", TASK_AUGMENT, 0.1),
        ),
        current_skills=("s_health_assistant", "s_emotional_comm"),
        future_skills=("s_health_assistant", "s_digital_systems", "s_emotional_comm"),
        adjacent_occupations=("o_care_assistant"),
        demand_signal=0.75,
        wage_reference=0.9,
    ),
    "o_ai_ml_spec": Occupation(
        code="o_ai_ml_spec",
        label_ar="متخصص ذكاء اصطناعي وتعلم آلي",
        label_en="AI & Machine Learning Specialist",
        sector="data",
        tasks=(
            _t("t1", "تطوير النماذج وتحسينها", "Model development & tuning", TASK_AUGMENT, 0.4),
            _t("t2", "هندسة البيانات ومعالجتها", "Data engineering", TASK_AUGMENT, 0.25),
            _t("t3", "ترجمة احتياجات الأعمال", "Business needs translation", TASK_HUMAN, 0.2),
            _t("t4", "مراجعة أخلاقيات النماذج", "Model ethics review", TASK_HUMAN, 0.15),
        ),
        current_skills=("s_ai_ml_spec", "s_bigdata"),
        future_skills=("s_ai_ml_spec", "s_responsible_ai", "s_algorithm_audit"),
        adjacent_occupations=("o_bi_analyst", "o_data_quality"),
        demand_signal=0.9,
        wage_reference=1.8,
        demographics_notes="من أكثر الأدوار نمواً عالمياً (WEF 2025)؛ فجوة مهارات حادة",
    ),
    "o_software_dev": Occupation(
        code="o_software_dev",
        label_ar="مطوّر برمجيات",
        label_en="Software Developer",
        sector="data",
        tasks=(
            _t("t1", "كتابة الكود النمطي", "Routine coding", TASK_AUTO_TOOLS, 0.3),
            _t("t2", "تصميم البنى المعمارية", "Architecture design", TASK_AUGMENT, 0.3),
            _t("t3", "فهم المتطلبات والتفاوض عليها", "Requirements negotiation", TASK_HUMAN, 0.25),
            _t(
                "t4",
                "مراجعة الكود واتخاذ القرار الهندسي",
                "Code review & engineering judgment",
                TASK_HUMAN,
                0.15,
            ),
        ),
        current_skills=("s_software_dev", "s_critical_thinking"),
        future_skills=("s_software_dev", "s_ai_tools", "s_process_automation"),
        adjacent_occupations=("o_ai_ml_spec", "o_ops_analyst"),
        demand_signal=0.5,
        wage_reference=1.6,
        demographics_notes="أعلى تغطية استخدام مرصود عالمياً (75% — Anthropic 2026)",
    ),
    "o_teacher": Occupation(
        code="o_teacher",
        label_ar="معلم",
        label_en="Teacher",
        sector="education",
        tasks=(
            _t("t1", "تصحيح الواجبات النمطي", "Routine grading", TASK_AUTO_TOOLS, 0.2),
            _t(
                "t2", "إعداد المواد والدروس", "Lesson preparation (AI-assisted)", TASK_AUGMENT, 0.25
            ),
            _t(
                "t3",
                "إدارة الصف والتوجيه الإنساني",
                "Classroom management & mentorship",
                TASK_HUMAN,
                0.35,
            ),
            _t(
                "t4",
                "تقييم التعلم العميق والمشاريع",
                "Deep-learning & project assessment",
                TASK_HUMAN,
                0.2,
            ),
        ),
        current_skills=("s_teaching", "s_curriculum_design"),
        future_skills=("s_teaching", "s_ai_lit", "s_assessment_design", "s_teacher_training"),
        adjacent_occupations=("o_curriculum_specialist", "o_teacher_trainer"),
        demand_signal=0.2,
        wage_reference=0.9,
        demographics_notes="المعلم يحتاج أولاً (وثيقة المشروع §9.5) — بدون معلم مؤهل لا يُحدَّث التعليم",
    ),
    "o_teacher_trainer": Occupation(
        code="o_teacher_trainer",
        label_ar="مدرب معلمين",
        label_en="Teacher Trainer",
        sector="education",
        tasks=(
            _t(
                "t1",
                "تدريب المعلمين على الأدوات الذكية",
                "AI tools training for teachers",
                TASK_AUGMENT,
                0.35,
            ),
            _t(
                "t2", "تصميم أدلة الاستخدام الأخلاقي", "Ethical usage guide design", TASK_HUMAN, 0.3
            ),
            _t("t3", "تقييم أثر الأدوات على التعلم", "Tool impact evaluation", TASK_AUGMENT, 0.2),
            _t("t4", "الدعم الميداني للمعلمين", "In-class mentorship", TASK_HUMAN, 0.15),
        ),
        current_skills=("s_teacher_training", "s_teaching", "s_ai_lit"),
        future_skills=("s_teacher_training", "s_ai_lit", "s_monitoring_eval"),
        adjacent_occupations=("o_teacher", "o_curriculum_specialist"),
        demand_signal=0.55,
        wage_reference=1.0,
    ),
    "o_curriculum_specialist": Occupation(
        code="o_curriculum_specialist",
        label_ar="أخصائي تطوير مناهج",
        label_en="Curriculum Development Specialist",
        sector="education",
        tasks=(
            _t(
                "t1",
                "تحليل الفجوة بين المنهج والسوق",
                "Curriculum–market gap analysis",
                TASK_AUGMENT,
                0.3,
            ),
            _t(
                "t2",
                "تصميم الوحدات القصيرة والشهادات",
                "Microcredential unit design",
                TASK_AUGMENT,
                0.3,
            ),
            _t("t3", "دمج محو الأمية الذكية", "AI literacy integration", TASK_HUMAN, 0.25),
            _t("t4", "التنسيق مع أصحاب العمل", "Employer engagement", TASK_HUMAN, 0.15),
        ),
        current_skills=("s_curriculum_design", "s_microcredential"),
        future_skills=("s_curriculum_design", "s_ai_lit", "s_data_analytics", "s_policy_analysis"),
        adjacent_occupations=("o_teacher_trainer", "o_policy_analysis"),
        demand_signal=0.6,
        wage_reference=1.05,
    ),
    "o_policy_analysis": Occupation(
        code="o_policy_analysis",
        label_ar="محلل سياسات سوق العمل",
        label_en="Labor Market Policy Analyst",
        sector="governance",
        tasks=(
            _t("t1", "تحليل بيانات سوق العمل", "Labor market data analysis", TASK_AUGMENT, 0.35),
            _t("t2", "محاكاة خيارات السياسة", "Policy option simulation", TASK_AUGMENT, 0.25),
            _t("t3", "صياغة توصيات القرار", "Decision recommendation drafting", TASK_HUMAN, 0.25),
            _t(
                "t4", "مراجعة الحوكمة والامتثال", "Governance & compliance review", TASK_HUMAN, 0.15
            ),
        ),
        current_skills=("s_policy_analysis", "s_data_analytics"),
        future_skills=("s_policy_analysis", "s_simulation", "s_compliance"),
        adjacent_occupations=("o_bi_analyst", "o_ops_analyst"),
        demand_signal=0.5,
        wage_reference=1.15,
    ),
    "o_compliance": Occupation(
        code="o_compliance",
        label_ar="مفتش امتثال خوارزمي",
        label_en="Algorithmic Compliance Officer",
        sector="governance",
        tasks=(
            _t(
                "t1",
                "تدقيق أنظمة التوظيف الآلية",
                "Automated hiring system audits",
                TASK_AUGMENT,
                0.3,
            ),
            _t("t2", "اختبار الانحياز على الفئات", "Bias testing across groups", TASK_AUGMENT, 0.3),
            _t(
                "t3", "إصدار توصيات تصحيحية", "Corrective recommendation issuance", TASK_HUMAN, 0.25
            ),
            _t(
                "t4",
                "التحقيق في الشكاوى والاعتراضات",
                "Complaint & appeal investigation",
                TASK_HUMAN,
                0.15,
            ),
        ),
        current_skills=("s_compliance", "s_algorithm_audit"),
        future_skills=("s_algorithm_audit", "s_compliance", "s_privacy_security"),
        adjacent_occupations=("o_hr_digital", "o_policy_analysis"),
        demand_signal=0.7,
        wage_reference=1.25,
    ),
    "o_green_tech": Occupation(
        code="o_green_tech",
        label_ar="تقني طاقة متجددة",
        label_en="Renewable Energy Technician",
        sector="green",
        tasks=(
            _t(
                "t1",
                "تركيب وصيانة الأنظمة الميدانية",
                "Field installation & maintenance",
                TASK_HUMAN,
                0.6,
            ),
            _t(
                "t2",
                "مراقبة أداء الأنظمة عن بُعد",
                "Remote performance monitoring",
                TASK_AUGMENT,
                0.2,
            ),
            _t(
                "t3",
                "تشخيص الأعطال بالأدوات الذكية",
                "AI-assisted fault diagnosis",
                TASK_AUGMENT,
                0.1,
            ),
            _t("t4", "التدريب المجتمعي على الاستخدام", "Community usage training", TASK_HUMAN, 0.1),
        ),
        current_skills=("s_green_tech", "s_fieldwork_complex"),
        future_skills=("s_renewable", "s_digital_systems", "s_fieldwork_complex"),
        adjacent_occupations=("o_field_engineer"),
        demand_signal=0.85,
        wage_reference=1.0,
        demographics_notes="نمو أخضر رئيسي (WEF 2025) — فرصة للفئات الريفية",
    ),
    "o_field_engineer": Occupation(
        code="o_field_engineer",
        label_ar="مهندس ميداني",
        label_en="Field Engineer",
        sector="green",
        tasks=(
            _t("t1", "الإشراف على الأعمال الميدانية", "Fieldwork supervision", TASK_HUMAN, 0.55),
            _t("t2", "تحليل بيانات الموقع", "Site data analysis", TASK_AUGMENT, 0.25),
            _t("t3", "التخطيط اللوجستي", "Logistics planning", TASK_AUGMENT, 0.1),
            _t("t4", "إدارة المخاطر والسلامة", "Risk & safety management", TASK_HUMAN, 0.1),
        ),
        current_skills=("s_fieldwork_complex", "s_green_tech"),
        future_skills=("s_fieldwork_complex", "s_data_analytics", "s_renewable"),
        adjacent_occupations=("o_green_tech"),
        demand_signal=0.7,
        wage_reference=1.1,
    ),
    "o_freelance_coord": Occupation(
        code="o_freelance_coord",
        label_ar="منسق عمل حر منظم",
        label_en="Organized Freelancing Coordinator",
        sector="digital_economy",
        tasks=(
            _t(
                "t1",
                "تجميع الفرص وتوزيعها",
                "Opportunity aggregation & distribution",
                TASK_AUGMENT,
                0.3,
            ),
            _t(
                "t2",
                "التحقق من الجودة والدفع",
                "Quality & payment verification",
                TASK_AUGMENT,
                0.25,
            ),
            _t(
                "t3", "تأهيل المستقلين الجدد", "Freelancer onboarding & upskilling", TASK_HUMAN, 0.3
            ),
            _t("t4", "حل النزاعات", "Dispute resolution", TASK_HUMAN, 0.15),
        ),
        current_skills=("s_freelance_org", "s_ops_coord"),
        future_skills=("s_freelance_org", "s_ai_tools", "s_emotional_comm"),
        adjacent_occupations=("o_system_support", "o_cx_advanced"),
        demand_signal=0.45,
        wage_reference=0.85,
        demographics_notes="نموذج اقتصادي جديد — يستوعب العمالة غير الرسمية",
    ),
    "o_simulation": Occupation(
        code="o_simulation",
        label_ar="محلل محاكاة سياسات",
        label_en="Policy Simulation Analyst",
        sector="governance",
        tasks=(
            _t("t1", "بناء نماذج المحاكاة", "Simulation model building", TASK_AUGMENT, 0.3),
            _t("t2", "تشغيل السيناريوهات", "Scenario runs", TASK_AUTO_TOOLS, 0.25),
            _t(
                "t3", "تفسير السيناريوهات للجنة الحوكمة", "Scenario interpretation", TASK_HUMAN, 0.3
            ),
            _t(
                "t4",
                "رصد حساسية الافتراضات",
                "Assumption sensitivity monitoring",
                TASK_AUGMENT,
                0.15,
            ),
        ),
        current_skills=("s_policy_analysis", "s_data_analytics"),
        future_skills=("s_policy_analysis", "s_simulation"),
        adjacent_occupations=("o_bi_analyst", "o_policy_analysis"),
        demand_signal=0.5,
        wage_reference=1.2,
    ),
}

# ── وحدات تدريب قصيرة (microcredentials) — وثيقة المشروع §5.6 و §9.4 ──────────

TRAINING_UNITS: dict[str, dict[str, object]] = {
    "u_ai_literacy": {
        "code": "u_ai_literacy",
        "label_ar": "محو الأمية الذكية الأساسية",
        "duration_weeks": 8,
        "skills": ("s_ai_lit", "s_ai_tools", "s_responsible_ai"),
        "target_occupations": ("o_data_entry", "o_admin_support", "o_cx_basic", "o_teacher"),
        "level": "foundational",
    },
    "u_data_analytics": {
        "code": "u_data_analytics",
        "label_ar": "تحليل البيانات التطبيقي",
        "duration_weeks": 10,
        "skills": ("s_data_analytics", "s_bi", "s_data_quality"),
        "target_occupations": ("o_data_entry", "o_admin_support", "o_cx_basic", "o_ops_analyst"),
        "level": "intermediate",
    },
    "u_privacy_ethics": {
        "code": "u_privacy_ethics",
        "label_ar": "الخصوصية وأخلاقيات البيانات",
        "duration_weeks": 6,
        "skills": ("s_privacy_security", "s_compliance", "s_responsible_ai"),
        "target_occupations": ("o_data_entry", "o_hr_digital", "o_data_quality"),
        "level": "foundational",
    },
    "u_professional_comm": {
        "code": "u_professional_comm",
        "label_ar": "التواصل المهني والتعاطفي",
        "duration_weeks": 6,
        "skills": ("s_emotional_comm", "s_care_advanced"),
        "target_occupations": ("o_cx_basic", "o_care_assistant", "o_admin_support"),
        "level": "foundational",
    },
    "u_process_automation": {
        "code": "u_process_automation",
        "label_ar": "أتمتة العمليات التشغيلية",
        "duration_weeks": 10,
        "skills": ("s_process_automation", "s_ops_coord", "s_ai_tools"),
        "target_occupations": ("o_admin_support", "o_ops_analyst"),
        "level": "intermediate",
    },
    "u_system_support": {
        "code": "u_system_support",
        "label_ar": "دعم الأنظمة الرقمية",
        "duration_weeks": 10,
        "skills": ("s_support_systems", "s_digital_systems"),
        "target_occupations": ("o_admin_support", "o_data_entry"),
        "level": "intermediate",
    },
    "u_data_quality": {
        "code": "u_data_quality",
        "label_ar": "جودة البيانات وضبطها",
        "duration_weeks": 8,
        "skills": ("s_data_quality", "s_data_analytics", "s_privacy_security"),
        "target_occupations": ("o_data_entry", "o_cx_basic"),
        "level": "intermediate",
    },
    "u_care_tech": {
        "code": "u_care_tech",
        "label_ar": "الرعاية المدعومة بالتقنية",
        "duration_weeks": 12,
        "skills": ("s_care_economy", "s_health_assistant", "s_digital_systems", "s_emotional_comm"),
        "target_occupations": ("o_cx_basic", "o_care_assistant"),
        "level": "intermediate",
    },
    "u_teacher_ai": {
        "code": "u_teacher_ai",
        "label_ar": "الذكاء الاصطناعي للمعلمين",
        "duration_weeks": 10,
        "skills": ("s_ai_lit", "s_assessment_design", "s_teacher_training"),
        "target_occupations": ("o_teacher", "o_teacher_trainer"),
        "level": "foundational",
    },
    "u_algorithm_audit": {
        "code": "u_algorithm_audit",
        "label_ar": "تدقيق الخوارزميات والامتثال",
        "duration_weeks": 12,
        "skills": ("s_algorithm_audit", "s_compliance", "s_privacy_security"),
        "target_occupations": ("o_hr_digital", "o_compliance"),
        "level": "advanced",
    },
    "u_green_tech": {
        "code": "u_green_tech",
        "label_ar": "التقنيات الخضراء العملية",
        "duration_weeks": 12,
        "skills": ("s_renewable", "s_green_tech", "s_fieldwork_complex"),
        "target_occupations": ("o_freelance_coord", "o_admin_support"),
        "level": "intermediate",
    },
    "u_freelance": {
        "code": "u_freelance",
        "label_ar": "العمل الحر المنظم",
        "duration_weeks": 6,
        "skills": ("s_freelance_org", "s_ops_coord", "s_cx"),
        "target_occupations": ("o_cx_basic", "o_data_entry"),
        "level": "foundational",
    },
}


# ── القطاعات الرصينة (وكيل خلق الوظائف §6 وكيل 6) ───────────────────────────

GROWTH_SECTORS: dict[str, dict[str, object]] = {
    "care": {
        "code": "care",
        "label_ar": "اقتصاد الرعاية",
        "growth_signal": 0.8,
        "key_occupations": ("o_care_assistant", "o_health_assistant"),
        "notes": "أكبر مصدر وظائف جديدة حسب WEF 2025 وILO — شيخوخة سكانية + رعاية إنسانية غير قابلة للأتمتة",
    },
    "green": {
        "code": "green",
        "label_ar": "الاقتصاد الأخضر",
        "growth_signal": 0.85,
        "key_occupations": ("o_green_tech", "o_field_engineer"),
        "notes": "الطاقة المتجددة من أسرع المهن نمواً (WEF 2025 top-growing)",
    },
    "data": {
        "code": "data",
        "label_ar": "اقتصاد البيانات",
        "growth_signal": 0.7,
        "key_occupations": ("o_data_quality", "o_ops_analyst", "o_bi_analyst"),
        "notes": "البيانات وجودتها من بنية التحول — كل تحول ذكاء اصطناعي يولّد حاجة جودة بيانات",
    },
    "digital_economy": {
        "code": "digital_economy",
        "label_ar": "الخدمات الرقمية والعمل الحر المنظم",
        "growth_signal": 0.55,
        "key_occupations": ("o_freelance_coord", "o_system_support"),
        "notes": "استيعاب العمالة غير الرسمية — وعدالة الوصول للمناطق الأقل حظاً",
    },
    "sme_digital": {
        "code": "sme_digital",
        "label_ar": "رقمنة المنشآت الصغيرة والمتوسطة",
        "growth_signal": 0.6,
        "key_occupations": ("o_ops_analyst", "o_system_support"),
        "notes": "OECD 2025: GenAI والأعمال الصغيرة — دعم الرقمنة يخلق وظائف توظيف مساند",
    },
    "ai_specialization": {
        "code": "ai_specialization",
        "label_ar": "التخصص في الذكاء الاصطناعي",
        "growth_signal": 0.9,
        "key_occupations": ("o_ai_ml_spec", "o_software_dev"),
        "notes": "فجوة مهارات حادة — الطلب يتجاوز العرض عالمياً (WEF 2025)",
    },
}
