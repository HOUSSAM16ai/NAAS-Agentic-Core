"""
نظام التوجيه الذكي (Intelligent Routing System).

يحتوي هذا الملف على المنطق الأساسي لتوجيه الطلبات بين مزودي الخدمة المختلفين،
مع مراعاة التكلفة، وزمن الاستجابة، وصحة الخدمة (Circuit Breaker).

المبادئ (Principles):
- Resilience: استخدام قاطع الدائرة لمنع الفشل المتسلسل.
- Intelligence: اتخاذ قرارات التوجيه بناءً على البيانات.
- KISS: تقسيم المنطق المعقد إلى دوال صغيرة ومفهومة.
"""

from __future__ import annotations

import logging
import math
import threading
from collections import deque
from datetime import UTC, datetime
from typing import TypedDict

from app.core.types import Metadata

from .models import (
    LoadBalancerState,
    ProtocolType,
    ProviderCandidate,
    RoutingDecision,
    RoutingStrategy,
)
from .providers.anthropic import AnthropicAdapter
from .providers.base import ModelProviderAdapter
from .providers.openai import OpenAIAdapter
from .strategies.implementations import get_strategy

logger = logging.getLogger(__name__)


class CircuitBreakerState(TypedDict):
    """
    بنية بيانات حالة قاطع الدائرة.

    Attributes:
        failures (int): عدد مرات الفشل المتتالية.
        last_failure (datetime | None): توقيت آخر فشل.
        open (bool): هل الدائرة مفتوحة (محظورة)؟
    """

    failures: int
    last_failure: datetime | None
    open: bool


class RoutingHistoryEntry(TypedDict):
    """بنية سجل تاريخ التوجيه."""

    timestamp: datetime
    decision: RoutingDecision
    model_type: str
    tokens: int


