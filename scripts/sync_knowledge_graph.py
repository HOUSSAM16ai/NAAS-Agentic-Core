#!/usr/bin/env python3
"""sync_knowledge_graph.py — مزامنة الشبكة المعرفية إلى knowledge_nodes/knowledge_edges (D-159).

جدولا ``knowledge_nodes``/``knowledge_edges`` كانا ZOMBIE (في REQUIRED_SCHEMA بلا أي
مستهلك — CLAUDE.md §6.6). هذا السكربت يجعلهما **مرآة حيّة** للـ Misconception Graph
الحتمي (العُقد + الحواف من ``semantic_property_skill``) على Supabase الإنتاجي عبر
جسر HTTPS:443 (``db_bridge.run_sql`` — المنافذ 5432/6543 محجوبة، CLAUDE.md §6.83).

المبادئ (D-159 — لا تُكسر بدون ADR):
1. **المسار الحي يبقى in-code حتمياً** — لا I/O لقاعدة البيانات في مسار الدور؛ الجداول
   مرآة للفحص/التحليل/الأدوات، والسكربت + بوّابة التكافؤ هما المستهلك الحقيقي.
2. **مزامنة idempotent**: UUIDv5 حتمي من اسم العقدة ⇒ ``ON CONFLICT (id) DO UPDATE``
   — إعادة التشغيل آمنة دائماً، لا صفوف مكرَّرة.
3. **بوّابة تكافؤ**: بعد المزامنة يُقارن عدد العُقد/الحواف على DB مع الكود — أي انحراف
   يُبلَّغ ويُرجِع exit=1.

Usage:
    set -a && . .devcontainer/secrets.env && set +a   # أو تصدير SUPABASE_EDGE_FUNCTION_KEY
    python3 scripts/sync_knowledge_graph.py           # مزامنة + تحقق تكافؤ
    python3 scripts/sync_knowledge_graph.py --dry-run # طباعة SQL فقط (بلا شبكة)
    python3 scripts/sync_knowledge_graph.py --verify  # تحقق تكافؤ فقط (بلا كتابة)
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

#: بصمة مصدر المزامنة — تعيش في metadata لكل صف (للفحص والتنظيف الآمن).
_SOURCE = "cogniforge_misconception_graph"


def _node_uuid(kind: str, name: str) -> str:
    """UUIDv5 حتمي — نفس الاسم ⇒ نفس المعرّف دائماً (idempotent upsert)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cogniforge:kg:{kind}:{name}"))


def _sql_str(value: str) -> str:
    """تهريب نصّ SQL (تكرار علامة الاقتباس المفردة)."""
    return "'" + (value or "").replace("'", "''") + "'"


def collect_graph() -> tuple[list[dict], list[dict]]:
    """يجمع العُقد والحواف من المصدر الحتمي الوحيد (semantic_property_skill)."""
    from app.services.skills.semantic_property_skill import (
        MISCONCEPTION_EDGES,
        MISCONCEPTION_GRAPH,
        PROPERTY_REGISTRY,
        _concept_definition,
    )

    concept_ids: set[str] = set()
    for spec in PROPERTY_REGISTRY.values():
        if spec.concept_id and spec.concept_id != "novel":
            concept_ids.add(spec.concept_id)
    for nodes in MISCONCEPTION_GRAPH.values():
        for node in nodes:
            concept_ids.add(node.bkt_concept)
    for edge in MISCONCEPTION_EDGES:
        concept_ids.add(edge.source)
        concept_ids.add(edge.target)
    concept_ids.update(MISCONCEPTION_GRAPH.keys())

    node_rows: list[dict] = []
    for cid in sorted(concept_ids):
        found = _concept_definition(cid)
        content = found[1] if found else ""
        node_rows.append(
            {
                "id": _node_uuid("concept", cid),
                "label": "concept",
                "name": cid,
                "content": content,
                "metadata": {"source": _SOURCE, "kind": "concept"},
            }
        )
    for concept_id, nodes in sorted(MISCONCEPTION_GRAPH.items()):
        for node in nodes:
            node_rows.append(
                {
                    "id": _node_uuid("misconception", node.id),
                    "label": "misconception",
                    "name": node.id,
                    "content": node.intervention,
                    "metadata": {
                        "source": _SOURCE,
                        "kind": "misconception",
                        "mtype": node.mtype,
                        "concept_id": concept_id,
                        "bkt_concept": node.bkt_concept,
                    },
                }
            )

    edge_rows: list[dict] = []
    for edge in MISCONCEPTION_EDGES:
        edge_rows.append(
            {
                "id": _node_uuid("edge", f"{edge.source}->{edge.relation}->{edge.target}"),
                "source_id": _node_uuid("concept", edge.source),
                "target_id": _node_uuid("concept", edge.target),
                "relation": edge.relation,
                "properties": {"source": _SOURCE},
            }
        )
    for concept_id, nodes in sorted(MISCONCEPTION_GRAPH.items()):
        for node in nodes:
            edge_rows.append(
                {
                    "id": _node_uuid("edge", f"{node.id}->misconception_of->{concept_id}"),
                    "source_id": _node_uuid("misconception", node.id),
                    "target_id": _node_uuid("concept", concept_id),
                    "relation": "misconception_of",
                    "properties": {"source": _SOURCE, "mtype": node.mtype},
                }
            )
    return node_rows, edge_rows


