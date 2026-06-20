"""D-125 — التركيب المفاهيمي الحتمي: قتل «متلازمة الردود المعلبة».

الكارثة (transcript حي بعد D-124): السؤال المفاهيمي/المقارنة («ما الفرق بين 165 و 14»،
«يعني 14 ما هو الهدف منها») كان يطابق على الأرقام فقط (165→total، 14→sum) فيطبع قالب
**الحساب** — متجاهلاً «الفرق»/«الهدف». الطالب يسأل عن المعنى/العلاقة فيتلقى خطوات الحساب.

D-125 (قرار المالك): كاشف مفاهيمي **يسبق** مطابقة الأرقام ⇒ شرح علاقة حواري قصير حتمي
(المقام/البسط/النسبة)، صفر LLM. أوسع من الكلمات (الدارجة «ليش»، «نفسر»، «المقصود»، «نقسم»)؛
«لماذا/ليش» + فعل إجرائي ⇒ يبقى حسابياً (قوالب D-124)؛ الهجين ⇒ علاقة + سطر حسابي واحد.

stdlib + standalone logic + source-inspection — يعمل في الـ sandbox بلا pydantic.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_SRC = (REPO_ROOT / "app/infrastructure/clients/orchestrator_client.py").read_text(
    encoding="utf-8"
)


# ── نُسَخ standalone مطابقة لمنطق D-125 (sandbox-safe replicas) ────────────────
_PROCEDURAL_VERBS: tuple[str, ...] = (
    "نجمع",
    "نحسب",
    "نحسبها",
    "نضرب",
    "نستخرج",
    "نستخدم",
    "لا نحسب",
    "كيف وجدنا",
    "كيف حصلنا",
    "كيف نحسب",
)


def _detect_conceptual_question(question: str) -> bool:
    q = (question or "").lower()
    strong = (
        "الفرق",
        "الاختلاف",
        "العلاقة",
        "الرابط",
        "مقارنة",
        "قارن",
        "ما يميز",
        "الهدف",
        "الغرض",
        "الغاية",
        "الفائدة",
        "ما فائدة",
        "فائدة",
        "ما معنى",
        "معنى",
        "ماذا يعني",
        "ماذا تعني",
        "المقصود",
        "ما المقصود",
        "نفسر",
        "التفسير",
        "كيف نفسر",
        "النسبة",
        "نقسم",
        "القسمة",
        "البسط والمقام",
        "بسط ومقام",
    )
    if any(m in q for m in strong):
        return True
    why = ("ليش", "لماذا", "علاش", "وعلاش", "علاه")
    if any(w in q for w in why):
        if any(p in q for p in _PROCEDURAL_VERBS):
            return False
        concept_ref = ("14", "165", "الناتج", "البسط", "المقام")
        if any(c in q for c in concept_ref):
            return True
    return False


# ── 1. الكاشف: مفاهيمي → True ───────────────────────────────────────────────────
class TestConceptualDetectionTrue:
    def test_difference(self) -> None:
        assert _detect_conceptual_question("ما الفرق بين 165 و 14") is True

    def test_purpose(self) -> None:
        assert _detect_conceptual_question("يعني 14 ما هو الهدف منها") is True

    def test_relationship_no_numbers(self) -> None:
        assert _detect_conceptual_question("ما العلاقة بين البسط والمقام") is True

    def test_meaning(self) -> None:
        assert _detect_conceptual_question("ما المقصود بالمقام هنا") is True
        assert _detect_conceptual_question("كيف نفسر هذا") is True

    def test_ratio_words(self) -> None:
        assert _detect_conceptual_question("ليش نقسم البسط على المقام") is True

    def test_darija_lich_plus_number(self) -> None:
        # «ليش 14؟» — دارجة + رقم بلا فعل إجرائي ⇒ مفاهيمي.
        assert _detect_conceptual_question("ليش 14؟") is True
        assert _detect_conceptual_question("لماذا 14 هو البسط؟") is True


# ── 2. الكاشف: حسابي/إجرائي → False ─────────────────────────────────────────────
class TestConceptualDetectionFalse:
    def test_computation_how(self) -> None:
        assert _detect_conceptual_question("كيف نحسب 165") is False
        assert _detect_conceptual_question("كيف وجدنا 4 الحمراء") is False
        assert _detect_conceptual_question("كيف حصلنا على 165") is False

    def test_why_plus_procedural_verb(self) -> None:
        # «لماذا» + فعل إجرائي ⇒ إجرائي (يبقى لقوالب D-124). تحفّظ المالك 3.
        assert _detect_conceptual_question("لماذا نجمع 4 و10") is False
        assert _detect_conceptual_question("لماذا لا نحسب الأبيض") is False

    def test_plain_confusion(self) -> None:
        assert _detect_conceptual_question("لم أفهم") is False
        assert _detect_conceptual_question("كيف افهم السؤال الأول") is False


# ── 3. الأولوية: المفاهيمي يهزم مطابقة الأرقام ─────────────────────────────────
class TestPriorityOverNumbers:
    def test_difference_beats_total_subpart(self) -> None:
        # «ما الفرق بين 165 و 14» يحوي «165» (subpart=total) لكنه مفاهيمي ⇒ يهزم.
        q = "ما الفرق بين 165 و 14"
        assert _detect_conceptual_question(q) is True  # يُفحَص أولاً ⇒ شرح العلاقة


# ── 4. تنسيق العلاقة يَنجو من حجب الإجابة (D-113) ────────────────────────────────
class TestRelationshipRedactionSurvival:
    def test_ratio_line_survives(self) -> None:
        import re

        num_re = r"[-+]?\d[\d.,]*\s*(?:/\s*\d[\d.,]*)?\s*%?"
        final_result_re = re.compile(
            r"(?P<lhs>[PECpec]\s*(?:_?[A-Za-z])?\s*\([^)\n]{0,60}\)\s*=\s*)(?P<rhs>" + num_re + r")"
        )
        conclusion_re = re.compile(
            r"(?P<lhs>(?:إذن|ومنه|النتيجة|الجواب|فإن)[^=\n]{0,90}=\s*)(?P<rhs>" + num_re + r")"
        )
        # السطر النهائي «نسبة البسط إلى المقام: 14 من كل 165» — لا «=»، لا كلمة خلاصة.
        line = "فالاحتمال هو نسبة البسط إلى المقام: 14 من كل 165."
        assert final_result_re.search(line) is None
        assert conclusion_re.search(line) is None

    def test_hybrid_comb_line_survives(self) -> None:
        import re

        num_re = r"[-+]?\d[\d.,]*\s*(?:/\s*\d[\d.,]*)?\s*%?"
        final_result_re = re.compile(
            r"(?P<lhs>[PECpec]\s*(?:_?[A-Za-z])?\s*\([^)\n]{0,60}\)\s*=\s*)(?P<rhs>" + num_re + r")"
        )
        # «C(11,3) = (11×10×9)/(3×2×1) = 165» يَنجو (RHS بعد أول = هو «(»).
        assert final_result_re.search("C(11,3) = (11×10×9)/(3×2×1) = 165") is None


# ── 5. source-inspection: الإصلاح موصول والمفاهيمي يسبق subpart ────────────────
class TestSourceWiring:
    def test_helpers_defined(self) -> None:
        assert "def _detect_conceptual_question(" in CLIENT_SRC
        assert "def _format_conceptual_relationship(" in CLIENT_SRC
        assert "_PROCEDURAL_VERBS" in CLIENT_SRC

    def test_conceptual_checked_before_subpart(self) -> None:
        # داخل _build_probability_direct_explanation: المفاهيمي قبل مطابقة الأرقام.
        seg = CLIENT_SRC[CLIENT_SRC.index("def _build_probability_direct_explanation(") :]
        seg = seg[: seg.index("def _format_conceptual_relationship(")]
        conc = seg.index("cls._detect_conceptual_question(question)")
        subp = seg.index("subpart = cls._detect_subpart_question(question)")
        assert conc < subp, "conceptual check MUST precede number matching (D-125)"

    def test_escape_condition_includes_conceptual(self) -> None:
        # D-127: تطوّر الشرط ليشمل المفهوم المُشخَّص — _conceptual لا يزال جزءاً منه.
        assert "_conceptual = self._detect_conceptual_question(question)" in CLIENT_SRC
        assert "_conceptual or _subpart is not None or _confusion_count >= 2:" in CLIENT_SRC

    def test_relationship_explains_numerator_denominator(self) -> None:
        seg = CLIENT_SRC[CLIENT_SRC.index("def _format_conceptual_relationship(") :]
        seg = seg[: seg.index("\n    async def _build_probability_tree_props")]
        assert "المقام" in seg and "البسط" in seg
        assert "نسبة البسط إلى المقام" in seg  # العلاقة لا الحساب
        assert "_fmt_comb(" in seg  # السطر الهجين الحسابي عبر _fmt_comb (يَنجو من الحجب)
