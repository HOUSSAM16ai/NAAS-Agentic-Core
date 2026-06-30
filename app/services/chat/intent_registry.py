"""
سجل أنماط النوايا (Intent Pattern Registry).

يوفر آلية مركزية لتسجيل أنماط النوايا دون الحاجة لتعديل الكود الأصلي.
يطبق مبدأ Open/Closed Principle - مفتوح للتوسع، مغلق للتعديل.

المبادئ:
- SOLID: Open/Closed Principle
- Registry Pattern: تسجيل الأنماط ديناميكياً
- Plugin Architecture: إضافة نوايا جديدة دون تعديل الكود
"""

from collections.abc import Callable
from typing import ClassVar

from app.services.chat.intent_detector import ChatIntent, IntentPattern


class IntentPatternRegistry:
    """
    سجل مركزي لأنماط النوايا.

    يسمح بتسجيل أنماط جديدة دون تعديل فئة IntentDetector.
    """

    _patterns: ClassVar[list[IntentPattern]] = []
    _default_patterns_loaded: ClassVar[bool] = False

    @classmethod
    def register(
        cls,
        pattern: str,
        intent: ChatIntent,
        extractor: Callable | None = None,
        priority: int = 0,
    ) -> None:
        """
        تسجيل نمط نية جديد.

        Args:
            pattern: التعبير النمطي للكشف عن النية.
            intent: نوع النية المطابقة.
            extractor: دالة استخراج المعاملات (اختياري).
            priority: أولوية النمط (الأعلى يُفحص أولاً).
        """
        if extractor is None:
            extractor = lambda _: {}  # noqa: E731

        intent_pattern = IntentPattern(
            pattern=pattern,
            intent=intent,
            extractor=extractor,
        )
        cls._patterns.append((priority, intent_pattern))
        # إعادة الترتيب حسب الأولوية (الأعلى أولاً)
        cls._patterns.sort(key=lambda x: x[0], reverse=True)

    @classmethod
    def get_all(cls) -> list[IntentPattern]:
        """
        استرجاع جميع الأنماط المسجلة مرتبة حسب الأولوية.

        Returns:
            list[IntentPattern]: قائمة الأنماط.
        """
        return [pattern for _, pattern in cls._patterns]

    @classmethod
    def clear(cls) -> None:
        """مسح جميع الأنماط المسجلة (للاختبار)."""
        cls._patterns.clear()
        cls._default_patterns_loaded = False

    @classmethod
    def is_loaded(cls) -> bool:
        """التحقق مما إذا تم تحميل الأنماط الافتراضية."""
        return cls._default_patterns_loaded

    @classmethod
    def mark_loaded(cls) -> None:
        """تعليم الأنماط الافتراضية كمحملة."""
        cls._default_patterns_loaded = True


# === تسجيل الأنماط الافتراضية ===
# هذه الأنماط تُحمّل عند استيراد الوحدة


def register_default_patterns() -> None:
    """تسجيل الأنماط الافتراضية إذا لم تكن مسجلة."""
    if IntentPatternRegistry.is_loaded():
        return

    # Admin queries (high priority)
    admin_patterns = [
        r"(user|users|مستخدم|مستخدمين|count users|list users|profile|stats|أعضاء)",
        r"(database|schema|tables|db map|database map|قاعدة بيانات|قاعدة البيانات|جداول|مخطط|بنية البيانات|خريطة قاعدة البيانات|العلاقات)",
        r"(route|endpoint|api path|مسار api|نقطة نهاية|services|microservices|خدمات|مصغرة)",
        r"(structure|project info|هيكل المشروع|معلومات المشروع|بنية النظام)",
        r"(python|بايثون|\.py)",
        r"(files|ملفات|ملف|عدد\s*ملفات)",
        r"(كم|count|احسب)\s*(عدد)?\s*(ملف|بايثون|python)",
    ]
    for pattern in admin_patterns:
        IntentPatternRegistry.register(pattern, ChatIntent.ADMIN_QUERY, priority=90)

    # Deep analysis (higher priority than content retrieval)
    IntentPatternRegistry.register(
        r"(حلل|analyze|explain|اشرح)\s+(.+)",
        ChatIntent.DEEP_ANALYSIS,
        priority=90,
    )

    # Content retrieval (high priority)
    IntentPatternRegistry.register(
        r"^((أ|ا)ريد|بدي|i want|need|show|أعطني|هات|give me)?\s*(.{0,60})(20[1-2][0-9]|bac|بكالوريا|subject|topic|lesson|درس|موضوع|تمارين|تمرين|exam|exercise|exercises|احتمالات|دوال|متتاليات|probability|functions|sequences)(.{0,60})?$",
        ChatIntent.CONTENT_RETRIEVAL,
        priority=80,
    )

    IntentPatternRegistry.register(
        r"(نص|text)\s+(التمرين|تمرين|exercise|exercises)\b(.+)?",
        ChatIntent.CONTENT_RETRIEVAL,
        priority=80,
    )

    # File operations
    IntentPatternRegistry.register(
        r"(read|open|show|cat|اقرا|اقرأ|اعرض|عرض)\s+(file|ملف)\s+(.+)",
        ChatIntent.FILE_READ,
        extractor=lambda m: {"path": m.group(3).strip()},
        priority=70,
    )

    # Code search
    IntentPatternRegistry.register(
        r"(ابحث|search|find|where|أين|اين)\s+(عن|for)?\s*(.+)",
        ChatIntent.CODE_SEARCH,
        extractor=lambda m: {"query": m.group(3).strip()},
        priority=70,
    )

    # Project indexing
    IntentPatternRegistry.register(
        r"(فهرس|index)\s+(المشروع|project)",
        ChatIntent.PROJECT_INDEX,
        priority=60,
    )

    # Analytics report
    IntentPatternRegistry.register(
        r"(مستواي|أدائي|نقاط ضعفي|نقاط الضعف|تقييم|level|performance|weakness|report|تشخيص\s*(نقاط|الضعف|أداء|الأداء|مستواي)|تقييم\s*مستواي|اختبرني|تشخيص\s*مستواي)",
        ChatIntent.ANALYTICS_REPORT,
        priority=70,
    )

    # Learning summary
    IntentPatternRegistry.register(
        r"(ملخص|تلخيص|خلاصة|لخص|summarize|summary).*(ما تعلمت|ما تعلمته|تعلمي|محادثاتي|دردشاتي|سجلي|what i learned|what i've learned|my learning|my chats|my history)",
        ChatIntent.LEARNING_SUMMARY,
        priority=60,
    )

    # Curriculum plan
    IntentPatternRegistry.register(
        r"(واجب|مسار|تعلم|homework|learning path|challenge|خطة|خريطة|منهج|plan|roadmap|study plan|ابدأ|start studying)",
        ChatIntent.CURRICULUM_PLAN,
        priority=50,
    )

    # Help
    IntentPatternRegistry.register(
        r"(مساعدة|help)",
        ChatIntent.HELP,
        priority=40,
    )

    IntentPatternRegistry.mark_loaded()


# تحميل الأنماط عند الاستيراد
register_default_patterns()
