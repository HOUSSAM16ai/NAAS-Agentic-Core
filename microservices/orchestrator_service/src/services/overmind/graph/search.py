import asyncio
import os
import time
from types import SimpleNamespace

import anyio
from llama_index.core.schema import Document as LlamaDocument
from pydantic import BaseModel

try:
    import dspy
except ModuleNotFoundError:

    def _dspy_input_field(*_: object, **__: object) -> str:
        return ""

    def _dspy_output_field(*_: object, **__: object) -> str:
        return ""

    def _dspy_predict(*_: object, **__: object):
        def _runner(**_: object) -> SimpleNamespace:
            return SimpleNamespace(
                year=None,
                subject="",
                branch="",
                exercise_num=None,
                language="ar",
                needs_web=False,
            )

        return _runner

    class _DSPySignature:
        pass

    class _DSPyModule:
        Signature = _DSPySignature
        InputField = staticmethod(_dspy_input_field)
        OutputField = staticmethod(_dspy_output_field)
        Predict = staticmethod(_dspy_predict)

    dspy = _DSPyModule()  # type: ignore[assignment]

from microservices.orchestrator_service.src.core.logging import get_logger

# Assuming research_client is used for actual db access
from microservices.orchestrator_service.src.infrastructure.clients.research_client import (
    research_client,
)
from microservices.orchestrator_service.src.services.overmind.latex_normalizer import (
    LatexStreamNormalizer,
    normalize_latex,
)

logger = get_logger("search-graph")


# --- NODE 1: QueryAnalyzerNode ---
class AnalyzeQuery(dspy.Signature):
    """Extract structured filters from Arabic query.

    Do NOT guess or infer the year or exercise number.
    If it is not explicitly stated in the prompt, you MUST output None.
    """

    history: str = dspy.InputField(
        desc="Previous conversation context to resolve pronouns and context"
    )
    question: str = dspy.InputField()
    year: int | None = dspy.OutputField()
    subject: str = dspy.OutputField()
    branch: str = dspy.OutputField()
    exercise_num: int | None = dspy.OutputField()
    language: str = dspy.OutputField()
    needs_web: bool = dspy.OutputField()


class QueryFilters(BaseModel):
    question: str
    year: int | None = None
    subject: str = ""
    branch: str = ""
    exercise_num: int | None = None
    language: str = "ar"
    needs_web: bool = False


class QueryAnalyzerNode:
    def __init__(self):
        # Initializing the actual DSPy module
        self.analyzer = dspy.Predict(AnalyzeQuery)

    async def __call__(self, state: dict) -> dict:
        from .telemetry import emit_telemetry

        start_time = time.time()

        query = state.get("query", "")
        messages = state.get("messages", [])
        error = None

        # D-103: محتوى تمرين محقون ⇒ الاسترجاع سيتجاوز البحث الدلالي،
        # فلا حاجة لاستخراج filters عبر DSPy (يوفّر LLM call كامل).
        if str(state.get("exercise_content") or "").strip():
            emit_telemetry(node_name="QueryAnalyzerNode", start_time=start_time, state=state)
            return {"filters": QueryFilters(question=query)}

        from .main import format_conversation_history

        # Exclude the current user query from history ONLY for prompt formatting
        prompt_messages = messages
        if messages:
            last_msg = messages[-1]
            role = (
                last_msg.get("role") or last_msg.get("type")
                if isinstance(last_msg, dict)
                else getattr(last_msg, "type", getattr(last_msg, "role", ""))
            )
            if role in ("human", "user"):
                prompt_messages = messages[:-1]
        formatted_history = format_conversation_history(prompt_messages)

        try:

            def _coerce_nullable_int(value: object) -> int | None:
                text_value = str(value).strip().lower()
                if text_value in {"", "none", "null"}:
                    return None
                return int(text_value) if text_value.isdigit() else None

            prediction = await asyncio.wait_for(
                anyio.to_thread.run_sync(
                    lambda: self.analyzer(history=formatted_history, question=query)
                ),
                timeout=10.0,
            )
            filters = QueryFilters(
                question=query,
                year=_coerce_nullable_int(getattr(prediction, "year", None)),
                subject=str(prediction.subject),
                branch=str(prediction.branch),
                exercise_num=_coerce_nullable_int(getattr(prediction, "exercise_num", None)),
            )
        except Exception as e:
            logger.warning(f"DSPy parsing failed, returning empty filters: {e}")
            error = e
            filters = QueryFilters(
                question=query,
                year=None,
                subject="",
                branch="",
                exercise_num=None,
            )

        emit_telemetry(
            node_name="QueryAnalyzerNode", start_time=start_time, state=state, error=error
        )
        return {"filters": filters}


