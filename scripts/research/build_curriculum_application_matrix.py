"""Build the task-specific application matrix over every catalogued course."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "docs/research/UNIVERSITY_CURRICULUM_CATALOG.json"
OUTPUT_JSON = ROOT / "docs/research/CURRICULUM_APPLICATION_MATRIX.json"
OUTPUT_MD = ROOT / "docs/research/CURRICULUM_APPLICATION_MATRIX.md"

RULES: list[tuple[str, str, str]] = [
    ("privacy|fairness|validity|crypt|security|ethic|privacy", "security_privacy_trust", "أي تغيير يتعامل مع بيانات أو نماذج أو قرارات حساسة يمر عبر الخصوصية والإنصاف والتهديدات والحدود."),
    ("machine learning|artificial intelligence|reinforcement|data science|neural|generative|learning methods|diffusion", "ai_ml_data", "أي تغيير نموذج أو بيانات أو تقييم يمر عبر فرضية، بيانات، تقييم، حدود تعميم، وكلفة."),
    ("algorithm|graph theory|computational|complexity|information theory|probabilistic|optimization", "algorithms_formal_reasoning", "أي منطق أو قرار أو فهرسة أو تحسين يثبت الصحة والتعقيد وحدود المسألة."),
    ("system|architecture|hardware|network|computing at scale|high performance|parallel|operating", "systems_performance", "أي خدمة أو تخزين أو نشر أو تزامن أو أداء يثبت الحدود والفشل والموارد والمراقبة."),
    ("programming language|compiler|abstraction|programming and machine|software", "software_language_runtime", "أي تغيير لغة أو runtime أو API أو تجريد يثبت العقد والأنواع والتوافق والاختبارات."),
    ("design|interactive|visualization|graphics|usable", "product_interface_human_factors", "أي واجهة أو تجربة أو تصور يثبت حاجة المستخدم وقابلية الاستخدام والنتيجة لا الزينة."),
    ("education|learning experience|k–12|k-12", "education_workforce", "أي قدرة تعليمية تقيس التعلم الحقيقي، انتقال المهارة، وحاجات سوق الشغل دون ادعاء أثر غير مثبت."),
    ("economics|democracy|world|market", "socioeconomic_governance", "أي قرار سوقي أو حوكمي يوضح أصحاب المصلحة والحوافز والمخاطر والأثر."),
    ("reading and research|special topics|thesis", "research_innovation", "أي بحث أو ابتكار يحدد الفرضية والمنهج والدليل والحدود وخطة التحويل إلى قدرة."),
]


def tags_for(text: str) -> list[tuple[str, str]]:
    lowered = text.lower()
    selected = [(tag, principle) for keywords, tag, principle in RULES if any(token in lowered for token in keywords.split("|"))]
    if not selected:
        selected = [("software_quality_and_proof", "أي تغيير يثبت الصحة والاختبار والعقد والتشغيل والرجوع الآمن.")]
    seen: set[str] = set()
    return [(tag, principle) for tag, principle in selected if not (tag in seen or seen.add(tag))]


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for course in catalog["courses"]:
        text = f"{course['course_id']} {course['title']} {course['description']}"
        tags = tags_for(text)
        rows.append(
            {
                "course_id": course["course_id"],
                "title": course["title"],
                "source": course["source"],
                "domain_tags": [tag for tag, _ in tags],
                "principles_ar": [principle for _, principle in tags],
                "change_types": ["code", "architecture", "agent", "research", "commercial"],
                "required_for_all_code": course["course_id"] == "COMPSCI 50",
                "status": "CATALOGED_PROVISIONAL_LOCAL_MAP",
                "authority_rule_ar": "لا يُعد هذا المقرر دليلاً مطبقاً حتى يذكره change packet للمهمة، ويحدد موضع التطبيق والاختبار والمالك.",
                "evidence_paths": ["docs/research/UNIVERSITY_CURRICULUM_CATALOG.json", "docs/research/authoritative-foundations.md"],
                "owner": "curriculum-governance",
            }
        )
    payload = {
        "$schema_version": "1",
        "decision": "D-278",
        "catalog_source": "docs/research/UNIVERSITY_CURRICULUM_CATALOG.json",
        "coverage_ar": "كل مقرر مميز في الكتالوج الرسمي له بطاقة تطبيق؛ لا توجد خانة UNMAPPED أو مقرر مخفي. الخريطة الأولية لا تدعي أن كل مبدأ نُفذ في المنتج؛ التنفيذ يثبت في packet المهمة.",
        "baseline_for_every_code_change": ["harvard-cs50x-foundations", "harvard-cs-concentration-domains", "nist-ssdf-1.1", "owasp-agent-security"],
        "required_card_fields": ["course_id", "domain_tags", "principles_ar", "change_types", "status", "authority_rule_ar", "evidence_paths", "owner"],
        "course_count": len(rows),
        "courses": rows,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for row in rows:
        for tag in row["domain_tags"]:
            counts[tag] = counts.get(tag, 0) + 1
    md = [
        "# Curriculum Application Matrix",
        "",
        "> Every course extracted from the official Harvard listing has a visible application card. The map is deliberately provisional: it prevents omission and gives agents a task gate, but it does not fabricate proof that the course content has been implemented.",
        "",
        f"**Courses covered:** {len(rows)}",
        "",
        "| Domain | Courses |",
        "|---|---:|",
    ]
    for tag, count in sorted(counts.items()):
        md.append(f"| `{tag}` | {count} |")
    md.extend(["", "| Course | Domains | Required for all code | Status |", "|---|---|---:|---|"])
    for row in rows:
        md.append(f"| `{row['course_id']}` {row['title']} | {', '.join(row['domain_tags'])} | {'yes' if row['required_for_all_code'] else 'task-specific'} | `{row['status']}` |")
    OUTPUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"course_count": len(rows), "domain_counts": dict(sorted(counts.items()))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
