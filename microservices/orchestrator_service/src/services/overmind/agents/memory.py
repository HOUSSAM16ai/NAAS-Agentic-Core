"""
عميل وكيل الذاكرة (Memory Agent Client).
---------------------------------------
يحوّل اللقطات المعرفية إلى صيغة خدمة الذاكرة
ويرسلها عبر واجهة HTTP وفق بروتوكول الميكروسيرفيس.

المعايير:
- CS50 2025 Strict Mode.
- توثيق "Legendary" باللغة العربية.
- فصل واضح بين التحويل والإرسال الشبكي.
"""

from __future__ import annotations

import json
import os

import httpx

from app.core.di import get_logger
from app.core.protocols import AgentMemory, CollaborationContext

logger = get_logger(__name__)


class MemoryAgent(AgentMemory):
    """
    عميل خدمة الذاكرة (Memory Agent).

    يعتمد على خدمة منفصلة لحفظ الذاكرة وفق مبدأ الميكروسيرفيس.
    """

    def __init__(self, *, base_url: str | None = None, timeout: float = 5.0) -> None:
        """
        تهيئة عميل الذاكرة.

        Args:
            base_url: عنوان خدمة الذاكرة.
            timeout: مهلة الطلب بالثواني.
        """
        env_url = os.getenv("MEMORY_AGENT_URL") or os.getenv("ORCHESTRATOR_MEMORY_AGENT_URL")
        self.base_url = base_url or env_url or "http://memory-agent:8002"
        self.timeout = timeout

    async def capture_memory(
        self,
        context: CollaborationContext,
        *,
        label: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        """
        إرسال لقطة معرفية إلى خدمة الذاكرة.

        Args:
            context: سياق التعاون المشترك.
            label: تسمية المرحلة أو الحدث.
            payload: بيانات اللقطة.

        Returns:
            dict: استجابة خدمة الذاكرة أو تقرير خطأ.
        """
        request_payload = self._build_memory_payload(label=label, payload=payload, context=context)
        endpoint = f"{self.base_url}/memories"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(endpoint, json=request_payload)
                response.raise_for_status()
                data = response.json()
                context.update("memory_last_response", data)
                return {"status": "success", "response": data}
            except httpx.HTTPError as exc:
                logger.warning("Memory Agent request failed: %s", exc)
                error_payload = {"status": "failed", "error": str(exc), "endpoint": endpoint}
                context.update("memory_last_response", error_payload)
                return error_payload

    def _build_memory_payload(
        self,
        *,
        label: str,
        payload: dict[str, object],
        context: CollaborationContext,
    ) -> dict[str, object]:
        """
        تحويل اللقطة إلى الصيغة المطلوبة لخدمة الذاكرة.

        Args:
            label: تسمية المرحلة.
            payload: البيانات الخام.
            context: السياق المشترك.

        Returns:
            dict: حمولة متوافقة مع واجهة /memories.
        """
        mission_id = context.get("mission_id")
        objective = context.get("objective")
        content = json.dumps(
            {
                "label": label,
                "payload": payload,
                "mission_id": mission_id,
                "objective": objective,
            },
            ensure_ascii=False,
            default=str,
        )

        tags = ["overmind", "memory_snapshot", f"phase:{label}"]
        if mission_id is not None:
            tags.append(f"mission:{mission_id}")
        if isinstance(payload, dict):
            agent_name = payload.get("agent")
            if isinstance(agent_name, str):
                tags.append(f"agent:{agent_name}")

        return {"content": content, "tags": tags}
