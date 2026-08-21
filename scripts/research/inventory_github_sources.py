"""Inventory GitHub repository references in the project without changing source files."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_JSON = ROOT / "docs/research/ALL_GITHUB_SOURCES_INVENTORY.json"
OUTPUT_MD = ROOT / "docs/research/ALL_GITHUB_SOURCES_INVENTORY.md"
URL_RE = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?")
IGNORE_PREFIXES = ("https://github.com/settings/", "https://github.com/sponsors/")
GENERATED_ARTIFACTS = {
    "docs/research/ALL_GITHUB_SOURCES_INVENTORY.json",
    "docs/research/ALL_GITHUB_SOURCES_INVENTORY.md",
    "docs/research/full-source-inventory.txt",
    "docs/governance/SOURCE_ADOPTION_MATRIX.json",
    "docs/governance/SOURCE_ADOPTION_MATRIX.md",
}


def normalize(url: str) -> str:
    return url.removesuffix(".git")


def read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def classify(url: str, backbone_ids: dict[str, str], standards: dict[str, str]) -> tuple[str, str]:
    if url in backbone_ids:
        return "mandatory_reference_backbone", backbone_ids[url]
    if url in standards:
        return "external_standards_registry", standards[url]
    return "other_repository_reference_or_dependency", "unclassified"


def main() -> None:
    backbone = read_json(ROOT / "docs/governance/REFERENCE_BACKBONE.json")
    standards = read_json(ROOT / "docs/governance/EXTERNAL_STANDARDS_REGISTRY.json")
    backbone_ids = {
        normalize(str(row.get("repo"))): str(row.get("id"))
        for row in backbone.get("references", [])
        if isinstance(row, dict) and row.get("repo")
    }
    standards_map = {
        normalize(str(row.get("repo"))): f"{row.get('id')}:{row.get('status')}"
        for row in standards.get("sources", [])
        if isinstance(row, dict) and row.get("repo")
    }

    occurrences: dict[str, set[str]] = defaultdict(set)
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or str(path.relative_to(ROOT)) in GENERATED_ARTIFACTS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for raw in URL_RE.findall(text):
            url = normalize(raw)
            if any(url.startswith(prefix) for prefix in IGNORE_PREFIXES):
                continue
            occurrences[url].add(str(path.relative_to(ROOT)))

    rows = []
    for url in sorted(occurrences):
        category, status = classify(url, backbone_ids, standards_map)
        rows.append(
            {
                "url": url,
                "category": category,
                "status_or_id": status,
                "occurrences": sorted(occurrences[url]),
            }
        )

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["category"]] += 1
    payload = {
        "generated_on": "2026-08-21",
        "method": "recursive scan of repository text files, normalize .git suffix, exclude github.com/settings and github.com/sponsors",
        "total_unique_repository_urls": len(rows),
        "counts_by_category": dict(sorted(counts.items())),
        "sources": rows,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Complete GitHub Repository Source Inventory",
        "",
        "> This inventory is generated from the repository’s current text files. It counts unique GitHub repository URLs after normalizing `.git` suffixes and excludes account settings and sponsor links. It does **not** claim that every referenced repository is a runtime dependency or an adopted standard.",
        "",
        f"**Total unique repository URLs:** {len(rows)}",
        "",
        "| Category | Count | Meaning |",
        "|---|---:|---|",
        f"| Mandatory reference backbone | {counts.get('mandatory_reference_backbone', 0)} | Pinned sources in `REFERENCE_BACKBONE.json`. |",
        f"| External standards registry | {counts.get('external_standards_registry', 0)} | Sources already recorded in `EXTERNAL_STANDARDS_REGISTRY.json`, with ACTIVE/SEAM/ABSENT status. |",
        f"| Other repository references or dependencies | {counts.get('other_repository_reference_or_dependency', 0)} | Existing links requiring classification; this category must not be silently discarded. |",
        "",
        "## Sources",
        "",
        "| Repository | Category | Status or ID | Seen in |",
        "|---|---|---|---|",
    ]
    for row in rows:
        seen = ", ".join(f"`{path}`" for path in row["occurrences"][:4])
        if len(row["occurrences"]) > 4:
            seen += f" (+{len(row['occurrences']) - 4} more)"
        lines.append(f"| [{row['url']}]({row['url']}) | {row['category']} | `{row['status_or_id']}` | {seen} |")
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"total_unique_repository_urls": len(rows), "counts_by_category": dict(sorted(counts.items()))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
