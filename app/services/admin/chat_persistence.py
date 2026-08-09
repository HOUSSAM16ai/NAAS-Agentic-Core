"""
طبقة البيانات للمحادثات الإدارية (Admin Chat Persistence).

تدير هذه الطبقة جميع عمليات الوصول إلى قاعدة البيانات المتعلقة بمحادثات المسؤول،
مع ضمان العزل التام لمنطق التخزين عن منطق الأعمال (Separation of Concerns).

المبادئ المعمارية:
- **Repository Pattern**: تغليف عمليات قاعدة البيانات.
- **Strict Typing**: استخدام أنواع محددة وتجنب `object`.
- **Fail Fast**: التحقق المبكر من صحة البيانات والصلاحيات.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.chat import AdminConversation, AdminMessage, MessageRole
from app.core.domain.user import User
from app.core.prompts import get_system_prompt
from shared.memory import assert_student_authored

logger = logging.getLogger(__name__)


class AdminChatPersistence:
    """
    تدير عمليات التخزين والاسترجاع لمحادثات المسؤول.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        تهيئة مستودع المحادثات.

        Args:
            db: جلسة قاعدة البيانات.
        """
        self.db = db

    async def verify_access(self, user_id: int, conversation_id: int) -> AdminConversation:
        """
        التحقق من صلاحية وصول المستخدم للمحادثة.

        Args:
            user_id: معرف المستخدم.
            conversation_id: معرف المحادثة.

        Returns:
            AdminConversation: كائن المحادثة في حال نجاح التحقق.

        Raises:
            ValueError: في حال عدم وجود المستخدم، المحادثة، أو عدم امتلاك الصلاحية.
        """
        user = await self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        conversation = await self.db.get(AdminConversation, conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")

        if user.is_admin:
            return conversation

        if conversation.user_id != user_id:
            raise ValueError("Access denied to conversation")

        return conversation

    async def get_or_create_conversation(
        self, user_id: int, title_hint: str, conversation_id: str | int | None = None
    ) -> AdminConversation:
        """
        استرجاع محادثة موجودة أو إنشاء واحدة جديدة.

        Args:
            user_id: معرف المستخدم.
            title_hint: عنوان مقترح للمحادثة الجديدة.
            conversation_id: معرف المحادثة (اختياري).

        Returns:
            AdminConversation: كائن المحادثة.
        """
        conversation: AdminConversation | None = None
        if conversation_id:
            try:
                conversation = await self.verify_access(user_id, int(conversation_id))
            except (ValueError, TypeError):
                # في حال عدم الصلاحية أو عدم الوجود، نرفع الخطأ
                raise

        if not conversation:
            conversation = AdminConversation(title=title_hint[:50], user_id=user_id)
            self.db.add(conversation)
            await self.db.commit()
            await self.db.refresh(conversation)

        return conversation

    async def save_message(
        self, conversation_id: int, role: MessageRole, content: str
    ) -> AdminMessage:
        """
        حفظ رسالة جديدة في المحادثة.

        Args:
            conversation_id: معرف المحادثة.
            role: دور المرسل.
            content: محتوى الرسالة.

        Returns:
            AdminMessage: كائن الرسالة المحفوظة.

        Raises:
            MemoryAuthorshipError: نصٌّ من تأليف النظام حاول التخزين بدور المستخدم
                (D-229/ISS-146) — تسميمُ ذاكرةٍ مؤجَّل الأثر.
        """
        if role == MessageRole.USER:
            assert_student_authored(content, where="admin.save_message")

        message = AdminMessage(conversation_id=conversation_id, role=role, content=content)
        self.db.add(message)
        await self.db.commit()
        return message

    async def get_chat_history(
        self, conversation_id: int, limit: int = 20
    ) -> list[dict[str, object]]:
        """
        استرجاع تاريخ المحادثة بتنسيق جاهز للنموذج (LLM).

        Args:
            conversation_id: معرف المحادثة.
            limit: الحد الأقصى للرسائل المسترجعة.

        Returns:
            list[dict[str, object]]: قائمة الرسائل بتنسيق القاموس.
        """
        stmt = (
            select(AdminMessage)
            .where(AdminMessage.conversation_id == conversation_id)
            .order_by(AdminMessage.created_at.desc(), AdminMessage.id.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        history_messages = list(result.scalars().all())
        history_messages.reverse()

        messages: list[dict[str, object]] = [
            {"role": "system", "content": await get_system_prompt()}
        ]
        for msg in history_messages:
            messages.append({"role": msg.role.value, "content": msg.content})

        return messages

    async def get_latest_conversation(self, user_id: int) -> AdminConversation | None:
        """
        استرجاع آخر محادثة للمستخدم.

        Args:
            user_id: معرف المستخدم.

        Returns:
            AdminConversation | None: كائن المحادثة أو None.
        """
        stmt = (
            select(AdminConversation)
            .where(AdminConversation.user_id == user_id)
            .order_by(AdminConversation.created_at.desc(), AdminConversation.id.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_conversations(self, user_id: int) -> list[AdminConversation]:
        """
        سرد جميع محادثات المستخدم.

        Args:
            user_id: معرف المستخدم.

        Returns:
            list[AdminConversation]: قائمة المحادثات.
        """
        stmt = (
            select(AdminConversation)
            .where(AdminConversation.user_id == user_id)
            .order_by(AdminConversation.created_at.desc(), AdminConversation.id.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_conversation_messages(
        self, conversation_id: int, limit: int = 1000
    ) -> list[AdminMessage]:
        """
        استرجاع رسائل محادثة محددة.

        Args:
            conversation_id: معرف المحادثة.
            limit: الحد الأقصى للرسائل.

        Returns:
            list[AdminMessage]: قائمة الرسائل.
        """
        stmt = (
            select(AdminMessage)
            .where(AdminMessage.conversation_id == conversation_id)
            .order_by(AdminMessage.created_at.desc(), AdminMessage.id.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())
        # إعادة الترتيب زمنياً للعرض
        messages.reverse()
        return messages
