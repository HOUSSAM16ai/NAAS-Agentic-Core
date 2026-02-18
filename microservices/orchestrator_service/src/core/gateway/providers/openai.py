from .base import ModelProviderAdapter


class OpenAIAdapter(ModelProviderAdapter):
    """OpenAI model provider adapter"""

    def call_model(self, model: str, prompt: str, params: dict[str, object]) -> dict[str, object]:
        """Call OpenAI model (placeholder)"""
        return {
            "provider": "openai",
            "model": model,
            "response": "Placeholder response",
            "tokens": 100,
        }

    def estimate_cost(self, model: str, tokens: int) -> float:
        """Estimate OpenAI cost"""
        cost_per_1k = 0.002 if "gpt-4" in model else 0.0002
        return (tokens / 1000) * cost_per_1k

    def estimate_latency(self, model: str, tokens: int) -> float:
        """Estimate OpenAI latency"""
        base_latency = 500.0 if "gpt-4" in model else 200.0
        return base_latency + (tokens * 0.5)
