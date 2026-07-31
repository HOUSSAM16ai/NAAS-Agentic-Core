"""عقود حدود التكامل المُصنَّفة (D-192 · roadmap §6.5.د D1).

**لماذا هذا الملفّ موجود:**

نقدٌ هندسي خارجي (2026-07-29) رصد أن الدستور يعلن «No `Any`» بينما `Any` موجودة على
**حدود التكامل** — وهي آخر مكان يُقبل فيه فقدان أمان العقد، لأنها بالضبط حيث تدخل
بيانات خدمةٍ أخرى إلى نواة التطبيق. الفحص أكّد النقد: **22** استعمالاً لـ`Any` عبر
أربعة ملفّات في `app/integration/`.

والمفارقة أن الطبقة **تحت** البوّابة كانت أدقّ منها: `research_client` يُرجِع
`list[dict[str, object]]` و`dict[str, object]`، فكانت طبقة البوّابة **تُوسّع** ما
ضيّقه العميل. هذه النماذج تُعيد الضيق إلى مكانه.

**قاعدة التصميم:** النماذج **متسامحة عند القراءة، صارمة عند العقد**
(`extra="ignore"` عبر `RobustBaseModel`): حقلٌ جديد من الخدمة لا يُسقط الدور، لكن
الحقول المُعلَنة مضمونة النوع. ومن يحتاج الحمولة الخام يجدها في `raw`.
"""

from __future__ import annotations

from pydantic import Field

from app.core.schemas import RobustBaseModel

__all__ = [
    "GatewayStatus",
    "PlanResult",
    "RefinedQuery",
    "RerankedDocument",
    "SearchHit",
]


class SearchHit(RobustBaseModel):
    """نتيجة بحث دلالي واحدة كما تعبر حدّ خدمة البحث."""

    text: str = Field(default="", description="نصّ المقطع المُسترجَع")
    score: float = Field(default=0.0, description="درجة التشابه")
    source: str = Field(default="", description="مُعرِّف المصدر/الملف")
    metadata: dict[str, object] = Field(default_factory=dict)


class RefinedQuery(RobustBaseModel):
    """استعلامٌ بعد التنقيح (DSPy/LLM) + المرشِّحات المستخرَجة."""

    query: str = Field(default="", description="الاستعلام بعد التنقيح")
    filters: dict[str, object] = Field(default_factory=dict)
    reasoning: str = Field(default="", description="تعليل التنقيح إن أُرسِل")


class RerankedDocument(RobustBaseModel):
    """مستندٌ بعد إعادة الترتيب."""

    text: str = Field(default="")
    score: float = Field(default=0.0)
    index: int = Field(default=0, ge=0, description="موضعه في القائمة الأصلية")


class GatewayStatus(RobustBaseModel):
    """حالة قدرةٍ خلف البوّابة — `status` نصّ مُقيَّد بالاستعمال لا بالنوع."""

    status: str = Field(default="unknown")
    mode: str = Field(default="", description="remote-microservice | local | disabled")
    detail: str = Field(default="")


class PlanResult(RobustBaseModel):
    """نتيجة التخطيط المعرفي.

    كان عقد التخطيط يقول حرفياً «Returns a PlanResult object (or similar structure)»
    لنوعٍ **غير موجود** — عقدٌ يصف نفسه بأنه غير محدَّد. هذا هو ذلك النوع.
    """

    plan_id: str = Field(default="")
    goal: str = Field(default="")
    steps: list[dict[str, object]] = Field(default_factory=list)
    status: str = Field(default="unknown")
    raw: dict[str, object] = Field(
        default_factory=dict, description="الحمولة الخام — لمن يحتاج حقلاً غير مُعلَن"
    )
