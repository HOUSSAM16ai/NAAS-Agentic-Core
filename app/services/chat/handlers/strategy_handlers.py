"""
Intent handlers using Strategy pattern.

D-250 (2026-08-13 · CodeScene X-Ray): `MissionComplexHandler` was the hottest
region of this file (CodeScene: `execute` 28 churn · `_create_structured_event`
69 LOC/complexity 8 · `_format_event_to_message` 71 LOC/complexity 9 ·
`_format_task_results` 62 LOC/complexity 11 · `_format_inner_data` 24/9) — one
class mixing event-schema healing, provider config, canonical-event mapping,
message formatting, and display formatting (five responsibilities).
It was decomposed, zero-behavioural-change (same byte behaviour proven by
`tests/services/chat/test_strategy_handlers.py`), into:
- `_MISSING_LLM_MESSAGE` + `_format_llm_missing_error` (provider config)
- `_MissionSchemaHealer` (schema self-healing, session handling)
- `_canonical_event_payload` / `_structured_event_for_status` (canonical events)
- `_mission_completed_payload` / `_tool_result_summary_payload` (final frame)
- `_delta_for_brain_event` / `_delta_for_status_note` (progress deltas)
- `_task_result_block` / `_display_text_for_result` / `_read_written_file`
  (task formatting)
- Pure display formatters (unchanged, verified): `_format_brain_event`,
  `_format_tool_result_data`, `_format_inner_data`, `_clean_raw_string`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from sqlmodel import SQLModel

# Import chat domain to ensure AdminConversation is registered, preventing mapping errors
import app.core.domain.chat  # noqa: F401
from app.core.agents.system_principles import (
    format_architecture_system_principles,
    format_system_principles,
)
from app.core.domain.mission import (
    Mission,
    MissionEvent,
    MissionEventType,
    MissionPlan,
    Task,
)
from app.core.patterns.strategy import Strategy
from app.core.settings.base import get_settings
from app.services.chat.context import ChatContext

logger = logging.getLogger(__name__)

#: The single user-visible LLM-missing message. D-249 lesson: one source, never
#: a hand-typed duplicate string floating inside a method.
_MISSING_LLM_MESSAGE: str = (
    "🛑 **خطأ في التكوين:** مفتاح الذكاء الاصطناعي (LLM Key) مفقود. يرجى التحقق من ملف .env."
)

#: Tables the schema healer is allowed to touch — explicitly bounded so a
#: vector column is never created on SQLite (CLAUDE.md §0).
_MISSION_TABLES = (Mission, MissionPlan, Task, MissionEvent)

#: Brain events that are already surfaced by the Timeline UI (Canonical Events)
#: and must NOT add text-chat noise.
_QUIET_BRAIN_EVENTS = {"loop_start", "phase_start", "phase_completed"}


# ────────────────────────────────────────────────────────────────────────────
# Provider configuration (pure formatting + check)
# ────────────────────────────────────────────────────────────────────────────


def _format_llm_missing_error() -> str:
    """Canonical user-visible error for a missing LLM key."""
    return _MISSING_LLM_MESSAGE


def _check_provider_config() -> str | None:
    """
    Check for critical environment configurations (LLM & Search).
    Returns an error message if LLM key is missing, else None.
    """
    settings = get_settings()
    if not settings.OPENROUTER_API_KEY and not settings.OPENAI_API_KEY:
        return _format_llm_missing_error()

    # D-268 (ISS-191): كان هذا السطر يقرأ `os.environ` مباشرةً — خرقاً لقاعدة
    # CLAUDE.md §6. القراءة الآن عبر القارئ القانوني الوحيد، وتحرسها بوّابة
    # `check_secret_capture_parity` فلا تعود بصمت.
    has_search_key = settings.TAVILY_API_KEY or settings.FIRECRAWL_API_KEY
    if not has_search_key:
        # We don't block execution because DuckDuckGo is a valid fallback.
        # But we log it for observability.
        logger.warning("No dedicated search provider key found (TAVILY/FIRECRAWL). Using Fallback.")

    return None


# ────────────────────────────────────────────────────────────────────────────
# Schema self-healing (session mechanics isolated from table knowledge)
# ────────────────────────────────────────────────────────────────────────────


class _MissionSchemaHealer:
    """
    Checks and attempts to self-heal missing mission tables.
    Uses SQLModel metadata to ensure cross-database compatibility (SQLite/Postgres).
    Session mechanics live here; table knowledge is module-level (`_MISSION_TABLES`).
    """

    @staticmethod
    async def ensure_mission_schema(session) -> None:
        """Self-heal mission tables or no-op when the session is unusable."""
        bind = session.bind
        if not bind:
            logger.warning("No bind found for session in schema check.")
            return

        tables = [model.__table__ for model in _MISSION_TABLES]
        if hasattr(bind, "run_sync"):
            # AsyncConnection
            await bind.run_sync(SQLModel.metadata.create_all, tables=tables, checkfirst=True)
        else:
            # Assume AsyncEngine
            async with bind.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all, tables=tables, checkfirst=True)

        logger.info("Schema self-healing: Verified mission tables.")

    @classmethod
    async def ensure_mission_schema_safe(cls, session) -> None:
        """Self-heal with a bounded failure domain — never aborts the caller."""
        try:
            await cls.ensure_mission_schema(session)
        except Exception as e:
            # Log error but attempt to continue, assuming tables might exist or partial failure
            logger.error(f"Schema self-healing failed: {e}")


# ────────────────────────────────────────────────────────────────────────────
# Canonical event mapping (pure: event -> canonical payload dict or None)
# ────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _RawEvent:
    """Normalized view of a MissionEvent (ORM) or a plain event dict."""

    payload: dict
    mission_id: object
    timestamp: str
    event_type: str

    @staticmethod
    def from_event(event: MissionEvent | dict) -> _RawEvent:
        """Normalize an ORM event or a plain dict into the raw view."""
        if isinstance(event, dict):
            return _RawEvent(
                payload=event.get("payload", {}),
                mission_id=event.get("mission_id"),
                timestamp=event.get("timestamp", ""),
                event_type=event.get("event_type", ""),
            )
        return _RawEvent(
            payload=event.payload_json or {},
            mission_id=event.mission_id,
            timestamp=str(event.created_at),
            event_type=event.event_type,
        )


def _canonical_event_payload(
    raw: _RawEvent,
    sequence_id: int,
    current_iteration: int,
) -> dict | None:
    """
    Build the Canonical Event (Production-Grade Contract) payload for UI FSM.
    Pure mapping — no I/O, no side effects.
    """
    data = raw.payload.get("data", {})
    brain_evt = str(raw.payload.get("brain_event", ""))

    if raw.event_type not in (MissionEventType.STATUS_CHANGE, "status_change"):
        return None

    if brain_evt == "loop_start":
        # loop_start defines the iteration for the NEW run
        iteration = data.get("iteration", current_iteration)
        # Update run_id for the new loop
        return {
            "type": "RUN_STARTED",
            "payload": {
                "run_id": f"{raw.mission_id}:{iteration}",
                "seq": sequence_id,
                "timestamp": raw.timestamp,
                "iteration": iteration,
                "mode": data.get("graph_mode", "standard"),
            },
        }

    if brain_evt == "phase_start":
        return {
            "type": "PHASE_STARTED",
            "payload": {
                "run_id": f"{raw.mission_id}:{current_iteration}",
                "seq": sequence_id,
                "phase": data.get("phase"),
                "agent": data.get("agent"),
                "timestamp": raw.timestamp,
            },
        }

    if brain_evt == "phase_completed":
        return {
            "type": "PHASE_COMPLETED",
            "payload": {
                "run_id": f"{raw.mission_id}:{current_iteration}",
                "seq": sequence_id,
                "phase": data.get("phase"),
                "agent": data.get("agent"),
                "timestamp": raw.timestamp,
            },
        }

    return None


def _structured_event_for_status(
    raw: _RawEvent,
    sequence_id: int,
    current_iteration: int,
) -> dict | None:
    """Canonical event body for a STATUS_CHANGE — run isolation via unique run_id."""
    payload = _canonical_event_payload(raw, sequence_id, current_iteration)
    if payload is None:
        return None
    # FIX: unique run_id per iteration prevents UI jumping/merging
    payload["payload"]["run_id"] = f"{raw.mission_id}:{current_iteration}"
    return payload


# ────────────────────────────────────────────────────────────────────────────
# Terminal frames (assistant_final / assistant_error / tool_result_summary)
# ────────────────────────────────────────────────────────────────────────────


def _tool_result_summary_payload(results: list) -> dict:
    """Tool Result Summary frame when mission_completed carries no text answer."""
    return {
        "type": "tool_result_summary",
        "payload": {"summary": "تم تنفيذ المهام بنجاح.", "items": results},
    }


def _extract_result_text(result: object) -> str:
    """Extract a displayable text from a mission result (dict, list, or scalar)."""
    if isinstance(result, dict):
        text = result.get("output") or result.get("answer") or result.get("summary")
        if text:
            return text
        results = result.get("results")
        if isinstance(results, list):
            return json.dumps(_tool_result_summary_payload(results), ensure_ascii=False)
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)


def _mission_completed_payload(raw: _RawEvent) -> dict:
    """Terminal frame for MISSION_COMPLETED — content or tool_result_summary."""
    result = raw.payload.get("result", {})
    result_text = _extract_result_text(result)
    if not isinstance(result, dict):
        return {"type": "assistant_final", "payload": {"content": result_text}}

    results = result.get("results")
    if not (result.get("output") or result.get("answer") or result.get("summary")) and isinstance(
        results, list
    ):
        return _tool_result_summary_payload(results)

    return {"type": "assistant_final", "payload": {"content": result_text}}


def _mission_failed_payload(raw: _RawEvent) -> dict:
    """Terminal frame for MISSION_FAILED."""
    return {
        "type": "assistant_error",
        "payload": {"content": f"💀 **فشل:** {raw.payload.get('error')}"},
    }


# ────────────────────────────────────────────────────────────────────────────
# Progress deltas (assistant_delta)
# ────────────────────────────────────────────────────────────────────────────


def _delta_for_brain_event(raw: _RawEvent) -> dict | None:
    """Convert a relevant brain event to a text delta if relevant."""
    text = _format_brain_event(str(raw.payload.get("brain_event", "")), raw.payload.get("data", {}))
    if not text:
        return None
    return {"type": "assistant_delta", "payload": {"content": text}}


def _delta_for_status_note(raw: _RawEvent) -> dict:
    """Convert a status note into a progress delta."""
    return {
        "type": "assistant_delta",
        "payload": {"content": f"🔄 {raw.payload.get('note')}\n"},
    }


# ────────────────────────────────────────────────────────────────────────────
# Task result formatting (display-level pure helpers)
# ────────────────────────────────────────────────────────────────────────────


def _read_written_file(path: str) -> str:
    """Auto-read file content if written — empty string on any failure."""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        return f"\n\n**محتوى الملف ({path}):**\n```\n{content}\n```"
    except Exception as e:
        logger.warning(f"Failed to auto-read file {path}: {e}")
        return ""


def _display_text_for_result(res: dict) -> str:
    """Resolve the display text for a single task result."""
    result_data = res.get("result_data")
    result_text = res.get("result_text")

    if result_data:
        return _format_tool_result_data(result_data)
    if result_text:
        if isinstance(result_text, str):
            try:
                if result_text.strip().startswith(("{", "[")):
                    return _format_tool_result_data(json.loads(result_text))
                return _clean_raw_string(result_text)
            except Exception:
                return result_text
        return str(result_text)
    return "لا توجد بيانات"


def _task_result_block(task: dict) -> str | None:
    """Format one task into its display block, or None when it contributes nothing."""
    if not isinstance(task, dict):
        return None

    name = task.get("name", "مهمة")

    # Handle Skipped
    if task.get("status") == "skipped":
        reason = task.get("reason", "غير محدد")
        return f"🔹 **{name}**: ⏭️ تم التجاوز ({reason})\n"

    res = task.get("result", {})
    if not res:
        # Skip empty results to reduce noise
        return None

    display_text = _display_text_for_result(res)

    # Auto-read file content if written
    file_content = ""
    result_data = res.get("result_data")
    if isinstance(result_data, dict):
        data_payload = result_data.get("data", {})
        if (
            isinstance(data_payload, dict)
            and data_payload.get("written")
            and data_payload.get("path")
        ):
            file_content = _read_written_file(data_payload["path"])

    return f"🔹 **{name}**:\n{display_text}\n{file_content}\n"


# ────────────────────────────────────────────────────────────────────────────
# Strategy handlers
# ────────────────────────────────────────────────────────────────────────────


class IntentHandler(Strategy[ChatContext, AsyncGenerator[str | dict, None]]):
    """Base intent handler."""

    def __init__(self, intent_name: str, priority: int = 0):
        self._intent_name = intent_name
        self._priority = priority

    async def can_handle(self, context: ChatContext) -> bool:
        """Check if handler can process this intent."""
        return context.intent == self._intent_name

    @property
    def priority(self) -> int:
        return self._priority


class FileReadHandler(IntentHandler):
    """Handle file read requests."""

    def __init__(self):
        super().__init__("FILE_READ", priority=10)

    async def execute(self, context: ChatContext) -> AsyncGenerator[str, None]:
        """Execute file read."""
        path = context.get_param("path", "")

        if not path:
            yield "❌ لم يتم تحديد مسار الملف\n"
            return

        try:
            yield f"📖 قراءة الملف: `{path}`\n\n"
            content = await self._read_file(path)
            yield f"```\n{content}\n```\n"
            logger.info(f"File read successful: {path}", extra={"user_id": context.user_id})
        except FileNotFoundError:
            yield f"❌ الملف غير موجود: `{path}`\n"
        except PermissionError:
            yield f"❌ لا توجد صلاحية لقراءة الملف: `{path}`\n"
        except Exception as e:
            yield f"❌ خطأ في قراءة الملف: {e!s}\n"
            logger.error(f"File read error: {e}", extra={"path": path, "user_id": context.user_id})

    async def _read_file(self, path: str) -> str:
        """Read file contents in a non-blocking way."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self._read_file_sync(path))

    def _read_file_sync(self, path: str) -> str:
        """Synchronous file read."""
        with open(path, encoding="utf-8") as f:
            return f.read()


