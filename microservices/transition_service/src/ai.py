"""المحرك اللغوي لخدمة التحول — سرد وتفسير فقط، لا يقرر الأرقام.

يحترم LLM_MOCK_MODE (نفس اصطلاح بقية خدمات المستودع) ويستخدم OpenRouter
كباقي الخدمات. أي مخرج لغوي يُنتج **تفسير** بيانات حتمية من `core.engine`؛
إذا تطلب الوكيل رقماً أو تصنيفاً فعليه استعمال المحرك الحتمي أولاً.

**D-189 · D-185 (نمط التوريد):** نداءات الخدمة الصادرة تمر عبر نسخة مورّدة
محروسة من `shared.http_client.correlated` (`core/correlated_http.py`) —
لا بناء مباشر لـ `httpx.AsyncClient` خارج المصنع المصرَّح (بوابة
`scripts/fitness/check_correlated_http.py` تراقب ذلك عبر AST). المصدر
الوحيد هو `shared/http_client/correlated.py`، والنسخة المورّدة في
`core/correlated_http.py` منسوخةٌ حرفياً منه (D-185).
"""

from __future__ import annotations

import logging
import os

from pydantic_settings import BaseSettings

from .core.correlated_http import correlated_client

logger = logging.getLogger("transition_service.ai")

LLM_MOCK_MODE = os.environ.get("LLM_MOCK_MODE", "0") == "1"


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "openai/gpt-oss-20b"

    class Config:
        env_prefix = ""


def _get_settings() -> Settings:
    return Settings(openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""))


def mock_llm(prompt: str) -> str:
    """نمط المحاكاة — CI والمستخدمون بلا مفتاح يحصلون على تفسير حتمي واضح."""
    return (
        "⚙️ [وضع المحاكاة — لا يوجد نموذج لغوي متصل] "
        "المخرجات العددية والمؤشرات حتمية وصالحة للتدقيق؛ "
        "هذا النص توضيحي مؤقت حتى يُربط نموذج لغوي عبر OPENROUTER_API_KEY."
    )


async def llm_narrate(prompt: str) -> str:
    """يولّد سرداً تفسيرياً موجزاً لمخرجات حتمية — لا يقرر أي رقم."""
    if LLM_MOCK_MODE:
        return mock_llm(prompt)
    try:
        settings = _get_settings()
        if not settings.openrouter_api_key:
            return mock_llm(prompt)
        async with correlated_client(timeout=60.0) as client:
            response = await client.post(
                f"{settings.base_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                auth=("Bearer", settings.openrouter_api_key),
                json={
                    "model": settings.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "أنت مفسّر منظومة تحول الذكاء الاصطناعي. سرد تفسيرات المخرجات الحتمية "
                                "بأمانة — لا تخترع أرقاماً ولا مؤشرات غير موجودة في المدخل."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 600,
                },
            )
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])
    except Exception as exc:
        logger.warning("LLM unavailable — falling back to mock narration: %s", exc)
        return mock_llm(prompt)
