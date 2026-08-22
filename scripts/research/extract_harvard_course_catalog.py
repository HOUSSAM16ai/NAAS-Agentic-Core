"""Extract every Harvard CS course entry from the saved official listing page.

The extractor preserves every distinct course code/title/description and records
all term offerings seen in the source snapshot. It is additive and does not
claim that a listing snapshot is the same as every course ever offered.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("/home/ubuntu/page_texts/seas.harvard.edu_computer-science_courses.md")
OUTPUT_JSON = ROOT / "docs/research/UNIVERSITY_CURRICULUM_CATALOG.json"
OUTPUT_MD = ROOT / "docs/research/UNIVERSITY_CURRICULUM_CATALOG.md"
COURSE_RE = re.compile(r"^COMPSCI\s+([0-9]+[A-Z]?)$", re.IGNORECASE)
TERM_RE = re.compile(r"^20[0-9]{2}\s+(Fall|Spring|Summer)$")


def nonempty(lines: list[str], index: int) -> str:
    cursor = index
    while cursor >= 0:
        value = lines[cursor].strip()
        if value:
            return value
        cursor -= 1
    return ""


def main() -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    entries: OrderedDict[str, dict[str, object]] = OrderedDict()
    for index, raw in enumerate(lines):
        match = COURSE_RE.match(raw.strip())
        if not match:
            continue
        code = match.group(1).upper()
        title = nonempty(lines, index - 1)
        # Locate the next term and faculty lines while staying inside this entry.
        cursor = index + 1
        while (
            cursor < len(lines)
            and not TERM_RE.match(lines[cursor].strip())
            and not COURSE_RE.match(lines[cursor].strip())
        ):
            cursor += 1
        term = (
            lines[cursor].strip()
            if cursor < len(lines) and TERM_RE.match(lines[cursor].strip())
            else "unknown"
        )
        description_start = cursor + 1
        # Descriptions end at COURSE WEBSITE or the next course code.
        description: list[str] = []
        while description_start < len(lines):
            value = lines[description_start].strip()
            if value == "COURSE WEBSITE" or COURSE_RE.match(value):
                break
            if value and not TERM_RE.match(value):
                description.append(value)
            description_start += 1
        description_text = " ".join(description).strip()
        key = f"COMPSCI {code}"
        if key not in entries:
            entries[key] = {
                "course_id": key,
                "title": title,
                "description": description_text,
                "offerings_seen": [],
                "source": "https://seas.harvard.edu/computer-science/courses",
                "catalog_status": "EXTRACTED_FROM_OFFICIAL_SNAPSHOT",
                "local_application_status": "UNMAPPED",
                "agent_requirement_status": "NOT_AUTHORITY_UNTIL_MAPPED",
            }
        row = entries[key]
        offerings = row["offerings_seen"]
        assert isinstance(offerings, list)
        if term not in offerings:
            offerings.append(term)
        if len(description_text) > len(str(row["description"])):
            row["description"] = description_text

    payload = {
        "$schema_version": "1",
        "decision": "D-278",
        "catalog_scope_ar": "كل المقررات المميزة في لقطة صفحة Harvard SEAS الرسمية، بما فيها الأساسية والمتقدمة والاختيارية والبحثية الظاهرة في الصفحة؛ لا تُحذف التكرارات الزمنية بل تُجمع كعروض لنفس المقرر.",
        "coverage_boundary_ar": "هذا كتالوج كامل للصفحة الرسمية التي تم التقاطها في 2026-08-21، وليس ادعاءً بأنه يشمل كل مقرر تاريخي أو كل مادة خارج الصفحة. أي مصدر إضافي يدخل كإضافة مع حالة تحقق.",
        "sources": [
            "https://seas.harvard.edu/computer-science/courses",
            "https://csadvising.seas.harvard.edu/concentration/requirements/",
            "https://cs50.harvard.edu/x/",
        ],
        "extraction_method": "parse saved official-page markdown; deduplicate by course code; retain longest description and all observed term offerings",
        "course_count": len(entries),
        "required_agent_fields": [
            "course_id",
            "title",
            "description",
            "source",
            "local_application_status",
            "agent_requirement_status",
            "owner",
            "mapped_change_types",
            "evidence_paths",
        ],
        "courses": list(entries.values()),
    }
    OUTPUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines_out = [
        "# Harvard Computer Science — Complete Official Listing Snapshot",
        "",
        "> This catalog contains every distinct Harvard CS course code extracted from the official course-listing snapshot. It preserves term offerings and explicitly marks every course as **unmapped** until a local application, owner, evidence path, and change-type mapping are added.",
        "",
        f"**Distinct course codes extracted:** {len(entries)}",
        "",
        "| Course | Title | Offerings seen | Local status |",
        "|---|---|---|---|",
    ]
    for row in entries.values():
        offerings = ", ".join(str(item) for item in row["offerings_seen"])
        title = str(row["title"]).replace("|", "\\|")
        lines_out.append(
            f"| `{row['course_id']}` | {title} | {offerings} | `{row['local_application_status']}` |"
        )
    OUTPUT_MD.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    print(
        json.dumps({"course_count": len(entries), "output": str(OUTPUT_JSON)}, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
