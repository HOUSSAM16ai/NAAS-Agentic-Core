"""أنواع وثوابت مسار الدردشة — الوحدة الورقية (leaf) لطبقات D-168.

مستخرَجة حرفياً من ``routes.py`` (D-168 Slice A1): لا تستورد من أي وحدة شقيقة **وقت
التشغيل** — كل وحدات ``chat_support`` و ``routes.py`` تستورد منها (طبقات باتجاه واحد،
درء الدورات). استيرادُ نوعٍ تحت ``TYPE_CHECKING`` لا يُنشئ اقتراناً وقت التشغيل ولا
يُغيّر رسم الاستيراد، فهو مسموح — والبديل عنه أن يُعلَن مفتاحٌ حقيقي بنوعٍ كاذب.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # لا استيراد وقت التشغيل — النوع للتحقّق الساكن وحده.
    from .trace_utils import OrchestratorTraceContext

MAX_HISTORY_MESSAGES = 24
MAX_CHECKPOINT_ANCHOR_MESSAGES = 4
MAX_HISTORY_SUMMARY_MESSAGES = 40
MAX_HISTORY_SUMMARY_CHARS = 2400
MAX_HISTORY_SUMMARY_ITEMS = 18


class ChatRunContext(TypedDict, total=False):
    """غلاف سياقي محدود لمسار تشغيل الدردشة لتجنّب القواميس المفتوحة في الحدود الحرجة.

    ⚠️ **العقد يُعلَن كاملاً أو لا يكون عقداً** (صنف ISS-152): كانت ثلاثة مفاتيح
    تُكتَب وتُقرأ وقت التشغيل بلا إعلان هنا — ``trace_context`` (يكتبها
    ``agent_chat_request`` و``chat_stream_engine``، وتقرأها ``agent_chat_admin_stream``
    بـ``tc.trace_id``) · ``history_messages`` (يقرأها الوكيل في أربعة مواضع) ·
    ``compatibility_facade`` (مصافحة §6.5). وكان ``conversation_id`` مُعلَناً
    ``int | str`` بينما ``ChatRequest`` يُصرّح ``int | None`` — فالقيمة الحقيقية لم
    تكن ضمن النوع المُعلَن أصلاً. غلافٌ «محدود» لا يذكر ما يحمله ليس حدّاً بل إيهامُ حدّ.
    """

    mission_type: str
    conversation_id: int | str | None
    thread_id: int | str
    session_id: int | str
    user_id: int
    #: تاريخ المحادثة المُمرَّر مع الدور — يقرأه الوكيل (`overmind/agents/orchestrator`).
    history_messages: list[dict[str, str]]
    #: أثر التتبّع الصادر — يُقرأ بـ`tc.trace_id` عند بناء `config`.
    trace_context: OrchestratorTraceContext
    #: مصافحة §6.5: المونوليث يملك رسالة المستخدم فلا يكتبها الأوركستريتور.
    compatibility_facade: bool
    # D-103: محتوى تمرين محقون من الـ monolith (شرح-بسياق عبر الرسم الـ13-node)
    exercise_content: str
    exercise_ref: str
    # D-115: درجة سُلّم الدعم (1..5) — تحكم عمق التلميح السقراطي في SynthesizerNode.
    support_level: int


# D-103: سقف حجم المحتوى المحقون — أكبر تمرين معروف ~9.7K حرف؛ 16K هامش آمن.
_INJECTED_EXERCISE_MAX_CHARS = 16000


def _extract_injected_exercise(context: ChatRunContext | None) -> str:
    """يستخرج محتوى التمرين المحقون من سياق الطلب — str نظيف أو "" (D-103)."""
    if not isinstance(context, dict):
        return ""
    raw = context.get("exercise_content")
    if not isinstance(raw, str):
        return ""
    return raw.strip()[:_INJECTED_EXERCISE_MAX_CHARS]


def _extract_support_level(context: ChatRunContext | None) -> int:
    """D-114/D-115: يستخرج support_level من السياق (clamp 1..5، افتراض آمن = 5/محجوب)."""
    if not isinstance(context, dict):
        return 5
    raw = context.get("support_level")
    try:
        level = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 5
    return level if 1 <= level <= 5 else 5


class MissionEventEnvelope(TypedDict):
    """العقد الداخلي القياسي لبث أحداث المهمات عبر WebSocket."""

    event_type: str
    data: dict[str, object]


class StreamFrame(BaseModel):
    """يمثل إطارًا موحّدًا لبث الدردشة ويفصل نص المستخدم عن الإشارات التحكمية."""

    type: str
    payload: dict[str, object] = Field(default_factory=dict)
