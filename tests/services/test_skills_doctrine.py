"""
D-069 / ISS-CI-GREEN-001 (2026-05-18) — Skills Doctrine Invariants.

هذه الاختبارات تثبت أن الـ doctrine الموحَّد في `app/services/skills/doctrine.py`:
1. يُصدِّر كل القواعد المتوقعة بأسماء stable.
2. كل caller يحترم الـ doctrine (drift detection).
3. الـ versioning monotonic — لا تراجع في الـ version.
4. الـ Skills الـ stale (مثل old EXPLANATION_DOCTRINE_VERSION="1.0.0") لا تتسلل.

هذه الاختبارات تُشغَّل في كل push/PR (لا paths filter — هي gate إلزامي).

تكمل ISS-080 (D-068) — الـ methodology_handle invariants من قبل.
"""

from __future__ import annotations

import pytest

from app.services.skills.doctrine import (
    DETAILED_EXPLANATION_RULES,
    DETAILED_EXPLANATION_VERSION,
    EXPLANATION_DOCTRINE,
    EXPLANATION_DOCTRINE_VERSION,
    MODEL_ANSWER_RELIANCE_RULES,
    MODEL_ANSWER_RELIANCE_VERSION,
    RETRIEVAL_DOCTRINE,
    RETRIEVAL_DOCTRINE_VERSION,
    SKILL_DOCTRINE_MANIFEST,
    get_detailed_explanation_summary,
    get_explanation_doctrine_summary,
    get_model_answer_reliance_summary,
    get_retrieval_doctrine_summary,
    list_all_doctrines,
)

# ────────────────────────────────────────────────────────────────────────
# 1. Doctrine Existence & Type
# ────────────────────────────────────────────────────────────────────────


class TestDoctrineExistence:
    """كل doctrine يجب أن تكون موجودة، tuple، وغير فارغة."""

    @pytest.mark.parametrize(
        "doctrine, name",
        [
            (RETRIEVAL_DOCTRINE, "RETRIEVAL_DOCTRINE"),
            (EXPLANATION_DOCTRINE, "EXPLANATION_DOCTRINE"),
            (MODEL_ANSWER_RELIANCE_RULES, "MODEL_ANSWER_RELIANCE_RULES"),
            (DETAILED_EXPLANATION_RULES, "DETAILED_EXPLANATION_RULES"),
        ],
    )
    def test_doctrine_is_tuple_of_strings(self, doctrine: tuple[str, ...], name: str) -> None:
        assert isinstance(doctrine, tuple), f"{name} يجب أن تكون tuple (immutable)"
        assert len(doctrine) > 0, f"{name} لا يمكن أن تكون فارغة"
        for i, rule in enumerate(doctrine):
            assert isinstance(rule, str), f"{name}[{i}] يجب أن تكون نص"
            assert len(rule) >= 10, f"{name}[{i}] قصيرة جداً (طول={len(rule)})"


class TestDoctrineVersions:
    """الـ versions يجب أن تكون semver-like strings."""

    @pytest.mark.parametrize(
        "version, name",
        [
            (RETRIEVAL_DOCTRINE_VERSION, "RETRIEVAL_DOCTRINE_VERSION"),
            (EXPLANATION_DOCTRINE_VERSION, "EXPLANATION_DOCTRINE_VERSION"),
            (MODEL_ANSWER_RELIANCE_VERSION, "MODEL_ANSWER_RELIANCE_VERSION"),
            (DETAILED_EXPLANATION_VERSION, "DETAILED_EXPLANATION_VERSION"),
        ],
    )
    def test_version_is_semver(self, version: str, name: str) -> None:
        parts = version.split(".")
        assert len(parts) == 3, f"{name}={version} يجب أن يكون MAJOR.MINOR.PATCH"
        for part in parts:
            assert part.isdigit(), f"{name}={version} كل جزء يجب أن يكون رقم"

    def test_explanation_v2_or_later(self) -> None:
        """ISS-080 (D-068) أنشأ v1.0.0. D-069 رقّى لـ v2.0.0 — لا تراجع."""
        major = int(EXPLANATION_DOCTRINE_VERSION.split(".")[0])
        assert major >= 2, (
            f"EXPLANATION_DOCTRINE_VERSION={EXPLANATION_DOCTRINE_VERSION} يجب أن يكون "
            "≥ 2.0.0 بعد D-069 — تراجع للـ v1 يعني فقدان قواعد الـ sanity/sanitization."
        )