class SuperCircuitBreaker:
    """
    قاطع الدائرة الخارق (Super Circuit Breaker).

    يمنع الفشل المتسلسل عبر إيقاف إرسال الطلبات إلى الخدمات المتعثرة مؤقتاً.
    يدعم حالات: Closed (يعمل)، Open (متوقف)، Half-Open (اختبار التعافي).
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state: dict[str, CircuitBreakerState] = {}
        self.lock = threading.RLock()

    def report_failure(self, service_id: str) -> None:
        """تسجيل فشل لخدمة معينة وتحديث حالتها."""
        with self.lock:
            if service_id not in self.state:
                self._init_service_state(service_id)

            self.state[service_id]["failures"] += 1
            self.state[service_id]["last_failure"] = datetime.now(UTC)

            if self.state[service_id]["failures"] >= self.failure_threshold:
                self.state[service_id]["open"] = True
                logger.warning(
                    f"Circuit Breaker OPEN for {service_id}. Failures: {self.state[service_id]['failures']}"
                )

    def report_success(self, service_id: str) -> None:
        """تسجيل نجاح وإعادة تعيين عداد الفشل."""
        with self.lock:
            if service_id in self.state:
                self.state[service_id]["failures"] = 0
                self.state[service_id]["open"] = False

    def is_open(self, service_id: str) -> bool:
        """التحقق مما إذا كانت الدائرة مفتوحة (الخدمة محظورة)."""
        with self.lock:
            if service_id not in self.state:
                return False
            if not self.state[service_id]["open"]:
                return False

            return not self._should_attempt_recovery(service_id)

    def _init_service_state(self, service_id: str) -> None:
        self.state[service_id] = {
            "failures": 0,
            "last_failure": None,
            "open": False,
        }

    def _should_attempt_recovery(self, service_id: str) -> bool:
        last_failure = self.state[service_id].get("last_failure")
        if last_failure:
            elapsed = (datetime.now(UTC) - last_failure).total_seconds()
            if elapsed > self.recovery_timeout:
                logger.info(f"Circuit Breaker HALF-OPEN for {service_id}")
                return True
        return False


class IntelligentRouter:
    """
    محرك التوجيه الذكي (Intelligent Routing Engine).

    المميزات:
    - توجيه مدرك للتكلفة (Cost-aware).
    - توجيه محسن لزمن الاستجابة (Latency-optimized).
    - موازنة الأحمال بين المزودين.
    - تكامل مع قاطع الدائرة.
    """

    def __init__(self) -> None:
        self.provider_adapters: dict[str, ModelProviderAdapter] = {
            "openai": OpenAIAdapter(),
            "anthropic": AnthropicAdapter(),
        }
        self.routing_history: deque[RoutingHistoryEntry] = deque(maxlen=10000)
        self.circuit_breaker = SuperCircuitBreaker()

        # تهيئة ديناميكية لحالة موازن الأحمال
        class AutoInitDict(dict[str, LoadBalancerState]):
            def __missing__(self, key: str) -> LoadBalancerState:
                value = LoadBalancerState(service_id=str(key))
                self[key] = value
                return value

        self.provider_stats: dict[str, LoadBalancerState] = AutoInitDict()
        self.lock = threading.RLock()

    def route_request(
        self,
        model_type: str,
        estimated_tokens: int,
        strategy: RoutingStrategy = RoutingStrategy.INTELLIGENT,
        constraints: Metadata | None = None,
    ) -> RoutingDecision:
        """
        توجيه الطلب إلى أنسب مزود خدمة.

        Args:
            model_type: نوع النموذج المطلوب.
            estimated_tokens: عدد الرموز المقدرة.
            strategy: استراتيجية التوجيه.
            constraints: قيود إضافية (التكلفة القصوى، الخ).
        """
        self._validate_routing_request(model_type, estimated_tokens)
        constraints = constraints or {}
        candidates = self._evaluate_candidates(model_type, estimated_tokens, constraints)

        if not candidates:
            raise ValueError("No suitable provider found for routing (or all circuits open)")

        best_candidate = self._apply_strategy_and_select_best(candidates, strategy)
        decision = self._create_routing_decision(best_candidate, strategy, len(candidates))
        self._record_decision(decision, model_type, estimated_tokens)

        return decision

    def _evaluate_candidates(
        self, model_type: str, estimated_tokens: int, constraints: Metadata
    ) -> list[ProviderCandidate]:
        """تقييم وترشيح المزودين المتاحين بناءً على القيود."""
        max_cost, max_latency = self._normalize_constraints(constraints)
        candidates: list[ProviderCandidate] = []

        for provider_name, adapter in self.provider_adapters.items():
            if self._is_provider_available(provider_name):
                candidate = self._evaluate_single_provider(
                    provider_name, adapter, model_type, estimated_tokens, max_cost, max_latency
                )
                if candidate:
                    candidates.append(candidate)

        return candidates

    def _is_provider_available(self, provider_name: str) -> bool:
        if self.circuit_breaker.is_open(provider_name):
            logger.warning(f"Skipping {provider_name} due to open circuit.")
            return False
        return True

    def _normalize_constraints(self, constraints: Metadata) -> tuple[float, float]:
        """
        تطبيع قيود التوجيه إلى حدود رقمية صريحة.

        يضمن هذا التابع أن قيم القيود قابلة للمقارنة،
        ويعيد افتراضات افتراضية عند غياب القيم.
        """

        def _coerce_constraint(value: object, default: float) -> float:
            if value is None:
                return default
            return float(value)

        try:
            max_cost = _coerce_constraint(constraints.get("max_cost", float("inf")), float("inf"))
            max_latency = _coerce_constraint(
                constraints.get("max_latency", float("inf")),
                float("inf"),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Routing constraints must be numeric values.") from exc
        if math.isnan(max_cost) or math.isnan(max_latency):
            raise ValueError("Routing constraints must be valid numeric values.")
        if max_cost < 0 or max_latency < 0:
            raise ValueError("Routing constraints must be non-negative values.")
        return max_cost, max_latency

    def _validate_routing_request(self, model_type: str, estimated_tokens: int) -> None:
        """
        التحقق من سلامة مدخلات طلب التوجيه.

        يفرض هذا التابع الحد الأدنى من الصحة لضمان وضوح القرار وسلامة الحسابات.
        """
        if not model_type or not model_type.strip():
            raise ValueError("Model type is required for routing.")
        if estimated_tokens <= 0:
            raise ValueError("Estimated tokens must be a positive integer.")

    def _evaluate_single_provider(
        self,
        provider_name: str,
        adapter: ModelProviderAdapter,
        model_type: str,
        tokens: int,
        max_cost: float,
        max_latency: float,
    ) -> ProviderCandidate | None:
        """تقييم مزود واحد وإرجاع مرشح صالح إن كان ضمن القيود."""
        try:
            cost = adapter.estimate_cost(model_type, tokens)
            latency = adapter.estimate_latency(model_type, tokens)

            if cost > max_cost or latency > max_latency:
                return None

            with self.lock:
                stats = self.provider_stats[provider_name]

            health_score = self._derive_health_score(stats)
            return self._build_candidate(provider_name, cost, latency, health_score)
        except Exception as e:
            logger.warning(f"Error evaluating provider {provider_name}: {e}")
            return None

    def _apply_strategy_and_select_best(
        self, candidates: list[ProviderCandidate], strategy: RoutingStrategy
    ) -> ProviderCandidate:
        """تطبيق استراتيجية التوجيه واختيار الأفضل."""
        strategy_impl = get_strategy(strategy)
        strategy_impl.calculate_scores(candidates)

        # اختيار المرشح الأعلى درجة
        return max(candidates, key=lambda x: x["score"])

    def _derive_health_score(self, stats: LoadBalancerState) -> float:
        """تحويل حالة المزود إلى درجة صحية رقمية قابلة للدمج."""
        return 1.0 if stats.is_healthy else 0.0

    def _build_candidate(
        self, provider_name: str, cost: float, latency: float, health_score: float
    ) -> ProviderCandidate:
        """
        بناء مرشح التوجيه بشكل موحد ومقروء.

        يتم ضبط الدرجة الابتدائية إلى صفر تمهيداً لحسابها بالاستراتيجية المختارة.
        """
        return {
            "provider": provider_name,
            "cost": cost,
            "latency": latency,
            "health_score": health_score,
            "score": 0.0,
        }

    def _create_routing_decision(
        self,
        best_candidate: ProviderCandidate,
        strategy: RoutingStrategy,
        candidate_count: int,
    ) -> RoutingDecision:
        """إنشاء كائن قرار التوجيه النهائي."""
        return RoutingDecision(
            service_id=str(best_candidate["provider"]),
            base_url=f"https://api.{best_candidate['provider']}.com",
            protocol=ProtocolType.REST,
            estimated_latency_ms=float(best_candidate["latency"]),
            estimated_cost=float(best_candidate["cost"]),
            confidence_score=float(best_candidate["score"]),
            reasoning=f"Selected {best_candidate['provider']} based on {strategy.value} strategy",
            metadata={"all_candidates": candidate_count},
        )

    def _record_decision(
        self,
        decision: RoutingDecision,
        model_type: str,
        estimated_tokens: int,
    ) -> None:
        """تسجيل القرار في الأرشيف."""
        with self.lock:
            entry: RoutingHistoryEntry = {
                "timestamp": datetime.now(UTC),
                "decision": decision,
                "model_type": model_type,
                "tokens": estimated_tokens,
            }
            self.routing_history.append(entry)

    def update_provider_stats(self, provider: str, success: bool, latency_ms: float) -> None:
        """تحديث إحصائيات المزود بعد تنفيذ الطلب."""
        if success:
            self.circuit_breaker.report_success(provider)
        else:
            self.circuit_breaker.report_failure(provider)

        with self.lock:
            stats = self.provider_stats[provider]
            self._update_load_balancer_stats(stats, success, latency_ms)

    def _update_load_balancer_stats(
        self, stats: LoadBalancerState, success: bool, latency_ms: float
    ) -> None:
        stats.total_requests += 1
        if not success:
            stats.total_errors += 1

        stats.avg_latency_ms = (
            stats.avg_latency_ms * (stats.total_requests - 1) + latency_ms
        ) / stats.total_requests

        error_rate = stats.total_errors / stats.total_requests if stats.total_requests > 0 else 0
        stats.is_healthy = error_rate < 0.1
