"""D-104 — اختبارات طبقة البيداغوجيا التكيفية (إغلاق حلقة BKT).

«المعيار الأعلى ليس الانبهار اللحظي، بل الاستقلال المعرفي»: قراءة الإتقان
تُحدِّد عمق التدريس — socratic للمتمكن، scaffolded للمبتدئ، والتقاط
المفاهيم الخاطئة قبل أن تتجذر.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source
from app.services.skills.adaptive_pedagogy_skill import (
    DIRECTIVE_MAX_CHARS,
    GUIDED_THRESHOLD,
    SOCRATIC_THRESHOLD,
    AdaptivePedagogySkill,
    PedagogyInput,
    get_adaptive_pedagogy_skill,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def skill() -> AdaptivePedagogySkill:
    return get_adaptive_pedagogy_skill()


class TestGuidancePolicy:
    """سياسة العتبات الحتمية — نفس المدخلات تُنتج نفس المستوى دائماً."""

    @pytest.mark.parametrize(
        ("mastery", "load", "expected"),
        [
            (0.9, "medium", "socratic"),
            (0.7, "medium", "socratic"),  # حدّ العتبة شامل
            (0.69, "medium", "guided"),
            (0.5, "medium", "guided"),
            (0.35, "medium", "guided"),  # حدّ العتبة شامل
            (0.34, "medium", "scaffolded"),
            (0.1, "medium", "scaffolded"),
            (None, "medium", "scaffolded"),  # لا بيانات = سقالات (أمان تربوي)
            (0.9, "high", "guided"),  # الحِمل المرتفع يُخفِّض درجة
            (0.5, "high", "scaffolded"),
            (0.1, "high", "scaffolded"),  # لا أدنى من السقالات
            (0.9, "low", "socratic"),
        ],
    )
    def test_thresholds(self, skill, mastery, load, expected):
        d = skill.derive(
            PedagogyInput(
                question="سؤال عن التكامل بالتجزئة",
                concept_id="integration",
                mastery=mastery,
                cognitive_load=load,
            )
        )
        assert d.guidance_level == expected

    def test_deterministic(self, skill):
        """نفس المدخلات ⇒ نفس التوجيه حرفياً (قابلية pytest — doctrine قاعدة 4)."""
        payload = PedagogyInput(question="احسب النهاية", concept_id="limits", mastery=0.6)
        assert skill.derive(payload) == skill.derive(payload)

    def test_thresholds_constants_guard(self):
        """تغيير العتبات يتطلب ترقية doctrine — هذا الاختبار يلتقط أي عبث صامت."""
        assert SOCRATIC_THRESHOLD == 0.7
        assert GUIDED_THRESHOLD == 0.35


class TestMisconceptionGuard:
    """وكيل التقاط المفاهيم الخاطئة قبل أن تتجذر."""

    def test_integration_product_misconception(self, skill):
        d = skill.derive(
            PedagogyInput(
                question="هل تكامل الجداء يساوي جداء التكاملين؟",
                concept_id="integration",
                mastery=0.5,
            )
        )
        assert d.misconception_alerts
        assert "بالتجزئة" in d.misconception_alerts[0]
        assert "انتبه" in d.directive_text

    def test_probability_independence_misconception(self, skill):
        d = skill.derive(
            PedagogyInput(
                question="حسبت جداء الاحتمالين مباشرة فهل هذا صحيح؟",
                concept_id="probability",
                mastery=0.5,
            )
        )
        assert d.misconception_alerts
        assert "الاستقلال" in d.misconception_alerts[0]

    def test_no_false_positive_on_clean_question(self, skill):
        """سؤال سليم لا يستحق تنبيهاً — التصحيح للفكرة الخاطئة فقط."""
        d = skill.derive(
            PedagogyInput(
                question="احسب تكامل x ln(x) بالتجزئة",
                concept_id="integration",
                mastery=0.5,
            )
        )
        assert d.misconception_alerts == ()
        assert "انتبه" not in d.directive_text

    def test_catalog_is_concept_scoped(self, skill):
        """marker مفهومٍ آخر لا يُطلق تنبيهاً خارج مفهومه."""
        d = skill.derive(
            PedagogyInput(
                question="هل تكامل الجداء يساوي جداء التكاملين؟",
                concept_id="probability",  # المفهوم المصنَّف مختلف
                mastery=0.5,
            )
        )
        assert d.misconception_alerts == ()


class TestDirectiveSafety:
    """قواعد D-067: قصير، عربي بسيط، بلا box-drawing وبلا LaTeX."""

    @pytest.mark.parametrize("mastery", [0.9, 0.5, 0.1, None])
    @pytest.mark.parametrize("load", ["low", "medium", "high"])
    def test_length_and_forbidden_chars(self, skill, mastery, load):
        d = skill.derive(
            PedagogyInput(
                question="هل تكامل الجداء يساوي جداء التكاملين؟ اشرح النهاية مالانهاية على مالانهاية",
                concept_id="integration",
                mastery=mastery,
                cognitive_load=load,
            )
        )
        assert len(d.directive_text) <= DIRECTIVE_MAX_CHARS
        # box-drawing (U+2500–U+257F) ممنوعة (D-067)
        assert not any(0x2500 <= ord(c) <= 0x257F for c in d.directive_text)
        assert "$" not in d.directive_text
        assert "\\(" not in d.directive_text


class TestWiringInvariants:
    """no-ZOMBIE (نمط D-073): الـ skill مُستهلَك فعلاً على المسار الحي."""

    ROUTER_SRC = (REPO_ROOT / "app/api/routers/customer_chat.py").read_text(encoding="utf-8")
    CLIENT_SRC = read_tutor_source()

    def test_router_builds_directive_with_isolated_session(self):
        assert "_build_pedagogy_directive" in self.ROUTER_SRC
        helper_start = self.ROUTER_SRC.index("async def _build_pedagogy_directive")
        # D-137: نقتطع جسم الدالة كاملاً حتى التعريف التالي (لا نافذة ثابتة تقطع except).
        rest = self.ROUTER_SRC[helper_start + 1 :]
        nxt = rest.find("\nasync def ")
        nxt2 = rest.find("\ndef ")
        end = min(p for p in (nxt, nxt2) if p != -1) if (nxt != -1 or nxt2 != -1) else len(rest)
        helper_seg = rest[:end]
        # جلسة DB معزولة + سقف زمني + fail-open
        assert "async_session_factory()" in helper_seg
        assert "asyncio.wait_for" in helper_seg
        # D-133/D-137: fail-open يُرجِع snapshot آمن بـ directive فارغ (لا bare `return ""`).
        assert '_PedagogySnapshot("",' in helper_seg

    def test_router_passes_directive_in_context(self):
        assert '"pedagogy_directive": pedagogy' in self.ROUTER_SRC

    def test_client_does_not_prepend_directive_d117(self):
        # D-117 (فصل الطبقات): التوجيه لم يَعُد يُسبَق للسؤال — كان النموذج يُردّده
        # حرفياً («[توجيه تربوي] ... مستوى الدعم: ...») فيرى الطالب «هندسة التعليم».
        # العمق يصل عبر support_level (في context → SynthesizerNode). لا prepend.
        assert 'f"[توجيه تربوي]' not in self.CLIENT_SRC, "D-117: directive prepend must be gone"
        # support_level مقروء في الـ client ويُمرَّر للـ payload عبر context
        assert 'get("support_level")' in self.CLIENT_SRC
        # D-137: الترتيب الجوهري — `_effective_question` (prepend MODE_B) يُبنى **قبل** الـ payload
        # الذي يحمل routing_mode (فتصل تعليمة MODE_B للسؤال). قراءة support_level إشارة مستقلّة.
        eff_pos = self.CLIENT_SRC.index("_effective_question = (")
        payload_pos = self.CLIENT_SRC.index('"routing_mode": "MODE_B" if _is_mode_b else "MODE_A"')
        assert eff_pos < payload_pos

    def test_deterministic_paths_precede_support_level_read(self):
        """التحية/المفهرَس/سؤال-فقط تسبق قراءة support_level — لا تلوّث للمسارات الحتمية."""
        sup_pos = self.CLIENT_SRC.index('get("support_level")')
        for marker in (
            "_greeting_fastpath_response",
            "_has_indexed_match(",
            "_stream_question_only_response(",
        ):
            assert self.CLIENT_SRC.index(marker) < sup_pos, marker

    def test_registry_and_doctrine_registered(self):
        from app.services.skills.doctrine import (
            ADAPTIVE_PEDAGOGY_DOCTRINE_VERSION,
            SKILL_DOCTRINE_MANIFEST,
        )
        from app.services.skills.registry import get_skill_registry

        names = [d.name for d in get_skill_registry().list()]
        assert "adaptive_pedagogy" in names
        entry = SKILL_DOCTRINE_MANIFEST["adaptive_pedagogy"]
        # D-137: النسخة تطوّرت (1.1.0 سُلّم الدعم → 1.2.0 D-114) — نتحقّق من الاتّساق + التطوّر.
        assert entry["version"] == ADAPTIVE_PEDAGOGY_DOCTRINE_VERSION
        major, minor, *_ = (int(x) for x in ADAPTIVE_PEDAGOGY_DOCTRINE_VERSION.split("."))
        assert (major, minor) >= (1, 1)
        assert "customer_chat._build_pedagogy_directive" in entry["consumed_by"]


class TestSupportLadder:
    """D-113: سُلّم الدعم الخماسي — السقالة تتلاشى مع الإتقان."""

    @pytest.mark.parametrize(
        ("mastery", "load", "expected_level", "expected_label"),
        [
            (None, "medium", 1, "worked_example"),
            (0.1, "medium", 1, "worked_example"),
            (0.3, "medium", 2, "completion"),
            (0.5, "medium", 3, "backward_fading"),
            (0.7, "medium", 4, "prompted"),
            (0.9, "medium", 5, "unaided"),
            (0.9, "high", 4, "prompted"),  # حِمل مرتفع ⇒ دعم أكثر (درجة أقل)
            (0.1, "high", 1, "worked_example"),  # لا أقل من 1
        ],
    )
    def test_support_levels(self, skill, mastery, load, expected_level, expected_label):
        d = skill.derive(
            PedagogyInput(question="سؤال عن الاحتمالات", mastery=mastery, cognitive_load=load)
        )
        assert d.support_level == expected_level
        assert d.ladder_label == expected_label
        # D-117: directive_text يحوي «مستوى الدعم» للقياس فقط (لوحة المعلم) — لا
        # يُسبَق للسؤال ولا يصل لأي prompt؛ العمق يصل عبر support_level المنفصل.
        assert "مستوى الدعم" in d.directive_text

    def test_unaided_is_golden_threshold(self, skill):
        """العتبة الذهبية: الإتقان العالي ⇒ بلا دعم (يولّد الطالب الحلّ وحده)."""
        d = skill.derive(PedagogyInput(question="احسب", mastery=0.95))
        assert d.support_level == 5
        assert "بلا مساعدة" in d.directive_text
