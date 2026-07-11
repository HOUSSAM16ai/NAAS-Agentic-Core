"""D-127 — المعمارية الإدراكية العصبية-الرمزية: تشخيص المفهوم + التصعيد السقراطي.

الكارثة (transcript حي بعد D-125): «ما هو البسط»/«ما هو المقام» تسقط للحل الكامل (لا تعريف
المفهوم)؛ و«لم أفهم»×2 / «ما هو البسط»×2 ⇒ إجابة متطابقة byte-by-byte (صفر تقدّم).

D-127 (رؤية المالك العصبية-الرمزية): الطبقة 1 تُصنّف *أيّ* صياغة → مفهوم واحد (numerator/
denominator/ratio/...) بلا رياضيات؛ الطبقة 5 تُسجّل سبب الحيرة (misconception)؛ الطبقة 4
تُصعّد سقراطياً (شرح→سؤال→إعادة توجيه) بدل التكرار؛ الطبقة 3 (الأرقام) رمزية صرفة.

stdlib + standalone replica + source-inspection — يعمل في الـ sandbox بلا pydantic.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_SRC = (REPO_ROOT / "app/services/skills/concept_diagnosis_skill.py").read_text(
    encoding="utf-8"
)
CLIENT_SRC = (REPO_ROOT / "app/infrastructure/clients/orchestrator_client.py").read_text(
    encoding="utf-8"
) + (REPO_ROOT / "app/services/skills/probability_tutor_brain.py").read_text(
    encoding="utf-8"
)  # D-163: عقل الاحتمالات استُخرج للوحدة المستقلة — نضمّ الاثنين ليصمد أي pin
DOCTRINE_SRC = (REPO_ROOT / "app/services/skills/doctrine.py").read_text(encoding="utf-8")

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


# ── نسخة standalone مطابقة لـ diagnose_deterministic (sandbox-safe) ────────────
def _normalize(text: str) -> str:
    return (text or "").translate(_AR_DIGITS).strip().lower()


_RATIO = ("الفرق بين", "الفرق", "العلاقة", "الرابط", "النسبة", "نقسم", "القسمة",
          "البسط والمقام", "بسط ومقام", "ضعت بين", "ضائع بين", "تهت بين")  # fmt: skip
_COMB = ("التوافيق", "توافيق", "الترتيب", "ترتيب", "الاختيار", "permutation",
         "combinaison", "لماذا نختار", "لماذا التوافيق")  # fmt: skip
_NUM = ("البسط", "ما هو البسط", "ماذا يمثل البسط", "معنى البسط", "14",
        "الحالات الملائمة", "الحالات المواتية", "الحالات التي تنجح", "ما الحالات")  # fmt: skip
_NUM_PROC = ("نجمع", "كيف حسبنا 14", "كيف نحسب 14", "وجدنا 14")
_DEN = ("المقام", "ما هو المقام", "ماذا يمثل المقام", "معنى المقام", "165",
        "فضاء العينة", "فضاء العيّنة", "العدد الكلي", "كل الطرق", "كل الاحتمالات",
        "كل الامكانات")  # fmt: skip
_FULL = ("اشرح", "الحل الكامل", "حل التمرين", "السؤال الأول", "السؤال الاول",
         "كيف أحل", "كيف احل", "كيف نحل")  # fmt: skip


def diagnose(q: str) -> str:
    n = _normalize(q)
    if any(m in n for m in ("الحمراء", "حمراء", "احمر")):
        return "color_red"
    if any(m in n for m in ("الخضراء", "خضراء", "اخضر")):
        return "color_green"
    if any(m in n for m in ("البيضاء", "بيضاء", "ابيض")):
        return "color_white"
    if any(m in n for m in _RATIO):
        return "ratio"
    if any(m in n for m in _COMB):
        return "combinations"
    if any(m in n for m in _NUM_PROC) or any(m in n for m in _NUM):
        return "numerator"
    if any(m in n for m in _DEN):
        return "denominator"
    if any(m in n for m in _FULL):
        return "full_solution"
    return "unknown"


# ── 1. الطبقة 1: كل صياغات المفهوم الواحد → نفس المفهوم ────────────────────────
class TestConceptMapping:
    def test_numerator_phrasings(self) -> None:
        for q in (
            "ما هو البسط",
            "ماذا يمثل البسط",
            "لماذا 14",
            "ما الهدف من 14",
            "ماذا تمثل 14",
            "كيف حسبنا 14",
            "ما هي الحالات الملائمة",
        ):
            assert diagnose(q) == "numerator", q

    def test_denominator_phrasings(self) -> None:
        for q in ("ما هو المقام", "لماذا 165", "ما معنى 165", "ما هو فضاء العينة"):
            assert diagnose(q) == "denominator", q

    def test_ratio_phrasings(self) -> None:
        for q in ("ما الفرق بين 14 و 165", "العلاقة بين البسط والمقام", "أنا ضعت بين 14 و165"):
            assert diagnose(q) == "ratio", q

    def test_colors(self) -> None:
        assert diagnose("الكرات الحمراء") == "color_red"
        assert diagnose("لماذا البيضاء مستحيلة") == "color_white"

    def test_full_solution(self) -> None:
        assert diagnose("اشرح السؤال الأول") == "full_solution"

    def test_unknown_goes_to_llm(self) -> None:
        # صياغة دارجة جديدة غير مُغطّاة حتمياً ⇒ unknown (تُحال للطبقة 1 LLM).
        assert diagnose("واش راه هاد الشي") == "unknown"


# ── 2. الطبقة 5: النموذج العقلي (المفهوم الخاطئ) ───────────────────────────────
def infer_misconception(concept: str, normalized: str) -> str:
    if concept == "numerator":
        if any(m in normalized for m in ("165", "المقام", "فضاء", "كل الطرق")):
            return "sample_space_confusion"
        return "favourable_outcomes_confusion"
    if concept == "ratio":
        return "fraction_meaning_confusion"
    if concept == "combinations":
        return "order_vs_selection_confusion"
    return "none"


class TestMentalModel:
    def test_numerator_mixing_with_denominator(self) -> None:
        # «لماذا 14 وليس 165» ⇒ numerator + sample_space_confusion (يخلط بينهما).
        assert infer_misconception("numerator", _normalize("لماذا 14 وليس 165")) == (
            "sample_space_confusion"
        )

    def test_ratio_fraction_confusion(self) -> None:
        assert infer_misconception("ratio", "") == "fraction_meaning_confusion"

    def test_combinations_order_confusion(self) -> None:
        assert infer_misconception("combinations", "") == "order_vs_selection_confusion"


# ── 3. الطبقة 4: التصعيد السقراطي (لا تكرار) ───────────────────────────────────
def concept_of_text(text: str) -> str:
    c = diagnose(text)
    if c == "unknown":
        low = (text or "").strip().lower()
        if any(m in low for m in ("لم أفهم", "لم افهم", "مفهمتش", "ما فهمت", "لا أفهم")):
            return "full_solution"
    return c


def count_prior(concept: str, history: list[dict[str, str]]) -> int:
    return sum(
        1
        for m in history
        if m.get("role") == "user" and concept_of_text(str(m.get("content", ""))) == concept
    )


class TestSocraticEscalation:
    def test_first_time_is_level_0(self) -> None:
        assert count_prior("numerator", []) == 0  # المرّة 1 ⇒ شرح

    def test_second_time_is_level_1(self) -> None:
        history = [{"role": "user", "content": "ما هو البسط"}]
        assert count_prior("numerator", history) == 1  # المرّة 2 ⇒ سؤال سقراطي

    def test_third_time_is_level_2(self) -> None:
        history = [
            {"role": "user", "content": "ما هو البسط"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "لماذا 14"},
        ]
        assert count_prior("numerator", history) == 2  # المرّة 3 ⇒ إعادة توجيه

    def test_confusion_maps_to_full_solution(self) -> None:
        assert concept_of_text("لم أفهم") == "full_solution"
        history = [{"role": "user", "content": "لم أفهم"}]
        assert count_prior("full_solution", history) == 1  # «لم أفهم»×2 ⇒ تصعيد لا تكرار

    def test_assistant_messages_not_counted(self) -> None:
        history = [{"role": "assistant", "content": "ما هو البسط هو ..."}]
        assert count_prior("numerator", history) == 0


# ── 4. source-inspection: الطبقات موصولة + الأرقام رمزية + يَنجو من الحجب ───────
class TestSourceWiring:
    def test_skill_defined(self) -> None:
        assert "class ConceptDiagnosisSkill" in SKILL_SRC
        assert "def diagnose_deterministic(" in SKILL_SRC
        assert "async def diagnose(" in SKILL_SRC
        assert "async def _classify_with_llm(" in SKILL_SRC

    def test_llm_output_enum_validated(self) -> None:
        # الطبقة 1 الآمنة: مخرج LLM مُتحقَّق ضد الـ enum + timeout + fallback.
        assert "_VALID_CONCEPTS" in SKILL_SRC
        assert "asyncio.wait_for" in SKILL_SRC
        assert "if token in _VALID_CONCEPTS" in SKILL_SRC

    def test_llm_never_does_math(self) -> None:
        # الـ prompt يُصرّح: لا تحلّ، لا تحسب، لا تشرح.
        assert "لا تحلّ، لا تحسب، لا تشرح" in SKILL_SRC

    def test_cognitive_response_wired(self) -> None:
        assert "def _build_cognitive_response(" in CLIENT_SRC
        assert "def _count_prior_concept(" in CLIENT_SRC
        assert "def _load_canonical_combinations(" in CLIENT_SRC

    def test_diagnosis_wired_in_chat(self) -> None:
        assert "ConceptDiagnosisSkill.diagnose_deterministic(question)" in CLIENT_SRC
        assert "self._build_cognitive_response(" in CLIENT_SRC

    def test_numbers_from_symbolic_engine(self) -> None:
        # الطبقة 3: الأرقام من ProbabilityCalculatorSkill (المحرك الرمزي)، صفر LLM.
        seg = CLIENT_SRC[CLIENT_SRC.index("def _load_canonical_combinations(") :][:1500]
        assert "ProbabilityCalculatorSkill" in seg
        assert "CombinationsModelOutput" in seg

    def test_redaction_safe_ratio_line(self) -> None:
        import re

        num_re = r"[-+]?\d[\d.,]*\s*(?:/\s*\d[\d.,]*)?\s*%?"
        conclusion_re = re.compile(
            r"(?P<lhs>(?:إذن|ومنه|النتيجة|الجواب|فإن)[^=\n]{0,90}=\s*)(?P<rhs>" + num_re + r")"
        )
        # «الاحتمال = 14 من كل 165» لا يبدأ بكلمة خلاصة ⇒ يَنجو من حجب D-113.
        assert conclusion_re.search("الاحتمال = 14 من كل 165") is None

    def test_doctrine_present(self) -> None:
        # D-128: bumped 1.0.0 → 1.1.0 (السرد السقراطي المُولَّد + event_meaning).
        assert "CONCEPT_DIAGNOSIS_DOCTRINE_VERSION: Final[str] = " in DOCTRINE_SRC
        assert '"concept_diagnosis": {' in DOCTRINE_SRC
        assert "الطبقة 1 (LLM) تُصنّف فقط" in DOCTRINE_SRC