# --- NODE 2: InternalRetrieverNode ---
class InternalRetrieverNode:
    async def __call__(self, state: dict) -> dict:
        from .telemetry import emit_telemetry

        start_time = time.time()

        # D-103: محتوى تمرين محقون من الـ monolith ⇒ تجاوز البحث الدلالي كلياً.
        # المصدر الوحيد = المحتوى المحقون — لا vector DB، لا خلط تمارين، لا tags خام
        # (يُحيّد سبب منع D-052 بالبناء).
        injected_exercise = str(state.get("exercise_content") or "").strip()
        if injected_exercise:
            docs = [
                LlamaDocument(
                    text=injected_exercise,
                    metadata={"source": "محتوى التمرين المرفق", "score": 1.0},
                )
            ]
            emit_telemetry(
                node_name="InternalRetrieverNode",
                start_time=start_time,
                state=state,
                retrieval_source="injected_exercise",
            )
            return {"retrieved_docs": docs}

        filters: QueryFilters = state.get("filters")

        exact_filters: dict[str, int | str] = {}
        if filters.year is not None:
            exact_filters["year"] = filters.year
        if filters.branch:
            exact_filters["branch"] = filters.branch
        if filters.subject:
            exact_filters["subject"] = filters.subject
        if filters.exercise_num is not None:
            exact_filters["exercise_num"] = filters.exercise_num
        try:
            exact_results = await asyncio.wait_for(
                research_client.semantic_search(
                    query=filters.question, top_k=5, filters=exact_filters
                ),
                timeout=10.0,
            )

            if exact_results:
                docs = [
                    LlamaDocument(
                        text=res.get("content", ""),
                        metadata={
                            "source": "قاعدة البيانات الداخلية",
                            "score": res.get("score", 1.0),
                        },
                    )
                    for res in exact_results
                ]
                emit_telemetry(
                    node_name="InternalRetrieverNode",
                    start_time=start_time,
                    state=state,
                    retrieval_source="internal_exact",
                )
                return {"retrieved_docs": docs}

            # To prevent 'Ghost Exam' injection, do not default to empty filters for generic queries
            # if we have no exact match. We should still apply whatever partial filters were extracted.
            # If the user says "تمرين احتمالات", exact_filters has {'subject': 'احتمالات'}.
            # We broaden top_k but keep exact_filters to prevent returning a random 2024 exam.
            semantic_results = await asyncio.wait_for(
                research_client.semantic_search(
                    query=filters.question, top_k=15, filters=exact_filters
                ),
                timeout=10.0,
            )
            docs = [
                LlamaDocument(
                    text=res.get("content", ""),
                    metadata={"source": "قاعدة البيانات الداخلية", "score": res.get("score", 0.5)},
                )
                for res in semantic_results
            ]
            emit_telemetry(
                node_name="InternalRetrieverNode",
                start_time=start_time,
                state=state,
                retrieval_source="internal_hybrid",
            )
            return {"retrieved_docs": docs}
        except Exception as e:
            emit_telemetry(
                node_name="InternalRetrieverNode", start_time=start_time, state=state, error=e
            )
            return {"retrieved_docs": []}


