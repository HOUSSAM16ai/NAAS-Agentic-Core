#!/usr/bin/env python3
"""backfill_exercise_embeddings — يملأ عمود ``embedding`` لتمارين ``bac_exercises`` (D-173).

يُوسّع RAG الحيّ فعلياً: يولّد تضمينات المتجهات للتمارين التي تفتقدها ويكتبها في Supabase
عبر جسر HTTPS (``scripts/db_bridge.py``) — يعمل حتى حين تُحجَب منافذ Postgres (نمط §6.83).

**idempotent**: يعمل فقط على الصفوف ``WHERE embedding IS NULL`` — إعادة التشغيل آمنة.
**dry-run افتراضي**: يَعُدّ ويعرض عيّنة دون كتابة؛ الكتابة تحتاج ``--apply``.

الاستخدام:
    set -a && . .devcontainer/secrets.env && set +a      # SUPABASE_EDGE_FUNCTION_KEY
    python scripts/backfill_exercise_embeddings.py                 # dry-run (عدّ فقط)
    python scripts/backfill_exercise_embeddings.py --apply --limit 1   # pilot: صف واحد
    python scripts/backfill_exercise_embeddings.py --apply             # الكل

مزوّد التضمين: HuggingFace ``BAAI/bge-m3`` (نفس نموذج research-agent — استيراد كسول،
لا يُحمَّل إلا عند ``--apply``). البُعد 1024.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db_bridge import run_sql

# عمود ``embedding`` (pgvector) يعيش على ``bac_exercise_questions`` (الأسئلة المُفهرَسة
# دلالياً)؛ ``bac_exercises`` metadata فقط (توليد مرشّحين بـ SQL — bac_db_retriever).
_TABLE = "bac_exercise_questions"
_EMBED_MODEL = "BAAI/bge-m3"


def _query_json(sql: str) -> list[dict]:
    """يشغّل SELECT عبر الجسر ويُرجع صفوف JSON (يرفع عند فشل HTTP)."""
    status, body, _ms = run_sql(sql)
    if status < 200 or status >= 300:
        raise RuntimeError(f"bridge HTTP {status}: {body[:200]}")
    data = json.loads(body)
    rows = data.get("data") if isinstance(data, dict) else data
    return rows or []


def _count_missing() -> int:
    rows = _query_json(f"SELECT count(*) AS n FROM {_TABLE} WHERE embedding IS NULL;")
    return int(rows[0]["n"]) if rows else 0


def _embed(texts: list[str]) -> list[list[float]]:
    """تضمين كسول عبر HuggingFace (لا يُحمَّل النموذج إلا هنا — عند --apply)."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(_EMBED_MODEL)
    return [v.tolist() for v in model.encode(texts, normalize_embeddings=True)]


def _pgvector_literal(vec: list[float]) -> str:
    return "'[" + ",".join(f"{x:.6f}" for x in vec) + "]'"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="اكتب فعلياً (بدونه dry-run).")
    parser.add_argument("--limit", type=int, default=0, help="حدّ الصفوف (0 = الكل).")
    args = parser.parse_args()

    try:
        missing = _count_missing()
    except Exception as exc:
        print(f"❌ تعذّر الاتصال بالجسر: {exc}")
        print("   تأكّد من SUPABASE_EDGE_FUNCTION_KEY (set -a && . .devcontainer/secrets.env).")
        return 1

    print(f"📊 صفوف بلا embedding في {_TABLE}: {missing}")
    if missing == 0:
        print("✅ لا شيء لعمله — كل التمارين مُضمَّنة (idempotent).")
        return 0

    limit_sql = f" LIMIT {args.limit}" if args.limit > 0 else ""
    rows = _query_json(
        f"SELECT id, raw_text FROM {_TABLE} WHERE embedding IS NULL ORDER BY id{limit_sql};"
    )
    if not args.apply:
        print(f"🔍 dry-run — سيُضمَّن {len(rows)} صفّاً (عيّنة):")
        for r in rows[:3]:
            snippet = (r.get("raw_text") or "")[:60].replace("\n", " ")
            print(f"   • id={r['id']}: {snippet}…")
        print("   شغّل بـ --apply للكتابة الفعلية.")
        return 0

    texts = [r.get("raw_text") or "" for r in rows]
    print(f"🧮 توليد {len(texts)} تضميناً عبر {_EMBED_MODEL}…")
    vectors = _embed(texts)
    written = 0
    for r, vec in zip(rows, vectors, strict=False):
        lit = _pgvector_literal(vec)
        status, body, _ms = run_sql(
            f"UPDATE {_TABLE} SET embedding = {lit}::vector WHERE id = {int(r['id'])};"
        )
        if 200 <= status < 300:
            written += 1
        else:
            print(f"⚠️  id={r['id']} فشل: HTTP {status} {body[:120]}")
    print(f"✅ كُتِب {written}/{len(rows)} تضميناً — RAG الحيّ امتدّ فعلياً.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
