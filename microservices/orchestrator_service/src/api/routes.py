import asyncio
import json
import logging
import os
import re
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import TypedDict

import anyio
import httpx
import jwt
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from microservices.orchestrator_service.src.api.context_utils import (
    _extract_client_context_messages,
    _merge_history_with_client_context,
)
from microservices.orchestrator_service.src.contracts.admin_tools import ADMIN_TOOL_CONTRACT
from microservices.orchestrator_service.src.core.config import get_settings
from microservices.orchestrator_service.src.core.database import (
    async_session_factory,
    get_checkpointer,
    get_db,
)
from microservices.orchestrator_service.src.core.event_bus import get_event_bus
from microservices.orchestrator_service.src.core.prom_metrics import (
    record_pipeline_error,
    record_pipeline_invocation,
    record_streaming_chunk,
    record_streaming_session,
    set_pipeline_active,
)
from microservices.orchestrator_service.src.core.security import (
    decode_user_id,
    extract_bearer_token,
    extract_websocket_auth,
)
from microservices.orchestrator_service.src.models.mission import Mission
from microservices.orchestrator_service.src.services.llm.client import get_ai_client
from microservices.orchestrator_service.src.services.overmind.agents.orchestrator import (
    OrchestratorAgent,
)
from microservices.orchestrator_service.src.services.overmind.domain.api_schemas import (
    MissionCreate,
    MissionEventResponse,
    MissionResponse,
)
from microservices.orchestrator_service.src.services.overmind.entrypoint import start_mission
from microservices.orchestrator_service.src.services.overmind.state import MissionStateManager
from microservices.orchestrator_service.src.services.overmind.utils.tools import tool_registry
from microservices.orchestrator_service.src.services.skills_pipeline import run_skills_pipeline
from microservices.orchestrator_service.src.services.tools.registry import get_registry

logger = logging.getLogger(__name__)

active_background_tasks = set()
MAX_HISTORY_MESSAGES = 24
MAX_CHECKPOINT_ANCHOR_MESSAGES = 4
MAX_HISTORY_SUMMARY_MESSAGES = 40
MAX_HISTORY_SUMMARY_CHARS = 2400
MAX_HISTORY_SUMMARY_ITEMS = 18

type JsonObject = dict[str, object]


class ChatRunContext(TypedDict, total=False):
    """غلاف سياقي محدود لمسار تشغيل الدردشة لتجنّب القواميس المفتوحة في الحدود الحرجة."""

    mission_type: str
    conversation_id: int | str
    thread_id: int | str
    session_id: int | str
    user_id: int
    # D-103: محتوى تمرين محقون من الـ monolith (شرح-بسياق عبر الرسم الـ13-node)
    exercise_content: str
    exercise_ref: str
    # D-114: درجة سُلّم الدعم (1..5) + توجيه المثال المحلول للمبتدئ المطلق.
    support_level: int
    worked_example_directive: str


# D-103: سقف حجم المحتوى المحقون — أكبر تمرين معروف ~9.7K حرف؛ 16K هامش آمن.
_INJECTED_EXERCISE_MAX_CHARS = 16000
# D-114: سقف توجيه المثال المحلول (نص قصير منظَّم).
_WORKED_EXAMPLE_DIRECTIVE_MAX_CHARS = 4000


def _extract_injected_exercise(context: ChatRunContext | None) -> str:
    """يستخرج محتوى التمرين المحقون من سياق الطلب — str نظيف أو "" (D-103)."""
    if not isinstance(context, dict):
        return ""
    raw = context.get("exercise_content")
    if not isinstance(raw, str):
        return ""
    return raw.strip()[:_INJECTED_EXERCISE_MAX_CHARS]


def _extract_support_level(context: ChatRunContext | None) -> int:
    """D-114: يستخرج support_level من السياق (clamp 1..5، افتراض آمن = 5/محجوب)."""
    if not isinstance(context, dict):
        return 5
    raw = context.get("support_level")
    try:
        level = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 5
    return level if 1 <= level <= 5 else 5


def _extract_worked_example_directive(context: ChatRunContext | None) -> str:
    """D-114: يستخرج توجيه المثال المحلول المحقون — str نظيف أو "" (للمبتدئ المطلق)."""
    if not isinstance(context, dict):
        return ""
    raw = context.get("worked_example_directive")
    if not isinstance(raw, str):
        return ""
    return raw.strip()[:_WORKED_EXAMPLE_DIRECTIVE_MAX_CHARS]


class MissionEventEnvelope(TypedDict):
    """العقد الداخلي القياسي لبث أحداث المهمات عبر WebSocket."""

    event_type: str
    data: dict[str, object]


class StreamFrame(BaseModel):
    """يمثل إطارًا موحّدًا لبث الدردشة ويفصل نص المستخدم عن الإشارات التحكمية."""

    type: str
    payload: dict[str, object] = Field(default_factory=dict)


def _resolve_session_id_from_incoming(incoming: dict[str, object]) -> str | None:
    """يستخرج session_id بشكل صريح من الحمولة أو من context لدعم تشخيص ثبات الهوية."""
    direct_session = incoming.get("session_id")
    if isinstance(direct_session, str) and direct_session.strip():
        return direct_session.strip()

    context_payload = incoming.get("context")
    if isinstance(context_payload, dict):
        context_session = context_payload.get("session_id")
        if isinstance(context_session, str) and context_session.strip():
            return context_session.strip()
    return None


def _emit_identity_diagnostic_log(
    *,
    route_name: str,
    conversation_id: int | str,
    thread_id: str | None,
    session_id: str | None,
) -> None:
    """يسجل بصمة الهوية لكل رسالة مع معلومات الحاوية لتأكيد تغيّر المسار أو ثباته."""
    orchestrator_instance_id = os.getenv("ORCHESTRATOR_INSTANCE_ID", "").strip() or "unset"
    hostname = os.getenv("HOSTNAME", "").strip() or "unknown"
    container_id = hostname
    logger.info(
        "[IDENTITY_DIAGNOSTIC] route=%s conversation_id=%s thread_id=%s session_id=%s "
        "orchestrator_instance_id=%s hostname=%s container_id=%s",
        route_name,
        conversation_id,
        thread_id or "missing",
        session_id or "missing",
        orchestrator_instance_id,
        hostname,
        container_id,
    )


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


async def _append_telemetry_line(line: str) -> None:
    """يكتب سطر تتبع حرج إلى ملف أدلة قابل للفحص خارج مخرجات الطرفية."""
    import os

    import anyio

    def write_sync():
        path = os.path.join(os.getenv("STATE_DIR", "/app"), "telemetry_evidence.txt")
        with open(path, "a", encoding="utf-8") as telemetry_file:
            telemetry_file.write(f"{line}\n")

    await anyio.to_thread.run_sync(write_sync)


router = APIRouter(
    tags=["Overmind (Super Agent)"],
)

_conv_service_client: httpx.AsyncClient | None = None


