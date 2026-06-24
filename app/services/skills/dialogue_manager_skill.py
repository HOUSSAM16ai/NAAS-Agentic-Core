"""
DialogueManagerSkill (D-142 Phase 2) — مدير الحوار الموحَّد: سلطة قرار الدور التعليمي.

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill».

## المسؤولية الواحدة
يقرّر **أقل تدخّل مفيد الآن** في حوار التدريس من ثلاث إشارات حيّة تُحسَب كل دور — لا «مصفوفة
levels» جامدة (نقد المالك): `f(دليل الفهم، قدرة الطالب، صعوبة الخطوة التالية)`. حتمي 100%
(صفر LLM — قابل للاختبار بـ pytest). يستهلك إشارات مُحسوبة مسبقاً (verified_correct من المحرك
الرمزي، understood من المُقيّم، ability من BKT، last_step من الحالة الدائمة) — لا يستورد Skill
آخر داخل `decide` (§0.5 استقلالية).

## الكارثة التي يحلّها (ISS-117)
كان قرار الدور مُبعثراً في سلسلة preempt تُعيد بناء الحالة من نصّ السجل كل دور ⇒ تكرار حرفي،
تجاهل الإجابة الصحيحة، وانحراف. هذا الـ Skill يوحّد القرار خلف عقد واحد، مدفوعاً بحالة دائمة.

## القرار (التقدّم الحتمي + حارس عدم القفز)
- دليل فهم موثوق (verified/understood) ⇒ **تقدّم حتمي** للخطوة التالية — لا إعادة سؤال.
- الميزانية السقراطية للمفهوم مُستنفَدة ⇒ **حلّ رمزي** (لا سؤال إضافي).
- النصّ المُرشَّح مُكرّر لآخر خطوة عُرضت ⇒ **تصعيد** (لا إعادة حرفية).
- قدرة الطالب < صعوبة الخطوة التالية ⇒ **خطوة وسطى أصغر** (لا قفز فوق المستوى).
- خلاف ذلك ⇒ مواصلة سقراطية.

## القياس (Prometheus)
- `cogniforge_skill_dialogue_manager_total{action,reason}` (counter)
"""

from __future__ import annotations

import contextlib

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.doctrine import DIALOGUE_MANAGER_DOCTRINE_VERSION

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _norm(text: str) -> str:
    return (text or "").translate(_AR_DIGITS).strip().lower()


#: صعوبة كل مفهوم/مكوّن معرفي [0,1] — لمعايرة الخطوة التالية مقابل قدرة الطالب.
_CONCEPT_DIFFICULTY: dict[str, float] = {
    "event_meaning": 0.20,
    "color_white": 0.20,
    "color_red": 0.30,
    "color_green": 0.30,
    "numerator": 0.40,
    "combinations": 0.50,
    "denominator": 0.50,
    "ratio": 0.70,
    "full_solution": 0.80,
}
#: المفهوم التالي في السُّلّم (مرآة NEXT_FOCUS في socratic_evaluator، مستقلّ بلا استيراد).
_NEXT_FOCUS: dict[str, str | None] = {
    "event_meaning": "denominator",
    "numerator": "denominator",
    "color_white": "numerator",
    "color_red": "color_green",
    "color_green": "denominator",
    "combinations": "numerator",
    "denominator": "ratio",
    "ratio": None,
    "full_solution": None,
}

#: حد القفز: لا نقدّم خطوة تتجاوز قدرة الطالب بأكثر من هذا الهامش.
_OVERJUMP_MARGIN: float = 0.15


def _budget(ability: float) -> int:
    """ميزانية سقراطية متكيّفة مع القدرة (لا ثابتة): قدرة منخفضة ⇒ تصعيد أسرع؛ عالية ⇒ وكالة أكبر."""
    base = 2
    if ability < 0.35:
        base = 1
    elif ability >= 0.70:
        base = 3
    return max(1, min(3, base))


def _difficulty(concept: str | None) -> float:
    return _CONCEPT_DIFFICULTY.get(concept or "", 0.5)


def _next_focus(concept: str) -> str | None:
    return _NEXT_FOCUS.get(concept, "denominator")


def near_duplicate(candidate: str, prior: str, *, threshold: float = 0.8) -> bool:
    """تداخل رموز/احتواء ≥ threshold بين مرشَّح وآخر خطوة عُرضت (حارس التكرار الدائم)."""
    a, b = _norm(candidate), _norm(prior)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    at, bt = set(a.split()), set(b.split())
    if not at:
        return False
    return len(at & bt) / len(at) >= threshold


