"""Build the complete repository-source adoption matrix from the normalized inventory.

The builder is intentionally honest: the 15 backbone sources have declared
local roles, the pre-existing external-standard records retain their original
status, and every other existing repository URL is enrolled as
PENDING_CLASSIFICATION rather than silently ignored or falsely treated as
adopted. Pending sources cannot become runtime authority without a source card,
owner, primary-source review, and a new decision where required.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "docs/research/ALL_GITHUB_SOURCES_INVENTORY.json"
BACKBONE = ROOT / "docs/governance/REFERENCE_BACKBONE.json"
STANDARDS = ROOT / "docs/governance/EXTERNAL_STANDARDS_REGISTRY.json"
OUTPUT_JSON = ROOT / "docs/governance/SOURCE_ADOPTION_MATRIX.json"
OUTPUT_MD = ROOT / "docs/governance/SOURCE_ADOPTION_MATRIX.md"


class SourceRow(TypedDict):
    url: str
    source_id: str
    status: str
    purpose_ar: str
    application_ar: str
    local_evidence_paths: list[str]
    enforcers: list[str]
    runtime_allowed: bool
    primary_source_review: bool
    owner: str
    upgrade_condition_ar: str
    occurrences: list[str]


BACKBONE_APPLICATIONS: dict[str, dict[str, object]] = {
    "developer-roadmap": {
        "application_ar": "خارطة مسارات التعلم والتبعيات في onboarding وخريطة علوم الحاسوب.",
        "evidence": ["docs/architecture/CS_KNOWLEDGE_MAP.md", "docs/START_HERE.md"],
    },
    "coding-interview-university": {
        "application_ar": "تقوية الخوارزميات وهياكل البيانات والتفكير التحليلي قبل القرارات ذات الحمل العالي.",
        "evidence": ["app/core/foundations", "tests"],
    },
    "the-algorithms-python": {
        "application_ar": "مرجع تنفيذ ومقارنة؛ لا تدخل خوارزمية المنتج دون اختبار محلي وملكية واضحة.",
        "evidence": ["app/core/foundations", "tests"],
    },
    "system-design-primer": {
        "application_ar": "مراجعة التوسع والاتساق والتوافر وحدود الفشل والقرارات المعمارية.",
        "evidence": ["docs/architecture", "docs/contracts"],
    },
    "system-design-101": {
        "application_ar": "تدقيق تدفقات البروتوكولات والرسوم المعمارية لتقليل سوء الفهم بين الفرق والوكلاء.",
        "evidence": ["docs/architecture", "docs/contracts"],
    },
    "build-your-own-x": {
        "application_ar": "تجارب تعليمية معزولة لفهم البروتوكولات والأنظمة الأساسية دون إدخال تجارب غير ناضجة للإنتاج.",
        "evidence": [
            "docs/research/authoritative-foundations.md",
            "docs/architecture/EXTENSION_SEAMS.md",
        ],
    },
    "clean-code-javascript": {
        "application_ar": "مراجعات جودة الواجهة وتقليل التعقيد مع احترام عقود المنتج.",
        "evidence": ["frontend", ".pre-commit-config.yaml"],
    },
    "clean-code-book": {
        "application_ar": "مرجع حرفية ومناقشة للصيانة؛ لا يتحول إلى قانون منفصل عن الفوارض المحلية.",
        "evidence": ["docs/quality/standards.md"],
    },
    "freecodecamp": {
        "application_ar": "مسار تأسيسي ومراجع onboarding للمساهمين والمهارات العامة.",
        "evidence": ["docs/guides", "docs/START_HERE.md"],
    },
    "awesome": {
        "application_ar": "اكتشاف خيارات فقط؛ كل خيار يمر بتقييم أمني ومعماري مستقل.",
        "evidence": [
            "docs/research/authoritative-foundations.md",
            "docs/commercial/OFFER_CATALOG.json",
        ],
    },
    "free-programming-books": {
        "application_ar": "مكتبة تعلم متعددة اللغات لتغطية فجوات المسارات دون تضمين المواد تلقائياً.",
        "evidence": ["docs/guides", "docs/research"],
    },
    "public-apis": {
        "application_ar": "اكتشاف تكاملات محتملة؛ لا API خارجي يُفعّل بلا عقد وخصوصية ومراقبة.",
        "evidence": ["docs/commercial/OFFER_CATALOG.json", "docs/contracts"],
    },
    "browser-use": {
        "application_ar": "مرجع بحثي لتفاعل الوكلاء مع المتصفح؛ يبقى خلف الهوية والصلاحيات والموافقة والعزل.",
        "evidence": ["SECURITY.md", "docs/architecture/AGENTIC_ORCHESTRATION_DOCTRINE.md"],
    },
    "llms-from-scratch": {
        "application_ar": "فهم بنية النماذج وحدودها وكلفتها؛ لا يقرر الحقيقة أو الأرقام.",
        "evidence": [
            "shared/ai_models/model_chain.py",
            "docs/architecture/AGENTIC_DESIGN_PRINCIPLES.md",
        ],
    },
    "awesome-claude-skills": {
        "application_ar": "استكشاف أنماط المهارات؛ كل مهارة محلية تحتاج عقداً وقياساً وفارضاً.",
        "evidence": [
            ".claude/skills",
            "docs/governance/AGENT_SKILLS.json",
            "scripts/fitness/check_agent_skills_spec.py",
        ],
    },
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(url: str) -> str:
    return url.removesuffix(".git")


def _backbone_row(source: dict, ref: dict) -> SourceRow:
    identifier = str(ref["id"])
    app = BACKBONE_APPLICATIONS.get(identifier, {})
    return {
        "url": normalize(str(source["url"])),
        "source_id": identifier,
        "status": "MANDATORY_REFERENCE",
        "purpose_ar": ref["role_ar"],
        "application_ar": app.get("application_ar", "يجب أن يملك التطبيق بطاقة محلية قبل التفعيل."),
        "local_evidence_paths": app.get("evidence", []),
        "enforcers": ["check_reference_backbone.py", "check_agent_context.py"],
        "runtime_allowed": False,
        "primary_source_review": True,
        "owner": "architecture-governance",
        "upgrade_condition_ar": "لا تغيير في الدور أو التفعيل التشغيلي دون بطاقة جديدة وADR ومراجعة أمنية وأدلة محلية.",
        "occurrences": source["occurrences"],
    }


def _standard_row(source: dict, ref: dict) -> SourceRow:
    status = str(ref.get("status", "ABSENT"))
    return {
        "url": normalize(str(source["url"])),
        "source_id": str(ref.get("id", "external-standard")),
        "status": f"EXTERNAL_{status}",
        "purpose_ar": "المصدر مسجل في سجل المعايير الخارجية؛ ارجع إلى `read_ar` و`adopted_ar` و`rejected_ar` قبل أي استعارة.",
        "application_ar": str(ref.get("adopted_ar", "لا يوجد تبنٍ معلن.")),
        "local_evidence_paths": ref.get("code_paths", []),
        "enforcers": ref.get("enforcers", []) or ["check_external_standards.py"],
        "runtime_allowed": status == "ACTIVE",
        "primary_source_review": "لم يُقرأ الكود" not in str(ref.get("read_ar", "")),
        "owner": "external-standards-governance",
        "upgrade_condition_ar": str(
            ref.get("upgrade_condition_ar", "الحالة لا تتغير دون قرار مكتوب ومراجعة المصدر.")
        ),
        "occurrences": source["occurrences"],
    }


def _pending_row(source: dict) -> SourceRow:
    return {
        "url": normalize(str(source["url"])),
        "source_id": "unclassified",
        "status": "PENDING_CLASSIFICATION",
        "purpose_ar": "لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط.",
        "application_ar": "لا تطبيق أو تبعية جديدة حتى تُنشأ بطاقة فهم وتطبيق وتُراجع الملكية والترخيص والأمن.",
        "local_evidence_paths": [],
        "enforcers": ["check_source_adoption_matrix.py"],
        "runtime_allowed": False,
        "primary_source_review": False,
        "owner": "research-governance",
        "upgrade_condition_ar": "قراءة المصدر الأولي، تحديد الغرض، استخراج المعيار، تسمية التطبيق المحلي والفارض والمالك، ثم تحديث الحالة بقرار مراجَع.",
        "occurrences": source["occurrences"],
    }


def _build_rows(inventory: dict, backbone: dict, standards: dict) -> list[SourceRow]:
    backbone_by_url = {normalize(str(row["repo"])): row for row in backbone["references"]}
    standards_by_url = {normalize(str(row["repo"])): row for row in standards["sources"]}
    rows: list[SourceRow] = []
    for source in inventory["sources"]:
        url = normalize(str(source["url"]))
        if url in backbone_by_url:
            rows.append(_backbone_row(source, backbone_by_url[url]))
        elif url in standards_by_url:
            rows.append(_standard_row(source, standards_by_url[url]))
        else:
            rows.append(_pending_row(source))
    return rows


def _build_payload(rows: list[SourceRow]) -> dict[str, object]:
    return {
        "$schema_version": "1",
        "decision": "D-276",
        "purpose_ar": "لا يوجد مستودع أو رابط GitHub في المشروع خارج سجل الفهم؛ كل مصدر إما موصوف ومثبت أو معلن صراحة أنه قيد التصنيف ولا يجوز تجاوزه.",
        "non_bypassable_rules_ar": [
            "لا حذف من الجرد أو المصفوفة.",
            "لا مصدر PENDING_CLASSIFICATION يصبح تبعية أو معياراً تشغيلياً.",
            "لا مصدر ACTIVE بلا غرض وتطبيق محلي وفارض ودليل.",
            "لا تغيير حالة دون مراجعة مصدر أولي وقرار مناسب.",
        ],
        "required_card_fields": [
            "purpose_ar",
            "application_ar",
            "local_evidence_paths",
            "enforcers",
            "runtime_allowed",
            "primary_source_review",
            "upgrade_condition_ar",
            "owner",
        ],
        "generated_from": "docs/research/ALL_GITHUB_SOURCES_INVENTORY.json",
        "total_sources": len(rows),
        "sources": rows,
    }


def _status_counts(rows: list[SourceRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = row["status"]
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _build_markdown(rows: list[SourceRow], counts: dict[str, int]) -> str:
    descriptions = {
        "MANDATORY_REFERENCE": "Pinned reference backbone; must be respected and locally traced.",
        "EXTERNAL_ACTIVE": "Existing external-standard record marked ACTIVE; still governed by its registry.",
        "EXTERNAL_SEAM": "Explicit seam with no uncontrolled runtime adoption.",
        "EXTERNAL_ABSENT": "Explicitly absent or rejected; cannot enter silently.",
        "PENDING_CLASSIFICATION": "Existing URL requiring primary-source understanding before any new use.",
    }
    lines = [
        "# Source Adoption Matrix",
        "",
        "> This matrix enrolls every unique GitHub repository URL found in the project. It does not pretend that every URL is adopted. It makes uncertainty visible and blocks pending sources from becoming silent authority or runtime coupling.",
        "",
        f"**Total sources:** {len(rows)}",
        "",
        "| Status | Count | Rule |",
        "|---|---:|---|",
    ]
    lines.extend(
        f"| `{status}` | {count} | {descriptions.get(status, 'Governed status; see matrix JSON.')} |"
        for status, count in counts.items()
    )
    lines.extend(
        [
            "",
            "## Sources",
            "",
            "| Source | Status | Purpose / current boundary | Local evidence |",
            "|---|---|---|---|",
        ]
    )
    lines.extend(
        f"| [{row['url']}]({row['url']}) | `{row['status']}` | {row['purpose_ar'].replace('|', '\\|')} | {', '.join(f'`{p}`' for p in row['local_evidence_paths']) or '—'} |"
        for row in rows
    )
    return "\n".join(lines) + "\n"


def _write_outputs(rows: list[SourceRow]) -> dict[str, object]:
    counts = _status_counts(rows)
    OUTPUT_JSON.write_text(
        json.dumps(_build_payload(rows), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    OUTPUT_MD.write_text(_build_markdown(rows, counts), encoding="utf-8")
    return {"total_sources": len(rows), "counts": counts}


def main() -> None:
    rows = _build_rows(load(INVENTORY), load(BACKBONE), load(STANDARDS))
    print(json.dumps(_write_outputs(rows), ensure_ascii=False))


if __name__ == "__main__":
    main()
