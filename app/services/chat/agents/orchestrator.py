"""
وكيل التنسيق (OrchestratorAgent) — قشرة الاستقبال ودورة الدور (D-253).


**لماذا هذا الملف رُفِّق (CodeScene X-Ray):** كان هذا الملف hotspotًا حيًا:
تعقيد `_handle_content_retrieval` C(14) و`_build_recent_history_brief` C(12)
و`_handle_chat_fallback` B(10) و`_extract_context_anchor` B(10) وتردد تغيير
عالٍ — مركز ثقل معماري واحد يحمل استخراج الفلاتر والشرح والمحادثة الاحتياطية
وسياق التاريخ واسترجاع المحتوى معًا.

**الجراحة (D-253 — نمط D-252 «القشرة + دورة الدور»):** كل منطق الدور انتقل
إلى `app/services/chat/agents/orchestrator_support/` في خمس شرائح نقية:
`search_params.py` (استخلاص فلاتر البحث) · `explanation.py` (الشرح التربوي
على الحل الرسمي) · `chat_fallback.py` (المحادثة الاحتياطية + كتل سلم التنقيط)
· `history_context.py` (المرجعية الضمنية والموجز) · `content_retrieval.py`
(تصنيف النوع وقرارات التسليم). هذا الملف بقي **قشرة استقبال وتفويض**: كشف
النية، التقاط الذاكرة (best effort)، التفويض للوكلاء، والحارس النصي العام
للفشل. **صفر تغيير سلوكي**: التوقيعات العامة (`run` · `__init__` ·
`data_agent` · `refactor_agent`) والأسماء الخاصة السابقة (كـ`_handle_chat_fallback`
و`_ai_extract_search_params`) محفوظة كقشرة تفوّض حرفًا إلى الشرائح — فيبقى كل
monkeypatch واختبار على الأسماء القديمة فعالًا (قانون late-binding من D-252).

**تغذية الحراس النصية:** المانيفست
`orchestrator_support/_sources.py` يركّب المصدر المركّب عبر
`read_orchestrator_agent_source()` — كل حاجزٍ نصي (skills_doctrine · legacy
noop · canonical/ownership fences) يقرأ السلوك المفكك كاملًا لا القشرة فقط.
"""

import logging
from collections.abc import AsyncGenerator

from app.core.ai_config import ActiveModels
from app.core.ai_gateway import AIClient
from app.services.chat.agents.admin import AdminAgent
from app.services.chat.agents.analytics import AnalyticsAgent
from app.services.chat.agents.curriculum import CurriculumAgent
from app.services.chat.agents.data_access import DataAccessAgent
from app.services.chat.agents.education_council import EducationCouncil
from app.services.chat.agents.orchestrator_support import chat_fallback as _chat_fallback_shard
from app.services.chat.agents.orchestrator_support import (
    content_retrieval as _content_retrieval_shard,
)
from app.services.chat.agents.orchestrator_support import (
    explanation as _explanation_shard,
)
from app.services.chat.agents.orchestrator_support import (
    history_context as _history_context_shard,
)
from app.services.chat.agents.orchestrator_support import (
    search_params as _search_params_shard,
)
from app.services.chat.agents.refactor import RefactorAgent
from app.services.chat.context_service import get_context_service
from app.services.chat.graph.components.context_composer import (
    _extract_requested_index,
    _extract_section_by_index,
)
from app.services.chat.graph.components.intent_detector import RegexIntentDetector
from app.services.chat.graph.domain import WriterIntent
from app.services.chat.intent_detector import ChatIntent, IntentDetector
from app.services.chat.tools import ToolRegistry

logger = logging.getLogger("orchestrator-agent")


def _extract_marking_scheme_blocks(content: str) -> list[str]:
    """
    استخراج كتل سلم التنقيط من النص الخام إذا كانت مضمّنة (إعادة تصدير من الشريحة).
    """
    return _chat_fallback_shard.extract_marking_scheme_blocks(content)


