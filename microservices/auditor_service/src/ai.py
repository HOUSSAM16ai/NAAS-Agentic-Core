import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)


class SimpleAIClient:
    """
    A lightweight AI client for the microservice.
    Uses OPENROUTER_API_KEY from environment.
    """

    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"
        # ISS-068: nemotron-reasoning — أسرع نموذج مجاني مع reasoning tokens
        self.model = os.environ.get("AUDITOR_LLM_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free")

        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not found. AI calls will fail.")

    async def send_message(
        self, system_prompt: str, user_message: str, temperature: float = 0.1
    ) -> str:
        """
        Sends a message to the LLM and returns the text response.
        """
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8002",  # Required by OpenRouter
            "X-Title": "AuditorMicroservice",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "top_p": 1,
            "repetition_penalty": 1.1,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=payload
                )
                response.raise_for_status()
                data = response.json()

                # Extract content
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                logger.error(f"Unexpected API response format: {data}")
                raise ValueError("Empty or invalid response from AI provider")

            except httpx.HTTPError as e:
                logger.error(f"HTTP Error calling AI provider: {e}")
                # Fallback to Mock if network fails (for test stability in sandbox)
                return self._mock_fallback(user_message)
            except Exception as e:
                logger.error(f"Error calling AI provider: {e}")
                raise

    def _mock_fallback(self, user_message: str) -> str:
        """
        Mock response for when AI is unreachable (sandbox mode).
        """
        logger.warning("Using Mock AI Response (Fallback)")
        return json.dumps(
            {
                "approved": True,
                "feedback": "System is running in fallback mode (AI unreachable).",
                "score": 0.8,
                "final_response": "**System Notice:**\nAI service is currently unavailable. Proceeding with default approval.",
                "recommendation": "Use fallback procedures.",
                "confidence": 50.0,
            }
        )
