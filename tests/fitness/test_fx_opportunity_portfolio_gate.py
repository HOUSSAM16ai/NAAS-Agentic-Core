"""اختبارات إيجابية وسلبية لمحفظة فرص العملة الصعبة."""

from copy import deepcopy

from scripts.fitness import check_fx_opportunity_portfolio as gate


def _repository_inputs() -> tuple[dict, dict, dict]:
    return (
        gate._load(gate.PORTFOLIO),
        gate._load(gate.OFFER_CATALOG),
        gate._load(gate.EVIDENCE_CATALOG),
    )


def test_repository_portfolio_passes() -> None:
    assert gate.main() == 0


def test_rejects_unknown_evidence_and_score_drift() -> None:
    portfolio, offers, evidence = _repository_inputs()
    broken = deepcopy(portfolio)
    broken["opportunities"][0]["evidence_ids"] = ["invented-source"]
    broken["opportunities"][0]["score"] += 1

    failures = gate.validate(broken, offers, evidence)

    assert len(failures) >= 1
    assert any("unknown evidence id" in failure for failure in failures)
    assert any("score drift" in failure for failure in failures)


def test_rejects_commercial_promotion_without_paid_proof() -> None:
    portfolio, offers, evidence = _repository_inputs()
    promoted = deepcopy(offers)
    promoted["offers"][0]["status"] = "PAID_PROOF"

    failures = gate.validate(portfolio, promoted, evidence)

    assert any("parent offer must remain PROPOSED" in failure for failure in failures)


def test_rejects_eighth_unapproved_offer() -> None:
    portfolio, offers, evidence = _repository_inputs()
    broken = deepcopy(portfolio)
    broken["opportunities"][0]["parent_offer_id"] = "new-unapproved-line"

    failures = gate.validate(broken, offers, evidence)

    assert any("unknown parent offer" in failure for failure in failures)
