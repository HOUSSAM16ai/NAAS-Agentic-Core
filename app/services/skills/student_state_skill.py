"""
StudentStateSkill — قراءة «حالة الطالب» كـ**إشارة قرار** (D-133).

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill».

## المسؤولية الواحدة
تحويل رسالة الطالب (+ تاريخ المحادثة) إلى **حزمة حالة متعدّدة الإشارات**:
``StudentState(primary_intent, secondary_signals, frustration)`` — لا تصنيفاً جامداً
واحداً. لا تحسب الرياضيات، ولا تعرّف المفهوم، ولا تقرّر السياسة (الطبقة 4). تقرأ فقط
**ماذا يريد الطالب** (النيّة) و**حالته الشعورية اللحظية** (الإحباط).

## الكارثة التي تحلّها (إعادة توجيه المالك)
النظام يفكّر بـ«المفهوم» بينما الطالب يتحرّك بـ**نيّة**: «لم أفهم X» ≠ «ما هو X»؛
«أعطني مثالاً» ≠ تعريف؛ «كيف نحسب» = إجراء. و«لم أفهم»×5 = **إحباط** لا يراه النظام.
هذه الطبقة تجعل الـ label يُنتج **بيداغوجيا مغايرة** (لا قاموساً جميلاً).

## نقد المالك الثلاثي (مُجسَّد في العقد)
1. **متعدّد الإشارات لا تصنيف جامد:** «لم أفهم المتغير العشوائي» = confusion + (definition)
   — `primary_intent + secondary_signals` تحفظ الحزمة كاملة.
2. **LLM = مُفسِّر ثانوي لا حَكَم:** الكواشف الحتمية هي السلطة؛ الـ LLM يُستدعى **فقط** عند
   `primary=unknown` (صياغة جديدة) ولا يطغى على إشارة حتمية. إشارته ثانوية.
3. **الإحباط لحظي يتلاشى:** يُحسب من **نافذة حديثة**، يتعافى فور رسالة غير-حيرة، يُغيّر
   السياسة لهذا الدور فقط، **لا يُخزَّن** كصفة طالب. لا I/O، لا حالة دائمة.

## الاستقلالية (§0.5)
- لا يستورد من Skills أخرى (markers محلية). حتمي تماماً في `read` — قابل للاختبار بـ pytest.

## القياس (Prometheus)
- `cogniforge_skill_student_state_total{primary_intent,source}` (counter)
- المقاييس السلوكية: `tutor_metrics.record_intent / record_frustration`.
"""

from __future__ import annotations

import contextlib
from typing import Literal

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill
from app.services.skills.doctrine import STUDENT_STATE_DOCTRINE_VERSION
from shared.intent import markers_for

#: نيّات الطالب — ماذا يريد (لا «ما المفهوم»).
Intent = Literal[
    "definition",
    "confusion",
    "example_request",
    "procedure",
    "comparison",
    "hint_request",
    "answer",
    "unknown",
]
#: حالة الإحباط اللحظية (تتلاشى، لا تُخزَّن).
FrustrationLevel = Literal["none", "low", "medium", "high"]

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _normalize(text: str) -> str:
    return (text or "").translate(_AR_DIGITS).strip().lower()


