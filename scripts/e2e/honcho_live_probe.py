#!/usr/bin/env python3
"""مسبار حيّ لطبقة الهوية المعرفية المحيطة — D-269 (§0.21).

## لماذا هذا السكربت موجود

وجودُ مفتاحٍ في إعدادات المستودع ليس دليلاً على قدرة. البرهان الثلاثي (§6.6) يطلب
``import`` + سلسلة نداء + **دليل تشغيل**، وهذا السكربت هو الساق الثالثة: يُشغَّل على
عدّاء GitHub ويُثبت أنّ المفتاح المُلتقَط **يعمل فعلاً** على الطرف الثالث.

ولماذا على العدّاء لا هنا: منفذا Postgres (6543/5432) محجوبان من حاويات التطوير
(قياسٌ حيّ)، فالعدّاء هو الموضع الوحيد الذي تكتمل فيه الرحلة.

## ما يُثبته وما لا يُثبته

* ✅ المفتاح مقبولٌ من الطرف الثالث، والطبقة متاحة.
* ⛔ **لا يُثبت** أنّ بيانات طالبٍ تُرسَل — لأنّها **لا تُرسَل**. النداء الوحيد
  استعلامُ قراءةٍ لقائمة مساحات العمل، ومسارُ الكتابة `SEAM` بصفر كود.

⛔ **الأسرار من البيئة حصراً** — لا مفتاح في هذا الملفّ (D-265 L8)، ولا يُطبَع
المفتاح ولا جزءٌ منه في أيّ مخرَج.

    python scripts/e2e/honcho_live_probe.py            # تقريرٌ فقط
    python scripts/e2e/honcho_live_probe.py --require  # غيابُ المفتاح فشلٌ صريح
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.ambient_memory import (
    AmbientMemoryConfig,
    probe_ambient_memory,
)


def _config_from_env() -> AmbientMemoryConfig:
    """يبني الإعداد من البيئة. هذا سكربتٌ خارج ``app/`` — فقراءةُ البيئة موطنه."""
    return AmbientMemoryConfig(
        api_key=os.environ.get("HONCHO_API_KEY"),
        base_url=os.environ.get("HONCHO_BASE_URL", "https://api.honcho.dev"),
        api_version=os.environ.get("HONCHO_API_VERSION", "v3"),
        workspace_id=os.environ.get("HONCHO_WORKSPACE_ID", "ETAALIM"),
        timeout_seconds=float(os.environ.get("HONCHO_PROBE_TIMEOUT_SECONDS", "10")),
    )


async def _run(require: bool) -> int:
    config = _config_from_env()
    print("🧠 مسبار طبقة الهوية المعرفية المحيطة (Honcho — D-269)")
    print(f"   المضيف   : {config.base_url}")
    print(f"   الإصدار  : {config.api_version}")
    print(f"   المفتاح  : {'مضبوط' if config.configured else 'غائب'}")  # ⛔ لا قيمة

    result = await probe_ambient_memory(config)
    print(f"\n   الحالة   : {result.state}")
    print(f"   التفصيل  : {result.detail}")
    if result.status_code is not None:
        print(f"   HTTP     : {result.status_code}")
    if result.workspace_count is not None:
        print(f"   مساحات   : {result.workspace_count}")

    if result.state == "reachable":
        print("\n✅ الطبقة متاحة والمفتاح مقبول — ⛔ وصفر بيانات طالبٍ غادرت المنصّة.")
        return 0

    if result.state == "not_configured":
        if require:
            print(
                "\n::error::`HONCHO_API_KEY` غير واصل — اضبطه في أسرار المستودع بهذا "
                "الاسم بالضبط. طُلب `--require`، والصمت لا يُقرأ نجاحاً (D-207)."
            )
            return 1
        print("\n::warning::`HONCHO_API_KEY` غير مضبوط — الطبقة اختيارية ولم تُختبَر.")
        return 0

    print(f"\n::error::المسبار فشل بالحالة «{result.state}» — {result.detail}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require",
        action="store_true",
        help="اجعل غيابَ المفتاح فشلاً صريحاً بدل تحذير.",
    )
    return asyncio.run(_run(parser.parse_args().require))


if __name__ == "__main__":
    sys.exit(main())
