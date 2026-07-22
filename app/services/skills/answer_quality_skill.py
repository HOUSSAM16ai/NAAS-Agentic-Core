"""
AnswerQualitySkill — Skill تقييم جودة الإجابة وتحسين الشرح.

المسؤولية الواحدة: تقييم إجابة LLM وفق الـ doctrines الرسمية وإعادة
بناء الشرح إذا لم يستوفِ المعايير.

**العقد** (Pydantic):
  - Input:  `AnswerQualityInput(question, answer, intent, subject)`
  - Output: `AnswerQualityOutput(score, issues, improved_answer, passed)`

**الـ Doctrines المُطبَّقة**:
  - EXPLANATION_DOCTRINE: قواعد الشرح الإلزامية
  - STEP_BY_STEP_EXPLANATION_RULES: قواعد الشرح خطوة بخطوة
  - MODEL_ANSWER_RELIANCE_RULES: قواعد الاحتجاج بالإجابة النموذجية

**القياس**:
  - `cogniforge_answer_quality_invocations_total{intent,status}` (counter)
  - `cogniforge_answer_quality_score_histogram` (histogram)
  - `cogniforge_answer_quality_improvements_total` (counter)

**الاستقلالية**:
  - لا يستورد من Skill آخر
  - يعمل بدون LLM (deterministic scoring)
  - fallback: يُعيد الإجابة الأصلية إذا فشل التحسين

D-072 (2026-05-19): إنشاء AnswerQualitySkill كـ Skill رسمي مستقل.
"""

from __future__ import annotations

import logging
import re
import time
from typing import ClassVar, Literal

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill
from app.services.skills.doctrine import (
    EXPLANATION_DOCTRINE,
    MODEL_ANSWER_RELIANCE_RULES,
    STEP_BY_STEP_EXPLANATION_RULES,
)

logger = logging.getLogger(__name__)

# ── Prometheus metrics — استيراد دفاعي ────────────────────────────────────────
try:
    from prometheus_client import Counter, Histogram

    _INVOCATIONS = Counter(
        "cogniforge_answer_quality_invocations_total",
        "عدد استدعاءات AnswerQualitySkill",
        ["intent", "status"],
    )
    _SCORE_HIST = Histogram(
        "cogniforge_answer_quality_score",
        "توزيع نقاط جودة الإجابة",
        buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    )
    _IMPROVEMENTS = Counter(
        "cogniforge_answer_quality_improvements_total",
        "عدد الإجابات التي تم تحسينها",
    )
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False


def _record_invocation(intent: str, status: str) -> None:
    """يُسجِّل استدعاء Skill في Prometheus."""
    if _METRICS_AVAILABLE:
        _INVOCATIONS.labels(intent=intent, status=status).inc()


def _record_score(score: float) -> None:
    """يُسجِّل نقطة جودة في Prometheus."""
    if _METRICS_AVAILABLE:
        _SCORE_HIST.observe(score)


def _record_improvement() -> None:
    """يُسجِّل تحسين إجابة في Prometheus."""
    if _METRICS_AVAILABLE:
        _IMPROVEMENTS.inc()


# ── Pydantic Contracts ────────────────────────────────────────────────────────


class AnswerQualityInput(RobustBaseModel):
    """مدخلات تقييم جودة الإجابة."""

    question: str = Field(..., min_length=1, max_length=2000, description="سؤال الطالب")
    answer: str = Field(..., min_length=1, description="إجابة النظام")
    intent: Literal["educational", "math", "chat", "retrieval"] = Field(
        "educational", description="نوع السؤال"
    )
    subject: str = Field("general", description="المادة الدراسية")
    require_latex: bool = Field(True, description="هل يُشترط وجود LaTeX في الإجابات الرياضية")
    require_steps: bool = Field(True, description="هل يُشترط الشرح خطوة بخطوة")


class QualityIssue(RobustBaseModel):
    """مشكلة جودة مُكتشَفة في الإجابة."""

    code: str = Field(..., description="رمز المشكلة")
    severity: Literal["critical", "warning", "info"] = Field(..., description="خطورة المشكلة")
    description: str = Field(..., description="وصف المشكلة")
    doctrine_rule: str = Field("", description="القاعدة المنتهَكة من الـ doctrine")