# ── markers من المصدر القانوني الواحد (D-186) ─────────────────────────────────────────
# §0.5 يمنع استيراد **مهارة** من مهارة أخرى؛ و`shared/intent` ليست مهارة بل مكتبة
# حتمية بلا تبعيات (نظير `shared/notation` الذي تستهلكه `NotationSkill`). الاستقلال محفوظ:
# لا حالة ولا شبكة ولا استيراد من `app/`.
#
# **لماذا لم تعد محلّية (ISS-139):** كانت `_DEFINITION_MARKERS` هنا (13 علامة) تُخالف
# `_DEFINITIONAL_MARKERS` في `semantic_property` (23) و`_DEFINITIONAL_INTENT` في
# `shared/notation` (27) — بلا اتّفاق بين أيّ اثنتين. فـ«ماذا يقصد بالحرف C» صُنِّفت
# `unknown` هنا، فتخطّى الدورُ المرحلةَ التعريفية وأُجيب الطالب بمثالٍ عارٍ.
#: حيرة صريحة («لم أفهم/مش فاهم»). أولوية عالية: الحيرة تطغى على بقية النيّات.
_CONFUSION_MARKERS: tuple[str, ...] = markers_for("confusion")
#: طلب مثال صريح («أعطني مثالاً»).
_EXAMPLE_MARKERS: tuple[str, ...] = markers_for("example_request")
#: طلب إجراء/طريقة حساب («كيف نحسب»).
_PROCEDURE_MARKERS: tuple[str, ...] = markers_for("procedure")
#: نيّة تعريفية («ما معنى/ماذا نقصد»).
_DEFINITION_MARKERS: tuple[str, ...] = markers_for("definition")
#: مقارنة/علاقة (D-125).
_COMPARISON_MARKERS: tuple[str, ...] = markers_for("comparison")
#: طلب تلميح/مساعدة («تلميح/ساعدني»).
_HINT_MARKERS: tuple[str, ...] = markers_for("hint_request")
#: أدوات استفهام (الرسالة التي تبدأ بها = ليست إجابة قصيرة).
_QUESTION_STARTERS: tuple[str, ...] = (
    "ما",
    "كيف",
    "لماذا",
    "لما",
    "هل",
    "ليش",
    "علاش",
    "اين",
    "أين",
    "متى",
    "كم",
    "ماذا",
    "وش",
    "واش",
    "اشرح",
    "وضح",
)
#: enum مُقيَّد لمخرج الـ LLM Listener (الطبقة 1 الآمنة، نقد 2).
_VALID_INTENTS: frozenset[str] = frozenset(
    {"definition", "confusion", "example_request", "procedure", "comparison", "hint_request"}
)
#: نافذة الإحباط — آخر N رسالة طالب (لحظي، نقد 3).
_FRUSTRATION_WINDOW: int = 4


# ── العقود (Pydantic) ────────────────────────────────────────────────────────
class StudentStateInput(RobustBaseModel):
    """مدخلات قراءة الحالة — typed contract."""

    question: str = Field(..., min_length=1, max_length=8000)
    history: list[dict[str, str]] | None = None


class StudentState(RobustBaseModel):
    """حزمة الطالب: النيّة الأساسية + إشارات ثانوية + الإحباط اللحظي."""

    primary_intent: Intent
    secondary_signals: tuple[Intent, ...] = ()
    frustration: FrustrationLevel = "none"
    source: str = "deterministic"  # deterministic | llm


# ── Prometheus metrics ─────────────────────────────────────────────────────────────
try:
    from prometheus_client import REGISTRY, Counter

    if "cogniforge_skill_student_state_total" in {m.name for m in REGISTRY.collect()}:
        _ss_total = None
    else:
        _ss_total = Counter(
            "cogniforge_skill_student_state_total",
            "Student-state reads, labelled by primary_intent/source.",
            ["primary_intent", "source"],
        )

    def _record(primary_intent: str, source: str) -> None:
        with contextlib.suppress(Exception):
            if _ss_total is not None:
                _ss_total.labels(primary_intent=primary_intent, source=source).inc()

except Exception:  # pragma: no cover

    def _record(primary_intent: str, source: str) -> None:
        pass


def _has_pending_socratic_question(history: list[dict[str, str]] | None) -> bool:
    """هل أحدث رسالة مساعد سؤال سقراطي معلّق (تنتهي بـ«؟»)؟ — لكشف نيّة الإجابة محلياً."""
    for msg in reversed(history or []):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "assistant":
            content = str(msg.get("content", "")).strip()
            return content.endswith("؟") or content.endswith("?")
    return False


def _looks_like_answer(norm: str) -> bool:
    """رسالة قصيرة لا تبدأ بأداة استفهام = إجابة محتملة على سؤال سقراطي."""
    if not norm:
        return False
    words = norm.split()
    if len(words) > 6:
        return False
    first = words[0].strip("؟?.,!")
    return not any(first == s or norm.startswith(s + " ") for s in _QUESTION_STARTERS)


def _user_messages(history: list[dict[str, str]] | None) -> list[str]:
    return [
        str(m.get("content", ""))
        for m in (history or [])
        if isinstance(m, dict) and m.get("role") == "user"
    ]