# --- NODE 3: RerankerNode ---
class RerankerNode:
    def __init__(self):
        try:
            from llama_index.postprocessor.flag_embedding_reranker import FlagEmbeddingReranker

            self.reranker = FlagEmbeddingReranker(
                model="cross-encoder/ms-marco-MiniLM-L-6-v2", top_n=5
            )
        except ImportError:
            self.reranker = None
            logger.warning("FlagEmbeddingReranker not installed, falling back to simple sort.")

    async def __call__(self, state: dict) -> dict:
        from .telemetry import emit_telemetry

        start_time = time.time()
        docs = state.get("retrieved_docs", [])
        filters: QueryFilters = state.get("filters")
        error = None

        if not docs:
            emit_telemetry(node_name="RerankerNode", start_time=start_time, state=state)
            return {"reranked_docs": []}

        # D-103: مستند محقون واحد لا يحتاج cross-encoder — passthrough مباشر.
        if str(state.get("exercise_content") or "").strip():
            emit_telemetry(node_name="RerankerNode", start_time=start_time, state=state)
            return {"reranked_docs": list(docs)}

        if self.reranker:
            try:
                from llama_index.core.schema import NodeWithScore, TextNode

                nodes = [
                    NodeWithScore(node=TextNode(text=d.text), score=d.metadata.get("score", 1.0))
                    for d in docs
                ]
                from llama_index.core.indices.query.schema import QueryBundle

                reranked_nodes = await anyio.to_thread.run_sync(
                    self.reranker.postprocess_nodes,
                    nodes,
                    QueryBundle(filters.question),
                )
                reranked = [
                    LlamaDocument(
                        text=n.node.text,
                        metadata={"source": "قاعدة البيانات الداخلية", "score": n.score},
                    )
                    for n in reranked_nodes
                ]
            except Exception as e:
                logger.error(f"Reranking failed: {e}")
                error = e
                reranked = docs[:5]
        else:
            reranked = sorted(
                docs,
                key=lambda doc: doc.metadata.get("score", 0),
                reverse=True,
            )[:5]

        emit_telemetry(node_name="RerankerNode", start_time=start_time, state=state, error=error)
        return {"reranked_docs": reranked}


# --- NODE 4: WebSearchFallbackNode ---
class WebSearchFallbackNode:
    async def __call__(self, state: dict) -> dict:
        from .telemetry import emit_telemetry

        start_time = time.time()
        reranked = state.get("reranked_docs", [])
        filters: QueryFilters = state.get("filters")
        error = None

        if len(reranked) == 0:
            query_str = f"بكالوريا {filters.subject} {filters.branch} {filters.year} تمرين {filters.exercise_num}"
            tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
            if not tavily_key:
                emit_telemetry(
                    node_name="WebSearchFallbackNode",
                    start_time=start_time,
                    state=state,
                    retrieval_source="web_skipped_missing_tavily",
                )
                return {"reranked_docs": [], "used_web": False}
            try:
                report = await asyncio.wait_for(
                    research_client.deep_research(query_str), timeout=10.0
                )
                docs = [LlamaDocument(text=report, metadata={"source": "الإنترنت", "score": 0.85})]
            except Exception as e:
                error = e
                docs = []

            emit_telemetry(
                node_name="WebSearchFallbackNode",
                start_time=start_time,
                state=state,
                error=error,
                retrieval_source="web",
            )
            return {"reranked_docs": docs, "used_web": True}

        emit_telemetry(node_name="WebSearchFallbackNode", start_time=start_time, state=state)
        return {"used_web": False}


# --- NODE 5: SynthesizerNode ---
class EducationalSynthesizer(dspy.Signature):
    """Synthesize an educational response from retrieved documents.
    You MUST obey any constraints specified in the conversation (e.g., 'question 1 only', 'no solution').
    Write your output clearly in Arabic."""

    context: str = dspy.InputField(desc="The raw retrieved exercise or document text.")
    conversation: str = dspy.InputField(
        desc="The recent conversation history including the user's active constraints."
    )
    query: str = dspy.InputField(desc="The user's original query.")
    response: str = dspy.OutputField(
        desc="The final synthesized response in Arabic obeying all constraints."
    )


