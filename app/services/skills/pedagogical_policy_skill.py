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
from app.services.skills.base import BaseSkill
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
    # ISS-120 (D-153): الحيرة المجرّدة ليست إجابة (اتساق مع is_response_to_socratic).
    if _is_bare_confusion(t):
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


def _has_pending_socratic_question(history: list[dict[str, str]] | None) -> bool:
    """D-130/D-137: هل أحدث رسالة مساعد سؤال سقراطي معلّق؟

    D-137 (إصلاح جذري): السؤال السقراطي الواقعي قد ينتهي بأمر («متى تنجح A؟ أعطني مثالاً»)
    فالـ «؟» في **منتصف** الرسالة لا آخرها — `endswith` كان يفوّتها فتُهمَل إجابة الطالب
    (كارثة الخيانة البيداغوجية). نكشف «؟» في أي موضع ضمن رسالة **قصيرة** (لا إفراغ تمرين طويل).
    """
    for msg in reversed(history or []):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "assistant":
            content = str(msg.get("content", "")).strip()
            if len(content) > 500:  # إفراغ تمرين/شرح طويل ⇒ ليس سؤالاً سقراطياً معلّقاً
                return False
            return "؟" in content or "?" in content
    return False


#: D-137: أدوات استفهام (الرسالة التي تبدأ بإحداها وتنتهي بـ«؟» = سؤال مضادّ لا إجابة).
_INTERROGATIVE_OPENERS: tuple[str, ...] = (
    "لماذا",
    "ماذا",
    "كيف",
    "هل",
    "متى",
    "اين",
    "أين",
    "كم ",
    "ما هو",
    "ما هي",
    "ماهو",
    "ماهي",
    "علاش",
    "واش",
    "شنو",
)


def _is_counter_question(normalized: str) -> bool:
    """D-137: هل الرسالة سؤال مضادّ (يبدأ بأداة استفهام وينتهي بـ«؟») لا إجابة؟"""
    if not (normalized.endswith("؟") or normalized.endswith("?")):
        return False
    return any(normalized.startswith(w) for w in _INTERROGATIVE_OPENERS)


#: أفعال طلب صريحة (الرسالة التي تبدأ/تحوي واحداً منها + اسم تمرين = طلب جديد لا إجابة).
_EXPLICIT_REQUEST_VERBS: tuple[str, ...] = (
    "اعطني",
    "أعطني",
    "اعطيني",
    "هات",
    "هاتي",
    "اكتب",
    "ارسم",
    "أرسم",
    "ابدأ",
)
#: كلمات تدلّ على طلب محتوى/تمرين جديد.
_NEW_CONTENT_WORDS: tuple[str, ...] = (
    "تمرين",
    "تمارين",
    "مسألة",
    "مسائل",
    "درس",
    "exercice",
    "exercise",
)


def _is_explicit_request(normalized: str) -> bool:
    """D-130 (تحسين A): هل الرسالة أمر/طلب محتوى جديد صريح (لا إجابة سقراطية)؟"""
    padded = f" {normalized} "
    has_verb = any(
        normalized.startswith(v + " ") or f" {v} " in padded for v in _EXPLICIT_REQUEST_VERBS
    )
    has_new_content = any(w in normalized for w in _NEW_CONTENT_WORDS)
    return has_verb and has_new_content


def _is_topic_switch(message: str) -> bool:
    """D-130 (تحسين A): هل الرسالة تبديل موضوع صريح (≠ احتمالات)؟ (حارس D-101)."""
    try:
        from app.services.capabilities.arabic_normalize import primary_canonical_topic

        topic = primary_canonical_topic(message)
        return topic is not None and topic.canonical_id != "probability"
    except Exception:  # pragma: no cover - fail-safe
        return False


