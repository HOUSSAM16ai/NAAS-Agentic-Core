"""
PedagogicalPolicySkill — الطبقة 4 (محرّك السياسة التربوية) من المعمارية الإدراكية
العصبية-الرمزية (D-129).

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill».

## المسؤولية الواحدة
تقرّر **أقل تدخّل تربوي مفيد الآن** — لا تحلّ الرياضيات، ولا تشخّص اللغة، ولا تقيس
الإتقان. تختار نوع التدخّل من حالة المحادثة فقط:
``definition`` (تعريف) | ``socratic`` (سؤال موجّه محدود) | ``symbolic_reveal`` (حلّ رمزي).

## الكارثة التي تحلّها (transcript حي بعد D-128)
السرد السقراطي صار فريداً (لا تكرار)، لكن النظام **يسأل بلا توقف** ولا يعترف بإجابات
الطالب ولا يتقدّم. الطالب يجيب «نفس اللون»/«2»/«أقل من ثلاثة» فيتلقى سؤالاً آخر — حلقة
استجواب بلا scaffolding. السياسة تكسرها: ميزانية أسئلة محدودة ثم حلّ رمزي + اعتراف بالإجابة.

## العقد التربوي (D-129)
تعريف → سؤال سقراطي محدود → اعتراف بالإجابة + تقدّم → حلّ رمزي عند الحاجة.
القاعدة الذهبية: لا سؤال إضافي بلا معنى · لا تكرار بلا تقدّم · لا إجابة بلا سياق · لا حلّ
رمزي قبل استنفاد محاولة الفهم.

## الاستقلالية (§0.5)
- لا يستورد من Skills أخرى. حتمي تماماً (لا LLM في القرار) — قابل للاختبار بـ pytest.

## القياس (Prometheus)
- `cogniforge_skill_pedagogical_policy_total{action,acknowledged}` (counter)
"""

from __future__ import annotations

import contextlib
from typing import Literal

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.doctrine import PEDAGOGICAL_POLICY_DOCTRINE_VERSION

#: ميزانية الأسئلة السقراطية لكل مسار — بعدها ⇒ حلّ رمزي (لا استجواب لا نهائي).
MAX_SOCRATIC: int = 2

PolicyAction = Literal["definition", "socratic", "symbolic_reveal"]

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
#: أدوات الاستفهام — الرسالة التي تبدأ بها = سؤال جديد لا إجابة.
_QUESTION_STARTERS: tuple[str, ...] = (
    "ما",
    "كيف",
    "لماذا",
    "لما",
    "هل",
    "ليش",
    "علاش",
    "أين",
    "اين",
    "متى",
    "كم",
    "ماذا",
    "وش",
    "واش",
    "اشرح",
    "وضح",
)
#: علامات أن المساعد قدّم تعريفاً/شرحاً سابقاً (عناوين ## أو صيغ التعريف).
_DEFINITION_MARKERS: tuple[str, ...] = (
    "## ما هو",
    "## ماذا نقصد",
    "## العلاقة",
    "## تأليفات",
    "## الحل الكامل",
    "## لماذا",
    "هو عدد الطرق",
    "هي الهدف",
    "البسط هو",
    "المقام هو",
    "الحادثة a هي",
    "الحادثة a تعني",
)


def _normalize(text: str) -> str:
    return (text or "").translate(_AR_DIGITS).strip().lower()


def is_answer_message(text: str) -> bool:
    """D-129: هل رسالة الطالب **إجابة** (لا سؤال جديد)؟

    إجابة = قصيرة (≤ 5 كلمات) + غير فارغة + لا تبدأ بأداة استفهام. («نفس اللون»، «2»،
    «أقل من ثلاثة»، «التوافيق» = إجابات؛ «كيف نحسب» = سؤال جديد).
    """
    t = _normalize(text)
    if not t:
        return False
    words = t.split()
    if len(words) > 5:
        return False
    first = words[0].strip("؟?.,!")
    return not any(first == s or t.startswith(s + " ") for s in _QUESTION_STARTERS)


def count_socratic_questions(history: list[dict[str, str]] | None) -> int:
    """عدد رسائل المساعد السابقة المنتهية بـ«؟» (الأسئلة السقراطية المطروحة)."""
    count = 0
    for msg in history or []:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = str(msg.get("content", "")).strip()
        if content.endswith("؟") or content.endswith("?"):
            count += 1
    return count


