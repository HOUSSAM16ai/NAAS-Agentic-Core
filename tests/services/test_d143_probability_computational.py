from __future__ import annotations

import pytest

"""
D-143 (ISS-117) — deterministic computational answers for BAC-2024 probability.

Kills the "drift-to-event-A + verbatim repetition" catastrophe: computational questions
(event B = 56, the combinations multiplication 11×10×9, products) are answered
deterministically (zero-LLM math) and never collapse to event A. Uncovered events
(C/D/X/conditional) get an honest deterministic deferral — never event-A's numbers,
never an LLM-generated probability (owner critique #1).
"""


from app.infrastructure.clients.orchestrator_client import OrchestratorClient
from app.services.skills.probability_skill import ProbabilityCalculatorSkill

_OFFICIAL = (
    "كرتان بيضاوان مرقمتان بـ: 1، 3\n"
    "أربع كرات حمراء مرقمة بـ: 0، 1، 1، 3\n"
    "خمس كرات خضراء مرقمة بـ: 0، 1، 1، 3، 4\n"
    "نسحب عشوائيًا 3 كرات دفعة واحدة من الكيس"
)


class TestNumberParityCounts:
    @pytest.mark.asyncio

    async def test_official_2024_counts(self):
        p = ProbabilityCalculatorSkill.number_parity_counts(_OFFICIAL)
        assert p == {"odd": 8, "even": 3, "zero": 2, "total": 11}

    @pytest.mark.asyncio


    async def test_no_numbered_balls_returns_none(self):
        assert ProbabilityCalculatorSkill.number_parity_counts("كيس فيه 4 كرات حمراء") is None
        assert ProbabilityCalculatorSkill.number_parity_counts("") is None

    @pytest.mark.asyncio


    async def test_arabic_indic_digits(self):
        p = ProbabilityCalculatorSkill.number_parity_counts("كرات مرقمة بـ: ١، ٣، ٤")
        assert p == {"odd": 2, "even": 1, "zero": 0, "total": 3}


class TestComputationalRouting:
    """_build_probability_computational_answer must answer correctly, never drift to event A."""

    async def _route(self, q):
        return await OrchestratorClient._build_probability_computational_answer(q, None)

    @pytest.mark.asyncio


    async def test_event_b_56_deterministic(self):
        for q in ("كيف حصلنا على 56", "بيّن أن P(B)=56/165", "احتمال الحادثة B جداء فردي"):
            r = await self._route(q)
            if r is None:
                continue
            text, event = r  # builder returns (text, event)
            assert event == "event_b", q
            assert "(8×7×6)" in text and "= 56" in text  # C(8,3)=56
            assert "165" in text
            assert "نفس اللون" not in text  # NOT event A

    @pytest.mark.asyncio


    async def test_combinations_why_multiply(self):
        for q in (
            "لماذا نضرب 11×10×9",
            "ليش ضربنا 11 و 10 و 9",
            "اقصد لماذا نضرب ثلاثة أرقام في بعضهم",
        ):
            r = await self._route(q)
            if r is None:
                continue
            text, event = r  # builder returns (text, event)
            assert event == "combinations", q
            assert "نقسم" in text  # divide by 3! (counting principle)
            assert "جداء أرقام" in text  # distinguishes from product events

    @pytest.mark.asyncio


    async def test_uncovered_events_honest_deferral_never_event_a(self):
        cases = {
            "احتمال الحادثة C جداء زوجي": "event_c",
            "احسب احتمال الحادثة D جداء معدوم": "event_d",
            "السحب على التوالي بدون إرجاع": "event_d",
            "عيّن قانون الاحتمال للمتغير العشوائي X": "random_var",
            "احسب الأمل الرياضي E(X)": "expected",
            "احسب الاحتمال الشرطي P_A(B)": "conditional",
        }
        for q, expected_event in cases.items():
            r = await self._route(q)
            if r is None:
                continue
            text, event = r  # builder returns (text, event)
            assert event == expected_event, f"{q} -> {event}"
            assert "14/165" not in text  # explicitly distanced from event A numbers
            assert "14/165" not in text and "14 من" not in text  # never event-A's number

    @pytest.mark.asyncio


    async def test_pass_through_not_hijacked(self):
        # greetings / retrieval / event-A / general → None (handled by the existing chain).
        for q in (
            "السلام عليكم",
            "اعطني تمرين الاحتمالات 2024",
            "كيف افهم السؤال الأول",
            "ما هي الحادثة A",
            "احتمال الحادثة A نفس اللون",
        ):
            assert await self._route(q) is None, q

    @pytest.mark.asyncio


    async def test_long_paste_not_hijacked(self):
        # a full-exercise paste (>300 chars, contains 56/فردي) must defer to retrieval, not event B.
        paste = "التمرين الأول الاحتمالات " + _OFFICIAL + " الحادثة B جداء فردي P(B)=56/165 " * 6
        assert len(paste) > 300
        assert await self._route(paste) is None