#: ISS-120 (D-153): إشارات الحيرة المجرّدة — «لم أفهم» **ليست إجابة** على سؤال
#: سقراطي؛ هي حيرة تُوجَّه لمسارات الحيرة. معاملتها كإجابة كانت تُنتج
#: «إجابتك في الطريق الصحيح —» رداً على «لم أفهم» (خيانة بيداغوجية).
#: نسخة محلية مصغّرة (استقلالية الـ Skills — §0.5، نمط D-013).
_BARE_CONFUSION_MARKERS: tuple[str, ...] = (
    "لم افهم",
    "لم أفهم",
    "ما فهمت",
    "مافهمت",
    "مفهمتش",
    "ما فهمتش",
    "لا افهم",
    "لا أفهم",
    "لست افهم",
    "مش فاهم",
    "لم استوعب",
    "je ne comprends pas",
    "i don't understand",
)


def _is_bare_confusion(normalized: str) -> bool:
    """ISS-120 (D-153): هل الرسالة حيرة مجرّدة (لا محتوى إجابة فيها)؟

    حيرة مجرّدة = تحوي إشارة حيرة **و** قصيرة (≤ 6 كلمات) — «لم أفهم»،
    «لم افهم التمرين»، «مفهمتش». رسالة أطول تحوي محتوى فعلياً («لم أفهم
    لماذا نجمع الحالات الممكنة…») تُترَك للمُقيّم يزنها كاملة.
    """
    if not normalized:
        return False
    if len(normalized.split()) > 6:
        return False
    return any(m in normalized for m in _BARE_CONFUSION_MARKERS)


def is_response_to_socratic(message: str, history: list[dict[str, str]] | None) -> bool:
    """D-130 (تحسين A، يحل Concern 1): هل رسالة الطالب إجابة على سؤال سقراطي معلّق؟

    **مستقل عن الطول تماماً** (فعل كلامي لا عدد كلمات): إجابة = «سؤال سقراطي معلّق» و«ليست
    أمراً صريحاً لمحتوى جديد» و«ليست تبديل موضوع». «نفس اللون» القصيرة والإجابة العبقرية
    الطويلة كلتاهما إجابة؛ «اعطني تمرين الدوال» ليست إجابة.
    """
    if not _has_pending_socratic_question(history):
        return False
    t = _normalize(message)
    if not t:
        return False
    # ISS-120 (D-153): الحيرة المجرّدة («لم أفهم») ليست إجابة أبداً — تُوجَّه
    # لمسارات الحيرة (تصعيد التمثيل)، لا لتقييم الإجابات (كانت تُنتج
    # «إجابتك في الطريق الصحيح —» رداً على «لم أفهم»).
    if _is_bare_confusion(t):
        return False
    if _is_explicit_request(t):
        return False
    if _is_counter_question(t):  # D-137: سؤال مضادّ («لماذا نسأل هذا؟») ليس إجابة
        return False
    return not _is_topic_switch(message)


def student_answered(question: str, history: list[dict[str, str]] | None) -> bool:
    """هل الطالب يُجيب سؤالاً سقراطياً سابقاً؟

    D-130 (تحسين A): يُحدَّد بالفعل الكلامي عبر ``is_response_to_socratic`` (مستقل عن الطول)
    بدل عدّ الكلمات (D-129 الأصلي كان يقصره على ≤5 كلمات — كان يفوّت الإجابات العبقرية الطويلة).
    """
    return is_response_to_socratic(question, history)


#: مفاهيم بصيرة سريعة (تكفيها لمسة واحدة) — أساس ميزانية 1.
_QUICK_INSIGHT_CONCEPTS: frozenset[str] = frozenset(
    {"color_white", "color_red", "color_green", "combinations"}
)
#: علامات الحيرة (لرفع وتيرة التصعيد للرمزي).
_CONFUSION_MARKERS: tuple[str, ...] = (
    "لم افهم",
    "لم أفهم",
    "مفهمتش",
    "ما فهمت",
    "لا افهم",
    "لا أفهم",
    "مازلت لا",
)