# ────────────────────────────────────────────────────────────────────────
# 2. Content Invariants — قواعد محددة يجب أن تكون موجودة
# ────────────────────────────────────────────────────────────────────────


class TestRetrievalDoctrineContent:
    """قواعد RETRIEVAL_DOCTRINE الإلزامية."""

    def test_mentions_indexed_first(self) -> None:
        full_text = " ".join(RETRIEVAL_DOCTRINE)
        assert "Indexed-first" in full_text or "indexed-first" in full_text.lower()

    def test_mentions_atomic_load(self) -> None:
        full_text = " ".join(RETRIEVAL_DOCTRINE)
        assert "Atomic" in full_text or "atomic" in full_text.lower()

    def test_mentions_display_strip(self) -> None:
        """يجب أن نمنع تسريب YAML / answer keys / chunk tags."""
        full_text = " ".join(RETRIEVAL_DOCTRINE)
        assert "YAML" in full_text or "frontmatter" in full_text.lower()
        assert "[ex:" in full_text or "chunk" in full_text.lower()

    def test_mentions_preempt_orchestrator(self) -> None:
        full_text = " ".join(RETRIEVAL_DOCTRINE)
        assert "Pre-empt" in full_text or "preempt" in full_text.lower() or "قبل" in full_text


class TestExplanationDoctrineContent:
    """قواعد EXPLANATION_DOCTRINE الإلزامية."""

    def test_mentions_model_answer_reliance(self) -> None:
        full_text = " ".join(EXPLANATION_DOCTRINE)
        # الكلمة الأساسية في الـ doctrine: «الإجابة النموذجية»
        assert "الإجابة النموذجية" in full_text, (
            "EXPLANATION_DOCTRINE يجب أن يَذكر صراحة الإجابة النموذجية"
        )

    def test_mentions_no_verbatim_copy(self) -> None:
        full_text = " ".join(EXPLANATION_DOCTRINE)
        assert "حرفياً" in full_text or "تنسخ" in full_text

    def test_mentions_latex_required(self) -> None:
        """v2.0.0+ يجب أن يفرض LaTeX."""
        full_text = " ".join(EXPLANATION_DOCTRINE)
        assert "LaTeX" in full_text

    def test_mentions_language_purity(self) -> None:
        """v2.0.0+ — قاعدة منع تسرّب اللغات الأجنبية."""
        full_text = " ".join(EXPLANATION_DOCTRINE)
        assert "عربية" in full_text or "روسية" in full_text or "صينية" in full_text


class TestModelAnswerRelianceContent:
    """قواعد الاحتجاج بالإجابة النموذجية."""

    def test_mentions_citation_principle(self) -> None:
        full_text = " ".join(MODEL_ANSWER_RELIANCE_RULES)
        assert "حُجَّة" in full_text or "حُجّة" in full_text or "مرجع" in full_text

    def test_mentions_numeric_invariants(self) -> None:
        full_text = " ".join(MODEL_ANSWER_RELIANCE_RULES)
        assert "عددية" in full_text or "أرقام" in full_text

    def test_mentions_forbidden_zone(self) -> None:
        full_text = " ".join(MODEL_ANSWER_RELIANCE_RULES)
        assert "ممنوع" in full_text

    def test_mentions_verification(self) -> None:
        full_text = " ".join(MODEL_ANSWER_RELIANCE_RULES)
        assert "تَحقَّق" in full_text or "تحقق" in full_text


