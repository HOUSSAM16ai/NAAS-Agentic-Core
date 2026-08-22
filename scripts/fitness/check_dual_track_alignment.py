"""Validate the engineering/production alignment contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALIGNMENT = ROOT / "docs/governance/DUAL_TRACK_ALIGNMENT.json"
OFFERS = ROOT / "docs/commercial/OFFER_CATALOG.json"
SOURCES = ROOT / "docs/governance/SOURCE_ADOPTION_MATRIX.json"
CURRICULUM = ROOT / "docs/research/CURRICULUM_APPLICATION_MATRIX.json"
EVIDENCE = ROOT / "docs/research/EVIDENCE_CATALOG.json"
FAILURES: list[str] = []
STATUS_RANK = {
    "PROPOSED": 0,
    "DISCOVERY": 1,
    "OFFER_READY": 2,
    "PILOT": 3,
    "PAID_PROOF": 4,
    "REPEATABLE": 5,
}
ENGINEERING_RELEASE_STATES = {"PILOT_READY", "PAID_PROOF", "REPEATABLE"}


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
        fail(f"{label} invalid JSON: {exc}")
        return None
    return payload if isinstance(payload, dict) else None


def main() -> int:
    alignment = load(ALIGNMENT, "dual-track alignment")
    offers = load(OFFERS, "offer catalog")
    sources = load(SOURCES, "source matrix")
    curriculum = load(CURRICULUM, "curriculum matrix")
    evidence = load(EVIDENCE, "evidence catalog")
    if any(value is None for value in (alignment, offers, sources, curriculum, evidence)):
        return 1
    assert (
        alignment is not None
        and offers is not None
        and sources is not None
        and curriculum is not None
        and evidence is not None
    )

    for section in ("engineering_track", "production_track", "shared_alignment_contract"):
        if not isinstance(alignment.get(section), dict):
            fail(f"missing alignment section: {section}")
    contract = alignment.get("shared_alignment_contract", {})
    required_fields = contract.get("required_fields", [])
    if not isinstance(required_fields, list) or len(required_fields) < 10:
        fail("shared alignment contract must declare at least ten required fields")

    offer_rows = offers.get("offers", [])
    offer_ids = {str(row.get("id")) for row in offer_rows if isinstance(row, dict)}
    source_by_id = {
        str(row.get("source_id")): row
        for row in sources.get("sources", [])
        if isinstance(row, dict)
    }
    curriculum_domains = {
        str(domain)
        for row in curriculum.get("courses", [])
        if isinstance(row, dict)
        for domain in row.get("domain_tags", [])
    }
    evidence_ids = {
        str(row.get("id")) for row in evidence.get("evidence", []) if isinstance(row, dict)
    }
    records = alignment.get("alignment_records", [])
    if not isinstance(records, list) or not records:
        fail("alignment_records must be non-empty")
    seen: set[str] = set()
    for index, row in enumerate(records, start=1):
        if not isinstance(row, dict):
            fail(f"alignment record[{index}] must be an object")
            continue
        identifier = str(row.get("alignment_id", ""))
        if not identifier or identifier in seen:
            fail(f"alignment record[{index}] has missing or duplicate alignment_id")
        seen.add(identifier)
        for field in (
            "capability",
            "offer_id",
            "buyer_or_user",
            "paid_problem_or_social_problem",
            "owner",
            "next_gate",
        ):
            if not str(row.get(field, "")).strip():
                fail(f"alignment {identifier or index} missing `{field}`")
        offer_id = str(row.get("offer_id", ""))
        if offer_id not in offer_ids:
            fail(f"alignment {identifier} references unknown offer: {offer_id}")
        standards = row.get("standards", [])
        if not isinstance(standards, list) or not standards:
            fail(f"alignment {identifier} must name source standards")
        for source_id in standards:
            source = source_by_id.get(str(source_id))
            if source is None:
                fail(f"alignment {identifier} references unknown source: {source_id}")
            elif source.get("status") in {"PENDING_CLASSIFICATION", "EXTERNAL_ABSENT"}:
                fail(f"alignment {identifier} cannot use blocked source: {source_id}")
        domains = row.get("curriculum_domains", [])
        if not isinstance(domains, list) or not domains:
            fail(f"alignment {identifier} must name curriculum domains")
        for domain in domains:
            if str(domain) not in curriculum_domains:
                fail(f"alignment {identifier} references unknown curriculum domain: {domain}")
        for evidence_id in row.get("evidence", []):
            if str(evidence_id) not in evidence_ids:
                fail(f"alignment {identifier} references unknown evidence: {evidence_id}")
        engineering_status = str(row.get("engineering_status", ""))
        commercial_status = str(row.get("commercial_status", ""))
        if engineering_status not in {
            "RESEARCH",
            "BUILDING",
            "PILOT_READY",
            "PAID_PROOF",
            "REPEATABLE",
        }:
            fail(f"alignment {identifier} has invalid engineering status: {engineering_status}")
        if commercial_status not in STATUS_RANK:
            fail(f"alignment {identifier} has invalid commercial status: {commercial_status}")
        if (
            engineering_status in ENGINEERING_RELEASE_STATES
            and STATUS_RANK[commercial_status] < STATUS_RANK["PILOT"]
        ):
            fail(
                f"alignment {identifier} claims engineering release before commercial pilot readiness"
            )

    if FAILURES:
        print(f"\n❌ Dual-track alignment gate failed: {len(FAILURES)} violation(s)")
        return 1
    passed(
        f"Dual-track alignment is coherent: {len(records)} capability records connect engineering evidence to production offers without bypass."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
