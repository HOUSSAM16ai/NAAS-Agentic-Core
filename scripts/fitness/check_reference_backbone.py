"""Enforce the immutable reference backbone for NAAS-Agentic-Core.

The backbone is a governed set of external repositories used as learning,
architecture, security, and agent-engineering references. It is deliberately
*not* a runtime dependency graph. This gate makes the user-requested set
machine-checkable:

* every declared reference must remain present;
* every reference is pinned to an auditable commit;
* every reference documents what was adopted and what was not adopted;
* the set cannot silently shrink, gain an unreviewed entry, or become a
  runtime import surface;
* the named enforcer and ADR must remain on disk.

Adding a new reference requires changing the manifest, this explicit expected
set, and ADR-013 in one reviewed change. Existing project files are never
removed by this gate.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "docs/governance/REFERENCE_BACKBONE.json"
ADR = REPO_ROOT / "docs/adr/ADR-013-reference-backbone.md"

# This is intentionally explicit rather than derived from the manifest. If a
# reference is removed from the manifest, the gate must fail instead of
# allowing the manifest to redefine the contract it is supposed to enforce.
EXPECTED_IDS = frozenset(
    {
        "developer-roadmap",
        "coding-interview-university",
        "the-algorithms-python",
        "system-design-primer",
        "system-design-101",
        "build-your-own-x",
        "clean-code-javascript",
        "clean-code-book",
        "freecodecamp",
        "awesome",
        "free-programming-books",
        "public-apis",
        "browser-use",
        "llms-from-scratch",
        "awesome-claude-skills",
    }
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")

FAILURES: list[str] = []


def fail(message: str) -> None:
    FAILURES.append(message)
    print(f"❌ {message}")


def passed(message: str) -> None:
    print(f"✅ {message}")


def load_manifest() -> dict | None:
    if not MANIFEST.is_file():
        fail(f"missing manifest: {MANIFEST.relative_to(REPO_ROOT)}")
        return None
    try:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"manifest is not valid JSON: {exc}")
        return None
    if not isinstance(payload, dict):
        fail("manifest root must be an object")
        return None
    return payload


def check_top_level(payload: dict) -> None:
    if payload.get("decision") != "ADR-013":
        fail("manifest decision must remain ADR-013")
    if payload.get("immutability_model", {}).get("reference_set") != "exactly_the_declared_ids":
        fail("manifest must declare an exact reference set")
    if payload.get("immutability_model", {}).get("runtime_dependency_policy") != (
        "forbidden_without_new_adr_and_security_review"
    ):
        fail("runtime dependency policy was weakened or changed")
    if payload.get("verification", {}).get("unverified_claims_excluded") is not True:
        fail("unverified claims must remain excluded")
    if payload.get("verification", {}).get("stars_are_not_governance_evidence") is not True:
        fail("star counts must not be treated as governance evidence")
    if not ADR.is_file():
        fail(f"backbone ADR is missing: {ADR.relative_to(REPO_ROOT)}")


def check_reference(label: str, row: object) -> None:
    if not isinstance(row, dict):
        fail(f"{label}: reference must be an object")
        return
    required = (
        "id",
        "repo",
        "commit_sha",
        "snapshot_url",
        "role_ar",
        "adopted_ar",
        "not_adopted_ar",
        "runtime_import",
    )
    for field in required:
        if not str(row.get(field, "")).strip() and field != "runtime_import":
            fail(f"{label}: missing required field `{field}`")

    repo = str(row.get("repo", ""))
    parsed = urlparse(repo)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        fail(f"{label}: repo must be an HTTPS GitHub URL")
    if repo.count("/") != 4 or repo.endswith("/"):
        fail(f"{label}: repo must identify exactly github.com/owner/name")

    sha = str(row.get("commit_sha", ""))
    if not SHA_RE.fullmatch(sha):
        fail(f"{label}: commit_sha must be a 40-character lowercase SHA-1")
    snapshot = str(row.get("snapshot_url", ""))
    if sha and sha not in snapshot:
        fail(f"{label}: snapshot_url must contain the pinned commit SHA")
    if row.get("runtime_import") is not False:
        fail(f"{label}: runtime_import must remain false")


def main() -> int:
    payload = load_manifest()
    if payload is None:
        return 1
    check_top_level(payload)

    references = payload.get("references")
    if not isinstance(references, list) or not references:
        fail("references must be a non-empty list")
        return 1

    ids = [str(row.get("id", "")) if isinstance(row, dict) else "" for row in references]
    actual_ids = frozenset(ids)
    if len(ids) != len(actual_ids):
        fail("reference ids must be unique")
    missing = sorted(EXPECTED_IDS - actual_ids)
    extra = sorted(actual_ids - EXPECTED_IDS)
    if missing:
        fail(f"mandatory backbone references were removed: {missing}")
    if extra:
        fail(f"unreviewed backbone references were added: {extra}; update ADR-013 and this gate")
    if len(references) != len(EXPECTED_IDS):
        fail(f"reference count drifted: expected {len(EXPECTED_IDS)}, got {len(references)}")

    for index, row in enumerate(references, start=1):
        check_reference(f"reference[{index}]", row)

    enforcers = payload.get("enforcers", [])
    if "scripts/fitness/check_reference_backbone.py" not in enforcers:
        fail("manifest must name its own enforcer")
    for enforcer in enforcers:
        if not (REPO_ROOT / str(enforcer)).is_file():
            fail(f"manifest names missing enforcer: {enforcer}")

    if FAILURES:
        print(f"\n❌ Reference backbone gate failed: {len(FAILURES)} violation(s)")
        return 1

    passed(
        f"Reference backbone is intact: {len(references)} pinned sources, "
        "no runtime imports, explicit adoption boundaries, and ADR-013 present."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
