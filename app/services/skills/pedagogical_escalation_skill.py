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

import re

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill
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
    """تطبيع عام للمقارنة (علامات الفهم/الأرقام) — **يطوي** المسافات (D-186).

    كان يكتفي بـ`strip()`، فسطران متطابقان بفارق مسافة مزدوجة لا يتطابقان. لكشف
    «هل بُثّت هذه الرُّتبة؟» استعمل `_squash` لا هذه: هناك تُحذَف المسافات حذفاً،
    لأن مُنسِّق الكتابة يحذفها ولا يكتفي بطيّها.
    """
    return re.sub(r"\s+", " ", (text or "").translate(_AR_DIGITS)).strip().lower()


def _squash(text: str) -> str:
    """تطبيع **بلا أي مسافة** — لمقارنة «هل بُثّت هذه الرُّتبة؟» حصراً.

    مُنسِّق الكتابة (typing effect) لا يكتفي بطيّ المسافات بل **يحذفها** أحياناً
    (`$C_{n}^{k}$ (ويُكتب` ⇒ `$C_{n}^{k}$(ويُكتب`)، فأي مقارنة تحترم المسافات تفشل.
    وفشلها ليس تجميلياً: الرُّتبة تبدو غير مُسلَّمة ⇒ تُعاد حرفياً ⇒ يلتقطها حارس
    التكرار ⇒ يستبدلها بـ«الحل الكامل» فيتسرّب حلّ التمرين (ISS-139).

    مقصور على كشف التسليم عمداً — تعميمه على مطابقة العلامات يخلق مطابقات كاذبة
    عبر حدود الكلمات.
    """
    return re.sub(r"\s+", "", (text or "").translate(_AR_DIGITS)).lower()


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
    #: D-159 (WP-B): الرُّتب المُسلَّمة من الحالة الدائمة (tutor_state.kc_progress.escalation_levels)
    #: — FSM حقيقي يَنجو من نافذة الـ50 رسالة وإعادة تشغيل العملية. None ⇒ مسح النصّ وحده.
    delivered_levels: list[int] | None = None
    #: ISS-149: نصّ الطالب **في هذا الدور**، صريحاً لا مُستنتَجاً من ذيل التاريخ.
    #:
    #: المونوليث يحفظ رسالة الطالب **قبل** بناء الدور (§6.5)، فذيل `history` في
    #: الإنتاج هو الرسالة الحاضرة بينما هو الرسالة **السابقة** في مُشغِّل العقود.
    #: أي أن «الحاضر» المُستنتَج يعني شيئين مختلفين في بيئتين — وقرارُ الإتقان
    #: أخطرُ من أن يُبنى على استنتاج. الصريح يحسم، والذيل يبقى تدهوراً رشيقاً.
    question: str = ""


class EscalationDecision(RobustBaseModel):
    """قرار المصفوفة: الإجراء + الرُّتبة + النصّ النهائي الحتمي."""

    action: str  # mastered | target_misconception | teach | exhausted
    strategy_level: int = 0  # 0..3
    text_kind: str = ""  # ack | intervention | definition | example | micro_simulation | handoff
    text: str = ""
    rationale: str = ""


