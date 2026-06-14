r"""AnswerRedactionSkill — الحارس الحتمي الأخير ضد كشف الإجابة النهائية (D-113).

كارثة «وَهْم الإتقان» (ISS-115): كشف الحلّ الكامل (P(A)=14/165، C(11,3)=165،
E(X)=1.73، $$\boxed{...}$$) يُدمّر التعلّم. الدفاع الأول هو الـ doctrine السقراطي
(`EXPLANATION_DOCTRINE` v3.0.0) + إرسال أسئلة-فقط للـ LLM. لكن النماذج المجانية قد
تخترع/تخمّن نتيجةً نهائية. هذا الـ Skill هو **شبكة الأمان الحتمية**: يحذف أي نتيجة
نهائية صريحة قبل وصولها للطالب — بلا LLM، بلا عشوائية، قابل للاختبار بـ pytest.

التصميم (يحترم `ANSWER_REDACTION_DOCTRINE`):
- `\boxed{X}` → `\boxed{?}` (يُبقي الصندوق فارغاً يدعو الطالب للحساب — أبلغ من الحذف).
- نتائج الاحتمال/التوافيق/الأمل الصريحة `P(...)=`، `E(...)=`، `C(...)=<عدد>` → يُحجب
  الطرف الأيمن بـ «؟» (تبقى البنية، يختفي الجواب).
- أسطر الخلاصة «إذن/ومنه/النتيجة ... = <عدد>» → يُحجب العدد الختامي.
- أسطر العلامات الصريحة «الإجابة النهائية:/النتيجة النهائية:» → يُحجب ما بعدها.
- **نطاق ضيّق:** لا يلمس الصيغ التعليمية الوسيطة (`نستخدم C(n,k)`، تعريف القانون،
  RHS رمزي مثل `C(n,k) = n!/(k!(n-k)!)`) — فقط النتائج العددية الختامية الصريحة.
- **fail-open مطلق:** أي استثناء ⇒ النص كما هو (لا يكسر دور الطالب).
"""

from __future__ import annotations

import contextlib
import logging
import re
import time

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.doctrine import ANSWER_REDACTION_DOCTRINE_VERSION

logger = logging.getLogger("cogniforge.skills.answer_redaction")

DOCTRINE_VERSION = ANSWER_REDACTION_DOCTRINE_VERSION

#: بديل الحجب داخل الرياضيات (يُبقي LaTeX صالحاً).
_MATH_MASK = "?"
#: بديل الحجب في النص العادي (دعوة سقراطية موجزة).
_PROSE_MASK = "؟"

# قيمة عددية ختامية: عدد/كسر/عشري/نسبة مئوية (يسمح بمسافات داخلية بسيطة).
_NUM = r"[-+]?\d[\d.,]*\s*(?:/\s*\d[\d.,]*)?\s*%?"

# نتيجة احتمال/توافيق/أمل صريحة: P(...)=، E(...)=، C(...)=<عدد ختامي فقط>.
# RHS يجب أن يكون عدداً صرفاً (لا صيغة رمزية مثل n!/(k!...)) لتجنّب false-positive.
_FINAL_RESULT_RE = re.compile(
    r"(?P<lhs>[PECpec]\s*(?:_?[A-Za-z])?\s*\([^)\n]{0,60}\)\s*=\s*)(?P<rhs>" + _NUM + r")"
)

# خلاصة لفظية تنتهي بعدد: «إذن/ومنه/النتيجة/الجواب ... = <عدد>».
_CONCLUSION_RE = re.compile(
    r"(?P<lhs>(?:إذن|ومنه|النتيجة|الجواب|فإن)[^=\n]{0,90}=\s*)(?P<rhs>" + _NUM + r")"
)

# أسطر العلامات الصريحة للنتيجة النهائية (يُحجب ما بعد النقطتين/المسافة).
_RESULT_MARKER_RE = re.compile(
    r"(?P<lbl>(?:الإجابة|النتيجة|الجواب)\s*(?:النهائية|النهائي)\s*[:：]?\s*)(?P<val>.+)"
)


def _strip_boxed(text: str) -> tuple[str, int]:
    r"""يستبدل محتوى كل `\boxed{...}` بـ `?` (مع موازنة الأقواس). يُبقي الصندوق."""
    out: list[str] = []
    i = 0
    n = len(text)
    count = 0
    while i < n:
        idx = text.find("\\boxed", i)
        if idx == -1:
            out.append(text[i:])
            break
        out.append(text[i:idx])
        j = idx + len("\\boxed")
        while j < n and text[j] in " \t":
            j += 1
        if j < n and text[j] == "{":
            depth = 0
            k = j
            while k < n:
                if text[k] == "{":
                    depth += 1
                elif text[k] == "}":
                    depth -= 1
                    if depth == 0:
                        k += 1
                        break
                k += 1
            out.append("\\boxed{" + _MATH_MASK + "}")
            count += 1
            i = k
        else:
            out.append(text[idx : idx + len("\\boxed")])
            i = idx + len("\\boxed")
    return "".join(out), count