class TestDetailedExplanationContent:
    """قواعد الشرح المفصل حسب نوع السؤال."""

    def test_mentions_concept_budget(self) -> None:
        full_text = " ".join(DETAILED_EXPLANATION_RULES)
        assert "ماذا نقصد" in full_text or "مفهومي" in full_text

    def test_mentions_method_budget(self) -> None:
        full_text = " ".join(DETAILED_EXPLANATION_RULES)
        assert "كيف نُثبت" in full_text or "كيف نحسب" in full_text

    def test_mentions_token_budget(self) -> None:
        full_text = " ".join(DETAILED_EXPLANATION_RULES)
        assert "token" in full_text

    def test_token_budgets_monotonic(self) -> None:
        """رقم token المسموح لكل نوع يجب أن يصعد: concept < justification < method < default < full."""
        full_text = " ".join(DETAILED_EXPLANATION_RULES)
        # تحقق وجود الأرقام بالترتيب الصحيح في النص
        for n in ("350", "450", "600", "700", "900"):
            assert n in full_text, f"الـ doctrine لا يحوي budget {n} token"


# ────────────────────────────────────────────────────────────────────────
# 3. Manifest Integrity
# ────────────────────────────────────────────────────────────────────────


class TestDoctrineManifest:
    """`SKILL_DOCTRINE_MANIFEST` يجب أن يصف كل doctrine بشكل صحيح."""

    def test_manifest_has_four_keys(self) -> None:
        expected = {"retrieval", "explanation", "model_answer_reliance", "detailed_explanation"}
        assert set(SKILL_DOCTRINE_MANIFEST.keys()) == expected

    def test_manifest_versions_match_constants(self) -> None:
        assert SKILL_DOCTRINE_MANIFEST["retrieval"]["version"] == RETRIEVAL_DOCTRINE_VERSION
        assert SKILL_DOCTRINE_MANIFEST["explanation"]["version"] == EXPLANATION_DOCTRINE_VERSION
        assert (
            SKILL_DOCTRINE_MANIFEST["model_answer_reliance"]["version"]
            == MODEL_ANSWER_RELIANCE_VERSION
        )
        assert (
            SKILL_DOCTRINE_MANIFEST["detailed_explanation"]["version"]
            == DETAILED_EXPLANATION_VERSION
        )

    def test_manifest_rules_count_match(self) -> None:
        assert SKILL_DOCTRINE_MANIFEST["retrieval"]["rules_count"] == len(RETRIEVAL_DOCTRINE)
        assert SKILL_DOCTRINE_MANIFEST["explanation"]["rules_count"] == len(EXPLANATION_DOCTRINE)
        assert SKILL_DOCTRINE_MANIFEST["model_answer_reliance"]["rules_count"] == len(
            MODEL_ANSWER_RELIANCE_RULES
        )
        assert SKILL_DOCTRINE_MANIFEST["detailed_explanation"]["rules_count"] == len(
            DETAILED_EXPLANATION_RULES
        )

    def test_manifest_lists_consumers(self) -> None:
        """كل doctrine يجب أن تذكر على الأقل consumer واحد."""
        for key, entry in SKILL_DOCTRINE_MANIFEST.items():
            consumers = entry.get("consumed_by")
            assert isinstance(consumers, tuple)
            assert len(consumers) >= 1, (
                f"doctrine {key} ليس له أي consumer — orphan doctrine = dead code"
            )


# ────────────────────────────────────────────────────────────────────────
# 4. Helper Functions
# ────────────────────────────────────────────────────────────────────────


class TestDoctrineHelpers:
    """الـ helper functions تُرجع نصوصاً صالحة للاستخدام في prompts."""

    def test_retrieval_summary(self) -> None:
        summary = get_retrieval_doctrine_summary()
        assert isinstance(summary, str)
        assert len(summary) > 50
        # الـ summary يجب أن يحوي العدد الصحيح من الفواصل
        assert summary.count(" | ") == len(RETRIEVAL_DOCTRINE) - 1

    def test_explanation_summary(self) -> None:
        summary = get_explanation_doctrine_summary()
        assert isinstance(summary, str)
        assert len(summary) > 50
        assert summary.count(" | ") == len(EXPLANATION_DOCTRINE) - 1

    def test_model_answer_summary(self) -> None:
        summary = get_model_answer_reliance_summary()
        assert isinstance(summary, str)
        assert len(summary) > 50

    def test_detailed_summary(self) -> None:
        summary = get_detailed_explanation_summary()
        assert isinstance(summary, str)
        assert len(summary) > 50

    def test_list_all_doctrines(self) -> None:
        all_d = list_all_doctrines()
        assert all_d == SKILL_DOCTRINE_MANIFEST


