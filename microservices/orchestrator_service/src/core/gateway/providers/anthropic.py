from .base import ModelProviderAdapter


class AnthropicAdapter(ModelProviderAdapter):
    """Anthropic (Claude) model provider adapter"""

    def call_model(self, model: str, prompt: str, params: dict[str, object]) -> dict[str, object]:
        """Call Anthropic model (placeholder)"""
        return {
            "provider": "anthropic",
            "model": model,
            "response": "Placeholder response",
            "tokens": 100,
        }

    def estimate_cost(self, model: str, tokens: int) -> float:
        """Estimate Anthropic cost"""
        cost_per_1k = 0.008
        return (tokens / 1000) * cost_per_1k

    def estimate_latency(self, model: str, tokens: int) -> float:
        """Estimate Anthropic latency"""
        return 300.0 + (tokens * 0.4)