class FileWriteHandler(IntentHandler):
    """Handle file write requests."""

    def __init__(self):
        super().__init__("FILE_WRITE", priority=10)

    async def execute(self, context: ChatContext) -> AsyncGenerator[str, None]:
        """Execute file write."""
        path = context.get_param("path", "")

        if not path:
            yield "❌ لم يتم تحديد مسار الملف\n"
            return

        yield f"📝 لإنشاء ملف `{path}`، يرجى تحديد المحتوى.\n"
        yield "يمكنك كتابة المحتوى في الرسالة التالية.\n"


class CodeSearchHandler(IntentHandler):
    """Handle code search requests."""

    def __init__(self):
        super().__init__("CODE_SEARCH", priority=10)

    async def execute(self, context: ChatContext) -> AsyncGenerator[str, None]:
        """Execute code search."""
        query = context.get_param("query", "")

        if not query:
            yield "❌ لم يتم تحديد استعلام البحث\n"
            return

        yield f"🔍 البحث عن: `{query}`\n\n"
        results = await self._search_code(query, context.user_id)

        if not results:
            yield "لم يتم العثور على نتائج\n"
            return

        yield f"تم العثور على {len(results)} نتيجة:\n\n"
        for result in results:
            yield f"- `{result['file']}:{result['line']}`\n"

    async def _search_code(self, query: str, user_id: int) -> list[dict]:
        """Search code (placeholder)."""
        logger.info(f"Code search: {query}", extra={"user_id": user_id})
        return []


