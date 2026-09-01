"""اختبارات سلبية لبوابة حزمة استثمار ضمان أفعال الوكلاء."""

import json
from pathlib import Path

from scripts.fitness import check_agent_assurance_investment_case as gate


def test_gate_passes_for_repository_contract() -> None:
    assert gate.main() == 0


def test_gate_rejects_promoted_offer_without_paid_evidence(tmp_path: Path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    commercial = docs / "commercial"
    research = docs / "research"
    shared = tmp_path / "shared"
    commercial.mkdir(parents=True)
    research.mkdir(parents=True)
    shared.mkdir(parents=True)
    case = commercial / "AGENT_ACTION_ASSURANCE_INVESTMENT_CASE.md"
    case.write_text("\n".join(gate.REQUIRED_SECTIONS), encoding="utf-8")
    evidence = research / "EVIDENCE_CATALOG.json"
    evidence.write_text(
        json.dumps({"evidence": [{"id": value} for value in gate.REQUIRED_EVIDENCE_IDS]}),
        encoding="utf-8",
    )
    offer = commercial / "OFFER_CATALOG.json"
    offer.write_text(
        json.dumps(
            {
                "offers": [
                    {
                        "id": "ai-red-teaming-multilingual",
                        "status": "PAID_PROOF",
                        "activation_gate_ar": "ثلاثة عملاء وتجديد",
                        "claims_forbidden_ar": "ROI",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    roi_model = shared / "agent_assurance_roi.py"
    roi_model.write_text("# model\n", encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "CASE", case)
    monkeypatch.setattr(gate, "EVIDENCE", evidence)
    monkeypatch.setattr(gate, "OFFER", offer)
    monkeypatch.setattr(gate, "ROI_MODEL", roi_model)

    assert gate.main() == 1
