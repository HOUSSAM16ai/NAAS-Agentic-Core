"""
D-100 — Skills Platform regression tests (registry + composition).

يثبت:
  • الـ registry يبني 14 Skill (12 ACTIVE + 2 FLAGGED) بلا ZOMBIE.
  • الـ FLAGGED مُعطَّلة افتراضياً ومُفعَّلة عبر علم البيئة.
  • `compose_text_refinement` يحافظ على الترتيب، يعزل الفشل، ويتدهور رشيقاً.
  • الـ manifest يصف skills_platform باتّساق.
"""

from __future__ import annotations

import pytest

from app.services.skills.registry import (
    RefinerResult,
    SkillRegistry,
    compose_text_refinement,
    get_skill_registry,
)

EXPECTED = {
    "greeting",
    "bac_exercise",
    "math",
    "answer_quality",
    "bkt_engine",
    "probability",
    "exercise_alignment",
    "output_firewall",
    "topic_lock",
    "arabic_stream_guard",
    "ws_heartbeat",
    "text_refinement_compose",
    "retrieval_rerank",
    "mcp_tool",
}


class TestRegistry:
    def test_registry_complete(self) -> None:
        reg = get_skill_registry()
        assert set(reg.names()) == EXPECTED
        assert len(reg.list()) == 14

    def test_status_split(self) -> None:
        reg = get_skill_registry()
        assert len(reg.by_status("ACTIVE")) == 12
        assert len(reg.by_status("FLAGGED")) == 2

    def test_no_zombie(self) -> None:
        for d in get_skill_registry().list():
            assert d.consumed_by, f"ZOMBIE skill (empty consumed_by): {d.name}"

    def test_flagged_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ENABLE_RETRIEVAL_RERANK_SKILL", raising=False)
        monkeypatch.delenv("ENABLE_MCP_TOOL_SKILL", raising=False)
        reg = get_skill_registry()
        assert reg.get("retrieval_rerank").is_enabled() is False
        assert reg.get("mcp_tool").is_enabled() is False
        assert reg.get("greeting").is_enabled() is True

    def test_flag_enables_via_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENABLE_MCP_TOOL_SKILL", "1")
        assert get_skill_registry().get("mcp_tool").is_enabled() is True

    def test_duplicate_registration_guarded(self) -> None:
        reg = SkillRegistry()
        d = get_skill_registry().get("greeting")
        reg.register(d)
        with pytest.raises(ValueError):
            reg.register(d)

    def test_as_dict_shape(self) -> None:
        d = get_skill_registry().get("bkt_engine").as_dict()
        assert d["name"] == "bkt_engine"
        assert d["status"] == "ACTIVE"
        assert d["enabled"] is True
        assert isinstance(d["consumed_by"], list)


class TestComposeTextRefinement:
    def test_order_failure_isolation(self) -> None:
        calls: list[str] = []

        def good(t: str, c: dict) -> RefinerResult:
            calls.append("good")
            return RefinerResult(t + "+g", True)

        def boom(t: str, c: dict) -> RefinerResult:
            calls.append("boom")
            raise RuntimeError("x")

        def noop(t: str, c: dict) -> RefinerResult:
            calls.append("noop")
            return RefinerResult(t, False)

        res = compose_text_refinement(
            "A", {}, steps=[("good", good), ("boom", boom), ("noop", noop)]
        )
        assert res.text == "A+g"
        assert res.applied_steps == ("good",)
        assert res.failed_steps == ("boom",)
        assert calls == ["good", "boom", "noop"]  # all ran in order despite failure

    def test_empty_text_safe(self) -> None:
        res = compose_text_refinement("", {})
        assert isinstance(res.text, str)

    def test_default_pipeline_runs_real_skills(self) -> None:
        # خط التنقية الافتراضي (Skills حقيقية) — لا يكسر، يُرجِع نصاً
        res = compose_text_refinement(
            "النتيجة النهائية $$x=1$$.",
            {"question": "ما قيمة x؟", "intent": "educational"},
        )
        assert isinstance(res.text, str) and res.text


class TestManifest:
    def test_skills_platform_manifest_consistent(self) -> None:
        from app.services.skills.doctrine import (
            SKILL_DOCTRINE_MANIFEST,
            SKILLS_PLATFORM_DOCTRINE,
            SKILLS_PLATFORM_DOCTRINE_VERSION,
        )

        entry = SKILL_DOCTRINE_MANIFEST["skills_platform"]
        assert entry["version"] == SKILLS_PLATFORM_DOCTRINE_VERSION
        assert entry["rules_count"] == len(SKILLS_PLATFORM_DOCTRINE)