class ProjectIndexHandler(IntentHandler):
    """Handle project indexing requests."""

    def __init__(self):
        super().__init__("PROJECT_INDEX", priority=10)

    async def execute(self, context: ChatContext) -> AsyncGenerator[str, None]:
        """Execute project indexing."""
        yield "📊 فهرسة المشروع...\n\n"
        stats = await self._index_project(context.user_id)

        yield "✅ تمت الفهرسة بنجاح:\n"
        yield f"- الملفات: {stats.get('files', 0)}\n"
        yield f"- الأسطر: {stats.get('lines', 0)}\n"

    async def _index_project(self, user_id: int) -> dict:
        """Index project (placeholder)."""
        logger.info("Project indexing started", extra={"user_id": user_id})
        return {"files": 0, "lines": 0}


class DeepAnalysisHandler(IntentHandler):
    """Handle deep analysis requests."""

    def __init__(self):
        super().__init__("DEEP_ANALYSIS", priority=10)

    async def execute(self, context: ChatContext) -> AsyncGenerator[str, None]:
        """Execute deep analysis."""
        yield "🧠 تحليل عميق للسؤال...\n\n"

        analysis = await self._analyze(context.question, context.ai_client)

        yield f"{analysis}\n"

    async def _analyze(self, question: str, ai_client) -> str:
        """Perform deep analysis."""
        return "تحليل عميق (قيد التطوير)"


