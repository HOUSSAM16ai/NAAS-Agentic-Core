# app/services/overmind/art/styles.py
"""
🎨 CS73: Aesthetic Styles and Color Theory
===========================================

تطبيق نظرية الألوان والأنماط الفنية على البيانات البرمجية.
يستخدم مبادئ التصميم الجرافيكي لإنشاء تصورات جمالية.

Color Theory (نظرية الألوان):
- Complementary: ألوان متكاملة تخلق تباين قوي
- Analogous: ألوان متجاورة تخلق انسجام
- Triadic: ثلاث ألوان متساوية البعد على عجلة الألوان
- Monochromatic: درجات مختلفة من لون واحد

Design Principles (مبادئ التصميم):
- Balance: التوازن البصري
- Contrast: التباين للفت الانتباه
- Harmony: الانسجام بين العناصر
- Hierarchy: التسلسل الهرمي للمعلومات
"""

from enum import Enum
from typing import ClassVar, NamedTuple


class ColorPalette(NamedTuple):
    """
    لوحة ألوان فنية لتصور البيانات.

    Attributes:
        primary: اللون الأساسي (للعناصر المهمة)
        secondary: اللون الثانوي (للعناصر الداعمة)
        accent: لون التمييز (للفت الانتباه)
        background: لون الخلفية
        text: لون النص
        success: لون النجاح (أخضر)
        warning: لون التحذير (أصفر/برتقالي)
        error: لون الخطأ (أحمر)
        info: لون المعلومات (أزرق)
    """

    primary: str
    secondary: str
    accent: str
    background: str
    text: str
    success: str
    warning: str
    error: str
    info: str


class ArtStyle(Enum):
    """
    أنماط فنية مختلفة لتصور البيانات.

    CS73 Concept: كل نمط يعبر عن الفلسفة الجمالية المختلفة.
    """

    # Minimalist: بساطة وأناقة
    MINIMALIST = "minimalist"

    # Cyberpunk: مستقبلي مع ألوان نيون
    CYBERPUNK = "cyberpunk"

    # Nature: مستوحى من الطبيعة
    NATURE = "nature"

    # Retro: نمط كلاسيكي قديم
    RETRO = "retro"

    # Modern: عصري وجريء
    MODERN = "modern"

    # Dark Mode: وضع داكن للعين
    DARK = "dark"

    # Light Mode: وضع فاتح ومشرق
    LIGHT = "light"

    # Gradient: تدرجات لونية ناعمة
    GRADIENT = "gradient"