def definition_already_given(history: list[dict[str, str]] | None) -> bool:
    """هل قدّم المساعد تعريفاً/شرحاً سابقاً؟ (لا نُعيد التعريف — نتقدّم)."""
    for msg in (history or [])[-10:]:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        low = _normalize(str(msg.get("content", "")))
        if any(m in low for m in _DEFINITION_MARKERS):
            return True
    return False


def student_answered(question: str, history: list[dict[str, str]] | None) -> bool:
    """هل الطالب يُجيب سؤالاً سقراطياً سابقاً؟ (آخر مساعد سأل «؟» + الحالي إجابة)."""
    last_assistant = None
    for msg in reversed(history or []):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            last_assistant = str(msg.get("content", "")).strip()
            break
    if not last_assistant:
        return False
    if not (last_assistant.endswith("؟") or last_assistant.endswith("?")):
        return False
    return is_answer_message(question)


# ── العقود (Pydantic) ────────────────────────────────────────────────────────
class PolicyInput(RobustBaseModel):
    """مدخلات السياسة — typed contract."""

    concept: str = Field(..., min_length=1, max_length=64)
    misconception: str = Field(default="none", max_length=64)
    question: str = Field(..., min_length=1, max_length=8000)
    history: list[dict[str, str]] | None = None


class PolicyOutput(RobustBaseModel):
    """قرار السياسة: التدخّل + هل نعترف بإجابة الطالب + إشارات الحالة."""

    action: PolicyAction
    acknowledge: bool = False
    socratic_count: int = 0
    student_answered: bool = False


# ── Prometheus metrics ─────────────────────────────────────────────────────────────
try:
    from prometheus_client import REGISTRY, Counter

    if "cogniforge_skill_pedagogical_policy_total" in {m.name for m in REGISTRY.collect()}:
        _policy_total = None
    else:
        _policy_total = Counter(
            "cogniforge_skill_pedagogical_policy_total",
            "Pedagogical-policy decisions, labelled by action/acknowledged.",
            ["action", "acknowledged"],
        )

    def _record(action: str, acknowledged: bool) -> None:
        with contextlib.suppress(Exception):
            if _policy_total is not None:
                _policy_total.labels(action=action, acknowledged=str(acknowledged).lower()).inc()

except Exception:  # pragma: no cover

    def _record(action: str, acknowledged: bool) -> None:
        pass


class PedagogicalPolicySkill:
    """
    Skill حتمي لاختيار التدخّل التربوي (الطبقة 4 — D-129).

    عقد دائم (لا يُكسر بدون ADR):
    1. السقراطية محدودة بميزانية (MAX_SOCRATIC) — بعدها حلّ رمزي، لا استجواب لا نهائي.
    2. الاعتراف بإجابة الطالب إلزامي (acknowledge عند student_answered).
    3. حتمي تماماً — لا LLM في القرار. الـ LLM للسرد السقراطي فقط (D-128).
    """

    _skill_name: str = "pedagogical_policy"
    doctrine_version: str = PEDAGOGICAL_POLICY_DOCTRINE_VERSION

    def decide(self, payload: PolicyInput) -> PolicyOutput:
        """يقرّر أقل تدخّل مفيد الآن — حتمي. لا يرفع استثناءات منطقية."""
        socratic_count = count_socratic_questions(payload.history)
        answered = student_answered(payload.question, payload.history)
        def_given = definition_already_given(payload.history)

        if socratic_count >= MAX_SOCRATIC:
            action: PolicyAction = "symbolic_reveal"  # نفاد الميزانية ⇒ إنقاذ تربوي
        elif not def_given and not answered:
            action = "definition"  # المفهوم جديد ⇒ تعريف موجز
        else:
            action = "socratic"  # لمس الفكرة ⇒ سؤال موجّه واحد (محدود)

        _record(action, answered)
        return PolicyOutput(
            action=action,
            acknowledge=answered,
            socratic_count=socratic_count,
            student_answered=answered,
        )


_pedagogical_policy_singleton: PedagogicalPolicySkill | None = None


def get_pedagogical_policy_skill() -> PedagogicalPolicySkill:
    """يُرجع نسخة مفردة (lazy singleton)."""
    global _pedagogical_policy_singleton
    if _pedagogical_policy_singleton is None:
        _pedagogical_policy_singleton = PedagogicalPolicySkill()
    return _pedagogical_policy_singleton


__all__ = [
    "MAX_SOCRATIC",
    "PedagogicalPolicySkill",
    "PolicyAction",
    "PolicyInput",
    "PolicyOutput",
    "count_socratic_questions",
    "definition_already_given",
    "get_pedagogical_policy_skill",
    "is_answer_message",
    "student_answered",
]