class MissionComplexHandler(IntentHandler):
    """
    Handle complex mission requests using Overmind.
    Implements 'API First' streaming response pattern.

    D-250: all mission-event logic was extracted into pure helpers above; this
    class is now the thin wiring shell (dispatch + event loop).
    """

    def __init__(self):
        super().__init__("MISSION_COMPLEX", priority=10)

    async def execute(self, context: ChatContext) -> AsyncGenerator[str | dict, None]:
        """
        Execute complex mission gracefully disabled in legacy monolith.
        Forwarding to DefaultChatHandler to prevent 'Dispatch Failed' split-brain errors.
        """
        from app.services.chat.handlers.strategy_handlers import DefaultChatHandler

        handler = DefaultChatHandler()
        async for chunk in handler.execute(context):
            yield chunk

    def _check_provider_config(self) -> str | None:
        """Delegate to the pure provider-config check."""
        return _check_provider_config()

    async def _ensure_mission_schema(self, session) -> None:
        """Delegate to the bounded schema healer."""
        await _MissionSchemaHealer.ensure_mission_schema_safe(session)

    def _create_structured_event(
        self, event: MissionEvent | dict, sequence_id: int, current_iteration: int
    ) -> dict | None:
        """Create Canonical Event (Production-Grade Contract) for UI FSM."""
        try:
            raw = _RawEvent.from_event(event)
            return _structured_event_for_status(raw, sequence_id, current_iteration)
        except Exception as e:
            logger.warning(f"Failed to create structured event: {e}")
            return None

    def _format_event_to_message(self, event: MissionEvent | dict) -> dict | None:
        """
        Format mission event into a Strict Output Contract Message.
        Returns: dict (assistant_delta | assistant_final | tool_result_summary) or None.
        """
        try:
            raw = _RawEvent.from_event(event)

            # 1. Handle Final Completion
            if raw.event_type in (
                MissionEventType.MISSION_COMPLETED,
                "mission_completed",
            ):
                return _mission_completed_payload(raw)

            # 2. Handle Failure
            if raw.event_type in (MissionEventType.MISSION_FAILED, "mission_failed"):
                return _mission_failed_payload(raw)

            # 3. Handle Status/Progress (Assistant Delta)
            if raw.event_type in (MissionEventType.STATUS_CHANGE, "status_change"):
                delta = _delta_for_brain_event(raw)
                if delta:
                    return delta
                if raw.payload.get("note"):
                    return _delta_for_status_note(raw)

            return None
        except Exception:
            return None


