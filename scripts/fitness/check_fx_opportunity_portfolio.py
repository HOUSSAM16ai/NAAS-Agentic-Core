"""يتحقق من أن محفظة فرص العملة الصعبة قابلة للتدقيق ولا ترفع الفرضيات."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORTFOLIO = ROOT / "docs/commercial/FX_OPPORTUNITY_PORTFOLIO.json"
OFFER_CATALOG = ROOT / "docs/commercial/OFFER_CATALOG.json"
EVIDENCE_CATALOG = ROOT / "docs/research/EVIDENCE_CATALOG.json"

ALLOWED_PRIORITIES = {"NOW", "OPTION", "WATCH"}
ALLOWED_HORIZONS = {"0-12_MONTHS", "6-24_MONTHS", "24-60_MONTHS", "24-84_MONTHS"}
SCORE_FIELDS = {
    "adjacency",
    "evidence",
    "buyer_access",
    "speed_to_paid_test",
    "repeatability",
    "defensibility",
    "capital_intensity",
    "bundling_risk",
}
REQUIRED_TEXT_FIELDS = {
    "buyer_ar",
    "paid_problem_ar",
    "deliverable_ar",
    "currency_route_ar",
    "next_experiment_ar",
    "success_gate_ar",
    "kill_criterion_ar",
    "unproven_ar",
}
REQUIRED_DISCOVERY_FIELDS = {
    "qualified_buyer_definition_ar",
    "contact_authorization_ar",
    "paid_pilot_boundary_ar",
    "decision_rule_ar",
}
REQUIRED_DISCOVERY_RECORD_FIELDS = {
    "segment",
    "consequential_workflow",
    "current_alternative",
    "pain_or_risk_evidence",
    "budget_owner",
    "procurement_path",
    "outcome",
}
FORBIDDEN_PROMISES = ("guaranteed", "مضمون", "سوق بلا منافسة", "امتثال مضمون")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def calculate_score(scores: dict[str, int]) -> int:
    """يحسب ترتيب الفرصة من الأبعاد المصرح بها دون تقدير مخفي."""

    return (
        5 * scores["adjacency"]
        + 4 * scores["evidence"]
        + 4 * scores["buyer_access"]
        + 3 * scores["speed_to_paid_test"]
        + 2 * scores["repeatability"]
        + 2 * scores["defensibility"]
        - 2 * scores["capital_intensity"]
        - 2 * scores["bundling_risk"]
    )


def _validate_text(opportunity_id: str, row: dict) -> list[str]:
    failures: list[str] = []
    for field in sorted(REQUIRED_TEXT_FIELDS):
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"{opportunity_id}: missing {field}")
    joined_text = " ".join(str(row.get(field, "")) for field in REQUIRED_TEXT_FIELDS)
    for phrase in FORBIDDEN_PROMISES:
        if phrase.casefold() in joined_text.casefold():
            failures.append(f"{opportunity_id}: forbidden promise {phrase!r}")
    return failures


def _validate_evidence(opportunity_id: str, row: dict, evidence_ids: set[str]) -> list[str]:
    failures: list[str] = []
    source_ids = row.get("evidence_ids", [])
    contrary_ids = row.get("contrary_evidence_ids", [])
    if not isinstance(source_ids, list) or not source_ids:
        failures.append(f"{opportunity_id}: evidence_ids must be non-empty")
        source_ids = []
    if not isinstance(contrary_ids, list) or not contrary_ids:
        failures.append(f"{opportunity_id}: contrary_evidence_ids must be non-empty")
        contrary_ids = []
    for source_id in [*source_ids, *contrary_ids]:
        if source_id not in evidence_ids:
            failures.append(f"{opportunity_id}: unknown evidence id {source_id!r}")
    return failures


def _validate_score(opportunity_id: str, row: dict, previous_score: int) -> tuple[list[str], int]:
    failures: list[str] = []
    scores = row.get("scores")
    if not isinstance(scores, dict) or set(scores) != SCORE_FIELDS:
        return [f"{opportunity_id}: score dimensions do not match contract"], previous_score
    if any(not isinstance(value, int) or not 0 <= value <= 5 for value in scores.values()):
        return [
            f"{opportunity_id}: every score dimension must be an integer in [0,5]"
        ], previous_score
    calculated = calculate_score(scores)
    if row.get("score") != calculated:
        failures.append(f"{opportunity_id}: score drift, expected {calculated}")
    if calculated > previous_score:
        failures.append(f"{opportunity_id}: opportunities must be sorted by descending score")
    return failures, calculated


def _validate_discovery_protocol(opportunity_id: str, row: dict) -> list[str]:
    """يتحقق من أن تجربة البيع القريبة تجمع دليلاً قابلاً للقرار لا وعوداً."""

    failures: list[str] = []
    protocol = row.get("discovery_protocol")
    if row.get("priority") != "NOW":
        if protocol is not None:
            failures.append(
                f"{opportunity_id}: only NOW opportunities may define discovery_protocol"
            )
        return failures
    if not isinstance(protocol, dict):
        return [f"{opportunity_id}: NOW opportunity needs discovery_protocol"]
    for field in sorted(REQUIRED_DISCOVERY_FIELDS):
        value = protocol.get(field)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"{opportunity_id}: discovery_protocol missing {field}")
    questions = protocol.get("interview_questions_ar")
    if (
        not isinstance(questions, list)
        or len(questions) < 5
        or not all(isinstance(question, str) and question.strip() for question in questions)
    ):
        failures.append(f"{opportunity_id}: discovery_protocol needs at least five questions")
    record_fields = protocol.get("evidence_record_fields")
    if (
        not isinstance(record_fields, list)
        or set(record_fields) != REQUIRED_DISCOVERY_RECORD_FIELDS
    ):
        failures.append(f"{opportunity_id}: discovery_protocol record fields do not match contract")
    return failures


def validate(portfolio: dict, offers: dict, evidence: dict) -> list[str]:
    """يعيد كل خروقات العقد بدلاً من إخفاء الفشل الأول."""

    failures: list[str] = []
    offer_rows = [row for row in offers.get("offers", []) if isinstance(row, dict)]
    offer_ids = {str(row.get("id")) for row in offer_rows}
    offer_status = {str(row.get("id")): str(row.get("status")) for row in offer_rows}
    evidence_ids = {
        str(row.get("id")) for row in evidence.get("evidence", []) if isinstance(row, dict)
    }
    opportunities = portfolio.get("opportunities", [])
    if portfolio.get("status_policy") != "RESEARCH_ONLY":
        failures.append("portfolio status_policy must remain RESEARCH_ONLY")
    if not isinstance(opportunities, list) or len(opportunities) < 3:
        return [*failures, "portfolio must contain at least three opportunities"]

    seen_ids: set[str] = set()
    expected_rank = 1
    previous_score = 101
    for row in opportunities:
        if not isinstance(row, dict):
            failures.append("every opportunity must be an object")
            continue
        opportunity_id = str(row.get("id", ""))
        if not opportunity_id or opportunity_id in seen_ids:
            failures.append(f"opportunity id missing or duplicated: {opportunity_id!r}")
        seen_ids.add(opportunity_id)
        if row.get("rank") != expected_rank:
            failures.append(f"{opportunity_id}: expected rank {expected_rank}")
        expected_rank += 1
        if row.get("priority") not in ALLOWED_PRIORITIES:
            failures.append(f"{opportunity_id}: invalid priority")
        if row.get("horizon") not in ALLOWED_HORIZONS:
            failures.append(f"{opportunity_id}: invalid horizon")

        parent_offer = str(row.get("parent_offer_id", ""))
        if parent_offer not in offer_ids:
            failures.append(f"{opportunity_id}: unknown parent offer {parent_offer!r}")
        elif offer_status.get(parent_offer) != "PROPOSED":
            failures.append(f"{opportunity_id}: parent offer must remain PROPOSED")

        failures.extend(_validate_text(opportunity_id, row))
        failures.extend(_validate_evidence(opportunity_id, row, evidence_ids))
        failures.extend(_validate_discovery_protocol(opportunity_id, row))
        score_failures, previous_score = _validate_score(opportunity_id, row, previous_score)
        failures.extend(score_failures)
    return failures


def main() -> int:
    """يفشل صراحة عند كسر مصدر أو ترتيب أو حد ادعاء."""

    missing = [path for path in (PORTFOLIO, OFFER_CATALOG, EVIDENCE_CATALOG) if not path.is_file()]
    if missing:
        for path in missing:
            print(f"❌ missing portfolio asset: {path.relative_to(ROOT)}")
        return 1
    failures = validate(_load(PORTFOLIO), _load(OFFER_CATALOG), _load(EVIDENCE_CATALOG))
    if failures:
        for failure in failures:
            print(f"❌ {failure}")
        print(f"\n❌ FX opportunity portfolio gate failed: {len(failures)} violation(s)")
        return 1
    print(
        "✅ FX opportunity portfolio is ranked, sourced, falsifiable, and commercially unpromoted."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