# ── العقود (Pydantic) ────────────────────────────────────────────────────────
class DialogueInput(RobustBaseModel):
    """إشارات الدور (مُحسوبة مسبقاً — المدير لا يحسبها، يقرّر بها)."""

    question: str = Field(default="", max_length=8000)
    concept: str = Field(default="event_meaning", max_length=64)
    verified_correct: bool = False  # 1A — السلطة الرمزية
    understood: bool = False  # من المُقيّم السقراطي
    ability: float = Field(default=0.0, ge=0.0, le=1.0)  # BKT mastery / ability_snapshot
    socratic_count: int = Field(default=0, ge=0)  # ميزانية المفهوم النشط من الحالة الدائمة
    last_step_emitted: str = Field(default="", max_length=8000)  # مرساة منع التكرار
    candidate_text: str = Field(default="", max_length=8000)  # ما يريد المسار بثّه


class DialogueDecision(RobustBaseModel):
    """قرار الدور: نوع التدخّل + بؤرة الخطوة + إشارة منع التكرار + السبب."""

    action: str  # acknowledge_advance|symbolic_reveal|intermediate_scaffold|continue_socratic
    focus: str | None = None
    avoid_repeat: bool = False
    reason: str = ""
    budget: int = 2


# ── Prometheus ────────────────────────────────────────────────────────────────
try:
    from prometheus_client import REGISTRY, Counter

    if "cogniforge_skill_dialogue_manager_total" in {m.name for m in REGISTRY.collect()}:
        _dm_total = None
    else:
        _dm_total = Counter(
            "cogniforge_skill_dialogue_manager_total",
            "DialogueManager decisions, labelled by action/reason.",
            ["action", "reason"],
        )

    def _record(action: str, reason: str) -> None:
        with contextlib.suppress(Exception):
            if _dm_total is not None:
                _dm_total.labels(action=action, reason=reason).inc()

except Exception:  # pragma: no cover

    def _record(action: str, reason: str) -> None:
        pass


class DialogueManagerSkill:
    """مدير الحوار — سلطة قرار الدور التعليمي (D-142 Phase 2).

    عقد دائم (لا يُكسر بدون ADR):
    1. القرار حتمي 100% (صفر LLM) — قابل للاختبار بـ pytest.
    2. دليل فهم موثوق ⇒ تقدّم حتمي، لا إعادة سؤال أبداً.
    3. لا تكرار حرفي (مرساة `last_step_emitted` الدائمة) ⇒ تصعيد.
    4. لا قفز فوق قدرة الطالب ⇒ خطوة وسطى أصغر.
    5. fail-open: المُنادي يلتقط أي خطأ ويعود للسلوك القائم.
    """

    _skill_name: str = "dialogue_manager"
    doctrine_version: str = DIALOGUE_MANAGER_DOCTRINE_VERSION

    def decide(self, payload: DialogueInput) -> DialogueDecision:
        """يقرّر أقل تدخّل مفيد — حتمي تماماً. لا يرفع استثناءات."""
        budget = _budget(payload.ability)
        avoid = bool(payload.candidate_text) and near_duplicate(
            payload.candidate_text, payload.last_step_emitted
        )
        nxt = _next_focus(payload.concept)

        # (1) دليل فهم موثوق ⇒ تقدّم حتمي (لا إعادة سؤال).
        if payload.verified_correct or payload.understood:
            return self._out("acknowledge_advance", focus=nxt, reason="evidence", budget=budget)

        # (2) ميزانية المفهوم مُستنفَدة ⇒ حلّ رمزي (لا سؤال إضافي).
        if payload.socratic_count >= budget:
            return self._out(
                "symbolic_reveal", focus=None, reason="budget", budget=budget, avoid=avoid
            )

        # (3) النصّ المُرشَّح مُكرّر ⇒ تصعيد بدل الإعادة الحرفية.
        if avoid:
            return self._out(
                "symbolic_reveal", focus=None, reason="dedup", budget=budget, avoid=True
            )

        # (4) قدرة الطالب < صعوبة الخطوة التالية ⇒ خطوة وسطى أصغر (لا قفز).
        if payload.ability + _OVERJUMP_MARGIN < _difficulty(nxt):
            return self._out(
                "intermediate_scaffold",
                focus="numerator",
                reason="ability_below_difficulty",
                budget=budget,
            )

        # (5) خلاف ذلك ⇒ مواصلة سقراطية.
        return self._out("continue_socratic", focus=nxt, reason="continue", budget=budget)

    @staticmethod
    def _out(
        action: str,
        *,
        focus: str | None,
        reason: str,
        budget: int,
        avoid: bool = False,
    ) -> DialogueDecision:
        _record(action, reason)
        return DialogueDecision(
            action=action, focus=focus, avoid_repeat=avoid, reason=reason, budget=budget
        )


_dialogue_manager_singleton: DialogueManagerSkill | None = None


def get_dialogue_manager_skill() -> DialogueManagerSkill:
    """يُرجِع نسخة مفردة (lazy singleton)."""
    global _dialogue_manager_singleton
    if _dialogue_manager_singleton is None:
        _dialogue_manager_singleton = DialogueManagerSkill()
    return _dialogue_manager_singleton


__all__ = [
    "DialogueDecision",
    "DialogueInput",
    "DialogueManagerSkill",
    "get_dialogue_manager_skill",
    "near_duplicate",
]
