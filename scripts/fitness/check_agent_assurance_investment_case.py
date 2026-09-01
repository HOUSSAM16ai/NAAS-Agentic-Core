"""يتحقق من اكتمال حزمة الاستثمار دون تحويل الفرضيات إلى أدلة سوق."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "docs/commercial/AGENT_ACTION_ASSURANCE_INVESTMENT_CASE.md"
EVIDENCE = ROOT / "docs/research/EVIDENCE_CATALOG.json"
OFFER = ROOT / "docs/commercial/OFFER_CATALOG.json"
ROI_MODEL = ROOT / "shared/agent_assurance_roi.py"

REQUIRED_EVIDENCE_IDS = {
    "agentdojo-2024",
    "injecagent-acl-2024",
    "metr-task-horizons-2025",
    "microsoft-entra-agent-id-2025",
    "nist-ai-rmf-1.0",
    "nist-agent-standards-initiative",
    "palo-alto-protect-ai-acquisition-2025",
}
REQUIRED_SECTIONS = (
    "## 2. The pain is observable, not hypothetical",
    "## 5. Customer ROI contract",
    "## 6. Venture return logic—without promising returns",
    "## 8. Competition and the anti-bundling test",
    "## 9. Risk register and falsification",
    "## 10. Ninety-day evidence plan",
    "## 11. Claim discipline",
)
FORBIDDEN_UNQUALIFIED_CLAIMS = (
    "guaranteed investor return",
    "guaranteed ROI",
    "guaranteed compliance",
    "proven product-market fit",
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _missing_assets() -> list[str]:
    failures: list[str] = []
    for path in (CASE, EVIDENCE, OFFER, ROI_MODEL):
        if not path.is_file():
            failures.append(f"missing required investment-case asset: {path.relative_to(ROOT)}")
    return failures


def _case_failures() -> list[str]:
    failures: list[str] = []
    case_text = CASE.read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        if section not in case_text:
            failures.append(f"investment case missing section: {section}")
    for claim in FORBIDDEN_UNQUALIFIED_CLAIMS:
        if claim in case_text:
            failures.append(f"investment case contains forbidden unqualified claim: {claim}")
    return failures


def _evidence_failures() -> list[str]:
    evidence = _load_json(EVIDENCE)
    evidence_ids = {
        str(row.get("id")) for row in evidence.get("evidence", []) if isinstance(row, dict)
    }
    return [
        f"evidence catalog missing investment source: {evidence_id}"
        for evidence_id in sorted(REQUIRED_EVIDENCE_IDS - evidence_ids)
    ]


def _offer_failures() -> list[str]:
    failures: list[str] = []
    offers = _load_json(OFFER)
    assurance_offer = next(
        (
            row
            for row in offers.get("offers", [])
            if isinstance(row, dict) and row.get("id") == "ai-red-teaming-multilingual"
        ),
        None,
    )
    if assurance_offer is None:
        failures.append("offer catalog missing ai-red-teaming-multilingual")
    else:
        if assurance_offer.get("status") != "PROPOSED":
            failures.append("assurance offer must remain PROPOSED before paid evidence")
        for token in ("ثلاثة عملاء", "تجديد", "ROI"):
            if token not in str(assurance_offer.get("activation_gate_ar", "")) + str(
                assurance_offer.get("claims_forbidden_ar", "")
            ):
                failures.append(f"assurance offer evidence contract missing token: {token}")
    return failures


def main() -> int:
    """يفشل عند غياب الدليل أو نموذج ROI أو حدود الادعاء."""

    failures = _missing_assets()
    if not failures:
        failures.extend(_case_failures())
        failures.extend(_evidence_failures())
        failures.extend(_offer_failures())

    if failures:
        for failure in failures:
            print(f"❌ {failure}")
        print(f"\n❌ Agent assurance investment gate failed: {len(failures)} violation(s)")
        return 1

    print("✅ Agent assurance investment case is evidence-led, falsifiable, and claim-bounded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
