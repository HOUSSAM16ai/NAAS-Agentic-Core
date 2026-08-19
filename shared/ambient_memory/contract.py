"""عقد طبقة الهوية المعرفية المحيطة — D-269.

الأنواع وحدها: لا شبكة، لا حالة، لا استيراد من ``app`` ولا من خدمةٍ شقيقة.

## القانون الذي يحرسه هذا الملفّ بالبناء لا بالنيّة

الطبقة الخامسة (Honcho) **تُقرأ ولا تحكم**، و⛔ **لا يعبرها حرفٌ واحد من نصّ
المحادثة**. ولذلك لا يحمل هذا العقد حقلاً واحداً يمكن أن يحمل محتوى طالب: أقصى ما
يصفه هو «هل الطبقة متاحة؟». المنعُ **بنيويّ** لا مُرشِّح — نفس منهج تقرير الوليّ
(D-196: «تقرير الوليّ لا يستعلم عن ``content`` إطلاقاً»)، لأنّ مُرشِّحاً يمكن
تعديلُه سطراً واحداً، ونوعاً بلا حقلٍ يتطلّب تغييراً مرئياً يُراجَع.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

#: حالات المسبار — قائمة مغلقة. ⛔ لا «probably-reachable» وأخواتها: عبارةٌ ضبابية
#: تُقرأ نجاحاً في لوحةٍ ثمّ تنكشف عند أوّل عطل (نمط GATE_STATE_MACHINE · D-267 L6).
ProbeState = Literal[
    "reachable",  # ردَّ الطرفُ الثالث بنجاحٍ على استعلامٍ للقراءة فقط
    "unauthorized",  # مفتاحٌ حاضرٌ ومرفوض (401/403) — عطلُ إعدادٍ صريح
    "unreachable",  # شبكةٌ أو مهلة — لا نعرف حالته، ونقول ذلك
    "not_configured",  # لا مفتاح — وهذا **ليس** عطلاً: الطبقة اختيارية
]

#: مهلةٌ صريحة دائماً. ``None`` تعني الافتراضي لا انتظاراً مفتوحاً — والانتظار
#: المفتوح على حدّ طرفٍ ثالث يحوّل البطء إلى تعليق (D-189 البند 4).
DEFAULT_PROBE_TIMEOUT_SECONDS: Final[float] = 5.0


@dataclass(frozen=True, slots=True)
class AmbientMemoryConfig:
    """إعداد الطبقة، مُمرَّراً وسيطاً.

    ⛔ ``shared/`` لا يستورد ``app`` (D-189 البند 5) — فالمونوليث يبني هذا الكائن من
    ``AppSettings`` ويمرّره، ولا تقرأ هذه الحزمة البيئة بنفسها.
    """

    api_key: str | None
    base_url: str = "https://api.honcho.dev"
    api_version: str = "v3"
    workspace_id: str = "ETAALIM"
    timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS

    @property
    def configured(self) -> bool:
        """هل يوجد مفتاحٌ غير فارغ؟ (الفراغ ليس مفتاحاً.)"""
        return bool(self.api_key and self.api_key.strip())

    def workspaces_list_url(self) -> str:
        """مسار الاستعلام الوحيد المسموح: **قراءةُ قائمة مساحات العمل**.

        مُثبَتٌ حيّاً 2026-08-19: ``POST /v3/workspaces/list`` ⇒ 200، بينما ``v2``
        و``v1`` ⇒ 404. الإصدار بيانٌ مقيس لا تخمين.
        """
        return f"{self.base_url.rstrip('/')}/{self.api_version}/workspaces/list"


@dataclass(frozen=True, slots=True)
class AmbientMemoryProbeResult:
    """نتيجة المسبار — بلا أيّ حقلٍ يمكن أن يحمل نصّ طالب (انظر ترويسة الملفّ)."""

    state: ProbeState
    detail: str
    workspace_count: int | None = None
    status_code: int | None = None

    @property
    def healthy(self) -> bool:
        """⚠️ ``not_configured`` **ليس** صحّة: هو «لا نعرف لأنّنا لم نُسأل».

        وخلطُ الاثنين هو بالضبط ما يحظره D-215 («``TIMEOUT`` ليس نجاحاً»).
        """
        return self.state == "reachable"

    def summarize(self) -> dict[str, object]:
        """تمثيلٌ صالحٌ للعرض في ``/health`` — أسماءٌ وأعدادٌ فقط."""
        summary: dict[str, object] = {"status": self.state, "detail": self.detail}
        if self.workspace_count is not None:
            summary["workspaces"] = self.workspace_count
        if self.status_code is not None:
            summary["http_status"] = self.status_code
        return summary
