"""
KC-Progress Structured Schema (D-159) — المخطط المُهيكَل لتقدّم المكوّنات المعرفية.

فلسفة المالك الحاكمة: «الخوارزمية بلا هيكل بيانات صحيح = محرك فيراري على دراجة خشبية».
قبل D-159 كان `tutor_state.kc_progress` JSON حرّاً يُبنى يدوياً في `_cognitive_turn`
(dict literals مبعثرة) — أي إغفال مفتاح أو خطأ إملائي يصير حالة فاسدة صامتة تُخزَّن
في الإنتاج. هذا الملف هو **المصدر الوحيد لشكل الحالة المعرفية الدائمة**.

## لماذا stdlib dataclasses (لا pydantic)
- حتمي 100%، صفر تبعيات — قابل للاختبار standalone في أي بيئة (نمط `MisconceptionNode`).
- `parse_kc_entry` متسامح (fail-open): أي dict قديم/ناقص يُقرأ بأمان — التوافق الخلفي
  مع كل صفوف `tutor_state` المخزّنة قبل D-159 مضمون بالبناء.
- `to_dict()` يحافظ على نفس مفاتيح الحمولة القديمة (D-158) بايتاً-ببايت؛ المفاتيح
  الجديدة (`escalation_levels`) تُكتب **فقط عند وجود قيمة** — فلا يتغيّر شكل الصفوف
  القائمة إلا حين تُستخدم الميزة الجديدة فعلاً.

## العقد (D-159 — لا يُكسر بدون ADR)
1. كل قراءة/كتابة لمدخل مكوّن في `kc_progress` تمرّ عبر `parse_kc_entry`/`to_dict` —
   لا dict literals يدوية في مسارات القرار.
2. `state ∈ {not_addressed, explained, understood}` و `evidence ∈ {none, weak, verified}` —
   أي قيمة خارجها تُطبَّع للافتراض الآمن (لا استثناء، fail-open).
3. مفتاح `_pending` (السؤال المعلّق عبر الأدوار) يُدار حصراً عبر `pending_of`/`make_pending`.
4. `escalation_levels` (WP-B/D-159) هي ذاكرة FSM التصعيد الدائمة لكل مفهوم — تحلّ محلّ
   مسح نصّ التاريخ (الذي يتبخر خارج نافذة الـ50 رسالة وعند إعادة تشغيل العملية).
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: حالات المكوّن المعرفي المسموحة (أي قيمة أخرى تُطبَّع إلى not_addressed).
KC_STATES: tuple[str, ...] = ("not_addressed", "explained", "understood")
#: مستويات الدليل المسموحة (أي قيمة أخرى تُطبَّع إلى none).
KC_EVIDENCE: tuple[str, ...] = ("none", "weak", "verified")
#: مفتاح السؤال المعلّق داخل kc_progress (يُدار عبر pending_of/make_pending حصراً).
PENDING_KEY: str = "_pending"


@dataclass
class KCEntry:
    """مدخل مكوّن معرفي واحد داخل `tutor_state.kc_progress` — الحالة الدائمة النمطية."""

    state: str = "not_addressed"
    attempts: int = 0
    evidence: str = "none"
    difficulty: float = 0.0
    representations_delivered: list[str] = field(default_factory=list)
    last_emitted_hash: str = ""
    updated_turn: int = 0
    #: D-159 (WP-B): رُتب المصفوفة التصعيدية المُسلَّمة لهذا المفهوم (مثل ["L1","L2"]) —
    #: FSM دائم يحلّ محلّ إعادة البناء من مسح نصّ التاريخ.
    escalation_levels: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """الحمولة القابلة للتخزين — مطابقة لمفاتيح D-158؛ الجديد يُكتب فقط عند وجوده."""
        payload: dict = {
            "state": self.state,
            "attempts": int(self.attempts),
            "evidence": self.evidence,
            "difficulty": float(self.difficulty),
            "representations_delivered": list(self.representations_delivered),
            "last_emitted_hash": self.last_emitted_hash,
            "updated_turn": int(self.updated_turn),
        }
        if self.escalation_levels:
            payload["escalation_levels"] = list(self.escalation_levels)
        return payload

    # ── سلوكيات الحالة (تحوّلات FSM صغيرة صريحة بدل تعديل حقول متناثر) ────────────
    def mark_delivered(self, step: str) -> None:
        """يسجّل خطوة/تمثيلاً سُلِّم — لا يتكرر أبداً (قاعدة D-158-b)."""
        if step and step not in self.representations_delivered:
            self.representations_delivered.append(step)

    def mark_escalation(self, level: str) -> None:
        """يسجّل رُتبة تصعيد سُلِّمت (L1/L2/L3) — ذاكرة FSM الدائمة (WP-B)."""
        if level and level not in self.escalation_levels:
            self.escalation_levels.append(level)


def _coerce_str(value: object, allowed: tuple[str, ...], default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def parse_kc_entry(raw: object) -> KCEntry:
    """يقرأ مدخلاً مخزّناً (أو أي شيء) إلى `KCEntry` سليم — fail-open مطلق.

    dict قديم (قبل D-159) بلا `escalation_levels` يُقرأ بأمان؛ قيم فاسدة تُطبَّع
    للافتراضات؛ أي نوع غير dict ⇒ مدخل جديد نظيف.
    """
    if not isinstance(raw, dict):
        return KCEntry()
    try:
        reps = raw.get("representations_delivered")
        levels = raw.get("escalation_levels")
        return KCEntry(
            state=_coerce_str(raw.get("state"), KC_STATES, "not_addressed"),
            attempts=max(0, int(raw.get("attempts") or 0)),
            evidence=_coerce_str(raw.get("evidence"), KC_EVIDENCE, "none"),
            difficulty=max(0.0, min(1.0, float(raw.get("difficulty") or 0.0))),
            representations_delivered=[str(r) for r in reps if r] if isinstance(reps, list) else [],
            last_emitted_hash=str(raw.get("last_emitted_hash") or ""),
            updated_turn=max(0, int(raw.get("updated_turn") or 0)),
            escalation_levels=[str(v) for v in levels if v] if isinstance(levels, list) else [],
        )
    except Exception:  # pragma: no cover - fail-safe (state must never abort a turn)
        return KCEntry()


def pending_of(kc_progress: object) -> tuple[str, str] | None:
    """يقرأ السؤال المعلّق `(kc_id, step_key)` من kc_progress — None إن غاب/فسد."""
    if not isinstance(kc_progress, dict):
        return None
    pending = kc_progress.get(PENDING_KEY)
    if not isinstance(pending, dict):
        return None
    kc_id = pending.get("kc_id")
    step_key = pending.get("step_key")
    if isinstance(kc_id, str) and kc_id and isinstance(step_key, str) and step_key:
        return kc_id, step_key
    return None


def make_pending(kc_id: str, step_key: str) -> dict:
    """يبني حمولة `_pending` الموحَّدة (الشكل الوحيد المسموح تخزينه)."""
    return {"kc_id": kc_id, "step_key": step_key}


def escalation_levels_of(kc_progress: object, concept_id: str) -> list[int]:
    """رُتب التصعيد الدائمة لمفهومٍ ما كأعداد صحيحة (["L1","L3"] ⇒ [1, 3]) — fail-open.

    WP-B (D-159): هذه هي القراءة الموحَّدة التي تُغذّي `EscalationInput.delivered_levels`
    فيَنجو FSM التصعيد من نافذة التاريخ وإعادة تشغيل العملية.
    """
    if not isinstance(kc_progress, dict):
        return []
    entry = parse_kc_entry(kc_progress.get(concept_id))
    levels: list[int] = []
    for token in entry.escalation_levels:
        if isinstance(token, str) and token.startswith("L"):
            try:
                levels.append(int(token[1:]))
            except ValueError:
                continue
    return sorted(set(levels))


__all__ = [
    "KC_EVIDENCE",
    "KC_STATES",
    "PENDING_KEY",
    "KCEntry",
    "escalation_levels_of",
    "make_pending",
    "parse_kc_entry",
    "pending_of",
]
