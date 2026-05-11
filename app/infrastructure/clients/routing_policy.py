"""سياسات التوجيه والـ fallback لعميل orchestrator بشكل مركزي وقابل للاختبار.

الخطوة الانتقالية الثانية (2026-05-10 — feat/microservices-step2-stategraph-routing):
  - ORCHESTRATOR_CHAT_ENDPOINT يتحكم في نقطة النهاية المستهدفة:
      "state_graph"  → /api/chat/messages  (StateGraph 13 عقدة — الهدف الانتقالي)
      "agent"        → /agent/chat         (OrchestratorAgent — السلوك القديم)
  - القيمة الافتراضية: "state_graph" — الانتقال مفعّل بشكل صريح.
  - يمكن التراجع فوراً بضبط ORCHESTRATOR_CHAT_ENDPOINT=agent في البيئة.
  - راجع D-021 في .memory/decisions.md للسياق الكامل.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

_logger = logging.getLogger("routing-policy")

# نقاط النهاية المدعومة — لا تُضف قيماً هنا بدون ADR.
_ENDPOINT_MAP: dict[str, str] = {
    "state_graph": "/api/chat/messages",  # StateGraph 13 عقدة (D-021 — الهدف الانتقالي)
    "agent": "/agent/chat",  # OrchestratorAgent (السلوك القديم — للتراجع فقط)
}

_DEFAULT_ENDPOINT_MODE = "state_graph"


@dataclass(frozen=True, slots=True)
class ChatRoutingPolicy:
    """يمثل سياسة توجيه موحدة لمسار chat مع كسر زجاجي صريح.

    الحقول:
        candidate_bases: قائمة عناوين orchestrator المرشحة (مرتبة بالأولوية).
        fallback_enabled: هل يُسمح بالـ fallback المحلي عند فشل جميع المرشحين.
        breakglass_multi_target: وضع الطوارئ — يُفعّل عناوين احتياطية متعددة.
        contract_version: إصدار عقد الـ API المستخدم في الطلبات.
        endpoint_mode: نمط نقطة النهاية ("state_graph" | "agent").
    """

    candidate_bases: list[str]
    fallback_enabled: bool
    breakglass_multi_target: bool
    contract_version: str
    endpoint_mode: str

    @classmethod
    def from_environment(cls, canonical_base_url: str) -> ChatRoutingPolicy:
        """يبني السياسة من المتغيرات البيئية مع افتراض canonical صارم افتراضيًا.

        المتغيرات البيئية المؤثرة:
            ORCHESTRATOR_CHAT_ENDPOINT: "state_graph" (افتراضي) | "agent"
            ORCHESTRATOR_ALLOW_MULTI_TARGET_CHAT: "1" لتفعيل وضع الطوارئ
            ORCHESTRATOR_SERVICE_FALLBACK_URLS: عناوين احتياطية مفصولة بفاصلة
            ORCHESTRATOR_LOCAL_FALLBACK_ENABLED: "0" لتعطيل الـ fallback المحلي
            CHAT_CONTRACT_VERSION: إصدار العقد (افتراضي: "v1")
        """
        breakglass_multi_target = os.getenv("ORCHESTRATOR_ALLOW_MULTI_TARGET_CHAT", "0") == "1"
        bases: list[str] = [canonical_base_url.rstrip("/")]

        if breakglass_multi_target:
            fallback_urls_raw = os.getenv("ORCHESTRATOR_SERVICE_FALLBACK_URLS", "")
            fallback_bases = [
                url.strip().rstrip("/") for url in fallback_urls_raw.split(",") if url.strip()
            ]
            bases.extend(fallback_bases)

        deduped: list[str] = []
        for base in bases:
            if base and base not in deduped:
                deduped.append(base)

        raw_mode = os.getenv("ORCHESTRATOR_CHAT_ENDPOINT", _DEFAULT_ENDPOINT_MODE).strip().lower()
        # تحقق صارم — أي قيمة غير معروفة تُعيد إلى الوضع الافتراضي مع تحذير.
        if raw_mode not in _ENDPOINT_MAP:
            _logger.warning(
                "ORCHESTRATOR_CHAT_ENDPOINT=%r is not a known mode; "
                "falling back to %r. Valid values: %s",
                raw_mode,
                _DEFAULT_ENDPOINT_MODE,
                list(_ENDPOINT_MAP),
            )
            raw_mode = _DEFAULT_ENDPOINT_MODE

        return cls(
            candidate_bases=deduped,
            fallback_enabled=os.getenv("ORCHESTRATOR_LOCAL_FALLBACK_ENABLED", "1") != "0",
            breakglass_multi_target=breakglass_multi_target,
            contract_version=os.getenv("CHAT_CONTRACT_VERSION", "v1"),
            endpoint_mode=raw_mode,
        )

    def candidate_urls(self) -> list[str]:
        """يعيد عناوين chat المرشحة وفق السياسة الموحّدة.

        الوضع الافتراضي (state_graph): يوجّه نحو /api/chat/messages
        وضع التراجع (agent): يوجّه نحو /agent/chat
        """
        path = _ENDPOINT_MAP[self.endpoint_mode]
        return [f"{base}{path}" for base in self.candidate_bases]

    @property
    def targets_state_graph(self) -> bool:
        """صحيح عندما تكون السياسة موجّهة نحو StateGraph الحقيقي."""
        return self.endpoint_mode == "state_graph"
