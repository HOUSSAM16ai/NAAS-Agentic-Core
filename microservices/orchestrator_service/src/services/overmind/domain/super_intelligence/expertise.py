"""
مُعرِّف الخبرة العلمية (Expertise Profiler).

يحدد مجال السؤال ومستوى الصرامة المطلوب لإنتاج إجابات
عالية الجودة في الفيزياء والرياضيات والعلوم والطب.
"""


def build_expertise_profile(situation: str) -> dict[str, object]:
    """
    بناء ملف خبرة علمية يوجّه الوكلاء لإجابات صارمة ودقيقة.

    Args:
        situation: نص السؤال أو الموقف

    Returns:
        dict[str, object]: ملف خبرة منظم
    """
    domain = _detect_domain(situation)
    rigor = _detect_rigor_level(situation)
    guidelines = _build_guidelines(domain, rigor)
    return {
        "domain": domain,
        "rigor_level": rigor,
        "guidelines": guidelines,
        "requires_citations": domain in {"medicine", "physics"},
    }


def _detect_domain(situation: str) -> str:
    """
    تصنيف مجال السؤال (فيزياء/رياضيات/علوم/طب/عام).
    """
    normalized = situation.lower()
    domain_keywords = {
        "physics": ["quantum", "relativity", "thermodynamics", "فيزياء", "ميكانيكا"],
        "mathematics": ["theorem", "proof", "lemma", "رياضيات", "معادلة", "تكامل"],
        "medicine": ["diagnosis", "clinical", "dosage", "طب", "علاج", "تشخيص"],
        "science": ["chemistry", "biology", "genetics", "علوم", "كيمياء", "أحياء"],
    }
    for domain, keywords in domain_keywords.items():
        if any(keyword in normalized for keyword in keywords):
            return domain
    return "general"


def _detect_rigor_level(situation: str) -> str:
    """
    تقدير مستوى الصرامة المطلوبة في الإجابة.
    """
    normalized = situation.lower()
    high_rigor = [
        "proof",
        "derive",
        "formal",
        "برهان",
        "اشتقاق",
        "صياغة رسمية",
    ]
    medium_rigor = ["explain", "why", "لماذا", "كيف"]
    if any(keyword in normalized for keyword in high_rigor):
        return "high"
    if any(keyword in normalized for keyword in medium_rigor):
        return "medium"
    return "standard"


def _build_guidelines(domain: str, rigor: str) -> list[str]:
    """
    بناء إرشادات إجابة صارمة حسب المجال ومستوى الصرامة.
    """
    common = [
        "ابدأ بتعريف المصطلحات الأساسية بدقة.",
        "قسّم الإجابة إلى خطوات منطقية واضحة.",
        "تحقق من الاتساق الداخلي قبل تقديم الخلاصة.",
    ]
    rigorous = [
        "قدّم البرهان أو الاشتقاق خطوة بخطوة.",
        "اذكر الفرضيات وحدود التطبيق صراحة.",
    ]
    medical = [
        "ضمّن تنبيه السلامة الطبية وعدم الاستبدال بالاستشارة المهنية.",
        "اذكر نطاق الجرعات أو البروتوكولات إن وُجدت بحذر.",
    ]
    domain_specific = {
        "physics": ["استخدم صيغاً ومعادلات قياسية وعرّف الرموز قبل الاستخدام."],
        "mathematics": ["قدّم التعريفات ثم البرهان ثم الحالات الخاصة."],
        "science": ["اربط النتائج بالآليات أو التجارب الداعمة."],
        "medicine": medical,
    }
    guidelines = list(common)
    if rigor == "high":
        guidelines.extend(rigorous)
    if domain in domain_specific:
        guidelines.extend(domain_specific[domain])
    return guidelines
