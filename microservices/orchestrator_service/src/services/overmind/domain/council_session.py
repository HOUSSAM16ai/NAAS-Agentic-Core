"""
جلسة مجلس الحكمة (Council Session).
-----------------------------------
توفر طبقة تنسيق خفيفة بين مجلس الوكلاء وذاكرة التعاون،
وتضمن تسجيل المساهمات بشكل موحد مع تلخيص آمن للبيانات.

المعايير:
- CS50 2025 Strict Mode.
- توثيق "Legendary" باللغة العربية.
- فصل واضح بين التنسيق والعمليات التنفيذية.
"""

from __future__ import annotations

import time

from app.core.protocols import CollaborationContext
from microservices.orchestrator_service.src.services.overmind.collaboration import CollaborationHub


class CouncilSession:
    """
    جلسة تشغيل لمجلس الوكلاء.

    توفر هذه الجلسة واجهة موحدة لتسجيل المساهمات، وإرسال الإشعارات،
    وتلخيص المعطيات الحساسة قبل تخزينها في الذاكرة المشتركة.
    """

    def __init__(
        self,
        *,
        hub: CollaborationHub | None,
        context: CollaborationContext,
    ) -> None:
        """
        تهيئة جلسة مجلس الوكلاء.

        Args:
            hub: مركز التعاون (اختياري).
            context: سياق التعاون المشترك.
        """
        self.hub = hub
        self.context = context
        self._contribution_counter = 0

    def record_action(
        self,
        *,
        agent_name: str,
        action: str,
        input_data: object,
        output_data: object,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        """
        تسجيل مساهمة وكيل ضمن الجلسة.

        Args:
            agent_name: اسم الوكيل.
            action: اسم الإجراء.
            input_data: البيانات الداخلة.
            output_data: البيانات الخارجة.
            success: حالة النجاح.
            error_message: رسالة الخطأ عند الفشل.
        """
        self._contribution_counter += 1
        payload = {
            "agent": agent_name,
            "action": action,
            "success": success,
            "error_message": error_message,
            "input_summary": self._summarize_payload(input_data),
            "output_summary": self._summarize_payload(output_data),
            "sequence": self._contribution_counter,
            "timestamp": time.time(),
        }

        self.context.update("last_agent_action", payload)
        self.context.update(f"agent_last_action::{agent_name}", payload)

        if self.hub:
            self.hub.record_contribution(
                agent_name=agent_name,
                action=action,
                input_data=payload["input_summary"],
                output_data=payload["output_summary"],
                success=success,
                error_message=error_message,
            )

    def notify_agent(self, target_agent: str, message: dict[str, object]) -> None:
        """
        إرسال إشعار لوكيل محدد عبر مركز التعاون.

        Args:
            target_agent: اسم الوكيل المستهدف.
            message: رسالة الإشعار.
        """
        if not self.hub:
            return
        self.hub.notify_agent(target_agent, message)

    def snapshot(self) -> dict[str, object]:
        """
        إرجاع ملخص سريع لحالة الجلسة.

        Returns:
            dict: ملخص الجلسة.
        """
        return {
            "contributions_recorded": self._contribution_counter,
            "shared_memory_keys": list(self.context.shared_memory.keys()),
        }

    def _summarize_payload(self, payload: object) -> dict[str, object]:
        """
        تلخيص البيانات لتجنب التخزين المفرط.

        Args:
            payload: البيانات الأصلية.

        Returns:
            dict: ملخص مبسط.
        """
        if isinstance(payload, dict):
            return {"type": "dict", "keys": list(payload.keys()), "size": len(payload)}
        if isinstance(payload, list):
            return {"type": "list", "length": len(payload)}
        if isinstance(payload, tuple):
            return {"type": "tuple", "length": len(payload)}
        return {"type": type(payload).__name__, "value_preview": str(payload)[:120]}