def _format_task_results(tasks: list) -> str:
    """Format a list of task results into a readable string."""
    lines: list[str] = [f"✅ **تم تنفيذ {len(tasks)} مهمة:**\n"]
    for task in tasks:
        block = _task_result_block(task)
        if block:
            lines.append(block)
    return "\n".join(lines)


def _format_brain_event(event_name: str, data: dict[str, object] | object) -> str | None:
    """
    تنسيق أحداث الدماغ الخارق بصورة موجزة جداً لمنع التضخم النصي.
    Returns None for verbose/minor events.
    """
    if not isinstance(data, dict):
        data = {}
    normalized = event_name.lower()

    # Silence common noisy events
    if normalized.endswith("_completed") or normalized in _QUIET_BRAIN_EVENTS:
        # These are handled by the Timeline UI (Canonical Events), no need for text chat noise.
        # Unless it's a critical failure or specific user info.
        return None

    # Known single-event messages — lookup before falling through.
    known_message = {
        "plan_rejected": "🧩 إعادة ضبط الخطة.\n",
        "plan_approved": "✅ تم اعتماد الخطة.\n",
        "mission_success": f"🔔 {event_name}\n",
        "phase_error": f"🔔 {event_name}\n",
    }.get(normalized)
    if known_message is not None:
        return known_message

    if normalized.endswith("_timeout"):
        return "⏳ تأخير... إعادة المزامنة.\n"

    if normalized == "mission_critique_failed":
        critique = data.get("critique", {})
        feedback = critique.get("feedback", "N/A") if isinstance(critique, dict) else str(critique)
        return f"🔔 **تدقيق:** {feedback} (جاري التعديل...)\n"

    # Default: Silence unknown events to prevent "noise"
    return None