async def get_conv_service_client() -> httpx.AsyncClient:
    global _conv_service_client
    if _conv_service_client is None or _conv_service_client.is_closed:
        _conv_service_client = httpx.AsyncClient(
            base_url=os.getenv("CONVERSATION_SERVICE_URL", "http://conversation-service:8010"),
            timeout=10.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _conv_service_client


async def close_conv_service_client() -> None:
    if _conv_service_client and not _conv_service_client.is_closed:
        await _conv_service_client.aclose()


class OutboxRelayResponse(BaseModel):
    """استجابة تشغيل relay اليدوي لسجلات outbox."""

    processed: int
    published: int
    failed: int
    skipped: int


class OutboxStatusResponse(BaseModel):
    """استجابة تلخص الحالة التشغيلية لطابور outbox."""

    pending: int
    processing: int
    failed: int
    published: int
    oldest_pending_age_seconds: int | None
    generated_at: str


def _is_admin_payload(payload: dict[str, object]) -> bool:
    """يتحقق من صلاحيات الإدارة داخل حمولة JWT وفق مبدأ أقل صلاحية وfail-closed."""
    role = str(payload.get("role", "")).lower().strip()
    scope_text = str(payload.get("scope", "")).lower()
    has_admin_role = role in {"admin", "super_admin", "superadmin"}
    has_admin_flag = payload.get("is_admin") is True
    has_admin_scope = "admin" in scope_text and "tool" in scope_text
    return has_admin_role or has_admin_flag or has_admin_scope


def _coerce_admin_state(payload: dict[str, object] | None = None) -> dict[str, object]:
    """يبني حالة إدارة ضيقة ومتوافقة لعقدة التحكم دون توسيع الواجهة العامة."""

    safe_payload = payload or {}
    role = str(safe_payload.get("role", "")).strip().lower()
    scope = str(safe_payload.get("scope", "")).strip().lower()
    is_admin = _is_admin_payload(safe_payload)
    return {
        "is_admin": is_admin,
        "user_role": role,
        "scope": scope,
    }


def _merge_admin_inputs(
    base_inputs: dict[str, object], admin_payload: dict[str, object] | None
) -> dict[str, object]:
    """يحقن غلاف الإدارة الموحد فقط عند الحاجة، مع إبقاء المسارات الأخرى دون تغيير."""

    if admin_payload is None:
        return base_inputs
    return {**base_inputs, **_coerce_admin_state(admin_payload)}


async def require_internal_admin_access(
    authorization: str | None = Header(default=None),
    x_internal_admin_key: str | None = Header(default=None),
) -> int:
    """يفرض مصادقة وتفويضاً مغلقين لمسارات الأدوات عبر مفتاح داخلي أو JWT إداري صريح."""
    settings = get_settings()

    if (
        x_internal_admin_key
        and settings.ADMIN_TOOL_API_KEY
        and x_internal_admin_key == settings.ADMIN_TOOL_API_KEY
    ):
        return 0

    token = extract_bearer_token(authorization)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if not _is_admin_payload(payload):
        raise HTTPException(status_code=403, detail="forbidden")

    user_id = int(payload.get("sub", payload.get("user_id", 0)) or 0)
    if user_id <= 0:
        raise HTTPException(status_code=403, detail="forbidden")
    return user_id


def _safe_assistant_error(request_id: str) -> str:
    """يبني رسالة خطأ آمنة للمستخدم دون أي تسريب تشخيصي داخلي."""
    return f"تعذر معالجة طلب الدردشة حالياً. رقم المتابعة: {request_id}"


def _safe_conversation_id(raw_value: object) -> int | None:
    """يحوّل conversation_id بشكل آمن لدعم int أو string رقمي مع تتبع تشخيصي واضح."""
    if raw_value is None:
        return None
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if not stripped:
            return None
        try:
            parsed = int(stripped)
            logger.warning(
                "[CONV_ID_TYPE] Received conversation_id as string '%s' and converted to int=%s",
                raw_value,
                parsed,
            )
            return parsed
        except ValueError:
            logger.error(
                "[CONV_ID_TYPE] Invalid numeric conversion for conversation_id='%s'; using None",
                raw_value,
            )
            return None

    logger.error(
        "[CONV_ID_TYPE] Unexpected conversation_id type=%s; using None",
        type(raw_value).__name__,
    )
    return None


def _resolve_effective_conversation_id(
    *, incoming_value: object, sticky_value: int | None
) -> int | None:
    """يحدّد conversation_id النهائي مع أولوية للطلب الحالي ثم ذاكرة الاتصال."""
    parsed = _safe_conversation_id(incoming_value)
    if parsed is not None:
        return parsed
    return sticky_value


def _safe_thread_id(raw_value: object) -> str | None:
    """يطبّع thread_id لدعم int/str مع رفض القيم الفارغة."""
    if raw_value is None:
        return None
    if isinstance(raw_value, int):
        return str(raw_value)
    if isinstance(raw_value, str):
        normalized = raw_value.strip()
        if normalized:
            return normalized
    return None


def _resolve_thread_id(context: ChatRunContext, fallback_conversation_id: int | str) -> str:
    """يستخرج thread_id ثابتًا من السياق مع عزل المستخدم."""
    explicit = _safe_thread_id(context.get("thread_id"))
    if explicit:
        return explicit

    conv_id = context.get("conversation_id", fallback_conversation_id)
    user_id = context.get("user_id")
    if user_id is None:
        raise ValueError(
            f"[THREAD_RESOLUTION] user_id required for safe thread binding. conv_id={conv_id!r}"
        )
    return f"u{user_id}:c{conv_id}"


def _build_conversation_thread_id(user_id: int, conversation_id: int | str) -> str:
    """يبني معرف خيط حتمي خاص بالمحادثة لضمان ثبات checkpointer بين الأدوار."""
    return f"u{user_id}:c{conversation_id}"


def _conversation_id_from_scoped_thread(thread_id: str, user_id: int) -> int | None:
    """يستخرج conversation_id من thread_id مقيّد بالمستخدم: u<uid>:c<cid>."""
    normalized = thread_id.strip()
    match = re.fullmatch(r"u(\d+):c(\d+)", normalized)
    if not match:
        return None
    scoped_user_id = int(match.group(1))
    if scoped_user_id != user_id:
        return None
    return int(match.group(2))


def _decode_auth_payload_or_401(authorization: str | None) -> tuple[int, dict[str, object]]:
    """يفك JWT من ترويسة Authorization ويعيد user_id والحمولة مع فشل مغلق."""
    token = extract_bearer_token(authorization)
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    user_id = int(payload.get("sub", payload.get("user_id", 0)) or 0)
    if user_id <= 0:
        raise HTTPException(status_code=401, detail="Invalid user")
    return user_id, payload


async def _serialize_json_async(payload: object) -> str:
    """يُسلسل الحمولة إلى JSON داخل خيط منفصل لحماية حلقة الأحداث من الحجب."""
    return await anyio.to_thread.run_sync(lambda p: json.dumps(p, ensure_ascii=False), payload)


# ─────────────────────────────────────────────────────────────────────────────
# ISS-056 (D-049 — JSON Envelope Anti-Leak Doctrine):
# SynthesizerNode في graph/search.py يُرجِع `final_response` كـ dict بمظروف:
#   {"المصدر": ..., "مستوى_الثقة": ..., "التمرين": <نص حقيقي للطالب>,
#    "السنة": ..., "الشعبة": ..., "المادة": ..., "رقم_التمرين": ...}
#
# قبل الإصلاح: `_serialize_json_async(final_resp)` كان يُسلسل المظروف كاملاً كـ
# JSON ويرسله للطالب → كارثة تظهر فيها {"المصدر":"معرفة مادة"... } مكشوفة.
#
# بعد الإصلاح: نستخرج الحقل البشري (`التمرين`/`الإجابة`/`response`) فقط.
# هذه الدالة **يجب** أن تُستخدم في كل مكان يُحوَّل فيه `final_response` إلى نص
# للمستخدم النهائي. لا تُسلسل dict خام كـ JSON إلى assistant_delta/final أبداً.
# ─────────────────────────────────────────────────────────────────────────────
_HUMAN_RESPONSE_FIELDS: tuple[str, ...] = (
    "التمرين",  # SynthesizerNode envelope
    "الإجابة",  # AdminAgentNode / RenderAnswerNode envelope
    "response",
    "answer",
    "content",
    "text",
    "final_response",  # nested fallback
)


def _extract_human_readable_response(final_resp: object) -> str:
    """يستخرج النص البشري من `final_response` بدون تسريب مظروف JSON.

    يحل ISS-056 — JSON Envelope Leak Catastrophe.

    قواعد دائمة:
    - dict مع حقل بشري معروف (`التمرين`/`الإجابة`/…) → النص فقط
    - dict مع حقل خطأ (`خطأ`) → رسالة خطأ نظيفة بالعربية
    - dict بدون حقل بشري → "لا توجد تفاصيل متاحة." (لا dump للمظروف)
    - str → التنظيف فقط
    - None → الـ fallback الافتراضي
    """
    if isinstance(final_resp, dict):
        # حالة الخطأ من RenderAnswerNode — رسالة نظيفة، لا dump
        error_msg = final_resp.get("خطأ")
        if isinstance(error_msg, str) and error_msg.strip():
            action = str(final_resp.get("الإجراء", "")).strip()
            tail = f"\n\n{action}" if action else ""
            return f"حدث خطأ أثناء معالجة طلبك: {error_msg.strip()}{tail}"

        for key in _HUMAN_RESPONSE_FIELDS:
            value = final_resp.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            # حالة nested: قد يكون response_json داخل response_json
            if isinstance(value, dict):
                nested = _extract_human_readable_response(value)
                if nested and nested != "لا توجد تفاصيل متاحة.":
                    return nested

        # dict بدون حقل بشري معروف — لا تكشف المظروف الداخلي للطالب
        return "لا توجد تفاصيل متاحة."

    if final_resp is None:
        return "لا توجد تفاصيل متاحة."

    text = str(final_resp).strip()
    return text or "لا توجد تفاصيل متاحة."


async def _serialize_stream_frame(payload: object) -> str:
    """يبني NDJSON صارمًا لضمان عدم تسريب dict خام إلى عميل البث النصي."""
    return _serialize_stream_frame_sync(payload)


def _serialize_stream_frame_sync(payload: object) -> str:
    """سريع، متزامن، آمن لـ event loop."""
    if isinstance(payload, dict):
        frame = StreamFrame.model_validate(payload).model_dump()
    else:
        frame = StreamFrame(type="assistant_delta", payload={"content": str(payload)}).model_dump()
    return json.dumps(frame, ensure_ascii=False) + "\n"


@router.get(
    "/api/v1/system/outbox/status",
    response_model=OutboxStatusResponse,
    tags=["System"],
    dependencies=[Depends(require_internal_admin_access)],
)
async def outbox_status(db: AsyncSession = Depends(get_db)) -> OutboxStatusResponse:
    """يعرض لقطة تشغيلية آمنة عن outbox دون تعديل أي بيانات."""

    manager = MissionStateManager(session=db)
    snapshot = await manager.get_outbox_operational_snapshot()
    return OutboxStatusResponse(**snapshot)


@router.post(
    "/api/v1/system/outbox/relay",
    response_model=OutboxRelayResponse,
    tags=["System"],
    dependencies=[Depends(require_internal_admin_access)],
)
async def trigger_outbox_relay(
    batch_size: int = 50,
    max_failed_attempts: int = 3,
    processing_timeout_seconds: int = 300,
    db: AsyncSession = Depends(get_db),
) -> OutboxRelayResponse:
    """يشغل relay يدويًا بشكل آمن مع حدود واضحة للدفعة والمحاولات."""

    normalized_batch_size = max(1, min(batch_size, 200))
    normalized_attempts = max(1, min(max_failed_attempts, 10))
    normalized_processing_timeout = max(5, min(processing_timeout_seconds, 3600))

    manager = MissionStateManager(session=db)
    summary = await manager.relay_outbox_events(
        batch_size=normalized_batch_size,
        max_failed_attempts=normalized_attempts,
        processing_timeout_seconds=normalized_processing_timeout,
    )
    return OutboxRelayResponse(**summary)


# MCP Admin Tool Endpoints dynamically generated from contract
for tool_name in ADMIN_TOOL_CONTRACT:

    def _make_invoke(name: str):
        async def invoke_admin_tool(payload: JsonObject | None = None) -> JsonObject:
            if payload is None:
                payload = {}
            tool_fn = get_registry().get(name)
            if not tool_fn:
                raise HTTPException(status_code=404, detail="Tool not found in registry")

            try:
                import asyncio

                if hasattr(tool_fn, "ainvoke"):
                    result = await tool_fn.ainvoke(payload)
                elif asyncio.iscoroutinefunction(tool_fn) or asyncio.iscoroutinefunction(
                    getattr(tool_fn, "invoke", None)
                ):
                    result = await tool_fn(**payload)
                elif hasattr(tool_fn, "invoke"):
                    result = tool_fn.invoke(payload)
                else:
                    result = tool_fn(**payload)

                return {"status": "success", "result": result}
            except Exception:
                request_id = str(uuid.uuid4())
                logger.error(
                    "Admin tool invocation failed",
                    exc_info=True,
                    extra={"request_id": request_id, "tool_name": name},
                )
                return {
                    "status": "error",
                    "message": f"Tool execution failed. request_id={request_id}",
                }

        invoke_admin_tool.__name__ = f"invoke_admin_tool_{name.replace('.', '_')}"
        return invoke_admin_tool

    def _make_schema(name: str):
        async def get_admin_tool_schema() -> JsonObject:
            return {"name": name, "description": ADMIN_TOOL_CONTRACT.get(name), "parameters": {}}

        get_admin_tool_schema.__name__ = f"get_admin_tool_schema_{name.replace('.', '_')}"
        return get_admin_tool_schema

    def _make_health(name: str):
        async def get_admin_tool_health() -> JsonObject:
            tool_fn = get_registry().get(name)
            return {"name": name, "status": "healthy" if tool_fn else "unavailable"}

        get_admin_tool_health.__name__ = f"get_admin_tool_health_{name.replace('.', '_')}"
        return get_admin_tool_health

    router.post(
        f"/api/v1/tools/{tool_name}/invoke",
        tags=["Admin MCP Tools"],
        dependencies=[Depends(require_internal_admin_access)],
        operation_id=f"invoke_tool_{tool_name.replace('.', '_')}",
    )(_make_invoke(tool_name))

    router.get(
        f"/api/v1/tools/{tool_name}/schema",
        tags=["Admin MCP Tools"],
        dependencies=[Depends(require_internal_admin_access)],
        operation_id=f"get_schema_tool_{tool_name.replace('.', '_')}",
    )(_make_schema(tool_name))

    router.get(
        f"/api/v1/tools/{tool_name}/health",
        tags=["Admin MCP Tools"],
        dependencies=[Depends(require_internal_admin_access)],
        operation_id=f"get_health_tool_{tool_name.replace('.', '_')}",
    )(_make_health(tool_name))


class ChatRequest(BaseModel):
    question: str
    user_id: int
    conversation_id: int | None = None
    history_messages: list[dict[str, str]] = Field(default_factory=list)
    context: dict[str, object] = Field(default_factory=dict)


def _extract_chat_objective(payload: dict[str, object]) -> str | None:
    """يستخلص الهدف النصي للدردشة من حمولة عامة بشكل صريح وآمن."""
    question = payload.get("question")
    if isinstance(question, str) and question.strip():
        return question.strip()
    objective = payload.get("objective")
    if isinstance(objective, str) and objective.strip():
        return objective.strip()
    return None


async def _create_new_conversation(
    user_id: int, question: str, is_admin_scope: bool, session: AsyncSession
) -> int:
    create_query = (
        text(
            "INSERT INTO admin_conversations (title, user_id) VALUES (:title, :user_id) RETURNING id"
        )
        if is_admin_scope
        else text(
            "INSERT INTO customer_conversations (title, user_id) VALUES (:title, :user_id) RETURNING id"
        )
    )
    title = question.strip()[:120] or "Super Agent Mission"
    try:
        async with asyncio.timeout(5.0):
            created = await session.execute(create_query, {"title": title, "user_id": user_id})
    except TimeoutError as e:
        raise HTTPException(
            status_code=504, detail="Database timeout during conversation creation"
        ) from e
    created_id = created.scalar_one_or_none()
    if created_id is None:
        raise HTTPException(status_code=500, detail="failed to create conversation")
    return int(created_id)


async def _lazy_import_history_with_retry(
    *,
    conversation_id: int,
    user_id: int,
    conv_metadata: dict[str, str],
    messages: list[dict[str, str]],
    max_attempts: int = 3,
) -> None:
    """يحاول استيراد التاريخ إلى conversation-service مع إعادة المحاولة قبل الفشل."""
    delta_messages = messages

    payload = {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "idempotency_key": f"{conversation_id}:{user_id}:{len(messages)}",
        "max_messages": 50,
        "conversation_metadata": conv_metadata,
        "messages": delta_messages,
    }
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            client = await get_conv_service_client()
            resp = await client.post("/api/v1/conversations/import", json=payload)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") not in {"imported", "already_exists"}:
                raise ValueError(f"Unexpected import status: {data.get('status')}")
            return
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                wait_seconds = 0.5 * attempt
                logger.warning(
                    "[HISTORY_RETRY] attempt=%s/%s failed for conv=%s user=%s error=%s; retrying in %.1fs",
                    attempt,
                    max_attempts,
                    conversation_id,
                    user_id,
                    exc,
                    wait_seconds,
                )
                await asyncio.sleep(wait_seconds)
            else:
                logger.error(
                    "[HISTORY_RETRY] all attempts failed for conv=%s user=%s: %s",
                    conversation_id,
                    user_id,
                    last_error,
                )
    if last_error is not None:
        raise last_error


async def _ensure_conversation(
    *,
    session: AsyncSession,
    chat_scope: str,
    user_id: int,
    question: str,
    requested_conversation_id: int | None,
    skip_user_message: bool = False,
) -> tuple[int, list[dict[str, str]]]:
    """ينشئ أو يتحقق من المحادثة ويحفظ رسالة المستخدم لضمان اتساق التاريخ."""
    is_admin_scope = chat_scope == "admin"
    check_query = (
        text(
            "SELECT id, title, created_at FROM admin_conversations WHERE id=:conversation_id AND user_id=:user_id"
        )
        if is_admin_scope
        else text(
            "SELECT id, title, created_at FROM customer_conversations WHERE id=:conversation_id AND user_id=:user_id"
        )
    )
    get_messages_query = (
        text(
            """
            SELECT id, role, content, created_at
            FROM (
                SELECT id, role, content, created_at
                FROM admin_messages
                WHERE conversation_id=:conversation_id
                ORDER BY id DESC
                LIMIT :history_limit
            ) recent
            ORDER BY id ASC
            """
        )
        if is_admin_scope
        else text(
            """
            SELECT id, role, content, created_at
            FROM (
                SELECT id, role, content, created_at
                FROM customer_messages
                WHERE conversation_id=:conversation_id
                ORDER BY id DESC
                LIMIT :history_limit
            ) recent
            ORDER BY id ASC
            """
        )
    )
    get_older_messages_query = (
        text(
            """
            SELECT id, role, content
            FROM admin_messages
            WHERE conversation_id=:conversation_id
              AND id < :min_recent_id
            ORDER BY id DESC
            LIMIT :summary_limit
            """
        )
        if is_admin_scope
        else text(
            """
            SELECT id, role, content
            FROM customer_messages
            WHERE conversation_id=:conversation_id
              AND id < :min_recent_id
            ORDER BY id DESC
            LIMIT :summary_limit
            """
        )
    )

    insert_message_query = (
        text(
            "INSERT INTO admin_messages (conversation_id, role, content) "
            "VALUES (:conversation_id, :role, :content)"
        )
        if is_admin_scope
        else text(
            "INSERT INTO customer_messages (conversation_id, role, content) "
            "VALUES (:conversation_id, :role, :content)"
        )
    )

    messages: list[dict[str, str]] = []
    conversation_id = requested_conversation_id
    conv_metadata_to_import: dict[str, str] | None = None
    messages_to_import: list[dict[str, str]] = []

    if conversation_id is not None:
        try:
            async with asyncio.timeout(5.0):
                result = await session.execute(
                    check_query,
                    {"conversation_id": conversation_id, "user_id": user_id},
                )
        except TimeoutError as e:
            raise HTTPException(
                status_code=504, detail="Database timeout checking conversation"
            ) from e
        conv_row = result.fetchone()
        if conv_row is None:
            raise HTTPException(status_code=403, detail="conversation does not belong to user")

        try:
            try:
                async with asyncio.timeout(5.0):
                    messages_res = await session.execute(
                        get_messages_query,
                        {
                            "conversation_id": conversation_id,
                            "history_limit": MAX_HISTORY_MESSAGES,
                        },
                    )
            except TimeoutError as e:
                raise HTTPException(
                    status_code=504, detail="Database timeout retrieving messages"
                ) from e
            messages_rows = messages_res.fetchall()

            messages = [
                {
                    "role": str(m.role),
                    "content": str(m.content),
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages_rows
            ]

            min_id = min(m.id for m in messages_rows) if messages_rows else 0
            older_messages_rows = []
            if min_id > 0:
                async with asyncio.timeout(5.0):
                    older_messages_res = await session.execute(
                        get_older_messages_query,
                        {
                            "conversation_id": conversation_id,
                            "min_recent_id": min_id,
                            "summary_limit": MAX_HISTORY_SUMMARY_MESSAGES,
                        },
                    )
                older_messages_rows = list(reversed(older_messages_res.fetchall()))

            conv_metadata_to_import = {
                "title": str(conv_row.title),
                "created_at": conv_row.created_at.isoformat(),
            }
            messages_to_import = list(messages)

            if older_messages_rows:
                digest = _build_older_history_digest(older_messages_rows)
                if digest:
                    messages.insert(
                        0,
                        {
                            "role": "system",
                            "content": "ملخص موجز لما سبق في نفس المحادثة:\n" + digest,
                            "created_at": "",
                        },
                    )
            logger.info(
                "[CONV_LIFECYCLE] stage=history_loaded role=%s user=%s conv_id=%s msg_count=%s",
                "admin" if is_admin_scope else "customer",
                user_id,
                conversation_id,
                len(messages),
            )
        except Exception as e:
            logger.error(
                "[ENSURE_CONV] failed preparing history for import for conversation=%s user=%s; preserving same conversation_id. error=%s",
                conversation_id,
                user_id,
                e,
            )
    else:
        conversation_id = await _create_new_conversation(user_id, question, is_admin_scope, session)

    # Skip user message INSERT when Monolith compatibility facade already persisted it
    if not skip_user_message:
        try:
            async with asyncio.timeout(5.0):
                await session.execute(
                    insert_message_query,
                    {
                        "conversation_id": int(conversation_id),
                        "role": "user",
                        "content": question.replace("\x00", ""),
                    },
                )
        except TimeoutError as e:
            raise HTTPException(status_code=504, detail="Database timeout inserting message") from e
    await session.commit()

    if conv_metadata_to_import is not None and conversation_id is not None:
        try:
            await _lazy_import_history_with_retry(
                conversation_id=conversation_id,
                user_id=user_id,
                conv_metadata=conv_metadata_to_import,
                messages=messages_to_import,
            )
        except Exception as e:
            logger.error(
                "[ENSURE_CONV] failed lazy import for conversation=%s user=%s. error=%s",
                conversation_id,
                user_id,
                e,
            )

    return int(conversation_id), messages


async def _persist_assistant_message(
    *,
    session: AsyncSession,
    chat_scope: str,
    conversation_id: int,
    content: str,
    mission_id: int | None = None,
) -> None:
    """يحفظ رد المساعد النهائي ويربط mission_id بالمحادثة الإدارية عند توفره."""
    is_admin_scope = chat_scope == "admin"
    insert_message_query = (
        text(
            "INSERT INTO admin_messages (conversation_id, role, content) "
            "VALUES (:conversation_id, :role, :content)"
        )
        if is_admin_scope
        else text(
            "INSERT INTO customer_messages (conversation_id, role, content) "
            "VALUES (:conversation_id, :role, :content)"
        )
    )
    link_query = text(
        "UPDATE admin_conversations SET linked_mission_id=:mission_id WHERE id=:conversation_id"
    )

    try:
        async with asyncio.timeout(5.0):
            await session.execute(
                insert_message_query,
                {
                    "conversation_id": conversation_id,
                    "role": "assistant",
                    "content": content.replace("\x00", ""),
                },
            )
    except TimeoutError as e:
        raise HTTPException(
            status_code=504, detail="Database timeout persisting assistant message"
        ) from e

    if is_admin_scope and mission_id is not None:
        try:
            async with asyncio.timeout(5.0):
                await session.execute(
                    link_query,
                    {
                        "mission_id": mission_id,
                        "conversation_id": conversation_id,
                    },
                )
        except TimeoutError as e:
            raise HTTPException(status_code=504, detail="Database timeout linking mission") from e
    await session.commit()


async def _stream_chat_langgraph(
    websocket: WebSocket,
    objective: str,
    context: ChatRunContext,
    chat_scope: str,
    conversation_id: int,
    app_graph: object = None,
    admin_payload: dict[str, object] | None = None,
    history_messages: list[dict[str, str]] | None = None,
) -> None:
    """يشغّل LangGraph الموحد لمسارات البحث والإدارة ويبث الأحداث."""
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=256)
    thread_id = _resolve_thread_id(context, conversation_id)
    safe_history = list(history_messages) if history_messages else []
    if not safe_history:
        safe_history = await _extract_checkpoint_history(
            thread_id=thread_id,
            max_messages=MAX_CHECKPOINT_ANCHOR_MESSAGES * 2,
        )
    context_gap_reason = _context_gap_reason_for_followup(objective, safe_history)
    if context_gap_reason is not None:
        history_size = len(safe_history)
        logger.warning(
            "[CONTEXT_GUARD] blocked ambiguous follow-up without anchor. conv_id=%s thread_id=%s reason=%s history_size=%s objective=%s",
            conversation_id,
            thread_id,
            context_gap_reason,
            history_size,
            objective[:120],
        )
        await websocket.send_json(
            {
                "type": "context_missing",
                "payload": {
                    "code": context_gap_reason,
                    "message": "تعذّر تحديد الكيان المرجعي من السياق الحالي.",
                    "conversation_id": conversation_id,
                    "thread_id": thread_id,
                    "history_size": history_size,
                    "source": "orchestrator.context_guard",
                },
            }
        )
        await websocket.send_json(
            {
                "type": "assistant_error",
                "payload": {
                    "content": "يرجى ذكر الكيان المقصود صراحةً (مثال: ما عاصمة الجزائر؟).",
                    "code": context_gap_reason,
                    "source": "orchestrator.context_guard",
                },
            }
        )
        return
    prepared_objective = _augment_ambiguous_objective(objective, safe_history)

    async def _runner():
        async def _safe_put(evt: dict[str, object]) -> None:
            try:
                queue.put_nowait(evt)
            except asyncio.QueueFull:
                logger.warning("[QUEUE_OVERFLOW] dropping event type=%s", evt.get("type"))

        try:
            _graph = app_graph or getattr(websocket.app.state, "app_graph", None)
            if _graph is None:
                raise RuntimeError("LangGraph instance is required but was not found on app.state")
            incoming_messages = safe_history
            await _append_telemetry_line(
                f"[TELEMETRY] INGRESS | "
                f"conversation_id={conversation_id!r} | "
                f"thread_id={thread_id!r} | "
                f"messages_in_request={len(incoming_messages)}"
            )
            config = {"configurable": {"thread_id": thread_id}}

            # فحص حالة الـ checkpointer لتحديد ما إذا كانت الحالة محفوظة مسبقاً
            checkpointer = get_checkpointer()
            _checkpointer_available, _checkpoint_has_state = False, False
            if checkpointer is None:
                await _append_telemetry_line("[TELEMETRY] CHECKPOINTER NOT IN SCOPE")
            else:
                _t = time.monotonic()
                try:
                    _ckpt = await checkpointer.aget(config)
                    _elapsed = time.monotonic() - _t
                    _checkpoint_has_state = _ckpt is not None
                    _checkpointer_available = True
                    _keys = list(_ckpt.channel_values.keys()) if _ckpt else None
                    await _append_telemetry_line(
                        f"[TELEMETRY] CHECKPOINTER | "
                        f"elapsed={_elapsed:.4f}s | "
                        f"state={'NONE — no prior state' if _ckpt is None else _keys}"
                    )
                except Exception as _e:
                    await _append_telemetry_line(
                        f"[TELEMETRY] CHECKPOINTER CRASHED | {type(_e).__name__}: {_e}"
                    )

            # بناء رسائل الإدخال بشكل صحيح:
            # - إذا كان checkpointer يحمل حالة → نمرر رسالة المستخدم الحالية فقط (delta)
            # - إذا لم تكن هناك حالة محفوظة → نمرر كامل التاريخ + الرسالة الحالية
            graph_messages = _build_graph_messages_graph(
                objective=prepared_objective,
                history_messages=safe_history if safe_history else None,
                checkpointer_available=_checkpointer_available,
                checkpoint_has_state=_checkpoint_has_state,
            )
            inputs: dict[str, object] = {"messages": graph_messages, "query": prepared_objective}
            inputs = _merge_admin_inputs(inputs, admin_payload if chat_scope == "admin" else None)
            # D-103: تمرير محتوى التمرين المحقون إلى حالة الرسم (مسار WS)
            _injected_exercise = _extract_injected_exercise(context)
            if _injected_exercise:
                inputs["exercise_content"] = _injected_exercise
            # D-114: تمرير support_level + توجيه المثال المحلول إلى حالة الرسم (مسار WS)
            inputs["support_level"] = _extract_support_level(context)
            _we_directive = _extract_worked_example_directive(context)
            if _we_directive:
                inputs["worked_example_directive"] = _we_directive
            state_dict = inputs
            payload_messages = state_dict.get("messages", [])
            await _append_telemetry_line(
                f"[TELEMETRY] PRE-INVOKE | "
                f"checkpointer_available={_checkpointer_available} | "
                f"checkpoint_has_state={_checkpoint_has_state} | "
                f"messages type={type(payload_messages).__name__} | "
                f"count={len(payload_messages)} | "
                f"last_msg={str(payload_messages[-1])[:120] if payload_messages else 'EMPTY'}"
            )

            # ISS-STREAM-002 (جراحي — WS path): astream_events لا يُطلق on_custom_event
            # في LangGraph 1.2.0. الحل: astream(stream_mode=["custom","updates"])
            final_res = None
            ws_streamed_chars = 0

            async for _stream_mode, _chunk in _graph.astream(
                inputs,
                config=config,
                stream_mode=["custom", "updates"],
            ):
                if _stream_mode == "custom":
                    # token-by-token من stream_writer() في nodes
                    if isinstance(_chunk, dict) and _chunk.get("chunk_type") == "assistant_delta":
                        _content = _chunk.get("content")
                        if isinstance(_content, str) and _content:
                            ws_streamed_chars += len(_content)
                            await _safe_put(
                                {
                                    "type": "assistant_delta",
                                    "payload": {"content": _content},
                                }
                            )

                elif _stream_mode == "updates" and isinstance(_chunk, dict):
                    # state updates — phase_start + final_response
                    for _node_name, _node_output in _chunk.items():
                        if _node_name.startswith("__"):
                            continue
                        await _safe_put(
                            {
                                "type": "phase_start",
                                "payload": {"phase": _node_name, "agent": "orchestrator"},
                            }
                        )
                        if isinstance(_node_output, dict):
                            if "final_response" in _node_output:
                                final_res = {"final_response": _node_output["final_response"]}
                            elif _node_output.get("messages"):
                                _last = _node_output["messages"][-1]
                                if hasattr(_last, "content") and _last.content:
                                    final_res = {"final_response": _last.content}

            if checkpointer is not None:
                _t2 = time.monotonic()
                try:
                    _ckpt_after = await checkpointer.aget(config)
                    _elapsed2 = time.monotonic() - _t2
                    _msgs_saved = (
                        len(_ckpt_after.channel_values.get("messages", [])) if _ckpt_after else 0
                    )
                    await _append_telemetry_line(
                        f"[TELEMETRY] POST-INVOKE | "
                        f"elapsed={_elapsed2:.4f}s | "
                        f"messages_persisted={_msgs_saved} | "
                        f"state={'NONE — not saved' if _ckpt_after is None else 'SAVED'}"
                    )
                except Exception as _e:
                    await _append_telemetry_line(
                        f"[TELEMETRY] POST-INVOKE CRASHED | {type(_e).__name__}: {_e}"
                    )

            if not final_res:
                final_res = {"final_response": "لم يتم العثور على رد من النظام"}

            # D-047: attach streamed chars so consumer can suppress duplicated payload
            if isinstance(final_res, dict):
                final_res = dict(final_res)
                final_res["__streamed_chars"] = ws_streamed_chars

            await _safe_put({"type": "__DONE__", "result": final_res})
        except Exception as e:
            import traceback

            await _safe_put(
                {"type": "__ERROR__", "error": str(e), "traceback": traceback.format_exc()}
            )

    task = asyncio.create_task(_runner())
    active_background_tasks.add(task)

    def _cleanup_task(t: asyncio.Task) -> None:
        active_background_tasks.discard(t)
        try:
            t.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.error("LangGraph task failed", exc_info=True)

    task.add_done_callback(_cleanup_task)
    _task_ref = task  # store reference to avoid GC

    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    await websocket.send_json(
        {
            "type": "RUN_STARTED",
            "payload": {
                "run_id": "sync-run",
                "seq": 1,
                "timestamp": now,
                "iteration": 0,
                "mode": context.get("mission_type", "auto"),
            },
        }
    )

    final_content = ""
    try:
        while True:
            evt = await queue.get()
            if evt["type"] == "__DONE__":
                run_data = evt["result"]

                # Extract the final response from our custom Unified Graph output
                final_resp = run_data.get("final_response")

                # ISS-056: never serialize dict envelope as JSON to the user.
                # SynthesizerNode returns {"المصدر","التمرين",...} — we want التمرين only.
                response_text = _extract_human_readable_response(final_resp)

                final_content = response_text
                logger.info(f"FINAL RESPONSE → {response_text[:100]}")

                # D-047: إذا بُثَّت قطع token-by-token خلال الـ stream،
                # لا نُكرِّر response_text في assistant_final لتجنّب duplicate text.
                _ws_streamed = (
                    run_data.get("__streamed_chars", 0) if isinstance(run_data, dict) else 0
                )
                _final_content = "" if _ws_streamed and _ws_streamed > 0 else response_text
                await websocket.send_json(
                    {
                        "type": "assistant_final",
                        "payload": {
                            "content": _final_content,
                            "status": "ok",
                            "run_id": "sync-run",
                            "timeline": [],
                            "graph_mode": "unified_stategraph",
                            "route_id": f"chat_ws_{chat_scope}",
                            "streamed_chars": int(_ws_streamed),
                        },
                    }
                )
                break
            if evt["type"] == "__ERROR__":
                request_id = str(uuid.uuid4())
                # The exception was raised in the background _runner task, so there
                # is no active exception here — log the captured error/traceback the
                # runner placed on the queue (exc_info=True would log "NoneType: None").
                logger.error(
                    "LangGraph streaming failure | request_id=%s chat_scope=%s | error=%s\n%s",
                    request_id,
                    chat_scope,
                    evt.get("error"),
                    evt.get("traceback"),
                )
                final_content = _safe_assistant_error(request_id)
                await websocket.send_json(
                    {"type": "assistant_error", "payload": {"content": final_content}}
                )
                break
            if evt["type"] == "phase_start":
                phase_name = (
                    evt["payload"].get("phase", "") if isinstance(evt["payload"], dict) else ""
                )
                agent_name = (
                    evt["payload"].get("agent", "") if isinstance(evt["payload"], dict) else ""
                )
                await websocket.send_json(
                    {
                        "type": "PHASE_STARTED",
                        "payload": {
                            "run_id": "sync-run",
                            "seq": 2,
                            "phase": phase_name,
                            "agent": agent_name,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    }
                )
                await websocket.send_json(
                    {
                        "type": "assistant_delta",
                        "payload": {"content": f"🔄 جاري التنفيذ: {phase_name}\n"},
                    }
                )
            elif evt["type"] == "phase_completed":
                phase_name = (
                    evt["payload"].get("phase", "") if isinstance(evt["payload"], dict) else ""
                )
                agent_name = (
                    evt["payload"].get("agent", "") if isinstance(evt["payload"], dict) else ""
                )
                await websocket.send_json(
                    {
                        "type": "PHASE_COMPLETED",
                        "payload": {
                            "run_id": "sync-run",
                            "seq": 3,
                            "phase": phase_name,
                            "agent": agent_name,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    }
                )
            elif evt["type"] == "loop_start":
                iteration = (
                    evt["payload"].get("iteration", 0) if isinstance(evt["payload"], dict) else 0
                )
                mode = (
                    evt["payload"].get("graph_mode", "standard")
                    if isinstance(evt["payload"], dict)
                    else "standard"
                )
                await websocket.send_json(
                    {
                        "type": "RUN_STARTED",
                        "payload": {
                            "run_id": f"sync-run:{iteration}",
                            "seq": 4,
                            "timestamp": datetime.now(UTC).isoformat(),
                            "iteration": iteration,
                            "mode": mode,
                        },
                    }
                )
            else:
                await websocket.send_json(evt)

        if final_content.strip():
            try:
                async with async_session_factory() as db_session:
                    await _persist_assistant_message(
                        session=db_session,
                        chat_scope=chat_scope,
                        conversation_id=conversation_id,
                        content=final_content,
                        mission_id=None,
                    )
                await websocket.send_json(
                    {"type": "assistant_delta", "payload": {"content": "\n\n✅ [DB SAVED]"}}
                )
            except Exception as e:
                error_msg = str(e)
                await websocket.send_json(
                    {
                        "type": "assistant_delta",
                        "payload": {"content": f"\n\n🚨 **SYSTEM DB ERROR:** {error_msg}"},
                    }
                )
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    await websocket.send_json({"type": "complete", "payload": {}})


async def _run_chat_langgraph(
    objective: str,
    context: ChatRunContext,
    app_graph: object = None,
    admin_payload: dict[str, object] | None = None,
    history_messages: list[dict[str, str]] | None = None,
) -> AsyncGenerator[str, None]:
    """يشغّل LangGraph كعمود فقري لرحلة chat ويعيد حمولة موحدة قابلة للبث (HTTP legacy fallback)."""
    if not app_graph:
        raise RuntimeError("LangGraph instance is required but was not found on app.state")
    requested_conversation_id = context.get("conversation_id") if context else None
    safe_conversation_id = _safe_conversation_id(requested_conversation_id)
    conversation_id: int | str = (
        safe_conversation_id if safe_conversation_id is not None else str(uuid.uuid4())
    )
    thread_id = _resolve_thread_id(context, conversation_id)
    prepared_objective = _augment_ambiguous_objective(objective, history_messages)
    config = {"configurable": {"thread_id": thread_id}}
    logger.info(
        "[THREAD_BINDING] channel=http thread_id=%s source=%s conversation_id=%s",
        thread_id,
        "request_context"
        if "thread_id" in context or "session_id" in context
        else "conversation_fallback",
        str(conversation_id),
    )
    # فحص حالة الـ checkpointer لتحديد ما إذا كانت الحالة محفوظة مسبقاً
    _checkpointer_available, _checkpoint_has_state = await _detect_checkpoint_state(thread_id)
    graph_messages = _build_graph_messages_graph(
        objective=prepared_objective,
        history_messages=history_messages,
        checkpointer_available=_checkpointer_available,
        checkpoint_has_state=_checkpoint_has_state,
    )
    inputs: dict[str, object] = {"messages": graph_messages, "query": prepared_objective}
    inputs = _merge_admin_inputs(inputs, admin_payload)
    # D-103: تمرير محتوى التمرين المحقون إلى حالة الرسم (مسار HTTP — يستدعيه الـ monolith)
    _injected_exercise = _extract_injected_exercise(context)
    if _injected_exercise:
        logger.info(
            "[D-103] injected_exercise chars=%s ref=%s",
            len(_injected_exercise),
            str(context.get("exercise_ref", ""))[:120],
        )
        inputs["exercise_content"] = _injected_exercise

    # D-114: تمرير support_level + توجيه المثال المحلول إلى حالة الرسم (مسار HTTP)
    inputs["support_level"] = _extract_support_level(context)
    _we_directive = _extract_worked_example_directive(context)
    if _we_directive:
        logger.info("[D-114] worked_example_directive chars=%s", len(_we_directive))
        inputs["worked_example_directive"] = _we_directive

    # ISS-STREAM-002 (جراحي): astream_events لا يُطلق on_custom_event في LangGraph 1.2.0
    # عند استخدام stream_writer(). الحل: astream(stream_mode=["custom","updates"]) يُعيد
    # custom chunks مباشرة + state updates لاستخراج final_response.
    # المرجع: اختبار مباشر أثبت أن writer() يُستدعى لكن on_custom_event لا يُطلق أبداً.
    import time as _time_mod

    streamed_chars = 0
    final_resp = None
    _stream_start = _time_mod.perf_counter()
    _active_node = "unknown"

    # المرحلة 1: بث الـ phase_start events أولاً (لا تحتاج astream_events)
    # نُرسل phase_start لكل node عبر updates stream
    async for stream_mode, chunk in app_graph.astream(
        inputs,
        config=config,
        stream_mode=["custom", "updates"],
    ):
        if (
            stream_mode == "custom"
            and isinstance(chunk, dict)
            and chunk.get("chunk_type") == "assistant_delta"
        ):
            # custom chunks من stream_writer() — هذا هو مسار token-by-token
            content = chunk.get("content")
            node_name = chunk.get("node", _active_node)
            if isinstance(content, str) and content:
                streamed_chars += len(content)
                # ISS-STREAM-002: تسجيل كل chunk في Prometheus
                import contextlib

                with contextlib.suppress(Exception):
                    record_streaming_chunk("http", str(node_name), len(content))
                yield await _serialize_stream_frame(
                    {"type": "assistant_delta", "payload": {"content": content}}
                )

        elif stream_mode == "updates" and isinstance(chunk, dict):
            # state updates — نستخرج منها phase_start وfinal_response
            for node_name, node_output in chunk.items():
                if node_name.startswith("__"):
                    continue
                _active_node = node_name
                # phase_start لكل node
                yield await _serialize_stream_frame(
                    {
                        "type": "phase_start",
                        "payload": {"phase": node_name, "agent": "orchestrator"},
                    }
                )
                # استخراج final_response من آخر node ينتجه
                if isinstance(node_output, dict):
                    if "final_response" in node_output:
                        final_resp = node_output["final_response"]
                    elif node_output.get("messages"):
                        last_msg = node_output["messages"][-1]
                        if hasattr(last_msg, "content") and last_msg.content:
                            final_resp = last_msg.content

    # ISS-056: never leak SynthesizerNode dict envelope as JSON to the user
    response_text = _extract_human_readable_response(final_resp)

    # ISS-STREAM-002: تسجيل الجلسة الكاملة في Prometheus
    import contextlib

    with contextlib.suppress(Exception):
        _stream_duration = _time_mod.perf_counter() - _stream_start
        _session_status = "success" if streamed_chars > 0 else "fallback"
        record_streaming_session("http", _session_status, _stream_duration)

    # إذا بُثَّت قطع كافية → assistant_final بـ content="" (الـ deltas كافية)
    # إذا لم تُبَث أي قطعة (مثلاً النموذج لا يدعم streaming) → نُرسل النص كاملاً
    if streamed_chars == 0:
        yield await _serialize_stream_frame(
            {
                "type": "assistant_final",
                "payload": {
                    "content": response_text,
                    "status": "ok",
                    "run_id": "http-run",
                    "graph_mode": "unified_stategraph",
                },
            }
        )
    else:
        yield await _serialize_stream_frame(
            {
                "type": "assistant_final",
                "payload": {
                    "content": "",
                    "status": "ok",
                    "run_id": "http-run",
                    "graph_mode": "unified_stategraph",
                    "streamed_chars": streamed_chars,
                },
            }
        )


@router.get("/api/chat/messages", summary="Chat Health Endpoint")
async def chat_messages_health_endpoint() -> dict[str, str]:
    """يوفر نقطة صحة توافقية لمسار chat ضمن سلطة orchestrator الموحدة."""
    return {
        "status": "ok",
        "service": "orchestrator-service",
        "control_plane": "stategraph",
    }


@router.get("/api/chat/conversations", summary="List customer conversations")
async def list_customer_conversations(
    authorization: str | None = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, object]]:
    """يعرض قائمة محادثات العميل الحالي من قاعدة orchestrator."""
    user_id, _payload = _decode_auth_payload_or_401(authorization)
    query = text(
        """
        SELECT id, title, created_at
        FROM customer_conversations
        WHERE user_id = :user_id
        ORDER BY created_at DESC, id DESC
        LIMIT :limit
        """
    )
    async with async_session_factory() as session:
        rows = (await session.execute(query, {"user_id": user_id, "limit": limit})).fetchall()
    return [
        {
            "conversation_id": int(row.id),
            "title": str(row.title or ""),
            "created_at": row.created_at.isoformat() if row.created_at is not None else None,
        }
        for row in rows
    ]


@router.get("/api/chat/conversations/{conversation_id}", summary="Customer conversation details")
async def get_customer_conversation(
    conversation_id: int,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    """يعيد تفاصيل محادثة عميل ورسائلها بترتيب زمني."""
    user_id, _payload = _decode_auth_payload_or_401(authorization)
    check_query = text(
        """
        SELECT id, title, created_at
        FROM customer_conversations
        WHERE id = :conversation_id AND user_id = :user_id
        """
    )
    messages_query = text(
        """
        SELECT role, content, created_at
        FROM customer_messages
        WHERE conversation_id = :conversation_id
        ORDER BY id ASC
        """
    )
    async with async_session_factory() as session:
        conv_row = (
            await session.execute(
                check_query, {"conversation_id": conversation_id, "user_id": user_id}
            )
        ).fetchone()
        if conv_row is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        message_rows = (
            await session.execute(messages_query, {"conversation_id": conversation_id})
        ).fetchall()

    return {
        "conversation_id": int(conv_row.id),
        "title": str(conv_row.title or ""),
        "created_at": conv_row.created_at.isoformat() if conv_row.created_at is not None else None,
        "messages": [
            {
                "role": str(msg.role),
                "content": str(msg.content),
                "created_at": msg.created_at.isoformat() if msg.created_at is not None else None,
            }
            for msg in message_rows
        ],
    }


@router.get("/admin/api/conversations", summary="List admin conversations")
async def list_admin_conversations(
    authorization: str | None = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, object]]:
    """يعرض قائمة محادثات الأدمن الحالي."""
    user_id, payload = _decode_auth_payload_or_401(authorization)
    if not _is_admin_payload(payload):
        raise HTTPException(status_code=403, detail="forbidden")
    query = text(
        """
        SELECT id, title, created_at
        FROM admin_conversations
        WHERE user_id = :user_id
        ORDER BY created_at DESC, id DESC
        LIMIT :limit
        """
    )
    async with async_session_factory() as session:
        rows = (await session.execute(query, {"user_id": user_id, "limit": limit})).fetchall()
    return [
        {
            "conversation_id": int(row.id),
            "title": str(row.title or ""),
            "created_at": row.created_at.isoformat() if row.created_at is not None else None,
        }
        for row in rows
    ]


@router.get("/admin/api/conversations/{conversation_id}", summary="Admin conversation details")
async def get_admin_conversation(
    conversation_id: int,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    """يعيد تفاصيل محادثة الأدمن ورسائلها."""
    user_id, payload = _decode_auth_payload_or_401(authorization)
    if not _is_admin_payload(payload):
        raise HTTPException(status_code=403, detail="forbidden")
    check_query = text(
        """
        SELECT id, title, created_at
        FROM admin_conversations
        WHERE id = :conversation_id AND user_id = :user_id
        """
    )
    messages_query = text(
        """
        SELECT role, content, created_at
        FROM admin_messages
        WHERE conversation_id = :conversation_id
        ORDER BY id ASC
        """
    )
    async with async_session_factory() as session:
        conv_row = (
            await session.execute(
                check_query, {"conversation_id": conversation_id, "user_id": user_id}
            )
        ).fetchone()
        if conv_row is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        message_rows = (
            await session.execute(messages_query, {"conversation_id": conversation_id})
        ).fetchall()

    return {
        "conversation_id": int(conv_row.id),
        "title": str(conv_row.title or ""),
        "created_at": conv_row.created_at.isoformat() if conv_row.created_at is not None else None,
        "messages": [
            {
                "role": str(msg.role),
                "content": str(msg.content),
                "created_at": msg.created_at.isoformat() if msg.created_at is not None else None,
            }
            for msg in message_rows
        ],
    }


@router.post("/api/chat/messages", summary="StateGraph Chat Endpoint")
async def chat_messages_endpoint(
    payload: dict[str, object],
    request: Request,
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    """ينفّذ رسالة chat عبر خدمة LangGraph ويعيد نتيجة تشغيل موحدة عبر Stream."""
    objective = _extract_chat_objective(payload)
    if objective is None:
        raise HTTPException(status_code=422, detail="question/objective is required")

    context_payload = payload.get("context")
    context: ChatRunContext = {}
    if isinstance(context_payload, dict):
        for key, value in context_payload.items():
            if not isinstance(key, str):
                continue
            context[key] = value

    user_id, _jwt_payload = _decode_auth_payload_or_401(authorization)
    context["user_id"] = user_id

    chat_scope = "customer"

    requested_conversation_id = _safe_conversation_id(payload.get("conversation_id"))
    if requested_conversation_id is None:
        scoped_thread = _safe_thread_id(context.get("thread_id"))
        if scoped_thread is None:
            scoped_thread = _safe_thread_id(context.get("session_id"))
        if scoped_thread is not None:
            requested_conversation_id = _conversation_id_from_scoped_thread(
                thread_id=scoped_thread,
                user_id=user_id,
            )

    async with async_session_factory() as session:
        conversation_id, history_messages = await _ensure_conversation(
            session=session,
            chat_scope=chat_scope,
            user_id=user_id,
            question=objective,
            requested_conversation_id=requested_conversation_id,
        )
    context["conversation_id"] = conversation_id

    # حماية عزل السياق: يمنع قبول thread/session معرفَين من العميل حتى لا تختلط محادثات مستقلة.
    context["thread_id"] = _build_conversation_thread_id(user_id, conversation_id)

    async def _generator_with_persistence() -> AsyncGenerator[str, None]:
        generator = _run_chat_langgraph(
            objective,
            context,
            app_graph=getattr(request.app.state, "app_graph", None),
            history_messages=history_messages,
        )
        # ISS-STREAM-001: تجميع كل الـ deltas للحفظ الصحيح.
        # عند streaming، assistant_final يُرسل content="" لتجنب التكرار،
        # لذا يجب تجميع كل assistant_delta chunks لبناء النص الكامل.
        delta_parts: list[str] = []
        final_content = ""
        async for chunk in generator:
            try:
                chunk_data = json.loads(chunk)
                chunk_type = chunk_data.get("type", "")
                payload = chunk_data.get("payload", {})
                if chunk_type in ("assistant_delta",):
                    delta_text = payload.get("content", "")
                    if delta_text:
                        delta_parts.append(delta_text)
                elif chunk_type == "assistant_final":
                    # إذا كان content غير فارغ (fallback بدون streaming) → استخدمه
                    # إذا كان فارغاً (streaming mode) → استخدم الـ deltas المجمّعة
                    fc = payload.get("content", "")
                    if fc:
                        final_content = fc
                    elif delta_parts:
                        final_content = "".join(delta_parts)
            except Exception:
                pass
            yield chunk

        # إذا لم يصل assistant_final لكن وصلت deltas → استخدمها
        if not final_content and delta_parts:
            final_content = "".join(delta_parts)

        if final_content:
            try:
                async with async_session_factory() as db_session:
                    await _persist_assistant_message(
                        session=db_session,
                        chat_scope=chat_scope,
                        conversation_id=conversation_id,
                        content=final_content,
                    )
            except Exception as e:
                logger.error("[HTTP_PERSIST] failed to save final chat message: %s", e)

    return StreamingResponse(_generator_with_persistence(), media_type="text/plain")


@router.websocket("/api/chat/ws")
async def chat_ws_stategraph(websocket: WebSocket) -> None:
    from microservices.orchestrator_service.src.core.logging import get_logger

    logger = get_logger("routes")
    """يشغّل WebSocket chat فوق LangGraph لضمان توحيد مسار التنفيذ مع mission."""
    token, selected_protocol = extract_websocket_auth(websocket)
    if not token:
        await websocket.close(code=4401)
        return

    try:
        user_id = decode_user_id(token, get_settings().SECRET_KEY)
    except HTTPException:
        await websocket.close(code=4401)
        return

    await websocket.accept(subprotocol=selected_protocol)
    sticky_conversation_id: int | None = None
    sticky_thread_id: str | None = None
    try:
        while True:
            incoming = await websocket.receive_json()
            if not isinstance(incoming, dict):
                await websocket.send_json({"status": "error", "message": "invalid payload"})
                continue
            objective = _extract_chat_objective(incoming)
            if objective is None:
                await websocket.send_json(
                    {"status": "error", "message": "question/objective required"}
                )
                continue

            requested_conversation_id = incoming.get("conversation_id")

            logger.info(
                "[CONV_LIFECYCLE] stage=ws_received role=customer user=%s conv_id=%s type=%s",
                user_id,
                requested_conversation_id,
                type(requested_conversation_id).__name__,
            )
            conversation_id = _resolve_effective_conversation_id(
                incoming_value=requested_conversation_id,
                sticky_value=sticky_conversation_id,
            )
            if (
                requested_conversation_id is not None
                and requested_conversation_id != sticky_conversation_id
            ):
                sticky_thread_id = None
            logger.info(
                "[CONV_LIFECYCLE] stage=parsed role=customer user=%s conv_id=%s type=%s",
                user_id,
                conversation_id,
                type(conversation_id).__name__,
            )
            try:
                logger.info(f"ORCHESTRATOR received | chat_scope=customer | role={user_id}")
                logger.info(
                    "[CONV_LIFECYCLE] stage=ensure_entry role=customer user=%s conv_id=%s",
                    user_id,
                    conversation_id,
                )
                async with async_session_factory() as session:
                    conversation_id, history_messages = await _ensure_conversation(
                        session=session,
                        chat_scope="customer",
                        user_id=user_id,
                        question=objective,
                        requested_conversation_id=conversation_id,
                    )
                logger.info(
                    "[CONV_LIFECYCLE] stage=ensure_exit role=customer user=%s conv_id=%s msg_count=%s",
                    user_id,
                    conversation_id,
                    len(history_messages),
                )
                sticky_conversation_id = conversation_id
                sticky_thread_id = _build_conversation_thread_id(user_id, conversation_id)
            except HTTPException as error:
                await websocket.send_json(
                    {"type": "assistant_error", "payload": {"content": error.detail}}
                )
                continue

            await websocket.send_json(
                {
                    "type": "conversation_init",
                    "payload": {"conversation_id": conversation_id},
                }
            )

            context_payload = incoming.get("context")
            context: ChatRunContext = {}
            if isinstance(context_payload, dict):
                for key, value in context_payload.items():
                    if not isinstance(key, str):
                        continue
                    context[key] = value

            if "mission_type" in incoming:
                context["mission_type"] = incoming["mission_type"]
            elif (
                "metadata" in incoming
                and isinstance(incoming["metadata"], dict)
                and "mission_type" in incoming["metadata"]
            ):
                context["mission_type"] = incoming["metadata"]["mission_type"]
            context["conversation_id"] = conversation_id
            context["user_id"] = user_id
            if sticky_thread_id:
                context["thread_id"] = sticky_thread_id
            _emit_identity_diagnostic_log(
                route_name="orchestrator_ws_customer",
                conversation_id=conversation_id,
                thread_id=sticky_thread_id,
                session_id=_resolve_session_id_from_incoming(incoming),
            )

            try:
                client_context = _extract_client_context_messages(incoming)
                hydrated_messages = _merge_history_with_client_context(
                    history_messages, client_context
                )
            except Exception as e:
                logger.error(
                    "[HYDRATION_GUARD] Context hydration failed — "
                    f"falling back to DB history only. "
                    f"Error: {type(e).__name__}: {e}"
                )
                hydrated_messages = history_messages

            await _stream_chat_langgraph(
                websocket,
                objective=objective,
                context=context,
                chat_scope="customer",
                conversation_id=conversation_id,
                app_graph=getattr(websocket.app.state, "app_graph", None),
                history_messages=hydrated_messages,
            )
            logger.info(
                "[CONV_LIFECYCLE] stage=response_sent role=customer user=%s conv_id=%s",
                user_id,
                conversation_id,
            )

    except WebSocketDisconnect:
        logger.info("Customer chat websocket disconnected")


@router.websocket("/admin/api/chat/ws")
async def admin_chat_ws_stategraph(websocket: WebSocket) -> None:
    """يشغّل WebSocket الإداري عبر LangGraph بنفس السلطة الموحدة للـ control-plane."""
    token, selected_protocol = extract_websocket_auth(websocket)
    if not token:
        await websocket.close(code=4401)
        return

    try:
        auth_payload = jwt.decode(token, get_settings().SECRET_KEY, algorithms=["HS256"])
        user_id = int(auth_payload.get("sub", auth_payload.get("user_id", 0)) or 0)
        if user_id <= 0:
            raise HTTPException(status_code=401, detail="Invalid user")
    except (HTTPException, jwt.PyJWTError, ValueError):
        await websocket.close(code=4401)
        return

    if not _is_admin_payload(auth_payload):
        await websocket.close(code=4403)
        return

    await websocket.accept(subprotocol=selected_protocol)
    sticky_conversation_id: int | None = None
    sticky_thread_id: str | None = None
    try:
        while True:
            incoming = await websocket.receive_json()
            if not isinstance(incoming, dict):
                await websocket.send_json({"status": "error", "message": "invalid payload"})
                continue
            objective = _extract_chat_objective(incoming)
            if objective is None:
                await websocket.send_json(
                    {"status": "error", "message": "question/objective required"}
                )
                continue

            requested_conversation_id = incoming.get("conversation_id")

            logger.info(
                "[CONV_LIFECYCLE] stage=ws_received role=admin user=%s conv_id=%s type=%s",
                user_id,
                requested_conversation_id,
                type(requested_conversation_id).__name__,
            )
            conversation_id = _resolve_effective_conversation_id(
                incoming_value=requested_conversation_id,
                sticky_value=sticky_conversation_id,
            )
            if (
                requested_conversation_id is not None
                and requested_conversation_id != sticky_conversation_id
            ):
                sticky_thread_id = None
            logger.info(
                "[CONV_LIFECYCLE] stage=parsed role=admin user=%s conv_id=%s type=%s",
                user_id,
                conversation_id,
                type(conversation_id).__name__,
            )
            try:
                logger.info(f"ORCHESTRATOR received | chat_scope=admin | role={user_id}")
                logger.info(
                    "[CONV_LIFECYCLE] stage=ensure_entry role=admin user=%s conv_id=%s",
                    user_id,
                    conversation_id,
                )
                async with async_session_factory() as session:
                    conversation_id, history_messages = await _ensure_conversation(
                        session=session,
                        chat_scope="admin",
                        user_id=user_id,
                        question=objective,
                        requested_conversation_id=conversation_id,
                    )
                logger.info(
                    "[CONV_LIFECYCLE] stage=ensure_exit role=admin user=%s conv_id=%s msg_count=%s",
                    user_id,
                    conversation_id,
                    len(history_messages),
                )
                sticky_conversation_id = conversation_id
                sticky_thread_id = _build_conversation_thread_id(user_id, conversation_id)
            except HTTPException as error:
                await websocket.send_json(
                    {"type": "assistant_error", "payload": {"content": error.detail}}
                )
                continue

            await websocket.send_json(
                {
                    "type": "conversation_init",
                    "payload": {"conversation_id": conversation_id},
                }
            )

            context_payload = incoming.get("context")
            context: ChatRunContext = {}
            if isinstance(context_payload, dict):
                for key, value in context_payload.items():
                    if not isinstance(key, str):
                        continue
                    context[key] = value

            if "mission_type" in incoming:
                context["mission_type"] = incoming["mission_type"]
            elif (
                "metadata" in incoming
                and isinstance(incoming["metadata"], dict)
                and "mission_type" in incoming["metadata"]
            ):
                context["mission_type"] = incoming["metadata"]["mission_type"]
            context["conversation_id"] = conversation_id
            context["user_id"] = user_id
            if sticky_thread_id:
                context["thread_id"] = sticky_thread_id
            _emit_identity_diagnostic_log(
                route_name="orchestrator_ws_admin",
                conversation_id=conversation_id,
                thread_id=sticky_thread_id,
                session_id=_resolve_session_id_from_incoming(incoming),
            )

            try:
                client_context = _extract_client_context_messages(incoming)
                hydrated_messages = _merge_history_with_client_context(
                    history_messages, client_context
                )
            except Exception as e:
                logger.error(
                    "[HYDRATION_GUARD] Context hydration failed — "
                    f"falling back to DB history only. "
                    f"Error: {type(e).__name__}: {e}"
                )
                hydrated_messages = history_messages

            await _stream_chat_langgraph(
                websocket,
                objective=objective,
                context=context,
                chat_scope="admin",
                conversation_id=conversation_id,
                app_graph=getattr(websocket.app.state, "app_graph", None),
                admin_payload=auth_payload,
                history_messages=hydrated_messages,
            )
            logger.info(
                "[CONV_LIFECYCLE] stage=response_sent role=admin user=%s conv_id=%s",
                user_id,
                conversation_id,
            )

    except WebSocketDisconnect:
        logger.info("Admin chat websocket disconnected")


def _get_mission_status_payload(status: str) -> dict[str, str | None]:
    if status == "partial_success":
        return {"status": "success", "outcome": "partial_success"}
    return {"status": status, "outcome": None}


def _serialize_mission(mission: Mission) -> MissionResponse:
    status_payload = _get_mission_status_payload(mission.status.value)
    return MissionResponse(
        id=mission.id,
        objective=mission.objective,
        status=status_payload["status"],
        outcome=status_payload["outcome"],
        created_at=mission.created_at,
        updated_at=mission.updated_at,
        result={"summary": mission.result_summary} if mission.result_summary else None,
        steps=[],
    )


@router.post("/agent/chat", summary="Chat with Orchestrator Agent")
async def chat_with_agent_endpoint(
    request: ChatRequest,
    fastapi_req: Request,
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    """
    Direct chat endpoint for the Orchestrator Agent (Microservice).
    Streams the response chunk by chunk.
    """
    user_id, auth_payload = _decode_auth_payload_or_401(authorization)
    request.user_id = user_id  # Override body user_id with JWT user_id

    logger.info(f"Agent Chat Request: {request.question[:50]}... User: {request.user_id}")

    # Prepare context
    context = request.context.copy()
    context.update(
        {
            "user_id": request.user_id,
            "conversation_id": request.conversation_id,
            "history_messages": request.history_messages,
        }
    )

    # Validate admin explicitly from JWT payload
    is_admin = _is_admin_payload(auth_payload)
    # Detect if request comes from Monolith compatibility facade
    is_compatibility_facade = bool(context.get("compatibility_facade"))

    if is_admin:

        async def _admin_stream() -> AsyncGenerator[str, None]:
            try:
                admin_app = getattr(fastapi_req.app.state, "admin_app", None)
                if admin_app is None:
                    raise RuntimeError(
                        "LangGraph admin_app is required but was not found on app.state"
                    )

                if isinstance(request.context, dict):
                    request.context["is_admin"] = True
                    request.context["role"] = "admin"
                    admin_payload = request.context
                else:
                    admin_payload = {"is_admin": True, "role": "admin"}

                # Augment the objective for explicit context before sending to LangGraph
                prepared_objective = _augment_ambiguous_objective(
                    request.question, request.history_messages
                )

                # Use _build_graph_messages to safely build context avoiding context blindness
                conversation_id_fallback = (
                    request.conversation_id
                    if getattr(request, "conversation_id", None)
                    else str(uuid.uuid4())
                )
                thread_id = _resolve_thread_id(
                    {"user_id": request.user_id, "conversation_id": request.conversation_id},
                    fallback_conversation_id=str(conversation_id_fallback),
                )
                _checkpointer_available, _checkpoint_has_state = await _detect_checkpoint_state(
                    thread_id
                )
                admin_inputs = _merge_admin_inputs(
                    {"messages": [{"role": "user", "content": prepared_objective}]},
                    admin_payload,
                )

                conversation_id = (
                    request.conversation_id
                    if getattr(request, "conversation_id", None)
                    else str(uuid.uuid4())
                )

                thread_id = _resolve_thread_id(
                    {"user_id": request.user_id, "conversation_id": request.conversation_id},
                    fallback_conversation_id=str(conversation_id),
                )

                final_resp = None
                admin_streamed_chars = 0  # D-047
                config = {"configurable": {"thread_id": thread_id}}
                async for event in admin_app.astream_events(
                    admin_inputs, config=config, version="v2"
                ):
                    _evt_type = event["event"]
                    if _evt_type == "on_chain_start":
                        node_name = event.get("name", "")
                        if (
                            node_name
                            and not node_name.startswith("__")
                            and node_name != "LangGraph"
                        ):
                            yield await _serialize_stream_frame(
                                {
                                    "type": "phase_start",
                                    "payload": {"phase": node_name, "agent": "admin"},
                                }
                            )
                    elif _evt_type == "on_chat_model_stream":
                        # D-047: token-level streaming when nodes use LangChain ChatOpenAI
                        _chunk = event.get("data", {}).get("chunk")
                        if _chunk is not None:
                            _content = getattr(_chunk, "content", None)
                            if isinstance(_content, str) and _content:
                                admin_streamed_chars += len(_content)
                                yield await _serialize_stream_frame(
                                    {
                                        "type": "assistant_delta",
                                        "payload": {"content": _content},
                                    }
                                )
                    elif _evt_type == "on_custom_event":
                        # D-048: token-level streaming from DSPy/raw-OpenAI nodes via stream_writer
                        _data = event.get("data")
                        if isinstance(_data, dict) and _data.get("chunk_type") == "assistant_delta":
                            _content = _data.get("content")
                            if isinstance(_content, str) and _content:
                                admin_streamed_chars += len(_content)
                                yield await _serialize_stream_frame(
                                    {
                                        "type": "assistant_delta",
                                        "payload": {"content": _content},
                                    }
                                )
                    elif _evt_type == "on_chain_end":
                        node_name = event.get("name", "")
                        if (
                            node_name
                            and not node_name.startswith("__")
                            and node_name != "LangGraph"
                        ):
                            yield await _serialize_stream_frame(
                                {
                                    "type": "phase_completed",
                                    "payload": {"phase": node_name, "agent": "admin"},
                                }
                            )
                        if not node_name or node_name == "LangGraph":
                            output_data = event["data"].get("output", {})
                            if output_data and isinstance(output_data, dict):
                                if "final_response" in output_data:
                                    final_resp = output_data["final_response"]
                                elif output_data.get("messages"):
                                    last_msg = output_data["messages"][-1]
                                    if hasattr(last_msg, "content"):
                                        final_resp = last_msg.content

                # ISS-056: extract human-readable text only — never leak JSON envelope
                response_text = _extract_human_readable_response(final_resp)

                full_user_message = request.question
                full_ai_response = response_text
                try:
                    async with async_session_factory() as db_session:
                        conv_id, _ = await _ensure_conversation(
                            session=db_session,
                            chat_scope="admin",
                            user_id=request.user_id,
                            question=full_user_message,
                            requested_conversation_id=request.conversation_id,
                            skip_user_message=is_compatibility_facade,
                        )
                        await _persist_assistant_message(
                            session=db_session,
                            chat_scope="admin",
                            conversation_id=conv_id,
                            content=full_ai_response,
                        )
                    yield await _serialize_stream_frame(
                        {"type": "assistant_delta", "payload": {"content": "\n\n✅ [DB SAVED]"}}
                    )
                    # D-047: لا تُكرِّر response_text إذا تم بث القطع بالفعل token-by-token،
                    # لأن المتصفح يجمعها عبر mergeAssistantContent.
                    _final_payload_content = "" if admin_streamed_chars > 0 else response_text
                    # Signal Monolith that Orchestrator already persisted both messages
                    yield await _serialize_stream_frame(
                        {
                            "type": "assistant_final",
                            "payload": {"content": _final_payload_content},
                            "persisted": True,
                        }
                    )
                except Exception as e:
                    error_msg = str(e)
                    yield await _serialize_stream_frame(
                        {
                            "type": "assistant_error",
                            "payload": {"content": f"\n\n🚨 **SYSTEM DB ERROR:** {error_msg}"},
                        }
                    )
                    # DB write failed — Monolith must handle persistence
                    yield await _serialize_stream_frame(
                        {
                            "type": "assistant_final",
                            "payload": {"content": response_text},
                            "persisted": False,
                        }
                    )
            except Exception:
                request_id = str(uuid.uuid4())
                logger.error(
                    "Admin Chat Error",
                    exc_info=True,
                    extra={"request_id": request_id},
                )
                yield await _serialize_stream_frame(
                    {
                        "type": "assistant_error",
                        "payload": {"content": _safe_assistant_error(request_id)},
                    }
                )

        return StreamingResponse(_admin_stream(), media_type="text/plain")

    ai_client = get_ai_client()
    agent = OrchestratorAgent(ai_client, tool_registry)

    async def _stream_generator():
        try:
            prepared_objective = _augment_ambiguous_objective(
                request.question, request.history_messages
            )

            # Use _build_graph_messages to properly seed history for the agent context
            conversation_id_fallback = (
                request.conversation_id
                if getattr(request, "conversation_id", None)
                else str(uuid.uuid4())
            )
            thread_id = _resolve_thread_id(
                {"user_id": request.user_id, "conversation_id": request.conversation_id},
                fallback_conversation_id=str(conversation_id_fallback),
            )
            _checkpointer_available, _checkpoint_has_state = await _detect_checkpoint_state(
                thread_id
            )
            langchain_msgs = _build_graph_messages_manual(
                objective=prepared_objective,
                history_messages=request.history_messages,
            )

            run_result = agent.run(
                prepared_objective, context=context, history_messages=langchain_msgs
            )
            ai_chunks = []
            final_chunk = None
            async for chunk in run_result:
                if isinstance(chunk, str):
                    ai_chunks.append(chunk)
                    yield await _serialize_stream_frame(chunk)
                elif isinstance(chunk, dict) and chunk.get("type") == "assistant_delta":
                    delta_content = chunk.get("payload", {}).get("content", "")
                    if delta_content:
                        ai_chunks.append(str(delta_content))
                    yield await _serialize_stream_frame(chunk)
                elif isinstance(chunk, dict) and chunk.get("type") == "assistant_final":
                    final_content = chunk.get("payload", {}).get("content", "")
                    if final_content:
                        ai_chunks.append(str(final_content))
                    final_chunk = chunk
                else:
                    yield await _serialize_stream_frame(chunk)

            # The run completed successfully, trigger persistence
            full_user_message = request.question
            full_ai_response = "".join(ai_chunks)
            if full_ai_response:
                orchestrator_persisted = False
                try:
                    async with async_session_factory() as db_session:
                        conv_id, _ = await _ensure_conversation(
                            session=db_session,
                            chat_scope="customer",
                            user_id=request.user_id,
                            question=full_user_message,
                            requested_conversation_id=request.conversation_id,
                            skip_user_message=is_compatibility_facade,
                        )
                        await _persist_assistant_message(
                            session=db_session,
                            chat_scope="customer",
                            conversation_id=conv_id,
                            content=full_ai_response,
                        )
                    orchestrator_persisted = True
                    yield await _serialize_stream_frame(
                        {"type": "assistant_delta", "payload": {"content": "\n\n✅ [DB SAVED]"}}
                    )
                except Exception as e:
                    error_msg = str(e)
                    yield await _serialize_stream_frame(
                        {
                            "type": "assistant_error",
                            "payload": {"content": f"\n\n🚨 **SYSTEM DB ERROR:** {error_msg}"},
                        }
                    )
                # Signal Monolith whether Orchestrator handled persistence
                final_frame = {
                    "type": "assistant_final",
                    "payload": {"content": full_ai_response},
                    "persisted": orchestrator_persisted,
                }
                yield await _serialize_stream_frame(final_frame)
            elif final_chunk:
                # No AI response to persist — forward original final_chunk without persistence flag
                yield await _serialize_stream_frame(final_chunk)

        except Exception:
            request_id = str(uuid.uuid4())
            logger.error(
                "Agent Chat Error",
                exc_info=True,
                extra={"request_id": request_id},
            )
            yield await _serialize_stream_frame(
                {
                    "type": "assistant_error",
                    "payload": {"content": _safe_assistant_error(request_id)},
                }
            )

    return StreamingResponse(_stream_generator(), media_type="text/plain")


@router.post("/missions", response_model=MissionResponse, summary="Launch Mission")
async def create_mission_endpoint(
    request: MissionCreate,
    background_tasks: BackgroundTasks,
    req: Request,
    db: AsyncSession = Depends(get_db),
) -> MissionResponse:
    correlation_id = req.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    logger.info(f"Orchestrator: Creating mission with Correlation ID: {correlation_id}")

    try:
        mission = await start_mission(
            session=db,
            objective=request.objective,
            initiator_id=1,  # Default system user for now, or extract from token if forwarded
            context=request.context,
            force_research=False,
            idempotency_key=correlation_id,
        )

        return _serialize_mission(mission)

    except Exception as e:
        request_id = str(uuid.uuid4())
        logger.error(
            "Failed to create mission",
            exc_info=True,
            extra={"request_id": request_id},
        )
        raise HTTPException(
            status_code=500,
            detail=f"Mission creation failed. request_id={request_id}",
        ) from e


@router.get("/missions/{mission_id}", response_model=MissionResponse, summary="Get Mission")
async def get_mission_endpoint(
    mission_id: int, req: Request, db: AsyncSession = Depends(get_db)
) -> MissionResponse:
    state_manager = MissionStateManager(db)
    mission = await state_manager.get_mission(mission_id)

    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    return _serialize_mission(mission)


@router.get(
    "/missions/{mission_id}/events",
    response_model=list[MissionEventResponse],
    summary="Get Mission Events",
)
async def get_mission_events_endpoint(
    mission_id: int, req: Request, db: AsyncSession = Depends(get_db)
) -> list[MissionEventResponse]:
    """
    Retrieve historical events for a mission.
    """
    state_manager = MissionStateManager(db)
    events = await state_manager.get_mission_events(mission_id)

    return [
        MissionEventResponse(
            event_type=(
                evt.event_type.value if hasattr(evt.event_type, "value") else str(evt.event_type)
            ),
            mission_id=evt.mission_id,
            timestamp=evt.created_at,
            payload=evt.payload_json or {},
        )
        for evt in events
    ]


@router.websocket("/missions/{mission_id}/ws")
async def stream_mission_ws(
    websocket: WebSocket,
    mission_id: int,
) -> None:
    token, selected_protocol = extract_websocket_auth(websocket)
    if not token:
        await websocket.close(code=4401)
        return

    try:
        decode_user_id(token, get_settings().SECRET_KEY)
    except HTTPException:
        await websocket.close(code=4401)
        return

    await websocket.accept(subprotocol=selected_protocol)

    event_bus = get_event_bus()
    channel = f"mission:{mission_id}"

    # We need a subscription iterator
    subscription = event_bus.subscribe(channel)

    try:
        async with async_session_factory() as session:
            state_manager = MissionStateManager(session)
            mission = await state_manager.get_mission(mission_id)
            if not mission:
                await websocket.close(code=4004)
                return

            status_payload = _get_mission_status_payload(mission.status.value)
            await websocket.send_json({"type": "mission_status", "payload": status_payload})

            events = await state_manager.get_mission_events(mission_id)
            for evt in events:
                evt_type = (
                    evt.event_type.value
                    if hasattr(evt.event_type, "value")
                    else str(evt.event_type)
                )
                payload = evt.payload_json or {}
                await websocket.send_json(
                    {"type": "mission_event", "payload": {"event_type": evt_type, "data": payload}}
                )

    except Exception as e:
        logger.error(f"WS Init Error: {e}")
        await websocket.close(code=1011)
        return

    try:
        while True:
            try:
                async with asyncio.timeout(300.0):
                    event = await anext(subscription)
            except StopAsyncIteration:
                break
            except TimeoutError:
                await websocket.close(code=1011, reason="Timeout waiting for mission events")
                break

            canonical_event = _canonicalize_mission_event(event)
            if canonical_event is None:
                continue

            await websocket.send_json({"type": "mission_event", "payload": canonical_event})

            if canonical_event["event_type"] in ("mission_completed", "mission_failed"):
                # Fetch final status
                async with async_session_factory() as final_session:
                    sm = MissionStateManager(final_session)
                    m = await sm.get_mission(mission_id)
                    if m:
                        status_p = _get_mission_status_payload(m.status.value)
                        await websocket.send_json({"type": "mission_status", "payload": status_p})
                break

    except WebSocketDisconnect:
        logger.info(f"WS Disconnected: {mission_id}")
    except Exception as e:
        logger.error(f"WS Loop Error: {e}")
    finally:
        await websocket.close()
        try:
            await subscription.aclose()
        except Exception as e:
            logger.warning("[WS_CLEANUP] subscription.aclose() failed: %s", e)


# ═══════════════════════════════════════════════════════════════════════════
# Skills Composition Pipeline — /compose (Step 9)
# ═══════════════════════════════════════════════════════════════════════════


class ComposeRequest(BaseModel):
    """طلب تشغيل Skills Composition Pipeline."""

    query: str = Field(..., min_length=1, max_length=2000, description="سؤال الطالب أو المهمة")
    correlation_id: str | None = Field(
        default=None,
        description="معرف التتبع الموزع (يُولَّد تلقائياً إذا لم يُعطَ)",
    )


class SkillResultSchema(BaseModel):
    """نتيجة Skill واحدة في الـ Pipeline."""

    skill: str
    status: str
    data: dict[str, object]
    duration_ms: float
    error: str | None = None


class ComposeResponse(BaseModel):
    """الاستجابة الكاملة من Skills Composition Pipeline."""

    correlation_id: str
    query: str
    composed_answer: str
    pipeline_mode: str
    skills_active: list[str]
    total_duration_ms: float
    composition_confidence: float = 0.0  # D-110: ثقة التركيب [0,1]
    plan: SkillResultSchema
    research: SkillResultSchema
    reasoning: SkillResultSchema


@router.post(
    "/compose",
    response_model=ComposeResponse,
    tags=["Skills Pipeline"],
    summary="Skills Composition Pipeline",
    description=(
        "يُشغِّل Skills Composition Pipeline الكامل:\n"
        "1. PlanningSkill → خطة استراتيجية\n"
        "2. ResearchSkill → معلومات ذات صلة (بالتوازي مع Planning)\n"
        "3. ReasoningSkill → تفكير عميق MCTS + LLM\n"
        "4. Compose → إجابة مُركَّبة من الـ 3 Skills\n\n"
        "Fallback mode تلقائي عند تعذر الوصول لأي Skill."
    ),
)
async def compose_skills(
    request: ComposeRequest,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
) -> ComposeResponse:
    """
    يُنفِّذ Skills Composition Pipeline ويُعيد الإجابة المُركَّبة.

    يُسجِّل مقاييس Prometheus لكل استدعاء:
      - cogniforge_pipeline_invocations_total{mode=...}
      - cogniforge_pipeline_duration_seconds{mode=...}
      - cogniforge_pipeline_skill_calls_total{skill=...,status=...}
      - cogniforge_pipeline_skill_duration_seconds{skill=...}
    """
    correlation_id = request.correlation_id or x_correlation_id or str(uuid.uuid4())

    set_pipeline_active(1)
    try:
        result = await run_skills_pipeline(
            query=request.query,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        set_pipeline_active(0)
        record_pipeline_error("compose_error")
        logger.error("pipeline_error correlation_id=%s error=%s", correlation_id, exc)
        raise HTTPException(
            status_code=502,
            detail={
                "code": "PIPELINE_ERROR",
                "message": str(exc),
                "trace_id": correlation_id,
            },
        ) from exc

    set_pipeline_active(0)

    # تسجيل مقاييس Prometheus
    skill_results = [
        (result.plan.skill, result.plan.status, result.plan.duration_ms / 1000),
        (result.research.skill, result.research.status, result.research.duration_ms / 1000),
        (result.reasoning.skill, result.reasoning.status, result.reasoning.duration_ms / 1000),
    ]
    record_pipeline_invocation(
        mode=result.pipeline_mode,
        duration_seconds=result.total_duration_ms / 1000,
        skill_results=skill_results,
    )

    return ComposeResponse(
        correlation_id=result.correlation_id,
        query=result.query,
        composed_answer=result.composed_answer,
        pipeline_mode=result.pipeline_mode,
        skills_active=result.skills_active,
        total_duration_ms=result.total_duration_ms,
        composition_confidence=result.composition_confidence,
        plan=SkillResultSchema(**result.plan.__dict__),
        research=SkillResultSchema(**result.research.__dict__),
        reasoning=SkillResultSchema(**result.reasoning.__dict__),
    )


# ── Checkpointer Status — /checkpointer/status (Step 10) ─────────────────────


@router.get(
    "/checkpointer/status",
    summary="Postgres Checkpointer Status",
    tags=["observability"],
)
async def checkpointer_status() -> dict:
    """
    يُعيد حالة Postgres Checkpointer الحي.

    Step 10: runtime evidence للـ checkpointer.
    backend: postgres | memory | none
    """
    ckpt = get_checkpointer()

    if ckpt is None:
        return {
            "backend": "memory",
            "step": "10",
            "active": False,
            "tables_ready": False,
            "active_threads": 0,
            "message": "AsyncPostgresSaver not initialised — using MemorySaver fallback",
        }

    active_threads = len(getattr(ckpt, "_active_threads", set()))

    return {
        "backend": "postgres",
        "step": "10",
        "active": True,
        "tables_ready": True,
        "active_threads": active_threads,
        "pool_size": 5,
        "message": "AsyncPostgresSaver ACTIVE — LangGraph state persisted to PostgreSQL",
    }
