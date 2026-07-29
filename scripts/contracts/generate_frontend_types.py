#!/usr/bin/env python3
"""generate_frontend_types — يولّد أنواع TypeScript من عقود OpenAPI المُلتزَمة (D-185).

## لماذا هذا السكربت موجود
المستودع يعلن «API-first 13/13» وكل خدمة لها عقد OpenAPI مُلتزَم ومحروس ببوّابة
`check_openapi_parity.py`. لكن **الواجهة** كانت جافاسكربت صرفاً تقرأ كل حقل نصّياً بلا
أي ربط بتلك العقود — فانحراف عقدٍ في خدمة لا يُكتشَف إلا في متصفّح الطالب. هذا يجعل
«API-first» صحيحاً في الخلفية ووهماً عند الحافة.

هذا المولِّد يسدّ الفجوة: يحوّل `components.schemas` من كل عقد إلى واجهات TypeScript،
فيصير انحراف العقد **خطأ ترجمة** يلتقطه `npm run typecheck` في CI.

## الاستخدام
    python scripts/contracts/generate_frontend_types.py            # يكتب الملف
    python scripts/contracts/generate_frontend_types.py --check    # يفشل عند الانحراف

المخرَج: `frontend/types/api.d.ts` (مُولَّد — لا يُحرَّر يدوياً).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "docs/contracts/openapi"
OUTPUT = REPO_ROOT / "frontend/types/api.d.ts"

#: عمق تعشيش أقصى — يمنع الانفجار على المخططات العَودية.
_MAX_DEPTH = 6

#: معرِّف TypeScript صالح — ما عداه يُقتبَس.
_IDENTIFIER_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")

_PRIMITIVES: dict[str, str] = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "null": "null",
}


def ts_type(schema: dict[str, Any], depth: int = 0, prefix: str = "") -> str:
    """يحوّل مخطط JSON Schema واحداً إلى تعبير نوع TypeScript.

    ``prefix`` هو بادئة الخدمة. الإحالات (``$ref``) **يجب** أن تحمل البادئة نفسها التي
    تحملها التصريحات، وإلّا أشارت إلى اسم غير موجود — وهو ما التقطه `tsc` فعلاً
    (`Cannot find name 'Stage1SceneResponse'`).
    """
    if depth > _MAX_DEPTH or not isinstance(schema, dict):
        return "unknown"
    if "$ref" in schema:
        return _ident(prefix, schema["$ref"].rsplit("/", 1)[-1])
    union = schema.get("anyOf") or schema.get("oneOf")
    if union:
        parts = [ts_type(item, depth + 1, prefix) for item in union]
        return " | ".join(dict.fromkeys(parts)) or "unknown"
    schema_type = schema.get("type")
    if schema_type == "array":
        return f"{ts_type(schema.get('items', {}), depth + 1, prefix)}[]"
    if schema_type == "object" or "properties" in schema:
        properties = schema.get("properties") or {}
        if not properties:
            return "Record<string, unknown>"
        required = set(schema.get("required") or ())
        body = "; ".join(
            f"{_prop_key(key)}{'' if key in required else '?'}: {ts_type(value, depth + 1, prefix)}"
            for key, value in properties.items()
        )
        return "{ " + body + " }"
    return _PRIMITIVES.get(str(schema_type), "unknown")


def _ident(prefix: str, name: str) -> str:
    """الاسم القانوني لنوعٍ داخل خدمة — بادئة الخدمة + اسم المخطط."""
    return f"{prefix}{name.replace('-', '_')}"


def _prop_key(key: str) -> str:
    """يقتبس اسم الخاصية إن لم يكن معرِّفاً صالحاً في TypeScript (مثل ``p99.9``)."""
    return key if _IDENTIFIER_RE.fullmatch(key) else json.dumps(key)


def _declaration(ident: str, rendered: str) -> str:
    """`interface` للأنواع الكائنية و`type` لغيرها — enum/سلسلة/سجلّ ليست واجهات."""
    if rendered.startswith("{"):
        return f"export interface {ident} {rendered}"
    return f"export type {ident} = {rendered};"


def _header() -> list[str]:
    """ترويسة الملف المُولَّد — تشرح المصدر وتمنع التحرير اليدوي."""
    return [
        "/**",
        " * api.d.ts — أنواع مُولَّدة من عقود OpenAPI المُلتزَمة (D-185).",
        " *",
        " * ⚠️ مُولَّد آلياً — لا تُحرّره يدوياً.",
        " * المصدر: docs/contracts/openapi/*.json",
        " * التوليد: python scripts/contracts/generate_frontend_types.py",
        " *",
        " * لماذا: المستودع «API-first» لكن الواجهة كانت تقرأ كل حقل نصّياً بلا أي ربط",
        " * بالعقود — فأي تغيير في عقد خدمة لم يكن يُكتشَف إلا في المتصفح. هذه الأنواع",
        " * تجعل انحراف العقد خطأ ترجمة في CI (`npm run typecheck`).",
        " */",
        "",
    ]


def _footer() -> list[str]:
    """عقد أحداث WebSocket — يعكس `shared/chat_protocol` (ليس في OpenAPI)."""
    return [
        "// ── WebSocket chat event contract (shared/chat_protocol) ─────────",
        "export type ChatEventType =",
        "    | 'conversation_init'",
        "    | 'assistant_delta'",
        "    | 'assistant_final'",
        "    | 'persisted'",
        "    | 'complete'",
        "    | 'error';",
        "",
        "export interface ChatEvent {",
        "    type: ChatEventType;",
        "    payload?: {",
        "        content?: string;",
        "        conversation_id?: number;",
        "        request_id?: string;",
        "        ui_component?: Record<string, unknown> | null;",
        "        code?: string;",
        "    };",
        "    persisted?: boolean;",
        "}",
        "",
    ]


def render() -> str:
    """يبني محتوى `api.d.ts` كاملاً من كل العقود المُلتزَمة."""
    lines = _header()
    emitted: set[str] = set()
    for path in sorted(CONTRACTS_DIR.glob("*-openapi.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        service = path.stem.replace("-openapi", "")
        schemas = (spec.get("components") or {}).get("schemas") or {}
        picked = {n: s for n, s in schemas.items() if not n.startswith("HTTPValidation")}
        if not picked:
            continue
        title = (spec.get("info") or {}).get("title", service)
        prefix = service.title().replace("_", "")
        lines.append(f"// ── {service} ({title}) ─────────")
        for name, schema in sorted(picked.items()):
            ident = _ident(prefix, name)
            if ident in emitted:
                continue
            emitted.add(ident)
            lines.append(_declaration(ident, ts_type(schema, prefix=prefix)))
        lines.append("")
    lines += _footer()
    return "\n".join(lines)


def main() -> int:
    """يكتب الأنواع، أو يفشل عند الانحراف في وضع `--check`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="لا يكتب؛ يفشل عند أي انحراف")
    args = parser.parse_args()

    rendered = render()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
        if current != rendered:
            print(f"❌ {OUTPUT.relative_to(REPO_ROOT)} is stale — regenerate it:")
            print("   python scripts/contracts/generate_frontend_types.py")
            return 1
        print(f"✅ {OUTPUT.relative_to(REPO_ROOT)} matches the committed OpenAPI contracts.")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    count = rendered.count("export interface") + rendered.count("export type")
    print(f"✅ wrote {OUTPUT.relative_to(REPO_ROOT)} ({count} interfaces)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