def _count_confusion(history: list[dict[str, str]] | None) -> int:
    """عدد علامات الحيرة في رسائل الطالب (لتعديل الميزانية التكيّفية)."""
    count = 0
    for msg in history or []:
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        low = _normalize(str(msg.get("content", "")))
        if any(m in low for m in _CONFUSION_MARKERS):
            count += 1
    return count


def socratic_budget(
    concept: str,
    support_level: int | None = None,
    confusion_count: int = 0,
    frustration: str | None = None,
) -> int:
    """D-130 (تحسين B، يحل Concern 2): ميزانية الأسئلة السقراطية التكيّفية.

    مرتبطة بالمفهوم (مفاهيمي أعمق، بصيرة سريعة أقصر) وبحالة الطالب (BKT support_level،
    D-104/D-126) وبالحيرة المتكرّرة. clamp [1, 3]. ممنوع سقف ثابت واحد لكل المفاهيم.

    D-133: ``frustration=="high"`` ⇒ **0** (إيقاف التكرار فوراً، كشف خطوة رمزية أقرب) —
    إشارة لحظية لا هوية: تُغيّر هذا الدور فقط. الإحباط يطغى على بقية الميزانية.
    """
    if frustration == "high":  # D-133: لا سؤال إضافي لطالب محبَط ⇒ حلّ رمزي مباشر
        return 0
    budget = 1 if concept in _QUICK_INSIGHT_CONCEPTS else 2  # مفاهيمي/غير معروف ⇒ أساس 2
    if isinstance(support_level, int):
        if support_level <= 2:  # متعثّر ⇒ سرّع للسقالة الرمزية (لا نُحبطه)
            budget -= 1
        elif support_level >= 4:  # متمكّن ⇒ يحتمل عمقاً سقراطياً أكبر
            budget += 1
    if confusion_count > 1:  # حيرة متكرّرة ⇒ تصاعد أسرع
        budget -= confusion_count - 1
    return max(1, min(3, budget))


#: D-133: خريطة النيّة → نوع الرد (إشارة قرار: الـ label يُنتج بيداغوجيا مغايرة، لا تصنيفاً).
_INTENT_RESPONSE_MODE: dict[str, str] = {
    "confusion": "confusion_enriched",  # تعريف + مثال ملموس + سؤال واحد
    "example_request": "example_first",  # مثال قبل النظرية
    "procedure": "steps",  # خطوات لا تعريف
    "comparison": "relationship",  # شرح علاقة (D-125)
    "definition": "define",  # تعريف (D-132)
    "hint_request": "hint",  # تلميح أدنى
    "answer": "evaluate",  # تقييم الإجابة (D-130)
}


def response_mode_for(intent: str | None, action: PolicyAction, frustration: str | None) -> str:
    """D-133: نوع الرد المُختار — يربط النيّة/الإحباط بالبيداغوجيا الفعلية (للقياس + التوجيه)."""
    if frustration == "high":
        return "reveal"  # إيقاف التكرار + كشف خطوة أقرب
    if intent and intent in _INTENT_RESPONSE_MODE:
        return _INTENT_RESPONSE_MODE[intent]
    # غير محدّد ⇒ مشتقّ من الإجراء الحتمي القائم.
    return {"definition": "define", "socratic": "socratic", "symbolic_reveal": "reveal"}.get(
        action, action
    )


# ── العقود (Pydantic) ────────────────────────────────────────────────────────
class PolicyInput(RobustBaseModel):
    """مدخلات السياسة — typed contract."""

    concept: str = Field(..., min_length=1, max_length=64)
    misconception: str = Field(default="none", max_length=64)
    question: str = Field(..., min_length=1, max_length=8000)
    history: list[dict[str, str]] | None = None
    #: D-130 (تحسين B): مستوى الدعم (1..5، BKT/D-126) لميزانية سقراطية تكيّفية.
    support_level: int | None = None
    #: D-133: نيّة الطالب الأساسية (StudentStateSkill) — تُحدّد نوع الرد.
    intent: str | None = None
    #: D-133: حالة الإحباط اللحظية (none/low/medium/high) — high ⇒ إيقاف التكرار.
    frustration: str | None = None


