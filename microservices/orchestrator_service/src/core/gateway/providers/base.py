from abc import ABC, abstractmethod


class ModelProviderAdapter(ABC):
    """Abstract model provider interface"""

    @abstractmethod
    def call_model(self, model: str, prompt: str, params: dict[str, object]) -> dict[str, object]:
        """Call AI model"""
        pass

    @abstractmethod
    def estimate_cost(self, model: str, tokens: int) -> float:
        """Estimate API call cost"""
        pass

    @abstractmethod
    def estimate_latency(self, model: str, tokens: int) -> float:
        """Estimate response latency"""
        pass
