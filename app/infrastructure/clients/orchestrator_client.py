"""
Orchestrator Client.
Provides a typed interface to the Orchestrator Service.
Decouples the Monolith from the Overmind Orchestration Logic.

D-256 (CodeScene X-Ray — job 72): هذا الملف صار **قشرة استقبال وتفويض حرفية** —
كل ازدواج داخلي موثق (get_mission · get_mission_events · create_mission: نمط
`client + try/except + raise_for_status` المتكرر) وفصل payload الـ JWT انتقل إلى
حزمة `orchestrator_client_support/` (شريحة `missions.py` للقلب الموحد
`_request_mission` + `ServiceJwtPayload`، وشريحة `preempts.py` لقرار الاسترجاع
المفهرَس عالي التردد — نمط D-252/D-253/D-254/D-255). كل التوقيعات العامة
والخاصة (`self._x`) بقيت قشور تفويضٍ حرفية ليبقى كل اختبار وmonkeypatch فعالًا
(قانون late-binding من D-252) — **صفر تغيير سلوكي**.
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from app.core.http_client_factory import HTTPClientConfig, get_http_client
from app.core.settings.base import get_settings
from app.infrastructure.clients.orchestrator.chat_turn import ChatTurnMixin
from app.infrastructure.clients.orchestrator.local_fallback import LocalFallbackMixin
from app.infrastructure.clients.orchestrator.probability_ui import ProbabilityUIMixin
from app.infrastructure.clients.orchestrator.socratic_evaluation import SocraticEvaluationMixin
from app.infrastructure.clients.orchestrator.stream_normalization import StreamNormalizationMixin
from app.infrastructure.clients.orchestrator.text_streaming import TextStreamingMixin
from app.infrastructure.clients.orchestrator_client_support.missions import (
    ServiceJwtPayload,
    _MissionRequest,
    _request_mission,
)
from app.infrastructure.clients.orchestrator_client_support.preempts import (
    resolve_explanation_with_context,
    resolve_indexed_anchor,
)
from app.services.skills.probability_tutor_brain import ProbabilityTutorBrain

logger = logging.getLogger("orchestrator-client")


class MissionResponse(BaseModel):
    id: int
    objective: str
    status: str
    outcome: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    result: dict[str, object] | None = None
    steps: list[dict[str, object]] = []


class OrchestratorClient(
    ProbabilityTutorBrain,
    StreamNormalizationMixin,
    TextStreamingMixin,
    ProbabilityUIMixin,
    LocalFallbackMixin,
    SocraticEvaluationMixin,
    ChatTurnMixin,
):
    """Client for interacting with the Orchestrator Service.

    D-163: يرث «عقل الاحتمالات الحتمي» (`ProbabilityTutorBrain` — الوحدة المستخرَجة
    من هذا الملف حين كان God-file بـ 6,154 سطراً). كل `cls._x`/`self._x` التربوية
    تُحل عبر الـ MRO — سلوك runtime مطابق. **ممنوع** إعادة تعريف دوال العقل هنا.

    D-164: يرث كذلك mixins متماسكة استُخرجت من الـ God-file (`StreamNormalizationMixin` —
    توحيد أحداث التدفق + إطار الخطأ؛ `TextStreamingMixin` — typing-effect + تعقيم النص؛
    `ProbabilityUIMixin` — بُناة Generative-UI الاحتمالات الحتمية). `ProbabilityTutorBrain`
    يبقى **أول base** في الـ MRO؛ كل `self._x`/`cls._x` يُحل عبره — سلوك runtime مطابق.

    D-256: لا يُضاف هنا منطقٌ جديد — أي سلوكٍ جديد يخصّ الطلبات أو القرارات يذهب إلى
    حزمة `orchestrator_client_support/` (القلب النقي) وتبقى هذه الطبقة قشرةً فقط.
    """

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        # Ensure we strictly use the configuration from settings to avoid routing to 'localhost'
        # within isolated Docker containers and ensure robust Microservices service discovery.
        env_url = getattr(settings, "ORCHESTRATOR_SERVICE_URL", None)
        resolved_url = base_url or env_url
        if not resolved_url:
            raise RuntimeError("ORCHESTRATOR_SERVICE_URL must be configured")

        self.base_url = resolved_url.rstrip("/")
        self.config = HTTPClientConfig(
            name="orchestrator-client",
            timeout=60.0,
            max_connections=50,
        )

    def _file_intelligence_decision(self, question: str) -> tuple[bool, str | None]:
        """يستدعي قدرة ذكاء الملفات الرسمية لإنتاج قرار موحد."""
        # D-256: لا شريحة لها — سلوكُها سطرٌ واحدٌ لا ازدواج ولا تعقيد.
        from app.services.capabilities.file_intelligence import (
            FileIntelligenceRequest,
            detect_file_intelligence,
        )

        decision = detect_file_intelligence(FileIntelligenceRequest(question=question))
        return decision.recognized, decision.extension

    def _exercise_retrieval_decision(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None = None,
    ) -> bool:
        """يستدعي قدرة استرجاع التمارين الرسمية لتوحيد eligibility."""
        # D-256: قشرة تفويض حرفية — القلب في `exercise_retrieval` (وحدة رسمية).
        from app.services.capabilities.exercise_retrieval import (
            ExerciseRetrievalRequest,
            detect_exercise_retrieval,
        )

        decision = detect_exercise_retrieval(
            ExerciseRetrievalRequest(question=question),
            history_messages=history_messages,
        )
        return decision.recognized

    def _exercise_retrieval_full_decision(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None = None,
    ):
        """نسخة كاملة من القرار تُرجِع matched_entry لاستخدامه في الاسترجاع المُفهرَس.

        ISS-051: قبل هذا الإصلاح كنا نرمي matched_entry ونستدعي wide-net search
        الذي يقرأ كل ملفات knowledge_base/ فيُعيد أكثر من تمرين دفعة واحدة.
        """
        from app.services.capabilities.exercise_retrieval import (
            ExerciseRetrievalRequest,
            detect_exercise_retrieval,
        )

        return detect_exercise_retrieval(
            ExerciseRetrievalRequest(question=question),
            history_messages=history_messages,
        )

    def _has_indexed_match(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None = None,
    ) -> bool:
        """يكشف عن طلب استرجاع تمرين بكالوريا مع تطابق مُفهرَس مؤكد.

        ISS-056 (D-049 — Indexed Retrieval Preemption Doctrine):
        عندما يطابق سؤال الطالب ملفاً محدداً في knowledge_index، نتجاوز
        orchestrator-service و StateGraph وكل سلسلة fallback، ونعرض الملف
        النظيف مباشرة. يضمن:
          1. لا تسرَّب JSON envelope من SynthesizerNode
          2. لا هلوسة من LLM
          3. سرعة قصوى (لا HTTP roundtrip، لا LLM call)
          4. محتوى محدد رسمياً (الملف في knowledge_base/)

        ISS-CONV-C: يقبل history_messages لحل أسئلة المتابعة بالسياق.

        D-256 (CodeScene job 72): كانت هذه أعلى دالة ترددًا في هذا الملف
        (churn=2 · 38 سطراً) وتحمل embedded import مع try/except واسع —
        فكِّك قرارها إلى `resolve_indexed_anchor` النقية في شريحة preempts.
        """
        anchor = resolve_indexed_anchor(question, history_messages)
        # القرار مطابق للحرف سابقًا: recognized + (matched أو db_anchored).
        return anchor.recognized and (anchor.matched_entry is not None or anchor.db_anchored)

    def _has_explanation_with_context_match(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None,
    ) -> bool:
        """يكشف عن طلب شرح مرتبط بسياق تمرين بكالوريا (إما في السؤال أو في تاريخ المحادثة).

        ISS-058 (D-052 — Explanation Context Preemption Doctrine):
        عند طلبات شرح/استفسار مفاهيمي («ماذا نقصد بدالة أصلية»، «كيف نُثبت..»،
        «لماذا..») مرتبطة بتمرين بكالوريا (إما صريحاً في السؤال أو ضمنياً في
        المحادثة الجارية)، نتجاوز orchestrator-service بالكامل لمنع:
          1. dump عدة تمارين غير متعلقة (2016 + 2024 معاً — كارثة الشاشة الأخيرة)
          2. تسريب tags مثل [ex: ex_1] / [sol: ex_1] من vector DB
          3. هلوسة LLM بسبب context واسع وغير متعلق

        نحدد التمرين الصحيح من السياق ونمرره كـ context صريح للـ LLM.
        """
        return resolve_explanation_with_context(question, history_messages)

    def _build_service_jwt(self, user_id: int, *, is_admin: bool = False) -> str:
        """يولِّد JWT داخلي قصير العمر لمصادقة الـ monolith مع orchestrator-service.

        يستخدم نفس SECRET_KEY المشترك بين الـ monolith والـ orchestrator.
        صالح لمدة 5 دقائق فقط — يُجدَّد مع كل طلب.

        ISS-131 (D-169 — نفس درس D-162/§6.78): دور الإدمن يجب أن يُحمَل في الـ JWT
        صراحةً — `_is_admin_payload` في الـ orchestrator fail-closed (يفحص
        `role`/`is_admin`/`scope`)، وبدون الـ claim كانت أداة الإدمن تُنفَّذ ثم
        تُرفض بـ `ADMIN_ACCESS_DENIED` في `ValidateAccessNode` (سيناريو «كم عدد
        ملفات بايثون» الحي). القناة الإدارية للمونوليث موثوقة (actor.is_admin
        مُتحقَّق عند اتصال WS — D-WS-CONN-002) فالـ claim نقلٌ للحقيقة لا تصعيد.
        """
        settings = get_settings()
        return ServiceJwtPayload(user_id=user_id, is_admin=is_admin).encode(
            settings.SECRET_KEY,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        return get_http_client(self.config)

    async def create_mission(
        self,
        objective: str,
        context: dict[str, object] | None = None,
        priority: int = 1,
        idempotency_key: str | None = None,
    ) -> MissionResponse:
        """
        Create and start a mission via the Orchestrator Service.
        """
        payload = {
            "objective": objective,
            "context": context or {},
            "priority": priority,
        }
        headers = {}
        if idempotency_key:
            headers["X-Correlation-ID"] = idempotency_key

        try:
            logger.info(f"Dispatching mission to Orchestrator: {objective[:50]}...")
            data = await _request_mission(
                self._get_client,
                _MissionRequest(
                    base_url=self.base_url,
                    method="POST",
                    path="/missions",
                    json_body=payload,
                    headers=headers,
                    on_404=None,
                    empty_value=None,
                    log_prefix="Dispatching mission to Orchestrator",
                    log_detail=f"{objective[:50]}...",
                ),
            )
        except Exception as e:
            logger.error(f"Failed to create mission: {e}", exc_info=True)
            raise
        return MissionResponse(**data)

    async def get_mission(self, mission_id: int) -> MissionResponse | None:
        """
        Get mission details.
        """
        # D-256: القلب الموحد `_request_mission` يقتل ازدواج get_mission/get_mission_events.
        data = await _request_mission(
            self._get_client,
            _MissionRequest(
                base_url=self.base_url,
                method="GET",
                path=f"/missions/{mission_id}",
                on_404="empty",
                empty_value=None,
                log_prefix="Fetching mission",
                log_detail=str(mission_id),
            ),
        )
        return MissionResponse(**data) if data is not None else None

    async def get_mission_events(self, mission_id: int) -> list[dict]:
        """
        Get mission events from the Orchestrator Service.
        """
        # D-256: نفس القلب الموحد — السلوك 404⇒[] والخطأ⇒[] مطابق للحرف.
        try:
            data = await _request_mission(
                self._get_client,
                _MissionRequest(
                    base_url=self.base_url,
                    method="GET",
                    path=f"/missions/{mission_id}/events",
                    on_404="empty",
                    empty_value=[],
                    log_prefix="Fetching mission events",
                    log_detail=str(mission_id),
                ),
            )
            return list(data) if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Failed to get mission events {mission_id}: {e}")
            return []


# Singleton
orchestrator_client = OrchestratorClient()
