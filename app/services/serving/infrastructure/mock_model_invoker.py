# app/services/serving/infrastructure/mock_model_invoker.py
"""
Mock Model Invoker for Testing and Development
===============================================
Simulates model inference without actual model loading.

Replace with real invokers (OpenAI, TorchServe, etc.) in production.
"""

from __future__ import annotations

import random
import time
from typing import Any

from app.services.serving.domain.models import (
    ModelRequest,
    ModelResponse,
    ModelStatus,
    ModelVersion,
)


class MockModelInvoker:
    """
    Mock implementation of ModelInvoker port.

    Simulates inference with configurable latency and responses.
    Useful for testing, development, and load testing.
    """

    def __init__(
        self,
        simulate_latency: bool = True,
        min_latency_ms: float = 10.0,
        max_latency_ms: float = 500.0,
        error_rate: float = 0.0,
    ):
        """
        Initialize mock invoker.

        Args:
            simulate_latency: Whether to simulate processing time
            min_latency_ms: Minimum simulated latency
            max_latency_ms: Maximum simulated latency
            error_rate: Probability of returning an error (0.0 to 1.0)
        """
        self.simulate_latency = simulate_latency
        self.min_latency_ms = min_latency_ms
        self.max_latency_ms = max_latency_ms
        self.error_rate = error_rate

    def invoke(
        self,
        model: ModelVersion,
        request: ModelRequest,
    ) -> ModelResponse:
        """
        محاكاة استدعاء النموذج
        Simulate model inference.

        Returns a mock response with simulated processing time.
        """
        start_time = time.time()

        # Check if model is ready
        if model.status != ModelStatus.READY:
            return self._create_not_ready_response(model, request)

        # Simulate latency
        self._simulate_processing_delay()

        # Simulate random errors
        if random.random() < self.error_rate:
            return self._create_error_response(model, request, start_time)

        # Generate successful response
        return self._create_success_response(model, request, start_time)

    def _create_not_ready_response(
        self, model: ModelVersion, request: ModelRequest
    ) -> ModelResponse:
        """
        إنشاء استجابة لنموذج غير جاهز
        Create response for model not ready.
        """
        return ModelResponse(
            request_id=request.request_id,
            model_id=model.model_name,
            version_id=model.version_id,
            output_data=None,
            latency_ms=0.0,
            success=False,
            error=f"Model not ready (status: {model.status.value})",
        )

    def _simulate_processing_delay(self) -> None:
        """
        محاكاة وقت المعالجة
        Simulate processing latency.
        """
        if self.simulate_latency:
            latency_ms = random.uniform(self.min_latency_ms, self.max_latency_ms)
            time.sleep(latency_ms / 1000.0)

    def _create_error_response(
        self, model: ModelVersion, request: ModelRequest, start_time: float
    ) -> ModelResponse:
        """
        إنشاء استجابة خطأ محاكاة
        Create simulated error response.
        """
        actual_latency = (time.time() - start_time) * 1000
        return ModelResponse(
            request_id=request.request_id,
            model_id=model.model_name,
            version_id=model.version_id,
            output_data=None,
            latency_ms=actual_latency,
            success=False,
            error="Simulated random error",
        )

    def _create_success_response(
        self, model: ModelVersion, request: ModelRequest, start_time: float
    ) -> ModelResponse:
        """
        إنشاء استجابة نجاح
        Create successful response.
        """
        output_data = self._generate_mock_output(model, request)
        actual_latency = (time.time() - start_time) * 1000
        total_tokens = self._calculate_token_usage(request, output_data)

        return ModelResponse(
            request_id=request.request_id,
            model_id=model.model_name,
            version_id=model.version_id,
            output_data=output_data,
            latency_ms=actual_latency,
            tokens_used=total_tokens,
            cost_usd=self._estimate_cost(model, total_tokens),
            success=True,
        )

    def _calculate_token_usage(self, request: ModelRequest, output_data: dict) -> int:
        """
        حساب استخدام الرموز
        Calculate token usage (simplified estimation).
        """
        input_tokens = len(str(request.input_data)) // 4
        output_tokens = len(str(output_data)) // 4
        return input_tokens + output_tokens

    def health_check(self, model: ModelVersion) -> bool:
        """
        فحص صحة النموذج
        Check if model is healthy.
        """
        return model.status in (ModelStatus.READY, ModelStatus.SERVING)

    def _generate_mock_output(
        self,
        model: ModelVersion,
        request: ModelRequest,
    ) -> dict[str, Any]:
        """
        إنشاء مخرجات محاكاة واقعية
        Generate realistic mock output based on model type.
        """
        from app.services.serving.domain.models import ModelType

        if model.model_type == ModelType.LANGUAGE_MODEL:
            return self._generate_language_model_output(model, request)
        if model.model_type == ModelType.EMBEDDING_MODEL:
            return self._generate_embedding_output(model)
        if model.model_type == ModelType.VISION_MODEL:
            return self._generate_vision_output(model)

        return self._generate_generic_output(model, request)

    def _generate_language_model_output(
        self, model: ModelVersion, request: ModelRequest
    ) -> dict[str, Any]:
        """
        إنشاء استجابة نموذج لغوي
        Generate language model response.
        """
        input_text = str(request.input_data.get("prompt", ""))
        return {
            "text": f"Mock response for: {input_text[:50]}...",
            "finish_reason": "stop",
            "model": model.model_name,
        }

    def _generate_embedding_output(self, model: ModelVersion) -> dict[str, Any]:
        """
        إنشاء استجابة تضمين
        Generate embedding response.
        """
        return {
            "embedding": [random.random() for _ in range(384)],
            "model": model.model_name,
        }

    def _generate_vision_output(self, model: ModelVersion) -> dict[str, Any]:
        """
        إنشاء استجابة نموذج رؤية
        Generate vision model response.
        """
        return {
            "labels": [
                {"label": "cat", "confidence": 0.92},
                {"label": "dog", "confidence": 0.05},
                {"label": "bird", "confidence": 0.03},
            ],
            "model": model.model_name,
        }

    def _generate_generic_output(
        self, model: ModelVersion, request: ModelRequest
    ) -> dict[str, Any]:
        """
        إنشاء استجابة عامة
        Generate generic response.
        """
        return {
            "result": f"Processed by {model.model_name}",
            "request_id": request.request_id,
        }

    def _estimate_cost(self, model: ModelVersion, tokens: int) -> float:
        """Estimate cost based on token usage"""
        # Simplified cost model
        # Real implementation would use actual pricing tables
        cost_per_1k_tokens = 0.002  # $0.002 per 1K tokens
        return (tokens / 1000.0) * cost_per_1k_tokens
