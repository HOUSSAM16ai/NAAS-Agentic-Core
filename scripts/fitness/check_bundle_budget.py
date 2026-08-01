#!/usr/bin/env python3
"""ميزانية حجم حزمة الواجهة (D-199).

لماذا
-----
حزمة الواجهة تنمو بهدوء: مكتبةٌ هنا، أيقونةٌ هناك، ولا أحد يلاحظ حتى تصير الصفحة غير
قابلة للتحميل على 3G — وهي شبكة معظم طلابنا. **الميزانية تجعل النموّ قراراً لا مفاجأة**:
من يضيف ٢٠٠KB يجب أن يرفع الرقم صراحةً ويشرح لماذا، لا أن يمرّ الأمر بصمت.

القياس
------
مجموع حجم `.next/static/chunks/**/*.js` — أي شيفرة JavaScript التي يجب أن تصل المتصفّح.
يُستثنى الخطّ والصور: هي أصولٌ تُحمَّل بالتوازي ولا تحجب التنفيذ، ولها منطق تحسين مختلف.

القاعدة: **يتقلّص فقط**، كبقيّة دَيْن هذا المستودع (سابقة D-105). رفع السقف تغييرٌ
مقصود يظهر في المراجعة.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHUNKS_DIR = REPO_ROOT / "frontend" / ".next" / "static" / "chunks"

#: السقف بالكيلوبايت لمجموع شيفرة JS المُرسَلة. **يُخفَّض عند التحسّن، ولا يُرفَع بلا سبب.**
BUDGET_KB = 1100


def total_js_kilobytes() -> tuple[int, int]:
    """يُرجِع (المجموع بالكيلوبايت، عدد الملفّات)."""
    files = sorted(CHUNKS_DIR.rglob("*.js"))
    total = sum(path.stat().st_size for path in files)
    return round(total / 1024), len(files)


def main() -> int:
    if not CHUNKS_DIR.exists():
        print(
            f"❌ bundle budget: {CHUNKS_DIR.relative_to(REPO_ROOT)} is missing — "
            "run `npm run build --prefix frontend` first."
        )
        return 1

    total_kb, file_count = total_js_kilobytes()

    if total_kb > BUDGET_KB:
        print(
            f"❌ ميزانية الحزمة مخروقة (D-199): {total_kb}KB من JS عبر {file_count} ملفّاً، "
            f"والسقف {BUDGET_KB}KB.\n"
            "   إمّا أن تُقلِّص ما أضفته، أو ترفع BUDGET_KB صراحةً مع سببٍ في رسالة الالتزام.\n"
            "   تذكير: هذا الرقم يُترجَم مباشرةً إلى ثوانٍ ينتظرها طالبٌ على 3G."
        )
        return 1

    headroom = BUDGET_KB - total_kb
    print(
        f"✅ bundle budget: {total_kb}KB of JS across {file_count} chunks "
        f"(budget {BUDGET_KB}KB, {headroom}KB headroom)."
    )
    if headroom > 300:
        print(f"   💡 المتّسع كبير — يمكن خفض BUDGET_KB إلى {total_kb + 100} لتشديد الربط.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