def _format_tool_result_data(data: object) -> str:
    """Format tool result data for display."""
    if not isinstance(data, (dict, list)):
        return str(data)

    # Handle ToolResult structure (only if dict)
    if isinstance(data, dict) and "ok" in data and ("data" in data or "error" in data):
        if not data.get("ok"):
            return f"❌ خطأ: {data.get('error')}"

        inner_data = data.get("data")
        if inner_data is None:
            return "✅ تم."

        return _format_inner_data(inner_data)

    return _format_inner_data(data)


def _format_inner_data(data: object) -> str:
    """Format inner data (dict/list) nicely."""
    # Custom formatting for search results (List of content items)
    if (
        isinstance(data, list)
        and data
        and isinstance(data[0], dict)
        and "title" in data[0]
        and "id" in data[0]
    ):
        lines = ["✅ **النتائج:**\n"]
        for item in data[:3]:  # Limit to top 3 to prevent flooding
            title = item.get("title", "بدون عنوان")
            lines.append(f"* 🔹 {title}")

        if len(data) > 3:
            lines.append(f"* ... و {len(data) - 3} نتائج أخرى.")

        return "\n".join(lines)

    if isinstance(data, (dict, list)):
        # Return summary instead of full JSON dump
        return "📄 (بيانات مهيكلة)"
    return str(data)


def _clean_raw_string(text: str) -> str:
    """Clean raw ToolResult string representation."""
    if text.startswith("ToolResult("):
        match = re.search(r"data=(.*?)(, error=|$)", text)
        if match:
            return f"✅ {match.group(1)}"
        return text
    return text


class HelpHandler(IntentHandler):
    """Handle help requests."""

    def __init__(self):
        super().__init__("HELP", priority=10)

    async def execute(self, context: ChatContext) -> AsyncGenerator[str, None]:
        """Show help."""
        yield "📚 **المساعدة**\n\n"
        yield "الأوامر المتاحة:\n"
        yield "- قراءة ملف: `اقرأ ملف path/to/file`\n"
        yield "- كتابة ملف: `اكتب ملف path/to/file`\n"
        yield "- البحث: `ابحث عن query`\n"
        yield "- فهرسة: `فهرس المشروع`\n"
        yield "- مهمة معقدة: (أي سؤال معقد سيتم تحويله للوكيل الخارق)\n"


