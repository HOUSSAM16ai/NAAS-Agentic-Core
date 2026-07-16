"""بناء سياق الدردشة — history builders + حارس الكيان/الغموض + ذاكرة checkpoint.

مستخرَجة حرفياً من ``routes.py`` (D-168 Slice A1). تعتمد على ``chat_types`` (الثوابت)
و ``get_checkpointer`` فقط — لا تستورد من ``routes`` أبداً (طبقات باتجاه واحد).
"""

from __future__ import annotations

import asyncio
import logging
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from microservices.orchestrator_service.src.core.database import get_checkpointer

from .chat_types import (
    MAX_HISTORY_MESSAGES,
    MAX_HISTORY_SUMMARY_CHARS,
    MAX_HISTORY_SUMMARY_ITEMS,
    MissionEventEnvelope,
)

logger = logging.getLogger(__name__)


def _compress_text_for_context(content: str) -> str:
    """يضغط النص للسياق عبر إزالة الضوضاء وتوحيد المسافات وتقليص الطول."""
    collapsed = " ".join(content.replace("\x00", "").split())
    cleaned = collapsed.replace("```", "").strip()
    if len(cleaned) <= 260:
        return cleaned
    return f"{cleaned[:260]}…"


def _build_older_history_digest(rows: list[object]) -> str:
    """يبني ملخصًا موجزًا للرسائل الأقدم مع إزالة التكرارات البنيوية."""
    if not rows:
        return ""

    digest_items: list[str] = []
    seen: set[str] = set()
    current_size = 0
    for old_message in rows:
        role_value = getattr(old_message, "role", "")
        content_value = getattr(old_message, "content", "")
        role_label = "المستخدم" if str(role_value) == "user" else "المساعد"
        compact = _compress_text_for_context(str(content_value))
        if not compact:
            continue
        item = f"- {role_label}: {compact}"
        fingerprint = item.casefold()
        if fingerprint in seen:
            continue
        allowed = MAX_HISTORY_SUMMARY_CHARS - current_size
        if allowed <= 0:
            break
        if len(item) > allowed:
            item = f"{item[:allowed]}…"
        digest_items.append(item)
        seen.add(fingerprint)
        current_size += len(item)
        if len(digest_items) >= MAX_HISTORY_SUMMARY_ITEMS:
            break
    return "\n".join(digest_items)


def _build_langchain_messages(
    source_messages: list[dict[str, str]] | None,
) -> list[HumanMessage | AIMessage | SystemMessage]:
    """يبني نافذة سياق محدودة ويزيل التكرارات المتجاورة لتقليل تلوث السياق."""
    if not source_messages:
        return []

    normalized_messages: list[HumanMessage | AIMessage | SystemMessage] = []
    last_signature: tuple[str, str] | None = None
    for message in source_messages[-MAX_HISTORY_MESSAGES:]:
        role = message.get("role")
        content = str(message.get("content", "")).strip()
        if role not in {"user", "assistant", "system"} or not content:
            continue
        signature = (role, content)
        if signature == last_signature:
            continue
        if role == "user":
            normalized_messages.append(HumanMessage(content=content))
        elif role == "system":
            normalized_messages.append(SystemMessage(content=content))
        else:
            normalized_messages.append(AIMessage(content=content))
        last_signature = signature
    return normalized_messages


