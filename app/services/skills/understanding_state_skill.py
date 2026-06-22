"""
UnderstandingStateSkill — محرّك حالة الفهم (Understanding State Engine، D-135).

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill».

## المسؤولية الواحدة (Learning State)
يُجيب السؤال المركزي: **«ماذا فهم الطالب فعلاً حتى الآن، وما بقي غير مفهوم؟»** — لا «ما المفهوم؟».
يُفكّك الحلّ إلى **مكوّنات معرفية (Knowledge Components)** مُشتقّة من المحرك الرمزي، ويتتبّع حالة كل
مكوّن (`not_addressed / explained / understood`)، ثم يقرّر **أصغر تدخّل يبني الفهم** (شرح/تمثيل
أعلى/تقدّم) — حتمي تماماً، صفر LLM، الأرقام من المحرك الرمزي.

## نقد المالك الرباعي (يُجسّده هذا الـ Skill)
1. **Knowledge Gap لا رقم:** `detect_gap` يُشخّص الفجوة بالمعنى (`gap_signals`) — «لماذا قسمنا على 3!»
   (بلا رقم) ⇒ `kc_factorial`. الرقم إشارة واحدة لا مستخرَج.
2. **تكرار دلالي لا حرفي:** الحالة على مستوى المكوّن (شُرح/فُهم)، لا توقيع نصّي. مكوّن مفهوم لا يُعاد.
3. **الفهم ببرهان لا صحة:** `understood` يتطلّب `evidence_markers` (إظهار مرتبط بالمكوّن) — «فهمت»
   وحدها = إقرار ضعيف لا برهان.
4. **استباقي لا تفاعلي:** مكوّن شُرح بلا فهم ⇒ **تمثيل أعلى تلقائياً** (شرح→مثال→تشبيه→تطبيق) قبل
   شكوى الطالب.

## الاستقلالية (§0.5)
- لا يستورد من Skills أخرى. حتمي تماماً (combo يُمرَّر كمدخل من المنسّق). قابل للاختبار بـ pytest.

## القياس (Prometheus)
- `cogniforge_skill_understanding_state_total{kc,state}` (counter)
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Literal

from app.services.skills.doctrine import UNDERSTANDING_STATE_DOCTRINE_VERSION

KCState = Literal["not_addressed", "explained", "understood"]
DecisionAction = Literal["explain", "re_represent", "advance", "mastered"]

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

#: علامات حيرة/شكوى تكرار — «لم أفهم *هذا*» تُصعّد التركيز الحالي لا تقفز للجبهة (نقد 4).
_CONFUSION_MARKERS: tuple[str, ...] = (
    "لم افهم",
    "لم أفهم",
    "مش فاهم",
    "ما فهمت",
    "مافهمت",
    "لا افهم",
    "لا أفهم",
    "مفهمتش",
    "مازلت لا",
    "صعب",
    "تكرر",
    "كررت",
    "نفس الجواب",
    "نفس الشرح",
    "اعد",
)


def _normalize(text: str) -> str:
    return (text or "").translate(_AR_DIGITS).strip().lower()


def _expand_comb(c: int, k: int, fav: int) -> str:
    """توسيع المضروب الحتمي ``C(c,k) = (c×…)/(k×…) = fav`` (يَنجو من حجب D-113)."""
    if k < 1 or c < k:
        return f"C({c},{k}) = {fav}"
    num = "×".join(str(c - i) for i in range(k))
    den = "×".join(str(k - i) for i in range(k))
    return f"C({c},{k}) = ({num})/({den}) = {fav}"


# ── المكوّن المعرفي (KC) ─────────────────────────────────────────────────────
@dataclass(frozen=True)
class KnowledgeComponent:
    """مكوّن معرفي: فجوته + توقيع شرحه + برهان فهمه + سُلّم تمثيلاته (حتمي من combo)."""

    kc_id: str
    title: str
    order: int  # ترتيب الجبهة التعليمية
    gap_signals: tuple[str, ...]  # إشارات الفجوة (معنى لا رقم)
    explain_markers: tuple[str, ...]  # توقيع دلالي لكشف «شُرح» في رسائل المساعد
    evidence_markers: tuple[str, ...]  # إظهار الطالب للفهم (برهان)
    representations: tuple[str, ...]  # سُلّم: شرح→مثال→تشبيه→تطبيق (أرقام مبثوقة)


@dataclass(frozen=True)
class UnderstandingDecision:
    """قرار المحرّك: نوع التدخّل + المكوّن + مستوى التمثيل + النصّ الحتمي."""

    action: DecisionAction
    kc_id: str
    representation_level: int
    text: str


# ── Prometheus metrics ─────────────────────────────────────────────────────────────
try:
    from prometheus_client import REGISTRY, Counter

    if "cogniforge_skill_understanding_state_total" in {m.name for m in REGISTRY.collect()}:
        _us_total = None
    else:
        _us_total = Counter(
            "cogniforge_skill_understanding_state_total",
            "Understanding-state decisions, labelled by kc/state.",
            ["kc", "state"],
        )

    def _record(kc: str, state: str) -> None:
        with contextlib.suppress(Exception):
            if _us_total is not None:
                _us_total.labels(kc=kc, state=state).inc()

except Exception:  # pragma: no cover

    def _record(kc: str, state: str) -> None:
        pass


class UnderstandingStateSkill:
    """
    محرّك حالة الفهم (Learning State — D-135).

    عقد دائم (لا يُكسر بدون ADR):
    1. Learning State هو المحور: القرار يُبنى على «ماذا فُهم/ما بقي» (حالة المكوّنات).
    2. KC-aware لا number-match: الفجوة تُشخَّص بالمعنى؛ المكوّنات من combo؛ الرقم إشارة واحدة.
    3. التكرار دلالي: مكوّن مفهوم لا يُعاد؛ غير مفهوم ⇒ تمثيل مختلف (سُلّم).
    4. الفهم ببرهان لا صحة: understood يتطلّب evidence_markers؛ «فهمت» وحدها ضعيفة.
    5. استباقي: شُرح بلا فهم ⇒ قفزة تمثيل تلقائية قبل شكوى الطالب.
    6. الأرقام من المحرك الرمزي حصراً (combo)؛ صفر LLM؛ يَنجو من حجب D-113.
    """

    _skill_name: str = "understanding_state"
    doctrine_version: str = UNDERSTANDING_STATE_DOCTRINE_VERSION
    _MAX_LEVEL: int = 3

    # ── A) المكوّنات المعرفية مُشتقّة من المحرك الرمزي ──────────────────────────
    def knowledge_components(self, combo) -> list[KnowledgeComponent]:
        """يُفكّك الحلّ إلى مكوّنات معرفية بأرقام combo الحتمية (لا أرقام مكتوبة يدوياً)."""
        try:
            n, k = combo.n, combo.k
            total = combo.total_combinations
            same = combo.same_group_favorable
            groups = list(combo.groups)
        except Exception:  # pragma: no cover — combo مشوَّه
            return []

        possible = [g for g in groups if getattr(g, "is_possible", False)]
        rep = max(possible, key=lambda g: g.count) if possible else None
        fav_lines = "؛ ".join(
            (
                f"{g.label}: {_expand_comb(g.count, k, g.favorable_combinations)}"
                if g.is_possible
                else f"{g.label}: مستحيلة (العدد {g.count} أقل من {k})"
            )
            for g in groups
        )
        fav_sum = " + ".join(str(g.favorable_combinations) for g in groups if g.is_possible)
        rep_c = rep.count if rep else n
        rep_fav = rep.favorable_combinations if rep else total
        rep_label = rep.label if rep else "هذا الصنف"

        kcs: list[KnowledgeComponent] = [
            KnowledgeComponent(
                kc_id="kc_event_meaning",
                title="معنى الحادثة",
                order=0,
                gap_signals=(
                    "ما الحادثة",
                    "ماذا نقصد بالحادثة",
                    "معنى الحادثة",
                    "الحادثة a",
                    "نفس اللون",
                ),
                explain_markers=("الحادثة a", "نفس اللون", "معنى الحادثة"),
                evidence_markers=(
                    "نفس اللون",
                    "الاحمر والاخضر",
                    "الأحمر والأخضر",
                    "لون واحد",
                    "احمر او اخضر",
                ),
                representations=(
                    f"الحادثة A تتحقّق حين تكون الكرات الـ{k} **من نفس اللون** — كلها حمراء، أو كلها خضراء، أو كلها بيضاء.",
                    f"تخيّل أنك سحبت {k} كرات: لو كانت كلها خضراء ⇒ تحقّقت A؛ لو اختلطت الألوان ⇒ لم تتحقّق.",
                ),
            ),
            KnowledgeComponent(
                kc_id="kc_combination",
                title="معنى التأليفة C(n,k)",
                order=1,
                gap_signals=(
                    "التأليف",
                    "التأليفات",
                    "توافيق",
                    "اخترنا",
                    "نختار",
                    "اختيار",
                    "وصلنا ل",
                    "وصلنا الى",
                    "كيف حسبنا c",
                    "ما هي c",
                ),
                explain_markers=("عدد طرق اختيار", "دون اهتمام بالترتيب", "تأليفة", "c("),
                evidence_markers=(
                    "دون ترتيب",
                    "بدون ترتيب",
                    "لا يهم الترتيب",
                    "نختار 3 من",
                    "اختيار مجموعة",
                ),
                representations=(
                    f"C(n,k) = **عدد طرق اختيار k عناصر من n دون اهتمام بالترتيب**. مثلاً {rep_label}: {_expand_comb(rep_c, k, rep_fav)}.",
                    f"خذ {rep_label} (عددها {rep_c}): نختار {k} منها — كل اختيار **مجموعة** من {k} كرات بصرف النظر عن ترتيب سحبها: {_expand_comb(rep_c, k, rep_fav)}.",
                    f"تشبيه: اختيار {k} طلاب من {rep_c} للجنة — لا يهمّ من اخترتَ أولاً، المهمّ مَن في اللجنة. هذا هو C({rep_c},{k}).",
                    f"جرّب أنت: كم طريقة لاختيار 2 من 3؟ (الجواب C(3,2)). ثم طبّق نفس الفكرة على {rep_label}.",
                ),
            ),
            KnowledgeComponent(
                kc_id="kc_factorial",
                title="لماذا نقسم على k!",
                order=2,
                gap_signals=(
                    "قسمنا",
                    "نقسم",
                    "القسمة",
                    "المقام",
                    "الترتيب",
                    "لا نضرب مباشرة",
                    "لماذا نقسم",
                    "3!",
                    "العاملي",
                    "مضروب",
                ),
                explain_markers=("نقسم على", "الترتيب لا يهم", "المقام", "تُعدّ مرة واحدة"),
                evidence_markers=(
                    "الترتيب لا يهم",
                    "نفس المجموعة",
                    "تُعدّ مرة",
                    "مكررة",
                    "بدون ترتيب",
                ),
                representations=(
                    f"نقسم على k! (أي {'×'.join(str(k - i) for i in range(k))}) لأن **الترتيب لا يهمّ**: المجموعة الواحدة لا نريد عدّها أكثر من مرة.",
                    "البسط (الضرب التنازلي) يَعُدّ المجموعة الواحدة عدّة مرات حسب ترتيب سحبها؛ القسمة على k! تُلغي هذا التكرار.",
                    "تشبيه: لو رتّبت 3 أحرف {أ،ب،ج} تحصل على 6 ترتيبات، لكنها **مجموعة واحدة**. لذلك نقسم على 6 = 3!.",
                ),
            ),
            KnowledgeComponent(
                kc_id="kc_favorable_cases",
                title="عدّ الحالات الملائمة",
                order=3,
                gap_signals=(
                    "الحالات الملائمة",
                    "الملائمة",
                    "نجمع",
                    "المجموع",
                    "الحالات المناسبة",
                    "عدد الحالات",
                ),
                explain_markers=("الحالات الملائمة", "نجمع الحالات", "لكل لون"),
                evidence_markers=(
                    "نجمع الالوان",
                    "نجمع كل لون",
                    "اجمع الممكنة",
                    "حمراء زائد خضراء",
                ),
                representations=(
                    f"نعدّ تأليفات «نفس اللون» لكل صنف ثم نجمع الممكنة فقط: {fav_lines}؛ المجموع: {fav_sum} = {same}.",
                    f"الأبيض مستحيل (عدده أقل من {k})، فنجمع الأحمر والأخضر فقط: {fav_sum} = {same} حالة ملائمة.",
                ),
            ),
            KnowledgeComponent(
                kc_id="kc_sample_space",
                title="فضاء العيّنة",
                order=4,
                gap_signals=(
                    "كل الطرق",
                    "فضاء العينة",
                    "الفضاء",
                    "العدد الكلي",
                    "الكلي",
                    "مجموع الطرق",
                ),
                explain_markers=("كل الطرق", "فضاء العينة", "العدد الكلي"),
                evidence_markers=("كل الطرق", "c(11", "اختيار 3 من 11", "الفضاء الكلي"),
                representations=(
                    f"فضاء العيّنة = **كل طرق سحب {k} من {n}** دون ترتيب: {_expand_comb(n, k, total)}.",
                    f"هذا المقام في الاحتمال: مجموع كل النتائج الممكنة المتساوية الإمكان = {_expand_comb(n, k, total)}.",
                ),
            ),
            KnowledgeComponent(
                kc_id="kc_ratio",
                title="تكوين الاحتمال",
                order=5,
                # D-137: حُذفت «الاحتمال» المجرّدة — كانت تُطابق كل سؤال احتمالات (حتى
                # «ما هو الاحتمال الشرطي») فيختطف D-135 ويبثّ «14 من 165». الإشارات الآن
                # خاصة بـ**خطوة تكوين النسبة** لا كلمة مفهوم عامة.
                gap_signals=(
                    "النسبة",
                    "كيف نكون الاحتمال",
                    "كيف نكوّن الاحتمال",
                    "البسط على المقام",
                    "نقسم البسط",
                ),
                explain_markers=("الحالات الملائمة", "كل الطرق", "احتمال الحادثة"),
                evidence_markers=("ملائمة على الكلي", "البسط على المقام", "نقسم الملائمة"),
                representations=(
                    f"الاحتمال = (الحالات الملائمة) ÷ (كل الطرق) = {same} من {total}.",
                ),
            ),
        ]
        return kcs

    # ── B) مُشخِّص الفجوة المعرفية (semantic, not number) ──────────────────────
    def detect_gap(self, question: str, kcs: list[KnowledgeComponent]) -> KnowledgeComponent | None:
        """يُطابق نية السؤال بـ gap_signals للمكوّن (معنى لا رقم). None إن لا فجوة صريحة."""
        norm = _normalize(question)
        if not norm:
            return None
        best: KnowledgeComponent | None = None
        best_hits = 0
        for kc in kcs:
            hits = sum(1 for s in kc.gap_signals if _normalize(s) in norm)
            if hits > best_hits:
                best_hits, best = hits, kc
        return best if best_hits > 0 else None

    def _evidence_kc(
        self, message: str, kcs: list[KnowledgeComponent]
    ) -> KnowledgeComponent | None:
        """أي مكوّن يُظهر هذا النصّ برهان فهمه؟ (إظهار مرتبط، لا «فهمت» مجرّدة)."""
        norm = _normalize(message)
        if not norm:
            return None
        for kc in kcs:
            if any(_normalize(e) in norm for e in kc.evidence_markers):
                return kc
        return None

    # ── C) حالة الفهم لكل مكوّن (semantic + evidence) ──────────────────────────
    def understanding_state(
        self, history: list[dict[str, str]] | None, kcs: list[KnowledgeComponent]
    ) -> dict[str, KCState]:
        """حالة كل مكوّن من المحادثة: explained (شُرح) / understood (بُرهن) / not_addressed."""
        assistant_text = " ".join(
            _normalize(str(m.get("content", "")))
            for m in (history or [])
            if isinstance(m, dict) and m.get("role") == "assistant"
        )
        user_text = " ".join(
            _normalize(str(m.get("content", "")))
            for m in (history or [])
            if isinstance(m, dict) and m.get("role") == "user"
        )
        states: dict[str, KCState] = {}
        for kc in kcs:
            explained = any(_normalize(m) in assistant_text for m in kc.explain_markers)
            has_evidence = any(_normalize(e) in user_text for e in kc.evidence_markers)
            if explained and has_evidence:
                states[kc.kc_id] = "understood"
            elif explained:
                states[kc.kc_id] = "explained"
            else:
                states[kc.kc_id] = "not_addressed"
        return states

    def _explain_count(self, kc: KnowledgeComponent, history: list[dict[str, str]] | None) -> int:
        """كم مرّة شُرح هذا المكوّن (لتصعيد التمثيل الاستباقي)."""
        count = 0
        for m in history or []:
            if not isinstance(m, dict) or m.get("role") != "assistant":
                continue
            low = _normalize(str(m.get("content", "")))
            if any(_normalize(mk) in low for mk in kc.explain_markers):
                count += 1
        return count

    def _next_unmastered(
        self, kcs: list[KnowledgeComponent], states: dict[str, KCState]
    ) -> KnowledgeComponent | None:
        """الجبهة التعليمية: أوّل مكوّن غير مفهوم بالترتيب."""
        for kc in sorted(kcs, key=lambda c: c.order):
            if states.get(kc.kc_id) != "understood":
                return kc
        return None

    def _current_focus_kc(
        self, kcs: list[KnowledgeComponent], history: list[dict[str, str]] | None
    ) -> KnowledgeComponent | None:
        """المكوّن الذي خاطبته **آخر** رسالة مساعد (التركيز الحالي).

        «لم أفهم» تعني «لم أفهم *هذا*» (التركيز الحالي) لا «ابدأ من البداية» — فنُصعّد تمثيله،
        لا نقفز للجبهة. None إن لم تخاطب آخر رسالة مساعد مكوّناً معروفاً.
        """
        for m in reversed(history or []):
            if not isinstance(m, dict) or m.get("role") != "assistant":
                continue
            raw = str(m.get("content", ""))
            # D-137 (حارس تسرّب التركيز): إذا كانت آخر رسالة مساعد **مثالاً/تعريفاً لمفهوم**
            # (لا شرح خطوة حساب)، فلا تقفل التركيز عليها — كلمات مثل «نفس اللون» العابرة في
            # مثال الاحتمال الشرطي كانت تقفل خطأً على kc_event_meaning ⇒ «لم أفهم» ⇒ الحادثة A.
            if any(mk in raw for mk in ("## مثال", "مثال ملموس", "مثال آخر", "## ماذا نقصد")):
                return None
            low = _normalize(raw)
            for kc in kcs:
                if any(_normalize(mk) in low for mk in kc.explain_markers):
                    return kc
            return None  # آخر رسالة مساعد لم تخاطب مكوّناً معروفاً
        return None

    def _representation(self, kc: KnowledgeComponent, level: int) -> str:
        """نصّ التمثيل عند المستوى (clamp على السُّلّم المتاح)."""
        reps = kc.representations
        idx = max(0, min(level, len(reps) - 1))
        return reps[idx]

    # ── E) القرار ─────────────────────────────────────────────────────────────
    def decide(
        self,
        *,
        question: str,
        history: list[dict[str, str]] | None,
        combo,
        intent: str | None = None,
        frustration: str | None = None,
    ) -> UnderstandingDecision | None:
        """يقرّر أصغر تدخّل يبني الفهم — حتمي. None لغير الاحتمالات/تعذّر."""
        kcs = self.knowledge_components(combo)
        if not kcs:
            return None
        states = self.understanding_state(history, kcs)

        # A) برهان فهم في الرسالة الحالية لمكوّن **سبق شرحه** ⇒ اعتراف + تقدّم (نقد 3).
        # يفوز على تفسير «فجوة» إلا إذا سأل الطالب عن مكوّن **مختلف** صراحةً (gap ≠ المُبرهَن).
        gap = self.detect_gap(question, kcs)
        answered = self._evidence_kc(question, kcs)
        if (
            answered is not None
            and (gap is None or gap.kc_id == answered.kc_id)
            and states.get(answered.kc_id) in ("explained", "understood")
        ):
            states[answered.kc_id] = "understood"
            _record(answered.kc_id, "understood")
            nxt = self._next_unmastered(kcs, states)
            if nxt is None:
                return UnderstandingDecision(
                    action="mastered",
                    kc_id=answered.kc_id,
                    representation_level=0,
                    text="أحسنت ✅ — لقد بنيتَ كل خطوات هذا الجزء بنفسك. أنت جاهز للجزء التالي.",
                )
            return UnderstandingDecision(
                action="advance",
                kc_id=nxt.kc_id,
                representation_level=0,
                text=f"أحسنت ✅ — فهمتَ هذه النقطة. ننتقل الآن إلى **{nxt.title}**:\n\n{self._representation(nxt, 0)}",
            )

        # B) فجوة صريحة ⇒ ذلك المكوّن؛ وإلا: حيرة على التركيز الحالي ⇒ صعّده (لا تقفز للجبهة).
        # D-136 (كبح الاختطاف): لا تتقدّم في المسار إلا إذا كنا فعلاً وسطه (مكوّن مسار شُرح already).
        # سؤال عن مفهوم خارج مسار نفس-اللون (product_even/expected_value…) ⇒ None ⇒ يُسلَّم للمعالج
        # الواعي بالمفهوم بدل اختطافه إلى مثال الحادثة A الافتراضي.
        target = gap
        if target is None:
            _confused = any(_normalize(c) in _normalize(question) for c in _CONFUSION_MARKERS)
            focus = self._current_focus_kc(kcs, history) if _confused else None
            if focus is not None:
                target = focus
            else:
                on_path = any(s in ("explained", "understood") for s in states.values())
                target = self._next_unmastered(kcs, states) if on_path else None
        if target is None:
            return None
        st = states.get(target.kc_id, "not_addressed")
        if st == "understood":
            nxt = self._next_unmastered(kcs, states)
            if nxt is None:
                _record(target.kc_id, "understood")
                return UnderstandingDecision(
                    action="mastered",
                    kc_id=target.kc_id,
                    representation_level=0,
                    text="أحسنت ✅ — هذه النقطة واضحة لديك. أتقنتَ كل خطوات هذا الجزء.",
                )
            target = nxt
            st = states.get(target.kc_id, "not_addressed")

        # D) تمثيل استباقي: شُرح بلا فهم ⇒ تمثيل أعلى (لا تكرار)؛ غير مشروح ⇒ تمثيل 0.
        attempts = self._explain_count(target, history)
        level = min(attempts, self._MAX_LEVEL)
        action: DecisionAction = "explain" if attempts == 0 else "re_represent"
        _record(target.kc_id, st)
        return UnderstandingDecision(
            action=action,
            kc_id=target.kc_id,
            representation_level=level,
            text=self._representation(target, level),
        )


_understanding_state_singleton: UnderstandingStateSkill | None = None


def get_understanding_state_skill() -> UnderstandingStateSkill:
    """يُرجع نسخة مفردة (lazy singleton)."""
    global _understanding_state_singleton
    if _understanding_state_singleton is None:
        _understanding_state_singleton = UnderstandingStateSkill()
    return _understanding_state_singleton


__all__ = [
    "KCState",
    "KnowledgeComponent",
    "UnderstandingDecision",
    "UnderstandingStateSkill",
    "get_understanding_state_skill",
]
