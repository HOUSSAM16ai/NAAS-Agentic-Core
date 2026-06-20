"""D-128 — الـ LLM كجهاز عصبي: event_meaning + السرد السقراطي المُولَّد المحروس.

الكارثة (transcript حي بعد D-127): «ماذا نقصد بالحادثة A»/«الحادثة A كيف افهمها» (معنى الحدث)
تسقط للحل الكامل؛ والتصعيد عند المستوى 2 يُكرّر «نحن ندور في النقطة نفسها» byte-by-byte.

D-128 (رؤية المالك): الـ LLM = الجهاز العصبي — يُنتج الفهم/التربية (السؤال السقراطي عند التصعيد)
لا الحقيقة (الأرقام من المحرك الرمزي محقونة). + مفهوم event_meaning (تعريف الحدث الحتمي).
السرد المُولَّد محروس: عربي فقط + لا كشف جواب + لا garbage + fallback حتمي — ويُلغي التكرار.

stdlib + standalone replica + source-inspection — يعمل في الـ sandbox بلا pydantic.
السلوك الحي للـ LLM (التصنيف + السرد الفريد + صفر كشف) مُتحقَّق حياً بـ OpenRouter (انظر السجل).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_SRC = (REPO_ROOT / "app/services/skills/concept_diagnosis_skill.py").read_text(
    encoding="utf-8"
)
CLIENT_SRC = (REPO_ROOT / "app/infrastructure/clients/orchestrator_client.py").read_text(
    encoding="utf-8"
)
DOCTRINE_SRC = (REPO_ROOT / "app/services/skills/doctrine.py").read_text(encoding="utf-8")

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _normalize(text: str) -> str:
    return (text or "").translate(_AR_DIGITS).strip().lower()


# نسخة standalone من كاشف الحدث (مطابقة لـ diagnose_deterministic بعد D-128).
_EVENT = (
    "الحادثة a", "الحادثة b", "الحادثة c", "الحادثة d",
    "الحدث a", "الحدث b", "الحدث c", "الحدث d",
    "ماذا نقصد بالحادثة", "ما معنى الحادثة", "كيف افهم الحادثة",
)  # fmt: skip


def is_event(q: str) -> bool:
    n = _normalize(q)
    return any(m in n for m in _EVENT)


# ── 1. مفهوم event_meaning يلتقط كل صياغات معنى الحدث ──────────────────────────
class TestEventConcept:
    def test_event_phrasings_detected(self) -> None:
        for q in (
            "ماذا نقصد بالحادثة A",
            "الحادثة A كيف افهمها",
            "لم أفهم الحادثة A",
            "ما معنى الحادثة B",
            "كيف افهم الحادثة C",
        ):
            assert is_event(q), q

    def test_non_event_not_detected(self) -> None:
        for q in ("ما هو البسط", "كيف نحسب 165", "لم أفهم"):
            assert not is_event(q), q

    def test_event_in_enum(self) -> None:
        assert '"event_meaning",' in SKILL_SRC
        assert '"event_meaning",' in SKILL_SRC[SKILL_SRC.index("_VALID_CONCEPTS") :]

    def test_event_in_llm_classifier_prompt(self) -> None:
        assert "event_meaning (يسأل عن معنى الحادثة" in SKILL_SRC


# ── 2. السرد السقراطي المُولَّد محروس + يبدأ عند التصعيد فقط ──────────────────────
class TestGeneratedSocraticGuards:
    def test_method_defined(self) -> None:
        assert "async def _generate_socratic_narrative(" in CLIENT_SRC

    def test_starts_at_escalation_only(self) -> None:
        seg = CLIENT_SRC[CLIENT_SRC.index("async def _generate_socratic_narrative(") :][:3500]
        assert "if level < 1:" in seg  # المرّة الأولى ⇒ شرح حتمي (لا LLM)
        assert "return None" in seg

    def test_facts_injected_not_generated(self) -> None:
        # الحقائق الرمزية محقونة؛ 14/165 **غير** محقونة (الطالب يُقاد لاكتشافها).
        seg = CLIENT_SRC[CLIENT_SRC.index("def _symbolic_facts_brief(") :][:900]
        assert "g.count" in seg  # المعطيات (عدد كل لون)
        assert "الحادثة A = 3 كرات من نفس اللون" in seg
        assert "same_group_favorable" not in seg  # لا نحقن البسط المحسوب
        assert "total_combinations" not in seg  # لا نحقن المقام المحسوب

    def test_guarded_layers(self) -> None:
        seg = CLIENT_SRC[CLIENT_SRC.index("async def _generate_socratic_narrative(") :][:3500]
        assert "asyncio.wait_for" in seg  # timeout
        assert "redact_final_answers" in seg  # لا كشف جواب
        assert "_strip_garbage_markers" in seg  # لا garbage
        assert "is_probably_non_arabic" in seg  # عربي فقط
        assert "14\\s*/\\s*165" in seg or "14/165" in seg  # شبكة أمان نهائية

    def test_prompt_forbids_math_and_reveal(self) -> None:
        assert "ممنوع منعاً باتاً كشف الجواب النهائي" in CLIENT_SRC
        assert "ممنوع الحساب" in CLIENT_SRC

    def test_wired_in_chat_for_escalation(self) -> None:
        # موصول في chat_with_agent: يُولَّد ويستبدل القالب الحتمي عند التصعيد.
        seg = CLIENT_SRC[CLIENT_SRC.index("_direct = self._build_cognitive_response(") :][:900]
        assert "await self._generate_socratic_narrative(" in seg
        assert "if _narr:" in seg


# ── 3. event_meaning level-0 تعريف حتمي (لا الحل الكامل) ─────────────────────────
class TestEventDefinition:
    def test_event_branch_in_cognitive_response(self) -> None:
        assert 'if concept == "event_meaning":' in CLIENT_SRC
        seg = CLIENT_SRC[CLIENT_SRC.index('if concept == "event_meaning":') :][:900]
        assert "ماذا نقصد بالحادثة A" in seg
        assert "3 كرات من نفس اللون" in seg
        # لا يكشف الجواب النهائي 14/165 في التعريف.
        assert "14/165" not in seg

    def test_event_precedes_full_solution(self) -> None:
        # الحدث يُفحَص قبل full_solution (لا يسقط للحل الكامل).
        ev = CLIENT_SRC.index('if concept == "event_meaning":')
        fs = CLIENT_SRC.index('if concept == "full_solution":')
        assert ev < fs


# ── 4. doctrine + redaction-safety ─────────────────────────────────────────────
class TestDoctrineAndSafety:
    def test_doctrine_bumped(self) -> None:
        assert 'CONCEPT_DIAGNOSIS_DOCTRINE_VERSION: Final[str] = "1.1.0"' in DOCTRINE_SRC
        assert "الـ LLM = الجهاز العصبي" in DOCTRINE_SRC
        assert "السرد السقراطي المُولَّد محروس إلزامياً" in DOCTRINE_SRC

    def test_event_definition_survives_redaction(self) -> None:
        import re

        num_re = r"[-+]?\d[\d.,]*\s*(?:/\s*\d[\d.,]*)?\s*%?"
        final_re = re.compile(
            r"(?P<lhs>[PECpec]\s*(?:_?[A-Za-z])?\s*\([^)\n]{0,60}\)\s*=\s*)(?P<rhs>" + num_re + r")"
        )
        # تعريف الحدث «3 كرات من نفس اللون» لا يحوي نمط P()=عدد ⇒ يَنجو.
        assert final_re.search("الحادثة A هي الحصول على 3 كرات من نفس اللون") is None
