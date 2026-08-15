"""جذر إعدادات الاختبار — جسرٌ واحد للسياسة الموحَّدة (D-258).

D-258 (CodeScene X-Ray 2026-08-15): كانت هذه الوحدة تعيد تعريف
`_ALLOWED_WARNING_SUBSTRINGS`/`_count_enforced_warnings`/`pytest_sessionfinish`
بعد `from tests.conftest import *` — ازدواجٌ حقيقي (نسخةٌ أقدم من نسخة
`tests/conftest.py` الأحدث التي تحرس xfailed/xpassed أيضًا). السياسة الواحدة
توجد الآن في `tests/conftest_support.policy.py` وتُصدَّر من `tests.conftest` —
هنا يبقى الاستيراد القانوني الوحيد.
"""

from __future__ import annotations

from tests.conftest import *  # noqa: F403
