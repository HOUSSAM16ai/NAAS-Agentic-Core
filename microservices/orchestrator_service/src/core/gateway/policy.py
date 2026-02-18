import logging
import threading
from datetime import UTC, datetime

from .models import PolicyRule

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    محرك تنفيذ السياسات - Policy enforcement engine

    Features:
    - Rule-based policy enforcement
    - Dynamic policy updates
    - Policy violation tracking
    - Compliance reporting
    """

    def __init__(self):
        self.policies: dict[str, PolicyRule] = {}
        self.violations: list[dict[str, object]] = []
        self.lock = threading.RLock()

    def add_policy(self, policy: PolicyRule) -> None:
        """Add or update policy"""
        with self.lock:
            self.policies[policy.rule_id] = policy

    def evaluate(self, request_context: dict[str, object]) -> tuple[bool, str | None]:
        """
        Evaluate policies against request

        Returns:
            (allowed, reason) tuple
        """
        with self.lock:
            # Sort by priority
            sorted_policies = sorted(self.policies.values(), key=lambda p: p.priority, reverse=True)

            for policy in sorted_policies:
                if not policy.enabled:
                    continue

                # Simple condition evaluation (in production, use a proper expression engine)
                try:
                    # For demo, support simple conditions
                    if policy.action == "deny" and self._evaluate_condition(
                        policy.condition, request_context
                    ):
                        self._record_violation(policy, request_context)
                        return False, f"Policy violation: {policy.name}"

                except Exception as e:
                    logger.error(f"Policy evaluation error: {e}")
                    continue

            return True, None

    def _evaluate_condition(self, condition: str, context: dict[str, object]) -> bool:
        """Evaluate policy condition (simplified)"""
        # In production, use a proper expression engine
        # For now, support basic checks

        # Check for the default authentication policy
        if "not authenticated" in condition:
            return not context.get("authenticated", False)

        # Check if user_id is required but missing/None in context
        if (
            "user_id" in condition
            and ("required" in condition or "require" in condition)
            and "not required" not in condition
            and "optional" not in condition
        ):
            return not context.get("user_id")

        return False

    def _record_violation(self, policy: PolicyRule, context: dict[str, object]):
        """Record policy violation"""
        self.violations.append(
            {
                "timestamp": datetime.now(UTC),
                "policy_id": policy.rule_id,
                "policy_name": policy.name,
                "context": context,
            }
        )

    def get_violations(self, limit: int = 100) -> list[dict[str, object]]:
        """Get recent policy violations"""
        with self.lock:
            return self.violations[-limit:]
