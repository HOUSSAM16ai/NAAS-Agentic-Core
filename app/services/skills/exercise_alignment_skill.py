"""
ExerciseAlignmentSkill — محاذاة إجابة النظام مع معطيات التمرين.

الهدف: منع الانجراف الدلالي في مسائل الاحتمالات عبر إزالة سطور الإجابة
التي تُدخل كيانات لونية غير موجودة في سؤال الطالب.
"""

from __future__ import annotations

import re
from typing import ClassVar, Literal

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill


class ExerciseAlignmentInput(RobustBaseModel):
    """مدخلات مهارة المحاذاة."""

    question: str = Field(..., min_length=1, max_length=6000)
    answer: str = Field(..., min_length=1)
    intent: Literal["educational", "general", "chat"] = "educational"


class ExerciseAlignmentOutput(RobustBaseModel):
    """مخرجات مهارة المحاذاة."""

    aligned_answer: str
    removed_lines: int = 0
    applied: bool = False


class ExerciseAlignmentSkill(BaseSkill[ExerciseAlignmentInput, ExerciseAlignmentOutput]):
    """مهارة حتمية لمحاذاة الإجابة مع معطيات السؤال."""

    name: ClassVar[str] = "exercise_alignment"

    _COLOR_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "white": ("بيضاء", "أبيض", "ابيض"),
        "red": ("حمراء", "أحمر", "احمر"),
        "green": ("خضراء", "أخضر", "اخضر"),
        "blue": ("زرقاء", "أزرق", "ازرق"),
        "black": ("سوداء", "أسود", "اسود"),
        "yellow": ("صفراء", "أصفر", "اصفر"),
    }
    _COLOR_TOKENS: ClassVar[tuple[str, ...]] = tuple(
        token for aliases in _COLOR_ALIASES.values() for token in aliases
    )

    def run(self, payload: ExerciseAlignmentInput) -> ExerciseAlignmentOutput:
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`align`."""
        return self.align(payload)

    def align(self, payload: ExerciseAlignmentInput) -> ExerciseAlignmentOutput:
        """ينفّذ محاذاة ألوان الاحتمالات ويُعيد نصاً منقحاً."""
        if payload.intent not in ("educational", "general"):
            return ExerciseAlignmentOutput(aligned_answer=payload.answer)
        if "احتمال" not in payload.question and "احتمالات" not in payload.question:
            return ExerciseAlignmentOutput(aligned_answer=payload.answer)

        allowed_colors = [token for token in self._COLOR_TOKENS if token in payload.question]
        if not allowed_colors:
            return ExerciseAlignmentOutput(aligned_answer=payload.answer)

        removed = 0
        forbidden_colors = [token for token in self._COLOR_TOKENS if token not in allowed_colors]
        filtered_lines: list[str] = []
        for line in payload.answer.splitlines():
            has_color = any(tok in line for tok in self._COLOR_TOKENS)
            if not has_color:
                filtered_lines.append(line)
                continue

            sanitized_line = line
            for token in forbidden_colors:
                sanitized_line = sanitized_line.replace(token, "")
            sanitized_line = re.sub(r"\s{2,}", " ", sanitized_line).strip(" ،,")

            if not sanitized_line:
                removed += 1
                continue
            if sanitized_line != line:
                removed += 1
            filtered_lines.append(sanitized_line)

        cleaned = "\n".join(filtered_lines).strip()
        final_answer = cleaned if cleaned else payload.answer
        return ExerciseAlignmentOutput(
            aligned_answer=final_answer,
            removed_lines=removed,
            applied=removed > 0,
        )


def get_exercise_alignment_skill() -> ExerciseAlignmentSkill:
    """يُعيد Singleton لمهارة المحاذاة (BaseSkill.instance)."""
    return ExerciseAlignmentSkill.instance()
