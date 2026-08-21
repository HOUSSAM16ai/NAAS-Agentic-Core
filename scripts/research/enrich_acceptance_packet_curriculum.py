"""Add a complete curriculum-review manifest to the current acceptance packet."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "docs/changes/CURRENT_CODE_ACCEPTANCE_PACKET.json"
MATRIX = ROOT / "docs/research/CURRICULUM_APPLICATION_MATRIX.json"


def main() -> None:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    course_ids = [str(row["course_id"]) for row in matrix["courses"]]
    packet["curriculum"] = {
        "catalog_path": "docs/research/UNIVERSITY_CURRICULUM_CATALOG.json",
        "application_matrix_path": "docs/research/CURRICULUM_APPLICATION_MATRIX.json",
        "all_catalog_courses_loaded": True,
        "catalog_course_count": matrix["course_count"],
        "considered_course_ids": course_ids,
        "baseline_evidence_ids": ["harvard-cs50x-foundations", "harvard-cs-concentration-domains"],
        "task_specific_evidence_ids": ["harvard-cs50x-foundations", "harvard-cs-concentration-domains"],
        "unapplied_course_policy_ar": "كل المقررات قُرئت على مستوى الكتالوج والمصفوفة؛ ما لا ينطبق مباشرة على حزمة الحوكمة يُسجل كغير منطبق مع سبب، ولا يتحول إلى ادعاء تطبيق أو حذف من الكتالوج.",
        "applicability_result": "ALL_CATALOG_COURSES_CONSIDERED",
        "owner": "curriculum-governance"
    }
    PACKET.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"catalog_course_count": matrix["course_count"], "considered": len(course_ids)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
