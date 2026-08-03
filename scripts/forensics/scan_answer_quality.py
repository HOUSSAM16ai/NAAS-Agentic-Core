#!/usr/bin/env python3
"""مسحٌ شرعي لجودة إجابات الإنتاج — يصنّف كل دور مساعد ولا يطبع محتوى طالب (D-209).

## لماذا هذا السكربت موجود

D-207 وD-208 شُخِّصا **بقراءة قاعدة الإنتاج** لا بالتحليل الساكن — وهذا هو الفرق بين
«يبدو أن الكود صحيح» و«الطالب تلقّى هذا فعلاً». لكن القراءة كانت في كل مرّة استعلاماً
يدوياً يُكتب ثمّ يضيع، فلا يتراكم شيء ولا يُقارَن أسبوعٌ بأسبوع.

هذا السكربت يجعل المسح **قابلاً لإعادة التشغيل**: نفس التصنيف، نفس الحدود، نفس المخرَج.

## قانونان في تصميمه

1. **المصنِّف دالّة نقيّة** (`classify`) — بلا شبكة وبلا قاعدة بيانات، فيُختبَر بـ`pytest`
   عادي. قشرةُ الإدخال/الإخراج وحدها تلمس القاعدة (نواةٌ وظيفية وقشرةٌ أمرية).
2. ⛔ **لا يطبع محتوى رسالة طالبٍ أبداً** — الأعداد والمُعرَّفات والتواريخ فقط. تقريرٌ
   يقتبس سطراً من محادثة يصير باباً خلفياً إلى ما يحميه D-113/D-196.

## الاكتشاف الذي وُلد منه (2026-08-03)

على 2,250 دور مساعد في الإنتاج: **`truly_silent = 0`** — لا دورَ واحد تلقّى فيه الطالب
لا نصّاً ولا بطاقة. و«الأدوار الفارغة» الـ212 التي حملها ISS-145 كانت **كلّها** (212/212)
تحمل `ui_component` حقيقياً: `full_exercise_story` بمتوسّط 5.4KB · `bkt_hint_display` ·
`learning_path_card` … أي أنها بطاقاتُ الواجهة التوليدية المحفوظة عمداً (ISS-106 /
D-WS-CARD-PERSIST-001) لتُصيَّر من التاريخ بعد إعادة الدخول — لا إجاباتٌ ضائعة.

ولهذا فالثنائي `(content فارغ, ui_component غائب)` هو **التعريف الصحيح للصمت**، والعمود
وحده ليس تعريفاً. هذا هو الفرق بين بلاغٍ يقيس الشيء وبلاغٍ يقيس ظِلَّه.

## التشغيل

    python scripts/forensics/scan_answer_quality.py --self-test     # بلا قاعدة بيانات
    DATABASE_URL=... python scripts/forensics/scan_answer_quality.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from dataclasses import dataclass

#: محارف غير عربية/لاتينية تظهر حين ينهار ترميز النموذج (ISS-069 وأخواتها).
_GARBAGE_SCRIPT = re.compile(r"[一-鿿぀-ヿЀ-ӿ]")
#: أيّ حرف عربي.
_ARABIC = re.compile(r"[؀-ۿ]")
#: «لنكمل … خطوة بخطوة:» ثمّ ولا خطوة — عين ISS-148 (D-207).
_PROMISE_PREFIX = re.compile(r"^\s*(?:لنكمل|لنُكمل)")
#: رفضٌ إنجليزي مُسرَّب إلى طالبٍ عربي.
_ENGLISH_REFUSAL = re.compile(r"(?i)\b(as an ai|language model|i apologize|i cannot)\b")
#: تهنئةٌ على حيرة (ISS-149 · D-208).
_PRAISE = re.compile(r"أحسنت|ممتاز")
_CONFUSION = re.compile(r"لم أفهم|مفهمتش|ما فهمتش")

#: أدنى طولٍ لنصٍّ يُعتبَر جواباً حين لا تحمله بطاقة.
_MIN_TEXT_CHARS = 25


@dataclass(frozen=True)
class Turn:
    """دورٌ مساعد كما هو مُخزَّن — بلا هوية طالب."""

    message_id: int
    content: str | None
    ui_component: str | None


#: قواعد الأصناف النصّية **مرتَّبةً** — الترتيب جزء من التعريف لا تفصيلٌ تنفيذي
#: (D-206: كارثتان كان كشفُهما سليماً وعطبُهما في الأسبقيّة وحدها). أوّل مطابقةٍ تفوز،
#: والأشدّ أوّلاً: انهيار الترميز ⇒ غياب العربية ⇒ الوعد الفارغ ⇒ الرفض الإنجليزي ⇒
#: التهنئة على الحيرة.
_TEXT_RULES: tuple[tuple[str, object], ...] = (
    ("garbage_script", _GARBAGE_SCRIPT.search),
    ("no_arabic", lambda t: not _ARABIC.search(t)),
    ("empty_promise", _PROMISE_PREFIX.search),
    ("english_refusal", _ENGLISH_REFUSAL.search),
    ("praise_over_confusion", lambda t: bool(_PRAISE.search(t) and _CONFUSION.search(t))),
)


def classify(turn: Turn) -> str | None:
    """يُرجِع اسم صنف العطب أو ``None`` إن كان الدور سليماً.

    **الترتيب جزء من التعريف** (D-206): الصمت يُفحَص أوّلاً لأنه الأشدّ، ثمّ الأصناف
    النصّية بترتيب ``_TEXT_RULES``. ودورٌ بلا نصّ **ومعه بطاقة** ليس عطباً — البطاقة
    هي الجواب، وهو بالضبط ما أخطأ فيه ISS-145.
    """
    text = (turn.content or "").strip()
    card = (turn.ui_component or "").strip()

    if not text:
        # الصمت الحقيقي: لا نصّ **ولا** بطاقة. الطالب لم يتلقَّ شيئاً.
        # وبطاقةٌ بلا نصّ = مسار البصري الحتمي (D-116) يعمل كما صُمِّم.
        return None if card else "truly_silent"

    for name, matches in _TEXT_RULES:
        if matches(text):  # type: ignore[operator]
            return name

    if len(text) < _MIN_TEXT_CHARS and not card:
        return "stub_no_card"
    return None


_SELF_TESTS: tuple[tuple[Turn, str | None], ...] = (
    (Turn(1, "", None), "truly_silent"),
    (Turn(2, None, None), "truly_silent"),
    # القلب: بطاقةٌ بلا نصّ ليست عطباً — وهو ما أخطأ فيه ISS-145.
    (Turn(3, "", '{"component":"full_exercise_story"}'), None),
    (Turn(4, None, '{"component":"bkt_hint_display"}'), None),
    (Turn(5, "لنكمل معاً خطوة بخطوة حتى النهاية:", None), "empty_promise"),
    (Turn(6, "الجواب هو 你好 مرحبا", None), "garbage_script"),
    (Turn(7, "The answer is 42 and nothing else here", None), "no_arabic"),
    (Turn(8, "I apologize, as an AI أنا لا أستطيع", None), "english_refusal"),
    (Turn(9, "أحسنت ✅ يبدو أنك فهمت، لكنك قلت لم أفهم", None), "praise_over_confusion"),
    (Turn(10, "نعم ✅", None), "stub_no_card"),
    (Turn(11, "هذا شرحٌ عربيٌّ كاملٌ وطويلٌ بما يكفي ليكون جواباً حقيقياً.", None), None),
)


def _self_test() -> int:
    failures = [
        f"  • الرسالة {t.message_id}: توقّعتُ {want!r} فجاء {classify(t)!r}"
        for t, want in _SELF_TESTS
        if classify(t) != want
    ]
    if failures:
        print("❌ المصنِّف مخروق:\n" + "\n".join(failures))
        return 1
    print(f"✅ المصنِّف: {len(_SELF_TESTS)} حالة، كلّها مطابقة.")
    return 0


async def _scan(dsn: str) -> int:
    try:
        import asyncpg
    except ImportError:
        print("❌ asyncpg غير مثبَّت — المسح الحيّ يتطلّبه. جرّب --self-test.")
        return 2

    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT id, content, ui_component FROM customer_messages WHERE role='assistant'"
        )
    finally:
        await conn.close()

    counts: dict[str, int] = {}
    for row in rows:
        verdict = classify(Turn(row["id"], row["content"], row["ui_component"]))
        if verdict:
            counts[verdict] = counts.get(verdict, 0) + 1

    print(f"دقّقتُ {len(rows)} دور مساعد.")
    if not counts:
        print("✅ صفر عطبٍ مُصنَّف.")
        return 0
    for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {name:24s} {n:5d}")
    # ⛔ الصمت وحده يُفشِل: البقيّة تُبلَّغ ولا تُوقِف (أصنافٌ تاريخية مُغلَقة).
    return 1 if counts.get("truly_silent") else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="يفحص المصنِّف بلا قاعدة")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    dsn = os.environ.get("DATABASE_URL") or os.environ.get("APP_DATABASE_URL") or ""
    if not dsn:
        print("❌ لا DATABASE_URL. مررّه في البيئة أو استعمل --self-test.")
        return 2
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    dsn = re.sub(r"[?&]sslmode=[^&]*", "", dsn)
    return asyncio.run(_scan(dsn))


if __name__ == "__main__":
    sys.exit(main())