class AnswerQualityOutput(RobustBaseModel):
    """نتيجة تقييم جودة الإجابة."""

    score: float = Field(..., ge=0.0, le=1.0, description="نقطة الجودة (0-1)")
    passed: bool = Field(..., description="هل اجتازت الإجابة معايير الجودة")
    issues: list[QualityIssue] = Field(default_factory=list, description="المشاكل المُكتشَفة")
    improved_answer: str = Field("", description="الإجابة المُحسَّنة (إذا وُجدت مشاكل)")
    original_answer: str = Field("", description="الإجابة الأصلية")
    duration_ms: float = Field(0.0, description="وقت التقييم بالميلي ثانية")
    doctrine_version: str = Field("2.0.0", description="نسخة الـ doctrine المُطبَّقة")


class AnswerQualityFailure(RobustBaseModel):
    """فشل تقييم الجودة."""

    error: str
    fallback_answer: str = Field("", description="الإجابة الأصلية كـ fallback")


# ── Quality Checks ────────────────────────────────────────────────────────────

# الحد الأدنى لطول الإجابة التعليمية (حرف)
_MIN_EDUCATIONAL_LENGTH = 100
# الحد الأدنى لطول الإجابة الرياضية (حرف)
_MIN_MATH_LENGTH = 150
# نقطة النجاح
_PASS_THRESHOLD = 0.6

# أنماط LaTeX الصحيحة
_LATEX_PATTERN = re.compile(r"\$\$.*?\$\$|\$[^$]+\$", re.DOTALL)
# أنماط LaTeX الخاطئة (ISS-071)
_BAD_LATEX_PATTERN = re.compile(r"\\\[|\\\]|\\begin\{equation\}|\\begin\{align\}")
# أنماط box-drawing chars المحظورة (D-067)
_BOX_DRAWING_PATTERN = re.compile(r"[\u2500-\u257f]")
# أنماط الخطوات المرقمة
_NUMBERED_STEPS_PATTERN = re.compile(r"^\s*\d+[\.\)]\s+", re.MULTILINE)
# أنماط اللغة الأجنبية في الإجابة العربية
_FOREIGN_LANG_PATTERN = re.compile(
    r"\b(we need|let us|therefore|hence|thus|so we)\b", re.IGNORECASE
)


def _check_length(answer: str, intent: str) -> QualityIssue | None:
    """يتحقق من طول الإجابة."""
    min_len = _MIN_MATH_LENGTH if intent == "math" else _MIN_EDUCATIONAL_LENGTH
    if len(answer) < min_len:
        return QualityIssue(
            code="TOO_SHORT",
            severity="critical",
            description=f"الإجابة قصيرة جداً ({len(answer)} حرف، الحد الأدنى {min_len})",
            doctrine_rule=EXPLANATION_DOCTRINE[0] if EXPLANATION_DOCTRINE else "",
        )
    return None


def _check_latex(answer: str, intent: str, require_latex: bool) -> QualityIssue | None:
    """يتحقق من صحة LaTeX في الإجابات الرياضية."""
    if not require_latex or intent not in ("math", "educational"):
        return None

    # تحقق من LaTeX خاطئ (ISS-071)
    if _BAD_LATEX_PATTERN.search(answer):
        return QualityIssue(
            code="BAD_LATEX_FORMAT",
            severity="critical",
            description="الإجابة تستخدم \\[...\\] بدلاً من $$...$$",
            doctrine_rule="استخدم $$...$$ دائماً — لا \\[...\\]",
        )
    return None


def _check_box_drawing(answer: str) -> QualityIssue | None:
    """يتحقق من غياب box-drawing chars المحظورة (D-067)."""
    if _BOX_DRAWING_PATTERN.search(answer):
        return QualityIssue(
            code="BOX_DRAWING_CHARS",
            severity="warning",
            description="الإجابة تحتوي على box-drawing chars تُربك tokenizers النماذج المجانية",
            doctrine_rule="D-067: box-drawing chars محظورة في prompts والإجابات",
        )
    return None


