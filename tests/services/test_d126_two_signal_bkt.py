"""D-126 — الإتقان الصادق ثنائي القناة (Two-Signal Honest Mastery).

جوهر «صدق BKT» (roadmap M6): نفصل **الأداء المدعوم** (assisted — مُضخَّم بالمساعدة) عن
**الإتقان الحقيقي الدائم** (durable — مُثبَت بأداء غير مدعوم + مؤجَّل + على بند جديد). فجوة
الوهم = assisted − durable = مقياس النجاح الوحيد (CLAUDE.md §0.6). حتمي 100%، صفر LLM،
يبني على BKTEngine القائم (D-074 — لا ملف موازٍ).

البرهان الحاسم (سكربت المالك): الطالب المُسلَّم الحل ⇒ durable=0.0 (فجوة وهم عالية)؛ الطالب
الذي يُولِّد بنفسه (غير مدعوم + مؤجَّل + جديد) ⇒ durable عالٍ (فجوة وهم منخفضة).

stdlib + standalone replica + source-inspection — يعمل في الـ sandbox بلا pydantic.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_SRC = (REPO_ROOT / "app/services/skills/bkt_engine.py").read_text(encoding="utf-8")

# ── نُسَخ standalone مطابقة لخوارزمية D-126 (sandbox-safe replicas) ────────────
_LEAK = {1: 0.85, 2: 0.55, 3: 0.30, 4: 0.12, 5: 0.0}
_GEN = {1: 0.10, 2: 0.30, 3: 0.55, 4: 0.80, 5: 1.0}
_P_S, _P_G, _P_T = 0.10, 0.20, 0.12


def scaffold_leak(s: int) -> float:
    return _LEAK.get(s, 0.0)


def generation_weight(s: int) -> float:
    return _GEN.get(s, 1.0)


def delay_weight(h: float) -> float:
    if h < 0.5:
        return 0.3
    if h < 24.0:
        return 0.7
    return 1.0


def update_two_signal(prior, correct, *, s, h=0.0, novel=False, pd=0.0):
    prior = min(max(prior, 0.0), 1.0)
    pd = min(max(pd, 0.0), 1.0)
    p_ck = 1 - _P_S
    p_cu = _P_G + (1 - _P_G) * scaffold_leak(s)
    if correct:
        num = prior * p_ck
        den = num + (1 - prior) * p_cu
    else:
        num = prior * (1 - p_ck)
        den = num + (1 - prior) * (1 - p_cu)
    post = num / den if den > 0 else prior
    assisted = post + (1 - post) * (_P_T * generation_weight(s) * delay_weight(h))
    dur = pd
    if correct and s >= 5 and h >= 24 and novel:
        dur = pd + (1 - pd) * 0.5
    elif (not correct) and s >= 4:
        dur = pd * 0.7
    return round(min(max(assisted, 0.0), 1.0), 4), round(min(max(dur, 0.0), 1.0), 4)


def illusion_gap(a, d):
    return round(max(0.0, min(max(a, 0.0), 1.0) - min(max(d, 0.0), 1.0)), 4)


# ── 1. أوزان السقالة/التوليد/المباعدة ──────────────────────────────────────────
class TestWeights:
    def test_scaffold_leak_ladder(self) -> None:
        assert scaffold_leak(1) == 0.85  # مثال محلول كامل ⇒ تسريب أقصى
        assert scaffold_leak(5) == 0.0  # غير مدعوم ⇒ صفر تسريب (تشخيصي تماماً)

    def test_generation_weight_ladder(self) -> None:
        assert generation_weight(1) == 0.10
        assert generation_weight(5) == 1.0  # توليد كامل ⇒ ترسيخ أقصى

    def test_delay_weight_spacing(self) -> None:
        assert delay_weight(0.0) == 0.3  # فوري ⇒ حفظ لحظي
        assert delay_weight(2.0) == 0.7
        assert delay_weight(48.0) == 1.0  # مؤجَّل ≥ يوم ⇒ تعلّم دائم


# ── 2. البرهان الحاسم: المُسلَّم الحل (durable=0.0) مقابل المُولِّد (durable عالٍ) ──
class TestHonestMasteryProof:
    def test_answer_fed_student_durable_zero(self) -> None:
        # 6 تفاعلات «صحيحة» بمثال محلول كامل (support=1) ⇒ durable يبقى 0.0.
        a, d = 0.25, 0.0
        for _ in range(6):
            a, d = update_two_signal(a, True, s=1, h=0.0, pd=d)
        assert d == 0.0, f"answer-fed durable must stay 0.0, got {d}"
        assert illusion_gap(a, d) > 0.2, "answer-fed ⇒ high illusion gap (fluency illusion)"

    def test_generator_student_durable_high(self) -> None:
        # حاول/فشل → تلميح أدنى → غير مدعوم مؤجَّل جديد ×2.
        a, d = 0.25, 0.0
        a, d = update_two_signal(a, False, s=4, h=0.0, pd=d)
        a, d = update_two_signal(a, True, s=4, h=0.0, pd=d)
        a, d = update_two_signal(a, True, s=5, h=48, novel=True, pd=d)
        a, d = update_two_signal(a, True, s=5, h=72, novel=True, pd=d)
        assert d >= 0.7, f"generator durable must be high, got {d}"
        assert illusion_gap(a, d) < 0.2, "generator ⇒ low illusion gap (real mastery)"

    def test_durable_gate_requires_all_four_conditions(self) -> None:
        # correct + support>=5 + delay>=24 + novel — أيّ شرط مفقود ⇒ لا ارتفاع.
        assert update_two_signal(0.5, True, s=5, h=48, novel=True, pd=0.0)[1] > 0.0  # كلها
        assert update_two_signal(0.5, True, s=4, h=48, novel=True, pd=0.0)[1] == 0.0  # مدعوم
        assert update_two_signal(0.5, True, s=5, h=2, novel=True, pd=0.0)[1] == 0.0  # فوري
        assert update_two_signal(0.5, True, s=5, h=48, novel=False, pd=0.0)[1] == 0.0  # ليس جديداً
        assert update_two_signal(0.5, False, s=5, h=48, novel=True, pd=0.0)[1] == 0.0  # خاطئ

    def test_durable_decays_on_supported_failure(self) -> None:
        # فشل رغم مساعدة ثقيلة (support>=4) ⇒ durable يهبط (الإتقان لم يكن حقيقياً).
        _, d = update_two_signal(0.5, False, s=4, h=0.0, pd=0.8)
        assert d < 0.8 and abs(d - 0.56) < 1e-6  # 0.8 * 0.7


# ── 3. فجوة الوهم = المقياس الوحيد ──────────────────────────────────────────────
class TestIllusionGap:
    def test_gap_is_assisted_minus_durable(self) -> None:
        assert illusion_gap(0.9, 0.2) == 0.7
        assert illusion_gap(0.5, 0.5) == 0.0
        assert illusion_gap(0.3, 0.8) == 0.0  # لا تنزل تحت الصفر


# ── 4. source-inspection: حتمي، يبني على القائم، صفر LLM ────────────────────────
class TestSourceWiring:
    def test_functions_defined(self) -> None:
        for fn in (
            "def scaffold_leak(",
            "def generation_weight(",
            "def delay_weight(",
            "def update_mastery_two_signal(",
            "def illusion_gap(",
        ):
            assert fn in ENGINE_SRC, fn

    def test_exported(self) -> None:
        for name in (
            '"scaffold_leak"',
            '"generation_weight"',
            '"delay_weight"',
            '"update_mastery_two_signal"',
            '"illusion_gap"',
        ):
            assert name in ENGINE_SRC, name

    def test_builds_on_existing_engine_no_parallel_file(self) -> None:
        # D-074: لا ملف BKT موازٍ — الدوال داخل bkt_engine.py القائم.
        assert not (REPO_ROOT / "app/services/skills/bkt_two_signal.py").exists()
        assert "update_mastery_two_signal" in ENGINE_SRC

    def test_update_mastery_unchanged_backward_compat(self) -> None:
        # update_mastery القائم يبقى (توافق خلفي — لا كسر D-118/D-119).
        assert "def update_mastery(" in ENGINE_SRC

    def test_durable_constants_present(self) -> None:
        assert "_DURABLE_UNAIDED_LEVEL" in ENGINE_SRC
        assert "_DURABLE_MIN_DELAY_HOURS" in ENGINE_SRC


# ── 5. التخزين + المخطط + التوصيل (B2/B3/B4 source-inspection) ──────────────────
_SCHEMA_SRC = (REPO_ROOT / "app/core/db_schema_config.py").read_text(encoding="utf-8")
_PERSIST_SRC = (REPO_ROOT / "app/services/analytics/bkt_persistence.py").read_text(encoding="utf-8")
_ORM_SRC = (REPO_ROOT / "app/core/domain/bkt_analytics.py").read_text(encoding="utf-8")
_CHAT_SRC = (REPO_ROOT / "app/api/routers/customer_chat.py").read_text(encoding="utf-8")
_REDACT_SRC = (REPO_ROOT / "app/services/skills/answer_redaction_skill.py").read_text(
    encoding="utf-8"
)
_DOCTRINE_SRC = (REPO_ROOT / "app/services/skills/doctrine.py").read_text(encoding="utf-8")


class TestStorageWiring:
    def test_schema_has_durable_columns(self) -> None:
        # B2: الأعمدة في columns + auto_fix (auto-migration §6.77) + create_table.
        bkt_block = _SCHEMA_SRC[_SCHEMA_SRC.index('"student_bkt_analytics": {') :][:3000]
        for col in ("durable_mastery", "support_level", "delay_hours", "novel_item"):
            assert col in bkt_block, col
        assert "ADD COLUMN" in bkt_block and "durable_mastery" in bkt_block  # auto_fix ALTER

    def test_orm_has_durable_fields(self) -> None:
        for f in ("durable_mastery", "support_level", "delay_hours", "novel_item"):
            assert f in _ORM_SRC, f

    def test_persistence_computes_durable(self) -> None:
        # B3: يقرأ prior_durable + يحسب durable عبر update_mastery_two_signal.
        assert "latest_durable_mastery" in _PERSIST_SRC
        assert "update_mastery_two_signal(" in _PERSIST_SRC
        assert "illusion_gap(" in _PERSIST_SRC
        assert "durable_mastery=evaluation.durable_mastery" in _PERSIST_SRC

    def test_persistence_no_support_level_no_inflation(self) -> None:
        # honest: بلا support_level ⇒ durable يُحمَل دون تضخيم (carry-forward).
        assert "if support_level is not None:" in _PERSIST_SRC
        assert "durable = round(min(max(prior_durable, 0.0), 1.0), 4)" in _PERSIST_SRC

    def test_chat_passes_support_level_param(self) -> None:
        # B3: _evaluate_bkt_cards يقبل + يمرّر support_level/novel_item.
        seg = _CHAT_SRC[_CHAT_SRC.index("async def _evaluate_bkt_cards(") :][:1600]
        assert "support_level: int | None = None" in seg
        assert "support_level=support_level" in seg

    def test_no_reveal_reuses_redaction(self) -> None:
        # B4: audit_no_reveal يُعيد استخدام redact_final_answers (لا حارس موازٍ).
        assert "def audit_no_reveal(" in _REDACT_SRC
        assert "redact_final_answers(text, support_level=5)" in _REDACT_SRC
        assert not (REPO_ROOT / "naas").exists()  # لا scaffold مستقل (قرار المالك)

    def test_doctrine_two_signal_rule_and_version(self) -> None:
        # B5: ترقية الـ doctrine + قاعدة فجوة الوهم.
        assert 'BKT_COGNITIVE_DOCTRINE_VERSION: Final[str] = "2.0.0"' in _DOCTRINE_SRC
        assert "فجوة الوهم = assisted − durable" in _DOCTRINE_SRC
        assert "durable الصادق" in _DOCTRINE_SRC
