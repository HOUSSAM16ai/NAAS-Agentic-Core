"""مخزن المحادثات — httpx client lifecycle + إنشاء/تحقق المحادثة + حفظ رسائل المساعد.

مستخرَجة حرفياً من ``routes.py`` (D-168 Slice A3). تعتمد على ``chat_types`` +
``chat_context`` من الأشقاء — لا تستورد من ``routes`` أبداً (طبقات باتجاه واحد).
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .chat_context import _build_older_history_digest
from .chat_types import MAX_HISTORY_MESSAGES, MAX_HISTORY_SUMMARY_MESSAGES

logger = logging.getLogger(__name__)


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
