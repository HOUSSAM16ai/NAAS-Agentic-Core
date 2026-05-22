"""
Orchestrator Client.
Provides a typed interface to the Orchestrator Service.
Decouples the Monolith from the Overmind Orchestration Logic.
"""

from __future__ import annotations

import contextlib
import json
import logging
import time
import uuid
from ast import literal_eval
from collections.abc import AsyncGenerator

import httpx
import jwt as pyjwt
from pydantic import BaseModel
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.ai_gateway import get_ai_client
from app.core.http_client_factory import HTTPClientConfig, get_http_client
from app.core.settings.base import get_settings
from app.infrastructure.clients.routing_policy import ChatRoutingPolicy
from app.services.capabilities.exercise_retrieval import (
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
from shared.chat_protocol.chat_events import ChatEventEnvelope, ChatEventPayload, ChatEventType

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


class OrchestratorClient:
    """
    Client for interacting with the Orchestrator Service.
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
        """
        decision = detect_exercise_retrieval(
            ExerciseRetrievalRequest(question=question),
            history_messages=history_messages,
        )
        return decision.recognized and decision.matched_entry is not None

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

        # المسار المُفضَّل — مطابقة مُفهرَسة دقيقة (ملف واحد، نص نظيف)
        if decision.matched_entry is not None:
            try:
                raw_content = load_exercise_content(decision.matched_entry)
                if raw_content:
                    return format_exercise_for_display(decision.matched_entry, raw_content)
            except Exception:
                logger.warning("indexed_retrieval_failed", exc_info=True)

        # المسار البديل — wide-net search (legacy)
        try:
            from app.services.chat.tools.retrieval.service import search_educational_content

            result = await search_educational_content(query=question)
            normalized = make_exercise_result(result)
            return normalized.message
        except Exception:
            logger.warning("local_retrieval_fallback_failed", exc_info=True)
            return None

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
        if not decision.recognized or not decision.full_content:
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
                exercise_full_content=decision.full_content,
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
        import asyncio

        full_response = await self._build_local_retrieval_response(question, history_messages)
        if not full_response:
            return

        try:
            from app.telemetry.path_observer import mark_fallback_used

            mark_fallback_used("local_retrieval_stream")
        except Exception:
            pass

        # ── استراتيجية البث الذكي (ISS-STREAM-002) ──────────────────────────
        # الهدف: typing-effect سلس يحاكي LLM streaming حقيقي.
        #
        # القواعد:
        # 1. الأسطر الفارغة والفواصل (---) → تُرسَل فوراً بدون تأخير
        # 2. عناوين Markdown (# ## ###) → تُرسَل كوحدة واحدة مع تأخير متوسط
        # 3. معادلات LaTeX ($$...$$) → تُرسَل كوحدة واحدة لا تُكسَر
        # 4. الأسطر العادية → تُقسَّم كلمة بكلمة مع تأخير 8-15ms
        # 5. الجداول → تُرسَل سطراً سطراً مع تأخير قصير
        import re as _re

        _LATEX_BLOCK_RE = _re.compile(r"\$\$[^$]*?\$\$", _re.DOTALL)  # noqa: N806
        # ISS-057 (D-051): يحفظ أربع صيغ من LaTeX inline كـ token واحد:
        #   $...$ | \(...\) | \\(...\\) | حتى عبر كلمات بدون فراغ
        # تطابق بالترتيب: $$ أولاً (في حالة عابر سطر)، ثم $، ثم \\(...\\)، ثم \(...\)
        _LATEX_INLINE_RE = _re.compile(  # noqa: N806
            r"\$\$[^$\n]+?\$\$"  # $$inline$$ نادر لكن ممكن
            r"|\$[^$\n]+?\$"  # $inline$
            r"|\\\\\([^\n]+?\\\\\)"  # \\(inline\\)  — الصيغة في knowledge_base
            r"|\\\([^\n]+?\\\)"  # \(inline\)
        )

        def _split_preserving_latex(line: str) -> list[str]:
            """يُقسِّم السطر إلى tokens مع الحفاظ على وحدة رموز LaTeX.

            ISS-057: يدعم كل صيغ inline math الموجودة في `knowledge_base/`:
            `$...$`, `\\(...\\)`, و `\\\\(...\\\\)` (double-backslash التاريخية).
            بهذا، الـ frontend يستقبل LaTeX block كـ chunk كامل ولا يُكشف نصف
            delimiter للطالب.
            """
            tokens: list[str] = []
            pos = 0
            for m in _LATEX_INLINE_RE.finditer(line):
                before = line[pos : m.start()]
                if before:
                    tokens.extend(w + " " for w in before.split() if w)
                tokens.append(m.group())
                pos = m.end()
            remainder = line[pos:]
            if remainder:
                tokens.extend(w + " " for w in remainder.split() if w)
            return tokens

        lines = full_response.splitlines(keepends=True)
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # سطر فارغ أو فاصل → فوري
            if not stripped or stripped == "---":
                yield line
                i += 1
                continue

            # معادلة LaTeX أحادية السطر $$...$$ — تُرسَل كوحدة واحدة لا تُكسَر
            if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4:
                yield line
                await asyncio.sleep(0.025)
                i += 1
                continue

            # معادلة LaTeX متعددة الأسطر $$ ... $$
            if stripped.startswith("$$") and not stripped.endswith("$$"):
                block = line
                i += 1
                while i < len(lines) and "$$" not in lines[i]:
                    block += lines[i]
                    i += 1
                if i < len(lines):
                    block += lines[i]
                    i += 1
                yield block
                await asyncio.sleep(0.025)
                continue

            # عنوان Markdown
            if stripped.startswith("#"):
                yield line
                await asyncio.sleep(0.018)
                i += 1
                continue

            # سطر جدول
            if stripped.startswith("|"):
                yield line
                await asyncio.sleep(0.010)
                i += 1
                continue

            # سطر عادي — word-by-word مع الحفاظ على LaTeX
            tokens = _split_preserving_latex(stripped)
            for _j, token in enumerate(tokens):
                yield token
                # تأخير أقصر للكلمات القصيرة، أطول للرموز الرياضية
                if "$" in token:
                    await asyncio.sleep(0.020)
                elif len(token) <= 3:
                    await asyncio.sleep(0.006)
                else:
                    await asyncio.sleep(0.011)
            yield "\n"
            i += 1

    @staticmethod
    def _format_history_for_prompt(history_messages: list[dict[str, str]]) -> str:
        """يحوّل قائمة رسائل المحادثة إلى نص سياق منسّق للـ prompt."""
        lines: list[str] = []
        for msg in history_messages[-20:]:
            role = str(msg.get("role", "")).strip()
            content = str(msg.get("content", "")).replace("\x00", "").strip()
            if not content or role not in {"user", "assistant"}:
                continue
            label = "المستخدم" if role == "user" else "المساعد"
            lines.append(f"{label}: {content}")
        return "\n".join(lines)

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

    # ISS-058 (D-052 — Retrieval Chunk Tag Stripping):
    # vector DB / retriever ينتج chunks مع علامات داخلية مثل [ex: ex_1] / [sol: ex_1]
    # / [grading: ex_1] تُساعد في الفهرسة لكنها لا تنتمي لواجهة المستخدم. نُزيلها
    # قبل بثها للطالب — هذا يحدث في الـ orchestrator path قبل الـ preempt.
    _RETRIEVAL_TAG_RE = __import__("re").compile(
        r"\[(?:ex|sol|grading|chunk|src|source|meta|tag|id|doc):[^\]\n]{0,80}\]",
        __import__("re").IGNORECASE,
    )

    @classmethod
    def _strip_retrieval_tags(cls, content: str) -> str:
        """يحذف علامات chunks الداخلية من نص المستخدم.

        يحذف: [ex: ex_1] | [sol: ex_1] | [grading: ex_1] | [chunk: ...] | [src: ...]
        أي tag على شكل [key: value] حيث key ∈ {ex, sol, grading, chunk, src, source, meta, tag, id, doc}.
        """
        return cls._RETRIEVAL_TAG_RE.sub("", content)

    @classmethod
    def _sanitize_text_for_user(cls, content: str) -> str:
        """يعقّم نصًا موجّهًا للمستخدم النهائي من أي تلميحات طوبولوجيا داخلية."""
        lowered = content.lower()
        blocked_tokens = (
            "orchestrator-service",
            "localhost",
            "127.0.0.1",
            "host.docker.internal",
            "orchestrator_service_url",
            "diagnostic",
        )
        if any(token in lowered for token in blocked_tokens):
            return "تعذر إتمام طلبك حالياً بسبب ضغط أو عطل مؤقت في خدمة المحادثة. حاول مرة أخرى بعد لحظات."
        # ISS-058: حذف tags chunks الداخلية ([ex: ex_1], [sol: ex_1], [grading: ex_1])
        return cls._strip_retrieval_tags(content)

    # ISS-STREAM-001: أنواع الأحداث التي تُمرَّر مباشرة بدون تحويل إلى assistant_delta.
    # أي نوع غير مدرج هنا ولا في _TEXT_EVENT_TYPES يُتجاهل (لا يُرسل للواجهة).
    _PASSTHROUGH_EVENT_TYPES: frozenset[str] = frozenset(
        {
            "conversation_init",
            "persisted",
            "complete",
            "phase_start",
            "phase_completed",
            "RUN_STARTED",
            "context_missing",
            # Generative UI — يُمرَّر للواجهة لتصيير مكوّن React تفاعلي.
            "ui_component",
        }
    )
    _TEXT_EVENT_TYPES: frozenset[str] = frozenset(
        {"assistant_delta", "assistant_final", "assistant_error", "status"}
    )

    def _normalize_stream_event(self, raw_event: object) -> dict[str, object]:
        """
        يوحد شكل أحداث التدفق ويضمن عدم تسريب تفاصيل داخلية.

        ISS-STREAM-001: الإصلاح الجراحي — الأحداث غير النصية (phase_start,
        RUN_STARTED, إلخ) تُمرَّر كما هي بدل تحويلها إلى assistant_delta
        مما كان يُسبب ظهور نصوص غريبة في الواجهة.
        """
        if not isinstance(raw_event, dict):
            # نص خام → delta
            return {
                "type": ChatEventType.ASSISTANT_DELTA.value,
                "payload": {"content": self._sanitize_text_for_user(str(raw_event))},
            }

        raw_type = str(raw_event.get("type", ChatEventType.ASSISTANT_DELTA.value))

        # Generative UI: نتحقق من الحمولة عبر العقد الصارم. أي مكوّن مجهول أو
        # حمولة مشوَّهة → noop (تُسقَط) بدل تمرير بيانات غير موثوقة للواجهة.
        if raw_type == "ui_component":
            return self._normalize_ui_component_event(raw_event)

        # أحداث التحكم تُمرَّر مباشرة بدون تحويل
        if raw_type in self._PASSTHROUGH_EVENT_TYPES:
            result = dict(raw_event)
            if "persisted" in raw_event:
                result["persisted"] = bool(raw_event["persisted"])
            return result

        # أحداث غير معروفة → تُتجاهل (لا تُرسل للواجهة كـ delta)
        if raw_type not in self._TEXT_EVENT_TYPES:
            return {"type": "noop", "payload": {}}

        payload = raw_event.get("payload")
        if not isinstance(payload, dict):
            payload = {"content": str(raw_event)}

        safe_payload = {
            "content": self._sanitize_text_for_user(str(payload.get("content", "")))
            if payload.get("content") is not None
            else None,
            "details": self._sanitize_text_for_user(str(payload.get("details", "")))
            if payload.get("details") is not None
            else None,
            "status_code": payload.get("status_code")
            if isinstance(payload.get("status_code"), int)
            else None,
            "request_id": str(payload.get("request_id"))
            if payload.get("request_id") is not None
            else None,
            "retry_hint": str(payload.get("retry_hint"))
            if payload.get("retry_hint") is not None
            else None,
        }

        event_type_map = {
            "assistant_delta": ChatEventType.ASSISTANT_DELTA,
            "assistant_final": ChatEventType.ASSISTANT_FINAL,
            "assistant_error": ChatEventType.ASSISTANT_ERROR,
            "status": ChatEventType.STATUS,
        }
        envelope = ChatEventEnvelope(
            type=event_type_map.get(raw_type, ChatEventType.ASSISTANT_DELTA),
            payload=ChatEventPayload(**safe_payload),
        )
        result = envelope.model_dump(exclude_none=True)
        # Preserve orchestrator persistence signal for conditional-write coordination
        if "persisted" in raw_event:
            result["persisted"] = bool(raw_event["persisted"])
        return result

    def _normalize_ui_component_event(self, raw_event: dict) -> dict[str, object]:
        """يتحقق من حمولة مكوّن UI توليدي ويعيد مغلفاً نظيفاً أو noop عند الفشل.

        أي مكوّن مجهول (خارج القائمة البيضاء) أو حمولة مشوَّهة أو ضخمة → noop
        (تُسقَط) — لا نمرر للواجهة بيانات غير موثوقة. هذا خط الدفاع الأول قبل
        React Error Boundary.
        """
        from pydantic import ValidationError

        from app.contracts.streaming import UIComponentPayload

        payload = raw_event.get("payload")
        if not isinstance(payload, dict):
            return {"type": "noop", "payload": {}}
        try:
            validated = UIComponentPayload.model_validate(payload)
        except ValidationError:
            logger.warning("ui_component_event_rejected", exc_info=True)
            return {"type": "noop", "payload": {}}
        # حماية ضد الحمولات الضخمة (cap التسلسل عند 16KB)
        try:
            if len(json.dumps(validated.props, default=str)) > 16000:
                logger.warning("ui_component_props_too_large")
                return {"type": "noop", "payload": {}}
        except (TypeError, ValueError):
            return {"type": "noop", "payload": {}}
        return {
            "type": "ui_component",
            "payload": {
                "component": validated.component,
                "props": validated.props,
                "fallback_text": self._sanitize_text_for_user(validated.fallback_text),
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Abstraction Ban (Cognitive Refactoring — V6.0):
    # تسميات عُقَد شجرة الاحتمالات يجب أن تكون ملموسة ومستخرَجة من سياق المسألة
    # ("كرة حمراء"، "سحب ناجح"، "قطعة معيبة") — لا رموز مجرّدة (A, B|A, Ā). نمط
    # هجين: استخراج حتمي أولاً، ثم LLM فقط عند عدم وجود كيان ملموس. حتى الـ
    # fallback النهائي ملموس ("الحدث الأول") — لا حرف A أبداً.
    # ─────────────────────────────────────────────────────────────────────────

    # كيانات ملموسة شائعة في مسائل بكالوريا الاحتمالات (لون + اسم، نتائج ثنائية).
    _CONCRETE_EVENT_PATTERNS: tuple[tuple[tuple[str, ...], str, str], ...] = (
        (("كرة حمراء", "كرات حمراء", "أحمر", "حمراء"), "كرة حمراء", "كرة غير حمراء"),
        (("كرة بيضاء", "كرات بيضاء", "أبيض", "بيضاء"), "كرة بيضاء", "كرة غير بيضاء"),
        (("كرة سوداء", "كرات سوداء", "أسود", "سوداء"), "كرة سوداء", "كرة غير سوداء"),
        (("كرة خضراء", "أخضر", "خضراء"), "كرة خضراء", "كرة غير خضراء"),
        (("معيب", "معيبة", "تالف", "تالفة", "défectueu"), "قطعة معيبة", "قطعة سليمة"),
        (("ناجح", "نجاح", "ينجح", "réussi", "succès"), "سحب ناجح", "سحب فاشل"),
        (("مدخن", "تدخين", "fumeur"), "مدخن", "غير مدخن"),
        (("مصاب", "مرض", "إصابة", "malade"), "مصاب", "سليم"),
        (("ذكر", "إناث", "أنثى", "ذكور"), "ذكر", "أنثى"),
        (("معطوب", "عطل", "panne"), "جهاز معطوب", "جهاز سليم"),
    )

    @classmethod
    def _extract_concrete_events(cls, normalized: str) -> dict[str, str] | None:
        """يستخرج تسميتين ملموستين من نص المسألة، أو None إن لم يجد كياناً."""
        first: tuple[str, str] | None = None
        second: tuple[str, str] | None = None
        for keywords, label, label_neg in cls._CONCRETE_EVENT_PATTERNS:
            if any(kw in normalized for kw in keywords):
                if first is None:
                    first = (label, label_neg)
                elif (label, label_neg) != first:
                    second = (label, label_neg)
                    break
        if first is None:
            return None
        if second is None:
            # حدث ثانٍ ملموس عام مرتبط بالسحب (مستوى شرطي)
            second = ("سحب ناجح", "سحب فاشل")
        return {
            "first": first[0],
            "first_neg": first[1],
            "second": second[0],
            "second_neg": second[1],
        }

    @classmethod
    def _detect_probability_tree(cls, question: str) -> dict[str, object] | None:
        """يكتشف طلبات شجرة الاحتمالات ويبني خصائص تصيير حتمية بتسميات ملموسة.

        يُفعَّل عند: (1) عبارة صريحة (شجرة احتمالات / probability tree / arbre de
        probabilité) أو (2) ذِكر "احتمال" مع وجود قيمة احتمالية رقمية. يستخرج حتى
        قيمتين احتماليتين لبناء شجرة ثنائية المستوى، وتسميات ملموسة من سياق
        المسألة (Abstraction Ban). يضع علم ``labels_generic`` ليُفعَّل إثراء الـ
        LLM لاحقاً عند الحاجة.
        """
        import re

        if not question or not isinstance(question, str):
            return None
        normalized = question.strip().lower()

        explicit_triggers = (
            "شجرة الاحتمال",
            "شجرة احتمال",
            "شجرة الاحتمالات",
            "مخطط الشجرة",
            "شجرة القرار",
            "probability tree",
            "tree diagram",
            "arbre de probabilit",
            "arbre pondéré",
            "diagramme en arbre",
        )
        has_explicit = any(trigger in normalized for trigger in explicit_triggers)
        has_probability_word = any(
            word in normalized for word in ("احتمال", "احتمالات", "probabilit", "proba")
        )

        # استخراج القيم الاحتمالية: كسور عشرية (0.3) أو نسب مئوية (30%)
        decimals = [float(m) for m in re.findall(r"\b0?\.\d+\b", normalized)]
        percents = [float(m) / 100.0 for m in re.findall(r"\b(\d{1,3})\s*%", normalized)]
        probs = [p for p in (decimals + percents) if 0.0 < p < 1.0][:2]

        if not has_explicit and not (has_probability_word and probs):
            return None

        def _complement(value: float) -> float:
            return round(1.0 - value, 4)

        p_first = probs[0] if probs else 0.5
        p_cond = probs[1] if len(probs) > 1 else 0.5

        events = cls._extract_concrete_events(normalized)
        labels_generic = events is None
        if events is None:
            # fallback ملموس عام — لا رموز مجرّدة أبداً (Abstraction Ban)
            events = {
                "first": "الحدث الأول",
                "first_neg": "عكس الحدث الأول",
                "second": "الحدث الثاني",
                "second_neg": "عكس الحدث الثاني",
            }

        tree = cls._build_tree_structure(events, p_first, p_cond, _complement)
        return {
            "title": "شجرة الاحتمالات",
            "is_illustrative": not probs,
            "labels_generic": labels_generic,
            "tree": tree,
        }

    @staticmethod
    def _build_tree_structure(
        events: dict[str, str],
        p_first: float,
        p_cond: float,
        complement: object,
    ) -> dict[str, object]:
        """يبني شجرة ثنائية المستوى بتسميات ملموسة. موضع العقدة يُمثّل الشرط."""
        _comp = complement  # callable
        return {
            "label": "البداية",
            "children": [
                {
                    "label": events["first"],
                    "p": round(p_first, 4),
                    "children": [
                        {"label": events["second"], "p": round(p_cond, 4)},
                        {"label": events["second_neg"], "p": _comp(p_cond)},  # type: ignore[operator]
                    ],
                },
                {
                    "label": events["first_neg"],
                    "p": _comp(p_first),  # type: ignore[operator]
                    "children": [
                        {"label": events["second"], "p": 0.5},
                        {"label": events["second_neg"], "p": 0.5},
                    ],
                },
            ],
        }

    @staticmethod
    def _build_calculated_tree_props(
        question: str,
        history_messages: list[dict[str, str]] | None = None,
    ) -> dict[str, object] | None:
        """يحسب شجرة احتمالات بكسور حقيقية عبر ProbabilityCalculatorSkill (D-075).

        Protocol V14.0 §3: الخلفية تحسب P(الحدث) = العدد/المجموع ديناميكياً من
        التركيبة العربية (مثل 4/11) بدلاً من إغراق الواجهة بقيمة 0.5 وهمية. كل
        عقدة تحمل (p_num/p_den) فتُصيّر الواجهة الكسر الدقيق. محروس بـ try/except —
        أي فشل يُرجع None ويسقط للمسار الحتمي القديم (`_detect_probability_tree`).
        """
        try:
            from app.services.skills.probability_skill import (
                ProbabilityCalculatorSkill,
                ProbabilityInput,
                ProbabilityModelOutput,
            )

            skill = ProbabilityCalculatorSkill()
            result = skill.analyze(ProbabilityInput(question=question, history=history_messages))
            if not isinstance(result, ProbabilityModelOutput):
                return None
            return {
                "title": result.title,
                "is_illustrative": False,  # قيم محسوبة حقيقية — ليست توضيحية
                "calculated": True,
                "with_replacement": result.with_replacement,
                "total": result.total,
                "composition": [
                    {
                        "label": item.label,
                        "count": item.count,
                        "p_num": item.p_num,
                        "p_den": item.p_den,
                        "p_decimal": item.p_decimal,
                    }
                    for item in result.composition
                ],
                "tree": result.tree,
            }
        except Exception:
            logger.warning("_build_calculated_tree_props_failed", exc_info=True)
            return None

    @staticmethod
    def _build_calculated_ui(
        question: str,
        history_messages: list[dict[str, str]] | None = None,
    ) -> dict[str, object] | None:
        """D-078 (V19.0 → V28.0): الموجِّه التربوي — يُرجِع حدث ui_component الصحيح.

        «دفعة واحدة» (سحب آني) → ``combinations_visualizer`` (تأليفي C_n^k)؛
        «على التوالي» / سحب مفرد → ``probability_tree``. هذا يمنع فرض شجرة
        تتابعية على مسألة آنية (كارثة تربوية). كاشف الإحباط (مفهمتش/كيفاش)
        يُفعِّل الأداة البصرياً عبر سياق المحادثة. محروس بـ try/except.

        المخرج: ``{"component": str, "props": dict, "fallback_text": str,
        "terminate_pipeline": bool}`` أو None.

        ## V28.0 — قانون الكبح النصي (Text-Wall Muzzle)
        ``terminate_pipeline=True`` يُصدَر حصراً مع ``impossible_case``.
        يُلزم ``chat_with_agent`` بإنهاء المسار فوراً بعد بثّ المكوّن البصري
        و``companion_text`` (جملة واحدة) — لا LLM، لا شجرة، لا synthesizer.
        """
        try:
            from app.services.skills.probability_skill import (
                CombinationsModelOutput,
                FullExerciseStoryOutput,
                ImpossibleCaseOutput,
                ProbabilityCalculatorSkill,
                ProbabilityInput,
                ProbabilityModelOutput,
            )

            skill = ProbabilityCalculatorSkill()
            result = skill.analyze(ProbabilityInput(question=question, history=history_messages))

            # V31.5 (Full Exercise OS): القصة التربوية الشاملة — Carousel متعدّد
            # الخطوات يغطّي التمرين كاملاً (معطيات → فضاء عيّنة → حدث مركّب →
            # متغيّر عشوائي). يُفعَّل عند حيرة الطالب. terminate_pipeline=True
            # يكبح جدار النص — companion_text (جملة واحدة) هو النص الوحيد.
            if isinstance(result, FullExerciseStoryOutput):
                return {
                    "component": "full_exercise_story",
                    "terminate_pipeline": True,
                    "companion_text": result.companion_text,
                    "props": {
                        "title": result.title,
                        "ui_mode": result.ui_mode,
                        "calculated": True,
                        "n": result.n,
                        "k": result.k,
                        "total_combinations": result.total_combinations,
                        "exercise_steps": [
                            {
                                "step_index": s.step_index,
                                "step_id": s.step_id,
                                "title": s.title,
                                "render_kind": s.render_kind,
                                "visual_directives": s.visual_directives,
                                "numerical_state": s.numerical_state,
                                "pedagogical_message": s.pedagogical_message,
                            }
                            for s in result.exercise_steps
                        ],
                    },
                    "fallback_text": (
                        f"شرح بصري شامل: سحب {result.k} من {result.n} "
                        f"(C={result.total_combinations}) عبر {len(result.exercise_steps)} خطوات."
                    ),
                }

            # V28.0: الحالة المستحيلة — short-circuit كامل للـ pipeline.
            # terminate_pipeline=True يُوقف كل عقد LLM/شجرة/synthesizer لاحقة.
            # companion_text (≤ 120 حرف) هو النص الوحيد المسموح به مع المكوّن.
            if isinstance(result, ImpossibleCaseOutput):
                return {
                    "component": "impossible_draw_animation",
                    "terminate_pipeline": True,
                    "companion_text": result.companion_text,
                    "props": {
                        "title": result.title,
                        "ui_mode": result.ui_mode,
                        "visual_directives": {
                            "animation_hint": result.visual_directives.animation_hint,
                            "fallback_math": result.visual_directives.fallback_math,
                        },
                        "numerical_state": {
                            "available_items": result.numerical_state.available_items,
                            "requested_items": result.numerical_state.requested_items,
                            "item_color": result.numerical_state.item_color,
                        },
                        "pedagogical_message": result.pedagogical_message,
                        "item_label": result.item_label,
                        "container": result.container,
                    },
                    "fallback_text": result.pedagogical_message,
                }

            if isinstance(result, CombinationsModelOutput):
                props = {
                    "title": result.title,
                    "calculated": True,
                    "draw_mode": "simultaneous",
                    "deep_dive": result.deep_dive,
                    "n": result.n,
                    "k": result.k,
                    "total_combinations": result.total_combinations,
                    "groups": [
                        {
                            "label": g.label,
                            "count": g.count,
                            "favorable_combinations": g.favorable_combinations,
                            # V30.0 — حارس الحلقة الداخلية: الواجهة تعرض
                            # pedagogical_string حين is_possible=False بدل C_n^k=0.
                            "is_possible": g.is_possible,
                            "pedagogical_string": g.pedagogical_string,
                            "color": g.color,
                        }
                        for g in result.groups
                    ],
                    "same_group_favorable": result.same_group_favorable,
                    "formula": result.formula,
                    # V30.0 — القصة البصرية الشاملة (Deep Dive storytelling).
                    "urn_state": result.urn_state,
                    "event_analysis": result.event_analysis,
                }
                return {
                    "component": "combinations_visualizer",
                    # V30.0 — قانون الكبح النصي: المكوّن البصري يُنهي المسار.
                    # لا جدار نصّي ولا اشتقاق رياضي نصّي يتبع المكوّن.
                    "terminate_pipeline": True,
                    "companion_text": "إليك الشرح البصري المفصل للتمرين خطوة بخطوة 🪄",
                    "props": props,
                    "fallback_text": (
                        f"سحب آني: اختيار {result.k} من {result.n} → "
                        f"عدد التأليفات C({result.n},{result.k}) = {result.total_combinations}."
                    ),
                }

            if isinstance(result, ProbabilityModelOutput):
                props = {
                    "title": result.title,
                    "is_illustrative": False,
                    "calculated": True,
                    "with_replacement": result.with_replacement,
                    "total": result.total,
                    "composition": [
                        {
                            "label": item.label,
                            "count": item.count,
                            "p_num": item.p_num,
                            "p_den": item.p_den,
                            "p_decimal": item.p_decimal,
                        }
                        for item in result.composition
                    ],
                    "tree": result.tree,
                }
                return {
                    "component": "probability_tree",
                    # V30.0 — قانون الكبح النصي: شجرة الاحتمالات تُنهي المسار أيضاً.
                    # لا اشتقاق رياضي نصّي يتبع المكوّن البصري.
                    "terminate_pipeline": True,
                    "companion_text": "إليك الشرح البصري المفصل للتمرين خطوة بخطوة 🪄",
                    "props": props,
                    "fallback_text": ("شجرة الاحتمالات (تعذّر عرض الرسم التفاعلي — هذا نص بديل)."),
                }
            return None
        except Exception:
            logger.warning("_build_calculated_ui_failed", exc_info=True)
            return None

    async def _build_probability_tree_props(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None = None,
    ) -> dict[str, object] | None:
        """غلاف غير متزامن: استخراج حتمي ثم إثراء LLM للتسميات عند الحاجة فقط.

        إذا فشل الاستخراج الحتمي في إيجاد كيان ملموس (``labels_generic=True``)،
        نحاول أولاً استخراج الكيانات من سياق المحادثة (history_messages) قبل
        اللجوء للـ LLM. هذا يحل Bug D: "اعطني شجرة الاحتمالات" بعد تمرين
        الاحتمالات 2024 يجب أن يُنتج "كرة حمراء" لا "الحدث الأول".

        Bug A fix: كل المسار محروس بـ try/except شامل — أي استثناء (بما فيه
        pydantic.ValidationError من get_settings() أو asyncio.TimeoutError من
        _enrich_tree_labels_with_llm) يُسجَّل ويُرجع None بدلاً من الانتشار
        للـ WebSocket handler وتسبيب 500 HTML bleed في Next.js DevTools.
        """
        try:
            # ── D-075 (Protocol V14.0): REAL probability calculation first ──
            # ProbabilityCalculatorSkill يحسب كسوراً حقيقية من تركيبة المسألة
            # العربية (P(حمراء)=4/11) بدلاً من القيمة الوهمية 0.5. يُحاول السؤال
            # ثم سياق المحادثة. عند النجاح نُرجع شجرة بكسور دقيقة (p_num/p_den).
            calc_props = self._build_calculated_tree_props(question, history_messages)
            if calc_props is not None:
                return calc_props

            props = self._detect_probability_tree(question)
            if props is None:
                return None
            if not props.get("labels_generic"):
                props.pop("labels_generic", None)
                return props

            # Bug D fix: محاولة استخراج كيانات ملموسة من سياق المحادثة أولاً
            # (أسرع وأكثر دقة من LLM عند وجود تمرين سابق في السياق)
            if history_messages:
                history_text = " ".join(
                    str(m.get("content", ""))[:2000]
                    for m in history_messages[-6:]
                    if isinstance(m, dict)
                ).lower()
                if history_text.strip():
                    context_events = self._extract_concrete_events(history_text)
                    if context_events is not None:
                        tree = props.get("tree")
                        if isinstance(tree, dict):
                            children = tree.get("children")
                            if isinstance(children, list) and len(children) == 2:
                                children[0]["label"] = context_events["first"]
                                children[1]["label"] = context_events["first_neg"]
                                for branch in children:
                                    sub = branch.get("children")
                                    if isinstance(sub, list) and len(sub) == 2:
                                        sub[0]["label"] = context_events["second"]
                                        sub[1]["label"] = context_events["second_neg"]
                        props.pop("labels_generic", None)
                        return props

            # محاولة إثراء عبر LLM (best-effort) عند غياب السياق
            with contextlib.suppress(Exception):
                enriched = await self._enrich_tree_labels_with_llm(question)
                if enriched is not None:
                    tree = props.get("tree")
                    if isinstance(tree, dict):
                        children = tree.get("children")
                        if isinstance(children, list) and len(children) == 2:
                            children[0]["label"] = enriched["first"]
                            children[1]["label"] = enriched["first_neg"]
                            for branch in children:
                                sub = branch.get("children")
                                if isinstance(sub, list) and len(sub) == 2:
                                    sub[0]["label"] = enriched["second"]
                                    sub[1]["label"] = enriched["second_neg"]
            props.pop("labels_generic", None)
            return props
        except Exception:
            logger.warning("_build_probability_tree_props_failed", exc_info=True)
            return None

    @staticmethod
    async def _enrich_tree_labels_with_llm(question: str) -> dict[str, str] | None:
        """يستخرج كيانات ملموسة عبر LLM ويُرجع dict تسميات أو None عند الفشل.

        محروس بـ timeout 8s. يرفض أي ناتج يحوي رموزاً مجرّدة (A/B بمفردها).
        """
        import asyncio
        import json

        from app.core.ai_gateway import get_ai_client

        system_prompt = (
            "أنت مستخرج كيانات لمسائل الاحتمالات. من نص المسألة، استخرج حدثين "
            "كعبارات اسمية عربية قصيرة وملموسة (مثل 'كرة حمراء'، 'قطعة معيبة'، "
            "'سحب ناجح'). ممنوع منعاً باتاً استخدام الرموز المجرّدة A أو B أو Ā. "
            "أعِد JSON فقط بهذا الشكل بلا أي نص آخر: "
            '{"first":"...","first_neg":"...","second":"...","second_neg":"..."}'
        )
        ai_client = get_ai_client()
        raw = await asyncio.wait_for(
            ai_client.send_message(system_prompt, question.strip()[:1200], temperature=0.2),
            timeout=8.0,
        )
        if not raw or not isinstance(raw, str):
            return None
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        data = json.loads(raw[start : end + 1])
        keys = ("first", "first_neg", "second", "second_neg")
        if not all(isinstance(data.get(k), str) and data[k].strip() for k in keys):
            return None
        cleaned = {k: data[k].strip()[:60] for k in keys}
        # رفض الرموز المجرّدة (Abstraction Ban)
        banned = {"a", "b", "ā", "b̄", "a'", "b'"}
        if any(cleaned[k].lower() in banned for k in keys):
            return None
        return cleaned

    @staticmethod
    def _sanitize_error_for_user(*, request_id: str) -> dict[str, object]:
        """ينتج رسالة خطأ آمنة للمستخدم بدون أي تفاصيل طوبولوجيا أو تشخيص داخلي."""
        return {
            "type": "assistant_error",
            "payload": {
                "content": "تعذر إتمام طلبك حالياً بسبب ضغط أو عطل مؤقت في خدمة المحادثة. حاول مرة أخرى بعد لحظات.",
                "request_id": request_id,
                "retry_hint": "يمكنك إعادة المحاولة بعد دقيقة.",
            },
        }

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
        try:
            _ui_event = self._build_calculated_ui(question, history_messages=history_messages)
        except Exception:
            _ui_event = None

        if _ui_event is not None:
            _is_impossible = _ui_event.get("terminate_pipeline") is True

            # ─────────────────────────────────────────────────────────────────
            # Protocol V34.0 — Contextual Unmuzzle & The Teacher's Voice
            # ─────────────────────────────────────────────────────────────────
            # إذا عبّر الطالب عن حيرة («لم أفهم»، «اشرح لي»)، نكسر حلقة الكبح
            # النصي (Muzzle) ونسمح للـ LLM بالاستمرار لتقديم السرد البيداغوجي العميق.
            # الواجهة البصرية تُبثّ كالعادة، لكن النص يقوم بالعبء الثقيل للشرح.
            from app.services.skills.probability_skill import ProbabilityCalculatorSkill

            _is_confusion = ProbabilityCalculatorSkill.is_confusion(question)
            if _is_confusion and _is_impossible:
                _is_impossible = False
                logger.info(
                    "contextual_unmuzzle_triggered",
                    extra={"question": question, "component": _ui_event.get("component")},
                )

            logger.info(
                "generative_ui_emit",
                extra={
                    "request_id": str(uuid.uuid4()),
                    "component": _ui_event.get("component"),
                    "terminate_pipeline": _is_impossible,
                    "question_len": len(question),
                },
            )
            yield self._normalize_stream_event({"type": "ui_component", "payload": _ui_event})

            # V28.0: impossible_case — terminate pipeline immediately.
            # Emit companion_text (≤ 120 chars) as the sole text output, then return.
            # This is the Text-Wall Muzzle: no LLM, no tree, no synthesizer follows.
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
                                "fallback_path": 0.1,  # impossible_case = أعلى أولوية بعد greeting
                                "stream_chars": float(len(_companion)),
                            },
                        )
                return

        # ─────────────────────────────────────────────────────────────────────
        # ISS-056 (D-049 — Indexed Retrieval Preemption):
        # إذا طابق السؤال تمريناً محدداً في knowledge_index، نتجاوز كل
        # شيء (orchestrator + StateGraph + fallback chain) ونبث المحتوى
        # المُفهرَس النظيف مباشرة. هذا يحل كارثة JSON envelope leak عند المصدر.
        # ISS-CONV-C: نمرر history_messages لحل أسئلة المتابعة بالسياق.
        # ─────────────────────────────────────────────────────────────────────
        if self._has_indexed_match(question, history_messages):
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
        # ISS-058 (D-052 — Explanation-with-Context Preemption):
        # عند طلب شرح/استفسار مرتبط بتمرين بكالوريا (صريحاً أو ضمن السياق)،
        # نتجاوز orchestrator + StateGraph لمنع dump عدة تمارين غير متعلقة
        # (كارثة 2016 + 2024 المُختلطين) ولمنع تسريب tags خام مثل [ex: ex_1].
        #
        # ISS-059 (D-053): الآن نحسب القرار **مرة واحدة** ونمرِّره للـ stream
        # بدل إعادة حسابه — يوفِّر ~10-20ms + file I/O مكرَّر.
        # ─────────────────────────────────────────────────────────────────────
        _explanation_decision = detect_explanation_with_context(
            ExerciseRetrievalRequest(question=question),
            history_messages=history_messages,
        )
        if _explanation_decision.recognized and _explanation_decision.matched_entry is not None:
            logger.info(
                "explanation_context_preempt",
                extra={
                    "request_id": str(uuid.uuid4()),
                    "reason": _explanation_decision.reason,
                    "matched_file": _explanation_decision.matched_entry.file_path,
                },
            )
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

        payload = {
            "question": question,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "history_messages": history_messages or [],
            "context": context or {},
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
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            parsed_line = json.loads(line)
                            yield self._normalize_stream_event(parsed_line)
                        except json.JSONDecodeError:
                            recovered = self._recover_structured_event(line)
                            if recovered is not None:
                                yield self._normalize_stream_event(recovered)
                            else:
                                logger.warning(f"Received non-JSON line from agent: {line[:50]}...")
                                yield self._normalize_stream_event(line)
                    return
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
                    question=question,
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
                        question,
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

    @staticmethod
    def _recover_structured_event(raw_line: str) -> dict[str, object] | None:
        """يحاول استعادة حدث هيكلي من تمثيل dict نصي لمنع تسريب البنية إلى الدردشة."""
        candidate = raw_line.strip()
        if not (candidate.startswith("{") and candidate.endswith("}")):
            return None
        try:
            parsed = literal_eval(candidate)
        except (SyntaxError, ValueError):
            return None
        if not isinstance(parsed, dict):
            return None
        if not isinstance(parsed.get("type"), str):
            return None
        payload = parsed.get("payload")
        if payload is not None and not isinstance(payload, dict):
            return None
        return parsed


# Singleton
orchestrator_client = OrchestratorClient()
