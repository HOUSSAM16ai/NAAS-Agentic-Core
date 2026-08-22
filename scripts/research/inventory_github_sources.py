"""Inventory every GitHub repository URL currently present in repository text."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_JSON = ROOT / "docs/research/ALL_GITHUB_SOURCES_INVENTORY.json"
OUTPUT_MD = ROOT / "docs/research/ALL_GITHUB_SOURCES_INVENTORY.md"
URL_RE = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?")
IGNORE_PREFIXES = ("https://github.com/settings/", "https://github.com/sponsors/")


class InventoryRow(TypedDict):
    url: str
    category: str
    status_or_id: str
    occurrences: list[str]


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


def _is_scannable(path: Path) -> bool:
    relative = str(path.relative_to(ROOT))
    return path.is_file() and ".git" not in path.parts and relative not in GENERATED_ARTIFACTS


def _scan_file(path: Path, occurrences: dict[str, set[str]]) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    relative = str(path.relative_to(ROOT))
    for raw in URL_RE.findall(text):
        url = normalize(raw)
        if not any(url.startswith(prefix) for prefix in IGNORE_PREFIXES):
            occurrences[url].add(relative)


def _collect_occurrences() -> dict[str, set[str]]:
    occurrences: dict[str, set[str]] = defaultdict(set)
    for path in ROOT.rglob("*"):
        if _is_scannable(path):
            _scan_file(path, occurrences)
    return occurrences


def _build_rows(
    occurrences: dict[str, set[str]], backbone_ids: dict[str, str], standards: dict[str, str]
) -> list[InventoryRow]:
    rows: list[InventoryRow] = []
    for url in sorted(occurrences):
        category, status = classify(url, backbone_ids, standards)
        rows.append(
            {
                "url": url,
                "category": category,
                "status_or_id": status,
                "occurrences": sorted(occurrences[url]),
            }
        )
    return rows


def _source_maps() -> tuple[dict[str, str], dict[str, str]]:
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
    return backbone_ids, standards_map


def _category_counts(rows: list[InventoryRow]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["category"]] += 1
    return dict(sorted(counts.items()))


def _build_payload(rows: list[InventoryRow], counts: dict[str, int]) -> dict[str, object]:
    return {
        "generated_on": "2026-08-21",
        "method": "recursive scan of repository text files, normalize .git suffix, exclude github.com/settings and github.com/sponsors",
        "total_unique_repository_urls": len(rows),
        "counts_by_category": counts,
        "sources": rows,
    }


def _occurrences_display(row: InventoryRow) -> str:
    occurrences = row["occurrences"]
    seen = ", ".join(f"`{path}`" for path in occurrences[:4]) or "—"
    extra = f" (+{len(occurrences) - 4} more)" if len(occurrences) > 4 else ""
    return seen + extra


def _build_markdown(rows: list[InventoryRow], counts: dict[str, int]) -> str:
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
    lines.extend(
        f"| [{row['url']}]({row['url']}) | {row['category']} | `{row['status_or_id']}` | {_occurrences_display(row)} |"
        for row in rows
    )
    return "\n".join(lines) + "\n"


def _write_outputs(rows: list[InventoryRow]) -> dict[str, object]:
    counts = _category_counts(rows)
    OUTPUT_JSON.write_text(
        json.dumps(_build_payload(rows, counts), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(_build_markdown(rows, counts), encoding="utf-8")
    return {"total_unique_repository_urls": len(rows), "counts_by_category": counts}


def main() -> None:
    backbone_ids, standards = _source_maps()
    rows = _build_rows(_collect_occurrences(), backbone_ids, standards)
    print(json.dumps(_write_outputs(rows), ensure_ascii=False))


if __name__ == "__main__":
    main()