def _assess_frustration(question: str, history: list[dict[str, str]] | None) -> FrustrationLevel:
    """الإحباط اللحظي (نقد 3): نافذة حديثة + تكرار نفس السؤال؛ يتلاشى عند التعافي.

    - يُحسب من آخر ``_FRUSTRATION_WINDOW`` رسائل طالب (incl الحالية) — لحظي لا تراكمي أبدي.
    - **يتلاشى فوراً** إن لم تكن الرسالة الحالية حيرة (لحظة تعافٍ ⇒ سقف ``low``).
    - تكرار نفس السؤال يرفع الدرجة. لا I/O، لا تخزين — صفة لحظية لا هوية.
    """
    cur = _normalize(question)
    recent = [_normalize(m) for m in _user_messages(history)][-(_FRUSTRATION_WINDOW - 1) :]
    window = [*recent, cur]
    confusions = sum(1 for m in window if any(k in m for k in _CONFUSION_MARKERS))
    # تكرار نفس السؤال (≥ مرتين في النافذة) ⇒ تصاعد.
    if cur and sum(1 for m in window if m == cur) >= 2:
        confusions += 1
    current_is_confusion = any(k in cur for k in _CONFUSION_MARKERS)
    if not current_is_confusion:
        # تعافٍ لحظي: مهما تراكم سابقاً، اللحظة الحالية ليست حيرة ⇒ خفّض.
        return "low" if confusions >= 2 else "none"
    if confusions >= 4:
        return "high"
    if confusions >= 2:
        return "medium"
    return "low"


