"""
PedagogicalEscalationSkill — المصفوفة التصعيدية التكيّفية (D-138).

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill».

## المسؤولية الواحدة
تقرّر **أقل تدخّل مفيد في الوقت المناسب** لتعليم **مفهوم مُسمّى** (الاحتمال الشرطي، المتغير
العشوائي…) — لا تُكرّر مستوى أبداً، وتصعّد عبر سُلّم `تعريف → مثال → محاكاة مصغّرة`، **مُعايَرةً**
بقدرة الطالب (BKT support_level) وأثر فهمه ومفهومه الخاطئ.

## ليست «سُلَّماً جامداً» (حكم المالك)
قبل كل تدخّل تسأل: **«هل تناسب هذه السقالة قدرة الطالب الحالية وصعوبة الخطوة القادمة؟»**. تدمج
ثلاث إشارات:
- **Understanding Signal**: دليل فهم المفهوم (آلية، لا «فهمت») ⇒ `mastered` (توقّف) — التصعيد على
  الأثر لا عدّ «لم أفهم».
- **Misconception Check**: مفهوم خاطئ مُشخَّص ⇒ تدخّل مُوجَّه بدل تسلّق أعمى.
- **Ability + Step-Difficulty Calibration**: `support_level` يُعايِر الرُّتبة — قدرة منخفضة ⇒ سقالة
  أعلى أسرع؛ قدرة عالية ⇒ رُتبة أخف (student agency).

## القرار حتمي (صفر LLM)
دالة نقية قابلة للاختبار بـ pytest. المحتوى الحتمي (تعريف/مثال من السجلّ، محاكاة من
`MicroSimulationSkill`) يُمرَّر إليها؛ هي تقرّر **أيّ رُتبة** وتبني النصّ النهائي. concept-scoped
(تستخدم نصّ المفهوم نفسه لذاكرة التصعيد) ⇒ لا انحراف لتمرين البكالوريا.
"""

from __future__ import annotations

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.doctrine import PEDAGOGICAL_ESCALATION_DOCTRINE_VERSION

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

#: رُتب الاستراتيجية.
L1_DEFINITION: int = 1
L2_ANALOGY: int = 2
L3_MICRO_SIMULATION: int = 3
L4_VISUAL: int = 4  # مؤجَّل — لا واجهة توليدية في القلب الآن (D-138).

#: النيّات التي تُفسَّر كـ «حيرة/طلب مزيد» (تُصعِّد للمستوى التالي غير المُسلَّم).
_CONFUSION_INTENTS: frozenset[str] = frozenset(
    {"confusion", "procedure", "hint_request", "unknown"}
)
#: علامات طلب مثال **عددي** ⇒ محاكاة مصغّرة (L3) مباشرة.
_NUMERIC_MARKERS: tuple[str, ...] = ("عددي", "رقمي", "بالارقام", "بالأرقام", "numeric")
#: طول المقطع المميِّز لكشف رُتبة سُلّمت (concept-scoped — نصّ المفهوم نفسه).
_FRAGMENT_LEN: int = 22


def _norm(text: str) -> str:
    return (text or "").translate(_AR_DIGITS).strip().lower()


class EscalationInput(RobustBaseModel):
    """مدخلات المصفوفة — typed contract (concept-scoped)."""

    concept_id: str
    title: str = ""
    definition: str = ""
    example: str = ""
    micro_sim: str | None = None
    intent: str = "unknown"
    frustration: str | None = None
    support_level: int | None = None
    history: list[dict[str, str]] = Field(default_factory=list)
    evidence_markers: tuple[str, ...] = ()
    #: مفهوم خاطئ مُشخَّص (الأورقستريتور يُجريه عبر diagnose_misconception ويمرّره).
    misconception_intervention: str | None = None
    misconception_mtype: str | None = None
    #: D-147: سؤال «خطوة التطبيق» على هذا التمرين — يُستبدَل به الـ punt العام عند نفاد السُّلّم.
    apply_step: str | None = None


class EscalationDecision(RobustBaseModel):
    """قرار المصفوفة: الإجراء + الرُّتبة + النصّ النهائي الحتمي."""

    action: str  # mastered | target_misconception | teach | exhausted
    strategy_level: int = 0  # 0..3
    text_kind: str = ""  # ack | intervention | definition | example | micro_simulation | handoff
    text: str = ""
    rationale: str = ""


