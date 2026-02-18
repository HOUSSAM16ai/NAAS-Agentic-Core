# app/services/overmind/domain/context.py
"""
سياق التعاون (Collaboration Context).
---------------------------------------------------------
تنفيذ ملموس لبروتوكول CollaborationContext لإدارة الحالة المشتركة
بين وكلاء "مجلس الحكمة" (Council of Wisdom).

المعايير:
- CS50 2025 Strict Mode.
- توثيق "Legendary" باللغة العربية.
"""

from app.core.protocols import CollaborationContext


class InMemoryCollaborationContext(CollaborationContext):
    """
    سياق تعاوني في الذاكرة (In-Memory).

    يستخدم لتمرير المعلومات والحالة بين الوكلاء خلال دورة حياة المهمة الواحدة.
    """

    def __init__(self, initial_data: dict[str, object] | None = None) -> None:
        self.shared_memory: dict[str, object] = initial_data or {}

    def update(self, key: str, value: object) -> None:
        """
        تحديث قيمة في الذاكرة المشتركة.

        Args:
            key (str): المفتاح.
            value (object): القيمة الجديدة.
        """
        self.shared_memory[key] = value

    def get(self, key: str) -> object | None:
        """
        استرجاع قيمة من الذاكرة المشتركة.

        Args:
            key (str): المفتاح.

        Returns:
            object | None: القيمة المطلوبة أو None إذا لم تكن موجودة.
        """
        return self.shared_memory.get(key)
