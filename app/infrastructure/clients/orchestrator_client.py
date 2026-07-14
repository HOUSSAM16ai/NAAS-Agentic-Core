"""
Orchestrator Client.
Provides a typed interface to the Orchestrator Service.
Decouples the Monolith from the Overmind Orchestration Logic.
"""

from __future__ import annotations

import logging
import time

import httpx
import jwt as pyjwt
from pydantic import BaseModel

from app.core.http_client_factory import HTTPClientConfig, get_http_client
from app.core.settings.base import get_settings
from app.infrastructure.clients.orchestrator.chat_turn import ChatTurnMixin
from app.infrastructure.clients.orchestrator.local_fallback import LocalFallbackMixin
from app.infrastructure.clients.orchestrator.probability_ui import ProbabilityUIMixin
from app.infrastructure.clients.orchestrator.socratic_evaluation import SocraticEvaluationMixin
from app.infrastructure.clients.orchestrator.stream_normalization import StreamNormalizationMixin
from app.infrastructure.clients.orchestrator.text_streaming import TextStreamingMixin
from app.services.capabilities.exercise_retrieval import (
    ExerciseRetrievalDecision,
    ExerciseRetrievalRequest,
    detect_exercise_retrieval,
    detect_explanation_with_context,
)
from app.services.capabilities.file_intelligence import (
    FileIntelligenceRequest,
    detect_file_intelligence,
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
        decision = detect_file_intelligence(FileIntelligenceRequest(question=question))
        return decision.recognized, decision.extension

    def _exercise_retrieval_decision(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None = None,
    ) -> bool:
        """يستدعي قدرة استرجاع التمارين الرسمية لتوحيد eligibility."""
        decision = detect_exercise_retrieval(
            ExerciseRetrievalRequest(question=question),
            history_messages=history_messages,
        )
        return decision.recognized

    def _exercise_retrieval_full_decision(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None = None,
    ) -> ExerciseRetrievalDecision:
        """نسخة كاملة من القرار تُرجِع matched_entry لاستخدامه في الاسترجاع المُفهرَس.

        ISS-051: قبل هذا الإصلاح كنا نرمي matched_entry ونستدعي wide-net search
        الذي يقرأ كل ملفات knowledge_base/ فيُعيد أكثر من تمرين دفعة واحدة.
        """
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

        التوسّع لمليارات التمارين: عند نية استرجاع مؤكدة بلا تطابق في الفهرس المنسَّق
        (تمرين غير مُدرَج محلياً) لكن مع إشارة بنيوية كافية (سنة/رقم/موضوع مرجعي)،
        نُفعِّل preempt الاسترجاع ليجرّب Supabase. آمن: إن لم يُنتج المسار محتوى →
        البث الفارغ يسقط للمسار العادي (راجع chat_with_agent).
        """
        decision = detect_exercise_retrieval(
            ExerciseRetrievalRequest(question=question),
            history_messages=history_messages,
        )
        if not decision.recognized:
            return False
        if decision.matched_entry is not None:
            return True
        # المسار القابل للتوسّع: نية استرجاع + إشارة بنيوية → نجرّب Supabase
        try:
            from app.services.capabilities.bac_db_retriever import extract_db_facets

            return extract_db_facets(question).is_anchored
        except Exception:
            return False

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
        decision = detect_explanation_with_context(
            ExerciseRetrievalRequest(question=question),
            history_messages=history_messages,
        )
        return decision.recognized and decision.matched_entry is not None

    def _build_service_jwt(self, user_id: int) -> str:
        """يُولِّد JWT داخلي قصير العمر لمصادقة الـ monolith مع orchestrator-service.

        يستخدم نفس SECRET_KEY المشترك بين الـ monolith والـ orchestrator.
        صالح لمدة 5 دقائق فقط — يُجدَّد مع كل طلب.
        """
        settings = get_settings()
        now = int(time.time())
        payload = {
            "sub": str(user_id),
            "user_id": user_id,
            "iat": now,
            "exp": now + 300,  # 5 دقائق
            "iss": "cogniforge-monolith",
        }
        return pyjwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

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
        url = f"{self.base_url}/missions"
        payload = {
            "objective": objective,
            "context": context or {},
            "priority": priority,
        }
        headers = {}
        if idempotency_key:
            headers["X-Correlation-ID"] = idempotency_key

        client = await self._get_client()
        try:
            logger.info(f"Dispatching mission to Orchestrator: {objective[:50]}...")
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return MissionResponse(**data)
        except Exception as e:
            logger.error(f"Failed to create mission: {e}", exc_info=True)
            raise

    async def get_mission(self, mission_id: int) -> MissionResponse | None:
        """
        Get mission details.
        """
        url = f"{self.base_url}/missions/{mission_id}"
        client = await self._get_client()
        try:
            response = await client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return MissionResponse(**data)
        except Exception as e:
            logger.error(f"Failed to get mission {mission_id}: {e}")
            raise

    async def get_mission_events(self, mission_id: int) -> list[dict]:
        """
        Get mission events from the Orchestrator Service.
        """
        url = f"{self.base_url}/missions/{mission_id}/events"
        client = await self._get_client()
        try:
            response = await client.get(url)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get mission events {mission_id}: {e}")
            return []


# Singleton
orchestrator_client = OrchestratorClient()
