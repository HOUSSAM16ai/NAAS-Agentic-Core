from types import ModuleType

from microservices.research_agent.src.logging import get_logger

logger = get_logger(__name__)


def _load_dspy() -> ModuleType:
    """
    تحميل مكتبة DSPy عند الحاجة لتجنب كلفة الاستيراد المبكر.
    """
    import dspy

    return dspy


def _build_refiner(dspy: ModuleType) -> object:
    """
    إنشاء وحدة DSPy لإعادة صياغة الاستعلام بشكل منظم.
    """

    class StructuredQuerySignature(dspy.Signature):
        """
        تحليل الاستعلام التعليمي لاستخراج البيانات الوصفية وصياغة طلب بحث أدق.

        يركز هذا التوقيع على:
        - السنة: سنة الامتحان إن وُجدت.
        - المادة: اسم المادة الدراسية.
        - الشعبة: الفرع الدراسي.
        - الاستعلام المنقح: صياغة واضحة للموضوع الرئيس للبحث الدلالي.
        """

        user_query: str = dspy.InputField(desc="The raw query from the student.")
        refined_query: str = dspy.OutputField(desc="The optimized search term.")
        year: int | None = dspy.OutputField(desc="The exam year if mentioned, else None.")
        subject: str | None = dspy.OutputField(desc="The subject name if mentioned, else None.")
        branch: str | None = dspy.OutputField(desc="The branch name if mentioned, else None.")

    class StructuredQueryRefiner(dspy.Module):
        """
        وحدة DSPy لإعادة صياغة الاستعلام التعليمي بشكل منظم.
        """

        def __init__(self):
            super().__init__()
            self.prog = dspy.ChainOfThought(StructuredQuerySignature)

        def forward(self, user_query: str):
            return self.prog(user_query=user_query)

    return StructuredQueryRefiner()


def get_refined_query(
    user_query: str, api_key: str, model_name: str = "nvidia/nemotron-3-nano-30b-a3b:free"
) -> dict[str, object]:
    """
    إعادة صياغة الاستعلام عبر DSPy مع استخراج بيانات وصفية مساعدة.

    يعيد هذا التابع قاموساً يحتوي على:
    'refined_query', 'year', 'subject', 'branch'.
    """
    try:
        dspy = _load_dspy()
        lm = dspy.LM(
            model=f"openai/{model_name}",
            api_key=api_key,
            api_base="https://openrouter.ai/api/v1",
            max_tokens=300,
        )

        with dspy.context(lm=lm):
            refiner = _build_refiner(dspy)
            result = refiner(user_query=user_query)

            # Extract and clean
            return {
                "refined_query": result.refined_query,
                "year": _safe_int(result.year),
                "subject": result.subject
                if result.subject and result.subject.lower() != "none"
                else None,
                "branch": result.branch
                if result.branch and result.branch.lower() != "none"
                else None,
            }

    except Exception as e:
        logger.warning(f"DSPy refinement failed: {e}")
        return {"refined_query": user_query}


def _safe_int(val: object) -> int | None:
    try:
        if val and str(val).lower() != "none":
            return int(str(val))
    except (TypeError, ValueError):
        return None
    return None