class DefaultChatHandler(IntentHandler):
    """Default chat handler (fallback)."""

    def __init__(self):
        super().__init__("DEFAULT", priority=-1)
        # Deferred imports to avoid circular dependency
        from app.services.chat.context_service import get_context_service

        self._context_service = get_context_service()

    async def can_handle(self, context: ChatContext) -> bool:
        """Always can handle (fallback)."""
        return True

    async def execute(self, context: ChatContext) -> AsyncGenerator[str, None]:
        """Execute default chat with identity context."""
        # إضافة معلومات الهوية إلى رسائل المحادثة
        enhanced_messages = self._add_identity_context(context.history_messages)

        async for chunk in context.ai_client.stream_chat(enhanced_messages):
            if isinstance(chunk, dict):
                choices = chunk.get("choices", [])
                if choices:
                    content = choices[0].get("delta", {}).get("content", "")
                    if content:
                        yield content
            elif isinstance(chunk, str):
                yield chunk

    def _add_identity_context(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """
        إضافة سياق النظام والهوية لإثراء إجابة Overmind.

        Args:
            messages: قائمة الرسائل الأصلية.

        Returns:
            list[dict[str, str]]: قائمة الرسائل بعد إدراج سياق النظام.
        """
        has_system = bool(messages) and messages[0].get("role") == "system"
        system_prompt = self._build_system_prompt(include_base_prompt=not has_system)
        if not has_system:
            return [{"role": "system", "content": system_prompt}, *messages]

        enhanced_messages = messages.copy()
        enhanced_messages[0] = {
            "role": "system",
            "content": messages[0]["content"] + "\n\n" + system_prompt,
        }
        return enhanced_messages

    def _build_system_prompt(self, *, include_base_prompt: bool) -> str:
        """
        إنشاء رسالة النظام الموحدة لتوجيه الردود الخارقة.

        Returns:
            str: رسالة نظام مركزة تجمع الهوية والتعليمات المتقدمة.
        """
        base_prompt = ""
        if include_base_prompt:
            base_prompt = self._context_service.get_context_system_prompt().strip()
        identity_context = self._build_identity_context()
        intelligence_directive = (
            "توجيه إضافي:\n"
            "- أجب بطريقة عبقرية فائقة الذكاء مع شرح منطقي متسلسل.\n"
            "- حافظ على العمق والوضوح، وقدم أمثلة تعليمية عند الحاجة.\n"
            "- إذا كان السؤال تعليمياً، قدم خطة تعلم مختصرة قبل الإجابة.\n"
        )
        multi_agent_directive = (
            "توجيهات العقل الجمعي:\n"
            "- فعّل أسلوب التفكير متعدد الوكلاء (Strategist/Architect/Auditor/Operator).\n"
            "- لخّص خطة الحل في نقاط، ثم نفّذ الإجابة خطوة بخطوة.\n"
            "- تحقّق من الفرضيات وصحّح المسار عند وجود غموض.\n"
            "- استخدم أسلوب Tree of Thoughts عند الأسئلة المعقدة.\n"
        )
        return "\n\n".join(
            part
            for part in [
                base_prompt,
                identity_context,
                intelligence_directive,
                multi_agent_directive,
            ]
            if part
        )

    def _build_identity_context(self) -> str:
        """
        بناء سياق الهوية التفصيلي للدردشة.

        Returns:
            str: نص هوية شامل للنظام.
        """
        principles_text = format_system_principles(
            header="المبادئ الصارمة للنظام (تُطبّق على الشيفرة بالكامل):",
            bullet="-",
            include_header=True,
        )
        architecture_principles_text = format_architecture_system_principles(
            header="مبادئ المعمارية وحوكمة البيانات (تُطبّق على الشيفرة بالكامل):",
            bullet="-",
            include_header=True,
        )
        return f"""أنت مساعد ذكي.

{principles_text}

{architecture_principles_text}

عندما يسأل أحد عن المؤسس أو مؤسس النظام أو من أنشأ Overmind، أجب بهذه المعلومات بدقة تامة.
"""