class PolicyOutput(RobustBaseModel):
    """قرار السياسة: التدخّل + هل نعترف بإجابة الطالب + إشارات الحالة."""

    action: PolicyAction
    acknowledge: bool = False
    socratic_count: int = 0
    student_answered: bool = False
    #: D-133: نوع الرد المُختار — يُثبت أن النيّة/الإحباط أنتجا بيداغوجيا مغايرة.
    response_mode: str = "socratic"


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


class PedagogicalPolicySkill(BaseSkill):
    """
    Skill حتمي لاختيار التدخّل التربوي (الطبقة 4 — D-129/D-130).

    عقد دائم (لا يُكسر بدون ADR):
    1. السقراطية محدودة بميزانية **تكيّفية** (``socratic_budget`` حسب المفهوم/الحالة، D-130
       تحسين B) — بعدها حلّ رمزي، لا استجواب لا نهائي.
    2. الاعتراف بإجابة الطالب إلزامي (acknowledge عند student_answered) — يُحدَّد بالفعل الكلامي
       لا بالطول (D-130 تحسين A).
    3. حتمي تماماً — لا LLM في القرار. الـ LLM للسرد السقراطي/التقييم فقط (D-128/D-130).
    """

    _skill_name: str = "pedagogical_policy"
    name = "pedagogical_policy"

    def run(self, payload):
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`decide`."""
        return self.decide(payload)

    doctrine_version: str = PEDAGOGICAL_POLICY_DOCTRINE_VERSION

    def decide(self, payload: PolicyInput) -> PolicyOutput:
        """يقرّر أقل تدخّل مفيد الآن — حتمي. لا يرفع استثناءات منطقية.

        D-133: النيّة + الإحباط (إشارة قرار) يُغيّران الإجراء فعلاً — لا تصنيف فقط:
        ``frustration=="high"`` ⇒ ميزانية 0 ⇒ ``symbolic_reveal`` (إيقاف التكرار)؛
        و``response_mode`` يربط النيّة بالبيداغوجيا (confusion_enriched/example_first/steps/...).
        """
        socratic_count = count_socratic_questions(payload.history)
        answered = student_answered(payload.question, payload.history)
        def_given = definition_already_given(payload.history)
        # D-130 (تحسين B) + D-133: ميزانية تكيّفية حسب المفهوم + حالة الطالب + الحيرة + الإحباط.
        budget = socratic_budget(
            payload.concept,
            payload.support_level,
            _count_confusion(payload.history),
            payload.frustration,
        )

        if socratic_count >= budget:
            action: PolicyAction = "symbolic_reveal"  # نفاد الميزانية/إحباط ⇒ إنقاذ تربوي
        elif not def_given and not answered:
            action = "definition"  # المفهوم جديد ⇒ تعريف موجز
        else:
            action = "socratic"  # لمس الفكرة ⇒ سؤال موجّه واحد (محدود)

        mode = response_mode_for(payload.intent, action, payload.frustration)
        _record(action, answered)
        with contextlib.suppress(Exception):
            from app.services.skills.tutor_metrics import (
                record_frustration,
                record_intent,
                record_response_mode,
            )

            if payload.intent:
                record_intent(payload.intent)
            if payload.frustration:
                record_frustration(payload.frustration)
            record_response_mode(mode)
        return PolicyOutput(
            action=action,
            acknowledge=answered,
            socratic_count=socratic_count,
            student_answered=answered,
            response_mode=mode,
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
    "is_response_to_socratic",
    "response_mode_for",
    "socratic_budget",
    "student_answered",
]