def build_sync_sql(node_rows: list[dict], edge_rows: list[dict]) -> tuple[str, str]:
    """يبني عبارتَي upsert (عقد ثم حواف) — statement واحد لكل جدول (idempotent)."""
    node_values = ",\n".join(
        "({id}, {label}, {name}, {content}, {meta}::jsonb)".format(
            id=_sql_str(r["id"]),
            label=_sql_str(r["label"]),
            name=_sql_str(r["name"]),
            content=_sql_str(r["content"]),
            meta=_sql_str(json.dumps(r["metadata"], ensure_ascii=False)),
        )
        for r in node_rows
    )
    nodes_sql = (
        'INSERT INTO "knowledge_nodes" ("id", "label", "name", "content", "metadata")\n'
        f"VALUES\n{node_values}\n"
        'ON CONFLICT ("id") DO UPDATE SET '
        '"label" = EXCLUDED."label", "name" = EXCLUDED."name", '
        '"content" = EXCLUDED."content", "metadata" = EXCLUDED."metadata";'
    )
    edge_values = ",\n".join(
        "({id}, {source_id}, {target_id}, {relation}, {props}::jsonb)".format(
            id=_sql_str(r["id"]),
            source_id=_sql_str(r["source_id"]),
            target_id=_sql_str(r["target_id"]),
            relation=_sql_str(r["relation"]),
            props=_sql_str(json.dumps(r["properties"], ensure_ascii=False)),
        )
        for r in edge_rows
    )
    edges_sql = (
        'INSERT INTO "knowledge_edges" ("id", "source_id", "target_id", "relation", "properties")\n'
        f"VALUES\n{edge_values}\n"
        'ON CONFLICT ("id") DO UPDATE SET '
        '"relation" = EXCLUDED."relation", "properties" = EXCLUDED."properties";'
    )
    return nodes_sql, edges_sql


_PARITY_SQL = (
    "SELECT "
    f"(SELECT COUNT(*) FROM \"knowledge_nodes\" WHERE \"metadata\"->>'source' = '{_SOURCE}') "
    "AS nodes, "
    f"(SELECT COUNT(*) FROM \"knowledge_edges\" WHERE \"properties\"->>'source' = '{_SOURCE}') "
    "AS edges;"
)


def _run(sql: str) -> dict:
    from db_bridge import run_sql

    status, body, ms = run_sql(sql, timeout=60.0)
    print(f"  [HTTP {status} · {ms:.0f}ms]")
    if status >= 300:
        print(body[:500], file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def verify_parity(node_rows: list[dict], edge_rows: list[dict]) -> bool:
    """بوّابة التكافؤ: عدد صفوف DB (لبصمة المصدر) == عدد الكود."""
    result = _run(_PARITY_SQL)
    data = (result.get("data") or [{}])[0]
    db_nodes, db_edges = int(data.get("nodes", -1)), int(data.get("edges", -1))
    ok = db_nodes == len(node_rows) and db_edges == len(edge_rows)
    print(
        f"parity: code nodes={len(node_rows)} edges={len(edge_rows)} | "
        f"db nodes={db_nodes} edges={db_edges} → {'✅ MATCH' if ok else '❌ DRIFT'}"
    )
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print SQL, no network")
    parser.add_argument("--verify", action="store_true", help="parity check only")
    args = parser.parse_args()

    node_rows, edge_rows = collect_graph()
    print(f"graph: {len(node_rows)} nodes, {len(edge_rows)} edges (source={_SOURCE})")

    if args.dry_run:
        nodes_sql, edges_sql = build_sync_sql(node_rows, edge_rows)
        print(nodes_sql)
        print(edges_sql)
        print(_PARITY_SQL)
        return
    if args.verify:
        sys.exit(0 if verify_parity(node_rows, edge_rows) else 1)

    nodes_sql, edges_sql = build_sync_sql(node_rows, edge_rows)
    print("syncing knowledge_nodes ...")
    _run(nodes_sql)
    print("syncing knowledge_edges ...")
    _run(edges_sql)
    sys.exit(0 if verify_parity(node_rows, edge_rows) else 1)


if __name__ == "__main__":
    main()
