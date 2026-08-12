"""بناء سياق دور الدردشة من حمولة العميل — ورقةٌ بلا اعتماديات على الأشقّاء (ISS-155).

تُستخرَج هنا الأجزاء الثلاثة التي كانت مكرَّرة **حرفياً** في توأمَي WebSocket
(`chat_ws_stategraph` و`admin_chat_ws_stategraph`): قسر سياق العميل، واستنتاج
`mission_type`، وحارس الترطيب.

## لماذا وحدةٌ منفصلة عن `chat_ws_turn`

درس D-237/ADR-009 (البند ٣): أوّل استخراجٍ هناك نقل المولّدَين سليمَين، فقاست
البوّابة `cc 35` و`عمق 11` في الوحدة الجديدة — **دالّةٌ إلهية استُبدلت بوحدةٍ
إلهية**، وهو نمط الفشل السادس في البروتوكول. الفصل هنا **بالمسؤولية وقبل أوّل
قياس**: هذه الوحدة تعرف الحمولة الواردة ولا تعرف المقبس ولا قاعدة البيانات.

وهي **ورقة** عمداً: لا تستورد إلّا `chat_types` و`context_utils`. فأيّ مستهلكٍ
لاحق (مسار HTTP مثلاً) يأخذها بلا أن يجرّ معه آلة الدور كاملةً.
"""

from __future__ import annotations

import logging

from .chat_types import ChatRunContext
from .context_utils import _extract_client_context_messages, _merge_history_with_client_context

logger = logging.getLogger(__name__)


def _extract_chat_objective(payload: dict[str, object]) -> str | None:
    """يستخلص الهدف النصي للدردشة من حمولة عامة بشكل صريح وآمن.

    نُقلت من `routes.py` حرفياً: الدالّة يحتاجها مسارا WS **و**HTTP، والسور
    أحاديّ الاتجاه (`tests/architecture/test_chat_canonical_and_ownership_fences.py`)
    يمنع `chat_ws_turn` من الاستيراد من `.routes`. `routes.py` يُعيد تصديرها.
    """
    question = payload.get("question")
    if isinstance(question, str) and question.strip():
        return question.strip()
    objective = payload.get("objective")
    if isinstance(objective, str) and objective.strip():
        return objective.strip()
    return None


def _coerce_client_context(raw: object) -> ChatRunContext:
    """يبني سياقاً من حمولة العميل، متجاهلاً كلّ مفتاحٍ ليس سلسلة.

    نقلٌ حرفيّ من التوأمين: الحمولة تأتي من الشبكة، فالمفتاح غير النصّي يُتجاهَل
    بصمت بدل أن يُسقِط الدور.
    """
    context: ChatRunContext = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if not isinstance(key, str):
                continue
            context[key] = value
    return context


def _mission_type_in_metadata(incoming: dict[str, object]) -> bool:
    """هل تحمل الحمولة `mission_type` داخل `metadata` القاموسي؟"""
    metadata = incoming.get("metadata")
    return isinstance(metadata, dict) and "mission_type" in metadata


def _apply_mission_type(context: ChatRunContext, incoming: dict[str, object]) -> None:
    """ينقل `mission_type` من الحمولة إلى السياق — العلويّ يسبق المُعشَّش.

    الأسبقيّة جزءٌ من العقد لا تفصيلُ تنفيذ (D-206 · L2)، ويحرسها سيناريو
    `mission_type_both_top_level_wins` في عقد الترانسكريبت.
    """
    if "mission_type" in incoming:
        context["mission_type"] = incoming["mission_type"]
    elif _mission_type_in_metadata(incoming):
        context["mission_type"] = incoming["metadata"]["mission_type"]


def _hydrate_history(
    history_messages: list[dict[str, str]], incoming: dict[str, object]
) -> list[dict[str, str]]:
    """يدمج سياق العميل مع تاريخ قاعدة البيانات — ويسقط إلى التاريخ وحده عند أيّ فشل.

    الحارس يلفّ **الدمج والاستخراج معاً** كما في الأصل: فشلُ أيٍّ منهما يعني أنّ
    الترطيب لم يتمّ، والتاريخ المخزَّن أصدق من دمجٍ نصفيّ.
    """
    try:
        client_context = _extract_client_context_messages(incoming)
        return _merge_history_with_client_context(history_messages, client_context)
    except Exception as e:
        logger.error(
            "[HYDRATION_GUARD] Context hydration failed — "
            f"falling back to DB history only. "
            f"Error: {type(e).__name__}: {e}"
        )
        return history_messages