def _check_numbered_steps(answer: str, require_steps: bool, intent: str) -> QualityIssue | None:
    """يتحقق من وجود خطوات مرقمة في الإجابات التعليمية."""
    if not require_steps or intent == "chat":
        return None
    if not _NUMBERED_STEPS_PATTERN.search(answer):
        return QualityIssue(
            code="NO_NUMBERED_STEPS",
            severity="warning",
            description="الإجابة لا تحتوي على خطوات مرقمة",
            doctrine_rule=STEP_BY_STEP_EXPLANATION_RULES[0]
            if STEP_BY_STEP_EXPLANATION_RULES
            else "",
        )
    return None


def _check_foreign_language(answer: str) -> QualityIssue | None:
    """يتحقق من غياب اللغة الأجنبية في الإجابة العربية (D-067 reasoning leak)."""
    if _FOREIGN_LANG_PATTERN.search(answer):
        return QualityIssue(
            code="FOREIGN_LANGUAGE_LEAK",
            severity="critical",
            description="الإجابة تحتوي على نص إنجليزي — reasoning leak محتمل (D-067)",
            doctrine_rule="D-067: لا تُمرِّر reasoning كـ content",
        )
    return None


def _check_model_answer_reference(answer: str, intent: str) -> QualityIssue | None:
    """يتحقق من الاحتجاج بالإجابة النموذجية في الشرح التعليمي."""
    if intent not in ("educational", "math"):
        return None
    # الإجابة الجيدة تحتوي على مصطلحات تدل على الشرح المنهجي
    methodology_markers = ["إذن", "نستنتج", "بالتعويض", "نحسب", "نجد", "الخطوة", "أولاً", "ثانياً"]
    has_methodology = any(marker in answer for marker in methodology_markers)
    if not has_methodology and len(answer) > 200:
        return QualityIssue(
            code="NO_METHODOLOGY_MARKERS",
            severity="info",
            description="الإجابة لا تحتوي على مؤشرات منهجية واضحة",
            doctrine_rule=MODEL_ANSWER_RELIANCE_RULES[0] if MODEL_ANSWER_RELIANCE_RULES else "",
        )
    return None


def _compute_score(issues: list[QualityIssue]) -> float:
    """يحسب نقطة الجودة بناءً على المشاكل المُكتشَفة."""
    if not issues:
        return 1.0

    deductions = {
        "critical": 0.3,
        "warning": 0.1,
        "info": 0.02,
    }
    total_deduction = sum(deductions.get(issue.severity, 0.0) for issue in issues)
    return max(0.0, 1.0 - total_deduction)


def _build_improvement_header(issues: list[QualityIssue], answer: str) -> str:
    """يبني إجابة مُحسَّنة بإضافة تحذيرات للمشاكل الحرجة."""
    critical_issues = [i for i in issues if i.severity == "critical"]
    if not critical_issues:
        return answer

    # إضافة تنبيه للمشاكل الحرجة فقط (لا نُعيد كتابة الإجابة — deterministic)
    warning_note = ""
    for issue in critical_issues:
        if issue.code == "FOREIGN_LANGUAGE_LEAK":
            # إزالة النص الأجنبي
            return _FOREIGN_LANG_PATTERN.sub("", answer).strip()
        if issue.code == "BAD_LATEX_FORMAT":
            # تصحيح LaTeX — سلسلة تحويلات متتالية
            result = re.sub(r"\\\[", "$$", answer)
            result = re.sub(r"\\\]", "$$", result)
            result = re.sub(r"\\begin\{equation\}", "$$", result)
            result = re.sub(r"\\end\{equation\}", "$$", result)
            result = re.sub(r"\\begin\{align\*?\}", "$$", result)
            return re.sub(r"\\end\{align\*?\}", "$$", result)

    return warning_note + answer if warning_note else answer


# ── AnswerQualitySkill ────────────────────────────────────────────────────────