def _build_graph_messages_graph(
    *,
    objective: str,
    history_messages: list[dict[str, str]] | None,
    checkpointer_available: bool,
    checkpoint_has_state: bool,
) -> list[HumanMessage | AIMessage | SystemMessage]:
    """يبني رسائل الإدخال للرسم البياني مع مسار احتياطي صريح ضد عمى السياق."""
    latest_user_message = HumanMessage(content=objective)

    def _append_latest_if_missing(
        seeded: list[HumanMessage | AIMessage | SystemMessage],
    ) -> list[HumanMessage | AIMessage | SystemMessage]:
        """يضيف رسالة المستخدم الحالية فقط إذا لم تكن مكررة في نهاية القائمة."""
        if seeded:
            tail = seeded[-1]
            if isinstance(tail, HumanMessage):
                tail_content = str(getattr(tail, "content", "")).strip()
                if tail_content == objective.strip():
                    return seeded
        seeded.append(latest_user_message)
        return seeded

    import logging

    local_logger = logging.getLogger("routes")

    history_len = len(history_messages) if history_messages else 0
    local_logger.warning(
        f"[_build_graph_messages_graph] checkpointer_available={checkpointer_available}, "
        f"checkpoint_has_state={checkpoint_has_state}, history_messages_len={history_len}"
    )

    if checkpointer_available and checkpoint_has_state:
        # CONTEXT FIX: Checkpointer claims state, but what if it's truncated?
        # If DB history is manually injected and checkpointer has < DB history, we must seed from DB history.
        # But LangGraph checkpointer will auto-hydrate anyway. We just need to make sure we don't accidentally
        # strip history if it's NOT a real checkpointer. Since we fixed app.state.app_graph, it is the real one.
        # Therefore, delta is correct for the REAL checkpointer.
        local_logger.info(
            "[_build_graph_messages_graph] checkpointer active and has state -> passing ONLY latest user message."
        )
        return [latest_user_message]

    if history_messages:
        seeded = _build_langchain_messages(history_messages)
        return _append_latest_if_missing(seeded)

    # Fallback to rely purely on checkpointer ONLY if history is absent
    return [latest_user_message]


