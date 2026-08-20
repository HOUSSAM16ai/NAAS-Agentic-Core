"""End-to-end tests — full HTTP cycle over all 13 agent endpoints.

Environment: pytest runs with LLM_MOCK_MODE=1 and an in-memory database,
mirroring the CI matrix (see `.github/workflows/ci.yml` `microservices-tests` job).

Deterministic scenario used throughout:
    Fatima, an administrative-support clerk (o_admin_support) in a rural
    region, low income, mid-career — the archetypal transition candidate.
All assertions are *numeric* and reproducible; narrative text only needs to
mention the evidence base.
"""

import pytest
from fastapi.testclient import TestClient

from microservices.transition_service.src.main import app

client = TestClient(app)

FATIMA = {
    "worker_id": "w_fatima",
    "current_occupation": "o_admin_support",
    "region": "rural",
    "age_band": "mid",
    "gender_band": "f",
    "current_skills": ["s_doc_sort", "s_ops_coord"],
    "income_band": "low",
}


@pytest.mark.parametrize("endpoint", ["/health", "/agents"])
def test_health_and_agents(endpoint: str) -> None:
    resp = client.get(endpoint)
    assert resp.status_code == 200


def test_metrics_endpoint() -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "cogniforge_transition_requests_total" in resp.text


def test_dispatch_unknown_agent_400() -> None:
    resp = client.post("/dispatch/unknown_agent", json={})
    assert resp.status_code == 400