# ─────────────────────────────────────────────────────────────────────────────
# D-103 (Change B): استشارة reasoning-agent (:8008 MCTS) للأسئلة الرياضية
# المعقدة قبل التوليف — تعميق الرسم بالوكلاء. fail-open مطلق: أي خطأ/مهلة/
# تعطيل ⇒ "" والتوليف يتابع بدون الاستشارة. لا تفشل دور الطالب أبداً.
# ─────────────────────────────────────────────────────────────────────────────
_REASONING_CONSULT_MARKERS: tuple[str, ...] = (
    "تكامل",
    "اشتقاق",
    "مشتق",
    "نهاية",
    "معادلة تفاضلية",
    "برهن",
    "أثبت",
    "اثبت",
    "استنتج",
    "ادرس الدالة",
    "ادرس تغيرات",
    "دالة أصلية",
    "دالة اصلية",
    "متتالية",
    "عدد مركب",
    "العدد المركب",
    "أعداد مركبة",
    "اعداد مركبة",
    "الأعداد المركبة",
    "الاعداد المركبة",
    "lim",
    "integral",
    "derivative",
    "prove",
)

_REASONING_HINT_MAX_CHARS = 4000


def _is_complex_math_query(query: str) -> bool:
    """كاشف حتمي محافظ — لا LLM: السؤال معقد رياضياً فقط عند وجود marker صريح."""
    text = str(query or "").strip()
    if len(text) < 15:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _REASONING_CONSULT_MARKERS)


async def _consult_reasoning_agent(query: str) -> str:
    """يستشير reasoning-agent ويُرجع hint نصياً — أو "" عند أي تعذّر (fail-open)."""
    from microservices.orchestrator_service.src.core.prom_metrics import (
        record_reasoning_consult,
    )

    enabled = os.environ.get("ORCHESTRATOR_REASONING_CONSULT_ENABLED", "1").strip().lower()
    if enabled in ("0", "false", "no"):
        record_reasoning_consult("disabled")
        return ""
    if not _is_complex_math_query(query):
        record_reasoning_consult("skipped")
        return ""

    try:
        timeout_raw = os.environ.get("ORCHESTRATOR_REASONING_CONSULT_TIMEOUT", "20")
        timeout_s = max(1.0, float(timeout_raw or "20"))
    except (TypeError, ValueError):
        timeout_s = 20.0

    try:
        # import كسول: يسهّل الاختبار (monkeypatch) ولا يكلّف وقت import الوحدة.
        from microservices.orchestrator_service.src.infrastructure.clients.reasoning_client import (
            reasoning_client,
        )

        data = await asyncio.wait_for(reasoning_client.reason_deeply(query), timeout=timeout_s)
        if isinstance(data, dict) and not data.get("error"):
            answer = str(data.get("answer") or "").strip()
            trace = str(data.get("logic_trace") or "").strip()
            hint = answer
            if trace and trace not in hint:
                hint = (hint + "\n" + trace).strip()
            if hint:
                record_reasoning_consult("success")
                logger.info("reasoning_consult success chars=%s", len(hint))
                return hint[:_REASONING_HINT_MAX_CHARS]
        record_reasoning_consult("error")
    except TimeoutError:
        record_reasoning_consult("timeout")
        logger.warning("reasoning_consult timeout after %.1fs", timeout_s)
    except Exception as exc:
        record_reasoning_consult("error")
        logger.warning("reasoning_consult failed: %s", exc)
    return ""


def _weave_reasoning_hint(base_text: str, reasoning_hint: str) -> str:
    """يُلحق hint الاستدلال بنص الـ prompt — صيغة موحَّدة للمواضع الثلاثة."""
    if not reasoning_hint:
        return base_text
    return f"{base_text}\n\nتحليل استدلالي مساعد (تحقق منه ولا تنسخه حرفياً):\n{reasoning_hint}"


