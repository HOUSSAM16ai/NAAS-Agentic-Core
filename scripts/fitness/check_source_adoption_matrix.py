"""Enforce complete, non-bypassable coverage of discovered GitHub sources."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs/governance/SOURCE_ADOPTION_MATRIX.json"
INVENTORY = ROOT / "docs/research/ALL_GITHUB_SOURCES_INVENTORY.json"
BACKBONE = ROOT / "docs/governance/REFERENCE_BACKBONE.json"
VALID_STATUSES = {
    "MANDATORY_REFERENCE",
    "EXTERNAL_ACTIVE",
    "EXTERNAL_SEAM",
    "EXTERNAL_ABSENT",
    "PENDING_CLASSIFICATION",
}
FAILURES: list[str] = []


def fail(message: str) -> None:
    FAILURES.append(message)
    print(f"❌ {message}")


def passed(message: str) -> None:
    print(f"✅ {message}")


def load(path: Path, label: str) -> dict | None:
    if not path.is_file():
        fail(f"{label} missing: {path.relative_to(ROOT)}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{label} is invalid JSON: {exc}")
        return None
    if not isinstance(payload, dict):
        fail(f"{label} root must be an object")
        return None
    return payload


def check_url(url: str, label: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        fail(f"{label}: not an HTTPS GitHub repository URL: {url}")
    pieces = parsed.path.strip("/").split("/")
    if len(pieces) != 2 or not all(pieces):
        fail(f"{label}: URL must identify github.com/owner/name: {url}")


def main() -> int:
    matrix = load(MATRIX, "source adoption matrix")
    inventory = load(INVENTORY, "source inventory")
    backbone = load(BACKBONE, "reference backbone")
    if matrix is None or inventory is None or backbone is None:
        return 1

    inventory_urls = {str(row.get("url", "")) for row in inventory.get("sources", []) if isinstance(row, dict)}
    rows = matrix.get("sources", [])
    if not isinstance(rows, list) or not rows:
        fail("matrix sources must be a non-empty list")
        return 1
    matrix_urls = {str(row.get("url", "")) for row in rows if isinstance(row, dict)}
    if matrix_urls != inventory_urls:
        fail(f"matrix/inventory mismatch: matrix-only={sorted(matrix_urls - inventory_urls)}, inventory-only={sorted(inventory_urls - matrix_urls)}")
    if len(rows) != len(matrix_urls):
        fail("matrix contains duplicate source URLs")
    if matrix.get("total_sources") != len(inventory_urls):
        fail("matrix total_sources does not equal inventory cardinality")

    backbone_urls = {str(row.get("repo", "")).removesuffix(".git") for row in backbone.get("references", []) if isinstance(row, dict)}
    mandatory_rows = [row for row in rows if isinstance(row, dict) and row.get("status") == "MANDATORY_REFERENCE"]
    if {str(row.get("url", "")) for row in mandatory_rows} != backbone_urls:
        fail("every backbone repository must appear exactly once as MANDATORY_REFERENCE")

    required_fields = matrix.get("required_card_fields", [])
    if not isinstance(required_fields, list) or len(required_fields) < 8:
        fail("matrix must declare its complete source-card field contract")

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            fail(f"source[{index}] must be an object")
            continue
        label = f"source[{index}]"
        url = str(row.get("url", ""))
        check_url(url, label)
        status = row.get("status")
        if status not in VALID_STATUSES:
            fail(f"{label}: invalid status {status!r}")
        for field in ("purpose_ar", "application_ar", "upgrade_condition_ar", "owner"):
            if not str(row.get(field, "")).strip():
                fail(f"{label}: missing `{field}`")
        evidence = row.get("local_evidence_paths", [])
        if not isinstance(evidence, list):
            fail(f"{label}: local_evidence_paths must be a list")
        for path in evidence:
            if not (ROOT / str(path)).exists():
                fail(f"{label}: evidence path does not exist: {path}")
        enforcers = row.get("enforcers", [])
        if not isinstance(enforcers, list) or not enforcers:
            fail(f"{label}: every source must name at least one enforcer")
        for enforcer in enforcers:
            candidate_paths = (
                ROOT / "scripts/fitness" / str(enforcer),
                ROOT / ".github/scripts" / str(enforcer),
                ROOT / str(enforcer),
            )
            if not any(path.exists() for path in candidate_paths):
                fail(f"{label}: named enforcer does not exist: {enforcer}")
        if row.get("runtime_allowed") is True and status not in {"MANDATORY_REFERENCE", "EXTERNAL_ACTIVE"}:
            fail(f"{label}: runtime_allowed is only possible for governed active statuses")
        if status == "PENDING_CLASSIFICATION":
            if row.get("runtime_allowed") is not False:
                fail(f"{label}: pending source must be runtime-disabled")
            if row.get("primary_source_review") is not False:
                fail(f"{label}: pending source cannot claim primary-source review")
            if row.get("source_id") != "unclassified":
                fail(f"{label}: pending source must remain explicitly unclassified")

    if FAILURES:
        print(f"\n❌ Source adoption matrix gate failed: {len(FAILURES)} violation(s)")
        return 1
    passed(f"Complete source coverage is enforced: {len(rows)} unique repositories, no invisible source, and pending sources are blocked from runtime authority.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