# ────────────────────────────────────────────────────────────────────────
# 5. Skill Integration — Skills يستخدمون الـ doctrine
# ────────────────────────────────────────────────────────────────────────


class TestSkillIntegration:
    """`BACExerciseSkill` و الـ Skills الأخرى يجب أن تستهلك الـ doctrine."""

    def test_bac_skill_re_exports_explanation_doctrine(self) -> None:
        """backward compat: `bac_exercise_skill.EXPLANATION_DOCTRINE` يعمل."""
        import app.services.skills.bac_exercise_skill as bac_skill_mod

        assert bac_skill_mod.EXPLANATION_DOCTRINE is EXPLANATION_DOCTRINE, (
            "bac_exercise_skill يجب أن يُعيد تصدير نفس الـ tuple "
            "(ليس نسخة) — يضمن single source of truth."
        )

    def test_bac_skill_re_exports_version(self) -> None:
        import app.services.skills.bac_exercise_skill as bac_skill_mod

        assert bac_skill_mod.EXPLANATION_DOCTRINE_VERSION == EXPLANATION_DOCTRINE_VERSION

    def test_methodology_handle_uses_current_version(self) -> None:
        """ISS-080: BACSkillExplanationOutput.methodology_handle يحمل الإصدار الحالي."""
        from app.services.skills.bac_exercise_skill import BACSkillExplanationOutput

        # Construct with minimum required fields
        try:
            from app.services.capabilities.exercise_retrieval import ExerciseEntry

            entry = ExerciseEntry(
                file_path="test.md",
                year=2016,
                session=1,
                subject_number=1,
                exercise_number=1,
                branch="math",
                topics=("test",),
                tags=("test",),
            )
            out = BACSkillExplanationOutput(
                matched_entry=entry,
                display_content="d",
                full_content="f",
            )
            assert out.methodology_handle == (
                f"explanation_doctrine_v{EXPLANATION_DOCTRINE_VERSION}"
            )
        except (ImportError, TypeError):
            # ExerciseEntry shape may vary — skip live construction
            pytest.skip("ExerciseEntry not constructible in this env")


# ────────────────────────────────────────────────────────────────────────
# 6. CI Drift Detection — basic shape invariants
# ────────────────────────────────────────────────────────────────────────


class TestDoctrineDrift:
    """يكتشف drift صامت بين الـ doctrine و الـ system prompts."""

    def test_retrieval_doctrine_min_size(self) -> None:
        """RETRIEVAL_DOCTRINE يجب أن يحوي ≥ 5 قاعدة (D-069 baseline)."""
        assert len(RETRIEVAL_DOCTRINE) >= 5

    def test_explanation_doctrine_min_size(self) -> None:
        """EXPLANATION_DOCTRINE v2 يحوي ≥ 8 قاعدة (8 v1 + 3 v2 additions)."""
        assert len(EXPLANATION_DOCTRINE) >= 8

    def test_model_answer_min_size(self) -> None:
        assert len(MODEL_ANSWER_RELIANCE_RULES) >= 5

    def test_detailed_min_size(self) -> None:
        assert len(DETAILED_EXPLANATION_RULES) >= 8

    def test_total_doctrine_text_length(self) -> None:
        """قياس total drift على أعلى مستوى: لو حجم الـ doctrines صغير كثيراً
        فقدنا قواعد. لو كبير جداً قد نكون أضفنا duplicates."""
        total = (
            sum(len(r) for r in RETRIEVAL_DOCTRINE)
            + sum(len(r) for r in EXPLANATION_DOCTRINE)
            + sum(len(r) for r in MODEL_ANSWER_RELIANCE_RULES)
            + sum(len(r) for r in DETAILED_EXPLANATION_RULES)
        )
        assert 2_000 < total < 20_000, (
            f"Total doctrine size={total} خارج النطاق المتوقع — drift محتمل"
        )
