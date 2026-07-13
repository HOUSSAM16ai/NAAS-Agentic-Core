"""
Orchestrator Client.
Provides a typed interface to the Orchestrator Service.
Decouples the Monolith from the Overmind Orchestration Logic.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncGenerator

import httpx
import jwt as pyjwt
from pydantic import BaseModel
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.ai_gateway import get_ai_client
from app.core.http_client_factory import HTTPClientConfig, get_http_client
from app.core.settings.base import get_settings
from app.infrastructure.clients.orchestrator.probability_ui import ProbabilityUIMixin
from app.infrastructure.clients.orchestrator.stream_normalization import StreamNormalizationMixin
from app.infrastructure.clients.orchestrator.text_streaming import TextStreamingMixin
from app.infrastructure.clients.routing_policy import ChatRoutingPolicy
from app.services.capabilities.exercise_retrieval import (
    ExerciseEntry,
    ExerciseRetrievalDecision,
    ExerciseRetrievalRequest,
    detect_exercise_retrieval,
    detect_explanation_with_context,
    format_exercise_for_display,
    load_exercise_content,
)
from app.services.capabilities.exercise_retrieval import (
    make_result as make_exercise_result,
)
from app.services.capabilities.file_intelligence import (
    FileIntelligenceRequest,
    build_file_count_command,
    default_project_root,
    detect_file_intelligence,
)
from app.services.capabilities.file_intelligence import (
    make_result as make_file_result,
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
    ProbabilityTutorBrain, StreamNormalizationMixin, TextStreamingMixin, ProbabilityUIMixin
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

    async def _execute_shell_tool(
        self,
        command: str,
        cwd: str,
        timeout: int = 30,
    ) -> dict[str, object]:
        """ينفذ أداة shell عبر طبقة الأدوات لضمان حساب حقيقي قائم على التنفيذ الفعلي."""
        from app.services.agent_tools.shell_tool import execute_shell

        return await execute_shell(command=command, cwd=cwd, timeout=timeout)

    async def _count_files_in_project(self, extension: str | None = None) -> int | None:
        """يحسب عدد الملفات فعلياً عبر shell ويعيد None عند فشل التنفيذ أو التحليل."""
        project_root = default_project_root()
        command = build_file_count_command(extension=extension)
        shell_result = await self._execute_shell_tool(command=command, cwd=project_root, timeout=45)

        if not shell_result.get("success"):
            logger.warning("Local shell file-count command failed", extra={"result": shell_result})
            return None

        stdout_value = str(shell_result.get("stdout", "")).strip()
        if not stdout_value:
            return None

        first_line = stdout_value.splitlines()[0].strip()
        if not first_line.isdigit():
            logger.warning(
                "Shell output is not a numeric file count", extra={"stdout": stdout_value}
            )
            return None

        return int(first_line)

    async def _build_local_file_count_response(self, question: str) -> str | None:
        """ينشئ رداً محلياً بعد تنفيذ عدّ احترافي حقيقي عبر القدرة الرسمية لذكاء الملفات."""
        recognized, extension = self._file_intelligence_decision(question)
        if not recognized:
            return None

        files_count = await self._count_files_in_project(extension=extension)
        result = make_file_result(extension=extension, count=files_count)
        return result.message

    async def _build_local_retrieval_response(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None = None,
    ) -> str | None:
        """
        ينفذ استرجاعاً محلياً للمعرفة التعليمية عند تعطل service control plane.

        ISS-051 (D-048 — Indexed Knowledge Retrieval):
        المسار المُفضَّل: استخدام matched_entry من knowledge_index.py لجلب ملف
        واحد بالضبط وتنسيقه كبطاقة امتحان نظيفة (بدون YAML، بدون حل).

        المسار البديل: عند فشل المطابقة المُفهرَسة (entry غير موجود في الفهرس)،
        نلجأ إلى wide-net search كما في النسخة القديمة — لكنه نادر الآن
        لأن detect_exercise_retrieval يستخرج matched_entry بنفسه.

        ISS-CONV-C: يقبل history_messages لحل أسئلة المتابعة بالسياق.
        """
        decision = self._exercise_retrieval_full_decision(question, history_messages)
        if not decision.recognized:
            return None

        # المسار المُفضَّل — مطابقة مُفهرَسة دقيقة (الـ 3 المنسَّقة): عرض غني من markdown
        # (نص نظيف + بطاقة امتحان). الفهرس المنسَّق يعمل كـ cache سريع للتمارين الساخنة.
        if decision.matched_entry is not None:
            try:
                raw_content = load_exercise_content(decision.matched_entry)
                if raw_content:
                    return format_exercise_for_display(decision.matched_entry, raw_content)
            except Exception:
                logger.warning("indexed_retrieval_failed", exc_info=True)
            # الملف النصّي مفقود → نص قاعدة البيانات (Supabase = single source of truth)
            db_text = await self._fetch_indexed_entry_db_text(decision.matched_entry)
            if db_text:
                return db_text

        # المسار القابل للتوسّع (مليارات التمارين) — Supabase candidate-generation + rerank
        # يُفعَّل للتمارين غير المُدرَجة في الفهرس المنسَّق. آمن: None عند تعذّر الوصول.
        db_match_text = await self._search_supabase_exercise(question)
        if db_match_text:
            return db_match_text

        # المسار البديل الأخير — wide-net search (legacy)
        try:
            from app.services.chat.tools.retrieval.service import search_educational_content

            result = await search_educational_content(query=question)
            normalized = make_exercise_result(result)
            return normalized.message
        except Exception:
            logger.warning("local_retrieval_fallback_failed", exc_info=True)
            return None

    async def _fetch_indexed_entry_db_text(self, entry: ExerciseEntry) -> str | None:
        """يجلب نص تمرين مُفهرَس من Supabase بهويته (سنة + رقم + موضوع مرجعي).

        يُستخدم كـ single-source-of-truth عند غياب ملف markdown المحلي. None عند
        أي تعذّر وصول → يبقى المسار يعتمد على الفهرس النصّي.
        """
        try:
            from app.services.capabilities.bac_db_retriever import fetch_exercise_raw_text
            from app.services.capabilities.knowledge_index import entry_canonical_ids

            canonical_id = next(iter(entry_canonical_ids(entry)), None)
            raw = await fetch_exercise_raw_text(
                year=entry.year,
                exercise_number=entry.exercise_number,
                canonical_id=canonical_id,
            )
            return self._format_db_exercise_text(raw) if raw else None
        except Exception:
            logger.info("indexed_entry_db_text_failed", exc_info=True)
            return None

    async def _search_supabase_exercise(self, question: str) -> str | None:
        """استرجاع تمرين من Supabase (candidate-gen + rerank) للتمارين غير المُفهرَسة محلياً.

        المسار القابل للتوسّع لمليارات التمارين. None عند تعذّر الوصول/لا نتيجة →
        يتقدّم المسار للبديل (wide-net / المسار العادي).
        """
        try:
            from app.services.capabilities.bac_db_retriever import search_bac_exercises_db

            match = await search_bac_exercises_db(question)
            if match is not None and match.raw_text.strip():
                return self._format_db_exercise_text(match.raw_text)
        except Exception:
            logger.info("supabase_exercise_search_failed", exc_info=True)
        return None

    @staticmethod
    def _format_db_exercise_text(raw_text: str | None) -> str | None:
        """ينظّف نص تمرين قادم من Supabase للعرض (يقطع أي قسم حل تسرَّب، يحذف الفراغ)."""
        if not raw_text or not raw_text.strip():
            return None
        try:
            from app.services.capabilities.exercise_retrieval import _trim_at_solution

            cleaned = _trim_at_solution(raw_text)
        except Exception:
            cleaned = raw_text
        cleaned = (cleaned or "").strip()
        return cleaned or None

    async def _stream_exercise_explanation_response(
        self,
        question: str,
        conversation_id: int | None,
        history_messages: list[dict[str, str]] | None = None,
        precomputed_decision: object = None,  # ExplanationWithContextDecision أو None
    ) -> AsyncGenerator[str, None]:
        """
        يشرح تمرين بكالوريا محدد بالاعتماد على محتواه الكامل من قاعدة المعرفة.

        ISS-053: مسار جديد يحل هلوسة LangGraph عند طلبات "اشرح تمرين الدوال
        العددية 2016". بدلاً من إرسال السؤال بدون سياق، نجلب النص الكامل
        (نص التمرين + الإجابة النموذجية) ونمرره للـ LLM كـ context صريح.

        ISS-058: الآن يستخدم تاريخ المحادثة لربط أسئلة "ماذا نقصد" / "كيف نُثبت"
        بتمرين البكالوريا الذي طُلب حديثاً — فلا يذهب إلى wide-net retrieval.

        ISS-059 (D-053): الآن يقبل `precomputed_decision` لتجنب استدعاء
        `detect_explanation_with_context` مرة ثانية (الـ caller حسبها فعلاً).
        يوفِّر ~10-20ms من زمن TTFB ويتجنَّب file I/O مكرراً.

        يُدرَج في fallback chain بين exercise_retrieval و LangGraph:
          file_intelligence → exercise_retrieval → exercise_explanation → LangGraph → general_chat
        """
        # ISS-059: استخدم القرار المُحسَب مسبقاً إن وُجد (يوفِّر file I/O)
        if precomputed_decision is not None:
            decision = precomputed_decision
        else:
            decision = detect_explanation_with_context(
                ExerciseRetrievalRequest(question=question),
                history_messages=history_messages,
            )
        # D-113 (ISS-115 — وَهْم الإتقان): الشرح السقراطي يستقبل **أسئلة التمرين
        # فقط** (display_content)، لا الإجابة النموذجية (full_content). فلا يملك
        # الـ LLM ما يكشفه. full_content محجوز لوضع التحقق المنفصل حصراً.
        socratic_content = (getattr(decision, "display_content", None) or "").strip()
        if not decision.recognized or not socratic_content:
            return

        try:
            from app.telemetry.path_observer import mark_fallback_used

            mark_fallback_used("exercise_explanation_stream")
        except Exception:
            pass

        try:
            from app.services.chat.local_graph import run_local_graph_with_exercise_context

            async for chunk in run_local_graph_with_exercise_context(
                question=question,
                exercise_full_content=socratic_content,
                conversation_id=conversation_id,
                history_messages=history_messages,
            ):
                if chunk:
                    yield chunk
        except Exception:
            logger.warning("exercise_explanation_stream_failed", exc_info=True)
            return

    async def _stream_local_retrieval_response(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        نسخة انسيابية من ``_build_local_retrieval_response`` — تبث المحتوى
        المسترجَع كلمة بكلمة لإنشاء typing-effect بدل dump واحد كبير.

        D-048: المحتوى المُسترجَع ثابت (ليس LLM streaming حقيقي)، لكننا نُقسّمه
        إلى أسطر/فقرات صغيرة ونُغذّيها واحدة تلو الأخرى مع تأخيرات صغيرة
        ليظهر للطالب كأنه يُكتب فوراً أمام عينيه.

        إذا أصدر المولِّد صفر قطعة → fallback chain يتقدم للخطوة التالية.

        ISS-CONV-C: يقبل history_messages لحل أسئلة المتابعة بالسياق.
        """
        full_response = await self._build_local_retrieval_response(question, history_messages)
        if not full_response:
            return

        try:
            from app.telemetry.path_observer import mark_fallback_used

            mark_fallback_used("local_retrieval_stream")
        except Exception:
            pass

        async for chunk in self._stream_markdown_typing(full_response):
            yield chunk

    async def _stream_question_only_response(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """ISS-112: «أعطني السؤال رقم N فقط» — اقتطاع حتمي من النص الرسمي.

        الفضيحة المُشخَّصة حياً: طلب «السؤال رقم 2 فقط» كان يُرجع التمرين كاملاً
        أو حلاً مُهلوَساً من LLM. هذا المسار صفر-LLM: يكشف النية + يقتطع السؤال
        المرقَّم من display_content (بدون حل أصلاً) ويبثّه typing-effect.
        يُصدر صفر قطعة عند عدم التعرف → المسار يتابع طبيعياً.
        """
        try:
            from app.services.capabilities.exercise_retrieval import (
                detect_question_only_request,
            )

            decision = detect_question_only_request(
                ExerciseRetrievalRequest(question=question),
                history_messages=history_messages,
            )
        except Exception:
            logger.warning("question_only_detection_failed", exc_info=True)
            return
        if not decision.recognized or not decision.sliced_content:
            return

        logger.info(
            "question_only_preempt reason=%s n=%s file=%s",
            decision.reason,
            decision.question_number,
            getattr(decision.matched_entry, "file_path", None),
        )
        try:
            from app.telemetry.path_observer import mark_fallback_used

            mark_fallback_used("question_only_stream")
        except Exception:
            pass

        async for chunk in self._stream_markdown_typing(decision.sliced_content):
            yield chunk

    async def _build_local_graph_response(
        self,
        question: str,
        conversation_id: int | None,
        history_messages: list[dict[str, str]] | None = None,
    ) -> str | None:
        """
        يشغّل محرك LangGraph المحلي (local_graph.py) ويعيد الرد النهائي.
        يستخدم MemorySaver مع thread_id=conversation_id لاستمرارية السياق.
        يعود None عند أي فشل دون أن يُسقط الـ fallback chain.

        ملاحظة (D-047): هذه نسخة non-streaming — تُستخدم للاختبارات والمسارات
        التي لا تحتاج typing effect. للبث الانسيابي استخدم
        ``_stream_local_graph_response`` (المسار الافتراضي في ``chat_with_agent``).
        """
        try:
            from app.services.chat.local_graph import run_local_graph
            from app.telemetry.path_observer import mark_fallback_used

            mark_fallback_used("local_graph")
            return await run_local_graph(
                question=question,
                conversation_id=conversation_id,
                history_messages=history_messages,
            )
        except Exception:
            logger.warning("local_graph_response_failed", exc_info=True)
            return None

    async def _stream_local_graph_response(
        self,
        question: str,
        conversation_id: int | None,
        history_messages: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        نسخة انسيابية من ``_build_local_graph_response`` — تُصدِر قطع الرد كلمة بكلمة.

        D-047: يكسر "Streaming Event Bottleneck" — بدل buffer-and-wait لـ ainvoke،
        نُغذِّي قناة WS بـ assistant_delta متعدد فوراً من OpenRouter SSE.

        Yields:
            str: قطع المحتوى التتابعية (typically 1-20 chars each).

        إذا أصدر المولِّد صفر قطعة → fallback chain يتقدم للخطوة التالية.
        """
        try:
            from app.services.chat.local_graph import run_local_graph_stream
            from app.telemetry.path_observer import mark_fallback_used

            mark_fallback_used("local_graph_stream")
            async for chunk in run_local_graph_stream(
                question=question,
                conversation_id=conversation_id,
                history_messages=history_messages,
            ):
                if chunk:
                    yield chunk
        except Exception:
            logger.warning("local_graph_stream_failed", exc_info=True)
            return

    async def _build_local_general_chat_response(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None = None,
    ) -> str | None:
        """
        يولد إجابة محلية عامة عبر بوابة الذكاء عند تعطل orchestrator.

        هذا المسار يُستخدم فقط كملاذ أخير بعد فشل مسارات fallback المتخصصة
        (عدّ الملفات والاسترجاع التعليمي)، بهدف إبقاء الدردشة الأساسية متاحة
        في بيئات التطوير مثل Codespaces.
        يحتفظ الآن بسياق المحادثة الكامل لمنع ظاهرة عمى السياق (Context Blindness).
        """
        sanitized_question = question.replace("\x00", "").strip()
        if not sanitized_question:
            return None

        try:
            from app.telemetry.path_observer import mark_fallback_used

            mark_fallback_used("local_general_chat")
        except Exception:  # pragma: no cover — observability never blocks chat
            pass

        local_system_prompt = (
            "أنت مساعد ذكي واسع المعرفة. "
            "أجب بدقة مباشرة على سؤال المستخدم مع الاستناد إلى سياق المحادثة السابقة "
            "عند وجود ضمائر أو إشارات مرجعية. لا تشر إلى تفاصيل داخلية."
        )
        ai_client = get_ai_client()
        try:
            if history_messages:
                history_text = self._format_history_for_prompt(history_messages)
                if history_text:
                    user_message = f"سياق المحادثة السابقة:\n{history_text}\n\nالسؤال الحالي: {sanitized_question}"
                else:
                    user_message = sanitized_question
            else:
                user_message = sanitized_question

            response_text = await ai_client.send_message(local_system_prompt, user_message)
        except Exception:
            logger.warning("local_general_chat_fallback_failed", exc_info=True)
            return None

        clean_response = response_text.replace("\x00", "").strip()
        if not clean_response:
            return None
        return clean_response

    async def _stream_local_general_chat_response(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        نسخة انسيابية من ``_build_local_general_chat_response`` — تبث المحتوى
        كلمة بكلمة عبر OpenRouter SSE بدل تجميعه ثم إرساله دفعة واحدة.

        D-047: المسار الأخير في fallback chain — لا يجوز أن يكسر typing effect.
        """
        sanitized_question = question.replace("\x00", "").strip()
        if not sanitized_question:
            return

        try:
            from app.telemetry.path_observer import mark_fallback_used

            mark_fallback_used("local_general_chat_stream")
        except Exception:
            pass

        local_system_prompt = (
            "أنت مساعد ذكي واسع المعرفة. "
            "أجب بدقة مباشرة على سؤال المستخدم مع الاستناد إلى سياق المحادثة السابقة "
            "عند وجود ضمائر أو إشارات مرجعية. لا تشر إلى تفاصيل داخلية."
        )
        ai_client = get_ai_client()

        if history_messages:
            history_text = self._format_history_for_prompt(history_messages)
            user_message = (
                f"سياق المحادثة السابقة:\n{history_text}\n\nالسؤال الحالي: {sanitized_question}"
                if history_text
                else sanitized_question
            )
        else:
            user_message = sanitized_question

        messages: list[dict[str, str]] = [
            {"role": "system", "content": local_system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            async for raw_chunk in ai_client.stream_chat(messages):
                try:
                    choices = raw_chunk.get("choices") if isinstance(raw_chunk, dict) else None
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}) or {}
                    content = delta.get("content")
                    if not content or not isinstance(content, str):
                        continue
                    clean = content.replace("\x00", "")
                    if clean:
                        yield clean
                except Exception:
                    continue
        except Exception:
            logger.warning("local_general_chat_stream_failed", exc_info=True)
            return

    async def _stream_socratic_evaluation(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None,
        tutor_state: dict | None = None,
    ):
        """D-130: يُقيّم إجابة الطالب الحرّة ويبثّ المكافأة + التسليم الرمزي المتدرّج.

        understood=true ⇒ تشجيع (LLM محروس) + خطوة رمزية حتمية + سؤال المتابعة.
        understood=false ⇒ اعتراف لطيف + تلميح. **لا إعادة طباعة للتمرين مهما حدث.**

        D-142 Phase 2: ``tutor_state`` (الحالة الدائمة) يُغذّي حارس التكرار بمرساة
        ``last_step_emitted`` (تنجو من نافذة التاريخ)، ويُستشار ``DialogueManagerSkill``
        (خلف العلم ``SEMANTIC_TUTOR_ENABLED``، fail-open) لقرار التقدّم/التصعيد/عدم القفز.
        """
        try:
            from app.services.skills.concept_diagnosis_skill import (
                ConceptDiagnosisInput,
                get_concept_diagnosis_skill,
            )
            from app.services.skills.semantic_property_skill import get_semantic_property_skill
            from app.services.skills.socratic_evaluator_skill import (
                SocraticEvaluatorInput,
                get_socratic_evaluator_skill,
            )
            from app.services.skills.tutor_metrics import (
                record_intervention,
                record_progress,
                record_repetition_avoided,
            )

            combo = self._load_canonical_combinations(question, history_messages)
            if combo is None:
                return  # غير احتمالات ⇒ لا نلتقط (المسار يُكمل)
            # قياس 1 (D-131 §5): التقطنا إجابة الطالب بدل إعادة طباعة التمرين.
            record_repetition_avoided()

            # المفهوم الحالي: من السؤال السقراطي السابق + إجابة الطالب (الطبقة 1، D-127).
            prior_socratic = ""
            for msg in reversed(history_messages or []):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    prior_socratic = str(msg.get("content", ""))[:600]
                    break
            _diag = await get_concept_diagnosis_skill().diagnose(
                ConceptDiagnosisInput(
                    question=f"{prior_socratic} {question}".strip(),
                    history=history_messages,
                )
            )
            concept = _diag.concept if _diag.concept != "unknown" else "event_meaning"

            facts = self._symbolic_facts_brief(combo)
            # ISS-122 (D-155): الحقيقة الرمزية تحكم إجابة الطالب **الرقمية** أولاً —
            # السؤال المعلّق يُشتق من قوالبنا في أحدث رسالة مساعد، والأرقام من
            # combo حصراً. كارثة الترانسكريبت: «هل هي 14 من 165» أُعيد سؤالها.
            _pending = self._pending_focus_from_history(history_messages)
            _numeric = self._verify_numeric_answer(question, combo, _pending)
            # D-142 (1A): السلطة الرمزية — تحقّق صحة الإجابة مقابل المحرك الرمزي (combo).
            _verified = self._verify_answer_against_combo(question, combo) or _numeric is not None

            _mtype = ""
            result = None
            if _numeric == "final_ratio":
                # ISS-122 (D-155): اعتراف صريح + تقدّم للسؤال الفرعي التالي — بلا
                # أرقام (يَنجو من حجب D-113 بنيوياً؛ تأكيد ما ولّده الطالب ليس كشفاً).
                text = (
                    "أحسنت! ✅ إجابتك صحيحة تماماً — ركّبت احتمال الحادثة A بنفسك: "
                    "الحالات الملائمة على كل الحالات الممكنة.\n\n"
                    "ننتقل للسؤال التالي في التمرين — **الحادثة B**: جداء الأرقام "
                    "عدد فردي. قبل أي حساب، سؤال واحد: متى يكون جداء ثلاثة أعداد فردياً؟"
                )
                record_progress("advanced")
            elif _numeric in ("step_correct", "direction"):
                # ISS-122 (D-155): خطوة جزئية صحيحة ⇒ اعتراف + **الخطوة التالية غير
                # المُجابة** (لا إعادة سؤال ما أُجيب، لا reveal superset).
                if _pending == "denominator" or _numeric == "direction":
                    text = self._build_symbolic_step(combo, "ratio", acknowledge=True)
                else:
                    text = (
                        "أحسنت — هذا هو عدد الحالات الملائمة (البسط). "
                        f"والآن: كم عدد **كل** الطرق الممكنة لسحب {combo.k} كرات من {combo.n}؟"
                    )
                record_progress("advanced")
            else:
                result = await get_socratic_evaluator_skill().evaluate(
                    SocraticEvaluatorInput(
                        student_answer=question,
                        concept=concept,
                        facts=facts,
                        history=history_messages,
                        verified_correct=_verified,
                    )
                )

                if result.understood:
                    body = self._build_symbolic_step(combo, result.next_focus, acknowledge=True)
                    # نُسبق التشجيع المُولَّد (إن وُجد ولم يكن مكرّراً للاعتراف القياسي).
                    enc = (result.encouragement or "").strip()
                    text = f"{enc}\n\n{body}" if enc and "الطريق الصحيح" not in enc else body
                    record_progress("advanced")  # قياس 4: تقدّم لخطوة جديدة
                else:
                    # D-131 «شخّص ثم تدخّل»: نشخّص الاعتقاد الخاطئ من رد الطالب ⇒ تدخّل مُوجَّه
                    # (مختلف لكل misconception)، لا تلميح موحَّد. عند الغموض نُصدر probe تشخيصياً.
                    enc = (result.encouragement or "فكرة جيدة — لنقترب أكثر.").strip()
                    _mc = get_semantic_property_skill().diagnose_misconception(
                        concept, question, history_messages
                    )
                    if _mc is not None:
                        _mtype = _mc.mtype
                        record_intervention(_mc.mtype)  # قياس 3: تدخّل مُصنَّف بنوع الاعتقاد
                        record_progress("advanced")
                        text = f"{enc}\n\n{_mc.intervention}"
                    else:
                        _probe = get_semantic_property_skill().first_probe(concept)
                        record_progress("repeated")
                        text = (
                            f"{enc} {_probe}"
                            if _probe
                            else (
                                f"{enc} لاحظ نوع كل كرة: أيّ الألوان يكفي عددها لسحب 3 منها "
                                "معاً؟ ابدأ بعدّ الألوان الممكنة فقط."
                            )
                        )

            # D-142 Phase 2: سلطة قرار الدور (DialogueManager) خلف العلم، fail-open. تُعيد
            # تشكيل القرار بإشارات حيّة (دليل + قدرة BKT + ميزانية المفهوم الدائمة + منع تكرار).
            _dm_reason = ""
            _ts = tutor_state if isinstance(tutor_state, dict) else {}
            _last_step = str(_ts.get("last_step_emitted") or "")
            # ISS-122 (D-155): الحكم الرقمي الحتمي نهائي — لا يُعاد تشكيله بالـ DM.
            if self._semantic_tutor_enabled() and _numeric is None and result is not None:
                _dm = self._dialogue_decision(
                    question=question,
                    concept=concept,
                    verified_correct=_verified,
                    understood=result.understood,
                    tutor_state=_ts,
                    candidate_text=text,
                )
                if _dm is not None:
                    _dm_reason = _dm.reason
                    _action = _dm.action
                    if _action == "acknowledge_advance":
                        text = self._build_symbolic_step(combo, _dm.focus, acknowledge=True)
                    elif _action == "intermediate_scaffold":
                        text = self._build_symbolic_step(combo, "numerator", acknowledge=True)
                    elif _action == "symbolic_reveal":
                        _rv = self._build_symbolic_reveal(
                            question, history_messages, acknowledge=True
                        )
                        if _rv:
                            text = _rv
                    record_progress("advanced")

            # D-142 (1B) + ISS-121 (D-154): «ممنوع بثّ مكرَّر» بنيوياً — التطبيع صار
            # محايداً للحجب (أرقام/«؟» ⇒ #) فلا يَعمى عن النسخة المحفوظة المحجوبة؛
            # وعند التكرار نجرّب سلسلة بدائل بالترتيب (إنقاذ ⇒ خطوات السُّلّم بؤرةً
            # بؤرة ⇒ مُوجّه توليد قصير) ونبثّ **أول غير مكرَّر** — كل دور يقدّم جديداً.
            def _is_dup(t: str) -> bool:
                return self._recently_emitted(t, history_messages) or (
                    _last_step and self._near_dup(t, _last_step)
                )

            if _is_dup(text):
                # ISS-122 (D-155): «الخطوة التالية غير المُجابة» أولاً (من السؤال
                # المعلّق)، والإنقاذ الكامل (reveal superset) **أخيراً** — كان أول
                # البدائل فيعيد طباعة المعروض (تكرار مُقنَّع، الدور 4 في الترانسكريبت).
                _first, _second = (
                    ("ratio", "numerator") if _pending == "denominator" else ("numerator", "ratio")
                )
                _alternatives = (
                    self._build_symbolic_step(combo, _first, acknowledge=True),
                    self._build_symbolic_step(combo, _second, acknowledge=True),
                    "أنت تملك الآن كل المعطيات — جرّب بنفسك: ركّب البسط على المقام، "
                    "وأخبرني ما قيمة P(A) التي حصلت عليها، وسأخبرك إن أصبت.",
                    self._build_symbolic_reveal(question, history_messages, acknowledge=True),
                )
                for _cand in _alternatives:
                    if _cand and not _is_dup(_cand):
                        text = _cand
                        record_progress("advanced")
                        break

            logger.info(
                "socratic_evaluation",
                extra={
                    "concept": concept,
                    "understood": bool(_numeric) or bool(result and result.understood),
                    "source": (result.source if result else f"numeric:{_numeric}"),
                    "next_focus": (result.next_focus or "") if result else "",
                    "misconception_mtype": _mtype,
                    "verified_correct": _verified,
                    "numeric_verdict": _numeric or "",
                    "pending_focus": _pending or "",
                    "dialogue_manager_reason": _dm_reason,
                },
            )

            async for chunk in self._stream_markdown_typing(text):
                yield chunk
        except Exception:
            logger.warning("_stream_socratic_evaluation_failed", exc_info=True)
            return

    @staticmethod
    def _explanation_via_orchestrator_enabled() -> bool:
        """D-103: هل يُمرَّر شرح التمارين عبر orchestrator (الرسم الـ13-node)؟

        رافعة رجوع فورية بلا deploy (نمط D-025 / routing_policy):
        ``EXPLANATION_VIA_ORCHESTRATOR=0`` يعيد السلوك المحلي القديم.
        """
        raw = os.getenv("EXPLANATION_VIA_ORCHESTRATOR", "1").strip().lower()
        return raw not in ("0", "false", "no")

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

    async def chat_with_agent(
        self,
        question: str,
        user_id: int,
        conversation_id: int | None = None,
        history_messages: list[dict[str, str]] | None = None,
        context: dict[str, object] | None = None,
    ) -> AsyncGenerator[dict | str, None]:
        """
        Chat with the Orchestrator Agent (Microservice).
        Expects NDJSON stream from the service.
        Yields either structured event dictionaries or fallback strings.
        """
        import time

        from app.services.skills.concept_diagnosis_skill import (
            ConceptDiagnosisInput,
            get_concept_diagnosis_skill,
        )
        from app.services.skills.pedagogical_policy_engine import (
            PedagogicalPolicyEngine,
            PolicyObservation,
        )
        from app.telemetry.unified_observability import get_unified_observability

        obs = get_unified_observability()
        _t0 = time.perf_counter()
        _root_ctx = None
        with contextlib.suppress(Exception):
            _root_ctx = obs.start_trace(
                "orchestrator.chat_with_agent",
                tags={
                    "user_id": str(user_id),
                    "conversation_id": str(conversation_id),
                    "question_len": len(question),
                },
            )

        # Extract current state
        tutor_state = context.get("tutor_state", {}) if isinstance(context, dict) else {}

        # Formulate Observation
        ConceptDiagnosisInput(question=question, history=history_messages)
        diagnosis = get_concept_diagnosis_skill().diagnose_deterministic(question)

        is_correct = self._verify_answer_against_combo(
            question, self._load_canonical_combinations(question, history_messages)
        )

        obs = PolicyObservation(
            question=question,
            active_concept=diagnosis.concept or tutor_state.get("active_concept", ""),
            is_correct=is_correct,
            has_misconception=bool(diagnosis.misconception),
            detected_misconception=diagnosis.misconception or "",
            is_frustrated=False,  # Could be inferred from sentiment, using default
        )

        # Consult Policy Engine
        engine = PedagogicalPolicyEngine()
        policy_decision = engine.evaluate_turn(tutor_state, obs)

        # We must inject policy_decision into the context so it can be passed back to record_turn in customer_chat
        if context is not None:
            context["policy_decision"] = policy_decision

        # Enforce Symbolic Truth explicitly: if question targets unmodeled mathematical event, force drift prevention
        _comp = await self._build_probability_computational_answer(question, history_messages)
        if _comp:
            _comp_text, _comp_event = _comp
            if _comp_event.startswith("defer_"):
                # Strict drift prevention: Unmodeled event
                yield self._normalize_stream_event(
                    {"type": "assistant_delta", "payload": {"content": _comp_text}}
                )
                yield self._normalize_stream_event(
                    {"type": "assistant_final", "payload": {"content": ""}}
                )
                return

        # D-158: طبقة القرار الموحَّدة فوق tutor_state المُخزَّن (خلف COGNITIVE_TURN_ENABLED،
        # افتراض OFF ⇒ سلوك اليوم دون تغيير). عند التفعيل تعترض دور الاحتمالات وتُصدِر خطوة
        # واحدة تدريجية (تقتل التفريغ + التكرار + سجن 600-حرف بنيوياً). fail-open ⇒ تسليم للكتل.
        if self._cognitive_turn_enabled():
            _ct_text, _ct_delta = self._cognitive_turn(
                question, history_messages, tutor_state, policy_decision
            )
            if _ct_text:
                yield self._normalize_stream_event(
                    {"type": "assistant_delta", "payload": {"content": _ct_text}}
                )
                yield self._normalize_stream_event(
                    {"type": "assistant_final", "payload": {"content": ""}}
                )
                return

        # In D-144, if the policy engine mandates a specific pedagogical action (e.g. symbolic reveal or intermediate scaffold)
        # we bypass the standard generative fallbacks and directly emit that action.
        if policy_decision.next_action == "symbolic_reveal":
            _reveal_text = self._build_symbolic_reveal(
                question, history_messages, acknowledge=obs.is_correct
            )
            if _reveal_text:
                yield self._normalize_stream_event(
                    {"type": "assistant_delta", "payload": {"content": _reveal_text}}
                )
                yield self._normalize_stream_event(
                    {"type": "assistant_final", "payload": {"content": ""}}
                )
                return

        # ─────────────────────────────────────────────────────────────────────
        # ISS-079 (D-067 — 2026-05-17): Greeting Fast-Path Preemption
        # كارثة المستخدم: "السلام عليكم" → رد etymological طويل بكلمات أجنبية
        # ("hopephe pepe aaaa" / "وتُستَخدم كتعبير ترحيبي" بدلاً من رد التحية)
        # السبب: نماذج OpenRouter المجانية تفسر التحية كسؤال علمي تحت
        # "أجب بدقة" system prompt → etymology طويلة بدلاً من رد بسيط.
        # الحل: ردود deterministic للتحيات الشائعة (0ms، 100% نظيف).
        # ─────────────────────────────────────────────────────────────────────
        try:
            from app.services.chat.local_graph import _greeting_fastpath_response

            greeting_response = _greeting_fastpath_response(question)
        except Exception:
            # D-158: أُزيل هنا التكرار الميت (PedagogicalPolicyEngine/evaluate_turn +
            # فحص defer مكرَّر يُهمَل ناتجه) الذي كان يعمل فقط لو فشل استيراد التحية.
            # المنطق الحقيقي (policy + defer) يجري مرة واحدة في أعلى الدالة.
            greeting_response = None

        if greeting_response:
            logger.info(
                "greeting_fastpath_preempt",
                extra={
                    "request_id": str(uuid.uuid4()),
                    "question_len": len(question),
                    "reason": "matched_greeting_fastpath",
                },
            )
            # ابث الرد كقطعة واحدة (التحية قصيرة بطبعها)
            yield self._normalize_stream_event(
                {"type": "assistant_delta", "payload": {"content": greeting_response}}
            )
            yield self._normalize_stream_event(
                {"type": "assistant_final", "payload": {"content": ""}}
            )
            if _root_ctx:
                with contextlib.suppress(Exception):
                    obs.end_span(
                        _root_ctx.span_id,
                        status="OK",
                        metrics={
                            "duration_ms": (time.perf_counter() - _t0) * 1000,
                            "fallback_path": 0.25,  # greeting = أعلى أولوية
                            "stream_chars": float(len(greeting_response)),
                        },
                    )
            return

        # ─────────────────────────────────────────────────────────────────────
        # ISS-112 — «أعطني السؤال رقم N فقط» (question-only preempt):
        # يسبق الاسترجاع المُفهرَس: طلب سؤال مرقَّم محدد يجب أن يُقتطع من النص
        # الرسمي (صفر LLM) لا أن يُغرق الطالب بالتمرين كاملاً أو — أسوأ —
        # بحل مُهلوَس. نية الشرح («اشرح السؤال 2») لا تُختطف (الكاشف يرفضها).
        # صفر قطع مبثوثة ⇒ المسار يتابع طبيعياً (fail-open).
        # ─────────────────────────────────────────────────────────────────────
        qo_streamed_chars = 0
        try:
            async for chunk in self._stream_question_only_response(question, history_messages):
                if not chunk:
                    continue
                qo_streamed_chars += len(chunk)
                yield self._normalize_stream_event(
                    {"type": "assistant_delta", "payload": {"content": chunk}}
                )
        except Exception:
            logger.warning("question_only_preempt_failed", exc_info=True)

        if qo_streamed_chars > 0:
            if _root_ctx:
                with contextlib.suppress(Exception):
                    obs.end_span(
                        _root_ctx.span_id,
                        status="OK",
                        metrics={
                            "duration_ms": (time.perf_counter() - _t0) * 1000,
                            "fallback_path": 0.4,  # بين التحية والاسترجاع المُفهرَس
                            "stream_chars": float(qo_streamed_chars),
                        },
                    )
            yield self._normalize_stream_event(
                {"type": "assistant_final", "payload": {"content": ""}}
            )
            return

        # ─────────────────────────────────────────────────────────────────────
        # D-143 (ISS-117): أسئلة الاحتمالات الحسابية تُجاب حتمياً **قبل** سُلّم الحادثة A.
        # «لماذا نضرب 11×10×9» ⇒ مبدأ العدّ؛ «كيف حصلنا على 56» ⇒ الحادثة B (56/165 من أرقام
        # الكرات)؛ الحوادث غير المنمذجة (C/D/X/الأمل/الشرطي) ⇒ تأجيل حتمي صادق يُبعدها عن A.
        # صفر LLM في مسار الرياضيات (نقد المالك #1). يكسر اختطاف المصفوفة للأسئلة الحسابية.
        # ─────────────────────────────────────────────────────────────────────
        _comp = await self._build_probability_computational_answer(question, history_messages)
        if _comp is not None:
            _comp_text, _comp_event = _comp
            # D-143 (RC-4): لا تُعَد الإجابة الحسابية نفسها حرفياً عند تكرار السؤال. عند
            # التكرار نتقدّم لتمثيلٍ حتميّ **مختلف** (تخصيص بيداغوجي، نقد المالك #2) ثم
            # لمُوجِّه تقدّم — صفر LLM، صفر تكرار حرفي. لو استُنفِدت كلّها ⇒ نُسلّم للطبقة التالية.
            _comp_outcome = (
                "correct_event" if _comp_event in ("event_b", "combinations") else "deferred"
            )
            _comp_emit = True
            if self._recently_emitted(_comp_text, history_messages):
                _comp_var = self._probability_computational_variant(_comp_event, history_messages)
                if _comp_var and not self._recently_emitted(_comp_var, history_messages):
                    _comp_text, _comp_outcome = _comp_var, "advanced"
                else:
                    _comp_adv = self._probability_computational_advance_prompt()
                    if not self._recently_emitted(_comp_adv, history_messages):
                        _comp_text, _comp_outcome = _comp_adv, "advanced"
                    else:
                        _comp_emit = False
            if _comp_emit:
                with contextlib.suppress(Exception):
                    from app.services.skills.tutor_metrics import record_probability_routing

                    record_probability_routing(_comp_event, _comp_outcome)
                _comp_chars = 0
                async for chunk in self._stream_markdown_typing(_comp_text):
                    if not chunk:
                        continue
                    _comp_chars += len(chunk)
                    yield self._normalize_stream_event(
                        {"type": "assistant_delta", "payload": {"content": chunk}}
                    )
                if _comp_chars > 0:
                    logger.info(
                        "probability_computational_answer",
                        extra={
                            "event": _comp_event,
                            "outcome": _comp_outcome,
                            "stream_chars": float(_comp_chars),
                        },
                    )
                    yield self._normalize_stream_event(
                        {"type": "assistant_final", "payload": {"content": ""}}
                    )
                    return

        # ─────────────────────────────────────────────────────────────────────
        # ISS-116 (D-138 — المصفوفة التصعيدية التكيّفية): تعليم **مفهوم مُسمّى** عبر
        # Escalation Matrix + Understanding-Signal + Misconception-Check، مُعايَرةً بقدرة
        # الطالب (support_level/BKT). concept-scoped ⇒ لا انحراف لـ event-A؛ ذاكرة التصعيد ⇒
        # لا تكرار؛ «اعطني مثال عددي» ⇒ محاكاة مصغّرة حتمية (L3)؛ دليل فهم ⇒ توقّف؛ مفهوم خاطئ ⇒
        # تدخّل مُوجَّه. المسار الأساسي لتعليم المفهوم المعروف؛ preempt التعريف أدناه يبقى
        # للمفاهيم الجديدة غير المُسجَّلة (LLM Listener-Definer). حكم المالك: «أقل تدخّل مفيد».
        # ─────────────────────────────────────────────────────────────────────
        try:
            from app.services.skills.micro_simulation_skill import get_micro_simulation_skill
            from app.services.skills.pedagogical_escalation_skill import (
                EscalationInput,
                get_pedagogical_escalation_skill,
            )
            from app.services.skills.semantic_property_skill import (
                PROPERTY_REGISTRY,
                get_semantic_property_skill,
            )
            from app.services.skills.student_state_skill import (
                StudentStateInput,
                get_student_state_skill,
            )

            _concept_teach_intents = frozenset(
                {"definition", "example_request", "confusion", "procedure", "hint_request"}
            )
            _esc_state = get_student_state_skill().read(
                StudentStateInput(question=question, history=history_messages)
            )
            _esc_hist = " ".join(
                str(m.get("content", "")) for m in (history_messages or []) if isinstance(m, dict)
            )
            _esc_sps = get_semantic_property_skill()
            # D-139: حارس الحساب — «احسب/كم/اوجد/بيّن/استنتج» تبقى للمسار الحسابي (لا تُفعَّل المصفوفة).
            # D-143: + «نضرب/ضربنا/ضرب/حصلنا على» — أسئلة العدّ/الجداء يتولّاها المسار الحسابي الحتمي
            # (defense-in-depth خلف preempt _build_probability_computational_answer)، لا سُلّم الحادثة A.
            _esc_ql = (question or "").lower()
            _esc_compute = any(
                m in _esc_ql
                for m in (
                    "احسب",
                    "أحسب",
                    "كم ",
                    "اوجد",
                    "أوجد",
                    "بيّن",
                    "بين ان",
                    "استنتج",
                    "نضرب",
                    "ضربنا",
                    "ضرب ",
                    "حصلنا على",
                )
            )
            # D-139: متابعة المفهوم — «كيف/لماذا/وضح/اشرح/مثال/لم أفهم/؟» تُمسَك حتى لو صُنّفت unknown
            # (كانت «كيف نضيق الإمكانيات» / «كيف نحصل على معدومة» تسقط لـ D-135 → نص الحادثة A).
            _esc_followup = any(
                m in _esc_ql
                for m in (
                    "كيف",
                    "لماذا",
                    "علاش",
                    "وضح",
                    "اشرح",
                    "بسط",
                    "؟",
                    "مثال",
                    "لم افهم",
                    "لم أفهم",
                    "مفهمتش",
                )
            )
            _esc_teach_ok = _esc_state.primary_intent in _concept_teach_intents or (
                _esc_state.primary_intent == "unknown"
                and (_esc_followup or _esc_sps.interpret(question) is not None)
            )
            _esc_active = (
                _esc_sps.detect_active_concept(question, history_messages)
                if _esc_teach_ok
                and not _esc_compute
                and self._is_prob_context(question + " " + _esc_hist)
                else None
            )
            if _esc_active is not None:
                # support_level من BKT (D-104/D-126) عبر context — يُعايِر الرُّتبة.
                try:
                    _esc_sup = int((context or {}).get("support_level") or 0) or None
                except (TypeError, ValueError):
                    _esc_sup = None
                # آخر رسالة طالب (للـ Misconception Check).
                _esc_last = next(
                    (
                        str(m.get("content", ""))
                        for m in reversed(history_messages or [])
                        if isinstance(m, dict) and m.get("role") == "user"
                    ),
                    question,
                )
                _esc_mis = _esc_sps.diagnose_misconception(
                    _esc_active.concept_id, _esc_last, history_messages
                )
                _esc_spec = PROPERTY_REGISTRY.get(_esc_active.property_id)
                # D-159 (WP-B): ذاكرة FSM الدائمة لهذا المفهوم من tutor_state.kc_progress —
                # تَنجو من نافذة الـ50 رسالة وإعادة تشغيل العملية (مسح النصّ يبقى شبكة أمان).
                from app.services.skills.kc_progress_schema import (
                    escalation_levels_of,
                    parse_kc_entry,
                )

                _esc_kcp = tutor_state.get("kc_progress") if isinstance(tutor_state, dict) else None
                _esc_kcp = _esc_kcp if isinstance(_esc_kcp, dict) else {}
                _esc_levels = escalation_levels_of(_esc_kcp, _esc_active.concept_id)
                # D-159 (WP-D): تشخيص الجذر عبر حواف الـ graph — حين يكون جذر الصعوبة
                # شرطاً مسبقاً ضعيفاً (بحسب الحالة الدائمة)، يستهدف التدخّلُ الجذرَ لا
                # العرَض («أساس فجوة الوهم»). fail-open ⇒ التدخّل الأصلي دون تغيير.
                _esc_intervention = _esc_mis.intervention if _esc_mis else None
                _esc_root = None
                if _esc_mis is not None:
                    with contextlib.suppress(Exception):
                        from app.services.skills.semantic_property_skill import diagnose_root

                        _esc_root = diagnose_root(_esc_mis.bkt_concept, _esc_kcp)
                        if _esc_root is not None:
                            _esc_intervention = _esc_root.intervention_text
                _esc_decision = get_pedagogical_escalation_skill().decide(
                    EscalationInput(
                        concept_id=_esc_active.concept_id,
                        title=_esc_active.title,
                        definition=_esc_active.definition,
                        example=_esc_active.example,
                        micro_sim=get_micro_simulation_skill().get_micro_simulation(
                            _esc_active.concept_id
                        ),
                        # D-147: سؤال خطوة التطبيق على التمرين — يستبدل الـ punt العام عند نفاد السُّلّم.
                        apply_step=get_micro_simulation_skill().get_apply_step(
                            _esc_active.concept_id
                        ),
                        intent=_esc_state.primary_intent,
                        frustration=_esc_state.frustration,
                        support_level=_esc_sup,
                        history=history_messages or [],
                        evidence_markers=(_esc_spec.evidence_markers if _esc_spec else ()),
                        misconception_intervention=_esc_intervention,
                        misconception_mtype=(_esc_mis.mtype if _esc_mis else None),
                        # D-159 (WP-B): الرُّتب المُسلَّمة من الحالة الدائمة (FSM حقيقي).
                        delivered_levels=_esc_levels,
                    )
                )
                # D-143 (RC-4): حارس التكرار — إن كان نصّ المصفوفة مُكرّراً لرسالة مساعد سابقة
                # (مثل «مررنا بالتعريف والمثال والمحاكاة…» عند استنفاد السُّلّم)، نُصعّد إلى الحلّ
                # الرمزي الحتمي بدل إعادته حرفياً (يكسر التكرار اللانهائي). يعمل حتى لو تجاوز
                # نافذة التاريخ عبر _recently_emitted.
                if _esc_decision.text and self._recently_emitted(
                    _esc_decision.text, history_messages
                ):
                    _esc_alt = self._build_probability_direct_explanation(
                        question, history_messages
                    ) or self._build_symbolic_reveal(question, history_messages, acknowledge=True)
                    if _esc_alt and not self._recently_emitted(_esc_alt, history_messages):
                        _esc_decision = _esc_decision.model_copy(update={"text": _esc_alt})
                if _esc_decision.text:
                    from app.services.skills.tutor_metrics import (
                        record_intent,
                        record_intervention,
                        record_repetition_avoided,
                        record_response_mode,
                    )

                    record_intent(_esc_state.primary_intent)
                    record_response_mode(_esc_decision.action)
                    record_repetition_avoided()  # المصفوفة تمنع التكرار بالتصميم.
                    if _esc_decision.action == "target_misconception" and _esc_mis is not None:
                        record_intervention(_esc_mis.mtype)
                    _esc_chars = 0
                    async for chunk in self._stream_markdown_typing(_esc_decision.text):
                        if not chunk:
                            continue
                        _esc_chars += len(chunk)
                        yield self._normalize_stream_event(
                            {"type": "assistant_delta", "payload": {"content": chunk}}
                        )
                    if _esc_chars > 0:
                        logger.info(
                            "pedagogical_escalation",
                            extra={
                                "concept": _esc_active.concept_id,
                                "action": _esc_decision.action,
                                "level": _esc_decision.strategy_level,
                                "intent": _esc_state.primary_intent,
                                "support_level": _esc_sup,
                                "root_concept": (_esc_root.root_concept_id if _esc_root else ""),
                            },
                        )
                        # D-159 (WP-B): كتابة الرُّتبة المُسلَّمة في الحالة الدائمة عبر دلتا
                        # kc_progress (يحفظها customer_chat عبر record_turn) — نهاية «FSM»
                        # الذي يُعيد بناء نفسه من مسح النصّ. fail-open مطلق.
                        with contextlib.suppress(Exception):
                            _esc_entry = parse_kc_entry(_esc_kcp.get(_esc_active.concept_id))
                            _esc_entry.attempts += 1
                            if _esc_decision.action == "teach" and _esc_decision.strategy_level:
                                _esc_entry.mark_escalation(f"L{_esc_decision.strategy_level}")
                                if _esc_entry.state == "not_addressed":
                                    _esc_entry.state = "explained"
                            elif _esc_decision.action == "mastered":
                                _esc_entry.state = "understood"
                                _esc_entry.evidence = "verified"
                            if isinstance(tutor_state, dict):
                                _esc_delta = tutor_state.setdefault("kc_progress_delta", {})
                                if isinstance(_esc_delta, dict):
                                    _esc_delta[_esc_active.concept_id] = _esc_entry.to_dict()
                        yield self._normalize_stream_event(
                            {"type": "assistant_final", "payload": {"content": ""}}
                        )
                        return
        except Exception:
            logger.warning("pedagogical_escalation_failed", exc_info=True)

        # ─────────────────────────────────────────────────────────────────────
        # ISS-116 (D-132 — Generalized Concept Understanding / preempt تعريفي عام):
        # «جاهزية للأسئلة الجديدة دائماً». إن كان السؤال نية تعريفية («ماذا نقصد بـ X»)
        # أو حيرة عن مفهوم مُسمّى («لم افهم المتغير العشوائي») ضمن سياق احتمالات ⇒ نُعرّف X
        # عبر interpret_or_define (السجلّ الحتمي أولاً، ثم الـ LLM Listener-Definer للمفاهيم
        # الجديدة). يسبق الالتقاط السقراطي لأن «لم افهم المتغير العشوائي» سؤال تعريفي جديد لا
        # إجابة على السؤال السقراطي السابق. يحلّ الكارثة: كان يُعاد بسؤال عن الحادثة A.
        # لا default مُجمَّد لمفهوم واحد. ممنوع على طلبات الحساب. D-138: المفاهيم المُسجَّلة
        # يتولّاها بلوك المصفوفة التصعيدية أعلاه؛ هذا يبقى للمفاهيم الجديدة غير المُسجَّلة.
        # ─────────────────────────────────────────────────────────────────────
        try:
            from app.services.skills.semantic_property_skill import get_semantic_property_skill
            from app.services.skills.student_state_skill import (
                StudentStateInput,
                get_student_state_skill,
            )

            _sps = get_semantic_property_skill()
            # D-133: قراءة حالة الطالب (نيّة + إحباط) كإشارة قرار — حتمي.
            _state = get_student_state_skill().read(
                StudentStateInput(question=question, history=history_messages)
            )
            _hist_text = " ".join(
                str(m.get("content", "")) for m in (history_messages or []) if isinstance(m, dict)
            )
            _ql = (question or "").lower()
            # D-133: الحيرة = primary_intent (أو secondary) لا markers مبعثرة.
            _confused = (
                _state.primary_intent == "confusion" or "confusion" in _state.secondary_signals
            )
            _compute = any(
                m in _ql
                for m in ("احسب", "أحسب", "كم ", "اوجد", "أوجد", "بين ان", "بيّن أن", "استنتج")
            )
            # D-137: نيّة التعريف من StudentState تُفعّل مسار التعريف أيضاً — «ما هو X»
            # يصنّفها StudentState `definition`، فلا تسقط لـ D-135 (كارثة «14 من 165» للشرطي).
            _wants_def = (
                _sps.is_definitional(question)
                or _state.primary_intent == "definition"
                or (_confused and _sps.interpret(question) is not None)
            )
            if _wants_def and not _compute and self._is_prob_context(question + " " + _hist_text):
                _def = await _sps.interpret_or_define(question)
                if _def is not None:
                    from app.services.skills.tutor_metrics import (
                        record_definitional_answer,
                        record_intent,
                        record_response_mode,
                    )

                    record_definitional_answer(_def.concept_id, resolved=True, source=_def.source)
                    record_intent(_state.primary_intent)
                    _text = (
                        f"## {_def.title}\n\n{_def.definition}"
                        if _def.title and _def.title != "تعريف"
                        else _def.definition
                    )
                    # D-133 (وصفة المالك): الحيرة ⇒ تعريف + **مثال ملموس** + **سؤال موجِّه واحد**
                    # — لا تعريف-فقط. المعطيات من المحرك الرمزي (محايدة للمفهوم)، السؤال محروس.
                    _mode = "define"
                    if _confused:
                        _mode = "confusion_enriched"
                        with contextlib.suppress(Exception):
                            _combo = self._load_canonical_combinations(question, history_messages)
                            if _combo is not None:
                                _balls = self._balls_brief(_combo)
                                _gq = await self._generate_guiding_question(_def.concept_id, _balls)
                                _text += f"\n\nلنربطها بهذا التمرين: {_balls}.\n\n" + (
                                    _gq or "هل يمكنك تطبيق هذا على معطيات الكيس؟"
                                )
                    record_response_mode(_mode)
                    _def_chars = 0
                    async for chunk in self._stream_markdown_typing(_text):
                        if not chunk:
                            continue
                        _def_chars += len(chunk)
                        yield self._normalize_stream_event(
                            {"type": "assistant_delta", "payload": {"content": chunk}}
                        )
                    if _def_chars > 0:
                        logger.info(
                            "definitional_preempt",
                            extra={
                                "concept": _def.concept_id,
                                "source": _def.source,
                                "intent": _state.primary_intent,
                                "frustration": _state.frustration,
                                "response_mode": _mode,
                            },
                        )
                        yield self._normalize_stream_event(
                            {"type": "assistant_final", "payload": {"content": ""}}
                        )
                        return
        except Exception:
            logger.warning("definitional_preempt_failed", exc_info=True)

        # ─────────────────────────────────────────────────────────────────────
        # ISS-116 (D-136 — مثال واعٍ بالمفهوم النشط): «اعطني مثال» ⇒ مثال **المفهوم
        # الذي يجري الحوار عنه** (product_even/expected_value…) لا مثال الحادثة A الأعمى
        # الافتراضي (كارثة transcript: 4 أسئلة مختلفة ⇒ نفس مثال A). يسبق D-135 (المكبوح)
        # والاسترجاع المُفهرَس. لا تكرار (المعروض already ⇒ زاوية LLM محروسة).
        # ─────────────────────────────────────────────────────────────────────
        try:
            from app.services.skills.semantic_property_skill import get_semantic_property_skill
            from app.services.skills.student_state_skill import (
                StudentStateInput,
                get_student_state_skill,
            )

            _ex_state = get_student_state_skill().read(
                StudentStateInput(question=question, history=history_messages)
            )
            _ex_hist = " ".join(
                str(m.get("content", "")) for m in (history_messages or []) if isinstance(m, dict)
            )
            # D-137: يَفعل على example_request **أو** الحيرة مع مفهوم نشط — «لم أفهم» بعد شرح
            # الاحتمال الشرطي يُعيد إشراك المفهوم النشط (الاحتمال الشرطي) لا الحادثة A الافتراضية.
            _ex_confused = (
                _ex_state.primary_intent == "confusion"
                or "confusion" in _ex_state.secondary_signals
            )
            _ex_active = get_semantic_property_skill().detect_active_concept(
                question, history_messages
            )
            _ex_fire = _ex_state.primary_intent == "example_request" or (
                _ex_confused and _ex_active is not None
            )
            if _ex_fire and self._is_prob_context(question + " " + _ex_hist):
                _ce = await self._build_concept_example(question, history_messages)
                if _ce:
                    from app.services.skills.tutor_metrics import (
                        record_intent,
                        record_response_mode,
                    )

                    record_intent(_ex_state.primary_intent)
                    record_response_mode("example_first")
                    _ce_chars = 0
                    async for chunk in self._stream_markdown_typing(_ce):
                        if not chunk:
                            continue
                        _ce_chars += len(chunk)
                        yield self._normalize_stream_event(
                            {"type": "assistant_delta", "payload": {"content": chunk}}
                        )
                    if _ce_chars > 0:
                        logger.info("concept_example_preempt", extra={"intent": "example_request"})
                        yield self._normalize_stream_event(
                            {"type": "assistant_final", "payload": {"content": ""}}
                        )
                        return
        except Exception:
            logger.warning("concept_example_preempt_failed", exc_info=True)

        # ─────────────────────────────────────────────────────────────────────
        # ISS-116 (D-130 — الإصغاء النشط / مُقيّم الإجابات السقراطي):
        # إذا كانت أحدث رسالة مساعد سؤالاً سقراطياً طرحناه، فرسالة الطالب الحالية
        # = **إجابة** على ذلك السؤال — تُقيَّم وتُكافأ، لا تُعاد طباعة التمرين.
        # يسبق الاسترجاع المُفهرَس (#3) لأن إجابة الطالب الحرة («نفس اللون فقط،
        # الحمراء والخضراء») تحوي كلمات اللون فتُطابق _has_indexed_match فتُعيد
        # طباعة التمرين كاملاً (الخيانة البيداغوجية). قفل الحالة عبر التاريخ
        # (لا حقل دائم). حارس تبديل الموضوع (D-101) داخل is_response_to_socratic.
        #
        # ISS-122 (D-155): سؤال مفاهيمي/استفهامي أثناء الحوار («لم افهم العلاقة
        # بين 14 و 165»، «لماذا حصلنا على 14 و 165») **ليس إجابةً تُقيَّم** — كان
        # يُبتلع هنا فيسقط في سُلّم بدائل أصمّ. يسقط الآن لكتلة D-124/D-125
        # (شرح العلاقة/الاشتقاق). «هل هي 14 من 165» تبقى إجابة (تطلب تأكيداً).
        # ─────────────────────────────────────────────────────────────────────
        if (
            self._in_socratic_dialogue(question, history_messages)
            and not self._detect_conceptual_question(question)
            and not (question or "").strip().startswith(self._QUESTION_OPENERS_NOT_ANSWERS)
        ):
            se_streamed_chars = 0
            _tutor_state = (context or {}).get("tutor_state") if isinstance(context, dict) else None
            try:
                async for chunk in self._stream_socratic_evaluation(
                    question,
                    history_messages,
                    tutor_state=_tutor_state if isinstance(_tutor_state, dict) else None,
                ):
                    if not chunk:
                        continue
                    se_streamed_chars += len(chunk)
                    yield self._normalize_stream_event(
                        {"type": "assistant_delta", "payload": {"content": chunk}}
                    )
            except Exception:
                logger.warning("socratic_evaluation_preempt_failed", exc_info=True)

            if se_streamed_chars > 0:
                if _root_ctx:
                    with contextlib.suppress(Exception):
                        obs.end_span(
                            _root_ctx.span_id,
                            status="OK",
                            metrics={
                                "duration_ms": (time.perf_counter() - _t0) * 1000,
                                "fallback_path": 0.45,  # بين question-only والاسترجاع المُفهرَس
                                "stream_chars": float(se_streamed_chars),
                            },
                        )
                yield self._normalize_stream_event(
                    {"type": "assistant_final", "payload": {"content": ""}}
                )
                return
            # إذا فشل البث (نادر) → نُكمل المسار العادي (لا إعادة طباعة بسبب fail-open)

        # ─────────────────────────────────────────────────────────────────────
        # ISS-056 (D-049 — Indexed Retrieval Preemption):
        # إذا طابق السؤال تمريناً محدداً في knowledge_index، نتجاوز كل
        # شيء (orchestrator + StateGraph + fallback chain) ونبث المحتوى
        # المُفهرَس النظيف مباشرة. هذا يحل كارثة JSON envelope leak عند المصدر.
        # ISS-CONV-C: نمرر history_messages لحل أسئلة المتابعة بالسياق.
        #
        # ISS-110 (D-101): هذه الكتلة تسبق الآن _build_calculated_ui — طلب
        # تمرين صريح («اعطني تمرين الدوال العددية») يهزم دائماً الواجهة
        # المحسوبة. قبل هذا الترتيب، MODE_A كان يُنهي المسار بمكوّن احتمالات
        # مبني من history التمرين السابق قبل وصول الاسترجاع المُفهرَس (كارثة حية).
        # ─────────────────────────────────────────────────────────────────────
        if self._has_indexed_match(
            question, history_messages
        ) and not self._is_short_answer_in_dialogue(question, history_messages):
            logger.info(
                "indexed_retrieval_preempt",
                extra={
                    "request_id": str(uuid.uuid4()),
                    "question_len": len(question),
                    "reason": "matched_knowledge_index_entry",
                },
            )
            ret_streamed_chars = 0
            try:
                async for chunk in self._stream_local_retrieval_response(
                    question, history_messages
                ):
                    if not chunk:
                        continue
                    ret_streamed_chars += len(chunk)
                    yield self._normalize_stream_event(
                        {"type": "assistant_delta", "payload": {"content": chunk}}
                    )
            except Exception:
                logger.warning("indexed_retrieval_preempt_failed", exc_info=True)

            if ret_streamed_chars > 0:
                if _root_ctx:
                    with contextlib.suppress(Exception):
                        obs.end_span(
                            _root_ctx.span_id,
                            status="OK",
                            metrics={
                                "duration_ms": (time.perf_counter() - _t0) * 1000,
                                "fallback_path": 0.5,  # preempt = أعلى من file_intelligence
                                "stream_chars": float(ret_streamed_chars),
                            },
                        )
                yield self._normalize_stream_event(
                    {"type": "assistant_final", "payload": {"content": ""}}
                )
                return
            # إذا فشل البث (نادر جداً) → نُكمل المسار العادي

        # ─────────────────────────────────────────────────────────────────────
        # D-124 — مخرج الطوارئ الحتمي (Deterministic Escape Hatch):
        # كسر «حلقة الموت اللانهائية» في تمرين الاحتمالات. بعد D-116/D-123 صار كل
        # سؤال احتمالات يُنهي دائماً إلى الكاروسيل (صفر LLM) ⇒ سؤال محدّد («كيف
        # وجدنا 4 الحمراء؟») أو حيرة متكررة («لم أفهم»×N) يُعيدان طباعة نفس
        # الكاروسيل بلا تقدّم. الحل (تشخيص المالك): سؤال محدّد (فوراً) أو عداد
        # الحيرة ≥ 2 ⇒ شرح رياضي **مباشر حتمي** (من التمرين الرسمي، history=None،
        # صفر LLM) يكسر حلقة الكاروسيل. يقع **قبل** _build_calculated_ui. topic-safe:
        # _build_probability_direct_explanation يُرجِع None لغير الاحتمالات.
        # ─────────────────────────────────────────────────────────────────────
        # D-127 — المعمارية الإدراكية العصبية-الرمزية (الطبقة 1: فهم → مفهوم):
        # نُشخّص المفهوم (حتمي أولاً، LLM محروس عند unknown في سياق احتمالات فقط)،
        # ثم نبني استجابة مدفوعة بالمفهوم + تصعيد سقراطي مضاد للتكرار (الطبقة 4).
        # كل صياغات «البسط/14» → numerator → تعريف؛ نفس المفهوم مرّتين → سؤال سقراطي.
        # D-125: المفاهيمي/المقارنة لا يزال مدعوماً عبر concept=ratio.
        _conceptual = self._detect_conceptual_question(question)
        _subpart = self._detect_subpart_question(question)
        _confusion_count = self._count_probability_confusion(question, history_messages)

        from app.services.skills.concept_diagnosis_skill import ConceptDiagnosisSkill

        _det = ConceptDiagnosisSkill.diagnose_deterministic(question)
        _concept = _det.concept
        _misconception = _det.misconception
        _history_text = " ".join(
            str(m.get("content", "")) for m in (history_messages or []) if isinstance(m, dict)
        )
        # الطبقة 1 LLM فقط عند unknown + سياق احتمالات (لا هدر على غير الاحتمالات).
        if _concept == "unknown" and self._is_prob_context(question + " " + _history_text):
            with contextlib.suppress(Exception):
                from app.services.skills.concept_diagnosis_skill import (
                    ConceptDiagnosisInput,
                    get_concept_diagnosis_skill,
                )

                _diag = await get_concept_diagnosis_skill().diagnose(
                    ConceptDiagnosisInput(question=question, history=history_messages)
                )
                _concept = _diag.concept
                _misconception = _diag.misconception
        # حيرة عامة بلا مفهوم محدّد ⇒ full_solution (مع تصعيد سقراطي عند التكرار).
        if _concept == "unknown" and _confusion_count >= 2:
            _concept, _misconception = "full_solution", "none"

        # D-133: حالة الطالب (نيّة + إحباط) — إشارة قرار تُغيّر نوع الرد + ميزانية السقراطية.
        # حتمي أولاً (رخيص)؛ LLM ثانوي **فقط** عند primary=unknown + سياق احتمالات (نقد المالك 2،
        # لا هدر LLM على غير الاحتمالات — يُحاكي بوّابة concept_diagnosis).
        from app.services.skills.student_state_skill import (
            StudentStateInput,
            get_student_state_skill,
        )

        _state = get_student_state_skill().read(
            StudentStateInput(question=question, history=history_messages)
        )
        if _state.primary_intent == "unknown" and self._is_prob_context(
            question + " " + _history_text
        ):
            with contextlib.suppress(Exception):
                _state = await get_student_state_skill().read_or_classify(
                    StudentStateInput(question=question, history=history_messages)
                )
        try:  # BKT/الإتقان هي السلطة (نقد 2): support_level من context (D-104/D-126).
            _sup_level = int((context or {}).get("support_level") or 5)
        except (TypeError, ValueError):
            _sup_level = 5

        # ISS-122 (D-155): أول طلب مساعدة عام («كيف افهم للتمرين»/«من أين أبدأ»)
        # في سياق احتمالات وقبل أي خطوة تدريس ⇒ probe تشخيصي حتمي (كان يسقط
        # للـ LLM fallback العام فيُنتج جملة عامة بلا تشخيص).
        _first_help = (
            self._is_first_help_request(question)
            and self._is_prob_context(question + " " + _history_text)
            and not self._has_prior_tutoring_step(history_messages)
        )

        if (
            _concept != "unknown"
            or _conceptual
            or _subpart is not None
            or _confusion_count >= 2
            or _state.primary_intent in ("example_request", "procedure")
            or _first_help
            # D-135: إجابة قصيرة وسط حوار تمرين ⇒ ادخل ليُقيّمها محرّك حالة الفهم (اعتراف+تقدّم).
            or self._is_short_answer_in_dialogue(question, history_messages)
        ):
            # D-127: الاستجابة المدفوعة بالمفهوم أولاً؛ fallback إلى منطق D-124/D-125.
            _direct = None
            # ISS-122 (D-155): سؤال مفاهيمي («العلاقة/لماذا/الفرق») ⇒ شرح العلاقة
            # (D-125) مباشرةً — لا يعالجه محرّك حالة الفهم ولا السياسة (كانا
            # يختطفانه لتمثيل مكرَّر). قاعدة D-125: الفحص المفاهيمي يسبق كل شيء.
            if _conceptual:
                _direct = self._build_probability_direct_explanation(question, history_messages)
            # ISS-122 (D-155): «التشخيص قبل الشرح» — أول طلب مساعدة ⇒ سؤال تشخيصي
            # واحد بلا أي قيم محسوبة، ثم ننتظر محاولة الطالب.
            if _direct is None and _first_help:
                with contextlib.suppress(Exception):
                    _fh_combo = self._load_canonical_combinations(question, history_messages)
                    if _fh_combo is not None:
                        _direct = self._build_diagnostic_probe(_fh_combo)
                        from app.services.skills.tutor_metrics import record_response_mode

                        record_response_mode("diagnostic_probe")
            # D-135: محرّك حالة الفهم (Learning State) — الأولوية: يُجيب الفجوة المعرفية المحدّدة،
            # يتقدّم على برهان الفهم، ويُصعّد التمثيل استباقياً (لا تكرار دلالي). الأرقام من المحرك
            # الرمزي (combo)، صفر LLM. يحلّ الكارثة: «كيف وصلنا ل 10»⇒kc_combination، «لماذا قسمنا
            # على 3!»⇒kc_factorial (بلا رقم)، «لم أفهم»×2⇒تمثيل مختلف لا تكرار، إجابة⇒اعتراف+تقدّم.
            # ISS-122 (D-155): مُقيَّد بـ `_direct is None` — المفاهيمي/probe التشخيص لهما الأولوية.
            with contextlib.suppress(Exception):
                _us_combo = (
                    self._load_canonical_combinations(question, history_messages)
                    if _direct is None
                    else None
                )
                if _us_combo is not None:
                    from app.services.skills.tutor_metrics import (
                        record_progress,
                        record_understanding,
                    )
                    from app.services.skills.understanding_state_skill import (
                        get_understanding_state_skill,
                    )

                    # D-159 (WP-C): الحالة الدائمة (tutor_state.kc_progress) هي سلطة حالة
                    # المكوّنات — تقاعد إعادة البناء من مسح النصّ (يبقى fallback).
                    _us_kcp = (
                        tutor_state.get("kc_progress") if isinstance(tutor_state, dict) else None
                    )
                    _us_kcp = _us_kcp if isinstance(_us_kcp, dict) else {}
                    _us = get_understanding_state_skill().decide(
                        question=question,
                        history=history_messages,
                        combo=_us_combo,
                        intent=_state.primary_intent,
                        frustration=_state.frustration,
                        kc_progress=_us_kcp,
                    )
                    if _us is not None and _us.text:
                        _direct = _us.text
                        record_understanding(_us.kc_id, _us.action)
                        record_progress(
                            "advanced"
                            if _us.action in ("advance", "mastered")
                            else ("re_represented" if _us.action == "re_represent" else "explained")
                        )
                        logger.info(
                            "understanding_state",
                            extra={
                                "kc": _us.kc_id,
                                "action": _us.action,
                                "representation_level": _us.representation_level,
                            },
                        )
                        # D-159 (WP-C): كتابة قرار المحرّك في الحالة الدائمة — المكوّن
                        # المُبرهَن يصير understood والمشروح explained (دلتا kc_progress
                        # يحفظها customer_chat عبر record_turn). fail-open مطلق.
                        with contextlib.suppress(Exception):
                            from app.services.skills.kc_progress_schema import parse_kc_entry

                            _us_delta = (
                                tutor_state.setdefault("kc_progress_delta", {})
                                if isinstance(tutor_state, dict)
                                else {}
                            )
                            if isinstance(_us_delta, dict):
                                if _us.understood_kc_id:
                                    _u_entry = parse_kc_entry(_us_kcp.get(_us.understood_kc_id))
                                    _u_entry.state = "understood"
                                    _u_entry.evidence = "verified"
                                    _u_entry.attempts += 1
                                    _us_delta[_us.understood_kc_id] = _u_entry.to_dict()
                                if _us.kc_id and _us.kc_id != _us.understood_kc_id:
                                    _t_entry = parse_kc_entry(_us_kcp.get(_us.kc_id))
                                    if _t_entry.state == "not_addressed":
                                        _t_entry.state = "explained"
                                    _t_entry.attempts += 1
                                    _t_entry.mark_delivered(f"rep{_us.representation_level}")
                                    _us_delta[_us.kc_id] = _t_entry.to_dict()
            # D-133: النيّة تُحدّد نوع الرد قبل السياسة (إشارة قرار، لا تصنيف):
            #   example_request ⇒ مثال قبل النظرية؛ procedure ⇒ خطوات رمزية متدرّجة.
            if _direct is None and _state.primary_intent in ("example_request", "procedure"):
                from app.services.skills.tutor_metrics import record_response_mode

                if _state.primary_intent == "example_request":
                    _direct = self._build_concrete_example(question, history_messages)
                    if _direct:
                        record_response_mode("example_first")
                else:  # procedure — ISS-121 (D-154): سُلّم لا تفريغ
                    # «كيف» تدخل السُّلّم من خطوة البسط **المنتهية بسؤال** («كم عدد
                    # كل الطرق؟») — التفريغ الكامل (`_build_symbolic_reveal`) محجوز
                    # حصراً لإنقاذ استنفاد الميزانية (D-129). القانون الرابع:
                    # «التلميح قبل الحل» + مقياس roadmap §7 (صفر كشف للنتيجة).
                    _proc_combo = self._load_canonical_combinations(question, history_messages)
                    if _proc_combo is not None:
                        # ISS-122 (D-155): «التشخيص قبل الشرح» — أول طلب إجراء في
                        # التمرين يتلقى probe تشخيصياً واحداً (صفر قيم محسوبة) ثم
                        # ننتظر محاولة الطالب؛ الخطوة المحسوبة بعد أول تفاعل فقط.
                        if not self._has_prior_tutoring_step(history_messages):
                            _direct = self._build_diagnostic_probe(_proc_combo)
                            record_response_mode("diagnostic_probe")
                        else:
                            _direct = self._build_symbolic_step(_proc_combo, None)
                            record_response_mode("steps")
            if _direct is None and _concept != "unknown":
                # D-129: محرّك السياسة التربوية (الطبقة 4) يقرّر التدخّل: تعريف →
                # سؤال سقراطي محدود → اعتراف + تقدّم → حلّ رمزي عند نفاد الميزانية.
                # يكسر الاستجواب اللانهائي ويعترف بإجابات الطالب.
                from app.services.skills.pedagogical_policy_skill import (
                    PolicyInput,
                    get_pedagogical_policy_skill,
                )

                _policy = get_pedagogical_policy_skill().decide(
                    PolicyInput(
                        concept=_concept,
                        misconception=_misconception,
                        question=question,
                        history=history_messages,
                        # D-133: إشارة القرار — النيّة + الإحباط + الإتقان (BKT) تُغيّر التدخّل.
                        intent=_state.primary_intent,
                        frustration=_state.frustration,
                        support_level=_sup_level,
                    )
                )
                _ack = "إجابتك في الطريق الصحيح — " if _policy.acknowledge else ""
                if _policy.action == "symbolic_reveal":
                    # D-129: الإنقاذ التربوي الحتمي بعد استنفاد السقراطية.
                    _direct = self._build_symbolic_reveal(
                        question, history_messages, acknowledge=_policy.acknowledge
                    )
                elif _policy.action == "socratic":
                    # D-128: سرد سقراطي مُولَّد فريد (محروس)؛ اعتراف بإجابة الطالب.
                    with contextlib.suppress(Exception):
                        _narr = await self._generate_socratic_narrative(
                            _concept, _misconception, question, history_messages
                        )
                        if _narr:
                            _direct = (_ack + _narr) if _ack else _narr
                    if not _direct:  # fallback: قالب حتمي
                        _det = self._build_cognitive_response(
                            _concept, _misconception, question, history_messages
                        )
                        if _det:
                            _direct = (_ack + _det) if _ack else _det
                else:  # definition
                    _direct = self._build_cognitive_response(
                        _concept, _misconception, question, history_messages
                    )
                logger.info(
                    "pedagogical_policy",
                    extra={
                        "concept": _concept,
                        "action": _policy.action,
                        "acknowledge": _policy.acknowledge,
                        "socratic_count": _policy.socratic_count,
                        # D-133: إشارة القرار — يُثبت أن النيّة/الإحباط غيّرا البيداغوجيا.
                        "intent": _state.primary_intent,
                        "frustration": _state.frustration,
                        "response_mode": _policy.response_mode,
                    },
                )
            # F4 (D-160/ISS-126): نفس نيّة «اشرح اشتقاق هذه القيمة» في الكتلة القديمة
            # (defense-in-depth: لو عمل هذا المسار — cognitive_turn مُعطَّل أو أرجع None —
            # يظلّ «كيف حسبنا 4» يُعلّم اشتقاق الحمراء بدل الاشتقاق الكامل العام).
            if not _direct:
                with contextlib.suppress(Exception):
                    _sc_combo = self._load_canonical_combinations(question, history_messages)
                    _sc_part = (
                        self._detect_step_explanation(question, _sc_combo)
                        if _sc_combo is not None
                        else None
                    )
                    if _sc_part is not None:
                        _direct = self._build_probability_direct_explanation(
                            question, history_messages, forced_subpart=_sc_part
                        )
            if not _direct:
                _direct = self._build_probability_direct_explanation(question, history_messages)
            # ISS-120 (D-153): حارس التكرار على مسار محرّك حالة الفهم — كان هذا
            # المسار يتجاوز `_recently_emitted` و`last_step_emitted` فيبثّ نفس
            # التمثيل («تخيّل أنك سحبت 3 كرات…») حرفياً كل دور («لم أفهم»×2 ⇒
            # نفس النص). عند التكرار ⇒ تصعيد للحلّ الرمزي المتدرّج؛ وإن كان هو
            # الآخر مكرَّراً ⇒ إسقاط النص فيتولّى الكاروسيل/المسار التالي.
            if _direct:
                with contextlib.suppress(Exception):
                    _d153_ts = (
                        (context or {}).get("tutor_state") if isinstance(context, dict) else None
                    )
                    _d153_last = (
                        str(_d153_ts.get("last_step_emitted") or "")
                        if isinstance(_d153_ts, dict)
                        else ""
                    )

                    def _d153_dup(t: str) -> bool:
                        return self._recently_emitted(t, history_messages) or (
                            _d153_last and self._near_dup(t, _d153_last)
                        )

                    if _d153_dup(_direct):
                        # ISS-121 (D-154): سلسلة بدائل — أول غير مكرَّر يُبثّ؛ وإلا
                        # يسقط النص فيتولّى الكاروسيل/المسار التالي. صفر بثّ مكرَّر.
                        # ISS-122 (D-155): «الخطوة التالية غير المُجابة» أولاً (من
                        # السؤال المعلّق) والإنقاذ الكامل (reveal superset) أخيراً.
                        _lad_combo = self._load_canonical_combinations(question, history_messages)
                        _lad_pending = self._pending_focus_from_history(history_messages)
                        _lf, _ls = (
                            ("ratio", "numerator")
                            if _lad_pending == "denominator"
                            else ("numerator", "ratio")
                        )
                        _alts: tuple[str | None, ...] = (
                            (
                                self._build_symbolic_step(_lad_combo, _lf)
                                if _lad_combo is not None
                                else None
                            ),
                            (
                                self._build_symbolic_step(_lad_combo, _ls)
                                if _lad_combo is not None
                                else None
                            ),
                            "أنت تملك الآن كل المعطيات — جرّب بنفسك: ركّب البسط على "
                            "المقام، وأخبرني ما قيمة P(A) التي حصلت عليها، وسأخبرك إن أصبت.",
                            self._build_symbolic_reveal(question, history_messages),
                        )
                        _direct = None
                        for _cand in _alts:
                            if _cand and not _d153_dup(_cand):
                                _direct = _cand
                                break
            if _direct:
                logger.info(
                    "probability_direct_explanation_escape_hatch",
                    extra={
                        "request_id": str(uuid.uuid4()),
                        "concept": _concept,
                        "misconception": _misconception,
                        "subpart": _subpart or "",
                        "confusion_count": _confusion_count,
                        "reason": (
                            f"concept:{_concept}"
                            if _concept != "unknown"
                            else (
                                "conceptual_question"
                                if _conceptual
                                else ("subpart_question" if _subpart else "repeated_confusion")
                            )
                        ),
                    },
                )
                _direct_chars = 0
                try:
                    async for _chunk in self._stream_markdown_typing(_direct):
                        if not _chunk:
                            continue
                        _direct_chars += len(_chunk)
                        yield self._normalize_stream_event(
                            {"type": "assistant_delta", "payload": {"content": _chunk}}
                        )
                except Exception:
                    logger.warning("probability_direct_explanation_stream_failed", exc_info=True)
                if _direct_chars > 0:
                    if _root_ctx:
                        with contextlib.suppress(Exception):
                            obs.end_span(
                                _root_ctx.span_id,
                                status="OK",
                                metrics={
                                    "duration_ms": (time.perf_counter() - _t0) * 1000,
                                    # بين preempt (0.5) والكاروسيل المحسوب
                                    "fallback_path": 0.45,
                                    "stream_chars": float(_direct_chars),
                                },
                            )
                    yield self._normalize_stream_event(
                        {"type": "assistant_final", "payload": {"content": ""}}
                    )
                    return
                # إن فشل البث (نادر) → نُكمل إلى الكاروسيل العادي أدناه

        # ─────────────────────────────────────────────────────────────────────
        # Generative UI Streaming (probability tree / impossible_case):
        # عند طلب يتضمن شجرة احتمالات، نبثّ حدث ui_component فوراً (incremental).
        #
        # V28.0 — قانون الكبح النصي (Text-Wall Muzzle):
        # إذا كان المكوّن impossible_draw_animation (terminate_pipeline=True)،
        # نبثّ المكوّن + companion_text (جملة واحدة ≤ 120 حرف) ثم نُنهي المسار
        # فوراً — لا LLM، لا شجرة، لا synthesizer، لا جدار نص.
        # للمكوّنات الأخرى (probability_tree / combinations_visualizer): نسقط
        # للمسار النصي العادي كما كان (لا return).
        # ─────────────────────────────────────────────────────────────────────
        # D-078 (V19.0 → V28.0): الموجِّه التربوي يختار المكوّن الصحيح.
        # كاشف الإحباط (مفهمتش/كيفاش) يُفعِّل الأداة بصرياً عبر سياق المحادثة.
        # V38.0: hoisted so the fallback chain can read the routing decision
        # even when _ui_event is None (no probability context detected).
        _is_mode_b: bool = False

        try:
            _ui_event = self._build_calculated_ui(question, history_messages=history_messages)
        except Exception:
            _ui_event = None

        if _ui_event is not None:
            # ─────────────────────────────────────────────────────────────────
            # Protocol V38.0 — Dual-Mode Routing (replaces V34.0 Contextual Unmuzzle)
            # ─────────────────────────────────────────────────────────────────
            # _build_calculated_ui already encoded the routing decision:
            #   MODE_A → terminate_pipeline=True  (direct question, muzzle after UI)
            #   MODE_B → terminate_pipeline=False (confusion, keep pipeline alive)
            #
            # We read the decision directly from the event — no second confusion
            # check needed here. This keeps the routing logic in one place.
            _routing_mode = _ui_event.get("routing_mode", "MODE_A")
            _is_mode_b = _routing_mode == "MODE_B"  # hoisted — readable by fallback chain
            # terminate_pipeline is already False for MODE_B (set in _build_calculated_ui)
            _is_impossible = _ui_event.get("terminate_pipeline") is True

            logger.info(
                "generative_ui_emit",
                extra={
                    "request_id": str(uuid.uuid4()),
                    "component": _ui_event.get("component"),
                    "routing_mode": _routing_mode,
                    "terminate_pipeline": _is_impossible,
                    "question_len": len(question),
                },
            )
            yield self._normalize_stream_event({"type": "ui_component", "payload": _ui_event})

            # MODE_A — Text-Wall Muzzle: terminate immediately after UI component.
            # Emit companion_text (≤ 120 chars) as the sole text output, then return.
            # MODE_B falls through to the LLM path below for deep pedagogical narrative.
            if _is_impossible:
                _companion = str(
                    _ui_event.get("companion_text")
                    or "إليك تفصيل التمرين في واجهتك التفاعلية الخيالية أدناه 🪄"
                )
                yield self._normalize_stream_event(
                    {"type": "assistant_delta", "payload": {"content": _companion}}
                )
                yield self._normalize_stream_event(
                    {"type": "assistant_final", "payload": {"content": ""}}
                )
                if _root_ctx:
                    with contextlib.suppress(Exception):
                        obs.end_span(
                            _root_ctx.span_id,
                            status="OK",
                            metrics={
                                "duration_ms": (time.perf_counter() - _t0) * 1000,
                                "fallback_path": 0.1,
                                "stream_chars": float(len(_companion)),
                            },
                        )
                return
            # MODE_B: UI emitted, pipeline continues — LLM will provide deep narrative.
            if _is_mode_b:
                logger.info(
                    "deep_pedagogy_mode_active",
                    extra={"component": _ui_event.get("component"), "question_len": len(question)},
                )

        # ─────────────────────────────────────────────────────────────────────
        # ISS-058 (D-052 — Explanation-with-Context):
        # عند طلب شرح/استفسار مرتبط بتمرين بكالوريا (صريحاً أو ضمن السياق).
        #
        # ISS-059 (D-053): نحسب القرار **مرة واحدة** ونمرِّره للـ stream
        # بدل إعادة حسابه — يوفِّر ~10-20ms + file I/O مكرَّر.
        #
        # D-103: افتراضياً نمرّر الشرح عبر orchestrator (الرسم الـ13-node) مع
        # **حقن** محتوى التمرين الدقيق في context — الرسم يتجاوز retriever-ه
        # كلياً ويستخدم المحقون كمصدر وحيد، فيُحيَّد سبب منع D-052 الأصلي
        # (خلط تمارين vector DB + tags خام) بالبناء. الشرح المحلي يبقى fallback
        # كاملاً. رافعة رجوع فورية: EXPLANATION_VIA_ORCHESTRATOR=0.
        # ─────────────────────────────────────────────────────────────────────
        _explanation_decision = detect_explanation_with_context(
            ExerciseRetrievalRequest(question=question),
            history_messages=history_messages,
        )
        _exercise_injection: dict[str, str] = {}
        if _explanation_decision.recognized and _explanation_decision.matched_entry is not None:
            logger.info(
                "explanation_context_preempt reason=%s matched_file=%s history_len=%s",
                _explanation_decision.reason,
                _explanation_decision.matched_entry.file_path,
                len(history_messages or []),
                extra={
                    "request_id": str(uuid.uuid4()),
                    "reason": _explanation_decision.reason,
                    "matched_file": _explanation_decision.matched_entry.file_path,
                },
            )
            _exp_full_content = str(getattr(_explanation_decision, "full_content", "") or "")
            if self._explanation_via_orchestrator_enabled() and _exp_full_content.strip():
                # D-103: حقن المحتوى والمتابعة إلى orchestrator — لا بثّ محلي هنا.
                _exercise_injection = {
                    "exercise_content": _exp_full_content,
                    "exercise_ref": str(_explanation_decision.matched_entry.file_path),
                }
                logger.info(
                    "explanation_via_orchestrator file=%s chars=%s",
                    _explanation_decision.matched_entry.file_path,
                    len(_exp_full_content),
                )
            else:
                exp_streamed_chars = 0
                try:
                    async for chunk in self._stream_exercise_explanation_response(
                        question=question,
                        conversation_id=conversation_id,
                        history_messages=history_messages,
                        precomputed_decision=_explanation_decision,  # ISS-059
                    ):
                        if not chunk:
                            continue
                        exp_streamed_chars += len(chunk)
                        yield self._normalize_stream_event(
                            {"type": "assistant_delta", "payload": {"content": chunk}}
                        )
                except Exception:
                    logger.warning("explanation_context_preempt_failed", exc_info=True)

                if exp_streamed_chars > 0:
                    if _root_ctx:
                        with contextlib.suppress(Exception):
                            obs.end_span(
                                _root_ctx.span_id,
                                status="OK",
                                metrics={
                                    "duration_ms": (time.perf_counter() - _t0) * 1000,
                                    "fallback_path": 0.75,  # explanation preempt
                                    "stream_chars": float(exp_streamed_chars),
                                },
                            )
                    yield self._normalize_stream_event(
                        {"type": "assistant_final", "payload": {"content": ""}}
                    )
                    return
                # إذا فشل البث → نُكمل المسار العادي

        # V38.0 — Deep Pedagogy Mode (MODE_B): inject Socratic instruction.
        # Rules (D-067): prompt < 1000 chars, no box-drawing chars, no LaTeX in prompt.
        # The instruction is prepended to the question so the LLM receives it as
        # user intent — not as a system override that triggers reasoning mode.
        _deep_pedagogy_instruction = (
            "[وضع الشرح العميق] "
            "الطالب يعبّر عن حيرة. ابدأ بالمعنى والصورة الذهنية قبل أي صيغة. "
            "استخدم أسلوباً سقراطياً دافئاً. "
            "لا تبدأ بـ LaTeX أو رموز رياضية. "
            "اشرح لماذا يحدث هذا قبل كيف يُحسب."
        )
        _effective_question = (
            _deep_pedagogy_instruction + "\n\n" + question if _is_mode_b else question
        )

        # D-117 (فصل الطبقات: الطالب يرى التعليم لا هندسة التعليم): التوجيه التربوي
        # (D-104) لم يَعُد يُسبَق للسؤال. كان النموذج المجاني يُردّده حرفياً
        # («[توجيه تربوي] ... مستوى الدعم: ...») فيرى الطالب «هندسة التعليم» لا
        # التعليم. عمق التدريس يصل الآن عبر `support_level` (مُمرَّر في context →
        # يستهلكه SynthesizerNode في الرسم). التوجيه يبقى في context للقياس فقط
        # (يصل ضمن `**(context or {})` في الـ payload) — لا يُسبَق للسؤال أبداً.

        # D-114: support_level يحكم إعفاء الحجب (sanitize_final_text). الافتراض
        # الآمن = 5 (محجوب كلياً) عند الغياب/الخطأ — لا 1 (fail-closed).
        try:
            _support_level = int((context or {}).get("support_level") or 5)
        except (TypeError, ValueError):
            _support_level = 5
        if _support_level < 1 or _support_level > 5:
            _support_level = 5

        payload = {
            "question": _effective_question,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "history_messages": history_messages or [],
            "context": {
                **(context or {}),
                "routing_mode": "MODE_B" if _is_mode_b else "MODE_A",
                # D-103: محتوى التمرين المحقون (إن وُجد) — الرسم يستهلكه بدل retriever-ه
                **_exercise_injection,
            },
        }

        routing_policy = ChatRoutingPolicy.from_environment(self.base_url)
        candidate_urls = routing_policy.candidate_urls()
        client = await self._get_client()
        request_id = str(uuid.uuid4())
        connection_errors: list[str] = []
        contract_version = routing_policy.contract_version
        fallback_enabled = routing_policy.fallback_enabled

        # تسجيل وضع التوجيه كـ gauge قابل للقياس في Grafana :3001
        # cogniforge_routing_mode_state_graph: 1 = StateGraph, 0 = Agent
        # cogniforge_routing_target_total{target=...}: عداد تراكمي لكل هدف
        try:
            _obs_routing = obs
            _obs_routing.record_metric(
                "routing.mode.state_graph",
                1.0 if routing_policy.targets_state_graph else 0.0,
                labels={"endpoint_mode": routing_policy.endpoint_mode},
            )
            _obs_routing.record_metric(
                "routing.target.total",
                1.0,
                labels={"target": routing_policy.endpoint_mode},
            )
        except Exception:
            pass

        logger.info(
            "chat_contract_route_start",
            extra={
                "request_id": request_id,
                "contract_version": contract_version,
                "candidate_count": len(candidate_urls),
                "fallback_enabled": fallback_enabled,
                "endpoint_mode": routing_policy.endpoint_mode,
                "targets_state_graph": routing_policy.targets_state_graph,
            },
        )

        # توليد JWT داخلي لمصادقة الـ monolith مع orchestrator-service
        # يُجدَّد مع كل طلب لضمان عدم انتهاء الصلاحية
        try:
            service_token = self._build_service_jwt(user_id)
            auth_headers = {
                "Authorization": f"Bearer {service_token}",
                "X-Correlation-ID": request_id,
                "X-Service-Source": "cogniforge-monolith",
            }
        except Exception as jwt_err:
            logger.warning("service_jwt_generation_failed: %s", jwt_err)
            auth_headers = {"X-Correlation-ID": request_id}

        for candidate_url in candidate_urls:
            try:
                logger.info(
                    "chat_routing_attempt",
                    extra={"candidate_url": candidate_url, "request_id": request_id},
                )
                response: httpx.Response | None = None

                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(1),
                    wait=wait_exponential(multiplier=1, min=1, max=4),
                    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
                    reraise=True,
                ):
                    with attempt:
                        request = client.build_request(
                            "POST", candidate_url, json=payload, headers=auth_headers
                        )
                        response = await client.send(request, stream=True)

                if response is None:
                    continue

                try:
                    response.raise_for_status()
                    # D-103: حارس البثّ الفارغ — orchestrator أجاب 200 لكن لم يبثّ
                    # أي محتوى مرئي ولا إطاراً نهائياً ⇒ نعامله كفشل ونُكمل للمرشح
                    # التالي / الـ fallback المحلي بدل إنهاء الدور فارغاً.
                    _orch_visible = False
                    # ISS-114 (D-106): الثغرة الكبرى — بثّ orchestrator HTTP كان
                    # يصل للطالب بلا حارس (غارباج لاتيني + HTML). نلفّه بمرشّح
                    # نزاهة المحتوى على كامل التيار. fail-open: None = سلوك اليوم.
                    _integrity = None
                    try:
                        from app.services.skills.content_integrity_skill import (
                            StreamIntegrityFilter,
                            sanitize_final_text,
                        )

                        _integrity = StreamIntegrityFilter()
                    except Exception:  # pragma: no cover - fail-open على مستوى التوصيل
                        _integrity = None
                        sanitize_final_text = None  # type: ignore[assignment]
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            parsed_line = json.loads(line)
                            normalized = self._normalize_stream_event(parsed_line)
                            _ntype = (
                                normalized.get("type") if isinstance(normalized, dict) else None
                            )
                            if _ntype == "assistant_delta":
                                _ncontent = (normalized.get("payload") or {}).get("content")
                                if isinstance(_ncontent, str) and _ncontent:
                                    # عقد empty_stream (D-103 rule 4): يُحسَب من
                                    # المحتوى الخام قبل الفلترة.
                                    _orch_visible = True
                                    if _integrity is not None:
                                        cleaned = _integrity.feed(_ncontent)
                                        if not cleaned:
                                            continue  # المرشّح حجز/حذف هذه القطعة
                                        normalized["payload"]["content"] = cleaned
                            elif _ntype == "assistant_final":
                                _orch_visible = True
                                if sanitize_final_text is not None:
                                    _fc = (normalized.get("payload") or {}).get("content")
                                    if isinstance(_fc, str) and _fc:
                                        # D-114: support_level==1 يُعفي كتلة المثال
                                        # المحلول الملفوفة بالفواصل من الحجب.
                                        normalized["payload"]["content"] = sanitize_final_text(
                                            _fc, _support_level
                                        )
                            elif _ntype in ("assistant_error", "error", "complete"):
                                _orch_visible = True
                            yield normalized
                        except json.JSONDecodeError:
                            recovered = self._recover_structured_event(line)
                            if recovered is not None:
                                _orch_visible = True
                                yield self._normalize_stream_event(recovered)
                            else:
                                logger.warning(f"Received non-JSON line from agent: {line[:50]}...")
                                _orch_visible = True
                                yield self._normalize_stream_event(line)
                    # ISS-114: إفراغ ذيل المرشّح المحجوز (صفر فقدان bytes).
                    if _integrity is not None:
                        _tail = _integrity.flush()
                        if _tail:
                            yield {"type": "assistant_delta", "payload": {"content": _tail}}
                    if _orch_visible:
                        return
                    connection_errors.append(f"{candidate_url} => empty_stream")
                    logger.warning(
                        "chat_routing_empty_stream",
                        extra={"request_id": request_id, "candidate_url": candidate_url},
                    )
                finally:
                    await response.aclose()

            except Exception as e:
                connection_errors.append(f"{candidate_url} => {e}")
                logger.error(
                    "chat_routing_failed",
                    exc_info=True,
                    extra={"request_id": request_id, "candidate_url": candidate_url},
                )

        diagnostic = " | ".join(connection_errors) if connection_errors else "No endpoint attempted"
        logger.error(
            "Failed to chat with agent across all endpoints", extra={"diagnostic": diagnostic}
        )

        # ─────────────────────────────────────────────────────────────────────
        # D-112 (2026-06-13): العمود الفقري الإلزامي — الخدمات المصغرة + الرسم
        # الـ13-node هي القلب الوحيد. عند تعذّرها لا نسقط بصمت إلى local_graph
        # الضعيف؛ بل نُصدِر خطأً صريحاً («runtime truth over synthetic certainty»).
        # علم REQUIRE_ORCHESTRATOR=1 افتراضي مُفعَّل؛ =0 يُعيد الـ fallback القديم
        # (rollback بلا deploy — نمط D-025).
        # ─────────────────────────────────────────────────────────────────────
        _require_orch = os.environ.get("REQUIRE_ORCHESTRATOR", "1").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if _require_orch:
            logger.error(
                "orchestrator_required_hard_fail",
                extra={"request_id": request_id, "diagnostic": diagnostic},
            )
            with contextlib.suppress(Exception):
                obs.record_metric(
                    "routing.target.total",
                    1.0,
                    labels={"target": "orchestrator_required_error"},
                )
            if _root_ctx:
                with contextlib.suppress(Exception):
                    obs.end_span(
                        _root_ctx.span_id,
                        status="ERROR",
                        metrics={
                            "duration_ms": (time.perf_counter() - _t0) * 1000,
                            "hard_fail": 1.0,
                        },
                    )
            yield {
                "type": "error",
                "payload": {
                    "code": "ORCHESTRATOR_REQUIRED",
                    "message": (
                        "النظام يتطلب الخدمات الذكية المتقدمة وهي غير متاحة حالياً. "
                        "يرجى المحاولة بعد قليل."
                    ),
                },
            }
            return

        if fallback_enabled:
            # تسجيل الـ fallback المحلي كـ metric — يُظهر في Grafana أن الخدمة المصغرة غير متاحة
            with contextlib.suppress(Exception):
                obs.record_metric(
                    "routing.target.total",
                    1.0,
                    labels={"target": "local_fallback"},
                )

            _fb_t0 = time.perf_counter()
            _fb_ctx = None
            with contextlib.suppress(Exception):
                _fb_ctx = obs.start_trace(
                    "orchestrator.fallback.file_intelligence",
                    parent_context=_root_ctx,
                    tags={"fallback_step": "file_intelligence"},
                )
            local_file_count_response = await self._build_local_file_count_response(question)
            try:
                if _fb_ctx:
                    obs.end_span(
                        _fb_ctx.span_id,
                        status="OK" if local_file_count_response else "SKIP",
                        metrics={"duration_ms": (time.perf_counter() - _fb_t0) * 1000},
                    )
            except Exception:
                pass
            if local_file_count_response:
                if _root_ctx:
                    with contextlib.suppress(Exception):
                        obs.end_span(
                            _root_ctx.span_id,
                            status="OK",
                            metrics={
                                "duration_ms": (time.perf_counter() - _t0) * 1000,
                                "fallback_path": 1.0,
                            },
                        )
                yield self._normalize_stream_event(
                    {"type": "assistant_delta", "payload": {"content": local_file_count_response}}
                )
                yield self._normalize_stream_event(
                    {"type": "assistant_final", "payload": {"content": ""}}
                )
                return

            # ── Exercise retrieval — STREAMING path (D-048) ──
            # يبث محتوى التمرين المُسترجَع كلمة بكلمة بدل dump واحد كبير.
            # ISS-051: المسار القديم كان يُرسل النص الكامل في assistant_delta
            # واحد → لا typing-effect. الآن نُقسّم على حدود الأسطر/الكلمات.
            _ret_t0 = time.perf_counter()
            _ret_ctx = None
            with contextlib.suppress(Exception):
                _ret_ctx = obs.start_trace(
                    "orchestrator.fallback.exercise_retrieval.stream",
                    parent_context=_root_ctx,
                    tags={"fallback_step": "exercise_retrieval_stream"},
                )
            ret_streamed_any = False
            ret_streamed_chars = 0
            try:
                async for chunk in self._stream_local_retrieval_response(
                    question, history_messages
                ):
                    if not chunk:
                        continue
                    ret_streamed_any = True
                    ret_streamed_chars += len(chunk)
                    yield self._normalize_stream_event(
                        {"type": "assistant_delta", "payload": {"content": chunk}}
                    )
            except Exception:
                logger.warning("local_retrieval_stream_yield_failed", exc_info=True)

            try:
                if _ret_ctx:
                    obs.end_span(
                        _ret_ctx.span_id,
                        status="OK" if ret_streamed_any else "SKIP",
                        metrics={
                            "duration_ms": (time.perf_counter() - _ret_t0) * 1000,
                            "stream_chars": float(ret_streamed_chars),
                        },
                    )
            except Exception:
                pass

            if ret_streamed_any:
                if _root_ctx:
                    with contextlib.suppress(Exception):
                        obs.end_span(
                            _root_ctx.span_id,
                            status="OK",
                            metrics={
                                "duration_ms": (time.perf_counter() - _t0) * 1000,
                                "fallback_path": 2.0,
                                "stream_chars": float(ret_streamed_chars),
                            },
                        )
                yield self._normalize_stream_event(
                    {"type": "assistant_final", "payload": {"content": ""}}
                )
                return

            # ── Exercise explanation with context — ISS-053 ──────────────────
            # يشرح تمرين بكالوريا محدد بالاعتماد على محتواه الكامل (نص + إجابة نموذجية).
            # يحل هلوسة LangGraph عند "اشرح تمرين الدوال العددية 2016".
            # يُدرَج قبل LangGraph لأنه أدق وأكثر موثوقية للتمارين المعروفة.
            _exp_t0 = time.perf_counter()
            _exp_ctx = None
            with contextlib.suppress(Exception):
                _exp_ctx = obs.start_trace(
                    "orchestrator.fallback.exercise_explanation.stream",
                    parent_context=_root_ctx,
                    tags={"fallback_step": "exercise_explanation_stream"},
                )
            exp_streamed_any = False
            exp_streamed_chars = 0
            try:
                async for chunk in self._stream_exercise_explanation_response(
                    question=question,
                    conversation_id=conversation_id,
                    history_messages=history_messages,
                    # ISS-059 + D-103: القرار محسوب مسبقاً في بداية chat_with_agent —
                    # لا إعادة كشف ولا file I/O مكرَّر في مسار الـ fallback.
                    precomputed_decision=(
                        _explanation_decision
                        if (
                            _explanation_decision.recognized
                            and _explanation_decision.matched_entry is not None
                        )
                        else None
                    ),
                ):
                    if not chunk:
                        continue
                    exp_streamed_any = True
                    exp_streamed_chars += len(chunk)
                    yield self._normalize_stream_event(
                        {"type": "assistant_delta", "payload": {"content": chunk}}
                    )
            except Exception:
                logger.warning("exercise_explanation_stream_yield_failed", exc_info=True)

            try:
                if _exp_ctx:
                    obs.end_span(
                        _exp_ctx.span_id,
                        status="OK" if exp_streamed_any else "SKIP",
                        metrics={
                            "duration_ms": (time.perf_counter() - _exp_t0) * 1000,
                            "stream_chars": float(exp_streamed_chars),
                        },
                    )
            except Exception:
                pass

            if exp_streamed_any:
                if _root_ctx:
                    with contextlib.suppress(Exception):
                        obs.end_span(
                            _root_ctx.span_id,
                            status="OK",
                            metrics={
                                "duration_ms": (time.perf_counter() - _t0) * 1000,
                                "fallback_path": 2.5,
                                "stream_chars": float(exp_streamed_chars),
                            },
                        )
                yield self._normalize_stream_event(
                    {"type": "assistant_final", "payload": {"content": ""}}
                )
                return

            # ── LangGraph local engine — STREAMING path (D-047) ──
            # يبث الرد كلمة بكلمة عبر assistant_delta بدل dump واحد كبير.
            _lg_t0 = time.perf_counter()
            _lg_ctx = None
            with contextlib.suppress(Exception):
                _lg_ctx = obs.start_trace(
                    "orchestrator.fallback.langgraph.stream",
                    parent_context=_root_ctx,
                    tags={
                        "fallback_step": "langgraph_stream",
                        "conversation_id": str(conversation_id),
                    },
                )
            streamed_any = False
            streamed_chars = 0
            try:
                async for chunk in self._stream_local_graph_response(
                    question=_effective_question,
                    conversation_id=conversation_id,
                    history_messages=history_messages,
                ):
                    if not chunk:
                        continue
                    streamed_any = True
                    streamed_chars += len(chunk)
                    yield self._normalize_stream_event(
                        {"type": "assistant_delta", "payload": {"content": chunk}}
                    )
            except Exception:
                logger.warning("local_graph_stream_yield_failed", exc_info=True)

            try:
                if _lg_ctx:
                    obs.end_span(
                        _lg_ctx.span_id,
                        status="OK" if streamed_any else "SKIP",
                        metrics={
                            "duration_ms": (time.perf_counter() - _lg_t0) * 1000,
                            "stream_chars": float(streamed_chars),
                        },
                    )
            except Exception:
                pass

            if streamed_any:
                if _root_ctx:
                    with contextlib.suppress(Exception):
                        obs.end_span(
                            _root_ctx.span_id,
                            status="OK",
                            metrics={
                                "duration_ms": (time.perf_counter() - _t0) * 1000,
                                "fallback_path": 3.0,
                                "stream_chars": float(streamed_chars),
                            },
                        )
                yield self._normalize_stream_event(
                    {"type": "assistant_final", "payload": {"content": ""}}
                )
                return

            # Ultimate safety net: STREAMING raw LLM call (no graph, no state) — D-047
            is_file_intelligence = self._file_intelligence_decision(question)[0]
            is_exercise_retrieval = self._exercise_retrieval_decision(question, history_messages)
            if not is_file_intelligence and not is_exercise_retrieval:
                _gc_t0 = time.perf_counter()
                _gc_ctx = None
                with contextlib.suppress(Exception):
                    _gc_ctx = obs.start_trace(
                        "orchestrator.fallback.general_chat.stream",
                        parent_context=_root_ctx,
                        tags={"fallback_step": "general_chat_stream"},
                    )
                gc_streamed_any = False
                gc_streamed_chars = 0
                try:
                    async for chunk in self._stream_local_general_chat_response(
                        _effective_question,
                        history_messages=history_messages,
                    ):
                        if not chunk:
                            continue
                        gc_streamed_any = True
                        gc_streamed_chars += len(chunk)
                        yield self._normalize_stream_event(
                            {"type": "assistant_delta", "payload": {"content": chunk}}
                        )
                except Exception:
                    logger.warning("local_general_chat_stream_yield_failed", exc_info=True)

                try:
                    if _gc_ctx:
                        obs.end_span(
                            _gc_ctx.span_id,
                            status="OK" if gc_streamed_any else "SKIP",
                            metrics={
                                "duration_ms": (time.perf_counter() - _gc_t0) * 1000,
                                "stream_chars": float(gc_streamed_chars),
                            },
                        )
                except Exception:
                    pass

                if gc_streamed_any:
                    if _root_ctx:
                        with contextlib.suppress(Exception):
                            obs.end_span(
                                _root_ctx.span_id,
                                status="OK",
                                metrics={
                                    "duration_ms": (time.perf_counter() - _t0) * 1000,
                                    "fallback_path": 4.0,
                                    "stream_chars": float(gc_streamed_chars),
                                },
                            )
                    yield self._normalize_stream_event(
                        {"type": "assistant_final", "payload": {"content": ""}}
                    )
                    return

        # All paths exhausted — record error span and yield error event
        if _root_ctx:
            with contextlib.suppress(Exception):
                obs.end_span(
                    _root_ctx.span_id,
                    status="ERROR",
                    error_message="all_fallback_paths_exhausted",
                    metrics={"duration_ms": (time.perf_counter() - _t0) * 1000},
                )
        try:
            yield self._normalize_stream_event(self._sanitize_error_for_user(request_id=request_id))
            yield self._normalize_stream_event(
                {"type": "assistant_final", "payload": {"content": ""}}
            )
        except Exception as e:
            logger.error(f"Failed to chat with agent: {e}", exc_info=True)
            yield self._normalize_stream_event(self._sanitize_error_for_user(request_id=request_id))
            yield self._normalize_stream_event(
                {"type": "assistant_final", "payload": {"content": ""}}
            )


# Singleton
orchestrator_client = OrchestratorClient()