def _build_graph_messages_manual(
    *,
    objective: str,
    history_messages: list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    """يبني رسائل الإدخال لوكيل OrchestratorAgent اليدوي (بدون LangChain/Checkpointer)."""
    messages = []

    if history_messages:
        for msg in history_messages:
            role = msg.get("role")
            content = msg.get("content")
            if role and content:
                messages.append({"role": role, "content": content})

    # Add the latest objective if not a duplicate
    if not messages or messages[-1].get("content", "").strip() != objective.strip():
        messages.append({"role": "user", "content": objective})

    return messages


def _question_contains_explicit_entity(question: str) -> bool:
    """يتحقق مما إذا كان السؤال يحتوي كيانًا صريحًا بدل الضمير المرجعي."""
    normalized = question.strip()
    if not normalized:
        return False

    if re.search(r"\b(?:france|algeria|egypt|morocco|tunisia|germany|spain)\b", normalized, re.I):
        return True

    arabic_tokens_raw = [
        token.strip("؟،.!:؛") for token in re.findall(r"[\u0600-\u06FF]+", normalized) if token
    ]
    arabic_tokens = [token for token in arabic_tokens_raw if token]
    if not arabic_tokens:
        return False

    stop_words = {
        "ما",
        "ماذا",
        "من",
        "هي",
        "هو",
        "هل",
        "كم",
        "عدد",
        "في",
        "على",
        "عن",
        "الى",
        "إلى",
        "هذه",
        "هذا",
        "ذلك",
        "تلك",
        "الدولة",
        "البلد",
        "المدينة",
        "عاصمة",
        "عاصمتها",
        "سكانها",
        "عددها",
        "عددهم",
        "موقعها",
        "مساحتها",
        "حدثني",
        "اخبرني",
        "أخبرني",
        "قل",
        "تكلم",
        "احك",
    }
    return any(token not in stop_words and len(token) > 2 for token in arabic_tokens)


def _extract_recent_entity_anchor(history_messages: list[dict[str, str]] | None) -> str | None:
    """يستخرج مرساة كيان حديثة من آخر رسائل المستخدم كحل احتياطي ضد فقدان السياق."""
    if not history_messages:
        return None

    stop_words = {
        "و",
        "ما",
        "وما",
        "ماذا",
        "وماذا",
        "من",
        "هي",
        "هو",
        "هل",
        "كم",
        "عدد",
        "في",
        "على",
        "عن",
        "الى",
        "إلى",
        "هذه",
        "هذا",
        "ذلك",
        "تلك",
        "عاصمتها",
        "سكانها",
        "عددها",
        "موقعها",
        "مساحتها",
        "أين",
        "اين",
        "ايه",
        "تقع",
        "يقع",
        "توجد",
        "يوجد",
        "تقوم",
        "يقوم",
    }

    def _extract_from_text(content: str) -> str | None:
        english_entities = re.findall(
            r"\b(?:France|Algeria|Egypt|Morocco|Tunisia|Germany|Spain)\b",
            content,
            flags=re.IGNORECASE,
        )
        if english_entities:
            return english_entities[-1]

        arabic_tokens = [
            token.strip("؟،.!:؛") for token in re.findall(r"[\u0600-\u06FF]+", content) if token
        ]
        arabic_tokens = [token for token in arabic_tokens if token]
        candidate_tokens = [
            token for token in arabic_tokens if len(token) > 2 and token not in stop_words
        ]
        if candidate_tokens:
            return candidate_tokens[-1]
        return None

    for message in reversed(history_messages):
        if message.get("role") != "user":
            continue
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        extracted = _extract_from_text(content)
        if extracted:
            return extracted

    # Forensic fallback: if user turns were trimmed/lost, use assistant turns as a backup anchor source.
    for message in reversed(history_messages):
        if message.get("role") != "assistant":
            continue
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        extracted = _extract_from_text(content)
        if extracted:
            return extracted
    return None


def _augment_ambiguous_objective(
    objective: str,
    history_messages: list[dict[str, str]] | None,
) -> str:
    normalized = objective.strip()
    if not normalized:
        return normalized
    if not _is_ambiguous_followup(normalized):
        return normalized
    if _question_contains_explicit_entity(normalized):
        return normalized

    anchor = _extract_recent_entity_anchor(history_messages)
    if not anchor:
        return normalized

    # Deterministic rewriting rule
    if (
        "ها" in normalized
        or "هذا" in normalized
        or "هذه" in normalized
        or normalized.startswith("كيف")
        or normalized.startswith("لماذا")
        or normalized.startswith("كم")
    ):
        return f"{normalized} (مرجع سياقي إلزامي: {anchor})"
    return f"{normalized} (مرجع سياقي إلزامي: {anchor})"

    return normalized


def _context_gap_reason_for_followup(
    objective: str,
    history_messages: list[dict[str, str]] | None,
) -> str | None:
    """يكشف فجوة السياق للمتابعات الإحالية ويعيد سببًا صريحًا عند غياب المرساة."""
    normalized = objective.strip()
    if not normalized:
        return "EMPTY_OBJECTIVE"
    if not _is_ambiguous_followup(normalized):
        return None
    if _question_contains_explicit_entity(normalized):
        return None
    anchor = _extract_recent_entity_anchor(history_messages)
    if anchor:
        return None
    logger.info("[CONTEXT_GUARD] missing entity anchor for ambiguous follow-up")
    return "MISSING_ENTITY_ANCHOR"


async def _detect_checkpoint_state(thread_id: str) -> tuple[bool, bool]:
    """يفحص توفّر checkpointer ووجود حالة محفوظة للخيط الحالي بشكل آمن."""
    checkpointer = get_checkpointer()
    if checkpointer is None:
        return False, False

    try:
        checkpoint_config = {"configurable": {"thread_id": thread_id}}
        async with asyncio.timeout(1.5):
            checkpoint_tuple = await checkpointer.aget_tuple(checkpoint_config)
        return True, checkpoint_tuple is not None
    except Exception as exc:
        logger.warning(
            "[CHECKPOINTER] state probe failed for thread_id=%s; falling back to injected history. reason=%s",
            thread_id,
            exc,
        )
        return False, False


def _normalize_checkpoint_role(raw_role: object) -> str | None:
    """يوحد تسمية الدور القادمة من checkpointer إلى user/assistant/system."""
    if not isinstance(raw_role, str):
        return None
    normalized = raw_role.strip().casefold()
    if normalized in {"human", "user"}:
        return "user"
    if normalized in {"ai", "assistant"}:
        return "assistant"
    if normalized == "system":
        return "system"
    return None


def _normalize_checkpoint_content(raw_content: object) -> str:
    """يحوّل محتوى رسالة checkpointer إلى نص بسيط قابل للتمرير للسياق."""
    if isinstance(raw_content, str):
        return raw_content.strip()
    if isinstance(raw_content, list):
        chunks: list[str] = []
        for item in raw_content:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    chunks.append(text)
                continue
            if isinstance(item, dict):
                raw_text = item.get("text")
                if isinstance(raw_text, str):
                    text = raw_text.strip()
                    if text:
                        chunks.append(text)
        return " ".join(chunks).strip()
    return ""


def _normalize_checkpoint_message(message: object) -> dict[str, str] | None:
    """يستخرج role/content من رسالة checkpointer مع توافق لأشكال LangChain المختلفة."""
    role = _normalize_checkpoint_role(getattr(message, "type", None))
    if role is None and isinstance(message, dict):
        role = _normalize_checkpoint_role(message.get("role"))
    if role is None:
        role = _normalize_checkpoint_role(getattr(message, "role", None))
    if role is None:
        return None

    content = _normalize_checkpoint_content(getattr(message, "content", None))
    if not content and isinstance(message, dict):
        content = _normalize_checkpoint_content(message.get("content"))
    if not content:
        return None

    return {"role": role, "content": content}


async def _extract_checkpoint_history(
    thread_id: str,
    max_messages: int = MAX_HISTORY_MESSAGES,
) -> list[dict[str, str]]:
    """يقرأ سجل الرسائل من checkpointer ليُستخدم كنسخة احتياطية عند فقدان التاريخ المحقون."""
    checkpointer = get_checkpointer()
    if checkpointer is None:
        return []

    try:
        checkpoint_config = {"configurable": {"thread_id": thread_id}}
        async with asyncio.timeout(1.5):
            checkpoint = await checkpointer.aget(checkpoint_config)
    except Exception as exc:
        logger.warning(
            "[CHECKPOINTER] history extraction failed for thread_id=%s; reason=%s",
            thread_id,
            exc,
        )
        return []

    if checkpoint is None:
        return []

    raw_channel_values = getattr(checkpoint, "channel_values", None)
    if not isinstance(raw_channel_values, dict):
        return []
    raw_messages = raw_channel_values.get("messages")
    if not isinstance(raw_messages, list):
        return []

    normalized_history: list[dict[str, str]] = []
    for raw_message in raw_messages[-max_messages:]:
        normalized = _normalize_checkpoint_message(raw_message)
        if normalized is None:
            continue
        normalized_history.append(normalized)
    return normalized_history


def _is_ambiguous_followup(query: str) -> bool:
    """يكتشف الاستعلامات الإحالية القصيرة التي تحتاج سياقًا صريحًا."""
    normalized = query.strip().casefold()
    if not normalized:
        return False
    triggers = (
        "عاصمتها",
        "عاصمته",
        "عاصمتهم",
        "عدد سكانها",
        "عدد سكانه",
        "سكانها",
        "سكانه",
        "موقعها",
        "موقعه",
        "اين تقعها",
        "أين تقعها",
        "where is it",
        "where is she",
        "where is he",
        "what is its population",
        "how many people live there",
        "what is its",
        "its capital",
        "their capital",
    )
    if any(trigger in normalized for trigger in triggers):
        return True

    demonstratives = ("هذا", "هذه", "ذلك", "تلك", "هاته", "there", "this", "that")
    followup_nouns = (
        "الدولة",
        "البلد",
        "المدينة",
        "الكيان",
        "الدالة",
        "المعادلة",
        "التمرين",
        "السؤال",
        "function",
        "equation",
        "problem",
    )
    if any(word in normalized for word in demonstratives) and any(
        noun in normalized for noun in followup_nouns
    ):
        return True

    vague_leads = ("كيف جاءت", "كيف حصل", "كيف صارت", "لماذا جاءت", "كيف طلعت")
    if any(normalized.startswith(prefix) for prefix in vague_leads):
        return True

    tokens = normalized.split()
    pronoun_like_terms = {
        "عاصمتها",
        "عاصمته",
        "عاصمتهم",
        "عاصمتها؟",
        "عاصمته؟",
        "عاصمتهم؟",
        "سكانها",
        "سكانه",
        "سكانها؟",
        "سكانه؟",
        "عددهم",
        "عددها",
    }
    return len(tokens) <= 6 and any(token in pronoun_like_terms for token in tokens)


def _canonicalize_mission_event(event: object) -> MissionEventEnvelope | None:
    """يوحّد أشكال الحدث التاريخية إلى غلاف داخلي ثابت مع توافق رجعي عند الحافة."""

    if not isinstance(event, dict):
        return None

    raw_event_type = event.get("event_type")
    if not isinstance(raw_event_type, str) or not raw_event_type.strip():
        return None

    payload_candidate = event.get("payload_json")
    if not isinstance(payload_candidate, dict):
        payload_candidate = event.get("data")
    if not isinstance(payload_candidate, dict):
        payload_candidate = {}

    return {"event_type": raw_event_type, "data": payload_candidate}
