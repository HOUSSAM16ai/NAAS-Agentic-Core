"""يقيس ثِقَل كلّ دستورٍ مقابل جرّه — «خفيف» رقماً لا انطباعاً (D-284).

**لماذا هذه الأداة:** جهاز الحوكمة في هذا المستودع بلغ **٧٠٪** من حجم كود المنتج
(١٣٦ ألف سطر مقابل ١٩٤ ألفاً). و«خفيف» ليس عدد الأسطر بل **كم شيئاً يجب أن تعرفه
لتغيّر سطراً واحداً** — ولا شيء كان يقيس ذلك.

⛔ **وما ليس المشكلة، قِيس فاستُبعِد:** ليست «قوانين بلا فوارض» — السجلّ يُظهر كلّ
دستورٍ بفارضه. العطب هو الكلفة المعرفية، لا الانضباط.

**ما تقيسه:** لكلّ دستورٍ في `CONSTITUTION_REGISTRY.json` — كلفتَه بالأسطر (قسمه في
`CLAUDE.md` + وثائق قانونه + وثائق حالته) مقابل **استشهاداته الحيّة** بمُعرَّفه
(`D-NNN`) في كود المنتج والبوّابات والاختبارات. والنسبة `traction_per_kloc` هي
الخلاصة: دستورٌ يكلّف ثلاثة آلاف سطرٍ ويُستشهَد به مرّةً **يُثقِل ولا يوجّه**.

⛔ **حدُّ هذا القياس، ويُقال قبل أن يُقرأ الجدول:** قلّةُ الاستشهاد **ليست حكماً بانعدام
القيمة**. قانونٌ وقائيّ يعمل **بمنعه لا بذكره** (حظرُ نموذجٍ بعينه مثلاً) يظهر هنا
بجرٍّ منخفض وهو من أنفع ما في المستودع. الأداة تعرض الرقم ولا تُصدر حكماً.

⛔ **قراءةٌ محضة:** لا تُعدِّل ملفّاً، ولا تحذف قسماً، ولا تلمس وثيقة قانون. القرار
للمالك (D-266 L9).

    python scripts/research/measure_governance_weight.py           # جدولٌ مقروء
    python scripts/research/measure_governance_weight.py --json    # تقريرٌ خام
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs/governance/CONSTITUTION_REGISTRY.json"
CONSTITUTION = ROOT / "CLAUDE.md"
REPORT = ROOT / "docs/research/GOVERNANCE_WEIGHT_REPORT.json"

#: أين يُقاس «الجرّ». كود المنتج أوّلاً — استشهادٌ هناك يعني أنّ القانون غيّر قراراً.
CITATION_SCOPES: dict[str, tuple[str, ...]] = {
    "code": ("app", "shared", "microservices", "naas_verifier"),
    "gate": ("scripts",),
    "test": ("tests",),
}

#: ⚠️ لا يُقاس الاستشهاد داخل الحوكمة نفسها: دستورٌ يذكر نفسه في وثيقته ليس جرّاً.
EXCLUDED_FROM_CITATIONS = ("docs", ".memory")


class MeasureError(RuntimeError):
    """مُدخَلٌ مفقود أو مكسور — ⛔ يُرفَع صراحةً ولا يُعاد جدولٌ ناقصٌ يبدو كاملاً."""


def _load_registry() -> list[dict[str, object]]:
    if not REGISTRY.is_file():
        raise MeasureError(f"constitution registry not found: {REGISTRY.relative_to(ROOT)}")
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = payload.get("constitutions")
    if not isinstance(rows, list) or not rows:
        raise MeasureError("registry declares no constitutions")
    return rows


def _section_line_counts() -> dict[str, int]:
    """أسطر كلّ قسم `## 0.N.` في الدستور — من عنوانه إلى العنوان التالي."""
    lines = CONSTITUTION.read_text(encoding="utf-8").splitlines()
    heading = re.compile(r"^## (0(?:\.\d+)?)\.")
    starts: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        match = heading.match(line)
        if match:
            starts.append((match.group(1), index))

    counts: dict[str, int] = {}
    for position, (section, start) in enumerate(starts):
        end = starts[position + 1][1] if position + 1 < len(starts) else len(lines)
        counts[section] = end - start
    return counts


def _line_count(relative: str) -> int:
    """أسطر ملفٍّ مُعلَن. ⛔ ملفٌّ غائب يُرفَع به خطأ — الصفر الصامت يُقرأ خفّة."""
    path = ROOT / relative
    if not path.is_file():
        raise MeasureError(f"declared document does not exist: {relative}")
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _citation_counts(identifier: str) -> dict[str, int]:
    """كم مرّةً يُذكَر `D-NNN` خارج طبقة الحوكمة نفسها."""
    pattern = re.compile(rf"\b{re.escape(identifier)}\b")
    counts = dict.fromkeys(CITATION_SCOPES, 0)
    for scope, roots in CITATION_SCOPES.items():
        for root in roots:
            base = ROOT / root
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*")):
                if not path.is_file() or path.suffix not in {".py", ".js", ".jsx", ".ts", ".tsx"}:
                    continue
                relative = path.relative_to(ROOT)
                if relative.parts and relative.parts[0] in EXCLUDED_FROM_CITATIONS:
                    continue
                counts[scope] += len(
                    pattern.findall(path.read_text(encoding="utf-8", errors="replace"))
                )
    return counts


def measure() -> dict[str, object]:
    """يُعيد التقرير كاملاً. حتميّ: نفس الشجرة تُعطي نفس الأرقام دائماً."""
    sections = _section_line_counts()
    rows: list[dict[str, object]] = []

    for entry in _load_registry():
        section = str(entry.get("section", ""))
        identifier = str(entry.get("id", ""))
        if not section or not identifier:
            raise MeasureError(f"registry row missing section/id: {entry}")
        if section not in sections:
            raise MeasureError(
                f"{identifier}: registry names section {section} which CLAUDE.md does not have"
            )

        law_lines = sum(_line_count(str(doc)) for doc in entry.get("law_docs", []))
        status_lines = sum(_line_count(str(doc)) for doc in entry.get("status_docs", []))
        claude_lines = sections[section]
        cost = claude_lines + law_lines + status_lines

        citations = _citation_counts(identifier)
        total_citations = sum(citations.values())
        rows.append(
            {
                "section": section,
                "id": identifier,
                "title_ar": entry.get("title_ar", ""),
                "claude_md_lines": claude_lines,
                "law_doc_lines": law_lines,
                "status_doc_lines": status_lines,
                "total_cost_lines": cost,
                "citations": citations,
                "total_citations": total_citations,
                # الجرّ لكلّ ألف سطر كلفة — القسمة على الكلفة لا على العدد المطلق،
                # وإلّا بدا الدستور الضخم رابحاً لمجرّد ضخامته.
                "traction_per_kloc": round(total_citations / (cost / 1000), 2) if cost else 0.0,
            }
        )

    rows.sort(key=lambda row: (row["traction_per_kloc"], -row["total_cost_lines"]))
    total_cost = sum(int(row["total_cost_lines"]) for row in rows)
    return {
        "$schema_version": "1",
        "decision": "D-284",
        "purpose_ar": (
            "كلفة كل دستورٍ بالأسطر مقابل استشهاداته الحيّة. ⛔ قلّةُ الاستشهاد ليست "
            "حكماً بانعدام القيمة: قانونٌ وقائيّ يعمل بمنعه لا بذكره."
        ),
        "constitutions_measured": len(rows),
        "total_cost_lines": total_cost,
        "citation_scopes": {scope: list(roots) for scope, roots in CITATION_SCOPES.items()},
        "rows_sorted_by_traction_ascending": rows,
    }


def _render(report: dict[str, object]) -> str:
    rows = report["rows_sorted_by_traction_ascending"]
    assert isinstance(rows, list)
    lines = [
        f"دساتير مقيسة : {report['constitutions_measured']}",
        f"كلفة إجمالية : {report['total_cost_lines']} سطراً",
        "",
        f"{'القسم':<7}{'المُعرَّف':<9}{'كلفة':>7}{'كود':>6}{'بوّابة':>8}{'اختبار':>8}{'جرّ/kloc':>10}",
        "─" * 55,
    ]
    for row in rows:
        citations = row["citations"]
        lines.append(
            f"{row['section']:<7}{row['id']:<9}{row['total_cost_lines']:>7}"
            f"{citations['code']:>6}{citations['gate']:>8}{citations['test']:>8}"
            f"{row['traction_per_kloc']:>10}"
        )
    lines += [
        "",
        "⛔ قلّةُ الجرّ ليست حكماً بانعدام القيمة — قانونٌ وقائيّ يعمل بمنعه لا بذكره.",
        "⛔ هذه قراءةٌ محضة: لا حذف ولا دمج. القرار للمالك.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="اكتب التقرير الخام إلى القرص")
    args = parser.parse_args(argv)

    try:
        report = measure()
    except MeasureError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.json:
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"✅ {REPORT.relative_to(ROOT)}")
    else:
        print(_render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
