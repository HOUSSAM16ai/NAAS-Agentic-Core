import re
from typing import ClassVar

from app.core.logging import get_logger

logger = get_logger("fallback-expander")


class FallbackQueryExpander:
    """
    A simple rule-based query expander to handle multilingual search
    when the advanced LLM-based query refiner is unavailable.

    """

    # Mapping English/French terms to Arabic Baccalaureate keywords
    TERM_MAPPING: ClassVar[dict[str, str]] = {
        # Probability
        "probability": "احتمال",
        "probabilité": "احتمال",
        "probabilities": "احتمالات",
        "balls": "كرات",
        "urn": "كيس",
        "bag": "كيس",
        "dice": "نرد",
        "random variable": "متغير عشوائي",
        # Branches
        "experimental": "تجريبية",
        "sciences": "علوم",
        "math": "رياضيات",
        "mathematics": "رياضيات",
        "technique": "تقني",
        "economy": "تسيير",
        # Complex Numbers
        "complex": "مركبة",
        "complex numbers": "أعداد مركبة",
        "nombres complexes": "أعداد مركبة",
        "imaginary": "تخيلي",
        "z": "z",
        # Functions / Analysis
        "function": "دالة",
        "functions": "دوال",
        "fonction": "دالة",
        "derivative": "مشتقة",
        "integral": "تكامل",
        "logarithm": "لوغاريتم",
        "ln": "ln",
        "exponential": "اسية",
        "exp": "exp",
        "limit": "نهاية",
        "limits": "نهايات",
        "curve": "منحنى",
        # Sequences
        "sequence": "متتالية",
        "sequences": "متتاليات",
        "suite": "متتالية",
        "arithmetic": "حسابية",
        "geometric": "هندسية",
        "recurrence": "تراجع",
        # Geometry
        "geometry": "هندسة",
        "space": "فضاء",
        "plane": "مستوي",
        "vector": "شعاع",
        "barycenter": "مرجح",
        # General / Exam terms
        "exercise": "تمرين",
        "exercice": "تمرين",
        "sujet": "موضوع",
        "problem": "مسألة",
        "solution": "حل",
        "correction": "تصحيح",
        "topic": "موضوع",
        "subject": "موضوع",
        "bac": "بكالوريا",
        "baccalaureate": "بكالوريا",
    }

    # Arabic Stemming/Normalization Map (Plural/Definite -> Singular Indefinite)
    ARABIC_STEMS: ClassVar[dict[str, str]] = {
        # Probability
        "الاحتمالات": "احتمال",
        "احتمالات": "احتمال",
        "الإحتمالات": "احتمال",
        "إحتمالات": "احتمال",
        "الكرات": "كرة",
        "كرات": "كرة",
        "الكريات": "كرة",
        "كريات": "كرة",
        "الالوان": "لون",
        "الوان": "لون",
        "ألوان": "لون",
        # Analysis
        "الدوال": "دالة",
        "دوال": "دالة",
        "المتتاليات": "متتالية",
        "متتاليات": "متتالية",
        "النهايات": "نهاية",
        "نهايات": "نهاية",
        "الاشتقاقية": "مشتقة",
        "اشتقاقية": "مشتقة",
        "التكاملات": "تكامل",
        "تكاملات": "تكامل",
        "الأعداد": "عدد",
        "أعداد": "عدد",
        "اعداد": "عدد",
        # General
        "الحلول": "حل",
        "حلول": "حل",
        "التمارين": "تمرين",
        "تمارين": "تمرين",
        "المسألة": "تمرين",
        "مسألة": "تمرين",
        "المواضيع": "موضوع",
        "مواضيع": "موضوع",
        "الشعب": "شعبة",
        "شعب": "شعبة",
        "العلوم": "علوم",
        "الرياضيات": "رياضيات",
        "والالوان": "لون",
    }

    # Common Student Typos -> Correct Term
    COMMON_TYPOS: ClassVar[dict[str, str]] = {
        "تجربة": "تجريبية",  # علوم تجربة -> علوم تجريبية
        "تجربيه": "تجريبية",
        "تجربية": "تجريبية",
        "تقني": "تقني",
        "رياصي": "رياضي",
        "رياظي": "رياضي",
        "فلسفه": "فلسفة",
        "اداب": "آداب",
        "لغات": "لغات",
        "اجنبية": "أجنبية",
        "اجنبيه": "أجنبية",
        "الاول": "الأول",
        "الثاني": "الثاني",
        "الثانى": "الثاني",
        "الثالث": "الثالث",
        "الرابع": "الرابع",
    }

    STOP_WORDS: ClassVar[set[str]] = {
        "في",
        "على",
        "من",
        "إلى",
        "عن",
        "لسنة",
        "سنة",
        "عام",
        "للعام",
        "شعبة",
        "الشعبة",
        "لشعبة",
        "مادة",
        "المادة",
        "و",
        "أو",
        "مع",
        "هل",
        "كيف",
        "ما",
        "ماذا",
        "اريد",
        "أريد",
        "ابحث",
        "أبحث",
        "اعطني",
        "أعطني",
        "هات",
        "قدم",
        "شوف",
        "تشوفلي",
        "ممكن",
        "نتاع",
        "تاع",
        "لي",
        "اللي",
        "ديال",
        "جا",
        "جاء",
        "الماضي",
        "المقبل",
        "القادم",
        "اسئلة",
        "أسئلة",
        "امتحان",
        "بكالوريا",
        "البكالوريا",
        "bac",
        "الباك",
        "باك",
        "1",
        "01",
        "تقني",
        "تسيير",
        "اقتصاد",
        "لغات",
        "أجنبية",
        "آداب",
        "فلسفة",
    }

    @classmethod
    def generate_variations(cls, q: str | None) -> list[str]:
        """
        Generates a list of query variations.
        """
        if not q:
            return []

        variations = [q]

        q_lower = q.lower()
        q_lower = re.sub(r"[،؛؟!.,:;?]", " ", q_lower)
        words = q_lower.split()

        # Strategy 1: Translate
        translated_words = []
        has_translation = False

        for word in words:
            if word in cls.TERM_MAPPING:
                translated_words.append(cls.TERM_MAPPING[word])
                has_translation = True
            elif word.isdigit():
                pass
            else:
                translated_words.append(word)

        if has_translation:
            translated_q = " ".join(translated_words).strip()
            if translated_q and translated_q != q_lower:
                variations.append(translated_q)

        # Strategy 2: Typo Correction
        base_for_typo = variations[-1]
        typo_words = []
        has_typo = False
        for word in base_for_typo.split():
            if word in cls.COMMON_TYPOS:
                typo_words.append(cls.COMMON_TYPOS[word])
                has_typo = True
            else:
                typo_words.append(word)

        if has_typo:
            typo_q = " ".join(typo_words).strip()
            if typo_q not in variations:
                variations.append(typo_q)

        # Strategy 3: Stemming
        base_for_stem = variations[-1]
        stemmed_words = []
        has_stemming = False

        for word in base_for_stem.split():
            if word in cls.ARABIC_STEMS:
                stemmed_words.append(cls.ARABIC_STEMS[word])
                has_stemming = True
            elif word.startswith("ال") and len(word) > 4:
                stripped = word[2:]
                if stripped in cls.ARABIC_STEMS:
                    stemmed_words.append(cls.ARABIC_STEMS[stripped])
                    has_stemming = True
                else:
                    stemmed_words.append(word)
            else:
                stemmed_words.append(word)

        if has_stemming:
            stemmed_q = " ".join(stemmed_words).strip()
            if stemmed_q not in variations:
                variations.append(stemmed_q)

        # Strategy 4: Stop Word Removal
        base_for_stop = variations[-1]
        clean_words = []
        has_stop_word = False

        for word in base_for_stop.split():
            if word in cls.STOP_WORDS:
                has_stop_word = True
                continue
            if (
                word.isdigit()
                and len(word) == 4
                and (word.startswith("20") or word.startswith("19"))
            ):
                has_stop_word = True
                continue
            word_no_al = word[2:] if word.startswith("ال") and len(word) > 3 else word
            if word_no_al in cls.STOP_WORDS:
                has_stop_word = True
                continue
            clean_words.append(word)

        if has_stop_word and clean_words:
            clean_q = " ".join(clean_words).strip()
            if clean_q and clean_q not in variations:
                variations.append(clean_q)

        return variations