class PedagogicalEscalationSkill(BaseSkill):
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
    name = "pedagogical_escalation"

    def run(self, payload):
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`decide`."""
        return self.decide(payload)

    doctrine_version: str = PEDAGOGICAL_ESCALATION_DOCTRINE_VERSION

    # ── إشارات الدخل ──────────────────────────────────────────────────────────
    @staticmethod
    def _last_student_text(history: list[dict[str, str]] | None) -> str:
        for msg in reversed(history or []):
            if isinstance(msg, dict) and msg.get("role") == "user":
                return str(msg.get("content", ""))
        return ""

    @staticmethod
    def _is_confusion_signal(text: str) -> bool:
        """هل النصّ إشارة حيرة؟ — من `shared/intent` حصراً (D-186: مصدرٌ واحد)."""
        try:
            from shared.intent import matches

            return matches(text, "confusion")
        except Exception:  # pragma: no cover - fail-safe
            return False

    @staticmethod
    def _is_question_not_answer(text: str) -> bool:
        """هل النصّ سؤالٌ لا تقرير؟ — بوّابة الفعل الكلامي القائمة (D-162).

        يُعاد استعمال المُصنِّف نفسه الذي يميّز السؤال من الإجابة في المحرّك الرمزي،
        لا نسخةٌ سادسة تتفرّق عنه بأوّل تعديل (D-186·L6 / D-206·L6).
        """
        try:
            from app.services.skills.probability_brain.cognitive_verification import (
                CognitiveVerificationMixin,
            )

            return CognitiveVerificationMixin._is_question_not_answer(text)
        except Exception:  # pragma: no cover - fail-safe
            return False

    def _current_student_text(self, payload: EscalationInput) -> str:
        """نصّ الطالب في هذا الدور: الصريح أوّلاً، ثمّ ذيل التاريخ تدهوراً رشيقاً."""
        return (payload.question or "").strip() or self._last_student_text(payload.history)

    def _has_understanding_evidence(self, payload: EscalationInput) -> bool:
        """Understanding Signal: هل أظهر الطالب **آلية فهم المفهوم** الآن؟

        ISS-149 — ثلاثة قيود، كلٌّ منها وحده كان يكفي لمنع الكارثة:

        1. **الحاضر لا الماضي.** كان المسح يشمل آخر ٦ رسائل طالب، فأثرٌ من دورٍ
           سابق يهزم إشارةَ هذا الدور. أثرُ الماضي عُمِل به حين وقع؛ وذاكرةُ ما
           بين الأدوار موطنها `delivered_levels` الدائمة (D-159) لا إعادةُ الحكم.
        2. **الحيرة المُعلَنة تُبطِل البرهان.** طالبٌ يقول «لم أفهم» لا يُهنَّأ
           مهما قال قبل قليل — وإلّا هُنِّئ على حيرته وسُجِّل إتقانٌ لم يحدث.
        3. **السؤال ليس برهاناً.** «كيف نفرق بين **البسط** و المقام؟» كانت تُطابِق
           المؤشّر «البسط» فتُقرأ برهانَ فهمه: الطالبُ سأل عن المصطلح فحُسِب أنّه
           أتقنه. بوّابة الفعل الكلامي (D-158/D-162) كانت مطبَّقة على الإجابات
           وحدها ولم تُطبَّق قطّ على مؤشّرات الفهم.

        القيد الثاني لا يُلغي القيد الأول من عقد D-138: رسالةٌ تُظهر الآلية فعلاً
        («اها فهمت، تقلص الفضاء فنقسم على عدد اقل») تبقى برهاناً — العبرة بما
        **قاله الطالب الآن**، لا بلافتة النيّة ولا بما قاله قبل ثلاثة أدوار.
        """
        if not payload.evidence_markers:
            return False
        text = self._current_student_text(payload)
        if not text:
            return False
        if self._is_confusion_signal(text) or self._is_question_not_answer(text):
            return False
        low = _norm(text)
        return any(_norm(m) in low for m in payload.evidence_markers)

    def _levels_delivered(self, payload: EscalationInput) -> set[int]:
        """الرُّتب المُسلَّمة لهذا المفهوم — الحالة الدائمة (D-159) ∪ مسح النصّ (شبكة أمان).

        D-159 (WP-B): `delivered_levels` من `tutor_state.kc_progress` هي ذاكرة FSM
        الدائمة (تَنجو من نافذة الـ50 رسالة وإعادة تشغيل العملية — كان مسح النصّ وحده
        يتبخر خارجهما فيتكرّر التعريف/المثال). مسح نصّ المساعد يبقى fallback للأدوار
        السابقة على التخزين — **الاتحاد** يمنع تكرار الرُّتبة من أي مصدر.
        """
        delivered: set[int] = set()
        for lvl in payload.delivered_levels or []:
            if isinstance(lvl, int) and L1_DEFINITION <= lvl <= L4_VISUAL:
                delivered.add(lvl)
        # D-186: المقارنة بلا مسافات — مُنسِّق الكتابة يحذف مسافات فتفشل المطابقة الحرفية.
        assistant_text = "".join(
            _squash(str(m.get("content", "")))
            for m in (payload.history or [])
            if isinstance(m, dict) and m.get("role") == "assistant"
        )
        if not assistant_text:
            return delivered
        if payload.definition and _squash(payload.definition)[:_FRAGMENT_LEN] in assistant_text:
            delivered.add(L1_DEFINITION)
        if payload.example and _squash(payload.example)[:_FRAGMENT_LEN] in assistant_text:
            delivered.add(L2_ANALOGY)
        if payload.micro_sim and _squash(payload.micro_sim)[:_FRAGMENT_LEN] in assistant_text:
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

    def _render(
        self, level: int, payload: EscalationInput, delivered: set[int] | None = None
    ) -> tuple[str, str]:
        """يبني نصّ الرُّتبة الحتمي. يُنزِّل الرُّتبة إن غاب محتواها — **وليس** إن سُلِّمت.

        D-186 (ISS-139): كان التنزّل أعمى، فرُتبة عليا بلا محتوى (لا محاكاة مصغّرة
        لهذا المفهوم) تنزل إلى المثال **المُسلَّم أصلاً** فيُعاد حرفياً. عندها يلتقط
        حارسُ التكرار الإعادةَ ويستبدلها بـ«الحل الكامل خطوة بخطوة» — فينتهي «لم أفهم»
        بتسريب حلّ التمرين كاملاً (165 · 4 · 10 · 14) للطالب.

        الآن: ما سُلِّم لا يُعاد. وإن لم يبقَ جديد ⇒ `("", "")` فيتولّاها
        `_exhausted_decision` بسؤال تطبيق على التمرين (D-147) — تقدّمٌ بلا كشف.
        """
        done = delivered or set()
        for lvl in (level, level - 1, level - 2):
            if lvl in done:
                continue
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
        if self._has_understanding_evidence(payload):
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
        # (3) قانون «التعريف قبل المثال» (D-186 — ISS-139).
        #
        # سؤال تعريفي صريح («ماذا يقصد بالحرف C») لا يُجاب **أبداً** بمثالٍ عارٍ. كان
        # حارس التكرار في `_calibrate` يتخطّى الرُّتبة المُسلَّمة دائماً، فسؤالٌ تعريفي
        # مُعاد يقفز فوق L1 ويُرجع «## مثال ملموس» وحده — أي أن الطالب لم يُخبَر أصلاً
        # بما يعنيه الرمز الذي سأل عنه. (يقع هذا **حتى مع** تصنيف نيّة صحيح، فتوحيد
        # قوائم العلامات وحده ما كان ليكفي.)
        #
        # وإعادة السؤال ليست إشارة «تقدَّم في السُّلّم» بل إشارة **أن التعريف لم يصل**:
        # فنُعيده مُثرًى بالمثال معاً — لا نتخطّاه.
        if payload.intent == "definition" and payload.definition:
            head = f"## {payload.title}\n\n" if payload.title else ""
            text = f"{head}{payload.definition}"
            level = L1_DEFINITION
            # التعريف يُعاد دائماً (هو ما سُئل عنه)، **مع الرُّتبة التالية غير المُسلَّمة**
            # — فالسؤال المُعاد لا يُجاب بنسخةٍ حرفية من الدور السابق («صفر تكرار حرفي»).
            delivered_now = self._levels_delivered(payload)
            if L1_DEFINITION in delivered_now:
                extra, kind = self._render(L3_MICRO_SIMULATION, payload, delivered_now)
                if extra:
                    text += f"\n\n{extra}"
                    level = L3_MICRO_SIMULATION if kind == "micro_simulation" else L2_ANALOGY
            self._record(payload.concept_id, f"L{level}")
            return EscalationDecision(
                action="teach",
                strategy_level=level,
                text_kind="definition",
                text=text,
                rationale="definition_before_example",
            )
        # (4) التصعيد المُعايَر (ذاكرة + قدرة + صعوبة).
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
        text, kind = self._render(target, payload, delivered)
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
