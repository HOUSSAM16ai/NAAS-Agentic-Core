"""
واجهات المستودعات (Protocols) في طبقة النطاق.

تعرّف هذه العقود الطريقة المسموح بها للتعامل مع البيانات بحيث يبقى تنفيذ
البنية التحتية قابلاً للاستبدال دون المساس بالمنطق التطبيقي. جميع التوثيقات
والأنواع مكتوبة بالعربية لضمان وضوح العقود واستبعاد أي استخدام للنوع
"object" غير المنضبط.
"""

from __future__ import annotations

from typing import Protocol, TypedDict

from .user import User


class UserUpdatePayload(TypedDict, total=False):
    """
    حمولة تحديث المستخدم المسموح بها.

    تقتصر الحقول على القيم التي يدعمها النموذج لضمان التوافق مع مبدأ
    "العقود الصارمة" ومنع تمرير قيم غير متوقعة.
    """

    full_name: str
    email: str
    password: str
    is_admin: bool


class DatabaseRepository(Protocol):
    """واجهة عمليات قاعدة البيانات."""

    async def check_connection(self) -> bool:
        """
        يتحقق من سلامة اتصال قاعدة البيانات.

        Returns:
            bool: True إذا كان الاتصال نشطًا، False خلاف ذلك.
        """


class UserRepository(Protocol):
    """واجهة مستودع المستخدمين المعرّفة في طبقة النطاق."""

    async def find_by_id(self, user_id: int) -> User | None:
        """
        يجلب مستخدمًا اعتمادًا على المعرّف الأولي.

        Args:
            user_id: المعرّف الفريد للمستخدم.

        Returns:
            User | None: الكيان إذا وُجد، أو None إذا لم يُعثر عليه.
        """

    async def find_by_email(self, email: str) -> User | None:
        """
        يبحث عن مستخدم بواسطة البريد الإلكتروني بعد ضبط الحالة.

        Args:
            email: البريد الإلكتروني المستهدف.

        Returns:
            User | None: الكيان المطابق أو None عند عدم التطابق.
        """

    async def create(self, user_data: UserUpdatePayload) -> User:
        """
        ينشئ مستخدمًا جديدًا بالحقول المسموح بها.

        Args:
            user_data: حمولة إنشاء تتضمن الاسم، البريد، كلمة المرور، وحقل
                الصلاحيات عند الحاجة.

        Returns:
            User: الكيان الذي تم إنشاؤه بعد الحفظ.
        """

    async def update(self, user_id: int, user_data: UserUpdatePayload) -> User | None:
        """
        يحدّث بيانات مستخدم موجود إذا وُجد.

        Args:
            user_id: المعرّف الفريد للمستخدم.
            user_data: الحقول المطلوب تعديلها.

        Returns:
            User | None: الكيان بعد التحديث أو None إذا لم يُعثر على المعرّف.
        """

    async def delete(self, user_id: int) -> bool:
        """
        يحذف مستخدمًا اعتمادًا على المعرّف الأولي.

        Args:
            user_id: المعرّف الفريد للمستخدم.

        Returns:
            bool: True عند نجاح الحذف، False إذا لم يوجد المستخدم.
        """