class StudentStateSkill(BaseSkill):
    """
    قراءة حالة الطالب كإشارة قرار (D-133).

    عقد دائم (لا يُكسر بدون ADR):
    1. **متعدّد الإشارات** — `primary_intent + secondary_signals` (لا تصنيف جامد، نقد 1).
    2. **LLM = مُفسِّر ثانوي لا حَكَم** — حتمي أولاً؛ LLM فقط عند unknown ولا يطغى (نقد 2).
    3. **الإحباط لحظي يتلاشى** — نافذة حديثة، يتعافى، لا يُخزَّن كصفة (نقد 3).
    4. الـ label يجب أن يُنتج بيداغوجيا مغايرة (السياسة، لا هذه الطبقة).
    """

    _skill_name: str = "student_state"
    name = "student_state"

    def run(self, payload):
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`read`."""
        return self.read(payload)

    doctrine_version: str = STUDENT_STATE_DOCTRINE_VERSION
    _LLM_TIMEOUT_S: float = 8.0

    def read(self, payload: StudentStateInput | str) -> StudentState:
        """حتمي: يقرأ الحزمة (نيّة أساسية + ثانوية + إحباط) من markers + التاريخ.

        لا يرفع استثناءات منطقية. ``unknown`` فقط حين لا تُطابق أي markers.
        """
        if isinstance(payload, str):
            question, history = payload, None
        else:
            question, history = payload.question, payload.history
        norm = _normalize(question)
        frustration = _assess_frustration(question, history)

        # كل الإشارات المُطابَقة (متعدّد-إشارات، نقد 1).
        signals: list[Intent] = []
        if any(m in norm for m in _CONFUSION_MARKERS):
            signals.append("confusion")
        if any(m in norm for m in _EXAMPLE_MARKERS):
            signals.append("example_request")
        if any(m in norm for m in _PROCEDURE_MARKERS):
            signals.append("procedure")
        if any(m in norm for m in _COMPARISON_MARKERS):
            signals.append("comparison")
        if any(m in norm for m in _HINT_MARKERS):
            signals.append("hint_request")
        if any(m in norm for m in _DEFINITION_MARKERS):
            signals.append("definition")
        if _has_pending_socratic_question(history) and _looks_like_answer(norm):
            signals.append("answer")
        # نقد المالك 1: «لم أفهم X» = confusion **+ definition_request** ضمنياً — الحيرة
        # عن مفهوم مُسمّى (يبقى محتوى بعد إزالة عبارة الحيرة) تحمل طلب تعريف ثانوياً.
        if "confusion" in signals and "definition" not in signals:
            stripped = norm
            for mk in _CONFUSION_MARKERS:
                stripped = stripped.replace(mk, " ")
            stripped = stripped.strip(" ،,.!؟?")
            if len(stripped) >= 3:  # يشير إلى موضوع/مفهوم، لا تعجّب حيرة مجرّد
                signals.append("definition")

        primary = self._pick_primary(signals)
        secondary = tuple(s for s in signals if s != primary)
        _record(primary, "deterministic")
        return StudentState(
            primary_intent=primary,
            secondary_signals=secondary,
            frustration=frustration,
            source="deterministic",
        )

    @staticmethod
    def _pick_primary(signals: list[Intent]) -> Intent:
        """ترتيب أولوية النيّة الأساسية (الحيرة تطغى — لحظة تدخّل تربوي).

        confusion > example_request > procedure > comparison > hint_request > answer > definition.
        («لم أفهم المتغير العشوائي» ⇒ primary=confusion، secondary∋definition — نقد 1).
        """
        order: tuple[Intent, ...] = (
            "confusion",
            "example_request",
            "procedure",
            "comparison",
            "hint_request",
            "answer",
            "definition",
        )
        for intent in order:
            if intent in signals:
                return intent
        return "unknown"

    async def read_or_classify(self, payload: StudentStateInput | str) -> StudentState:
        """هجين (نقد 2): حتمي أولاً؛ عند ``primary=unknown`` فقط ⇒ LLM Listener ثانوي محروس.

        الـ LLM **لا يطغى** على إشارة حتمية — يُستدعى حصراً حين تعجز الكواشف عن صياغة جديدة.
        """
        state = self.read(payload)
        if state.primary_intent != "unknown":
            return state
        question = payload if isinstance(payload, str) else payload.question
        intent = await self._classify_with_llm(question)
        if intent is None:
            return state
        _record(intent, "llm")
        return StudentState(
            primary_intent=intent,  # type: ignore[arg-type]
            secondary_signals=state.secondary_signals,
            frustration=state.frustration,
            source="llm",
        )

    @classmethod
    async def _classify_with_llm(cls, question: str) -> str | None:
        """الطبقة 1: Listener محروس — يُعيد intent واحداً من enum مُقيَّد أو None.

        مخرج مُقيَّد (enum-validation) + timeout + fallback. لا يشرح، لا يحسب — تصنيف نيّة فقط.
        """
        import asyncio

        try:
            from app.core.ai_gateway import get_ai_client

            system_prompt = (
                "أنت مُصنّف نيّة (لا تشرح، لا تجيب، لا تحسب). صنّف ما يريده الطالب من رسالته "
                "إلى كلمة واحدة فقط من هذه القائمة بلا أي نص آخر:\n"
                "definition (يسأل عن معنى/تعريف) | confusion (يعبّر عن عدم فهم) | "
                "example_request (يطلب مثالاً) | procedure (يسأل كيف نحسب/الخطوات) | "
                "comparison (يسأل عن فرق/علاقة) | hint_request (يطلب تلميحاً).\n"
                "أعِد الكلمة الإنجليزية فقط."
            )
            raw = await asyncio.wait_for(
                get_ai_client().send_message(
                    system_prompt, question.strip()[:400], temperature=0.0
                ),
                timeout=cls._LLM_TIMEOUT_S,
            )
            if not raw or not isinstance(raw, str) or not raw.strip():
                return None
            token = raw.strip().lower().split()[0].strip(".,:;\"'`")
            if token in _VALID_INTENTS:
                return token
            low = raw.lower()
            for intent in _VALID_INTENTS:
                if intent in low:
                    return intent
            return None
        except Exception:  # pragma: no cover — fail-safe
            return None


_student_state_singleton: StudentStateSkill | None = None


def get_student_state_skill() -> StudentStateSkill:
    """يُرجع نسخة مفردة (lazy singleton)."""
    global _student_state_singleton
    if _student_state_singleton is None:
        _student_state_singleton = StudentStateSkill()
    return _student_state_singleton


__all__ = [
    "FrustrationLevel",
    "Intent",
    "StudentState",
    "StudentStateInput",
    "StudentStateSkill",
    "get_student_state_skill",
]
