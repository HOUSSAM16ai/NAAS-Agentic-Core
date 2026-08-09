#!/usr/bin/env python3
"""تقرير زمن الدور وتسليم الكائن — من الإنتاج، للقراءة فقط (D-230).

## لماذا هذا التقرير موجود

قاعدة §6.7-ي: **الأجهزة قبل التصوير**. وقانون §0.6 المرحلة ١ («الطالب يتفاعل مع كائنات
لا يقرأ جداراً») ظلّ بلا مقياسٍ واحد، فانحدر تسليم الكائن من 36.6٪ إلى 3.4٪ عبر شهرين
**ولم يُبلِّغ شيء**. ما لا يُقاس ينحرف، وما لا يُرى لا يُساءَل.

هذا السكربت يُخرِج الرقمين اللذين يجب أن يُتابَعا:

  ① زمن الوصول إلى أوّل ردٍّ غير فارغ، مُصنَّفاً بحدود `shared/ux/budgets`
  ② نسبة الردود التي تحمل كائناً تفاعلياً، شهراً بشهر

⛔ **قراءة فقط.** لا `INSERT` ولا `UPDATE` ولا DDL — تقريرٌ يُشخِّص، ولا يلمس بيانات
طالب. ويقرأ `DATABASE_URL` من البيئة (لا أسرار في الشيفرة).

    python scripts/reports/turn_latency.py [--since 2026-05-01]
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from typing import Any, Final

from shared.ux import ATTENTION_LIMIT_S, FLOW_LIMIT_S, classify_latency

#: مهلة صريحة دائماً — انتظارٌ مفتوح على حدّ خدمة يحوّل البطء إلى تعليق (D-189 بند ٤).
_TIMEOUT_S: Final[float] = 30.0

_LATENCY_SQL: Final[str] = """
WITH turns AS (
  SELECT u.id AS uid, u.created_at AS asked,
         (SELECT MIN(a.created_at) FROM customer_messages a
           WHERE a.conversation_id = u.conversation_id AND a.role = 'assistant'
             AND a.created_at > u.created_at AND LENGTH(a.content) > 0) AS answered
  FROM customer_messages u
  WHERE u.role = 'user' AND u.created_at >= :since
)
SELECT
  COUNT(*)                                                       AS turns,
  COUNT(*) FILTER (WHERE answered IS NULL)                       AS never_answered,
  percentile_cont(0.50) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM answered - asked)) AS p50,
  percentile_cont(0.75) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM answered - asked)) AS p75,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM answered - asked)) AS p95,
  COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM answered - asked) > :attention) AS over_attention,
  COUNT(*) FILTER (WHERE EXTRACT(EPOCH FROM answered - asked) <= :flow)     AS within_flow
FROM turns
"""

_OBJECT_SQL: Final[str] = """
SELECT date_trunc('month', created_at)::date AS month,
       COUNT(*) AS replies,
       COUNT(*) FILTER (
         WHERE ui_component IS NOT NULL AND ui_component NOT IN ('', 'null')
       ) AS with_object
FROM customer_messages
WHERE role = 'assistant'
GROUP BY 1 ORDER BY 1
"""


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("APP_DATABASE_URL")
    if not url:
        raise SystemExit("❌ DATABASE_URL غير مضبوط. التقرير يقرأ من البيئة — لا أسرار في الشيفرة.")
    # SQLAlchemy يُوجِّه `postgresql://` إلى psycopg2 المتزامن (بند CLAUDE.md).
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default="2026-05-01", help="بداية نافذة القياس")
    args = parser.parse_args()

    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError

    engine = create_engine(_database_url(), connect_args={"connect_timeout": int(_TIMEOUT_S)})
    try:
        with engine.connect() as conn:
            row = (
                conn.execute(
                    text(_LATENCY_SQL),
                    {
                        "since": args.since,
                        "attention": ATTENTION_LIMIT_S,
                        "flow": FLOW_LIMIT_S,
                    },
                )
                .mappings()
                .one()
            )
            months = conn.execute(text(_OBJECT_SQL)).mappings().all()
    except OperationalError as exc:
        # ⛔ لا أصفار عند تعذّر الاتصال: صفرٌ يُقرأ «لا انتظار» والحقيقة «لم نقِس».
        # جدار الصندوق الرملي يحجب منافذ Postgres (5432/6543) — موثَّق في CLAUDE.md §6.7-ز.
        print(
            "❌ تعذّر الوصول إلى قاعدة البيانات — **لم يُقَس شيء** (لا أرقام تُطبَع).\n"
            f"   السبب: {type(exc.orig).__name__ if exc.orig else 'OperationalError'}.\n"
            "   في الصندوق الرملي/Codespaces منافذُ Postgres محجوبة بجدارٍ ناري.\n"
            "   البديل الموثَّق: `scripts/db_bridge.py` عبر HTTPS:443 "
            "(يتطلّب SUPABASE_EDGE_FUNCTION_KEY في البيئة).",
            file=sys.stderr,
        )
        return 2

    _print_latency(row, args.since)
    _print_object_delivery(months)
    return 0


def _print_latency(row: Mapping[str, Any], since: str) -> None:
    turns = row["turns"] or 0
    print(f"\n══ زمن الوصول إلى أوّل ردٍّ (منذ {since}) ══")
    if not turns:
        print("  لا أدوار في النافذة — لا رقمَ يُدَّعى.")
        return

    for label in ("p50", "p75", "p95"):
        value = row[label]
        if value is None:
            print(f"  {label:<4} —  (لا بيانات كافية)")
        else:
            print(f"  {label:<4} {value:8.2f}s   {classify_latency(float(value)).value}")

    for caption, key in (
        (f"ضمن التدفّق (≤{FLOW_LIMIT_S:g}s)", "within_flow"),
        (f"فوق حدّ الانتباه (>{ATTENTION_LIMIT_S:g}s)", "over_attention"),
        ("بلا ردٍّ إطلاقاً", "never_answered"),
    ):
        count = row[key] or 0
        print(f"  {caption:<26} {count:5d} / {turns}  ({100 * count / turns:.1f}٪)")


def _print_object_delivery(months: Sequence[Mapping[str, Any]]) -> None:
    print("\n══ تسليم الكائن التفاعلي (شهراً بشهر) ══")
    print("  الشهر        ردود   بكائن   النسبة")
    total_replies = total_objects = 0
    for month in months:
        replies = month["replies"] or 0
        objects = month["with_object"] or 0
        total_replies += replies
        total_objects += objects
        pct = (100 * objects / replies) if replies else 0.0
        print(f"  {month['month']}  {replies:5d}  {objects:5d}   {pct:5.1f}٪")
    if total_replies:
        print(
            f"  {'الإجمالي':<11} {total_replies:5d}  {total_objects:5d}   "
            f"{100 * total_objects / total_replies:5.1f}٪"
        )
    print()


if __name__ == "__main__":
    sys.exit(main())