def redact_final_answers(text: str) -> tuple[str, int]:
    """يحجب كل نتيجة نهائية صريحة من ``text``. حتمي، fail-open.

    Returns:
        (النص المحجوب، عدد الحجوبات).
    """
    if not text or not text.strip():
        return text or "", 0
    try:
        total = 0
        result, n_boxed = _strip_boxed(text)
        total += n_boxed

        def _mask_rhs(match: re.Match[str]) -> str:
            nonlocal total
            total += 1
            return f"{match.group('lhs')}{_PROSE_MASK}"

        result = _FINAL_RESULT_RE.sub(_mask_rhs, result)
        result = _CONCLUSION_RE.sub(_mask_rhs, result)

        def _mask_marker(match: re.Match[str]) -> str:
            nonlocal total
            total += 1
            return f"{match.group('lbl')}{_PROSE_MASK} (حاول أن تصل إليها بنفسك)"

        result = _RESULT_MARKER_RE.sub(_mask_marker, result)
        return result, total
    except Exception:  # pragma: no cover - fail-open مطلق
        logger.debug("answer_redaction failed (fail-open)", exc_info=True)
        return text, 0


def redact_chunk(text: str) -> str:
    r"""حجب آمن للبثّ المباشر (per-chunk): `\boxed{...}` فقط (لا يحتاج سياقاً).

    النتائج اللفظية والمعادلات تحتاج سطراً كاملاً، فتُترك للحجب النهائي
    (`redact_final_answers` عبر `sanitize_final_text`).
    """
    if not text or "\\boxed" not in text:
        return text or ""
    try:
        cleaned, _ = _strip_boxed(text)
        return cleaned
    except Exception:  # pragma: no cover
        return text


# ── العقود (Pydantic) ────────────────────────────────────────────────────────


class AnswerRedactionInput(RobustBaseModel):
    """مدخلات الحجب."""

    text: str = Field(..., max_length=200_000)


class AnswerRedactionOutput(RobustBaseModel):
    """مخرج الحجب."""

    redacted_text: str
    redactions: int = 0
    applied: bool = False
    doctrine_version: str = DOCTRINE_VERSION


def _record_metric(status: str, redactions: int, duration_s: float) -> None:
    with contextlib.suppress(Exception):
        from app.telemetry.unified_observability import get_unified_observability

        obs = get_unified_observability()
        obs.record_metric(
            "skill.answer_redaction.invocations.total",
            1.0,
            labels={"status": status},
        )
        if redactions:
            obs.record_metric("skill.answer_redaction.redactions.total", float(redactions))
        obs.record_metric("skill.answer_redaction.duration_seconds", duration_s)


class AnswerRedactionSkill:
    """واجهة Skill رسمية للـ registry + القياس (D-113).

    عقد دائم (لا يُكسر بدون ADR):
    1. النتيجة النهائية لا تصل الطالب أبداً في الشرح العادي.
    2. النطاق ضيّق — الصيغ التعليمية الوسيطة تبقى سليمة.
    3. الرياضيات تبقى صالحة (`\\boxed{?}` لا حذف يكسر LaTeX).
    4. حتمي بلا LLM — قابل للاختبار.
    5. fail-open مطلق — فشل الحارس لا يكسر دور الطالب.
    """

    VERSION = DOCTRINE_VERSION
    SKILL_NAME = "answer_redaction"

    def redact(self, payload: AnswerRedactionInput | str) -> AnswerRedactionOutput:
        t0 = time.perf_counter()
        if isinstance(payload, str):
            payload = AnswerRedactionInput(text=payload)
        try:
            cleaned, n = redact_final_answers(payload.text)
            _record_metric("success", n, time.perf_counter() - t0)
            return AnswerRedactionOutput(
                redacted_text=cleaned,
                redactions=n,
                applied=n > 0,
            )
        except Exception:  # pragma: no cover - fail-open
            logger.debug("answer_redaction skill failed (fail-open)", exc_info=True)
            _record_metric("fallback", 0, time.perf_counter() - t0)
            return AnswerRedactionOutput(redacted_text=payload.text, applied=False)


_SKILL_SINGLETON: AnswerRedactionSkill | None = None


def get_answer_redaction_skill() -> AnswerRedactionSkill:
    """Singleton للـ AnswerRedactionSkill."""
    global _SKILL_SINGLETON
    if _SKILL_SINGLETON is None:
        _SKILL_SINGLETON = AnswerRedactionSkill()
    return _SKILL_SINGLETON


__all__ = [
    "AnswerRedactionInput",
    "AnswerRedactionOutput",
    "AnswerRedactionSkill",
    "get_answer_redaction_skill",
    "redact_chunk",
    "redact_final_answers",
]
