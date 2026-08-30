"""ما يُبلَّغ عنه ولا يحجب — سجلٌّ مُصرَّح واحد للمخالفات المؤجَّلة عمداً.

**لماذا هذا الملفّ (ISS-199):** الدفعة ``3176fe6`` («feat: enforce dual-track governance
and live E2E gates» — دفعةٌ مباشرة على ``main`` برسالةٍ عارية) أضافت ``workflow_call``
إلى ``live-e2e.yml`` ووصلت ``live-e2e-required`` بـ``required-ci`` في ``ci.yml`` — وفي
``needs`` وفي سلسلة ``isValid`` معاً. و``diff`` تلك الدفعة على ``live-e2e.yml`` يبدأ عند
``@@ -25``: أي أنّ **الرأس (١→٢٤) لم يُلمَس**، وهو يقول حرفيّاً «لماذا ``workflow_dispatch``
وحده، ولماذا **ليس** في ``required-ci`` … وانقطاعُ طرفٍ ثالث يجب ألّا يحجب دمجاً — نفس
القاعدة المُعلَنة على ``codescene-coverage``». فبقي العقد المكتوب يصف نقيض التنفيذ، وهو
**صنف ISS-198 نفسه**: وعدٌ يفارق تنفيذه فيكذب على كلّ من يقرؤه.

والأثر مقيسٌ لا نظري: صارت بوّابةٌ **حاجبة** مُوجَّهةً إلى **ISS-150**، وهو في
``.memory/issues.md`` **🔴 مفتوح** بنصٍّ صريح («⛔ لم يُصلَح عمداً … الإصلاح يحتاج جولته:
توسيع مرمى الحارس + عقد ترانسكريبت مُثبَتٌ أحمر قبل الإصلاح»). وبوّابةٌ تحجب على عطبٍ
قرّر المستودع تأجيله لا تحرس ضدّ انحدار — تمنع **كلّ** دفعة، بالبناء لا بالمصادفة. وهو
بالضبط ما يحذّر منه رأس الـworkflow نفسه («failing every commit … trains people to ignore
the job») وما وقع فعلاً في ISS-197.

**القاعدة الدائمة:** المخالفة إمّا **حاجبة**، وإمّا مؤجَّلةٌ **بتصريح** يسمّي بلاغاً
**مفتوحاً** في ``.memory/issues.md``. لا خانة فارغة ولا تخطٍّ صامت (D-206 L11)، ولا قائمة
ثانية في سكربتٍ آخر (D-186 — مصدرٌ واحد للنيّة). والسجلّ **يتقلّص فقط وفي الاتجاهين**:
بلاغٌ أُغلق وبقي هنا ⇒ CI أحمر، تماماً كما يُحمِّر دَينٌ أُغلق بلا تحديث رقمه في
``check_correlated_http`` (D-189).

⛔ **والتأجيل ليس إخفاءً:** المخالفة المؤجَّلة تُطبَع بنصّها كاملاً ومعها مُعرَّف بلاغها
في كلّ تشغيل، وتُحصى في سطر الحصيلة. ما يتغيّر هو **رمز الخروج** وحده.

تحرسه ``scripts/fitness/check_e2e_deferred_findings.py``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Final

#: البلاغات المفتوحة التي تُبلَّغ ولا تحجب، ولكلٍّ سببٌ منطوق. المفتاح مُعرَّفٌ يجب أن
#: يوجد في ``.memory/issues.md`` **وأن يكون مفتوحاً** — تفرض الأمرين البوّابة.
DEFERRED_FINDINGS: Final[Mapping[str, str]] = {
    "ISS-150": (
        "شظايا لاتينية داخل ردٍّ عربي. البلاغ مفتوحٌ في `.memory/issues.md` بقرارٍ "
        "مكتوبٍ بتأجيل إصلاحه إلى جولته الخاصّة (توسيع مرمى الحارس + عقد ترانسكريبت "
        "مُثبَتٌ أحمر قبل الإصلاح — D-186#6). يعود حاجباً يوم يُغلَق البلاغ، لا قبله."
    ),
}

#: العدد المُجمَّد — يتقلّص فقط. رفعُه مِسنَنٌ مُعلَن يتطلّب قراراً مرقَّماً يسمّي السبب
#: (D-266 L9)؛ وخفضُه يوجب حذف سطره معه، وإلّا احمرّت البوّابة في الاتجاه الآخر.
FROZEN_DEFERRED_COUNT: Final[int] = 1

#: صيغةُ مُعرَّف البلاغ كما تُكتب داخل نصّ المخالفة نفسها — `… (ISS-150)`.
_ISSUE_ID: Final[re.Pattern[str]] = re.compile(r"\bISS-\d{3}\b")


def deferring_issues(problem: str) -> frozenset[str]:
    """البلاغات المؤجَّلة التي تُغطّي هذه المخالفة — أو مجموعةٌ فارغة فتكون حاجبة.

    التغطية **كاملةٌ أو لا شيء**: مخالفةٌ تسمّي بلاغَين وأحدهما غير مؤجَّل تبقى حاجبة
    (مثال حيّ: ``دورٌ صامت … (ISS-145 · ISS-154)``). وإلّا لأعفى بلاغٌ مؤجَّلٌ واحد
    رفيقَه غير المؤجَّل في نفس السطر — وهو إعفاءٌ بالمصادفة لا بالتصريح، وهو نفس صنف
    الحارس الذي يسقط عند ساقه الأولى (ISS-159).

    ومخالفةٌ لا تسمّي بلاغاً إطلاقاً — وهي حالُ كلّ مخالفات **العقد** (إطارٌ نهائيّ
    واحد · نصّ نظامٍ يصل الطالب · دورٌ صامت) — حاجبةٌ دائماً.
    """
    named = frozenset(_ISSUE_ID.findall(problem))
    if named and named <= frozenset(DEFERRED_FINDINGS):
        return named
    return frozenset()


def split_problems(problems: Iterable[str]) -> tuple[list[str], list[str]]:
    """يفصل المخالفات إلى ``(حاجبة، مؤجَّلة)`` مع حفظ ترتيبها داخل كلٍّ منهما."""
    blocking: list[str] = []
    deferred: list[str] = []
    for problem in problems:
        if deferring_issues(problem):
            deferred.append(problem)
        else:
            blocking.append(problem)
    return blocking, deferred


def mark(problem: str) -> str:
    """سطرُ العرض لمخالفةٍ واحدة — ``❌`` للحاجبة و``⚠️`` للمؤجَّلة بتصريح."""
    return f"⚠️ {problem} — مؤجَّل بتصريح" if deferring_issues(problem) else f"❌ {problem}"


def render_deferred(deferred: Iterable[str]) -> list[str]:
    """أسطرُ التقرير للمخالفات المؤجَّلة — تُطبَع دائماً، بنصّها ومُعرَّفها وسببها.

    تُبنى حتى حين تكون الرحلة ناجحة: خُضرةٌ لا تذكر ما رأته تُقرأ «لم يحدث شيء».
    """
    lines: list[str] = []
    for problem in deferred:
        lines.append(f"   ⚠️ {problem}")
        for issue_id in sorted(deferring_issues(problem)):
            lines.append(f"      ↳ {issue_id}: {DEFERRED_FINDINGS[issue_id]}")
    return lines