class SynthesizerNode:
    def __init__(self):
        self.generator = dspy.Predict(EducationalSynthesizer)

    @staticmethod
    def _get_writer():
        """D-048: stream_writer إذا توفر."""
        try:
            from langgraph.config import get_stream_writer

            return get_stream_writer()
        except Exception:
            return None

    async def __call__(self, state: dict) -> dict:
        import json

        from .telemetry import emit_telemetry

        start_time = time.time()
        reranked = state.get("reranked_docs", [])
        filters: QueryFilters = state.get("filters")
        query = state.get("query", "")
        messages = state.get("messages", [])

        recent_messages: list[str] = []
        for msg in messages[-6:]:
            content = getattr(msg, "content", None)
            if not isinstance(content, str) or not content.strip():
                continue
            role = getattr(msg, "type", getattr(msg, "role", "user"))
            prefix = "User: " if role in ("human", "user") else "Assistant: "
            text = content.strip()
            if text.startswith("{") and role in ("ai", "assistant"):
                try:
                    data = json.loads(text)
                    if isinstance(data, dict):
                        extracted = data.get("الإجابة") or data.get("التمرين") or text
                        text = str(extracted)
                except Exception:
                    pass
            recent_messages.append(f"{prefix}{text}")

        conversation_text = "\n".join(recent_messages) if recent_messages else query

        # D-103 (Change B): استشارة reasoning-agent للأسئلة الرياضية المعقدة —
        # fail-open: "" عند أي تعذّر، والتوليف يتابع كالمعتاد.
        reasoning_hint = await _consult_reasoning_agent(query)

        if not reranked:
            # ISS-STREAM-002: عند عدم وجود نتائج بحث → استخدم LLM مباشرة مع streaming
            writer = self._get_writer()
            text_val = ""
            source = "معرفة عامة"
            confidence = "0.70"
            if writer is not None:
                try:
                    from microservices.orchestrator_service.src.services.llm.client import (
                        get_ai_client as get_llm_client,
                    )

                    llm_client = get_llm_client()
                    stream_messages = [
                        {
                            "role": "system",
                            "content": "أنت مدرس بكالوريا جزائري. أجب بدقة واختصار.",
                        },
                        # D-103: حقن hint الاستدلال عند توفره (فرع no-docs)
                        {"role": "user", "content": _weave_reasoning_hint(query, reasoning_hint)},
                    ]
                    # D-061 (ISS-074): تطبيع LaTeX على streaming chunks
                    from microservices.orchestrator_service.src.services.overmind.response_sanitizer import (
                        sanitize_chunk,
                    )

                    normalizer = LatexStreamNormalizer()
                    parts: list[str] = []
                    async for chunk in llm_client.stream_chat(stream_messages):
                        content = llm_client.extract_stream_content(chunk)
                        if not content:
                            continue
                        for safe_chunk in normalizer.feed(content):
                            # ISS-078 D-066: sanitize chunk قبل إرساله للعميل
                            sanitized = sanitize_chunk(safe_chunk)
                            if not sanitized:
                                continue
                            parts.append(sanitized)
                            writer(
                                {
                                    "chunk_type": "assistant_delta",
                                    "content": sanitized,
                                    "node": "synthesizer",
                                }
                            )
                    for tail_chunk in normalizer.flush():
                        sanitized_tail = sanitize_chunk(tail_chunk)
                        if not sanitized_tail:
                            continue
                        parts.append(sanitized_tail)
                        writer(
                            {
                                "chunk_type": "assistant_delta",
                                "content": sanitized_tail,
                                "node": "synthesizer",
                            }
                        )
                    text_val = "".join(parts).strip()
                except Exception as e:
                    logger.error(f"Synthesizer no-docs streaming failed: {e}")
            if not text_val:
                text_val = "لا توجد تفاصيل متاحة."
        else:
            raw_doc_text = reranked[0].text
            source = reranked[0].metadata.get("source", "الإنترنت")
            confidence = str(reranked[0].metadata.get("score", 0.85))

            writer = self._get_writer()
            text_val = ""
            if writer is not None:
                # D-048: STREAMING — استدعاء raw OpenAI مع stream=True + custom events
                # نُحاكي نفس قالب EducationalSynthesizer signature ولكن بـ streaming.
                try:
                    system_msg = (
                        "أنت مدرس بكالوريا جزائري. اعتمد على context الذي يحويه التمرين "
                        "أو الدرس من قاعدة المعرفة، وعلى محادثة الطالب. اكتب شرحاً متماسكاً "
                        "بالعربية الفصحى. لا تُكرر نص المصدر حرفياً."
                    )
                    user_msg = (
                        f"المصدر (context):\n{raw_doc_text}\n\n"
                        f"محادثة الطالب:\n{conversation_text}\n\n"
                        f"السؤال الحالي: {query}\n\n"
                        "اكتب الشرح أو الحل."
                    )
                    # D-103: حقن hint الاستدلال عند توفره (فرع with-docs)
                    user_msg = _weave_reasoning_hint(user_msg, reasoning_hint)
                    stream_messages = [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ]
                    from microservices.orchestrator_service.src.services.llm.client import (
                        get_ai_client as get_llm_client,
                    )

                    llm_client = get_llm_client()
                    # D-061 (ISS-074): تطبيع LaTeX على streaming chunks
                    normalizer = LatexStreamNormalizer()
                    parts: list[str] = []
                    async for chunk in llm_client.stream_chat(stream_messages):
                        try:
                            # ISS-STREAM-002: extract_stream_content يدعم ChatCompletionChunk و dict
                            content = llm_client.extract_stream_content(chunk)
                            if not content:
                                continue
                            for safe_chunk in normalizer.feed(content):
                                # ISS-078 D-066: sanitize chunk قبل إرساله للعميل
                                from microservices.orchestrator_service.src.services.overmind.response_sanitizer import (
                                    sanitize_chunk,
                                )

                                sanitized = sanitize_chunk(safe_chunk)
                                if not sanitized:
                                    continue
                                parts.append(sanitized)
                                writer(
                                    {
                                        "chunk_type": "assistant_delta",
                                        "content": sanitized,
                                        "node": "synthesizer",
                                    }
                                )
                        except Exception:
                            continue
                    for tail_chunk in normalizer.flush():
                        from microservices.orchestrator_service.src.services.overmind.response_sanitizer import (
                            sanitize_chunk,
                        )

                        sanitized_tail = sanitize_chunk(tail_chunk)
                        if not sanitized_tail:
                            continue
                        parts.append(sanitized_tail)
                        writer(
                            {
                                "chunk_type": "assistant_delta",
                                "content": sanitized_tail,
                                "node": "synthesizer",
                            }
                        )
                    text_val = "".join(parts).strip()
                except Exception as e:
                    logger.error(f"Synthesizer streaming failed: {e}")
                    text_val = ""

            if not text_val:
                # Fallback إلى DSPy (batch mode أو فشل streaming)
                try:
                    # D-103: حقن hint الاستدلال في مسار DSPy batch أيضاً
                    dspy_context = _weave_reasoning_hint(raw_doc_text, reasoning_hint)
                    prediction = await anyio.to_thread.run_sync(
                        lambda: self.generator(
                            context=dspy_context, conversation=conversation_text, query=query
                        )
                    )
                    raw_pred = getattr(prediction, "response", raw_doc_text).strip()
                    # D-061: تطبيع LaTeX حتى في batch mode
                    text_val = normalize_latex(raw_pred)
                except Exception as e:
                    logger.error(f"Synthesizer LLM generation failed: {e}")
                    text_val = (
                        "عذراً، تعذر صياغة الشرح المطلوب بسبب خطأ داخلي. يرجى إعادة صياغة السؤال."
                    )

        # D-064 (ISS-076): تنظيف foreign-script للمخرج التعليمي
        from microservices.orchestrator_service.src.services.overmind.response_sanitizer import (
            sanitize_response,
        )

        text_val = sanitize_response(text_val, intent="educational")

        response_json = {
            "المصدر": source,
            "مستوى_الثقة": confidence,
            "التمرين": text_val,
            "السنة": str(filters.year) if filters else "N/A",
            "الشعبة": filters.branch if filters else "غير محدد",
            "المادة": filters.subject if filters else "غير محدد",
            "رقم_التمرين": filters.exercise_num if filters else 1,
        }

        emit_telemetry(
            node_name="SynthesizerNode",
            start_time=start_time,
            state=state,
            confidence=float(confidence),
        )

        from langchain_core.messages import AIMessage

        # ISS-056: AIMessage carries the human-readable text ONLY.
        # The metadata envelope lives in final_response for internal use; if any
        # downstream code accidentally surfaces `messages[-1].content` to the user,
        # they get the answer, never a JSON dump.
        return {
            "final_response": response_json,
            "messages": [AIMessage(content=text_val or "لا توجد تفاصيل متاحة.")],
        }
