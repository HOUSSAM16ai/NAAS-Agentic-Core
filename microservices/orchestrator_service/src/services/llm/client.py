"""
AI Client for Orchestrator Service.
Provides a simple interface to OpenAI-compatible LLMs.
"""

import logging
import os
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk

from microservices.orchestrator_service.src.core.config import get_settings

logger = logging.getLogger("ai-client")


class AIClient:
    """
    Simple AI Client for Orchestrator Service.
    Wraps AsyncOpenAI to provide generate and stream_chat methods.
    """

    def __init__(self) -> None:
        from openai import OpenAI

        settings = get_settings()
        if settings.OPENROUTER_API_KEY:
            api_key = settings.OPENROUTER_API_KEY
            base_url = "https://openrouter.ai/api/v1"
        else:
            api_key = settings.OPENAI_API_KEY
            base_url = None

        if not api_key:
            logger.warning("No API Key found for AI Client. AI features will fail.")

        self.client = AsyncOpenAI(
            api_key=api_key or "dummy-key",
            base_url=base_url,
        )

        self.sync_client = OpenAI(
            api_key=api_key or "dummy-key",
            base_url=base_url,
        )
        # ISS-STREAM-002: z-ai/glm-4.5-air:free يدعم token-level streaming حقيقي عبر OpenRouter
        # nvidia/nemotron-3-super-120b-a12b:free كان يُعيد chunk واحد فقط → لا typing effect
        self.default_model = os.getenv(
            "ORCHESTRATOR_LLM_MODEL", "z-ai/glm-4.5-air:free"
        )

    async def generate(
        self,
        model: str | None = None,
        messages: list[dict[str, str]] | None = None,
        **kwargs: object,
    ) -> object:
        """
        Generate a complete response.
        If 'response_format' is JSON, returns the parsed object if possible, or the raw response.
        Use for non-streaming tasks.
        """
        target_model = model or self.default_model
        if not messages:
            messages = [{"role": "user", "content": kwargs.get("prompt", "")}]

        try:
            return await self.client.chat.completions.create(
                model=target_model,
                messages=messages,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"AI Generation failed: {e}")
            raise

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs: object,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        Stream chat completion.
        Yields ChatCompletionChunk objects (OpenAI SDK type).
        Use extract_stream_content() to get text from each chunk safely.
        """
        target_model = model or self.default_model
        try:
            stream = await self.client.chat.completions.create(
                model=target_model,
                messages=messages,
                stream=True,
                **kwargs,
            )
            async for chunk in stream:
                yield chunk
        except Exception as e:
            logger.error(f"AI Stream failed: {e}")
            raise

    @staticmethod
    def extract_stream_content(chunk: object) -> str | None:
        """
        يستخرج محتوى النص من chunk بأمان سواء كان ChatCompletionChunk أو dict.

        ISS-STREAM-002: الإصلاح الجراحي — stream_chat يُعيد ChatCompletionChunk objects
        (OpenAI SDK) وليس dicts. الكود القديم كان يستخدم chunk.get('choices') مما يُسبب
        AttributeError يُبتلع بـ except → لا يُصدر أي محتوى → timeout كارثي.
        """
        # ChatCompletionChunk (OpenAI SDK object)
        if hasattr(chunk, "choices"):
            choices = chunk.choices
            if choices and len(choices) > 0:
                delta = choices[0].delta
                if delta is not None:
                    content = getattr(delta, "content", None)
                    if isinstance(content, str) and content:
                        return content
            return None

        # dict fallback (legacy/mock)
        if isinstance(chunk, dict):
            choices = chunk.get("choices")
            if choices and len(choices) > 0:
                delta = choices[0]
                if isinstance(delta, dict):
                    content = delta.get("delta", {}).get("content")
                else:
                    content = getattr(getattr(delta, "delta", None), "content", None)
                if isinstance(content, str) and content:
                    return content
        return None

    async def generate_text(self, prompt: str, **kwargs: object) -> str:
        """Helper for simple text generation."""
        response = await self.generate(prompt=prompt, **kwargs)
        return response.choices[0].message.content or ""

    def generate_sync(
        self,
        model: str | None = None,
        messages: list[dict[str, str]] | None = None,
        **kwargs: object,
    ) -> object:
        """
        Generate a complete response synchronously.
        """
        target_model = model or self.default_model
        if not messages:
            messages = [{"role": "user", "content": kwargs.get("prompt", "")}]

        try:
            return self.sync_client.chat.completions.create(
                model=target_model,
                messages=messages,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"AI Sync Generation failed: {e}")
            raise


# Singleton instance
ai_client = AIClient()


def get_ai_client() -> AIClient:
    return ai_client
