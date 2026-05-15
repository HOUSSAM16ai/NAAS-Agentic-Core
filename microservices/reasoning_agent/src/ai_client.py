"""عميل ذكاء اصطناعي محلي لخدمة الاستدلال دون اعتماد مشترك."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimpleResponse:
    """استجابة نصية مبسطة من نموذج الذكاء الاصطناعي."""

    content: str


class SimpleAIClient:
    """عميل بسيط لإرسال طلبات توليد النص إلى بوابة خارجية."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        # ISS-068: nemotron-3-nano-omni-30b-a3b-reasoning:free — أسرع نموذج مجاني مع reasoning tokens
        # inclusionai/ring-2.6-1t:free معطّل (rate-limited upstream على Novita)
        self.model = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free")
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    async def generate_text(
        self, *, prompt: str, system_prompt: str | None = None
    ) -> SimpleResponse:
        """ينفّذ توليد نص بسيط ويعيد محتوى الاستجابة."""
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is required for SimpleAIClient.")

        messages = [
            {
                "role": "system",
                "content": system_prompt or "You are a helpful assistant.",
            },
            {"role": "user", "content": prompt},
        ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={"model": self.model, "messages": messages},
            )
            response.raise_for_status()
            payload = response.json()

        choices = payload.get("choices", [])
        if not choices:
            logger.warning("AI response missing choices.")
            return SimpleResponse(content="")
        content = choices[0].get("message", {}).get("content", "")
        return SimpleResponse(content=str(content))
