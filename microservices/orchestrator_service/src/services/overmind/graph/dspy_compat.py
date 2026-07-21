"""DSPy compat shim — sliced verbatim from graph/main.py (D-173 Stage 2c).

نمط D-164/D-168: كل شريحة تُضاف لـ GRAPH_SOURCE_FILES؛ main.py يعيد التصدير
(noqa F401) فيبقى monkeypatch على `graph.main.<name>` والاستيراد الخارجي فعّالاً.
"""

from types import SimpleNamespace

try:
    import dspy
except ModuleNotFoundError:

    def _dspy_input_field(*_: object, **__: object) -> str:
        return ""

    def _dspy_output_field(*_: object, **__: object) -> str:
        return ""

    def _dspy_chain_of_thought(*_: object, **__: object):
        def _runner(**_: object) -> SimpleNamespace:
            return SimpleNamespace(
                is_admin=False,
                is_chat=False,
                confidence=0.0,
                tool_needed="",
                rewritten_query="",
            )

        return _runner

    def _dspy_predict(*_: object, **__: object):
        def _runner(**_: object) -> SimpleNamespace:
            return SimpleNamespace(response="")

        return _runner

    class _DSPySettings:
        def __init__(self) -> None:
            self.lm: object | None = None

        def configure(self, *, lm: object | None = None) -> None:
            self.lm = lm

    class _DSPySignature:
        pass

    class _DSPyModule:
        class LM:
            def __init__(self, **_: object) -> None:
                pass

        Signature = _DSPySignature
        settings = _DSPySettings()
        InputField = staticmethod(_dspy_input_field)
        OutputField = staticmethod(_dspy_output_field)
        ChainOfThought = staticmethod(_dspy_chain_of_thought)
        Predict = staticmethod(_dspy_predict)

    dspy = _DSPyModule()  # type: ignore[assignment]
