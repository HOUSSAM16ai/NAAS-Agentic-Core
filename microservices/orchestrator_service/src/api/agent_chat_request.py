"""تجميع سياق دور `/agent/chat` وقرار توجيهه — D-168 Slice A5.

مُستخرَجة **حرفياً** من `routes.py` (المُعالِج كان 336 سطراً وتعقيد 51 وعمق 13).
تعتمد على `chat_types` و`identity_access` فقط — لا تستورد `routes` أبداً (طبقاتٌ
باتجاه واحد، قاعدة D-168).

⚠️ **الاسم المستعار مقصود ومحفوظ:** `context` نسخةٌ من `request.context`، ثمّ يُكتب
`trace_context` في **الاثنين** بينما `update(...)` يمسّ النسخة وحدها. فالكائنان
يتباعدان بعد النسخ، وهذا ما يقرأه المسار الإداري لاحقاً (`routes.py:994` يفحص
`request.context` لا `context`). توحيدهما «تنظيفاً» يغيّر السلوك.
"""

from __future__ import annotations

from dataclasses import dataclass

from .chat_types import ChatRunContext
from .identity_access import _is_admin_payload


@dataclass(frozen=True, slots=True)
class TurnIdentity:
    """هوية الدور ومحادثته — تُمرَّر ككائنٍ واحد بدل ثلاثة وسائط متلازمة.

    الثلاثة تتحرّك معاً دائماً (هوية الطالب · محادثته · تاريخها)، فتمريرها مفكّكة
    يُوسّع كل توقيعٍ تمرّ به بلا فائدة — وهو ما رصدته CodeScene بـ
    «Excess Number of Function Arguments» على هذه الدالّة.
    """

    user_id: int
    conversation_id: int | None
    history_messages: list[dict[str, str]]


@dataclass(frozen=True, slots=True)
class AgentChatTurn:
    """السياق المُجمَّع + قرارا التوجيه لدورٍ واحد."""

    #: نسخةٌ مُثراة من `request.context` — ما يُمرَّر إلى الوكيل.
    context: ChatRunContext
    #: من الـJWT حصراً (fail-closed) — لا من جسم الطلب.
    is_admin: bool
    #: مصافحة §6.5: المونوليث يملك رسالة المستخدم فلا يكتبها الأوركستريتور.
    is_compatibility_facade: bool


def build_agent_chat_turn(
    *,
    request_context: dict[str, object],
    identity: TurnIdentity,
    trace_context: object,
    auth_payload: dict[str, object],
) -> AgentChatTurn:
    """يبني سياق الدور بنفس ترتيب `routes.py:923-938` وبنفس أثره الجانبي."""
    context: ChatRunContext = request_context.copy()  # type: ignore[assignment]
    if trace_context:
        context["trace_context"] = trace_context
        request_context["trace_context"] = trace_context
    context.update(
        {
            "user_id": identity.user_id,
            "conversation_id": identity.conversation_id,
            "history_messages": identity.history_messages,
        }
    )
    return AgentChatTurn(
        context=context,
        is_admin=_is_admin_payload(auth_payload),
        is_compatibility_facade=bool(context.get("compatibility_facade")),
    )
