"""NotationSkill — تعريف كل رمز رياضي يطبعه النظام (D-185).

## لماذا هذه المهارة موجودة
طالب حقيقي سأل **«ماذا نقصد بحرف C»** — عن رمزٍ طبعه المعلّم نفسه على الشاشة — فتُجوهِل
سؤاله وأُعيد عليه اشتقاقٌ لم يفهمه أصلاً (ISS-138). الجذر أنّ كل نقاط المطابقة في المنصّة
كانت مفتاحها **اسم المفهوم** لا **الرمز**، فمن لا يعرف الاسم لا يستطيع السؤال عن المعنى.

القانون الذي تُرسيه: **النظام يجب أن يكون قادراً على تعريف كل رمز يطبعه** —
تفرضه بوّابة `scripts/fitness/check_notation_definable.py`.

## المسؤولية الواحدة
تحويل سؤال الطالب الحرّ إلى رمزٍ مُعرَّف (`resolve`)، أو تعريف رمزٍ بعينه (`define`).
حتمية 100% — **لا LLM في هذا المسار إطلاقاً** (CLAUDE.md §0: الحقيقة الرمزية قبل اللغة).

## العقد والتدهور الرشيق (قانون المهارات ٥)
المصدر القانوني `shared/notation/registry.py`، وتعكسه الخدمة المصغّرة
`notation-service :8011` عبر عقد `docs/contracts/openapi/notation_service-openapi.json`.
- **المسار التعليمي** (دور الطالب) يستدعي `resolve()` الحتمي **المحلّي** — بلا شبكة، بلا
  زمن انتظار. لا يجوز أن يدفع الطالب ثمن نداء HTTP لمعرفة معنى حرف.
- **مستهلكو الـAPI والوكلاء** يستدعون `resolve_via_service()` الذي يمرّ بالخدمة مع
  `X-Correlation-ID`، ويسقط سقوطاً حتميّاً إلى النسخة المحلّية عند تعذّرها.
فالمهارة تعمل كاملةً بلا الخدمة، والخدمة تُتيحها لبقيّة النظام — وكلاهما يقرأ سجلّاً واحداً.

## القياس (Prometheus)
- ``cogniforge_skill_notation_total{action, status}`` (counter)
- ``cogniforge_skill_notation_duration_seconds`` (histogram)
"""

from __future__ import annotations

import os
import time
from typing import ClassVar

from app.services.skills.base import BaseSkill, skill_counter, skill_histogram
from shared.notation import NotationEntry, all_symbols, define, resolve

__all__ = ["NotationSkill", "get_notation_skill"]

_NOTATION_CALLS = skill_counter(
    "cogniforge_skill_notation_total",
    "استدعاءات مهارة الرموز الرياضية",
    ("action", "status"),
)
_NOTATION_DURATION = skill_histogram(
    "cogniforge_skill_notation_duration_seconds",
    "زمن مهارة الرموز الرياضية (ثوانٍ)",
)

#: مهلة قصيرة جداً — الخدمة اختيارية، والسقوط المحلّي فوري.
_SERVICE_TIMEOUT_S = 3.0


class NotationSkill(BaseSkill[str, NotationEntry | None]):
    """مهارة تعريف الرموز الرياضية — حتمية، بعقد، وبتدهور رشيق."""

    name: ClassVar[str] = "notation"
    version: ClassVar[str] = "1.0.0"

    def run(self, question: str) -> NotationEntry | None:
        """نقطة الدخول الموحّدة (BaseSkill) — تُفوّض إلى :meth:`resolve`."""
        return self.resolve(question)

    @property
    def service_url(self) -> str:
        """عنوان الخدمة المصغّرة — يُقرأ من البيئة (لا قيمة مُصلَّبة في الكود)."""
        return os.environ.get("NOTATION_SERVICE_URL", "http://localhost:8011")

    def resolve(self, question: str) -> NotationEntry | None:
        """يحوّل سؤال الطالب الحرّ إلى رمزٍ مُعرَّف — حتمي ومحلّي (مسار الدور التعليمي)."""
        started = time.monotonic()
        try:
            entry = resolve(question)
        except Exception:  # pragma: no cover - السجلّ حتمي؛ حارس دفاعي فقط
            _NOTATION_CALLS.labels(action="resolve", status="error").inc()
            return None
        finally:
            _NOTATION_DURATION.observe(time.monotonic() - started)
        _NOTATION_CALLS.labels(action="resolve", status="hit" if entry else "miss").inc()
        return entry

    def define(self, symbol: str) -> NotationEntry | None:
        """يُرجع تعريف رمزٍ بعينه (`C`, `n!`, `P_A(B)` …)."""
        started = time.monotonic()
        try:
            entry = define(symbol)
        finally:
            _NOTATION_DURATION.observe(time.monotonic() - started)
        _NOTATION_CALLS.labels(action="define", status="hit" if entry else "miss").inc()
        return entry

    def known_symbols(self) -> tuple[str, ...]:
        """كل الرموز التي يستطيع النظام تعريفها — مصدر بوّابة «لا رمز يتيم»."""
        return all_symbols()

    async def resolve_via_service(self, question: str) -> NotationEntry | None:
        """يمرّ بالخدمة المصغّرة (عقد + `X-Correlation-ID`)، ويسقط محليّاً عند تعذّرها.

        مُخصَّص لمستهلكي الـAPI والوكلاء لا لدور الطالب — فالدور التعليمي يستعمل
        :meth:`resolve` المحلّي حفظاً لزمن الاستجابة.
        """
        try:
            # D-189: كان هذا الموضع يُولِّد `uuid4()` **جديداً** لكل نداء، فيقطع سلسلة
            # الأثر بدل أن يمدّها — الدور يحمل مُعرَّفاً والنداء الصادر عنه يحمل آخر لا
            # صلة له به. `correlated_client` يمدّ المُعرَّف المحيط ولا يولّد إلا كملاذ أخير.
            from shared.http_client import correlated_client

            async with correlated_client(timeout=_SERVICE_TIMEOUT_S) as client:
                response = await client.post(
                    f"{self.service_url}/resolve",
                    json={"text": question},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception:
            # تدهور رشيق: الخدمة ليست شرطاً للإجابة — السجلّ نفسه محلّي.
            _NOTATION_CALLS.labels(action="resolve_service", status="fallback").inc()
            return self.resolve(question)
        if not payload.get("found"):
            _NOTATION_CALLS.labels(action="resolve_service", status="miss").inc()
            return None
        _NOTATION_CALLS.labels(action="resolve_service", status="hit").inc()
        # الخدمة تُرجع الحمولة فقط؛ نعيد الإدخال القانوني من السجلّ المحلّي (مصدر واحد).
        return define(str((payload.get("symbol") or {}).get("symbol", "")))


def get_notation_skill() -> NotationSkill:
    """المُفرَدة الكسولة لمهارة الرموز (BaseSkill.instance)."""
    return NotationSkill.instance()