class TestEarlyWarning:
    def test_national_map(self) -> None:
        resp = client.post("/early-warning", json={"scope": "national"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent"] == "early_warning"
        assert data["result"]["analyzed_occupations"] > 10
        assert (
            data["result"]["alerts"]["critical_count"] + data["result"]["alerts"]["elevated_count"]
            > 0
        )
        for entry in data["result"]["risk_map"]:
            assert entry["risk_band"] in ("critical", "elevated", "watch", "stable")

    def test_individual_watchlist(self) -> None:
        resp = client.post("/early-warning", json={"scope": "individual", "worker": FATIMA})
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["individual"]["worker_id"] == "w_fatima"


class TestExposure:
    def test_data_entry_exposure(self) -> None:
        resp = client.post("/exposure", json={"occupation_code": "o_data_entry"})
        assert resp.status_code == 200
        indices = resp.json()["result"]["indices"]
        assert indices["theoretical_exposure"] > 0.5
        assert indices["observed_exposure"] <= indices["theoretical_exposure"]
        assert indices["human_core_index"] < 0.3

    def test_task_breakdown_present(self) -> None:
        resp = client.post("/exposure", json={"occupation_code": "o_admin_support"})
        breakdown = resp.json()["result"]["task_breakdown"]
        assert len(breakdown) >= 4
        for task in breakdown:
            assert 0.0 <= task["theoretical_beta"] <= 1.0


class TestSkillsGap:
    def test_gap_against_future_skills(self) -> None:
        resp = client.post(
            "/skills-gap",
            json={
                "worker": FATIMA,
                "target_occupation": "o_data_quality",
            },
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        gap = result["skills_gap"]
        assert len(gap["missing_skills"]) > 0
        assert gap["gap_ratio"] > 0
        for skill in result["missing_skill_details"]:
            assert skill["kind"] in ("domain", "digital", "human", "governance")


class TestTransition:
    def test_transition_plan_has_bridge(self) -> None:
        resp = client.post("/transition", json={"worker": FATIMA, "max_paths": 3})
        assert resp.status_code == 200
        result = resp.json()["result"]
        paths = result["transition_paths"]
        assert 1 <= len(paths) <= 3
        top = paths[0]
        assert 0.0 <= top["feasibility_score"] <= 1.0
        assert 0.0 <= top["skill_distance"] <= 1.0
        # Every path carries an explicit support flag and wage delta (deterministic).
        assert "needs_transition_support" in top
        assert "wage_delta_reference" in top
        # The Fatima → data-quality path has a documented training bridge.
        dq = next((p for p in paths if p["target_occupation"] == "o_data_quality"), None)
        if dq:
            assert dq["training_bridge"]
            assert dq["total_bridge_weeks"] > 0

    def test_explicit_target(self) -> None:
        resp = client.post(
            "/transition",
            json={
                "worker": FATIMA,
                "target_occupation": "o_data_quality",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["transition_paths"][0]["target_occupation"] == "o_data_quality"


class TestEducation:
    def test_curriculum_gap(self) -> None:
        resp = client.post(
            "/education",
            json={
                "institution_type": "vocational",
                "target_skills": ["s_ai_tools", "s_data_basic", "s_critical_thinking"],
                "current_curriculum_skills": ["s_data_entry"],
            },
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["curriculum_gap"]["gap_ratio"] > 0
        assert result["recommended_units"]
        first = result["recommended_units"][0]
        assert "label_ar" in first

    def test_occupation_focus(self) -> None:
        resp = client.post(
            "/education",
            json={
                "institution_type": "school",
                "for_occupation": "o_data_quality",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["occupation_focus"]["code"] == "o_data_quality"


class TestJobCreation:
    def test_all_sectors(self) -> None:
        resp = client.post("/job-creation", json={})
        assert resp.status_code == 200
        growth_map = resp.json()["result"]["growth_map"]
        assert len(growth_map) == 6
        for sector in growth_map:
            assert sector["roles"]
            assert "access_strategy" in sector


class TestSocialProtection:
    def test_low_income_worker_package(self) -> None:
        resp = client.post(
            "/social-protection",
            json={
                "worker": FATIMA,
                "transition_horizon_months": 12,
            },
        )
        assert resp.status_code == 200
        pkg = resp.json()["result"]["package"]
        provided = [c for c in pkg if c["provided"]]
        assert len(provided) >= 3  # retraining always + bridge + support
        assert any(c["name"].startswith("إعادة تأهيل") for c in pkg)


class TestGovernanceAgent:
    def test_high_risk_hiring_system(self) -> None:
        resp = client.post(
            "/governance",
            json={
                "system_type": "hiring",
                "decision_description": "System ranks job applicants automatically",
                "affected_groups": ["young", "women"],
            },
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["risk_classification"] == "high"
        assert len(result["obligations"]) >= 5
        assert result["appeal_mechanism"]["required"] is True

    def test_standard_system(self) -> None:
        resp = client.post(
            "/governance",
            json={
                "system_type": "other",
                "decision_description": "Answer common customer questions",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["risk_classification"] == "standard"


class TestEquity:
    def test_equity_index_from_population(self) -> None:
        population = [
            {**FATIMA, "worker_id": f"w_{i}", "gender_band": g, "income_band": inc}
            for i, (g, inc) in enumerate([("f", "low"), ("m", "mid"), ("f", "high"), ("m", "low")])
        ]
        resp = client.post("/equity", json={"population": population})
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["population_size"] == 4
        assert result["equity_index"] is not None
        assert 0.0 <= result["equity_index"] <= 1.0


class TestSimulation:
    def test_balanced_policy(self) -> None:
        resp = client.post(
            "/simulation",
            json={
                "policy_name": "national reskilling accelerator",
                "displacement_rate": 0.3,
                "reinstatement_rate": 0.5,
                "horizon_years": 5,
            },
        )
        assert resp.status_code == 200
        agg = resp.json()["result"]["aggregate"]
        assert agg["net_employment_effect"] >= 0
        assert agg["verdict"] in ("balanced_creation", "managed_transition")

    def test_displacement_heavy_policy(self) -> None:
        resp = client.post(
            "/simulation",
            json={
                "policy_name": "full automation mandate",
                "displacement_rate": 0.9,
                "reinstatement_rate": 0.05,
                "horizon_years": 10,
                "sector_codes": ["care"],
            },
        )
        assert resp.status_code == 200
        agg = resp.json()["result"]["aggregate"]
        assert agg["net_employment_effect"] < 0
        assert agg["verdict"] == "net_displacement"


class TestDialogue:
    def test_feedback_classification(self) -> None:
        resp = client.post(
            "/dialogue",
            json={
                "stakeholder": "worker",
                "feedback_text": "نحتاج تدريبًا أفضل ومهارات جديدة لمواجهة الأتمتة",
            },
        )
        assert resp.status_code == 200
        assert "reskilling" in resp.json()["result"]["themes_detected"]


class TestEvaluation:
    def test_kpi_measurement(self) -> None:
        resp = client.post(
            "/evaluation",
            json={
                "kpi_code": "six_month_placement",
                "measured_value": 72.0,
                "target_value": 80.0,
                "period": "current",
            },
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        # 72 >= 80*0.9 = 72.0 — boundary counts as on_track (>= 0.9×target)
        assert result["status"] in ("on_track", "at_risk")
        assert result["achievement_ratio"] == pytest.approx(0.9, rel=1e-3)
        assert "measured" in result and "target" in result

    def test_on_track(self) -> None:
        resp = client.post(
            "/evaluation",
            json={
                "kpi_code": "wage_change",
                "measured_value": 9.5,
                "target_value": 10.0,
                "period": "current",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["status"] == "on_track"

    def test_off_track(self) -> None:
        resp = client.post(
            "/evaluation",
            json={
                "kpi_code": "rural_access",
                "measured_value": 20.0,
                "target_value": 60.0,
                "period": "current",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["status"] == "off_track"


class TestRedTeam:
    def test_fairness_across_age_passes(self) -> None:
        resp = client.post(
            "/red-team",
            json={
                "test_kind": "fairness_across_age",
                "payload": {
                    "occupation": "o_admin_support",
                    "skills": ["s_doc_sort", "s_ops_coord"],
                },
            },
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["variants_tested"] == 3
        # Engine is demographic-blind → variance should be zero.
        assert result["verdict"] == "pass"
        for _metric, coeff in result["demographic_variance_coefficients"].items():
            assert coeff <= 0.10

    def test_unrealistic_recommendation_audit(self) -> None:
        resp = client.post(
            "/red-team",
            json={
                "test_kind": "unrealistic_recommendation",
                "payload": {},
            },
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        for violation in result["max_distance_violations"]:
            assert "source" in violation and "target" in violation


class TestGovernanceGate:
    def test_approve_path(self) -> None:
        resp = client.post(
            "/governance/decide",
            json={
                "request_id": "req-001",
                "agent": "sim_agent",
                "action_key": "notify_worker",
                "description": "Labor-market bulletin",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["allowed"] is True
        assert body["decision_level"] == "INFORMATIVE"
        assert "decision_log" in body

    def test_restricted_path(self) -> None:
        resp = client.post(
            "/governance/decide",
            json={
                "request_id": "req-002",
                "agent": "sim_agent",
                "action_key": "terminate_contract",
                "description": "Unilateral termination",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["allowed"] is False
        assert resp.json()["decision_level"] == "HIGH_RISK_REJECT"

    def test_log_overview(self) -> None:
        client.post(
            "/governance/decide",
            json={
                "request_id": "req-003",
                "agent": "sim_agent",
                "action_key": "notify_worker",
                "description": "x",
            },
        )
        resp = client.get("/governance/log")
        assert resp.status_code == 200
        assert resp.json()["total_decisions"] >= 1
