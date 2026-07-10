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
import re
import time
import uuid
from ast import literal_eval
from collections.abc import AsyncGenerator
from typing import ClassVar

import httpx
import jwt as pyjwt
from pydantic import BaseModel
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.ai_gateway import get_ai_client
from app.core.http_client_factory import HTTPClientConfig, get_http_client
from app.core.settings.base import get_settings
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

    async def _stream_markdown_typing(self, full_response: str) -> AsyncGenerator[str, None]:
        """يبثّ نصاً ثابتاً (markdown) بإيقاع typing-effect مع حماية LaTeX.

        مُستخرَج من ``_stream_local_retrieval_response`` (ISS-112) ليُشارَك مع
        مسار «السؤال فقط» — السلوك مطابق حرفياً لما قبل الاستخراج.
        """
        import asyncio

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
        """D-078 (V19.0 → V38.0): الموجِّه التربوي — يُرجِع حدث ui_component الصحيح.

        «دفعة واحدة» (سحب آني) → ``combinations_visualizer`` (تأليفي C_n^k)؛
        «على التوالي» / سحب مفرد → ``probability_tree``. هذا يمنع فرض شجرة
        تتابعية على مسألة آنية (كارثة تربوية). كاشف الإحباط (مفهمتش/كيفاش)
        يُفعِّل الأداة البصرياً عبر سياق المحادثة. محروس بـ try/except.

        المخرج: ``{"component": str, "props": dict, "fallback_text": str,
        "terminate_pipeline": bool, "routing_mode": str}`` أو None.

        ## V38.0 — نظام التوجيه الثنائي (Dual-Mode Routing)

        ### MODE_A — الوضع المباشر (Standard Direct Mode)
        يُستخدم عند السؤال المباشر أو طلب الحل العادي.
        - ``terminate_pipeline=True`` يُوقف المسار بعد المكوّن البصري.
        - ``companion_text`` (جملة واحدة) هو النص الوحيد المرافق.

        ### MODE_B — وضع البيداغوجيا العميقة (Deep Pedagogy Mode)
        يُفعَّل عند إشارات الحيرة («لم أفهم»، «اشرح لي»، «كيفاش»).
        - ``terminate_pipeline=False`` — المسار يبقى حياً.
        - المكوّن البصري يُبثّ أولاً، ثم يستمر السرد البيداغوجي من LLM.
        - القناتان (JSON + Markdown) منفصلتان تماماً — لا تلوّث متبادل.

        ## V28.0 — قانون الكبح النصي (Text-Wall Muzzle) — ساري في MODE_A فقط
        ``terminate_pipeline=True`` يُلزم ``chat_with_agent`` بإنهاء المسار
        فوراً بعد بثّ المكوّن البصري و``companion_text`` — لا LLM، لا synthesizer.
        """
        try:
            from app.services.capabilities.arabic_normalize import primary_canonical_topic
            from app.services.skills.probability_skill import (
                CombinationsModelOutput,
                FullExerciseStoryOutput,
                ImpossibleCaseOutput,
                ProbabilityCalculatorSkill,
                ProbabilityInput,
                ProbabilityModelOutput,
            )

            # ISS-110 (D-101): حاجب تبديل الموضوع — إذا كان السؤال الحالي يذكر
            # صراحةً موضوعاً مرجعياً غير الاحتمالات (دوال عددية / أعداد مركبة)،
            # فلا تُبنى أي واجهة احتمالات من سياق الـ history حتى مع وجود حيرة.
            _canonical = primary_canonical_topic(question)
            if _canonical is not None and _canonical.canonical_id != "probability":
                return None

            skill = ProbabilityCalculatorSkill()
            _combined_text = (
                question + " " + " ".join(m.get("content", "") for m in (history_messages or []))
            )

            # D-122/D-123: حارس سياق الاحتمالات (مُعرَّف مبكراً — للتحصين والتركيز).
            def _is_probability_context(text: str) -> bool:
                t = text or ""
                return any(
                    marker in t
                    for marker in ("كرات", "كرة", "كيس", "احتمال", "سحب", "نسحب", "p(a", "p(b")
                )

            # ─────────────────────────────────────────────────────────────────
            # D-123 — تحصين بالمحتوى الرسمي (history-immune):
            # الكارثة الحيّة: نص LLM مُهلوَس في الـ history («2 برتقالية + 3 زرقاء»)
            # كان يُسمّم استخراج التركيبة ⇒ كاروسيل خاطئ («سحب 2 من 11»/«كرة زرقاء»).
            # الحل: (1) جرّب السؤال وحده (تركيبة inline مثل «كيس فيه 4 حمراء و7 بيضاء»).
            # (2) إن لم توجد + سياق احتمالات (محادثة التمرين المُفهرَس) ⇒ ابنِ من
            # **المحتوى الرسمي للتمرين** + نية السؤال، بـ history=None ⇒ مناعة كاملة
            # من تلوّث الـ history. (3) آخر ملاذ: الاستخراج بالـ history (السلوك الأصلي).
            # هذا يضمن الكاروسيل الصحيح (2بيضاء/4حمراء/5خضراء) ⇒ terminate=True ⇒ صفر LLM.
            # ─────────────────────────────────────────────────────────────────
            def _result_ok(r: object) -> bool:
                return r is not None and getattr(r, "success", True) is not False

            # (1) السؤال وحده — يلتقط التركيبة الـ inline بلا تلوّث history.
            result = skill.analyze(ProbabilityInput(question=question, history=None))

            # (2) محادثة التمرين المُفهرَس: المحتوى الرسمي + نية السؤال، history=None.
            if not _result_ok(result) and _is_probability_context(_combined_text):
                with contextlib.suppress(Exception):
                    from app.services.capabilities.exercise_retrieval import (
                        ExerciseRetrievalRequest,
                        detect_exercise_retrieval,
                        load_exercise_questions_only,
                    )

                    _canon = detect_exercise_retrieval(
                        ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024"),
                        history_messages=history_messages,
                    )
                    if _canon.recognized and _canon.matched_entry:
                        # ISS-120 (D-153): أسئلة-فقط — نثر الحل النموذجي يولِّد كياناً
                        # وهمياً («بطاقة رقم 0») يُفسد فضاء العينة (n=14 بدل 11).
                        _official = load_exercise_questions_only(_canon.matched_entry)
                        # المحتوى الرسمي (التركيبة) + السؤال الحالي (نية الحيرة/التركيز)؛
                        # السؤال الحالي نظيف — التلوّث كان في الـ history (مُسقَط بـ None).
                        _canon_result = skill.analyze(
                            ProbabilityInput(question=f"{_official} {question}", history=None)
                        )
                        if _result_ok(_canon_result):
                            result = _canon_result

            # (3) آخر ملاذ — السلوك الأصلي (history). نادر بعد التحصين.
            if not _result_ok(result):
                result = skill.analyze(
                    ProbabilityInput(question=question, history=history_messages)
                )

            # V38.0 — Dual-Mode Routing: كشف نية الطالب قبل بناء الحمولة.
            # MODE_B يُفعَّل عند إشارات الحيرة — يُبقي المسار حياً للسرد البيداغوجي.
            # MODE_A هو الوضع الافتراضي — يُوقف المسار بعد المكوّن البصري.
            # ISS-114 (D-106): طلب توليد واجهة صريح («قم بتوليد واجهة تشرح
            # الحادثة») يُفعِّل MODE_B (مكوّن بصري + سرد بيداغوجي) — لا يصل
            # الطلب أبداً لـ LLM يكتب HTML خاماً.
            _is_deep_pedagogy = (
                ProbabilityCalculatorSkill.is_confusion(question)
                or ProbabilityCalculatorSkill.is_confusion(_combined_text)
                or ProbabilityCalculatorSkill.is_visual_request(question)
            )
            _routing_mode = "MODE_B" if _is_deep_pedagogy else "MODE_A"

            def _detect_focus_step(user_question: str) -> str | None:
                """يحدِّد خطوة الشرح المطلوبة صراحةً لتخصيص الواجهة والنص المرافق."""
                q = user_question.lower()
                if "p(a" in q or "نفس اللون" in q or "same color" in q:
                    return "same_color_event"
                if "p(b" in q or "p(c" in q or "فردي" in q or "زوجي" in q:
                    return "same_color_event"
                if "شرطي" in q or "p_a" in q or "p a" in q:
                    return "same_color_event"
                if "x>1" in q or "e(x" in q or "الأمل" in q or "المتغير" in q:
                    return "random_variable"
                if "جداء" in q and ("معدوم" in q or "صفر" in q):
                    return "sequential_zero_product"
                if "فضاء" in q or "c(" in q or "تأليف" in q:
                    return "sample_space"
                return None

            # D-122: إشارات طبيعية لأجزاء التمرين («السؤال الأول» = P(A) = الحدث A)
            # — لا تحوي رمز P(A) لكنها تستهدف خطوة. تُطبَّق فقط ضمن سياق احتمالات
            # مؤكَّد (حارس أدناه) تجنّباً لتحميل احتمالات في محادثة موضوع آخر.
            def _detect_part_reference(user_question: str) -> str | None:
                q = user_question.lower()
                # السؤال 2 / المتغير العشوائي X (يُفحَص أولاً: «الثاني» أكثر تحديداً)
                if (
                    "السؤال الثاني" in q
                    or "السؤال 2" in q
                    or "السوال الثاني" in q
                    or "الجزء الثاني" in q
                ):
                    return "random_variable"
                # السؤال 1 / الحدث A (الافتراض الرئيسي لتمرين الاحتمالات)
                if (
                    "السؤال الاول" in q
                    or "السؤال الأول" in q
                    or "السؤال 1" in q
                    or "السوال الاول" in q
                    or "الجزء الاول" in q
                    or "الجزء الأول" in q
                    or "الجزء 1" in q
                    or "الحدث a" in q
                    or "الحادثة a" in q
                    or "حل السؤال" in q
                    or "حل السوال" in q
                ):
                    return "same_color_event"
                return None

            # D-122: حارس سياق الاحتمالات مُعرَّف مبكراً أعلاه (D-123) — يُعاد استخدامه هنا.
            _focus_step_id = _detect_focus_step(question)
            # D-122: لو لم يُطابق رمز صريح، جرّب الإشارة الطبيعية لجزء التمرين —
            # فقط ضمن سياق احتمالات (history) كي لا تُحمَّل احتمالات في موضوع آخر.
            # «لم أفهم» في سياق احتمالات بلا جزء محدّد ⇒ خطوة الحدث (السؤال الرئيسي).
            if _focus_step_id is None and _is_probability_context(_combined_text):
                _focus_step_id = _detect_part_reference(question)
                if _focus_step_id is None and _is_deep_pedagogy:
                    _focus_step_id = "same_color_event"

            # ISS-110: نقبل أيضاً `no_probability_intent_in_question` — سؤال متابعة
            # بخطوة تركيز صريحة (_focus_step_id) يُعاد تحليله بالسياق الكامل.
            _is_no_model = getattr(result, "success", True) is False and getattr(
                result, "reason", ""
            ) in ("no_model_extracted", "no_probability_intent_in_question")
            if (result is None or _is_no_model) and _focus_step_id and history_messages:
                _history_context = " ".join(m.get("content", "") for m in history_messages)
                _contextual_question = f"{_history_context} {question}".strip()
                result = skill.analyze(
                    ProbabilityInput(question=_contextual_question, history=history_messages)
                )

            # ISS-110: نقبل أيضاً `no_probability_intent_in_question` — سؤال متابعة
            # بخطوة تركيز صريحة (_focus_step_id) يُعاد تحليله بالسياق الكامل.
            _is_no_model = getattr(result, "success", True) is False and getattr(
                result, "reason", ""
            ) in ("no_model_extracted", "no_probability_intent_in_question")
            if (result is None or _is_no_model) and _focus_step_id:
                with contextlib.suppress(Exception):
                    from app.services.capabilities.exercise_retrieval import (
                        ExerciseRetrievalRequest,
                        detect_exercise_retrieval,
                        load_exercise_questions_only,
                    )

                    _decision = detect_exercise_retrieval(
                        ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024"),
                        history_messages=history_messages,
                    )
                    if _decision.recognized and _decision.matched_entry:
                        # ISS-120 (D-153): أسئلة-فقط قبل استخراج الكيانات.
                        _full = load_exercise_questions_only(_decision.matched_entry)
                        _contextual_question = f"{_full} {question}".strip()
                        result = skill.analyze(
                            ProbabilityInput(
                                question=_contextual_question, history=history_messages
                            )
                        )

            # D-117 (Fix 4 — best-effort): حيرة عامة («لم أفهم» بلا خطوة تركيز
            # محددة) بعد تمرين احتمالات → أعِد استخراج تركيبة الكيس من الـ history
            # فيُعاد بثّ البصري الحتمي بدل السقوط للـ LLM (مصدر الغارباج). إن تعذّر
            # الاستخراج يبقى result فاشلاً → return None → الإصلاحات 1-3 تضمن نظافة
            # مخرَج الـ LLM. (المفهوم=probability مضمون بحاجب تبديل الموضوع أعلاه.)
            _is_no_model = getattr(result, "success", True) is False and getattr(
                result, "reason", ""
            ) in ("no_model_extracted", "no_probability_intent_in_question")
            if (result is None or _is_no_model) and _is_deep_pedagogy and history_messages:
                _history_context = " ".join(m.get("content", "") for m in history_messages).strip()
                if _history_context:
                    result = skill.analyze(
                        ProbabilityInput(question=_history_context, history=history_messages)
                    )

            def _companion_text_for_focus(default_text: str) -> str:
                """يبني نصاً مرافقاً موجهاً حسب طلب الطالب بدل تكرار عبارة عامة."""
                if _focus_step_id == "same_color_event":
                    return "سنشرح الآن خطوة الحدث المطلوب فقط مع ربطها بالواجهة مباشرة."
                if _focus_step_id == "random_variable":
                    return "سنركّز الآن على المتغير X وقانونه خطوة بخطوة داخل الواجهة."
                if _focus_step_id == "sample_space":
                    return "سنبدأ من فضاء العينة C(n,k) ثم نبني باقي النتائج عليه بصرياً."
                if _focus_step_id == "sequential_zero_product":
                    return "سنشرح خطوة الجداء المعدوم في السحب المتتالي مع منطق المتمم."
                return default_text

            # V44.0 — AEK: استدعاء النواة التعليمية التكيّفية لإثراء الحمولة
            # بالحالة المعرفية والنية التربوية. غير حرج — أي فشل يُسجَّل ويُتجاوَز.
            _aek_state: dict[str, object] = {}
            try:
                from app.services.aek.kernel import AdaptiveEducationalKernel

                _aek_output = AdaptiveEducationalKernel().process(
                    question=question,
                    history=list(history_messages or []),
                )
                _aek_state = {
                    "cognitive_state": _aek_output.channel_a.cognitive_state,
                    "cognitive_intent": _aek_output.channel_a.cognitive_intent,
                    "abstraction_level": _aek_output.channel_a.abstraction_level,
                    "cognitive_load_index": _aek_output.channel_a.cognitive_load_index,
                    "narrative": _aek_output.channel_b.narrative,
                    "pacing_hint": _aek_output.channel_b.pacing_hint,
                }
            except Exception:
                logger.debug("aek_enrichment_skipped", exc_info=True)

            # V31.5 (Full Exercise OS): القصة التربوية الشاملة — Carousel متعدّد
            # الخطوات يغطّي التمرين كاملاً (معطيات → فضاء عيّنة → حدث مركّب →
            # متغيّر عشوائي). يُفعَّل عند حيرة الطالب. terminate_pipeline=True
            # يكبح جدار النص — companion_text (جملة واحدة) هو النص الوحيد.
            if isinstance(result, FullExerciseStoryOutput):
                return {
                    "component": "full_exercise_story",
                    # V38.0: MODE_B (confusion) keeps pipeline alive for deep narrative.
                    # D-116: الاحتمالات = مُعلّم بصري حتمي كامل ⇒ terminate دائماً
                    # (حتى عند الحيرة) — لا سرد LLM (مصدر الغارباج). البصري هو البيداغوجيا.
                    "terminate_pipeline": True,
                    "routing_mode": _routing_mode,
                    "companion_text": _companion_text_for_focus(result.companion_text),
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
                        "focus_step_id": _focus_step_id,
                    },
                    "fallback_text": (
                        f"شرح بصري شامل: سحب {result.k} من {result.n} "
                        f"(C={result.total_combinations}) عبر {len(result.exercise_steps)} خطوات."
                    ),
                    "aek_state": _aek_state,
                }

            # V28.0: الحالة المستحيلة — short-circuit كامل للـ pipeline.
            # terminate_pipeline=True يُوقف كل عقد LLM/شجرة/synthesizer لاحقة.
            # companion_text (≤ 120 حرف) هو النص الوحيد المسموح به مع المكوّن.
            if isinstance(result, ImpossibleCaseOutput):
                return {
                    "component": "impossible_draw_animation",
                    # V38.0: impossible_case always terminates in MODE_A.
                    # In MODE_B (confusion about impossible draw), pipeline stays alive
                    # so the LLM can explain WHY the draw is impossible pedagogically.
                    # D-116: الاحتمالات = مُعلّم بصري حتمي كامل ⇒ terminate دائماً
                    # (حتى عند الحيرة) — لا سرد LLM (مصدر الغارباج). البصري هو البيداغوجيا.
                    "terminate_pipeline": True,
                    "routing_mode": _routing_mode,
                    "companion_text": _companion_text_for_focus(result.companion_text),
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
                    "aek_state": _aek_state,
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
                    # طلب الطالب المركّز: يسمح للواجهة بإبراز جزء محدد بدل العرض العام.
                    "focus_step_id": _focus_step_id,
                }
                return {
                    "component": "combinations_visualizer",
                    # V38.0: MODE_B (confusion) keeps pipeline alive for deep narrative.
                    # MODE_A terminates after the visual component (Text-Wall Muzzle).
                    # D-116: الاحتمالات = مُعلّم بصري حتمي كامل ⇒ terminate دائماً
                    # (حتى عند الحيرة) — لا سرد LLM (مصدر الغارباج). البصري هو البيداغوجيا.
                    "terminate_pipeline": True,
                    "routing_mode": _routing_mode,
                    "companion_text": _companion_text_for_focus(
                        "إليك الشرح البصري المفصل للتمرين خطوة بخطوة 🪄"
                    ),
                    "props": props,
                    "fallback_text": (
                        f"سحب آني: اختيار {result.k} من {result.n} → "
                        f"عدد التأليفات C({result.n},{result.k}) = {result.total_combinations}."
                    ),
                    "aek_state": _aek_state,
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
                    # V38.0: MODE_B (confusion) keeps pipeline alive for deep narrative.
                    # MODE_A terminates after the visual component (Text-Wall Muzzle).
                    # D-116: الاحتمالات = مُعلّم بصري حتمي كامل ⇒ terminate دائماً
                    # (حتى عند الحيرة) — لا سرد LLM (مصدر الغارباج). البصري هو البيداغوجيا.
                    "terminate_pipeline": True,
                    "routing_mode": _routing_mode,
                    "companion_text": _companion_text_for_focus(
                        "إليك الشرح البصري المفصل للتمرين خطوة بخطوة 🪄"
                    ),
                    "props": props,
                    "fallback_text": ("شجرة الاحتمالات (تعذّر عرض الرسم التفاعلي — هذا نص بديل)."),
                    "aek_state": _aek_state,
                }
            return None
        except Exception:
            logger.warning("_build_calculated_ui_failed", exc_info=True)
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # D-124 — مخرج الطوارئ الحتمي (Deterministic Escape Hatch):
    # كسر «حلقة الموت اللانهائية». بعد D-116/D-123 صار كل سؤال احتمالات يُنهي
    # دائماً إلى الكاروسيل البصري (terminate=True، صفر LLM). النتيجة الكارثية:
    # سؤال محدّد («كيف وجدنا 4 الحمراء؟») أو حيرة متكررة («لم أفهم»×N) يُعيدان
    # طباعة **نفس الكاروسيل** بلا تقدّم ولا إجابة — الطالب محاصَر. الحل (تشخيص
    # المالك CTO-grade): عداد محاولات + مخرج طوارئ ⇒ سؤال محدّد (فوراً) أو حيرة
    # ≥ 2 يكسران الكاروسيل ويقدّمان **شرحاً رياضياً مباشراً حتمياً** (محسوباً من
    # التمرين الرسمي عبر ProbabilityCalculatorSkill، history=None — D-123 — صفر
    # LLM، صفر هلوسة). استثناء مقصود ومُصرَّح من المالك لِـ doctrine السقراطي
    # (D-113/D-115): الطالب العالق يستحق المثال المحلول لكسر الحلقة.
    # ─────────────────────────────────────────────────────────────────────────

    #: D-124: علامات الحيرة المتكررة — **بلا «كيف» المجرّدة** (تكسر «كيف افهم
    #: السؤال الأول» الأولى، وهي سؤال عام يستحق الكاروسيل لا الشرح المباشر).
    _PROBABILITY_CONFUSION_MARKERS: tuple[str, ...] = (
        "لم أفهم",
        "لم افهم",
        "مفهمتش",
        "ما فهمت",
        "مافهمت",
        "ما افهم",
        "لا أفهم",
        "لا افهم",
        "مازلت",
        "ما زلت",
        "اشرح لي",
        "اشرحلي",
        "وضح لي",
        "وضحلي",
        "أين الشرح",
        "اين الشرح",
        "لا أعرف",
        "لا اعرف",
        "ماعرفت",
        "ما عرفت",
        "صعب",
        "أعد الشرح",
        "اعد الشرح",
    )

    @classmethod
    def _count_probability_confusion(
        cls, question: str, history_messages: list[dict[str, str]] | None
    ) -> int:
        """يَعُدّ رسائل الطالب الدالة على حيرة متكررة (السؤال الحالي + سجل المحادثة).

        حتمي، بلا I/O — نمط ``customer_chat._count_confusion_signals``. تكرار
        الحيرة (≥2) ⇒ الطالب عالق بعد رؤية الكاروسيل ⇒ مخرج الطوارئ. **بلا «كيف»
        المجرّدة** (D-124) كي لا يُحسب «كيف افهم السؤال الأول» الأول كحيرة. الرسالة
        التي هي علامة استفهام صرفة («؟») تُحسب حيرةً (الطالب يكرّرها أمام الكاروسيل).
        """
        texts: list[str] = [str(question or "")]
        for msg in history_messages or []:
            if isinstance(msg, dict) and msg.get("role") == "user":
                texts.append(str(msg.get("content") or ""))
        count = 0
        for text in texts:
            low = text.strip()
            if low in ("؟", "?", "؟؟", "??", "؟!", "!؟"):
                count += 1
                continue
            if any(marker in low for marker in cls._PROBABILITY_CONFUSION_MARKERS):
                count += 1
        return count

    @staticmethod
    def _detect_subpart_question(question: str) -> str | None:
        """يكشف سؤالاً محدّداً عن جزئية حسابية في تمرين الاحتمالات.

        يُرجِع: ``"red"``/``"green"``/``"white"`` (لون) | ``"total"`` (فضاء العينة
        C(11,3)) | ``"sum"`` (مجموع الحالات الملائمة 14) | ``None``. السؤال العام
        («كيف افهم السؤال الأول») ⇒ ``None`` (يبقى للكاروسيل البصري). D-124.
        """
        q = (question or "").lower()
        if any(m in q for m in ("حمراء", "الحمراء", "احمر", "الأحمر", "الاحمر", "حمر")):
            return "red"
        if any(m in q for m in ("خضراء", "الخضراء", "اخضر", "الأخضر", "الاخضر", "خضر")):
            return "green"
        if any(m in q for m in ("بيضاء", "البيضاء", "ابيض", "الأبيض", "الابيض", "بيض")):
            return "white"
        if any(m in q for m in ("165", "فضاء العينة", "العدد الكلي", "الفضاء", "c(11", "الكلي")):
            return "total"
        if any(
            m in q for m in ("14", "الملائمة", "الملاءمة", "نجمع", "لماذا نجمع", "الحالات الملائمة")
        ):
            return "sum"
        return None

    #: D-160 (ISS-126): علامات طلب شرح اشتقاق قيمة/خطوة («كيف حسبنا 4»، «اشرح كيف
    #: وصلنا لـ 10»، «من أين جاءت»). تُفرّق طلب الشرح عن محاولة الإجابة الرقمية.
    _STEP_EXPLAIN_MARKERS: tuple[str, ...] = (
        "كيف حسبنا",
        "كيف حسبت",
        "كيف نحسب",
        "كيف وجدنا",
        "كيف وصلنا",
        "كيف جاء",
        "من اين",
        "من أين",
        "اشرح",
        "اشرح لي",
        "وضح",
        "وضّح",
        "بين",
        "بيّن",
        "كيفاش",
        "علاش",
    )

    @classmethod
    def _detect_step_explanation(cls, question: str, combo) -> str | None:
        """D-160 (ISS-126): يكشف طلب شرح اشتقاق **خطوة/قيمة** ويربطه بجزئية.

        يحلّ الكارثة: «كيف حسبنا 4» (كيف اشتُقّت ``C(4,3)=4``) كان يسقط للإنقاذ النهائي
        المكرَّر لأن `_detect_subpart_question` يربط الألوان و14/165 **فقط** — لا القيم
        الملائمة 4/10. هذا الكاشف **data-driven** (يقرأ ``combo``، لا أرقاماً مُصلَّبة):
        يطابق أرقام السؤال ضد ``total_combinations``/``same_group_favorable`` وكل مجموعة
        (``favorable_combinations`` أو ``count``) ⇒ يعمل لأي تمرين لا هذا وحده.

        يُرجِع ``"red"``/``"green"``/``"white"``/``"total"``/``"sum"`` | ``None``. يشترط
        علامة شرح صريحة (`_STEP_EXPLAIN_MARKERS`) كي لا تُلتقَط محاولة إجابة رقمية
        («14 على 165» تبقى للتحقّق الرقمي S2، لا للشرح).
        """
        try:
            q = (question or "").lower()
            if not any(m in q for m in cls._STEP_EXPLAIN_MARKERS):
                return None
            # (أ) الكلمات اللونية / 14 / 165 — يعالجها الكاشف القائم مباشرةً.
            word_part = cls._detect_subpart_question(question)
            if word_part is not None:
                return word_part
            # (ب) مطابقة data-driven لأرقام السؤال ضد قيم combo.
            nums = {int(n) for n in re.findall(r"\d+", q)}
            if not nums:
                return None
            if int(getattr(combo, "total_combinations", -1)) in nums:
                return "total"
            if int(getattr(combo, "same_group_favorable", -1)) in nums:
                return "sum"
            for g in getattr(combo, "groups", []) or []:
                gfav = int(getattr(g, "favorable_combinations", -1))
                gcount = int(getattr(g, "count", -1))
                if gfav in nums or gcount in nums:
                    color = getattr(g, "color", None)
                    if color in ("red", "green", "white"):
                        return color
            return None
        except Exception:  # pragma: no cover - fail-safe
            return None

    @classmethod
    def _detect_naming_question(cls, question: str, combo) -> bool:
        """D-162 (ISS-128): يكشف سؤال التسمية عن قيم خطوات التمرين — data-driven.

        «ماذا نسمي حساب 4 و 10 لم افهمها؟» يطلب **اسم** العملية (التوافيق C(n,k))،
        لا نتيجتها. الشرط: علامة تسمية (`_NAMING_MARKERS`) **+** (أرقام السؤال ⊆
        قيم خطوات ``combo`` — favs/same/total/n/k/counts — **أو** ذكر الحساب/العملية).
        الأرقام من المحرك الرمزي حصراً ⇒ يعمل لأي تمرين (ملايير التمارين).
        """
        try:
            q = (question or "").lower()
            if not any(m in q for m in cls._NAMING_MARKERS):
                return False
            nums = cls._extract_answer_numbers(q)
            if nums:
                values = {
                    int(getattr(combo, "total_combinations", -1)),
                    int(getattr(combo, "same_group_favorable", -1)),
                    int(getattr(combo, "n", -1)),
                    int(getattr(combo, "k", -1)),
                }
                for g in getattr(combo, "groups", []) or []:
                    values.add(int(getattr(g, "favorable_combinations", -1)))
                    values.add(int(getattr(g, "count", -1)))
                return nums <= values
            return any(w in q for w in ("حساب", "الحساب", "العملية", "الطريقة", "c("))
        except Exception:  # pragma: no cover - fail-safe
            return False

    @classmethod
    def _build_naming_answer(cls, combo, pending_focus: str | None) -> str | None:
        """D-162 (ISS-128): يُجيب سؤال التسمية بالاسم — حتمي، صفر LLM.

        تعريف **التوافيق** من ``PROPERTY_REGISTRY["combinations"]`` (مصدر واحد —
        D-131 data-not-code) + ربط بقيمة واحدة عبر ``_fmt_comb`` (LaTeX، يَنجو من
        حجب D-113 بنيوياً — D-154) + **إعادة طرح السؤال المعلّق** (نصّه يطابق
        `_STEP_QUESTION_MARKERS` فيبقى pending مشتقاً صحيحاً) — لا تقدّم زائف.
        """
        try:
            definition = None
            with contextlib.suppress(Exception):
                from app.services.skills.semantic_property_skill import PROPERTY_REGISTRY

                _spec = PROPERTY_REGISTRY.get("combinations")
                definition = getattr(_spec, "definition", None) if _spec else None
            if not definition:
                definition = (
                    "هذا الحساب نسمّيه **التوافيق** (Combinations) ويُرمز له $C_{n}^{k}$: "
                    "عدد طرق اختيار k عناصر من بين n عنصراً **دون اهتمام بالترتيب**."
                )
            parts = [definition]
            _groups = [
                g for g in (getattr(combo, "groups", []) or []) if getattr(g, "is_possible", False)
            ]
            if _groups:
                _g0 = _groups[0]
                parts.append(
                    "مثلاً القيمة التي وجدناها لهذه المجموعة هي عدد التوافيق: "
                    + cls._fmt_comb(
                        int(_g0.count),
                        int(getattr(combo, "k", 3)),
                        int(_g0.favorable_combinations),
                    )
                )
            if pending_focus == "denominator":
                parts.append(
                    "والآن نعود لسؤالنا: كم عدد كل الطرق الممكنة لسحب "
                    f"{int(getattr(combo, 'k', 3))} كرات من {int(getattr(combo, 'n', 0))}؟"
                )
            elif pending_focus == "ratio":
                parts.append("والآن نعود لسؤالنا: لديك البسط والمقام — كيف تُكوّن منهما الاحتمال؟")
            return "\n\n".join(parts)
        except Exception:  # pragma: no cover - fail-safe
            return None

    #: D-125: أفعال إجرائية — «لماذا/ليش» معها تبقى سؤالاً حسابياً (قوالب D-124)،
    #: لا مفاهيمياً («لماذا نجمع»، «لماذا لا نحسب الأبيض»). تحفّظ المالك رقم 3.
    _PROCEDURAL_VERBS: tuple[str, ...] = (
        "نجمع",
        "نحسب",
        "نحسبها",
        "نضرب",
        "نستخرج",
        "نستخدم",
        "لا نحسب",
        "كيف وجدنا",
        "كيف حصلنا",
        "كيف نحسب",
    )

    @classmethod
    def _detect_conceptual_question(cls, question: str) -> bool:
        """D-125: هل السؤال مفاهيمي/مقارنة (يطلب المعنى/العلاقة لا خطوات الحساب)؟

        يحل «متلازمة الردود المعلبة»: «ما الفرق بين 165 و 14» يطلب العلاقة (البسط
        مقابل المقام)، لا حساب 165. أوسع من الكلمات الحرفية (تحفّظ المالك 1): يشمل
        الدارجة «ليش»/«علاش»، و«نفسر»/«المقصود»/«الناتج»/«نقسم/النسبة». «لماذا/ليش»
        + فعل إجرائي ⇒ ليس مفاهيمياً (تحفّظ 3)؛ أي علامة قوية ⇒ مفاهيمي حتى مع فعل
        إجرائي (الهجين، تحفّظ 2).
        """
        q = (question or "").lower()
        # علامات مفاهيمية قوية ⇒ مفاهيمي دائماً (تهزم حتى الأفعال الإجرائية — الهجين).
        strong = (
            "الفرق",
            "الاختلاف",
            "العلاقة",
            "الرابط",
            "مقارنة",
            "قارن",
            "ما يميز",
            "الهدف",
            "الغرض",
            "الغاية",
            "الفائدة",
            "ما فائدة",
            "فائدة",
            "ما معنى",
            "معنى",
            "ماذا يعني",
            "ماذا تعني",
            "المقصود",
            "ما المقصود",
            "نفسر",
            "التفسير",
            "كيف نفسر",
            "النسبة",
            "نقسم",
            "القسمة",
            "البسط والمقام",
            "بسط ومقام",
            # D-162 (ISS-128): نية التسمية («ماذا نسمي حساب 4 و 10؟») مفاهيمية —
            # الطالب يطلب اسم العملية (التوافيق)، لا خطوات الحساب.
            "نسمي",
            "ما اسم",
            "تسمية",
        )
        if any(m in q for m in strong):
            return True
        # «ليش/لماذا» + رقم/مفهوم وبلا فعل إجرائي ⇒ مفاهيمي («ليش 14؟»). تحفّظ 3.
        why = ("ليش", "لماذا", "علاش", "وعلاش", "علاه")
        if any(w in q for w in why):
            if any(p in q for p in cls._PROCEDURAL_VERBS):
                return False
            concept_ref = ("14", "165", "الناتج", "البسط", "المقام")
            if any(c in q for c in concept_ref):
                return True
        return False

    @staticmethod
    def _fmt_comb(c: int, k: int, fav: int) -> str:
        r"""يبني توسيع المضروب الحتمي بصيغة LaTeX (ISS-121 / D-154).

        مثال: ``_fmt_comb(4, 3, 4)`` ⇒ ``"$C_{4}^{3} = \dfrac{4\times 3\times 2}{3\times 2\times 1} = 4$"``.
        LaTeX ⇒ KaTeX يُصيّرها LTR-معزولة داخل فقرات RTL (يقتل بعثرة bidi التي
        شوّهت «(5×4×3)/(3×2×1)» على الهاتف)، وصيغة ``C_{n}^{k}`` (بلا قوسين بعد C)
        تَنجو بنيوياً من حجب D-113 (`_FINAL_RESULT_RE` يتطلب ``C(...)=عدد``).
        """
        if k < 1 or c < k:
            return f"$C_{{{c}}}^{{{k}}} = {fav}$"
        num = r"\times ".join(str(c - i) for i in range(k))
        den = r"\times ".join(str(k - i) for i in range(k))
        return f"$C_{{{c}}}^{{{k}}} = \\dfrac{{{num}}}{{{den}}} = {fav}$"

    @classmethod
    def _build_probability_direct_explanation(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
        *,
        forced_subpart: str | None = None,
    ) -> str | None:
        """D-124: شرح رياضي مباشر حتمي لتمرين الاحتمالات (يكسر حلقة الكاروسيل).

        D-160 (ISS-126): ``forced_subpart`` (اختياري) — يتجاوز `_detect_subpart_question`
        فيسمح لِـ `_cognitive_turn` بتوجيه الشرح لجزئية كشفها كاشف data-driven من قيمة
        السؤال (مثل «كيف حسبنا 4» ⇒ «red»)؛ يُعيد استخدام هذا الكود التعليمي كما هو.

        يُحمّل التمرين الرسمي المُفهرَس (D-123: ``history=None`` ⇒ مناعة من تلوّث
        الـ history)، يحلّله عبر ``ProbabilityCalculatorSkill`` (مخرَج
        ``CombinationsModelOutput``)، ثم يُنسِّق الجزئية المطلوبة (لون/فضاء/مجموع)
        أو الاشتقاق الكامل — **صفر LLM، صفر هلوسة**. يُرجِع ``None`` إن لم يكن تمرين
        احتمالات معروفاً (topic-safe) أو تعذّر الحساب. النصّ مُصمَّم لِيَنجو من حجب
        الإجابة (D-113): يتجنّب ``P(...)=عدد``/``\\boxed``/«النتيجة/إذن … = عدد».
        """
        try:
            from app.services.capabilities.arabic_normalize import primary_canonical_topic
            from app.services.capabilities.exercise_retrieval import (
                ExerciseRetrievalRequest,
                detect_exercise_retrieval,
                load_exercise_questions_only,
            )
            from app.services.skills.probability_skill import (
                CombinationsModelOutput,
                ProbabilityCalculatorSkill,
                ProbabilityInput,
            )

            # topic-safe: طلب موضوع آخر صريح (دوال/أعداد مركبة) ⇒ لا شرح احتمالات.
            _canonical = primary_canonical_topic(question)
            if _canonical is not None and _canonical.canonical_id != "probability":
                return None

            # تحميل التمرين الرسمي المُفهرَس (history-immune — D-123).
            # ISS-120 (D-153): أسئلة-فقط — نثر الحل النموذجي («تحمل الرقم 0 …
            # وعددها 3 كرات») يولِّد كياناً وهمياً يُفسد فضاء العينة (14 بدل 11).
            _decision = detect_exercise_retrieval(
                ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024"),
                history_messages=history_messages,
            )
            if not (_decision.recognized and _decision.matched_entry):
                return None
            _official = load_exercise_questions_only(_decision.matched_entry)
            if not _official:
                return None

            # تحليل حتمي من المحتوى الرسمي وحده (بلا سؤال الطالب ⇒ غير حائر ⇒
            # CombinationsModelOutput بالمجموعات، لا قصة بصرية deep_dive).
            skill = ProbabilityCalculatorSkill()
            result = skill.analyze(ProbabilityInput(question=_official, history=None))
            if not isinstance(result, CombinationsModelOutput):
                return None

            n = result.n
            k = result.k
            total = result.total_combinations
            groups = list(result.groups)
            same = result.same_group_favorable

            # D-125: السؤال المفاهيمي/المقارنة («ما الفرق بين 165 و 14»، «ما الهدف
            # من 14») يطلب **العلاقة** لا خطوات الحساب. يُفحَص **قبل** مطابقة الأرقام
            # كي لا يطبع قالب الحساب (متلازمة الردود المعلبة). يهزم مطابقة الأرقام دائماً.
            if cls._detect_conceptual_question(question):
                return cls._format_conceptual_relationship(question, n, k, total, same, groups)

            subpart = forced_subpart or cls._detect_subpart_question(question)

            def _group_for_color(color: str) -> object | None:
                for g in groups:
                    if (g.color or "") == color:
                        return g
                return None

            # ── جزئية لون واحد ────────────────────────────────────────────────
            if subpart in ("red", "green", "white"):
                g = _group_for_color(subpart)
                if g is not None:
                    if g.is_possible:
                        return (
                            f"## كيف نحسب تأليفات {g.label}\n\n"
                            f"عدد {g.label} في الكيس: {g.count}، ونريد اختيار {k} منها "
                            f"دفعةً واحدة (اختيار غير مرتّب). نطبّق قانون التوافيق:\n\n"
                            f"{cls._fmt_comb(g.count, k, g.favorable_combinations)}\n\n"
                            f"أي توجد {g.favorable_combinations} طريقة لاختيار {k} كرات "
                            f"من نفس هذا اللون — وهي إحدى مكوّنات الحالات الملائمة."
                        )
                    return (
                        f"## لماذا هذا اللون مستحيل\n\n"
                        f"عدد {g.label} في الكيس: {g.count}، ونحتاج اختيار {k}. بما أن "
                        f"{g.count} أصغر من {k}، لا يمكن سحب {k} كرات من هذا اللون معاً — "
                        f"لذلك عدد تأليفاته صفر، وهذا اللون لا يساهم في الحالات الملائمة."
                    )

            # ── فضاء العينة C(n,k) ────────────────────────────────────────────
            if subpart == "total":
                return (
                    f"## فضاء العينة C({n},{k})\n\n"
                    f"نسحب {k} كرات من {n} دفعةً واحدة. السحب الآني = اختيار غير مرتّب، "
                    f"فعدد كل الإمكانات هو:\n\n"
                    f"{cls._fmt_comb(n, k, total)}\n\n"
                    f"أي يوجد {total} طريقة مختلفة لاختيار {k} كرات من الكيس — وهو مقام الاحتمال."
                )

            # ── مجموع الحالات الملائمة + الاحتمال ─────────────────────────────
            possible = [g for g in groups if g.is_possible]
            favs = " + ".join(str(g.favorable_combinations) for g in possible)
            if subpart == "sum":
                lines = "\n".join(
                    (
                        f"- {g.label}: {cls._fmt_comb(g.count, k, g.favorable_combinations)}"
                        if g.is_possible
                        else f"- {g.label}: مستحيل (العدد {g.count} أصغر من {k})"
                    )
                    for g in groups
                )
                return (
                    f"## كيف نجمع لنحصل على الحالات الملائمة\n\n"
                    f"الحدث «{k} كرات من نفس اللون» يتحقق بأيّ لون ممكن:\n\n"
                    f"{lines}\n\n"
                    f"نجمع الحالات الممكنة فقط: ${favs} = {same}$\n\n"
                    # ISS-121 (D-154): صفر كشف للنتيجة — الطالب يركّب النسبة بنفسه.
                    f"وبهذا أصبح لديك البسط. ركّب الاحتمال **بنفسك**: البسط على "
                    f"المقام {total} — فما قيمة P(A)؟"
                )

            # ── الاشتقاق الكامل (حيرة متكررة، بلا جزئية محدّدة) ────────────────
            full_lines = "\n".join(
                (
                    f"   - {g.label}: {cls._fmt_comb(g.count, k, g.favorable_combinations)}"
                    if g.is_possible
                    else f"   - {g.label}: مستحيل (العدد {g.count} أصغر من {k})"
                )
                for g in groups
            )
            return (
                f"## الحل الكامل خطوة بخطوة\n\n"
                f"1) فضاء العينة — نسحب {k} كرات من {n} دفعةً واحدة:\n\n"
                f"   {cls._fmt_comb(n, k, total)}\n\n"
                f"2) الحالات الملائمة (الحدث: {k} كرات من نفس اللون) — لكل لون على حدة:\n\n"
                f"{full_lines}\n\n"
                f"3) نجمع الحالات الممكنة فقط: ${favs} = {same}$\n\n"
                # ISS-121 (D-154): صفر كشف للنتيجة — الخطوة الأخيرة توليد لا تلقين.
                f"4) والآن الخطوة الأخيرة **لك**: ركّب الاحتمال بنفسك — البسط على "
                f"المقام. فما قيمة P(A) التي تحصل عليها؟"
            )
        except Exception:
            logger.warning("_build_probability_direct_explanation_failed", exc_info=True)
            return None

    @classmethod
    async def _build_probability_computational_answer(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
    ) -> tuple[str, str] | None:
        """D-143: إجابة حتمية مباشرة لأسئلة الاحتمالات الحسابية — صفر LLM، topic-safe.

        يُجيب صراحةً (قبل سُلّم الحادثة A): (1) «لماذا نضرب 11×10×9» ⇒ مبدأ العدّ + القسمة
        على !3 ؛ (2) «كيف حصلنا على 56» / الحادثة B (جداء فردي) ⇒ C(عدد الفردية,k)/C(n,k)
        من أرقام الكرات الرسمية ؛ (3) الحوادث غير المنمذجة بعد (C/D/X/الأمل/الشرطي) ⇒
        **تأجيل حتمي صادق** يسمّي الحدث ويُبعده صراحةً عن الحادثة A — **بلا أيّ رقم من LLM
        وبلا أرقام الحادثة A**. يُرجِع ``(text, event)`` أو ``None`` (فيتولّى المسار القائم
        الحادثة A / الحيرة / التحية). نقد المالك #1: لا باب LLM في مسار الرياضيات.
        """
        try:
            from math import comb

            from app.services.capabilities.arabic_normalize import primary_canonical_topic
            from app.services.capabilities.exercise_retrieval import (
                ExerciseRetrievalRequest,
                detect_exercise_retrieval,
                load_exercise_content,
                load_exercise_questions_only,
            )
            from app.services.skills.probability_skill import (
                CombinationsModelOutput,
                ProbabilityCalculatorSkill,
                ProbabilityInput,
            )

            raw = (question or "").strip()
            # حارس اللصق/الاسترجاع: سؤال الطالب قصير؛ لصق التمرين كامل (يحوي «56/فردي/زوجي»)
            # يجب أن يتولّاه الاسترجاع المُفهرَس، لا هذا المسار.
            if len(raw) > 300:
                return None
            q = raw.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).lower()

            # topic-safe: طلب موضوع آخر صريح (دوال/أعداد مركبة) ⇒ لا شرح احتمالات.
            _canonical = primary_canonical_topic(question)
            if _canonical is not None and _canonical.canonical_id != "probability":
                return None

            # تصنيف السؤال الحسابي (حوادث الجداء قبل مبدأ العدّ لمنع التباس «نضرب»).
            is_event_b = (
                "56" in q
                or "p(b" in q
                or "الحادثة b" in q
                or ("جداء" in q and ("فردي" in q or "الفردي" in q))
            )

            # D-143 Phase 1.5: لا نعترض الأسئلة التعريفية/الاستفسارية ("ما هو"، "لم أفهم") لكي تلتقطها
            # الطبقة الدلالية (D-132) ولا تُختطَف كإجابات حسابية مؤجلة.
            from app.services.skills.semantic_property_skill import get_semantic_property_skill
            from app.services.skills.student_state_skill import (
                StudentStateInput,
                get_student_state_skill,
            )

            _sps = get_semantic_property_skill()
            _state = get_student_state_skill().read(
                StudentStateInput(question=question, history=history_messages)
            )
            _confused = (
                _state.primary_intent == "confusion" or "confusion" in _state.secondary_signals
            )
            _wants_def = (
                _sps.is_definitional(question)
                or _state.primary_intent == "definition"
                or (_confused and _sps.interpret(question) is not None)
            )

            _compute = any(
                m in q
                for m in (
                    "احسب",
                    "أحسب",
                    "كم ",
                    "اوجد",
                    "أوجد",
                    "بين ان",
                    "بيّن أن",
                    "استنتج",
                    "كيف",
                    "لماذا",
                )
            ) or any(
                m in q
                for m in (
                    "56",
                    "p(b",
                    "الحادثة b",
                    "جداء",
                    "معدوم",
                    "بدون ارجاع",
                    "التوالي",
                    "p(c",
                    "p_a",
                    "e(x",
                )
            )

            if _wants_def and not _compute:
                return None

            uncovered: tuple[str, str] | None = None
            if ("جداء" in q and ("زوجي" in q or "الزوجي" in q)) or "p(c" in q or "الحادثة c" in q:
                uncovered = ("event_c", "الحادثة C (جداء أرقامها زوجي)")
            elif (
                "معدوم" in q
                or "الحادثة d" in q
                or "بدون ارجاع" in q
                or "بدون إرجاع" in q
                or ("التوالي" in q and "ارجاع" in q)
            ):
                uncovered = ("event_d", "الحادثة D (السحب على التوالي بدون إرجاع — جداء معدوم)")
            elif "المتغير العشوائي" in q or "قانون الاحتمال" in q or "قانون احتمال" in q:
                uncovered = ("random_var", "المتغير العشوائي X")
            elif "الامل" in q or "الأمل" in q or "e(x" in q:
                uncovered = ("expected", "الأمل الرياضي E(X)")
            elif "الشرطي" in q or "شرطي" in q or "p_a" in q or "pa(" in q:
                uncovered = ("conditional", "الاحتمال الشرطي P_A(B)")
            # مبدأ العدّ: «نضرب/ضربنا/الترتيب/ثلاثة أرقام» وليس عن جداء أرقام الكرات (B/C/D).
            mult_markers = (
                "نضرب",
                "ضربنا",
                "نضربها",
                "11×10×9",
                "11x10x9",
                "الترتيب",
                "ثلاثة ارقام",
                "ثلاثة أرقام",
                "ثلاث ارقام",
            )
            is_combinations = any(m in q for m in mult_markers) and "جداء" not in q

            if not (is_event_b or is_combinations or uncovered is not None):
                return None

            # تحميل التمرين الرسمي المُفهرَس (history-immune — D-123).
            _decision = detect_exercise_retrieval(
                ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024"),
                history_messages=history_messages,
            )
            if not (_decision.recognized and _decision.matched_entry):
                return None
            # ISS-120 (D-153): الاستخراج/التكافؤ من أسئلة-فقط؛ الحل الكامل
            # (`_official`) يبقى حصراً لمرجع RAG-Grounded LLM أدناه (D-145).
            _official = load_exercise_content(_decision.matched_entry)
            _official_qonly = load_exercise_questions_only(_decision.matched_entry)
            if not _official or not _official_qonly:
                return None
            _combo = ProbabilityCalculatorSkill().analyze(
                ProbabilityInput(question=_official_qonly, history=None)
            )
            if not isinstance(_combo, CombinationsModelOutput):
                return None
            n, k, total = _combo.n, _combo.k, _combo.total_combinations

            # (1) الحادثة B — حتمي من أرقام الكرات الرسمية (Stage 1).
            if is_event_b:
                parity = ProbabilityCalculatorSkill.number_parity_counts(_official_qonly)
                if parity is None or parity.get("total", 0) != n:
                    return None
                odd = parity["odd"]
                fav = comb(odd, k)
                text = (
                    "## الحالات الملائمة للحادثة B (جداء الأرقام فردي)\n\n"
                    "جداء ثلاثة أعداد يكون **فردياً** فقط إذا كان كلّ عددٍ منها فردياً — يكفي "
                    "عددٌ زوجيّ واحد ليُصبح الجداء زوجياً. إذن نختار الكرات الثلاث من الكرات ذات "
                    f"الأرقام الفردية فقط.\n\nعدد الكرات ذات رقمٍ فردي في الكيس: {odd}، نختار "
                    f"منها {k}:\n\n{cls._fmt_comb(odd, k, fav)}\n\nوفضاء العيّنة هو كلّ طرق سحب "
                    f"{k} من {n}:\n\n{cls._fmt_comb(n, k, total)}\n\nفعدد الحالات الملائمة "
                    f"للحادثة B هو {fav} من أصل {total}."
                )
                return (text, "event_b")

            # (2) مبدأ العدّ (لماذا نضرب 11×10×9) — حتمي.
            if is_combinations:
                num = "×".join(str(n - i) for i in range(k))
                den = "×".join(str(k - i) for i in range(k))
                prod = 1
                for i in range(k):
                    prod *= n - i
                text = (
                    f"## لماذا نضرب {num}\n\n"
                    f"عند سحب {k} كرات من {n}، نَعُدّ بمبدأ الضرب: للكرة الأولى {n} احتمالاً، "
                    f"وبعد سحبها تبقى {n - 1} للثانية، ثمّ {n - 2} للثالثة — فعدد الترتيبات هو "
                    f"{num} = {prod}.\n\nلكنّ السحب **دفعةً واحدة** لا يهتمّ بالترتيب (نفس الكرات "
                    f"الثلاث بأيّ ترتيب = سحبةٌ واحدة)، وكلّ مجموعة من {k} كرات تُرتَّب بـ {den} "
                    f"طريقة، لذلك نقسم عليها:\n\n{cls._fmt_comb(n, k, total)}\n\nفنحصل على عدد "
                    f"المجموعات غير المرتّبة، وهو مقام الاحتمال. (لاحظ: هذا عدّ طرق السحب، وهو "
                    f"يختلف عن **جداء أرقام** الكرات في الحوادث B وC وD.)"
                )
                return (text, "combinations")

            # (3) حوادث غير منمذجة (C/D/X/E(X)/Conditional) ⇒ RAG-Grounded LLM
            # D-145: بدلاً من التأجيل، نمرر التمرين والحل النموذجي للـ LLM ليشرحه بيداغوجياً دون هلوسة.
            ev_id, ev_label = uncovered  # type: ignore[misc]

            try:
                import asyncio

                from app.core.ai_gateway import get_ai_client

                system_prompt = (
                    "أنت معلّم رياضيات جزائري متميز تشرح لطلبة البكالوريا. "
                    "مهمتك: الإجابة على سؤال الطالب بالاستناد **حصرياً** على النص المرفق (التمرين مع الإجابة النموذجية المرجعية). "
                    "ممنوع منعاً باتاً اختراع أرقام أو كسور غير موجودة في الحل النموذجي. "
                    "اقرأ الإجابة الخاصة بالحدث الذي يسأل عنه الطالب (مثلا الحادثة D أو المتغير X أو الأمل الرياضي)، واشرح خطواتها بتفصيل بيداغوجي. "
                    "استخدم LaTeX للمعادلات. لا تبدأ بكلمات مثل 'حسنا' أو 'أفهمك'. أعط الشرح مباشرة بصيغة المخاطب."
                )
                user_prompt = (
                    f"المرجع (التمرين والحل النموذجي):\n{_official}\n\n"
                    f"سؤال الطالب يخص: {ev_label}\n"
                    f"السؤال الفعلي: {question}\n\n"
                    "اشرح هذا الجزء للطالب خطوة بخطوة بالاستناد للمرجع فقط."
                )

                ai_client = get_ai_client()
                raw = await asyncio.wait_for(
                    ai_client.send_message(system_prompt, user_prompt, temperature=0.2),
                    timeout=15.0,
                )
                if raw and isinstance(raw, str) and raw.strip():
                    from app.services.skills.content_integrity_skill import _strip_garbage_markers

                    text = _strip_garbage_markers(raw.strip())
                    # Apply optional pedagogical redaction if needed, but for mathematical explanations of new parts,
                    # we often want to show the steps.
                    # text, _ = redact_final_answers(text, support_level=5)

                    if text:
                        return (text, ev_id)
            except Exception as llm_err:
                import logging

                logging.getLogger("orchestrator-client").warning(
                    f"RAG LLM fallback failed: {llm_err}", exc_info=True
                )

            # Fallback to the old deferral message if LLM fails
            text = (
                f"## {ev_label}\n\n"
                f"سؤالك يخصّ {ev_label}. حسابها دقيق ويحتاج للتركيز. لنبدأ: ما المُعطى الذي تريد أن نُوضّحه أولاً فيها؟"
            )
            return (text, ev_id)
        except Exception:
            logger.warning("_build_probability_computational_answer_failed", exc_info=True)
            return None

    @classmethod
    def _probability_computational_variant(
        cls, event: str, history_messages: list[dict[str, str]] | None
    ) -> str | None:
        """D-143 (RC-4): تمثيلٌ حتميّ **مختلف** للسؤال الحسابي نفسه عند تكراره — تخصيصٌ
        بيداغوجي لا إعادة حرفية (نقد المالك #2). صفر LLM. يُرجِع None عند أيّ تعذّر.
        """
        try:
            # الحوادث المؤجَّلة: خطوةٌ عمليّة مختلفة (لا تحتاج تحميل الأرقام).
            if event not in ("combinations", "event_b"):
                return (
                    "## لنبدأ خطوةً عمليّة\n\n"
                    "لنحسب هذه الحادثة بدقّة نحتاج أوّلاً تحديد الكرات المعنيّة بها (حسب أرقامها "
                    "أو نوع السحب). أخبرني: هل نبدأ بعدّ الكرات التي تُحقّق الشرط، أم بفضاء العيّنة "
                    "(كلّ طرق السحب)؟"
                )

            from math import comb

            from app.services.capabilities.exercise_retrieval import (
                ExerciseRetrievalRequest,
                detect_exercise_retrieval,
                load_exercise_questions_only,
            )
            from app.services.skills.probability_skill import (
                CombinationsModelOutput,
                ProbabilityCalculatorSkill,
                ProbabilityInput,
            )

            _decision = detect_exercise_retrieval(
                ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024"),
                history_messages=history_messages,
            )
            if not (_decision.recognized and _decision.matched_entry):
                return None
            # ISS-120 (D-153): أسئلة-فقط قبل استخراج الكيانات.
            official = load_exercise_questions_only(_decision.matched_entry)
            if not official:
                return None
            combo = ProbabilityCalculatorSkill().analyze(
                ProbabilityInput(question=official, history=None)
            )
            if not isinstance(combo, CombinationsModelOutput):
                return None
            n, k, total = combo.n, combo.k, combo.total_combinations

            if event == "combinations":
                return (
                    "## بمثالٍ ملموس\n\n"
                    "لنُسمِّ ثلاث كرات: أ، ب، ج. ترتيبُها يُعطي 6 صفوف: (أ،ب،ج)، (أ،ج،ب)، "
                    "(ب،أ،ج)، (ب،ج،أ)، (ج،أ،ب)، (ج،ب،أ) — أي 3×2×1=6 ترتيباتٍ لنفس المجموعة "
                    "الواحدة. لكنّ السحب دفعةً واحدة لا يميّز بينها فهي سحبةٌ واحدة. لذلك بعد عدّ "
                    f"الترتيبات {n}×{n - 1}×{n - 2} نقسم على 3!=6 لنُلغي تكرار الترتيب، فيتبقّى عدد "
                    f"المجموعات {cls._fmt_comb(n, k, total)}."
                )

            # event_b — صياغةٌ بديلة (تركيز على «لا رقم زوجي»).
            parity = ProbabilityCalculatorSkill.number_parity_counts(official)
            if parity is None or parity.get("total", 0) != n:
                return None
            odd = parity["odd"]
            fav = comb(odd, k)
            return (
                "## بطريقةٍ أخرى للحادثة B\n\n"
                "جداء الأرقام فردي ⟺ لا يدخل فيه أيّ رقمٍ زوجي (رقمٌ زوجيٌّ واحد يجعل الجداء "
                f"زوجياً). فننظر فقط إلى الكرات ذات الأرقام الفردية وعددها {odd}، ونعدّ طرق "
                f"اختيار {k} منها: {cls._fmt_comb(odd, k, fav)}؛ وكلّ طرق السحب "
                f"{cls._fmt_comb(n, k, total)}. فالحالات الملائمة {fav} من {total}."
            )
        except Exception:
            logger.warning("_probability_computational_variant_failed", exc_info=True)
            return None

    @staticmethod
    def _probability_computational_advance_prompt() -> str:
        """D-143 (RC-4): مُوجِّه تقدّمٍ نهائيّ حين تُستنفَد التمثيلات — لا إعادة حرفية."""
        return (
            "## لنُطبّق معاً\n\n"
            "شرحنا الفكرة بأكثر من طريقة — لِنُثبّتها بالحساب على جزءٍ محدّد. أيّهما تريد أن "
            "نُفصّل الآن: عدّ كلّ طرق السحب (المقام)، أم عدّ الحالات الملائمة لحادثةٍ بعينها؟"
        )

    @classmethod
    def _format_conceptual_relationship(
        cls,
        question: str,
        n: int,
        k: int,
        total: int,
        same: int,
        groups: list,
    ) -> str:
        """D-125: شرح العلاقة الحواري القصير (المقام مقابل البسط) — حتمي، لا حساب.

        يحل «متلازمة الردود المعلبة»: «ما الفرق بين 165 و 14» يطلب المعنى. المخرج
        ≤3 أسطر جوهرية (تحفّظ المالك 4 — لا فقرة فلسفية). الهجين (وُجد فعل حسابي
        «كيف حصلنا/نحسب/وجدنا») ⇒ سطر حسابي **واحد** منفصل عبر ``_fmt_comb`` (يَنجو
        من حجب D-113). redaction-safe: لا «P(...)=عدد»/«\\boxed»/«خلاصة … = عدد».
        """

        def _bare(label: str) -> str:
            return label.replace("كرة ", "", 1).strip() or label

        possible = [g for g in groups if getattr(g, "is_possible", True)]
        impossible = [g for g in groups if not getattr(g, "is_possible", True)]
        favs_parts = " + ".join(f"{g.favorable_combinations} لل{_bare(g.label)}" for g in possible)
        imp_note = ""
        if impossible:
            names = " و".join(f"ال{_bare(g.label)}" for g in impossible)
            imp_note = f"؛ و{names} مستحيلة (عددها أقل من {k})"

        body = (
            f"## العلاقة بين {total} و {same} (المقام والبسط)\n\n"
            f"**{total}** هو عدد كل الطرق الممكنة لسحب {k} كرات مهما كان لونها — "
            f"هذا هو **المقام** (ساحة كل ما يمكن أن يحدث).\n\n"
            f"**{same}** هو عدد الطرق التي تحقق «{k} من نفس اللون» فقط "
            f"({favs_parts}{imp_note}) — هذا هو **البسط** (الحالات التي تنجح).\n\n"
            f"فالاحتمال هو نسبة البسط إلى المقام: {same} من كل {total}."
        )

        # الهجين (تحفّظ المالك 2): إن طلب الطالب الحساب أيضاً، سطر حسابي واحد فقط.
        ql = (question or "").lower()
        if any(v in ql for v in ("كيف حصلنا", "كيف نحسب", "كيف وجدنا", "احسب", "الحساب")):
            favs_sum = " + ".join(str(g.favorable_combinations) for g in possible)
            body += (
                f"\n\nوللتذكير بالحساب فقط: {cls._fmt_comb(n, k, total)}، و {favs_sum} = {same}."
            )
        return body

    # ─────────────────────────────────────────────────────────────────────────
    # D-127 — المعمارية الإدراكية العصبية-الرمزية (Layers 3/4/5):
    # استجابة مدفوعة بالمفهوم (لا بالصياغة) + تصعيد سقراطي مضاد للتكرار. كل صياغات
    # المفهوم الواحد → استجابة واحدة؛ نفس المفهوم مرّتين → سؤال سقراطي لا تكرار.
    # الأرقام من المحرك الرمزي (الطبقة 3، صفر LLM). التشخيص من الطبقة 1 (ConceptDiagnosisSkill).
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _is_prob_context(text: str) -> bool:
        """سياق احتمالات (لتقييد استدعاء LLM التشخيص على الاحتمالات فقط)."""
        t = text or ""
        return any(
            m in t
            for m in (
                "كرات",
                "كرة",
                "كيس",
                "احتمال",
                "سحب",
                "نسحب",
                "البسط",
                "المقام",
                "p(a",
                "p(b",
                "165",
                "14",
                # D-159: مفردات تمرين الاحتمالات (أسئلة الحادثة A/B بلا ذكر الكيس صراحةً).
                "الحادثة",
                "الفردية",
            )
        )

    @staticmethod
    def _norm_for_dedup(text: str) -> str:
        """D-142 (1B) + ISS-121 (D-154): تطبيع نصّ للمقارنة على التكرار — محايد للحجب.

        النسخة المحفوظة (history + `last_step_emitted`) تمرّ عبر حجب D-113
        («14» ⇒ «؟») بينما المبثوثة كاملة الأرقام ⇒ حارس التكرار كان يَعمى عن
        تحويل الحجب فيبثّ الحل المكرَّر (كارثة الترانسكريبت). نستبدل مقاطع
        الأرقام و«؟/?» بعنصر نائب موحّد فتتطابق النسختان بنيوياً.
        """
        try:
            from app.services.capabilities.arabic_normalize import normalize_ar

            base = normalize_ar(text or "")
        except Exception:  # pragma: no cover - fail-safe
            base = (text or "").strip().lower()
        return re.sub(r"[\d؟?]+", "#", base)

    @classmethod
    def _recently_emitted(
        cls,
        candidate: str,
        history_messages: list[dict[str, str]] | None,
        *,
        lookback: int = 6,
        threshold: float = 0.8,
    ) -> bool:
        """D-142 (1B): هل بُثّ نصّ شبيه بـ ``candidate`` في رسائل المساعد الأخيرة؟

        حارس تكرار عام: احتواء أو تداخل رموز ≥ ``threshold`` مع رسالة مساعد سابقة ⇒ True،
        فيُصعّد المُنادي إلى الرُّتبة التالية بدل الإعادة الحرفية (يكسر كارثة التكرار ×3).
        """
        cand = cls._norm_for_dedup(candidate)
        cand_tokens = set(cand.split())
        if not cand_tokens:
            return False
        seen = 0
        for msg in reversed(history_messages or []):
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue
            seen += 1
            if seen > lookback:
                break
            prev = cls._norm_for_dedup(str(msg.get("content", "")))
            if not prev:
                continue
            if cand in prev or prev in cand:
                return True
            prev_tokens = set(prev.split())
            if prev_tokens and len(cand_tokens & prev_tokens) / len(cand_tokens) >= threshold:
                return True
        return False

    @classmethod
    def _verify_answer_against_combo(cls, answer: str, combo) -> bool:
        """D-142 (1A): تحقّق رمزي من صحة إجابة الطالب مقابل المحرك الرمزي (combo).

        صحيحة حتمياً حين تُسمّي لوناً ممكناً (عدده ≥ k) أو تُقرّ باستحالة لون (عدده < k).
        مستقلّ عن تشخيص المفهوم ⇒ يُكرّم الإجابة الصحيحة حتى لو أخطأ التشخيص (السلطة الرمزية).
        """
        try:
            from app.services.capabilities.arabic_normalize import normalize_ar

            norm = normalize_ar(answer or "")
            if not norm:
                return False
            possible = [
                normalize_ar(getattr(g, "label", ""))
                for g in getattr(combo, "groups", [])
                if getattr(g, "is_possible", True)
            ]
            possible_words = {p.split()[-1] for p in possible if p.split()}
            mentions_possible = any(w and w in norm for w in possible_words)
            raw = answer or ""
            mentions_impossible = any(
                w in raw for w in ("مستحيل", "لا يمكن", "فقط", "لونين", "غير كاف", "2 فقط")
            )
            return mentions_possible or mentions_impossible
        except Exception:  # pragma: no cover - fail-safe
            return False

    #: ISS-122 (D-155): قوالب أسئلة الخطوات التي نطرحها نحن — تُعرِّف «السؤال
    #: المعلّق» المشتق من أحدث رسالة مساعد (لا حالة دائمة جديدة). أي قالب سؤال
    #: جديد في البُناة الحتمية يجب أن يُسجَّل هنا وإلا صار سؤاله غير مرئي للتحقّق.
    _STEP_QUESTION_MARKERS: tuple[tuple[str, str], ...] = (
        ("كم عدد **كل** الطرق الممكنة", "denominator"),
        ("كم عدد كل الطرق الممكنة", "denominator"),
        ("كيف تُكوّن منهما الاحتمال", "ratio"),
        ("فما قيمة P(A)", "ratio"),
        ("ما قيمة P(A) التي حصلت عليها", "ratio"),
        ("أيّ الألوان يمكن أن تعطينا", "colors"),
    )

    #: ISS-122 (D-155): علامات «خطوة تدريس سابقة» — وجود أيٍّ منها في رسائل
    #: المساعد يعني أن الحوار التدريسي بدأ (فلا يُعاد probe التشخيص الأول).
    _TUTORING_STEP_MARKERS: tuple[str, ...] = (
        "الحالات الملائمة",
        "كم عدد **كل** الطرق",
        "كيف تُكوّن منهما الاحتمال",
        "أيّ الألوان يمكن أن تعطينا",
        "لنُكمل معاً خطوة بخطوة",
        "فما قيمة P(A)",
    )

    #: ISS-122 (D-155) + ISS-128 (D-162): بادئات استفهامية تجعل الرسالة سؤالاً لا
    #: إجابةً تُقيَّم — تسقط لطبقات الإجابة (F2/التسمية/D-124/D-125). «هل» ليست هنا
    #: عمداً: «هل هي 14 من 165» إجابة تطلب تأكيداً. D-162 وسّعها بعد كارثة
    #: «ماذا نسمي حساب 4 و 10 لم افهمها؟» التي اعتُرفت «إجابة في الطريق الصحيح».
    _QUESTION_OPENERS_NOT_ANSWERS: tuple[str, ...] = (
        "لماذا",
        "ليش",
        "علاش",
        "كيف",
        "كيفاش",
        "ماذا",
        "ما هو",
        "ما هي",
        "ماهو",
        "ماهي",
        "ما اسم",
        "ما الفرق",
        "ما معنى",
        "ما المقصود",
        "متى",
        "أين",
        "اين",
        "من أين",
        "من اين",
        "شنو",
        "واش",
    )

    #: D-162 (ISS-128): علامات نية التسمية («ماذا **نسمي** حساب 4 و 10؟») — الطالب
    #: يطلب **اسم** العملية (التوافيق)، لا نتيجتها. كانت عمياء عنها كل الطبقات.
    _NAMING_MARKERS: tuple[str, ...] = (
        "نسمي",
        "ما اسم",
        "ما إسم",
        "يسمى",
        "تسمى",
        "تسميه",
        "تسمية",
    )

    @classmethod
    def _is_question_not_answer(cls, message: str) -> bool:
        """D-162 (ISS-128): بوّابة الفعل الكلامي — سؤال الطالب لا يُقيَّم كإجابة أبداً.

        الكارثة: «ماذا نسمي حساب 4 و 10 لم افهمها؟» احتوت أرقاماً تطابق قيم
        combo فاعتُرفت ``step_correct`` وكُشف جواب السؤال المعلّق (165). السؤال
        والإجابة يجب أن يتمايزا **قبل** أي مطابقة رقمية. «هل» مستثناة عمداً
        (قاعدة D-155 الثابتة: «هل هي 14 من 165» إجابة تطلب تأكيداً).
        """
        try:
            q = (message or "").strip().lower()
            if not q:
                return False
            # «و ماذا نسمي...» — واو العطف لا تحجب البادئة (دون مسّ «واش» الدارجة).
            if q.startswith("و "):
                q = q[2:].lstrip()
            if q.startswith(cls._QUESTION_OPENERS_NOT_ANSWERS):
                return True
            return any(m in q for m in cls._NAMING_MARKERS)
        except Exception:  # pragma: no cover - fail-safe
            return False

    @classmethod
    def _pending_focus_from_history(
        cls, history_messages: list[dict[str, str]] | None
    ) -> str | None:
        """ISS-122 (D-155): السؤال المعلّق — أيّ خطوة سألنا عنها الطالب آخر مرة؟

        حتمي: يطابق قوالبنا نحن في أحدث رسالة مساعد (القوالب بلا أرقام فتنجو من
        حجب D-113 في النسخة المحفوظة). ``denominator``/``ratio``/``colors``/None.
        """
        last_assistant = ""
        for msg in reversed(history_messages or []):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                last_assistant = str(msg.get("content", ""))
                break
        if not last_assistant:
            return None
        for marker, focus in cls._STEP_QUESTION_MARKERS:
            if marker in last_assistant:
                return focus
        return None

    @staticmethod
    def _extract_answer_numbers(text: str) -> set[int]:
        """ISS-122 (D-155): أعداد رسالة الطالب (أرقام عربية ⇒ لاتينية أولاً)."""
        digits = (text or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        return {int(m) for m in re.findall(r"\d+", digits)}

    @classmethod
    def _verify_numeric_answer(cls, answer: str, combo, pending_focus: str | None) -> str | None:
        """ISS-122 (D-155): الحقيقة الرمزية تحكم إجابة الطالب **الرقمية**.

        كارثة الترانسكريبت: «هل هي 14 من 165» (الإجابة الصحيحة!) كانت غير مرئية
        لكل طبقات التحقّق (ألوان فقط) ⇒ أُعيد سؤال ما أُجيب للتو. الأرقام من
        ``combo`` حصراً (صفر hardcoding). يُرجِع:
        ``"final_ratio"`` (النسبة النهائية بأي صياغة) | ``"step_correct"``
        (خطوة السؤال المعلّق) | ``"direction"`` (اتجاه صحيح — «نفس الشئ مع 11»)
        | ``None`` (غير مؤكَّدة ⇒ تُترك للمُقيّم).
        """
        try:
            # D-162 (ISS-128): بوّابة الفعل الكلامي أولاً — «ماذا نسمي حساب 4 و 10
            # لم افهمها؟» سؤالٌ يحمل أرقاماً تطابق favs فكان يُعترف step_correct
            # ويُكشف جواب السؤال المعلّق. السؤال ليس إجابة أبداً (عدا «هل» — D-155).
            if cls._is_question_not_answer(answer):
                return None
            nums = cls._extract_answer_numbers(answer)
            if not nums:
                return None
            same = int(combo.same_group_favorable)
            total = int(combo.total_combinations)
            n = int(combo.n)
            favs = {
                int(g.favorable_combinations)
                for g in getattr(combo, "groups", [])
                if getattr(g, "is_possible", False)
            }
            # النسبة النهائية صحيحة بأي صياغة («14/165»، «14 من 165»، «14 على 165»)
            # وفي أي سؤال معلّق — تأكيد ما ولّده الطالب ليس كشفاً.
            if same in nums and total in nums:
                return "final_ratio"
            if pending_focus == "denominator":
                if total in nums:
                    return "step_correct"
                if n in nums:  # «نفس الشئ مع 11» — الاتجاه صحيح، نُكمل الحساب معاً.
                    return "direction"
                return None
            if pending_focus in (None, "numerator") and (same in nums or (favs and favs <= nums)):
                return "step_correct"
            return None
        except Exception:  # pragma: no cover - fail-safe
            return None

    @classmethod
    def _has_prior_tutoring_step(cls, history_messages: list[dict[str, str]] | None) -> bool:
        """ISS-122 (D-155): هل بُثّت أي خطوة تدريس (probe/سُلّم/إنقاذ) سابقاً؟"""
        for msg in history_messages or []:
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue
            content = str(msg.get("content", ""))
            if any(m in content for m in cls._TUTORING_STEP_MARKERS):
                return True
        return False

    @classmethod
    def _build_diagnostic_probe(cls, combo) -> str:
        """ISS-122 (D-155): سؤال تشخيصي واحد قبل أي محتوى محسوب — «التشخيص قبل الشرح».

        صفر قيم محسوبة (لا C، لا مجاميع) — الطالب يولّد بصيرة «البيضاء مستحيلة»
        بنفسه (generation effect). يَنجو من حجب D-113 بنيوياً (لا «=»، لا نتيجة).
        """
        comp = "، ".join(
            f"{g.count} {str(g.label).replace('كرة ', '')}" for g in getattr(combo, "groups", [])
        )
        k = int(combo.k)
        return (
            f"لنبدأ من فهمك أنت — نسحب {k} كرات دفعة واحدة من كيس فيه: {comp}.\n\n"
            f"سؤال واحد قبل أي حساب: أيّ الألوان يمكن أن تعطينا {k} كرات "
            f"من نفس اللون؟ ولماذا؟"
        )

    @staticmethod
    def _is_first_help_request(question: str) -> bool:
        """ISS-122 (D-155): أول طلب مساعدة عام («كيف افهم التمرين»/«من أين أبدأ»)."""
        try:
            from app.services.capabilities.arabic_normalize import normalize_ar

            norm = normalize_ar(question or "")
        except Exception:  # pragma: no cover - fail-safe
            norm = (question or "").strip()
        markers = (
            "كيف افهم",
            "كيف نفهم",
            "كيف احل",
            "كيف نحل",
            "من اين ابدا",
            "من اين نبدا",
            "كيف ابدا",
            "كيف نبدا",
        )
        return any(m in norm for m in markers)

    @classmethod
    def _near_dup(cls, a: str, b: str, *, threshold: float = 0.8) -> bool:
        """D-142 (1B/Phase2): تداخل رموز/احتواء بين نصّين (حارس التكرار ضد مرساة الحالة)."""
        na, nb = cls._norm_for_dedup(a), cls._norm_for_dedup(b)
        if not na or not nb:
            return False
        if na in nb or nb in na:
            return True
        ta = set(na.split())
        if not ta:
            return False
        return len(ta & set(nb.split())) / len(ta) >= threshold

    @staticmethod
    def _semantic_tutor_enabled() -> bool:
        """D-142/D-158: علم تحميل+كتابة `tutor_state` — قارئ موحَّد (افتراض True).

        D-158: يُفوَّض إلى `app.core.feature_flags` — يُنهي الافتراض المتعارض (كان False هنا
        و True في customer_chat) الذي كان يُعطِّل سلطة `DialogueManagerSkill` في الإنتاج.
        """
        from app.core.feature_flags import semantic_tutor_enabled

        return semantic_tutor_enabled()

    @staticmethod
    def _cognitive_turn_enabled() -> bool:
        """D-158/D-159: علم طبقة القرار الموحَّدة `_cognitive_turn` (افتراض True منذ D-159)."""
        from app.core.feature_flags import cognitive_turn_enabled

        return cognitive_turn_enabled()

    @classmethod
    def _dialogue_decision(
        cls,
        *,
        question: str,
        concept: str,
        verified_correct: bool,
        understood: bool,
        tutor_state: dict,
        candidate_text: str,
    ):
        """D-142 Phase 2: يستشير DialogueManagerSkill بإشارات الدور — fail-open (None عند الخطأ)."""
        try:
            from app.services.skills.dialogue_manager_skill import (
                DialogueInput,
                get_dialogue_manager_skill,
            )

            budget_map = tutor_state.get("socratic_count_by_concept") or {}
            socratic_count = int(budget_map.get(concept, 0)) if isinstance(budget_map, dict) else 0
            return get_dialogue_manager_skill().decide(
                DialogueInput(
                    question=question,
                    concept=concept,
                    verified_correct=bool(verified_correct),
                    understood=bool(understood),
                    ability=float(tutor_state.get("ability_snapshot") or 0.0),
                    socratic_count=socratic_count,
                    last_step_emitted=str(tutor_state.get("last_step_emitted") or ""),
                    candidate_text=candidate_text or "",
                )
            )
        except Exception:  # pragma: no cover - fail-safe
            return None

    @staticmethod
    def _concept_of_text(text: str) -> str:
        """D-127: المفهوم الحتمي لرسالة طالب (incl. confusion→full_solution)."""
        from app.services.skills.concept_diagnosis_skill import ConceptDiagnosisSkill

        c = ConceptDiagnosisSkill.diagnose_deterministic(text).concept
        if c == "unknown":
            low = (text or "").strip().lower()
            if any(
                m in low for m in ("لم أفهم", "لم افهم", "مفهمتش", "ما فهمت", "لا أفهم", "لا افهم")
            ) or low in ("؟", "?"):
                return "full_solution"
        return c

    @classmethod
    def _count_prior_concept(
        cls, concept: str, history_messages: list[dict[str, str]] | None
    ) -> int:
        """عدد رسائل الطالب السابقة التي تخصّ نفس المفهوم (سُلّم التصعيد السقراطي)."""
        count = 0
        for msg in history_messages or []:
            if (
                isinstance(msg, dict)
                and msg.get("role") == "user"
                and cls._concept_of_text(str(msg.get("content", ""))) == concept
            ):
                count += 1
        return count

    @classmethod
    def _load_canonical_combinations(
        cls, question: str, history_messages: list[dict[str, str]] | None
    ):
        """D-127: يحمّل تركيبة التمرين الرسمي (CombinationsModelOutput) — مناعة D-123.

        يُرجِع None لغير الاحتمالات (topic-safe) أو عند تعذّر الحساب.
        ISS-120 (D-153): يقرأ **أسئلة-فقط** — تغذية الملف الكامل (مع الحل النموذجي)
        كانت تولِّد كياناً وهمياً «بطاقة رقم 0 (العدد 3)» من نثر الحل («…لا تحمل
        الرقم 0 … سحب 3 كرات») ⇒ n=14 و C(14,3)=364 بدل 11/165 — كارثة الطالب.
        """
        try:
            from app.services.capabilities.arabic_normalize import primary_canonical_topic
            from app.services.capabilities.exercise_retrieval import (
                ExerciseRetrievalRequest,
                detect_exercise_retrieval,
                load_exercise_questions_only,
            )
            from app.services.skills.probability_skill import (
                CombinationsModelOutput,
                ProbabilityCalculatorSkill,
                ProbabilityInput,
            )

            _canonical = primary_canonical_topic(question)
            if _canonical is not None and _canonical.canonical_id != "probability":
                return None
            _decision = detect_exercise_retrieval(
                ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024"),
                history_messages=history_messages,
            )
            if not (_decision.recognized and _decision.matched_entry):
                return None
            _official = load_exercise_questions_only(_decision.matched_entry)
            if not _official:
                return None
            result = ProbabilityCalculatorSkill().analyze(
                ProbabilityInput(question=_official, history=None)
            )
            return result if isinstance(result, CombinationsModelOutput) else None
        except Exception:
            logger.warning("_load_canonical_combinations_failed", exc_info=True)
            return None

    @classmethod
    def _build_cognitive_response(
        cls,
        concept: str,
        misconception: str,
        question: str,
        history_messages: list[dict[str, str]] | None,
    ) -> str | None:
        """D-127: الطبقة 4 — استجابة مدفوعة بالمفهوم + تصعيد سقراطي (شرح→سؤال→تشخيص).

        المستوى من عدد المرّات السابقة لنفس المفهوم (`_count_prior_concept`): مرّة1 شرح،
        مرّة2 سؤال سقراطي (حسب `misconception`)، مرّة3+ إعادة توجيه. الأرقام رمزية (الطبقة 3).
        يَنجو من حجب D-113. يُرجِع None لغير الاحتمالات أو مفهوم غير مدعوم.
        """
        combo = cls._load_canonical_combinations(question, history_messages)
        if combo is None:
            return None
        n, k, total, same = (
            combo.n,
            combo.k,
            combo.total_combinations,
            combo.same_group_favorable,
        )
        groups = list(combo.groups)
        possible = [g for g in groups if g.is_possible]
        favs_lines = "\n".join(
            (
                f"- {g.label}: {cls._fmt_comb(g.count, k, g.favorable_combinations)}"
                if g.is_possible
                else f"- {g.label}: مستحيل (العدد {g.count} أصغر من {k})"
            )
            for g in groups
        )
        favs_sum = " + ".join(str(g.favorable_combinations) for g in possible)
        level = cls._count_prior_concept(concept, history_messages)

        # ── numerator (البسط/14) ──────────────────────────────────────────────
        if concept == "numerator":
            if level == 0:
                return (
                    "## ما هو البسط؟\n\n"
                    "البسط هو عدد الطرق التي **تحقق الشرط المطلوب** (3 كرات من نفس اللون). "
                    "نعدّها لكل لون ممكن:\n\n"
                    f"{favs_lines}\n\n"
                    f"فالبسط = {favs_sum} = {same}: الحالات التي «تنجح» من بين كل الإمكانات."
                )
            if level == 1:
                if misconception == "sample_space_confusion":
                    return (
                        "شرحنا أن البسط هو الحالات التي تحقق الشرط. لنفرّقه عن المقام بسؤال:\n\n"
                        f"من بين كل الطرق الـ{total}، كم طريقة فقط تعطي 3 كرات من **نفس اللون**؟ "
                        "(لا تحسب — فكّر: أيّ الألوان يكفي عددها لذلك؟)"
                    )
                return (
                    "بدل أن أعيد الشرح، سؤال لك:\n\n"
                    "من الألوان الثلاثة (حمراء/خضراء/بيضاء)، أيّها يمكن أن يعطيك 3 كرات من نفس "
                    "اللون، وأيّها مستحيل؟ ولماذا؟"
                )
            return (
                "شرحنا البسط مرّتين — لنحدّد أين تحديداً تتعثّر. اختر حرفاً واحداً:\n\n"
                "(أ) معنى «الحالات الملائمة» نفسها\n"
                "(ب) لماذا اللون الأبيض مستحيل\n"
                f"(ج) لماذا نجمع {favs_sum} لنحصل على {same}\n\n"
                "أخبرني بالحرف وسأركّز معك على تلك النقطة وحدها."
            )

        # ── denominator (المقام/165) ──────────────────────────────────────────
        if concept == "denominator":
            if level == 0:
                return (
                    "## ما هو المقام؟\n\n"
                    f"المقام هو عدد **كل** الطرق الممكنة لسحب {k} كرات من {n} مهما كان لونها:\n\n"
                    f"{cls._fmt_comb(n, k, total)}\n\n"
                    "إنه ساحة كل ما يمكن أن يحدث — القاسم الذي نقسم عليه."
                )
            if level == 1:
                return (
                    "سؤال لك حتى نتأكّد من فهم المقام:\n\n"
                    f"عندما نسحب {k} كرات من {n}، هل عدد كل الاختيارات الممكنة يعتمد على "
                    "**ألوان** الكرات أم على **عددها** فقط؟"
                )
            return (
                "شرحنا المقام مرّتين. لنحدّد العقدة — اختر: (أ) لماذا نختار بالتوافيق لا "
                "بالترتيب، أم (ب) معنى «كل الطرق الممكنة»؟ أخبرني بالحرف."
            )

        # ── ratio (العلاقة/الفرق) ─────────────────────────────────────────────
        if concept == "ratio":
            if level == 0:
                return cls._format_conceptual_relationship(question, n, k, total, same, groups)
            if level == 1:
                return (
                    "شرحنا العلاقة. سؤال لك:\n\n"
                    f"لو كان البسط {same} والمقام {total}، فهل يكبر الاحتمال كلما كبر **البسط** "
                    "أم كلما كبر **المقام**؟ ولماذا؟"
                )
            return (
                "لنحدّد العقدة في معنى النسبة — اختر: (أ) معنى «من بين»، (ب) لماذا البسط فوق "
                "والمقام تحت، (ج) ماذا يعني أن الاحتمال بين 0 و1؟ أخبرني بالحرف."
            )

        # ── الألوان ───────────────────────────────────────────────────────────
        if concept in ("color_red", "color_green", "color_white"):
            color = {"color_red": "red", "color_green": "green", "color_white": "white"}[concept]
            g = next((x for x in groups if (x.color or "") == color), None)
            if g is not None:
                if level == 0:
                    if g.is_possible:
                        return (
                            f"## تأليفات {g.label}\n\n"
                            f"عدد {g.label}: {g.count}، نختار منها {k}:\n\n"
                            f"{cls._fmt_comb(g.count, k, g.favorable_combinations)}\n\n"
                            f"أي {g.favorable_combinations} طريقة — إحدى مكوّنات البسط."
                        )
                    return (
                        f"## لماذا {g.label} مستحيلة؟\n\n"
                        f"عددها {g.count} فقط، ونحتاج اختيار {k}. بما أن {g.count} أصغر من {k}، "
                        "لا يمكن سحب 3 منها معاً — لذلك لا تساهم في البسط."
                    )
                if level == 1:
                    return (
                        f"سؤال لك عن {g.label}: لماذا نستخدم التوافيق C لا الترتيب عند عدّ "
                        f"اختيار {k} كرات منها؟ (تلميح: هل يهمّنا ترتيب سحبها؟)"
                    )
                return (
                    f"شرحنا {g.label} مرّتين. أين العقدة — في الصيغة C أم في معنى «اختيار دون "
                    "ترتيب»؟ أخبرني."
                )

        # ── event_meaning (معنى الحادثة A/B/C/D) — D-131/D-132: الطبقة الدلالية العامة ──
        # نداء واحد للطبقة الدلالية (data-driven، لا special-casing لكل حادثة). يُغطّي
        # «جداء معدوم/فردي/زوجي» + «نفس اللون» عبر PROPERTY_REGISTRY.
        # D-132: لا default مُجمَّد لـ same_color — الافتراض A فقط لسؤال «الحادثة» الصريح؛
        # المفاهيم غير الحدثية (المتغير العشوائي/الأمل/...) يلتقطها preempt التعريف في
        # chat_with_agent عبر interpret_or_define قبل الوصول هنا.
        if concept == "event_meaning":
            if level == 0:
                from app.services.skills.semantic_property_skill import (
                    PROPERTY_REGISTRY,
                    get_semantic_property_skill,
                )
                from app.services.skills.tutor_metrics import record_definitional_answer

                _sp = get_semantic_property_skill().interpret(question)
                if _sp is not None:
                    record_definitional_answer(_sp.concept_id, resolved=True)
                    return f"## {_sp.title}\n\n{_sp.definition}"
                # D-132: الافتراض A **فقط** عند سؤال حدثي صريح (الحادثة/الحدث/A).
                _q = (question or "").lower()
                if any(m in _q for m in ("الحادثة", "الحدث", "a", "نفس اللون")):
                    _spec = PROPERTY_REGISTRY["same_color"]
                    record_definitional_answer(_spec.concept_id, resolved=True)
                    return f"## {_spec.title}\n\n{_spec.definition}"
                return None  # مفهوم غير معروف غير حدثي ⇒ لا نُقحمه في الحادثة A
            # level >= 1 ⇒ يُستبدَل بالسرد السقراطي المُولَّد (chat_with_agent)؛ هذا fallback.
            return (
                "الحادثة A تعني «3 كرات من نفس اللون». سؤال لك: لو سحبت 3 كرات، متى تقول إنها "
                "«نجحت» وحقّقت A، ومتى تقول إنها فشلت؟ أعطني مثالاً من عندك."
            )

        # ── full_solution / حيرة عامة ─────────────────────────────────────────
        if concept == "full_solution":
            if level == 0:
                return (
                    "## الحل الكامل خطوة بخطوة\n\n"
                    f"1) فضاء العينة — نسحب {k} كرات من {n} دفعةً واحدة:\n\n"
                    f"   {cls._fmt_comb(n, k, total)}\n\n"
                    "2) الحالات الملائمة (3 كرات من نفس اللون) — لكل لون:\n\n"
                    f"{favs_lines}\n\n"
                    f"3) نجمع الممكنة: {favs_sum} = {same}\n\n"
                    f"4) الاحتمال = {same} من كل {total}."
                )
            # level >= 1 ⇒ يُستبدَل بالسرد السقراطي المُولَّد (chat_with_agent)؛ هذا fallback.
            return (
                "شرحنا الحل كاملاً. بدل تكراره، لنحدّد أين تحديداً تعثّرت — اختر حرفاً:\n\n"
                f"(أ) فضاء العينة ({total} — كل الطرق)\n"
                f"(ب) عدّ الحالات الملائمة ({same})\n"
                "(ج) معنى الاحتمال نفسه (البسط على المقام)\n\n"
                "أخبرني بالحرف وسأركّز على تلك النقطة وحدها."
            )

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # D-128 — السرد السقراطي المُولَّد بالـ LLM (الطبقة 4 — الـ LLM كجهاز عصبي):
    # عند التصعيد (التكرار) يُولّد الـ LLM **تدخّلاً سقراطياً فريداً** — الـ LLM يُنتج
    # **الفهم/التربية** (السؤال السقراطي) لا **الحقيقة** (الأرقام تُحقن من المحرك الرمزي).
    # محروس: عربي فقط + لا كشف جواب + لا garbage + timeout + fallback حتمي. يُلغي التكرار.
    # ─────────────────────────────────────────────────────────────────────────
    _CONCEPT_AR: ClassVar[dict[str, str]] = {
        "numerator": "البسط (الحالات الملائمة)",
        "denominator": "المقام (كل الطرق الممكنة)",
        "ratio": "النسبة بين البسط والمقام",
        "combinations": "التوافيق (الاختيار دون ترتيب)",
        "color_red": "تأليفات الكرات الحمراء",
        "color_green": "تأليفات الكرات الخضراء",
        "color_white": "استحالة 3 كرات بيضاء",
        "event_meaning": "معنى الحادثة A (3 من نفس اللون)",
        "full_solution": "الحل الكامل خطوة بخطوة",
    }
    _MISCONCEPTION_AR: ClassVar[dict[str, str]] = {
        "sample_space_confusion": "يخلط بين البسط (الحالات الملائمة) والمقام (كل الطرق)",
        "fraction_meaning_confusion": "لا يفهم معنى النسبة (البسط مقسوم على المقام)",
        "order_vs_selection_confusion": "يظن أن ترتيب السحب مهمّ بينما هو اختيار فقط",
        "favourable_outcomes_confusion": "لا يفهم ما الذي «ينجح» ويحقّق الشرط",
        "none": "غير محدّد",
    }

    @staticmethod
    def _symbolic_facts_brief(combo) -> str:
        """D-128: حقائق رمزية مُختصرة (المعطيات + تعريف الحدث) — بلا الجواب النهائي.

        نحقن المعطيات (عدد كل لون) + تعريف الحادثة A فقط؛ **لا** نحقن 14/165 (النتائج
        المحسوبة) كي لا يكشفها الـ LLM — الطالب يُقاد لاكتشافها سقراطياً.
        """
        parts = [f"الكيس فيه {combo.n} كرة، نسحب {combo.k} دفعةً واحدة"]
        for g in combo.groups:
            parts.append(f"{g.label}: {g.count}")
        parts.append("الحادثة A = 3 كرات من نفس اللون")
        return "؛ ".join(parts)

    @staticmethod
    def _balls_brief(combo) -> str:
        """D-133: معطيات الكيس **محايدة للمفهوم** (ألوان + أعداد بلا تعريف الحادثة A).

        تُستخدم لإثراء رد الحيرة وللمثال الملموس لأي مفهوم — لا A-bias (تعميم لا special-casing).
        """
        colors = "، ".join(f"{g.label}: {g.count}" for g in combo.groups)
        return f"الكيس فيه {combo.n} كرة (نسحب {combo.k} دفعةً واحدة): {colors}"

    @classmethod
    async def _generate_guiding_question(
        cls,
        concept: str,
        balls: str,
    ) -> str | None:
        """D-133: سؤال موجِّه واحد محروس **عام لأي مفهوم** (لإثراء رد الحيرة).

        الـ LLM = مُفسِّر/موجِّه لا حَكَم: يولّد سؤالاً يقود الطالب لتطبيق المفهوم على معطيات
        الكيس — لا يحسب، لا يكشف نتيجة. محروس بنفس طبقات D-128 + timeout + fallback ⇒ None.
        """
        try:
            import asyncio
            import re as _re

            from app.core.ai_gateway import get_ai_client

            system_prompt = (
                "أنت معلّم تربوي جزائري. ولّد **سؤالاً واحداً** يقود الطالب لتطبيق المفهوم على "
                "معطيات الكيس — لا تشرح، لا تحسب، لا تكشف أي نتيجة نهائية أو كسر (مثل 14/165). "
                "عربية فصحى، جملة واحدة قصيرة تنتهي بعلامة استفهام."
            )
            user = (
                f"المفهوم: {cls._CONCEPT_AR.get(concept, concept)}.\n"
                f"معطيات الكيس (استخدمها فقط): {balls}\n"
                "ولّد سؤالاً واحداً يطبّق المفهوم على هذه المعطيات."
            )
            raw = await asyncio.wait_for(
                get_ai_client().send_message(system_prompt, user, temperature=0.5),
                timeout=10.0,
            )
            if not raw or not isinstance(raw, str) or not raw.strip():
                return None

            from app.services.skills.answer_redaction_skill import redact_final_answers
            from app.services.skills.arabic_stream_guard import is_probably_non_arabic
            from app.services.skills.content_integrity_skill import _strip_garbage_markers

            text = _strip_garbage_markers(raw.strip())
            text, _ = redact_final_answers(text, support_level=5)
            text = text.strip()
            if not text or is_probably_non_arabic(text):
                return None
            if _re.search(r"14\s*/\s*165|56\s*/\s*165", text):
                return None
            return text
        except Exception:  # pragma: no cover — fail-safe
            return None

    @classmethod
    def _build_concrete_example(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
    ) -> str | None:
        """D-133 (intent=example_request): **مثال ملموس قبل النظرية** — حتمي.

        المعطيات الملموسة من المحرك الرمزي (الكيس الفعلي) لا LLM. يَنجو من حجب D-113
        (لا نتيجة نهائية). يُرجِع None لغير الاحتمالات.
        """
        combo = cls._load_canonical_combinations(question, history_messages)
        if combo is None:
            return None
        balls = cls._balls_brief(combo)
        return (
            f"لنبدأ بمثال ملموس من هذا التمرين قبل أي قاعدة:\n\n"
            f"{balls}.\n\n"
            f"تخيّل سحبة واحدة: نأخذ {combo.k} كرات معاً وننظر إلى ألوانها وأرقامها — "
            f"هذا هو الموقف الذي نعمل عليه. أيّ حالة تريد أن نتتبّعها معاً خطوة بخطوة؟"
        )

    @classmethod
    async def _build_concept_example(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
    ) -> str | None:
        """D-136: مثال **واعٍ بالمفهوم النشط** (لا مثال الحادثة A الأعمى الافتراضي).

        المفهوم من السياق (`detect_active_concept`): «اعطني مثال» بعد تعريف product_even ⇒ مثال
        product_even. deterministic أولاً (`PropertySpec.example`)؛ إن عُرِض المثال already ⇒ زاوية
        مختلفة (LLM محروس) — لا تكرار. يُرجِع None إن لا مفهوم نشط (يسقط للمعالج العام).
        """
        try:
            from app.services.skills.semantic_property_skill import get_semantic_property_skill

            concept = get_semantic_property_skill().detect_active_concept(
                question, history_messages
            )
            if concept is None or not concept.example:
                return None
            shown = " ".join(
                str(m.get("content", ""))
                for m in (history_messages or [])
                if isinstance(m, dict) and m.get("role") == "assistant"
            )
            already = concept.example[:40] in shown  # نفس المثال عُرِض already؟
            if not already:
                return f"## مثال ملموس\n\n{concept.example}"
            # تكرار ⇒ زاوية مختلفة (LLM محروس)؛ fallback للمثال الحتمي خير من مثال أعمى.
            alt = await cls._generate_concept_example_llm(concept, question, history_messages)
            return alt or f"مثال آخر للتوضيح:\n\n{concept.example}"
        except Exception:  # pragma: no cover — fail-safe
            return None

    @classmethod
    async def _generate_concept_example_llm(
        cls,
        concept,
        question: str,
        history_messages: list[dict[str, str]] | None,
    ) -> str | None:
        """D-136: مثال بديل (زاوية مختلفة) للمفهوم — LLM محروس. LLM = التدريس، symbolic = الأرقام.

        يُستدعى فقط عند تكرار المثال الحتمي. محروس بنفس طبقات D-128 + timeout + fallback ⇒ None.
        """
        try:
            import asyncio
            import re as _re

            from app.core.ai_gateway import get_ai_client

            combo = cls._load_canonical_combinations(question, history_messages)
            facts = cls._balls_brief(combo) if combo is not None else ""
            system_prompt = (
                "أنت معلّم رياضيات جزائري. أعطِ **مثالاً ملموساً واحداً مختلفاً** يوضّح المفهوم "
                "باستخدام معطيات هذا التمرين. لا تشرح القاعدة، لا تحسب نتيجة نهائية، ولا تذكر أي "
                "كسر نهائي (مثل 14/165). عربية فصحى، جملتان كحدّ أقصى."
            )
            user = (
                f"المفهوم: {concept.title}\n"
                f"تعريفه: {concept.definition}\n"
                f"معطيات التمرين (استخدمها): {facts}\n"
                f"مثال سبق عرضه (لا تُكرّره — غيّر الزاوية): {concept.example}\n"
                "أعطِ مثالاً ملموساً مختلفاً."
            )
            raw = await asyncio.wait_for(
                get_ai_client().send_message(system_prompt, user, temperature=0.5),
                timeout=10.0,
            )
            if not raw or not isinstance(raw, str) or not raw.strip():
                return None

            from app.services.skills.answer_redaction_skill import redact_final_answers
            from app.services.skills.arabic_stream_guard import is_probably_non_arabic
            from app.services.skills.content_integrity_skill import _strip_garbage_markers

            text = _strip_garbage_markers(raw.strip())
            text, _ = redact_final_answers(text, support_level=5)
            text = text.strip()
            if not text or is_probably_non_arabic(text):
                return None
            if _re.search(r"14\s*/\s*165|56\s*/\s*165", text):
                return None
            return f"مثال آخر:\n\n{text}"
        except Exception:  # pragma: no cover — fail-safe
            return None

    @classmethod
    async def _generate_socratic_narrative(
        cls,
        concept: str,
        misconception: str,
        question: str,
        history_messages: list[dict[str, str]] | None,
    ) -> str | None:
        """D-128: تدخّل سقراطي فريد مُولَّد بالـ LLM (محروس). يُرجِع None ⇒ القالب الحتمي.

        D-129: يُستدعى عندما تقرّر السياسة التربوية `socratic` (هي البوّابة الوحيدة الآن —
        لا بوّابة level داخلية). الـ LLM يُنتج الفهم (سؤال يقود الطالب)؛ الأرقام من المحرك
        الرمزي (محقونة). محروس بطبقات قائمة + timeout + fallback. أي فشل/كشف/garbage ⇒ None.
        """
        try:
            import asyncio
            import re as _re

            combo = cls._load_canonical_combinations(question, history_messages)
            if combo is None:
                return None

            facts = cls._symbolic_facts_brief(combo)
            prior_qs = " | ".join(
                str(m.get("content", ""))[:80]
                for m in (history_messages or [])[-8:]
                if isinstance(m, dict) and m.get("role") == "user"
            )
            from app.core.ai_gateway import get_ai_client

            system_prompt = (
                "أنت معلّم سقراطي تربوي جزائري. مهمتك توليد **سؤال واحد** يقود الطالب — لا الحل. "
                "ممنوع منعاً باتاً كشف الجواب النهائي أو أي كسر نهائي (مثل 14/165 أو 56/165). "
                "ممنوع الحساب. استخدم الأرقام المعطاة في «الحقائق» فقط ولا تخترع غيرها. الطالب "
                "عالق وكرّر سؤاله — غيّر الزاوية ولا تُعِد ما قيل. عربية فصحى فقط، جملة أو جملتان، "
                "أقل من 50 كلمة، وتنتهي بعلامة استفهام."
            )
            user = (
                f"المفهوم: {cls._CONCEPT_AR.get(concept, concept)}.\n"
                f"المفهوم الخاطئ عند الطالب: {cls._MISCONCEPTION_AR.get(misconception, '')}.\n"
                f"الحقائق (لا تُغيّرها ولا تتجاوزها): {facts}\n"
                f"أسئلة الطالب السابقة: {prior_qs}\n"
                "ولّد سؤالاً سقراطياً واحداً جديداً يكشف النقطة العالقة (لا تكرار)."
            )
            raw = await asyncio.wait_for(
                get_ai_client().send_message(system_prompt, user, temperature=0.6),
                timeout=12.0,
            )
            if not raw or not isinstance(raw, str) or not raw.strip():
                return None
            text = raw.strip()

            # ── الحراسة (طبقات قائمة) ──────────────────────────────────────────
            from app.services.skills.answer_redaction_skill import redact_final_answers
            from app.services.skills.arabic_stream_guard import is_probably_non_arabic
            from app.services.skills.content_integrity_skill import _strip_garbage_markers

            text = _strip_garbage_markers(text)
            text, _ = redact_final_answers(text, support_level=5)
            text = text.strip()
            if not text or is_probably_non_arabic(text):
                return None
            # رفض إن كشف الكسر النهائي رغم الحجب (شبكة أمان أخيرة).
            if _re.search(r"14\s*/\s*165|56\s*/\s*165", text):
                return None
            return text
        except Exception:
            logger.warning("_generate_socratic_narrative_failed", exc_info=True)
            return None

    @classmethod
    def _build_symbolic_reveal(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
        *,
        acknowledge: bool = False,
        delivered: set[str] | None = None,
    ) -> str | None:
        """D-129: الحلّ الرمزي المتدرّج — الإنقاذ التربوي بعد استنفاد السقراطية (الطبقة 4).

        حتمي تماماً (من المحرك الرمزي). يُسبَق باعتراف عند ``acknowledge``. يَنجو من حجب
        D-113 (نمط ``_fmt_comb`` + «من كل»). يُرجِع None لغير الاحتمالات.

        D-158: ``delivered`` (اختياري) — مجموعة مفاتيح الخطوات المعروضة سابقاً (من
        ``kc_progress.representations_delivered`` الدائم). عند تمريرها، تُحذف الكتلة
        المعروضة مسبقاً (numerator/denominator) فلا يُعاد التفريغ عبر الأدوار (يقتل S1
        بنيوياً). الافتراضي (None) مطابق بايتياً للسلوك السابق (كل الكتل).
        """
        combo = cls._load_canonical_combinations(question, history_messages)
        if combo is None:
            return None
        n, k, total, same = (
            combo.n,
            combo.k,
            combo.total_combinations,
            combo.same_group_favorable,
        )
        favs_lines = "\n".join(
            (
                f"- {g.label} (العدد {g.count}): {cls._fmt_comb(g.count, k, g.favorable_combinations)}"
                if g.is_possible
                else f"- {g.label} (العدد {g.count}): مستحيلة (أقل من {k})"
            )
            for g in combo.groups
        )
        favs_sum = " + ".join(str(g.favorable_combinations) for g in combo.groups if g.is_possible)
        prefix = "إجابتك في الطريق الصحيح — " if acknowledge else ""
        # ISS-121 (D-154): صفر كشف للنتيجة النهائية (roadmap §7) — الإنقاذ يقدّم
        # كل المكوّنات (scaffold مشروع — D-129) لكن **تركيب النسبة النهائية يولّده
        # الطالب بنفسه** (generation effect؛ «التلميح قبل الحل»). ممنوع طباعة
        # «فاحتمال الحادثة A هو X من كل Y».
        _d = delivered or set()
        num_block = (
            f"**الحالات الملائمة** (3 كرات من نفس اللون) — لكل لون:\n\n"
            f"{favs_lines}\n\n"
            f"نجمع الحالات الممكنة فقط: ${favs_sum} = {same}$\n\n"
        )
        den_block = f"**كل الطرق الممكنة** لسحب {k} من {n}:\n\n{cls._fmt_comb(n, k, total)}\n\n"
        body = f"{prefix}لنُكمل معاً خطوة بخطوة حتى النهاية:\n\n"
        if "numerator" not in _d:
            body += num_block
        if "ratio" not in _d and "denominator" not in _d:
            body += den_block
        body += (
            "الآن أمامك كل المكوّنات — ركّب الاحتمال **بنفسك**: البسط على المقام. "
            "فما قيمة P(A) التي تحصل عليها؟"
        )
        return body

    @classmethod
    def _in_socratic_dialogue(
        cls, question: str, history_messages: list[dict[str, str]] | None
    ) -> bool:
        """D-130: هل نحن وسط حوار سقراطي والطالب يُجيب سؤالنا السقراطي؟

        قفل الحالة عبر التاريخ (لا حقل دائم): أحدث رسالة مساعد سؤال سقراطي طرحناه
        (تنتهي بـ«؟»، ليست إفراغ تمرين)، ضمن سياق احتمالات، ورسالة الطالب الحالية
        إجابة (فعل كلامي لا طول — `is_response_to_socratic`، تحسين A). حارس تبديل
        الموضوع (D-101) داخل `is_response_to_socratic`.
        """
        try:
            from app.services.skills.pedagogical_policy_skill import is_response_to_socratic

            # أحدث رسالة مساعد يجب أن تكون سؤالاً سقراطياً (لا إفراغ تمرين).
            last_assistant = None
            for msg in reversed(history_messages or []):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    last_assistant = str(msg.get("content", "")).strip()
                    break
            if not last_assistant:
                return False
            # D-137: السؤال السقراطي قد ينتهي بأمر («...A؟ أعطني مثالاً») — نكشف «؟» في أي
            # موضع (لا endswith فقط) وإلا تُهمَل إجابة الطالب (كارثة الخيانة البيداغوجية).
            if "؟" not in last_assistant and "?" not in last_assistant:
                return False
            # تمييز السؤال السقراطي من إفراغ تمرين يحوي صدفةً «؟».
            if len(last_assistant) > 600 or any(
                m in last_assistant
                for m in ("التمرين الأول", "يحتوي كيس على", "احسب احتمال الحادثة")
            ):
                return False
            # سياق احتمالات (الحوار عن تمرين الاحتمالات).
            _hist_text = " ".join(
                str(m.get("content", "")) for m in (history_messages or []) if isinstance(m, dict)
            )
            if not cls._is_prob_context(question + " " + _hist_text):
                return False
            # رسالة الطالب الحالية إجابة (مستقل عن الطول، حارس تبديل الموضوع داخله).
            return is_response_to_socratic(question, history_messages)
        except Exception:  # pragma: no cover - fail-safe
            logger.warning("_in_socratic_dialogue_failed", exc_info=True)
            return False

    @classmethod
    def _is_short_answer_in_dialogue(
        cls, question: str, history_messages: list[dict[str, str]] | None
    ) -> bool:
        """D-135: إجابة قصيرة وسط حوار تمرين نشط (تلميح/شرح سابق، **لا «؟» شرط**)؟

        يمنع إعادة طباعة التمرين على إجابة الطالب الصحيحة («اللون الأحمر والأخضر فقط») — تُترَك
        لمحرّك حالة الفهم (D-135) ليُقيّمها كبرهان فهم ويتقدّم. حارس تبديل الموضوع (D-101) داخله.
        """
        try:
            norm = (question or "").strip()
            if not norm or len(norm.split()) > 8:  # الإجابات قصيرة؛ الطلبات الجديدة أطول
                return False
            _low = norm.lower()
            if any(
                m in _low
                for m in (
                    "اعطني",
                    "أعطني",
                    "اعطيني",
                    "هات",
                    "اكتب",
                    "ارسم",
                    "تمرين",
                    "مسألة",
                    "درس",
                )
            ):
                return False  # طلب محتوى/تمرين جديد صريح — ليس إجابة
            last_assistant = None
            for msg in reversed(history_messages or []):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    last_assistant = str(msg.get("content", "")).strip()
                    break
            if not last_assistant:
                return False
            if len(last_assistant) > 600 or "يحتوي كيس على" in last_assistant:
                return False  # آخر رسالة كانت إفراغ التمرين نفسه — ليست حوار تدريس
            _hist_text = " ".join(
                str(m.get("content", "")) for m in (history_messages or []) if isinstance(m, dict)
            )
            if not cls._is_prob_context(question + " " + _hist_text):
                return False
            from app.services.capabilities.arabic_normalize import primary_canonical_topic

            _topic = primary_canonical_topic(question)
            return not (_topic is not None and _topic.canonical_id != "probability")
        except Exception:  # pragma: no cover - fail-safe
            return False

    @classmethod
    def _build_symbolic_step(cls, combo, focus: str | None, *, acknowledge: bool = False) -> str:
        """D-130: الخطوة الرمزية المتدرّجة (التسليم الرمزي) — حتمية من المحرك الرمزي.

        عند فهم الطالب: نكشف **خطوة المفهوم الحالي** + سؤال المتابعة، لا الحل كاملاً
        (يُبقي السُّلّم السقراطي حياً، يحترم مثال المالك «C(4,3)+C(5,3)=14»). يَنجو من
        حجب D-113 (نمط `_fmt_comb` + «من كل»).
        """
        prefix = "إجابتك في الطريق الصحيح — " if acknowledge else ""
        n, k, total = combo.n, combo.k, combo.total_combinations
        # خطوة البسط (الحالات الملائمة): الافتراضي والأكثر شيوعاً بعد فهم «نفس اللون».
        if focus in (None, "denominator", "numerator", "event_meaning"):
            favs_lines = "\n".join(
                (
                    f"- {g.label}: {cls._fmt_comb(g.count, k, g.favorable_combinations)}"
                    if g.is_possible
                    else f"- {g.label}: مستحيلة (أقل من {k})"
                )
                for g in combo.groups
            )
            favs_sum = " + ".join(
                str(g.favorable_combinations) for g in combo.groups if g.is_possible
            )
            same = combo.same_group_favorable
            return (
                f"{prefix}بما أننا اقتصرنا على الألوان الممكنة، نحسب **الحالات الملائمة**:\n\n"
                f"{favs_lines}\n\n"
                f"نجمعها: {favs_sum} = {same}\n\n"
                f"والآن سؤالٌ يقودنا للخطوة التالية: كم عدد **كل** الطرق الممكنة لسحب {k} كرات من {n}؟"
            )
        # خطوة المقام (كل الطرق).
        if focus == "ratio":
            return (
                f"{prefix}**كل الطرق الممكنة** لسحب {k} من {n}:\n\n"
                f"{cls._fmt_comb(n, k, total)}\n\n"
                f"الآن لديك البسط والمقام — كيف تُكوّن منهما الاحتمال؟"
            )
        # افتراضي: الحلّ الرمزي الكامل المتدرّج (fallback).
        return cls._build_symbolic_reveal("", None, acknowledge=acknowledge) or (
            f"{prefix}لنُكمل معاً خطوةً بخطوة."
        )

    #: D-158: مُعرّف المكوّن المعرفي لمسار الحادثة A (نفس اللون) في tutor_state.kc_progress.
    _KC_PROB_A: str = "prob_event_a"
    #: D-159 (WP-E): مُعرّف مكوّن الحادثة B (جداء الأرقام فردي) — المحرّك متعدد العُقد.
    _KC_PROB_B: str = "prob_event_b"

    @classmethod
    def _load_canonical_parity(
        cls, _question: str, history_messages: list[dict[str, str]] | None
    ) -> dict[str, int] | None:
        """D-159 (WP-E): توزيع أرقام كرات التمرين الرسمي (odd/even/zero/total) — حتمي.

        يقرأ **أسئلة-فقط** (مناعة ISS-120) ويستخدم `number_parity_counts` (D-143) —
        صفر LLM؛ يُغذّي عقدة الحادثة B في محرّك الدور. None عند تعذّر أي خطوة (fail-open).
        """
        try:
            from app.services.capabilities.exercise_retrieval import (
                ExerciseRetrievalRequest,
                detect_exercise_retrieval,
                load_exercise_questions_only,
            )
            from app.services.skills.probability_skill import ProbabilityCalculatorSkill

            _decision = detect_exercise_retrieval(
                ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024"),
                history_messages=history_messages,
            )
            if not (_decision.recognized and _decision.matched_entry):
                return None
            _official = load_exercise_questions_only(_decision.matched_entry)
            if not _official:
                return None
            return ProbabilityCalculatorSkill.number_parity_counts(_official)
        except Exception:  # pragma: no cover - fail-safe
            logger.warning("_load_canonical_parity_failed", exc_info=True)
            return None

    @classmethod
    def _cognitive_turn(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
        tutor_state: dict | None,
        _policy_decision=None,  # D-158 Phase 1: محجوز (القرار من kc_progress، لا policy بعد)
    ) -> tuple[str | None, dict | None]:
        """D-158/D-159: طبقة القرار الموحَّدة فوق ``tutor_state`` المُخزَّن (حتمية، صفر LLM).

        المصدر الوحيد للقرار = ``kc_progress`` الدائم (لا مسح نصّ) عبر المخطط المُهيكَل
        `kc_progress_schema` (D-159 WP-A — لا dict literals يدوية بعد اليوم). تقتل
        الأعراض الثلاثة بنيوياً وعبر الكتل:
        - **S2** (أعلى أولوية): إجابة رقمية صحيحة ⇒ اعتراف + تقدّم — على المستوى الأعلى،
          لا تمرّ عبر `_in_socratic_dialogue` فينكسر سجن الـ600-حرف (رسالة سابقة طويلة لم
          تعد تُخفي إجابة الطالب الصحيحة).
        - **S3**: أول تفاعل مع المكوّن ⇒ سؤال تشخيصي (لا تفريغ) — مقاد بالحالة الدائمة
          لا بقوائم علامات هشّة («كيف نحسب» = «كيف افهم»).
        - **S1**: غير ذلك ⇒ خطوة **واحدة** لم تُعرَض بعد (``representations_delivered``)
          عبر `_build_symbolic_step`؛ التفريغ الكامل غير ممكن (السجل الدائم يمنع التكرار).

        D-159 (WP-E): المحرّك **متعدد العُقد** — بعد إتقان `prob_event_a` ينتقل تلقائياً
        إلى `prob_event_b` (جداء الأرقام فردي؛ الأرقام من `number_parity_counts` الحتمي
        D-143) — آلة حالات معرفية حقيقية لا عقدة واحدة مُجمَّدة.

        يُرجِع ``(text, kc_progress_delta)`` أو ``(None, None)`` (تسليم للكتل القائمة).
        يحقن الدلتا أيضاً في ``tutor_state["kc_progress_delta"]`` (dict مشترك) ليحفظها
        customer_chat عبر ``record_turn``.
        """
        try:
            if not isinstance(tutor_state, dict):
                return None, None
            # D-159 (ISS-125 lesson): بوّابة سياق الاحتمالات **قبل** أي تحميل — مع التفعيل
            # الافتراضي كان المحرّك يختطف أسئلة عامة (قانون نيوتن!) لأن مُحمّل التمرين
            # الرسمي يتعرّف دائماً. المحرّك يعمل فقط حين يكون السؤال/الحوار احتمالياً فعلاً.
            _ct_hist = " ".join(
                str(m.get("content", "")) for m in (history_messages or []) if isinstance(m, dict)
            )
            if not cls._is_prob_context(f"{question} {_ct_hist}"):
                return None, None
            # طلب محتوى/تمرين جديد صريح ⇒ ليس تفاعل تدريس (تسليم للاسترجاع).
            _low = (question or "").strip().lower()
            if any(m in _low for m in ("اعطني", "أعطني", "اعطيني", "هات", "اكتب", "ارسم", "درس")):
                return None, None
            # حارس تبديل الموضوع (D-101): سؤال غير احتمالي ⇒ تسليم للكتل.
            with contextlib.suppress(Exception):
                from app.services.capabilities.arabic_normalize import primary_canonical_topic

                _topic = primary_canonical_topic(question)
                if _topic is not None and _topic.canonical_id != "probability":
                    return None, None
            combo = cls._load_canonical_combinations(question, history_messages)
            if combo is None:
                return None, None

            from app.services.skills.kc_progress_schema import (
                PENDING_KEY,
                make_pending,
                parse_kc_entry,
                pending_of,
            )

            kc_progress = tutor_state.get("kc_progress")
            kc_progress = kc_progress if isinstance(kc_progress, dict) else {}
            pending = pending_of(kc_progress)
            entry_a = parse_kc_entry(kc_progress.get(cls._KC_PROB_A))
            turn_no = int(tutor_state.get("turn_count") or 0) + 1

            # D-159 (WP-E): اختيار العقدة النشطة — إتقان A ينقل المحرّك للحادثة B تلقائياً.
            active_kc = cls._KC_PROB_A
            parity: dict[str, int] | None = None
            if entry_a.state == "understood":
                parity = cls._load_canonical_parity(question, history_messages)
                if parity and int(parity.get("odd", 0)) >= int(combo.k):
                    active_kc = cls._KC_PROB_B
            entry = (
                entry_a
                if active_kc == cls._KC_PROB_A
                else parse_kc_entry(kc_progress.get(cls._KC_PROB_B))
            )

            def _finish(
                text: str,
                *,
                advance_state: str | None = None,
                clear_pending: bool = False,
                add_step: str | None = None,
                new_pending: str | None = None,
            ) -> tuple[str, dict]:
                if add_step:
                    entry.mark_delivered(add_step)
                if advance_state:
                    entry.state = advance_state
                entry.updated_turn = turn_no
                entry.last_emitted_hash = cls._norm_for_dedup(text)[:120]
                delta: dict = {active_kc: entry.to_dict()}
                if clear_pending:
                    delta[PENDING_KEY] = {}
                elif new_pending:
                    delta[PENDING_KEY] = make_pending(active_kc, new_pending)
                tutor_state["kc_progress_delta"] = delta
                return text, delta

            if active_kc == cls._KC_PROB_B:
                return cls._cognitive_turn_event_b(
                    question, history_messages, combo, parity, entry, _finish
                )

            # ── F2 (D-160/ISS-126): طلب شرح اشتقاق خطوة/قيمة («كيف حسبنا 4») ⇒ يُعلّم
            #    اشتقاق تلك الجزئية (يُعيد استخدام _build_probability_direct_explanation،
            #    forced_subpart)، dedup-محروس. يقتل الكارثة الجذرية: كان «كيف حسبنا 4»
            #    يسقط للإنقاذ النهائي المكرَّر «ركّب بنفسك» لأن لا فرع يشرح اشتقاق قيمة.
            #    **قبل S2**: طلب الشرح الصريح (بعلامة) يهزم تحقّق الإجابة الرقمية — «كيف
            #    حسبنا 14» شرحٌ لا إجابةَ «14» (لا اختطاف). الإجابة بلا علامة تبقى لـ S2.
            _explain_part = cls._detect_step_explanation(question, combo)
            if _explain_part is not None:
                _teach = cls._build_probability_direct_explanation(
                    question, history_messages, forced_subpart=_explain_part
                )
                if _teach and not cls._recently_emitted(_teach, history_messages):
                    entry.attempts += 1
                    return _finish(_teach, add_step=_explain_part)

            # السؤال المعلّق (D-155/D-158): kc_progress الدائم أولاً ثم اشتقاق التاريخ.
            _pending_focus = (
                pending[1] if pending and pending[0] == cls._KC_PROB_A else None
            ) or cls._pending_focus_from_history(history_messages)

            # ── F2b (D-162/ISS-128): سؤال التسمية («ماذا نسمي حساب 4 و 10؟») يُجاب
            #    بالاسم (التوافيق — data-driven من combo) + إعادة طرح السؤال المعلّق،
            #    مع إبقاء pending كما هو (لا تقدّم زائف). حتمي، صفر LLM. ──
            _is_q = cls._is_question_not_answer(question)
            if _is_q and cls._detect_naming_question(question, combo):
                _name_text = cls._build_naming_answer(combo, _pending_focus)
                if _name_text and not cls._recently_emitted(_name_text, history_messages):
                    entry.attempts += 1
                    return _finish(_name_text)

            # ── S2: إجابة رقمية صحيحة ⇒ اعتراف + تقدّم (المستوى الأعلى — لا سجن 600-حرف) ──
            _numeric = cls._verify_numeric_answer(question, combo, _pending_focus)
            if _numeric == "final_ratio":
                entry.attempts += 1
                entry.evidence = "verified"
                text = (
                    "أحسنت! ✅ إجابتك صحيحة تماماً — ركّبت احتمال الحادثة A بنفسك: "
                    "الحالات الملائمة على كل الحالات الممكنة.\n\n"
                    "ننتقل للسؤال التالي في التمرين — **الحادثة B**: جداء الأرقام "
                    "عدد فردي. قبل أي حساب، سؤال واحد: متى يكون جداء ثلاثة أعداد فردياً؟"
                )
                text, delta = _finish(text, advance_state="understood", clear_pending=True)
                # D-159 (WP-E): بذر عقدة الحادثة B — سؤالها التشخيصي طُرح في النصّ نفسه،
                # فتُسجَّل الحالة صادقةً: probe مُسلَّم + السؤال المعلّق صار على B.
                entry_b = parse_kc_entry(kc_progress.get(cls._KC_PROB_B))
                entry_b.mark_delivered("diagnostic_probe")
                entry_b.state = "explained"
                entry_b.updated_turn = turn_no
                delta[cls._KC_PROB_B] = entry_b.to_dict()
                delta[PENDING_KEY] = make_pending(cls._KC_PROB_B, "parity")
                return text, delta
            if _numeric in ("step_correct", "direction"):
                text = cls._build_symbolic_step(combo, "ratio", acknowledge=True)
                if not cls._recently_emitted(text, history_messages):
                    entry.attempts += 1
                    entry.evidence = "verified"
                    return _finish(text, add_step="ratio", new_pending="ratio")

            entry.attempts += 1

            # ── S3: أول تفاعل ⇒ التشخيص قبل الشرح ──
            if "diagnostic_probe" not in entry.representations_delivered:
                text = cls._build_diagnostic_probe(combo)
                return _finish(
                    text,
                    advance_state="explained",
                    add_step="diagnostic_probe",
                    new_pending="numerator",
                )

            # ── D-162 (ISS-128): سؤال وسط الحوار (بعد probe) لم تُجبه F2/التسمية ⇒
            #    يهرب لطبقات الإجابة (D-124/D-125/D-132 ثم LLM المحروس) — سُلّم S1
            #    الأعمى للأدوار غير الاستفهامية حصراً (كان سيكشف 165 متجاهلاً السؤال).
            #    أسئلة «كيف/كيفاش» الإجرائية تبقى لسلسلة F2/F1/F3 التعليمية (D-160). ──
            _qg = (question or "").strip().lower()
            if _qg.startswith("و "):
                _qg = _qg[2:].lstrip()
            if _is_q and not _qg.startswith(("كيف", "كيفاش")):
                return None, None

            # ── S1: كشف تدريجي — خطوة واحدة لم تُعرَض بعد (لا تفريغ كامل) ──
            for step in ("numerator", "ratio"):
                if step in entry.representations_delivered:
                    continue
                text = cls._build_symbolic_step(combo, step)
                if cls._recently_emitted(text, history_messages):
                    continue
                # D-162 (ISS-128): pending = بؤرة **السؤال المطروح فعلاً** في نصّ
                # الخطوة، لا اسم الخطوة المُسلَّمة — خطوة البسط تسأل عن المقام
                # («كم عدد كل الطرق الممكنة؟»)؛ تخزين "numerator" جعل {4,10} في
                # سؤالٍ لاحق تُعترف step_correct (favs ⊆ nums) — كارثة الترانسكريبت.
                return _finish(
                    text,
                    add_step=step,
                    new_pending=("denominator" if step == "numerator" else step),
                )

            # ── F1 (D-160): الإنقاذ النهائي محروس ضد التكرار (كان يُرجَع بلا حارس ⇒
            #    كارثة الترانسكريبت ×3). حين لا يكون مكرَّراً ⇒ يُبَثّ. ──
            text = cls._build_symbolic_reveal(
                question,
                history_messages,
                acknowledge=bool(_numeric),
                delivered=set(entry.representations_delivered),
            )
            if text and not cls._recently_emitted(text, history_messages):
                return _finish(text, new_pending="ratio")

            # ── F3 (D-160): الإنقاذ مكرَّر ⇒ الطالب العالق يتعلّم لا يدور: علّم اشتقاق
            #    أصغر جزئية ملموسة لم تُعرَض بعد (لا كشف P(A) النهائي — يحترم M6/M8). ──
            for _part in ("red", "green", "white", "total", "sum"):
                if _part in entry.representations_delivered:
                    continue
                _t = cls._build_probability_direct_explanation(
                    question, history_messages, forced_subpart=_part
                )
                if _t and not cls._recently_emitted(_t, history_messages):
                    return _finish(_t, add_step=_part)

            # كل شيء عُلِّم ومكرَّر ⇒ تسليم للكتل (fail-open) بدل إعادة نصّ مكرَّر.
            return None, None
        except Exception:  # pragma: no cover - fail-safe (never abort a turn)
            logger.warning("_cognitive_turn_failed", exc_info=True)
            return None, None

    @classmethod
    def _cognitive_turn_event_b(
        cls,
        question: str,
        history_messages: list[dict[str, str]] | None,
        combo,
        parity: dict[str, int] | None,
        entry,
        _finish,
    ) -> tuple[str | None, dict | None]:
        """D-159 (WP-E): دور الحادثة B (جداء الأرقام فردي) — حتمي من المحرك الرمزي.

        الأرقام من `number_parity_counts` (D-143) حصراً: عدد الكرات الفردية o ⇒ الحالات
        الملائمة C(o,k)؛ المقام نفسه من الجزء A. صفر LLM؛ النصوص تَنجو من حجب D-113
        (نمط `_fmt_comb` LaTeX + أسئلة توليد — النسبة النهائية لا تُطبع أبداً D-154).
        """
        import math

        if not parity:
            return None, None
        odd = int(parity.get("odd", 0))
        k = int(combo.k)
        total = int(combo.total_combinations)
        n = int(combo.n)
        fav_b = math.comb(odd, k) if odd >= k else 0
        if fav_b <= 0:
            return None, None

        # ── S2-B: إجابة رقمية صحيحة على B ⇒ اعتراف + إقفال العقدة ──
        nums = cls._extract_answer_numbers(question)
        if fav_b in nums and total in nums:
            entry.attempts += 1
            entry.evidence = "verified"
            text = (
                "أحسنت! ✅ ركّبت احتمال الحادثة B بنفسك — الحالات الملائمة على كل "
                "الحالات الممكنة.\n\n"
                "أنجزت الحادثتين A و B بيديك. حين تريد نتابع بقية أجزاء التمرين "
                "(الحادثة C أو المتغيّر العشوائي) بنفس الطريقة — أيّها تختار؟"
            )
            return _finish(text, advance_state="understood", clear_pending=True)
        if nums and (fav_b in nums or odd in nums):
            # خطوة صحيحة (وجد عدد الفرديات أو الحالات الملائمة) ⇒ اعتراف + خطوة النسبة.
            text = (
                "إجابتك في الطريق الصحيح — هذا بالضبط ما نحتاجه للحادثة B.\n\n"
                f"وكل الطرق الممكنة لم تتغيّر عن الجزء السابق (نفس الكيس ونفس السحب): "
                f"{cls._fmt_comb(n, k, total)}\n\n"
                "الآن لديك البسط والمقام — كيف تُكوّن منهما احتمال الحادثة B؟"
            )
            if not cls._recently_emitted(text, history_messages):
                entry.attempts += 1
                entry.evidence = "verified"
                return _finish(text, add_step="ratio", new_pending="ratio")

        entry.attempts += 1

        # ── S3-B: التشخيص قبل الشرح (يُبذَر عادةً من نهاية الجزء A) ──
        if "diagnostic_probe" not in entry.representations_delivered:
            text = (
                "ننتقل للحادثة B: **جداء الأرقام الثلاثة عدد فردي**.\n\n"
                "سؤال واحد قبل أي حساب: متى يكون جداء ثلاثة أعداد فردياً؟ "
                "وأيّ كرات الكيس تحمل أرقاماً فردية؟"
            )
            return _finish(
                text,
                advance_state="explained",
                add_step="diagnostic_probe",
                new_pending="parity",
            )

        # ── S1-B: كشف تدريجي — خطوة واحدة لم تُعرَض بعد ──
        if "numerator" not in entry.representations_delivered:
            text = (
                "الجداء يكون فردياً فقط إذا كانت **كل** الأرقام الثلاثة فردية — "
                f"فنقتصر على الكرات ذات الأرقام الفردية وعددها {odd}.\n\n"
                f"الحالات الملائمة للحادثة B: {cls._fmt_comb(odd, k, fav_b)}\n\n"
                "والآن سؤالٌ يقودنا للخطوة التالية: كم عدد **كل** الطرق الممكنة للسحب؟"
            )
            if not cls._recently_emitted(text, history_messages):
                return _finish(text, add_step="numerator", new_pending="numerator")
        if "ratio" not in entry.representations_delivered:
            text = (
                f"**كل الطرق الممكنة** لم تتغيّر عن الجزء السابق: "
                f"{cls._fmt_comb(n, k, total)}\n\n"
                "الآن لديك البسط والمقام — كيف تُكوّن منهما احتمال الحادثة B؟"
            )
            if not cls._recently_emitted(text, history_messages):
                return _finish(text, add_step="ratio", new_pending="ratio")

        # كل الخطوات عُرضت ⇒ مُوجّه توليد (لا كشف للنسبة النهائية — D-113/D-154).
        text = (
            "أمامك الآن كل المكوّنات — ركّب احتمال الحادثة B **بنفسك**: "
            "الحالات الملائمة على كل الحالات الممكنة. فما النسبة التي تحصل عليها؟"
        )
        if cls._recently_emitted(text, history_messages):
            return None, None  # تسليم للكتل القائمة بدل بثّ مكرَّر (قاعدة D-154).
        return _finish(text, new_pending="ratio")

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