class _ContentDeliveryPlan:
    """قرارات تسليم محتوى استرجاعٍ واحد (D-253) — تجمّع الصلاحيات الثلاث."""

    def __init__(
        self,
        include_solution: bool = False,
        exclude_solution: bool = False,
        include_grading: bool = False,
    ) -> None:
        self.include_solution = include_solution
        self.exclude_solution = exclude_solution
        self.include_grading = include_grading


class OrchestratorRunResult:
    """
    نتيجة تشغيل وكيل التنسيق.

    تدعم البث عبر التكرار غير المتزامن، كما تسمح بانتظار النتيجة كنص كامل.
    """

    def __init__(self, stream: AsyncGenerator[str, None]) -> None:
        self._stream = stream

    def __aiter__(self) -> AsyncGenerator[str, None]:
        return self._stream

    def __await__(self):
        async def _collect() -> str:
            chunks: list[str] = []
            async for chunk in self._stream:
                chunks.append(chunk)
            return "".join(chunks)

        return _collect().__await__()


class OrchestratorAgent:
    """
    الوكيل المنسق (Orchestrator Agent) — قشرة استقبال وتفويض (D-253).

    يعمل كنقطة دخول مركزية لتوجيه الطلبات إلى الوكلاء المتخصصين.
    منطق دورة الدور المفصّل (استرجاع المحتوى · الشرح · الاحتياطية · سياق
    التاريخ) يعيش في `orchestrator_support/` وليس هنا — هذا ملف القشرة وحسب.
    """

    def __init__(self, ai_client: AIClient, tools: ToolRegistry) -> None:
        self.ai_client = ai_client
        self.tools = tools
        self.intent_detector = IntentDetector()

        # Sub-Agents
        self.admin_agent = AdminAgent(tools, ai_client=ai_client)
        self.analytics_agent = AnalyticsAgent(tools, ai_client)
        self.curriculum_agent = CurriculumAgent(tools)
        self.education_council = EducationCouncil(tools)

    @property
    def data_agent(self) -> DataAccessAgent:
        """إتاحة وكيل البيانات للوصول والاختبار."""
        return self.admin_agent.data_agent

    @data_agent.setter
    def data_agent(self, value: DataAccessAgent) -> None:
        self.admin_agent.data_agent = value

    @property
    def refactor_agent(self) -> RefactorAgent:
        """إتاحة وكيل التحسينات للوصول والاختبار."""
        return self.admin_agent.refactor_agent

    @refactor_agent.setter
    def refactor_agent(self, value: RefactorAgent) -> None:
        self.admin_agent.refactor_agent = value

    def run(self, question: str, context: dict[str, object] | None = None) -> OrchestratorRunResult:
        """
        واجهة موحدة لمعالجة الطلبات مع دعم البث أو التجميع النصي.
        """
        return OrchestratorRunResult(self._run_stream(question, context))

    async def _run_stream(
        self,
        question: str,
        context: dict[str, object] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        التنفيذ الفعلي لمسار البث (قشرة التفويض — D-253).
        """
        logger.info(f"Orchestrator received: {question}")
        normalized = question.strip()
        context = context or {}
        normalized = self._resolve_contextual_reference(normalized, context)
        normalized = self._inject_recent_history_context(normalized, context)

        # 1. Intent Detection
        if "intent" in context and isinstance(context["intent"], ChatIntent):
            intent = context["intent"]
        else:
            intent_result = await self.intent_detector.detect(normalized)
            intent = intent_result.intent

        # 2. Memory Capture (Best Effort)
        await self._capture_memory_intent(normalized, intent)

        # 3. Dispatch
        try:
            async for chunk in self._dispatch_intent(intent, normalized, context):
                yield chunk
        except Exception as e:
            logger.error(f"Orchestrator dispatch failed: {e}", exc_info=True)
            yield "عذرًا، حدث خطأ غير متوقع أثناء معالجة طلبك."

    async def _capture_memory_intent(self, question: str, intent: ChatIntent) -> None:
        pass

    async def _dispatch_curriculum(
        self, question: str, context: dict[str, object]
    ) -> AsyncGenerator[str, None]:
        """قشرة تفويض — معالجة نية التخطيط المنهاجي (D-253)."""
        self._enrich_curriculum_context(context, question)
        context["user_message"] = question
        result = self.curriculum_agent.process(context)
        if hasattr(result, "__aiter__"):
            async for chunk in result:
                yield chunk
        else:
            yield str(result)

    async def _dispatch_intent(
        self,
        intent: ChatIntent,
        question: str,
        context: dict[str, object],
    ) -> AsyncGenerator[str, None]:
        """تفويض النية إلى الوكيل المتخصص (قشرة التفويض — D-253)."""
        if intent in {ChatIntent.ADMIN_QUERY, ChatIntent.CODE_SEARCH, ChatIntent.PROJECT_INDEX}:
            async for chunk in self.admin_agent.run(question, context):
                yield chunk
            return

        if intent in (ChatIntent.ANALYTICS_REPORT, ChatIntent.LEARNING_SUMMARY):
            result = self.analytics_agent.process(context)
            if hasattr(result, "__aiter__"):
                async for chunk in result:
                    yield chunk
            else:
                yield str(result)
            return

        if intent == ChatIntent.CURRICULUM_PLAN:
            async for chunk in self._dispatch_curriculum(question, context):
                yield chunk
            return

        if intent == ChatIntent.CONTENT_RETRIEVAL:
            async for chunk in self._handle_content_retrieval(question, context):
                yield chunk
            return

        async for chunk in self._handle_chat_fallback(question, context):
            yield chunk

    def _enrich_curriculum_context(self, context: dict, question: str) -> None:
        lowered = question.lower()
        if any(x in lowered for x in ["مسار", "path", "تقدم", "progress"]):
            context["intent_type"] = "path_progress"
        elif any(x in lowered for x in ["صعب", "hard", "easy", "سهل"]):
            context["intent_type"] = "difficulty_adjust"
            context["feedback"] = "too_hard" if "صعب" in lowered else "good"
        else:
            context["intent_type"] = "recommendation"

    def _resolve_contextual_reference(self, question: str, context: dict[str, object]) -> str:
        """قشرة تفويض — الشريحة في `history_context._resolve_contextual_reference`."""
        return _history_context_shard.resolve_contextual_reference(question, context)

    def _extract_context_anchor(
        self,
        *,
        context: dict[str, object],
        current_question: str,
    ) -> str | None:
        """قشرة تفويض — الشريحة في `history_context.extract_context_anchor`."""
        return _history_context_shard.extract_context_anchor(
            history_messages=context.get("history_messages"),
            current_question=current_question,
        )

    def _looks_like_pronoun_followup(self, question: str) -> bool:
        """قشرة تفويض — الشريحة في `history_context.looks_like_pronoun_followup`."""
        return _history_context_shard.looks_like_pronoun_followup(question)

    def _inject_recent_history_context(self, question: str, context: dict[str, object]) -> str:
        """قشرة تفويض — الشريحة في `history_context.inject_recent_history_context`."""
        return _history_context_shard.inject_recent_history_context(question, context)

    def _build_recent_history_brief(
        self,
        *,
        context: dict[str, object],
        current_question: str,
    ) -> str:
        """قشرة تفويض — الشريحة في `history_context.build_recent_history_brief`."""
        return _history_context_shard.build_recent_history_brief(
            history_messages=context.get("history_messages"),
            current_question=current_question,
        )

    async def _handle_content_retrieval(
        self, question: str, context: dict
    ) -> AsyncGenerator[str, None]:
        """
        معالجة استرجاع المحتوى (قشرة التفويض — D-253):
        1. استخراج الفلاتر بذكاء (AI Extraction) من النص الطبيعي.
        2. البحث عن IDs باستخدام search_content (الذي يدعم الآن الكلمات المتعددة).
        3. جلب المحتوى الخام وعرضه.
        4. توليد الشرح.
        """
        logger.info(f"Handling content retrieval for: {question}")

        # Step 1: Intelligent Search Parameter Extraction using LLM
        params = await self._ai_extract_search_params(question)

        candidates = await self.tools.execute("search_content", params)

        if not candidates:
            logger.info(_content_retrieval_shard.NO_CONTENT_FOUND_LOG)
            # Inject a hint into context so fallback knows we missed a search
            context["search_miss"] = True
            async for chunk in self._handle_chat_fallback(question, context):
                yield chunk
            return

        # Pick the best candidate (Logic: Top 1)
        best_candidate = _content_retrieval_shard.select_best_candidate(candidates)
        if best_candidate is None:
            logger.info(_content_retrieval_shard.NO_CONTENT_FOUND_LOG)
            context["search_miss"] = True
            async for chunk in self._handle_chat_fallback(question, context):
                yield chunk
            return

        content_id = best_candidate["id"]
        title = best_candidate["title"]

        yield f"{_content_retrieval_shard.CONTENT_FOUND_PREFIX} {title} ({content_id})\n\n"

        # Step 2: Determine if user wants solution
        writer_intent = RegexIntentDetector().analyze(question)

        # Logic: Only include solution if EXPLICITLY requested, NOT by default
        include_solution = writer_intent in (
            WriterIntent.SOLUTION_REQUEST,
            WriterIntent.GRADING_REQUEST,
        )
        exclude_solution = writer_intent == WriterIntent.QUESTION_ONLY_REQUEST
        include_grading = writer_intent == WriterIntent.GRADING_REQUEST

        # Log for debugging
        logger.info(
            f"Writer intent: {writer_intent}, include_solution: {include_solution}, exclude_solution: {exclude_solution}"
        )

        raw_data = await self.tools.execute(
            "get_content_raw",
            {
                "content_id": content_id,
                "include_solution": include_solution and not exclude_solution,
            },
        )

        if not raw_data or not raw_data.get("content"):
            yield _content_retrieval_shard.NO_CONTENT_FOUND
            return

        async for chunk in self._deliver_retrieved_content(
            question,
            context,
            raw_data,
            _ContentDeliveryPlan(
                include_solution=include_solution,
                exclude_solution=exclude_solution,
                include_grading=include_grading,
            ),
        ):
            yield chunk

    async def _deliver_retrieved_content(
        self,
        question: str,
        context: dict[str, object],
        raw_data: dict[str, object],
        plan: "_ContentDeliveryPlan",
    ) -> AsyncGenerator[str, None]:
        """المرحلة الثالثة — عرض المحتوى والشرح وسلم التنقيط (D-253)."""
        full_content = raw_data["content"]
        content_text = full_content
        requested_index = _extract_requested_index(question)
        if requested_index is not None:
            extracted = _extract_section_by_index(full_content, requested_index)
            if extracted:
                content_text = extracted
        yield _content_retrieval_shard.CONTENT_SEPARATOR
        yield content_text
        yield _content_retrieval_shard.CONTENT_TRAILER

        if plan.include_solution and not plan.exclude_solution:
            personalization_context = await self._build_education_brief(context)
            solution = raw_data.get("solution")
            async for chunk in self._generate_explanation(
                question, content_text, personalization_context, solution=solution
            ):
                yield chunk
        if plan.include_grading and not plan.exclude_solution:
            grading_blocks = _chat_fallback_shard.extract_marking_scheme_blocks(full_content)
            for delta in _chat_fallback_shard.format_marking_scheme_delivery(grading_blocks):
                yield delta
        else:
            yield _content_retrieval_shard.TRY_FIRST_ASK

    async def _ai_extract_search_params(self, question: str) -> dict:
        """قشرة تفويض — الشريحة في `search_params` (AI مع تراجعٍ حتمي)."""
        messages = _search_params_shard.build_search_param_messages(question)

        try:
            # D-067: استخدام PRIMARY model — nemotron-3-nano محظور (ISS-079, content=None)
            response = await self.ai_client.generate(
                model=ActiveModels.PRIMARY,
                messages=messages,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            params = _search_params_shard.parse_search_params(raw)
            if params is None:
                params = _search_params_shard.heuristic_extract_search_params(question)

            # Ensure limit default
            params["limit"] = 5

            # Fallback for 'q' if empty, use heuristic extraction
            if not params.get("q") and not params.get("year"):
                params = _search_params_shard.heuristic_extract_search_params(question)

            logger.info(f"AI extracted params: {params}")
            return params

        except Exception as e:
            logger.warning(f"AI parameter extraction failed: {e}. using heuristics.")
            return _search_params_shard.heuristic_extract_search_params(question)

    def _heuristic_extract_search_params(self, question: str) -> dict:
        """قشرة تفويض — الشريحة في `search_params.heuristic_extract_search_params`."""
        return _search_params_shard.heuristic_extract_search_params(question)

    async def _generate_explanation(
        self, question: str, content: str, personalization_context: str, solution: str | None = None
    ) -> AsyncGenerator[str, None]:
        """قشرة تفويض — الشريحة في `explanation` (شرح على الحل الرسمي كمصدر حقيقة)."""
        messages = [
            {
                "role": "system",
                "content": _explanation_shard.build_explanation_system_prompt(
                    personalization_context
                ),
            },
            {
                "role": "user",
                "content": _explanation_shard.build_explanation_user_message(
                    question, content, solution
                ),
            },
        ]
        async for chunk in self._stream_ai_chunks(messages):
            if hasattr(chunk, "choices"):
                delta = chunk.choices[0].delta if chunk.choices else None
                content_value = delta.content if delta else ""
            else:
                content_value = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")

            if content_value:
                yield content_value

    async def _handle_chat_fallback(
        self, question: str, context: dict
    ) -> AsyncGenerator[str, None]:
        """قشرة تفويض — الشرائح في `explanation` و`history_context` (المحادثة العامة)."""
        system_context = context.get("system_context", "")

        try:
            base_prompt = get_context_service().get_customer_system_prompt()
        except Exception:
            base_prompt = "أنت مساعد ذكي."

        # SMART TUTOR LOGIC
        # We permit general explanation if no specific exercise is loaded,
        # but strictly forbid fabricating specific numbers/exercises.
        strict_instruction = _chat_fallback_shard.FALLBACK_STRICT_INSTRUCTION

        personalization_context = await self._build_education_brief(context)

        # History
        history_text = _explanation_shard.build_fallback_history_text(
            context.get("history_messages", [])
        )

        messages = _explanation_shard.build_chat_fallback_messages(
            base_prompt=base_prompt,
            strict_instruction=strict_instruction,
            personalization_context=personalization_context,
            system_context=system_context,
            history_text=history_text,
            question=question,
        )

        async for chunk in self._stream_ai_chunks(messages):
            if hasattr(chunk, "choices"):
                delta = chunk.choices[0].delta if chunk.choices else None
                content_value = delta.content if delta else ""
            else:
                content_value = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")

            if content_value:
                yield content_value

    async def _build_education_brief(self, context: dict[str, object]) -> str:
        """بناء موجز تعليمي."""
        cached_context = context.get("education_brief")
        if isinstance(cached_context, str):
            return cached_context

        try:
            brief = await self.education_council.build_brief(context=context)
        except Exception as exc:
            logger.warning("Failed to build education brief: %s", exc)
            return ""

        rendered = brief.render()
        context["education_brief"] = rendered
        return rendered

    async def _stream_ai_chunks(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncGenerator[object, None]:
        """
        بث استجابات النموذج مع دعم نتائج قابلة للانتظار من AsyncMock.
        """
        if not self.ai_client:
            raise RuntimeError("عميل الذكاء الاصطناعي غير متوفر.")
        stream_result = self.ai_client.stream_chat(messages)
        if hasattr(stream_result, "__await__"):
            stream_result = await stream_result  # type: ignore[assignment]
        async for chunk in stream_result:
            yield chunk
