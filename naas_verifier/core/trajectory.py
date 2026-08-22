"""المسار — الخطوات والأدوات والحالات الوسيطة (D-267 §3).

المُتحقِّق يقرأ **مساراً**، لا نصّاً نهائياً. ولذلك المسار نوعٌ صريح: كل خطوةٍ تحمل
أداتها ووسائطها وحالتها قبل/بعد ومخرَجها المرصود — وبدون ذلك تصير الأبعاد الخمسة
(L3) غير قابلة للفحص أصلاً.

⛔ مكتبة قياسية فقط. لا استيراد من `app/**` ولا `microservices/**`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

__all__ = ["Step", "Trajectory", "TrajectoryError"]


class TrajectoryError(ValueError):
    """خرقُ مجالٍ في بناء المسار — يُرفَع ولا يُعاد صفرٌ مضلِّل (نمط `FoundationsError`)."""


@dataclass(frozen=True)
class Step:
    """خطوةٌ واحدة في مسار الوكيل تحت الاختبار.

    `state_before`/`state_after` تُقرآن كمُعرِّفات حالةٍ مُسمّاة — انتقالٌ غير مشروع
    بينهما هو بالضبط ما يكشفه بُعد `state_transitions`.
    """

    index: int
    action: str
    state_before: str
    state_after: str
    tool: str | None = None
    tool_args: Mapping[str, object] = field(default_factory=dict)
    output: str = ""

    def __post_init__(self) -> None:
        if self.index < 0:
            raise TrajectoryError(f"index must be >= 0, got {self.index}")
        if not self.action.strip():
            raise TrajectoryError(f"step {self.index}: action must not be empty")
        for name in ("state_before", "state_after"):
            if not str(getattr(self, name)).strip():
                raise TrajectoryError(f"step {self.index}: `{name}` must not be empty")
        if self.tool is not None and not self.tool.strip():
            raise TrajectoryError(
                f"step {self.index}: tool is present but empty — "
                "declare `None` for a step that uses no tool"
            )


@dataclass(frozen=True)
class Trajectory:
    """مسارٌ كامل: خطواتٌ مرتّبة + مخرَجٌ نهائي + وسمٌ للغة الهدف.

    `language` ليست زينة: أربعةٌ من أصناف الذخيرة **مشروطة باللغة**، ومسارٌ بلا لغةٍ
    مُعلَنة لا يمكن أن يُنسَب إلى صنفٍ لغويّ ولا أن يُقارَن بأساسٍ إنجليزي.
    """

    trajectory_id: str
    steps: Sequence[Step]
    final_output: str
    language: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.trajectory_id.strip():
            raise TrajectoryError("trajectory_id must not be empty")
        if not self.language.strip():
            raise TrajectoryError(
                f"{self.trajectory_id}: `language` must be declared — a trajectory "
                "without a language cannot be compared against a language baseline"
            )
        indices = [step.index for step in self.steps]
        if indices != sorted(indices):
            raise TrajectoryError(f"{self.trajectory_id}: steps must be ordered by index")

    @property
    def tools_used(self) -> tuple[str, ...]:
        return tuple(step.tool for step in self.steps if step.tool is not None)

    @property
    def transitions(self) -> tuple[tuple[str, str], ...]:
        return tuple((step.state_before, step.state_after) for step in self.steps)

    def outputs(self) -> tuple[str, ...]:
        """كلّ المخرَجات المرصودة — الوسطى **والنهائي**.

        الوسطى وحدها لا تكفي، والنهائي وحده هو ما يجعل النظام مُصحِّحاً لا مُتحقِّقاً.
        """
        return (*(step.output for step in self.steps), self.final_output)
