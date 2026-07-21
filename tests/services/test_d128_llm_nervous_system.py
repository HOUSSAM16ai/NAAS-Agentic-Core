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

from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_SRC = (REPO_ROOT / "app/services/skills/concept_diagnosis_skill.py").read_text(
    encoding="utf-8"
)
CLIENT_SRC = (
    read_tutor_source()
)  # D-163: عقل الاحتمالات استُخرج للوحدة المستقلة — نضمّ الاثنين ليصمد أي pin
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "_doctrine_sources", REPO_ROOT / "app/services/skills/doctrine/_sources.py"
)
_dsrc = _ilu.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_dsrc)
# D-173 Stage 2a: doctrine.py صار حزمة — البوّابات تقرأ المصدر المُركَّب عبر المانيفست.
DOCTRINE_SRC = _dsrc.read_doctrine_source()

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
        # D-129/D-137: بوّابة التصعيد انتقلت إلى محرّك السياسة (`_policy.action == "socratic"`)
        # — لا بوّابة `level` داخلية. السرد لا يُستدعى إلا تحت قرار السياسة السقراطي.
        seg = CLIENT_SRC[CLIENT_SRC.index("async def _generate_socratic_narrative(") :][:3500]
        assert "return None" in seg  # fallback حتمي عند أي فشل
        assert 'elif _policy.action == "socratic":' in CLIENT_SRC  # البوّابة الوحيدة

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
        # D-137: موصول تحت قرار السياسة السقراطي (D-129) — يُولَّد ويستبدل القالب الحتمي،
        # مع fallback إلى _build_cognitive_response. (الترتيب: السرد قبل الـ fallback.)
        seg = CLIENT_SRC[CLIENT_SRC.index('elif _policy.action == "socratic":') :][:900]
        assert "await self._generate_socratic_narrative(" in seg
        assert "if _narr:" in seg
        assert "_build_cognitive_response(" in seg  # fallback حتمي


# ── 3. event_meaning level-0 تعريف حتمي (لا الحل الكامل) ─────────────────────────
class TestEventDefinition:
    def test_event_branch_in_cognitive_response(self) -> None:
        # D-132/D-137: الفرع يُعرّف الحادثة عبر السجلّ الحتمي (PROPERTY_REGISTRY["same_color"]
        # عنوانه «ماذا نقصد بالحادثة A؟») لا نصاً inline، ولا يكشف 14/165.
        assert 'if concept == "event_meaning":' in CLIENT_SRC
        seg = CLIENT_SRC[CLIENT_SRC.index('if concept == "event_meaning":') :][:1500]
        assert 'PROPERTY_REGISTRY["same_color"]' in seg  # التعريف من السجلّ (لا full_solution)
        assert "نفس اللون" in seg
        assert "14/165" not in seg  # لا كشف الجواب النهائي في التعريف

    def test_event_precedes_full_solution(self) -> None:
        # الحدث يُفحَص قبل full_solution (لا يسقط للحل الكامل).
        ev = CLIENT_SRC.index('if concept == "event_meaning":')
        fs = CLIENT_SRC.index('if concept == "full_solution":')
        assert ev < fs


# ── 4. doctrine + redaction-safety ─────────────────────────────────────────────
class TestDoctrineAndSafety:
    def test_doctrine_bumped(self) -> None:
        # D-137: نسخة CONCEPT_DIAGNOSIS تطوّرت (≥ 1.1.0) — نتحقّق من التطوّر + المحتوى الجوهري.
        from app.services.skills.doctrine import CONCEPT_DIAGNOSIS_DOCTRINE_VERSION

        major, minor, *_ = (int(x) for x in CONCEPT_DIAGNOSIS_DOCTRINE_VERSION.split("."))
        assert (major, minor) >= (1, 1)
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