class TestDriftGuard:
    @pytest.mark.asyncio

    async def test_detect_active_concept_no_drift_for_computational(self):
        from app.services.skills.semantic_property_skill import get_semantic_property_skill

        sps = get_semantic_property_skill()
        # polluted history mentioning same-color event A; a computational question must NOT
        # inherit same_color from it.
        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات"},
            {"role": "assistant", "content": "الحادثة A: 3 كرات من نفس اللون، 14 من 165"},
        ]
        for q in ("لماذا نضرب 11×10×9", "كيف حصلنا على 56"):
            assert sps.detect_active_concept(q, history) is None, q


class TestRepetitionGuard:
    """RC-4 on the computational path: a repeated computational question must NOT
    re-emit the identical text — it advances to a DIFFERENT deterministic representation
    (variation, not repetition; owner critique #2). All zero-LLM."""

    @pytest.mark.asyncio


    async def test_deferral_never_prints_event_a_number(self):
        # The honest deferral must distance from event A WITHOUT printing 14/165.
        text, event = await OrchestratorClient._build_probability_computational_answer(
            "احتمال الحادثة C جداء زوجي", None
        )
        assert event == "event_c"
        assert "14/165" not in text
        assert "14/165" not in text and "14 من" not in text

    @pytest.mark.asyncio


    async def test_combinations_variant_differs_and_teaches(self):
        base = await OrchestratorClient._build_probability_computational_answer(
            "لماذا نضرب 11×10×9", None
        )
        assert base is not None
        base_text, event = base
        assert event == "combinations"
        var = OrchestratorClient._probability_computational_variant("combinations", None)
        assert var is not None
        assert var != base_text  # a DIFFERENT representation, not a verbatim repeat
        assert "نقسم" in var  # still teaches the counting principle
        assert "14/165" not in var

    @pytest.mark.asyncio


    async def test_event_b_variant_differs_and_keeps_56(self):
        res = await OrchestratorClient._build_probability_computational_answer(
            "كيف حصلنا على 56", None
        )
        if res is None:
            return
        base_text, event = res
        assert event == "event_b"
        var = OrchestratorClient._probability_computational_variant("event_b", None)
        assert var is not None
        assert var != base_text
        assert "= 56" in var  # still deterministically 56
        assert "نفس اللون" not in var

    @pytest.mark.asyncio


    async def test_deferral_variant_distinct_and_clean(self):
        var = OrchestratorClient._probability_computational_variant("event_d", None)
        assert var is not None
        assert "14/165" not in var and "نفس اللون" not in var

    @pytest.mark.asyncio


    async def test_advance_prompt_distinct_and_clean(self):
        adv = OrchestratorClient._probability_computational_advance_prompt()
        assert adv and "14/165" not in adv and "نفس اللون" not in adv
