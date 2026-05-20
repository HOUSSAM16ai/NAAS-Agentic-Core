"""اختبارات تخزين BKT (append-only) + حظر التجريد في شجرة الاحتمالات (V6.0)."""

from __future__ import annotations

import pytest

# تسجيل النماذج في SQLModel.metadata قبل إنشاء المخطط
from app.core.domain import bkt_analytics as _bkt_model  # noqa: F401
from app.core.domain import user as _user_model  # noqa: F401
from app.infrastructure.clients.orchestrator_client import OrchestratorClient
from app.services.analytics.bkt_persistence import BKTAnalyticsService

_ABSTRACT_LABELS = {"A", "Ā", "B | A", "B̄ | A", "B | Ā", "B̄ | Ā", "B"}


def _collect_labels(node: dict) -> list[str]:
    labels = [node.get("label", "")]
    for child in node.get("children", []) or []:
        labels.extend(_collect_labels(child))
    return labels


class TestAbstractionBan:
    def test_no_abstract_symbols_with_concrete_entities(self) -> None:
        props = OrchestratorClient._detect_probability_tree(
            "صندوق فيه كرات حمراء، احتمال سحب كرة حمراء هو 0.3 ثم النجاح 0.8"
        )
        assert props is not None
        labels = _collect_labels(props["tree"])
        assert not (set(labels) & _ABSTRACT_LABELS), f"abstract labels leaked: {labels}"
        assert "كرة حمراء" in labels

    def test_generic_fallback_is_concrete_not_abstract(self) -> None:
        # عبارة صريحة بلا كيان ملموس → تسميات عامة ملموسة، لا رموز A/B
        props = OrchestratorClient._detect_probability_tree("ارسم شجرة الاحتمالات")
        assert props is not None
        labels = _collect_labels(props["tree"])
        assert not (set(labels) & _ABSTRACT_LABELS)
        assert "الحدث الأول" in labels

    def test_structure_preserved(self) -> None:
        props = OrchestratorClient._detect_probability_tree(
            "احتمال الحدث الأول 0.3 والثاني بشرطه 0.8 — شجرة احتمالات"
        )
        assert props is not None
        assert props["title"] == "شجرة الاحتمالات"
        children = props["tree"]["children"]
        assert len(children) == 2
        assert children[0]["p"] == 0.3
        assert children[1]["p"] == 0.7  # complement

    def test_extract_concrete_events_detects_defective(self) -> None:
        events = OrchestratorClient._extract_concrete_events("نسبة القطع المعيبة في المصنع")
        assert events is not None
        assert events["first"] == "قطعة معيبة"
        assert events["first_neg"] == "قطعة سليمة"

    def test_extract_returns_none_without_entity(self) -> None:
        assert OrchestratorClient._extract_concrete_events("شجرة الاحتمالات العامة") is None


@pytest.mark.asyncio
class TestBKTPersistence:
    async def test_insert_and_read_back(self) -> None:
        from tests.conftest import managed_test_session

        async with managed_test_session() as db:
            service = BKTAnalyticsService(db)
            evaluation = await service.evaluate_and_record(
                user_id=90001,
                session_id=555,
                question="ارسم شجرة الاحتمالات بشرط الحادثة واحتمال 0.3",
            )
            assert evaluation.concept_id == "conditional_probability"
            assert 0.0 <= evaluation.student_mastery_probability <= 1.0

            latest = await service.latest_mastery(90001, "conditional_probability")
            assert latest == evaluation.student_mastery_probability

    async def test_append_only_accumulates_mastery(self) -> None:
        from tests.conftest import managed_test_session

        async with managed_test_session() as db:
            service = BKTAnalyticsService(db)
            q = "أعتقد أن احتمال الحادثة المشروطة هو 0.5 إذن النتيجة"
            first = await service.evaluate_and_record(user_id=90002, session_id=1, question=q)
            second = await service.evaluate_and_record(user_id=90002, session_id=1, question=q)
            # mastery signal repeated → second prior = first mastery → grows
            assert second.prior_mastery == pytest.approx(first.student_mastery_probability)
            assert second.student_mastery_probability >= first.student_mastery_probability
            count = await service.interaction_count(90002, second.concept_id)
            assert count == 2