class PedagogicalEscalationSkill:
    """
    المصفوفة التصعيدية التكيّفية (D-138).

    عقد دائم (لا يُكسر بدون ADR):
    1. السقالة تُختار بقدرة الطالب (support_level) وصعوبة الخطوة — لا سلّم جامد.
    2. التصعيد على أثر الفهم (evidence_markers) لا عدّ «لم أفهم».
    3. Misconception Check قبل التصعيد ⇒ تدخّل مُوجَّه.
    4. ممنوع تكرار رُتبة؛ استنفاد L3 ⇒ تسليم لطيف (handoff).
    5. concept-scoped (نصّ المفهوم نفسه لذاكرة التصعيد)؛ حتمي صفر-LLM.
    """

    _skill_name: str = "pedagogical_escalation"
    doctrine_version: str = PEDAGOGICAL_ESCALATION_DOCTRINE_VERSION

    # ── إشارات الدخل ──────────────────────────────────────────────────────────
    @staticmethod
    def _last_student_text(history: list[dict[str, str]] | None) -> str:
        for msg in reversed(history or []):
            if isinstance(msg, dict) and msg.get("role") == "user":
                return str(msg.get("content", ""))
        return ""

    def _has_understanding_evidence(
        self, evidence_markers: tuple[str, ...], history: list[dict[str, str]] | None
    ) -> bool:
        """Understanding Signal: هل أظهر الطالب **آلية فهم المفهوم** (لا «فهمت» المجرّدة)؟"""
        if not evidence_markers:
            return False
        for msg in reversed((history or [])[-6:]):
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue
            low = _norm(str(msg.get("content", "")))
            if any(_norm(m) in low for m in evidence_markers):
                return True
        return False

    def _levels_delivered(self, payload: EscalationInput) -> set[int]:
        """الرُّتب المُسلَّمة لهذا المفهوم (من نصّه نفسه في رسائل المساعد — concept-scoped)."""
        delivered: set[int] = set()
        assistant_text = " ".join(
            _norm(str(m.get("content", "")))
            for m in (payload.history or [])
            if isinstance(m, dict) and m.get("role") == "assistant"
        )
        if not assistant_text:
            return delivered
        if payload.definition and _norm(payload.definition)[:_FRAGMENT_LEN] in assistant_text:
            delivered.add(L1_DEFINITION)
        if payload.example and _norm(payload.example)[:_FRAGMENT_LEN] in assistant_text:
            delivered.add(L2_ANALOGY)
        if payload.micro_sim and _norm(payload.micro_sim)[:_FRAGMENT_LEN] in assistant_text:
            delivered.add(L3_MICRO_SIMULATION)
        return delivered

    # ── سياسة الرُّتبة ────────────────────────────────────────────────────────
    def _base_level(self, payload: EscalationInput, delivered: set[int]) -> int:
        """الرُّتبة الأساسية من النيّة (قبل المعايرة)."""
        intent = payload.intent
        if intent == "definition":
            return L1_DEFINITION
        if intent == "example_request":
            last = _norm(self._last_student_text(payload.history))
            numeric = any(_norm(m) in last for m in _NUMERIC_MARKERS)
            return L3_MICRO_SIMULATION if numeric else L2_ANALOGY
        # confusion / procedure / hint_request / unknown ⇒ المستوى التالي غير المُسلَّم.
        return (max(delivered) + 1) if delivered else L1_DEFINITION

    def _calibrate(self, base: int, payload: EscalationInput, delivered: set[int]) -> int:
        """يُعايِر الرُّتبة بالقدرة (support_level) + الإحباط + يمنع التكرار."""
        target = base
        while target in delivered and target <= L3_MICRO_SIMULATION:
            target += 1
        sup = payload.support_level if payload.support_level is not None else 3
        confused = payload.intent in _CONFUSION_INTENTS
        # قدرة منخفضة ⇒ سقالة أعلى أسرع (الوصول للمحاكاة، **لا تخطّيها** ⇒ سقف L3)؛
        # قدرة عالية ⇒ رُتبة أخف أولاً (student agency، لا إفراط في السقالة).
        if confused and sup <= 2:
            target = min(target + 1, L3_MICRO_SIMULATION)
        elif confused and sup >= 4 and target > L2_ANALOGY and L2_ANALOGY not in delivered:
            target = L2_ANALOGY
        # الإحباط العالي يُسرّع التصعيد وقد يستنفد ⇒ تسليم للرمزي (D-130: socratic_budget(high)=0).
        if payload.frustration == "high":
            target += 1
        # الحارس النهائي ضدّ التكرار ⇒ قد يستنفد L3 المُسلَّمة (handoff).
        while target in delivered and target <= L3_MICRO_SIMULATION:
            target += 1
        return min(target, L4_VISUAL)

    def _render(self, level: int, payload: EscalationInput) -> tuple[str, str]:
        """يبني نصّ الرُّتبة الحتمي. يُنزِّل الرُّتبة إن غاب محتواها."""
        for lvl in (level, level - 1, level - 2):
            if lvl == L3_MICRO_SIMULATION and payload.micro_sim:
                return f"## محاكاة مصغّرة\n\n{payload.micro_sim}", "micro_simulation"
            if lvl == L2_ANALOGY and payload.example:
                return f"## مثال ملموس\n\n{payload.example}", "example"
            if lvl == L1_DEFINITION and payload.definition:
                head = f"## {payload.title}\n\n" if payload.title else ""
                return f"{head}{payload.definition}", "definition"
        return "", ""

    @staticmethod
    def _exhausted_decision(
        payload: EscalationInput, *, fallback_text: str, fallback_rationale: str
    ) -> EscalationDecision:
        """D-147: عند نفاد السُّلّم — قُد بسؤال تطبيق مرتبط بالتمرين بدل الـ punt العام.

        إن توفّر `apply_step` (مفهوم معروف) ⇒ سؤال قائد ملموس (text_kind=apply). وإلّا ⇒
        التسليم العامّ القديم (concept مجهول) — فلا انحدار في السلوك للحالات غير المُغطّاة.
        """
        step = (payload.apply_step or "").strip()
        if step:
            return EscalationDecision(
                action="exhausted",
                text_kind="apply",
                text=step,
                rationale="apply_to_exercise",
            )
        return EscalationDecision(
            action="exhausted",
            text_kind="handoff",
            text=fallback_text,
            rationale=fallback_rationale,
        )

    # ── القرار ────────────────────────────────────────────────────────────────
    def decide(self, payload: EscalationInput) -> EscalationDecision:
        """يقرّر أقل تدخّل مفيد الآن (mastered/target_misconception/teach/exhausted)."""
        # (1) Understanding Signal — أثر فهم ⇒ توقّف + اعتراف (لا تصعيد).
        if self._has_understanding_evidence(payload.evidence_markers, payload.history):
            self._record(payload.concept_id, "mastered")
            return EscalationDecision(
                action="mastered",
                text_kind="ack",
                text="أحسنت ✅ — يبدو أنك أمسكت الفكرة. هل نطبّقها على التمرين الآن؟",
                rationale="understanding_evidence",
            )
        # (2) Misconception Check — مفهوم خاطئ مُشخَّص ⇒ تدخّل مُوجَّه (لا تسلّق أعمى).
        if payload.misconception_intervention and payload.intent in _CONFUSION_INTENTS:
            self._record(payload.concept_id, "misconception")
            return EscalationDecision(
                action="target_misconception",
                text_kind="intervention",
                text=payload.misconception_intervention,
                rationale=f"misconception:{payload.misconception_mtype or 'unknown'}",
            )
        # (3) التصعيد المُعايَر (ذاكرة + قدرة + صعوبة).
        delivered = self._levels_delivered(payload)
        target = self._calibrate(self._base_level(payload, delivered), payload, delivered)
        if target > L3_MICRO_SIMULATION:
            self._record(payload.concept_id, "exhausted")
            return self._exhausted_decision(
                payload,
                fallback_text=(
                    "مررنا بالتعريف والمثال والمحاكاة المصغّرة — لننتقل لتطبيق الفكرة على التمرين "
                    "خطوة بخطوة. أيّ خطوة تريد أن نبدأ بها؟"
                ),
                fallback_rationale="ladder_exhausted",
            )
        text, kind = self._render(target, payload)
        if not text:  # لا محتوى (نادر) ⇒ تسليم لطيف بدل فراغ.
            self._record(payload.concept_id, "exhausted")
            return self._exhausted_decision(
                payload,
                fallback_text="لنطبّق الفكرة على التمرين خطوة بخطوة — أيّ جزء تريد أن نبدأ به؟",
                fallback_rationale="no_content",
            )
        self._record(payload.concept_id, f"L{target}")
        return EscalationDecision(
            action="teach",
            strategy_level=target,
            text_kind=kind,
            text=text,
            rationale=f"escalate_to_L{target}",
        )

    @staticmethod
    def _record(concept_id: str, level: str) -> None:
        from app.services.skills.tutor_metrics import record_escalation

        record_escalation(concept_id, level)


_pedagogical_escalation_singleton: PedagogicalEscalationSkill | None = None


def get_pedagogical_escalation_skill() -> PedagogicalEscalationSkill:
    """يُرجع نسخة مفردة (lazy singleton)."""
    global _pedagogical_escalation_singleton
    if _pedagogical_escalation_singleton is None:
        _pedagogical_escalation_singleton = PedagogicalEscalationSkill()
    return _pedagogical_escalation_singleton


__all__ = [
    "L1_DEFINITION",
    "L2_ANALOGY",
    "L3_MICRO_SIMULATION",
    "L4_VISUAL",
    "EscalationDecision",
    "EscalationInput",
    "PedagogicalEscalationSkill",
    "get_pedagogical_escalation_skill",
]
