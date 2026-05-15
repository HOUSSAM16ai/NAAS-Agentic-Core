from microservices.reasoning_agent.src.compat import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from microservices.reasoning_agent.src.core.logging import get_logger
from microservices.reasoning_agent.src.services.ai_service import ai_service
from microservices.reasoning_agent.src.services.strategies.mcts import mcts_strategy

logger = get_logger("reasoning-workflow")


class RetrievalEvent(Event):
    query: str
    context: str


class ReasoningWorkflow(Workflow):
    # ISS-068: timeout مُخفَّض من 300s إلى 45s — MCTS مع نماذج مجانية يتجاوز rate limits عند depth>1
    def __init__(self, timeout: int = 45, verbose: bool = True):
        super().__init__(timeout=timeout, verbose=verbose)
        self.strategy = mcts_strategy

    @step
    async def retrieve(self, ctx: Context, ev: StartEvent) -> RetrievalEvent:
        query = ev.get("query")
        context_str = ev.get("context", "")

        logger.info(f"Workflow started for query: {query}")

        # In a real scenario, this would call Research Agent.
        # For now, we accept context passed in or use a placeholder if empty.
        if not context_str:
            context_str = "No external context provided. Relying on internal knowledge."

        return RetrievalEvent(query=query, context=context_str)

    @step
    async def reason(self, ctx: Context, ev: RetrievalEvent) -> StopEvent:
        query = ev.query
        context = ev.context

        logger.info("Executing MCTS Strategy...")
        # ISS-068: depth=1 لتجنب rate limiting مع النماذج المجانية (depth=2 يستدعي LLM 6+ مرات)
        best_node = await self.strategy.execute(root_content=f"Analyze: {query}", context=context, depth=1)

        logger.info(f"Selected best path: {best_node.content}")

        # Final Synthesis — ISS-068 + ISS-070: system prompt عبقري للرياضيات والعلوم
        system_prompt = (
            "أنت أستاذ رياضيات وعلوم عبقري للبكالوريا الجزائرية.\n"
            "مهمتك: تقديم إجابة شاملة ومفصلة بناءً على مسار التفكير المُقدَّم.\n\n"
            "## قواعد اللغة — صارمة لا تُخرق\n"
            "- اكتب بالعربية الفصحى الواضحة فقط\n"
            "- لا تخلط مع الروسية أو الإنجليزية أو الفرنسية إلا للمصطلحات التقنية\n\n"
            "## قواعد LaTeX — إلزامية\n"
            "1. $$...$$ للمعادلات المستقلة\n"
            "2. \\(...\\) للرموز المضمّنة في النص\n"
            "3. $$\\boxed{...}$$ للنتيجة النهائية\n\n"
            "## منهجية الإجابة\n"
            "1. **لماذا؟** — ابدأ بشرح سبب اختيار الطريقة\n"
            "2. **الخطوات المرقمة** — كل خطوة مع تبرير رياضي\n"
            "3. **الحسابات التفصيلية** — لا تتخطى خطوة\n"
            "4. **النتيجة في صندوق** — $$\\boxed{...}$$\n"
            "5. **التفسير الواقعي** — ماذا تعني النتيجة؟"
        )

        final_prompt = (
            f"السؤال: {query}\n"
            f"السياق: {context}\n"
            f"مسار التفكير المُختار: {best_node.content}\n\n"
            "قدّم الإجابة الكاملة المفصلة بالعربية مع LaTeX:"
        )

        result = await ai_service.generate_text(prompt=final_prompt, system_prompt=system_prompt)

        return StopEvent(result=result)


reasoning_workflow = ReasoningWorkflow()
