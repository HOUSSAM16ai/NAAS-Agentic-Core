"""
استثناءات العقل المدبر.
---------------------------------------------------------
تعريف استثناءات خاصة لتسهيل التحكم في التدفق والتشخيص.

المعايير:
- CS50 2025 Strict Mode.
- توثيق عربي.
"""


class OvermindError(Exception):
    """الاستثناء الأساسي لخدمة العقل المدبر."""

    pass


class StalemateError(OvermindError):
    """
    يُثار هذا الاستثناء عندما يكتشف "الناقد الداخلي" (Auditor)
    أن النظام عالق في حلقة استدلال مفرغة (Infinite Loop).
    """

    def __init__(self, message: str = "Infinite reasoning loop detected"):
        super().__init__(message)