class AnswerQualitySkill(BaseSkill):
    """
    Skill تقييم جودة الإجابة وتحسينها وفق الـ doctrines الرسمية.

    يُطبِّق هذا الـ Skill مجموعة من الفحوصات الحتمية (deterministic) على
    إجابة LLM قبل إرسالها للطالب، ويُصحِّح المشاكل القابلة للتصحيح تلقائياً.

    الاستخدام:
        skill = AnswerQualitySkill()
        result = skill.evaluate(AnswerQualityInput(
            question="اشرح قانون نيوتن",
            answer="...",
            intent="educational",
        ))
        if not result.passed:
            final_answer = result.improved_answer or result.original_answer
    """

    # نسخة الـ Skill — تُستخدم في Prometheus و CI gate
    VERSION: ClassVar[str] = "1.0.0"
    SKILL_NAME: ClassVar[str] = "answer_quality"
    name: ClassVar[str] = "answer_quality"

    def run(self, inp: AnswerQualityInput):
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`evaluate`."""
        return self.evaluate(inp)

    def evaluate(self, inp: AnswerQualityInput) -> AnswerQualityOutput | AnswerQualityFailure:
        """
        يُقيِّم جودة الإجابة ويُعيد نتيجة مُفصَّلة.

        الفحوصات المُطبَّقة (بالترتيب):
        1. طول الإجابة (EXPLANATION_DOCTRINE)
        2. صحة LaTeX (ISS-071)
        3. غياب box-drawing chars (D-067)
        4. وجود خطوات مرقمة (STEP_BY_STEP_EXPLANATION_RULES)
        5. غياب اللغة الأجنبية (D-067 reasoning leak)
        6. مؤشرات المنهجية (MODEL_ANSWER_RELIANCE_RULES)
        """
        t0 = time.monotonic()
        try:
            issues: list[QualityIssue] = []

            # تطبيق الفحوصات
            checks = [
                _check_length(inp.answer, inp.intent),
                _check_latex(inp.answer, inp.intent, inp.require_latex),
                _check_box_drawing(inp.answer),
                _check_numbered_steps(inp.answer, inp.require_steps, inp.intent),
                _check_foreign_language(inp.answer),
                _check_model_answer_reference(inp.answer, inp.intent),
            ]
            issues = [c for c in checks if c is not None]

            score = _compute_score(issues)
            passed = score >= _PASS_THRESHOLD

            # بناء الإجابة المُحسَّنة إذا وُجدت مشاكل قابلة للتصحيح
            improved = ""
            if issues:
                improved = _build_improvement_header(issues, inp.answer)
                if improved != inp.answer:
                    _record_improvement()

            duration_ms = (time.monotonic() - t0) * 1000
            _record_invocation(inp.intent, "success" if passed else "issues_found")
            _record_score(score)

            return AnswerQualityOutput(
                score=score,
                passed=passed,
                issues=issues,
                improved_answer=improved,
                original_answer=inp.answer,
                duration_ms=round(duration_ms, 2),
                doctrine_version="2.0.0",
            )

        except Exception as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            logger.error("AnswerQualitySkill.evaluate failed: %s (%.1fms)", exc, duration_ms)
            _record_invocation(inp.intent, "error")
            return AnswerQualityFailure(
                error=str(exc),
                fallback_answer=inp.answer,
            )


# ── Singleton ─────────────────────────────────────────────────────────────────
# Singleton: مُهيَّأ مرة واحدة — لا state داخلي، آمن للاستخدام المتزامن.
_answer_quality_skill: AnswerQualitySkill | None = None


def get_answer_quality_skill() -> AnswerQualitySkill:
    """يُعيد singleton من AnswerQualitySkill."""
    global _answer_quality_skill
    if _answer_quality_skill is None:
        _answer_quality_skill = AnswerQualitySkill()
    return _answer_quality_skill


__all__ = [
    "AnswerQualityFailure",
    "AnswerQualityInput",
    "AnswerQualityOutput",
    "AnswerQualitySkill",
    "QualityIssue",
    "get_answer_quality_skill",
]
