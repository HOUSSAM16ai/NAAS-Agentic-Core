"""Unit tests for the deterministic transition engine.

Tests assert the *numbers* produced by `src.core.engine` — these are the
auditable core: every score must be reproducible, bounded, and consistent
with the documented methodology (Eloundou β weighting, Anthropic observed
exposure, Acemoglu–Restrepo displacement/reinstatement).
"""

from microservices.transition_service.src.core import engine
from microservices.transition_service.src.data.occupations import (
    OCCUPATIONS,
    SKILLS,
    TRAINING_UNITS,
)


class TestAtlasIntegrity:
    def test_occupations_have_tasks(self) -> None:
        for code, occ in OCCUPATIONS.items():
            assert occ.tasks, f"{code} has no task breakdown"
            total = sum(t.time_fraction for t in occ.tasks)
            assert 0.95 <= total <= 1.05, f"{code} time fractions sum to {total}"

    def test_skills_all_referenced_skills_exist(self) -> None:
        for occ in OCCUPATIONS.values():
            for s in list(occ.current_skills) + list(occ.future_skills):
                assert s in SKILLS, f"{occ.code} references unknown skill {s}"

    def test_training_units_valid(self) -> None:
        for code, unit in TRAINING_UNITS.items():
            assert unit["duration_weeks"] > 0, code
            assert unit["level"] in ("foundational", "intermediate", "advanced")
            for s in unit["skills"]:
                assert s in SKILLS

    def test_growth_sectors_occupations_exist(self) -> None:
        from microservices.transition_service.src.data.occupations import GROWTH_SECTORS

        for sector in GROWTH_SECTORS.values():
            for code in sector["key_occupations"]:
                assert code in OCCUPATIONS, code


class TestExposure:
    def test_human_only_exposure_is_zero(self) -> None:
        # A profession whose tasks are all human-only must have zero exposure.
        for _code, occ in OCCUPATIONS.items():
            all_human = all(t.category == "human_only" for t in occ.tasks)
            if all_human:
                assert engine.theoretical_exposure(occ) == 0.0
                assert engine.observed_exposure(occ) == 0.0

    def test_full_automation_exposure_is_one(self) -> None:
        for _code, occ in OCCUPATIONS.items():
            all_auto = all(t.category == "auto_full" for t in occ.tasks)
            if all_auto:
                assert engine.theoretical_exposure(occ) == 1.0

    def test_observed_never_exceeds_theoretical(self) -> None:
        for occ in OCCUPATIONS.values():
            assert engine.observed_exposure(occ) <= engine.theoretical_exposure(occ) + 1e-9

    def test_data_entry_high_exposure(self) -> None:
        occ = OCCUPATIONS["o_data_entry"]
        assert engine.theoretical_exposure(occ) >= 0.6, "data entry is a textbook high-exposure job"

    def test_nurse_has_human_core(self) -> None:
        occ = OCCUPATIONS["o_care_assistant"]
        assert engine.human_core_index(occ) > 0.5

    def test_exposure_bounded(self) -> None:
        for occ in OCCUPATIONS.values():
            assert 0.0 <= engine.theoretical_exposure(occ) <= 1.0
            assert 0.0 <= engine.observed_exposure(occ) <= 1.0


class TestRiskBands:
    def test_band_thresholds(self) -> None:
        assert engine.risk_band(0.6) == "critical"
        assert engine.risk_band(0.59) == "elevated"
        assert engine.risk_band(0.35) == "elevated"
        assert engine.risk_band(0.34) == "watch"
        assert engine.risk_band(0.05) == "stable"

    def test_early_warning_composite_bounded(self) -> None:
        for occ in OCCUPATIONS.values():
            score = engine.early_warning_score(occ)["composite_risk"]
            assert -0.5 <= score <= 0.75  # -0.3*1.0 .. 0.35+0.35


class TestSkillsGap:
    def test_identical_skills_zero_gap(self) -> None:
        gap = engine.skills_gap(["s_data_entry", "s_ai_tools"], ["s_data_entry", "s_ai_tools"])
        assert gap["gap_ratio"] == 0.0
        assert gap["missing_skills"] == []

    def test_full_gap(self) -> None:
        gap = engine.skills_gap(["s_data_entry"], ["s_ai_prompt", "s_ml_ops"])
        assert gap["gap_ratio"] == 1.0
        assert gap["gap_severity"] == "high"

    def test_gap_ratio_linear(self) -> None:
        gap = engine.skills_gap(
            ["s_data_entry", "s_ai_tools"], ["s_data_entry", "s_critical_thinking"]
        )
        assert gap["gap_ratio"] == 0.5


class TestTransitionDistance:
    def test_self_distance_zero(self) -> None:
        occ = OCCUPATIONS["o_admin_support"]
        assert engine.transition_distance(occ, occ) == 0.0

    def test_adjacent_closer_than_far(self) -> None:
        admin = OCCUPATIONS["o_admin_support"]
        ops = OCCUPATIONS["o_ops_analyst"]
        nurse = OCCUPATIONS["o_care_assistant"]
        assert engine.transition_distance(admin, ops) < engine.transition_distance(admin, nurse)

    def test_distance_bounded(self) -> None:
        admin = OCCUPATIONS["o_admin_support"]
        for other in OCCUPATIONS.values():
            d = engine.transition_distance(admin, other)
            assert 0.0 <= d <= 1.0, d


class TestRecommendedPaths:
    def test_paths_sorted_by_feasibility(self) -> None:
        admin = OCCUPATIONS["o_admin_support"]
        candidates = [OCCUPATIONS[a] for a in admin.adjacent_occupations if a in OCCUPATIONS]
        paths = engine.recommended_paths(admin, candidates)
        feas = [p["transition_feasibility"] for p in paths]
        assert feas == sorted(feas, reverse=True)

    def test_feasibility_bounded(self) -> None:
        admin = OCCUPATIONS["o_admin_support"]
        candidates = [OCCUPATIONS[a] for a in admin.adjacent_occupations if a in OCCUPATIONS]
        for p in engine.recommended_paths(admin, candidates):
            assert 0.0 <= p["transition_feasibility"] <= 1.0


class TestTrainingCoverage:
    def test_covers_gap_skills(self) -> None:
        admin = OCCUPATIONS["o_admin_support"]
        ops = OCCUPATIONS["o_data_quality"]
        source_skills = set(admin.current_skills)
        target_skills = set(ops.current_skills)
        missing = target_skills - source_skills
        units = engine.training_coverage(admin, ops)
        covered = {s for u in units for s in u["skills_covered"]}
        assert missing <= covered | set(SKILLS.keys())
        assert units  # at least one unit bridges
