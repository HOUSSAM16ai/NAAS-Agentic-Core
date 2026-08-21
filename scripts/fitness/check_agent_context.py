"""Check the unified agent context and commercial traceability registry.

This gate makes the repository's agent boot contract executable. It verifies
that authority paths, boot sources, constitutional records, the reference
backbone, and the commercial offer catalog exist and remain structurally
connected. It does not infer truth from filenames or popularity; the source
files remain authoritative.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "docs/governance/AGENT_CONTEXT_REGISTRY.json"
BACKBONE = REPO_ROOT / "docs/governance/REFERENCE_BACKBONE.json"
OFFERS = REPO_ROOT / "docs/commercial/OFFER_CATALOG.json"

FAILURES: list[str] = []
VALID_STATES = {"PROPOSED", "DISCOVERY", "OFFER_READY", "PILOT", "PAID_PROOF", "REPEATABLE"}


def fail(message: str) -> None:
    FAILURES.append(message)
    print(f"❌ {message}")


def passed(message: str) -> None:
    print(f"✅ {message}")


def load_json(path: Path, label: str) -> dict | None:
    if not path.is_file():
        fail(f"{label} missing: {path.relative_to(REPO_ROOT)}")
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


def check_path(path_value: object, label: str) -> None:
    path = str(path_value).strip()
    if not path:
        fail(f"{label}: empty path")
        return
    if not (REPO_ROOT / path).exists():
        fail(f"{label}: source does not exist: {path}")


def check_registry(registry: dict) -> None:
    if registry.get("decision") != "D-275":
        fail("agent context registry must remain governed by D-275")
    if not str(registry.get("non_destructive_policy_ar", "")).strip():
        fail("non-destructive policy is missing")
    if registry.get("authority_order") is not None:
        authority = registry["authority_order"]
        if not isinstance(authority, list) or not authority:
            fail("authority_order must be a non-empty list")
        else:
            ranks = [row.get("rank") for row in authority if isinstance(row, dict)]
            if len(ranks) != len(set(ranks)):
                fail("authority ranks must be unique")
            if ranks != list(range(1, len(ranks) + 1)):
                fail("authority ranks must be contiguous from 1")
            for index, row in enumerate(authority, start=1):
                if not isinstance(row, dict):
                    fail(f"authority_order[{index}] must be an object")
                    continue
                check_path(row.get("path"), f"authority_order[{index}]")

    boot = registry.get("boot_sequence")
    if not isinstance(boot, list) or len(boot) < 5:
        fail("boot_sequence must contain at least five ordered steps")
    else:
        steps = [row.get("step") for row in boot if isinstance(row, dict)]
        if steps != list(range(1, len(steps) + 1)):
            fail("boot_sequence steps must be contiguous and ordered")
        for index, row in enumerate(boot, start=1):
            if not isinstance(row, dict):
                fail(f"boot_sequence[{index}] must be an object")
                continue
            reads = row.get("read", [])
            if not isinstance(reads, list) or not reads:
                fail(f"boot_sequence[{index}] must read at least one source")
            for path in reads:
                check_path(path, f"boot_sequence[{index}]")

    required_sources = registry.get("required_sources", [])
    if not isinstance(required_sources, list) or not required_sources:
        fail("required_sources must be non-empty")
    else:
        for path in required_sources:
            check_path(path, "required_sources")

    commercial_trace = registry.get("commercial_trace", {})
    required_fields = commercial_trace.get("required_fields_ar", [])
    if not isinstance(required_fields, list) or len(required_fields) < 6:
        fail("commercial_trace must declare the agent’s minimum commercial fields")
    if commercial_trace.get("canonical_offer_catalog") != "docs/commercial/OFFER_CATALOG.json":
        fail("commercial trace must point to the canonical offer catalog")
    if not isinstance(commercial_trace.get("forbidden_shortcuts_ar"), list) or not commercial_trace["forbidden_shortcuts_ar"]:
        fail("commercial trace must declare forbidden shortcuts")


def check_backbone(backbone: dict) -> set[str]:
    mandate = backbone.get("commercial_mandate", {})
    for field in ("objective_ar", "priority_rule_ar", "primary_success_metric_ar", "decision_gate_ar"):
        if not str(mandate.get(field, "")).strip():
            fail(f"reference backbone commercial mandate missing `{field}`")
    anti_vanity = mandate.get("anti_vanity_metrics_ar")
    if not isinstance(anti_vanity, list) or len(anti_vanity) < 3:
        fail("reference backbone must declare anti-vanity metrics")

    rows = backbone.get("references", [])
    ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            fail(f"backbone reference[{index}] must be an object")
            continue
        identifier = str(row.get("id", "")).strip()
        if not identifier:
            fail(f"backbone reference[{index}] has no id")
        ids.add(identifier)
    return ids


def check_offers(offers: dict, reference_ids: set[str]) -> None:
    if offers.get("decision") != "D-273":
        fail("offer catalog must remain governed by D-273")
    if not str(offers.get("commercial_objective_ar", "")).strip():
        fail("offer catalog commercial objective is missing")
    rows = offers.get("offers", [])
    if not isinstance(rows, list) or len(rows) != 7:
        fail(f"offer catalog must contain exactly the seven declared revenue lines; got {len(rows) if isinstance(rows, list) else 'invalid'}")
        return
    identifiers: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            fail(f"offer[{index}] must be an object")
            continue
        identifier = str(row.get("id", "")).strip()
        if not identifier or identifier in identifiers:
            fail(f"offer[{index}] has a missing or duplicate id")
        identifiers.add(identifier)
        for field in ("buyer_ar", "paid_problem_ar", "offer_outcome_ar", "hard_currency_route_ar", "activation_gate_ar", "claims_forbidden_ar"):
            if not str(row.get(field, "")).strip():
                fail(f"offer {identifier or index} missing `{field}`")
        status = row.get("status")
        if status not in VALID_STATES:
            fail(f"offer {identifier or index} has invalid readiness state: {status!r}")
        evidence = row.get("evidence_paths", [])
        if not isinstance(evidence, list):
            fail(f"offer {identifier or index} evidence_paths must be a list")
        elif status in {"PROPOSED", "DISCOVERY", "OFFER_READY"} and evidence:
            fail(f"offer {identifier} has evidence paths but is not yet in a proof state")
        refs = row.get("backbone_refs", [])
        if not isinstance(refs, list) or not refs:
            fail(f"offer {identifier or index} must cite at least one backbone reference")
        else:
            unknown = sorted(set(refs) - reference_ids)
            if unknown:
                fail(f"offer {identifier} cites unknown backbone references: {unknown}")


def main() -> int:
    registry = load_json(REGISTRY, "agent context registry")
    backbone = load_json(BACKBONE, "reference backbone")
    offers = load_json(OFFERS, "offer catalog")
    if registry is not None:
        check_registry(registry)
    reference_ids: set[str] = set()
    if backbone is not None:
        reference_ids = check_backbone(backbone)
    if offers is not None:
        check_offers(offers, reference_ids)

    if FAILURES:
        print(f"\n❌ Agent context gate failed: {len(FAILURES)} violation(s)")
        return 1
    passed("Agent boot context is coherent: authority, boot sequence, commercial trace, and seven offers resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