class VisualTheme:
    """
    ثيم بصري متكامل يجمع الألوان والأنماط.

    CS73: يطبق مبادئ الانسجام البصري والتوازن.
    """

    # تعريف لوحات الألوان للأنماط المختلفة
    PALETTES: ClassVar[dict[ArtStyle, ColorPalette]] = {
        ArtStyle.MINIMALIST: ColorPalette(
            primary="#2C3E50",
            secondary="#95A5A6",
            accent="#3498DB",
            background="#FFFFFF",
            text="#2C3E50",
            success="#27AE60",
            warning="#F39C12",
            error="#E74C3C",
            info="#3498DB",
        ),
        ArtStyle.CYBERPUNK: ColorPalette(
            primary="#00FF41",
            secondary="#FF006E",
            accent="#8338EC",
            background="#0D1B2A",
            text="#00FF41",
            success="#00FF41",
            warning="#FFB703",
            error="#FF006E",
            info="#00B4D8",
        ),
        ArtStyle.NATURE: ColorPalette(
            primary="#2D6A4F",
            secondary="#52B788",
            accent="#95D5B2",
            background="#F1FAEE",
            text="#1B4332",
            success="#40916C",
            warning="#F77F00",
            error="#D62828",
            info="#457B9D",
        ),
        ArtStyle.RETRO: ColorPalette(
            primary="#D4A373",
            secondary="#FAEDCD",
            accent="#E9EDC9",
            background="#FEFAE0",
            text="#6C584C",
            success="#CCD5AE",
            warning="#E76F51",
            error="#BC4749",
            info="#A0C4E7",
        ),
        ArtStyle.MODERN: ColorPalette(
            primary="#023047",
            secondary="#FFB703",
            accent="#FB8500",
            background="#FFFFFF",
            text="#023047",
            success="#06D6A0",
            warning="#FFB703",
            error="#EF476F",
            info="#118AB2",
        ),
        ArtStyle.DARK: ColorPalette(
            primary="#BB86FC",
            secondary="#03DAC6",
            accent="#CF6679",
            background="#121212",
            text="#FFFFFF",
            success="#03DAC6",
            warning="#FFA726",
            error="#CF6679",
            info="#64B5F6",
        ),
        ArtStyle.LIGHT: ColorPalette(
            primary="#6200EE",
            secondary="#03DAC6",
            accent="#018786",
            background="#FFFFFF",
            text="#000000",
            success="#4CAF50",
            warning="#FF9800",
            error="#B00020",
            info="#2196F3",
        ),
        ArtStyle.GRADIENT: ColorPalette(
            primary="#667EEA",
            secondary="#764BA2",
            accent="#F093FB",
            background="#FFFFFF",
            text="#333333",
            success="#00D4AA",
            warning="#FFA94D",
            error="#FF6B9D",
            info="#4F86F7",
        ),
    }

    @classmethod
    def get_palette(cls, style: ArtStyle) -> ColorPalette:
        """
        الحصول على لوحة الألوان لنمط معين.

        Args:
            style: النمط الفني المطلوب

        Returns:
            ColorPalette: لوحة الألوان المناسبة

        Example:
            >>> theme = VisualTheme.get_palette(ArtStyle.CYBERPUNK)
            >>> logger.info(theme.primary)
            '#00FF41'
        """
        return cls.PALETTES.get(style, cls.PALETTES[ArtStyle.MINIMALIST])

    @classmethod
    def create_gradient(cls, color1: str, color2: str, steps: int = 10) -> list[str]:
        """
        إنشاء تدرج لوني بين لونين.

        CS73 Concept: التدرج اللوني يخلق انتقال ناعم وجمالي.

        Args:
            color1: اللون الأول (hex format)
            color2: اللون الثاني (hex format)
            steps: عدد الخطوات في التدرج

        Returns:
            list[str]: قائمة من الألوان في التدرج

        Complexity: O(steps)
        """

        def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
            """تحويل hex إلى RGB"""
            hex_color = hex_color.lstrip("#")
            return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore

        def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
            """تحويل RGB إلى hex"""
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

        rgb1 = hex_to_rgb(color1)
        rgb2 = hex_to_rgb(color2)

        gradient: list[str] = []
        for i in range(steps):
            ratio = i / (steps - 1) if steps > 1 else 0
            r = int(rgb1[0] + (rgb2[0] - rgb1[0]) * ratio)
            g = int(rgb1[1] + (rgb2[1] - rgb1[1]) * ratio)
            b = int(rgb1[2] + (rgb2[2] - rgb1[2]) * ratio)
            gradient.append(rgb_to_hex((r, g, b)))

        return gradient

    @classmethod
    def get_contrasting_color(cls, color: str) -> str:
        """
        الحصول على لون متباين للنص على خلفية معينة.

        CS73 Principle: التباين الكافي يضمن قراءة سهلة.

        Args:
            color: لون الخلفية (hex format)

        Returns:
            str: أبيض أو أسود حسب السطوع

        Complexity: O(1)
        """
        # حساب السطوع (Luminance)
        hex_color = color.lstrip("#")
        r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

        # صيغة السطوع النسبي (Relative Luminance)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255

        # إذا كان اللون فاتح، استخدم نص داكن، والعكس
        return "#000000" if luminance > 0.5 else "#FFFFFF"
