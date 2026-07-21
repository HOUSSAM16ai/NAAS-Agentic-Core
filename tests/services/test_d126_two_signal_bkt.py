"""D-126/D-157 — الإتقان الصادق ثنائي القناة + محرّك الإتقان الصادق (Honest Mastery Engine).

نفصل **الأداء المدعوم** (assisted — مُضخَّم بالمساعدة) عن **الإتقان الحقيقي الدائم**
(durable). فجوة الوهم = assisted − durable = مقياس النجاح الوحيد (CLAUDE.md §0.6). حتمي
100%، صفر LLM، يبني على BKTEngine القائم (D-074 — لا ملف موازٍ).

D-157 (§6.132) أغلق حلقة فجوة الوهم بثلاثة إصلاحات جوهرية:
1. **إشارة صواب ثلاثية الحالة** (CORRECT/INCORRECT/UNKNOWN) — UNKNOWN ⇒ لا تحديث
   (يُصلِح التحيّز الهابط ISS-123: الافتراض القديم كان UNKNOWN⇒خطأ).
2. **قناة دائمة بمنحنى نسيان متّصل** (Half-Life Regression) — تتراكم بالدليل غير المدعوم
   المؤجَّل وتضمحلّ بالزمن (يُصلِح ISS-124: البوّابة الثنائية الصارمة جمّدت durable على 0).
   الثابت المضاد للوهم محفوظ: الكسب ∝ generation_weight(support) ⇒ ≈0 عند الدعم الثقيل.
3. **بثّ فجوة الوهم إلى Prometheus** (M9) — كانت تُحسَب وتُسجَّل في اللوغ بلا رصد.

stdlib + standalone replicas + source-inspection — يعمل في الـ sandbox بلا pydantic.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_SRC = (REPO_ROOT / "app/services/skills/bkt_engine.py").read_text(encoding="utf-8")

# ── نُسَخ standalone مطابقة لخوارزمية المحرّك (sandbox-safe replicas) ────────────
_LEAK = {1: 0.85, 2: 0.55, 3: 0.30, 4: 0.12, 5: 0.0}
_GEN = {1: 0.10, 2: 0.30, 3: 0.55, 4: 0.80, 5: 1.0}
_P_S, _P_G, _P_T = 0.10, 0.20, 0.12
# D-157 forgetting-curve constants (mirror bkt_engine.py)
_HL_BASE, _HL_MAX = 1.0, 180.0
_BASE_GAIN, _NOV_RETEST, _FAIL_DECAY = 0.5, 0.5, 0.7


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


def update_mastery(prior: float, correct: bool) -> float:
    """BKT بايزي أحادي الإشارة (mirror ``bkt_engine.update_mastery``)."""
    prior = min(max(prior, 0.0), 1.0)
    if correct:
        num = prior * (1 - _P_S)
        den = num + (1 - prior) * _P_G
    else:
        num = prior * _P_S
        den = num + (1 - prior) * (1 - _P_G)
    post = num / den if den > 0 else prior
    return round(min(max(post + (1 - post) * _P_T, 0.0), 1.0), 4)


def update_mastery_3state(prior: float, sig: str) -> float:
    """D-157: UNKNOWN ⇒ prior دون تغيير (يُصلِح التحيّز الهابط)."""
    if sig == "unknown":
        return round(min(max(prior, 0.0), 1.0), 4)
    return update_mastery(prior, sig == "correct")


def half_life_days(d: float) -> float:
    d = min(max(d, 0.0), 1.0)
    return _HL_BASE + (_HL_MAX - _HL_BASE) * (d * d)


def predicted_recall(d: float, days: float) -> float:
    hl = half_life_days(d)
    return 2.0 ** (-max(0.0, days) / hl) if hl > 0 else 0.0


def durable_continuous(pd: float, correct: bool, *, s: int, h: float = 0.0, novel: bool = False):
    """D-157: منحنى نسيان متّصل — mirror ``bkt_engine.durable_update_continuous``."""
    pd = min(max(pd, 0.0), 1.0)
    days = max(0.0, h / 24.0)
    decayed = pd * predicted_recall(pd, days)
    cause = "none"
    if correct:
        gain = _BASE_GAIN * generation_weight(s) * delay_weight(h) * (1.0 if novel else _NOV_RETEST)
        dur = decayed + (1 - decayed) * gain
        if gain > 0:
            cause = "unaided_delayed_novel" if (novel and s >= 4) else "retest"
    elif s >= 4:
        dur = decayed * _FAIL_DECAY
    else:
        dur = decayed
    return round(min(max(dur, 0.0), 1.0), 4), cause


def assisted_channel(prior: float, correct: bool, *, s: int, h: float = 0.0) -> float:
    """القناة المدعومة (mirror ``update_mastery_two_signal`` assisted branch)."""
    prior = min(max(prior, 0.0), 1.0)
    p_ck = 1 - _P_S
    p_cu = _P_G + (1 - _P_G) * scaffold_leak(s)
    if correct:
        num = prior * p_ck
        den = num + (1 - prior) * p_cu
    else:
        num = prior * (1 - p_ck)
        den = num + (1 - prior) * (1 - p_cu)
    post = num / den if den > 0 else prior
    return round(
        min(max(post + (1 - post) * (_P_T * generation_weight(s) * delay_weight(h)), 0.0), 1.0), 4
    )


def illusion_gap(a: float, d: float) -> float:
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


# ── 2. الإشارة الثلاثية (D-157) — UNKNOWN لا يُهبِط الإتقان ──────────────────────
class TestThreeStateSignal:
    def test_unknown_carries_prior_unchanged(self) -> None:
        # جذر ISS-123: رسالة محايدة (طلب تمرين/تحية) ⇒ لا تحديث.
        assert update_mastery_3state(0.42, "unknown") == 0.42

    def test_correct_raises_mastery(self) -> None:
        assert update_mastery_3state(0.30, "correct") > 0.30

    def test_incorrect_lowers_mastery(self) -> None:
        assert update_mastery_3state(0.60, "incorrect") < 0.60

    def test_unknown_no_longer_treated_as_wrong(self) -> None:
        # الفرق الجوهري: UNKNOWN ≠ INCORRECT (كان الافتراض القديم يساويهما).
        assert update_mastery_3state(0.50, "unknown") == 0.50
        assert update_mastery_3state(0.50, "incorrect") < 0.50


# ── 3. منحنى النسيان (D-157) — durable يرتفع بصدق ويضمحلّ بالزمن ──────────────────
class TestForgettingCurve:
    def test_half_life_grows_with_durable(self) -> None:
        assert half_life_days(0.0) < half_life_days(0.5) < half_life_days(1.0)
        assert half_life_days(1.0) == 180.0

    def test_predicted_recall_decays_over_time(self) -> None:
        assert predicted_recall(0.5, 0.0) == 1.0  # فوري ⇒ استدعاء كامل
        assert predicted_recall(0.5, 1000.0) < 0.5  # بعد زمن طويل ⇒ نسيان

    def test_strong_mastery_resists_forgetting(self) -> None:
        # إتقان راسخ (durable عالٍ) ⇒ نصف-عمر طويل ⇒ نسيان أبطأ.
        assert predicted_recall(0.95, 30.0) > predicted_recall(0.2, 30.0)


# ── 4. البرهان الحاسم: المُسلَّم الحل (durable≈0) مقابل المُولِّد (durable عالٍ) ──
class TestHonestMasteryProof:
    def test_answer_fed_student_durable_stays_low(self) -> None:
        # 6 تفاعلات «صحيحة» بمثال محلول كامل (support=1) ⇒ durable يبقى منخفضاً جداً
        # (الثابت المضاد للوهم: generation_weight(1)=0.10 ⇒ كسب ≈0).
        d = 0.0
        for _ in range(6):
            d, _c = durable_continuous(d, True, s=1, h=0.0)
        assert d < 0.1, f"answer-fed durable must stay low, got {d}"

    def test_generator_student_durable_rises(self) -> None:
        # حاول/فشل → غير مدعوم مؤجَّل جديد ×2 ⇒ durable يرتفع بصدق (D-157 يُصلِح
        # ISS-124: كان مُجمَّداً على 0 في النموذج القديم داخل الدردشة).
        d = 0.0
        d, _ = durable_continuous(d, False, s=4, h=0.0)  # محاولة فاشلة
        d, _ = durable_continuous(d, True, s=4, h=0.0)  # نجاح شبه-مدعوم
        d, _ = durable_continuous(d, True, s=5, h=48.0, novel=True)  # غير مدعوم مؤجَّل جديد
        d, _ = durable_continuous(d, True, s=5, h=72.0, novel=True)
        assert d >= 0.5, f"generator durable must rise, got {d}"

    def test_illusion_gap_higher_for_answer_fed_than_generator(self) -> None:
        # المحرّك الصادق يميّز: الأداء المدعوم يعكس prior (0.25) ولا يهبط بالسقالة،
        # وdurable يبقى ~0 للمُسلَّم الحل ويرتفع للمُولِّد ⇒ فجوة وهم أعلى للأول.
        a_af, d_af = 0.25, 0.0
        for _ in range(6):
            a_af = assisted_channel(a_af, True, s=1, h=0.0)
            d_af = durable_continuous(d_af, True, s=1, h=0.0)[0]
        a_g, d_g = 0.25, 0.0
        for s, h, nv in ((4, 0.0, False), (5, 48.0, True), (5, 72.0, True)):
            a_g = assisted_channel(a_g, True, s=s, h=h)
            d_g = durable_continuous(d_g, True, s=s, h=h, novel=nv)[0]
        assert illusion_gap(a_af, d_af) > illusion_gap(a_g, d_g)

    def test_anti_illusion_invariant_heavy_support_near_zero_gain(self) -> None:
        # الثابت الأهم: الدعم الثقيل (support=1) يمنح ~عُشر كسب غير المدعوم فقط
        # (generation_weight(1)=0.10) — فلا يُضخَّم durable بالمساعدة.
        d, _ = durable_continuous(0.0, True, s=1, h=48.0, novel=True)
        d5, _ = durable_continuous(0.0, True, s=5, h=48.0, novel=True)
        assert d < 0.08, f"heavy-support correct must stay near zero, got {d}"
        assert d5 > 0.4  # غير مدعوم بنفس الظرف ⇒ كسب كبير
        assert d5 > 8 * d  # النسبة ~10× (generation_weight)

    def test_durable_decays_on_supported_failure(self) -> None:
        # فشل رغم مساعدة ثقيلة (support≥4) ⇒ durable يهبط (الإتقان لم يكن حقيقياً).
        d, _ = durable_continuous(0.8, False, s=4, h=0.0)
        assert d < 0.8

    def test_durable_rise_cause_labelled(self) -> None:
        # M9: سبب الارتفاع مُصنَّف للقياس.
        _, cause = durable_continuous(0.0, True, s=5, h=48.0, novel=True)
        assert cause == "unaided_delayed_novel"
        _, cause2 = durable_continuous(0.3, True, s=3, h=2.0, novel=False)
        assert cause2 == "retest"
        _, cause3 = durable_continuous(0.5, False, s=2, h=0.0)
        assert cause3 == "none"


# ── 5. فجوة الوهم = المقياس الوحيد ──────────────────────────────────────────────
class TestIllusionGap:
    def test_gap_is_assisted_minus_durable(self) -> None:
        assert illusion_gap(0.9, 0.2) == 0.7
        assert illusion_gap(0.5, 0.5) == 0.0
        assert illusion_gap(0.3, 0.8) == 0.0  # لا تنزل تحت الصفر


# ── 6. source-inspection: المحرّك (حتمي، يبني على القائم، صفر LLM) ───────────────
class TestEngineWiring:
    def test_three_state_functions_defined(self) -> None:
        for fn in (
            "def infer_correctness_signal_3state(",
            "def update_mastery_3state(",
            "def infer_correctness_signal(",  # توافق خلفي
        ):
            assert fn in ENGINE_SRC, fn

    def test_forgetting_curve_functions_defined(self) -> None:
        for fn in (
            "def half_life_days(",
            "def predicted_recall(",
            "def durable_update_continuous(",
        ):
            assert fn in ENGINE_SRC, fn
        assert "2.0 ** (-" in ENGINE_SRC  # منحنى النسيان الأسّي

    def test_two_signal_delegates_to_continuous(self) -> None:
        # D-157: البوّابة الثنائية الصارمة استُبدلت — لم تَعُد ثوابتها موجودة.
        assert "durable_update_continuous(" in ENGINE_SRC
        assert "_DURABLE_UNAIDED_LEVEL" not in ENGINE_SRC
        assert "_DURABLE_MIN_DELAY_HOURS" not in ENGINE_SRC

    def test_builds_on_existing_engine_no_parallel_file(self) -> None:
        # D-074: لا ملف BKT موازٍ — الدوال داخل bkt_engine.py القائم.
        assert not (REPO_ROOT / "app/services/skills/bkt_two_signal.py").exists()
        assert "update_mastery_two_signal" in ENGINE_SRC

    def test_update_mastery_unchanged_backward_compat(self) -> None:
        assert "def update_mastery(" in ENGINE_SRC

    def test_correctness_signal_field_on_evaluation(self) -> None:
        assert "correctness_signal: CorrectnessSignal" in ENGINE_SRC
        assert "correctness_signal=signal" in ENGINE_SRC  # evaluate() يملؤه


# ── 7. التخزين + المخطط + التوصيل + القياس (M9) source-inspection ───────────────
_SCHEMA_SRC = (REPO_ROOT / "app/core/db_schema_config.py").read_text(encoding="utf-8")
_PERSIST_SRC = (REPO_ROOT / "app/services/analytics/bkt_persistence.py").read_text(encoding="utf-8")
_ORM_SRC = (REPO_ROOT / "app/core/domain/bkt_analytics.py").read_text(encoding="utf-8")
# D-173 Stage 2b: customer_chat helpers extracted to customer_chat_support/* —
# read the composed source via the manifest so structural asserts survive.
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "_cc_sources", REPO_ROOT / "app/api/routers/customer_chat_support/_sources.py"
)
_ccsrc = _ilu.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_ccsrc)
_CHAT_SRC = _ccsrc.read_customer_chat_source()
_METRICS_SRC = (REPO_ROOT / "app/services/skills/tutor_metrics.py").read_text(encoding="utf-8")
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "_doctrine_sources", REPO_ROOT / "app/services/skills/doctrine/_sources.py"
)
_dsrc = _ilu.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_dsrc)
# D-173 Stage 2a: doctrine.py صار حزمة — البوّابات تقرأ المصدر المُركَّب عبر المانيفست.
_DOCTRINE_SRC = _dsrc.read_doctrine_source()


class TestStorageWiring:
    def test_schema_has_durable_columns(self) -> None:
        bkt_block = _SCHEMA_SRC[_SCHEMA_SRC.index('"student_bkt_analytics": {') :][:3000]
        for col in ("durable_mastery", "support_level", "delay_hours", "novel_item"):
            assert col in bkt_block, col
        assert "ADD COLUMN" in bkt_block and "durable_mastery" in bkt_block

    def test_orm_has_durable_fields(self) -> None:
        for f in ("durable_mastery", "support_level", "delay_hours", "novel_item"):
            assert f in _ORM_SRC, f

    def test_persistence_computes_durable_continuous(self) -> None:
        # D-157: يقرأ prior_durable + يحسب durable عبر durable_update_continuous.
        assert "latest_durable_mastery" in _PERSIST_SRC
        assert "durable_update_continuous(" in _PERSIST_SRC
        assert "update_mastery_two_signal(" not in _PERSIST_SRC  # لم يَعُد يُستخدَم
        assert "illusion_gap(" in _PERSIST_SRC

    def test_persistence_unknown_signal_carries_forward(self) -> None:
        # honest: UNKNOWN ⇒ durable يُحمَل دون تضخيم (carry-forward، لا تحديث).
        assert 'evaluation.correctness_signal == "unknown"' in _PERSIST_SRC
        assert "durable = round(min(max(prior_durable, 0.0), 1.0), 4)" in _PERSIST_SRC

    def test_persistence_derives_novel_and_threads_signal(self) -> None:
        assert "effective_novel = novel_item or prior_count == 0" in _PERSIST_SRC
        assert "correctness_signal=correctness_signal" in _PERSIST_SRC

    def test_persistence_emits_m9_metrics(self) -> None:
        # A4 (M9): بثّ فجوة الوهم + القناتين + سبب الارتفاع.
        assert "record_illusion_gap(gap)" in _PERSIST_SRC
        assert "record_mastery_channels(" in _PERSIST_SRC
        assert "record_durable_rise(" in _PERSIST_SRC

    def test_metrics_module_exports_m9(self) -> None:
        for fn in (
            "def record_illusion_gap(",
            "def record_mastery_channels(",
            "def record_durable_rise(",
        ):
            assert fn in _METRICS_SRC, fn
        assert "cogniforge_tutor_illusion_gap" in _METRICS_SRC
        assert "cogniforge_tutor_durable_mastery" in _METRICS_SRC

    def test_chat_passes_support_level_and_symbolic_override(self) -> None:
        # A1b/A2: الأوراكل الرمزي يُحسَب داخل المهمة الخلفية (خارج المسار الحيّ)؛
        # support_level يُمرَّر بعد حساب البيداغوجيا.
        assert "def _derive_correctness_override(" in _CHAT_SRC
        assert "_derive_correctness_override(question, history_messages)" in _CHAT_SRC
        seg = _CHAT_SRC[_CHAT_SRC.index("async def _evaluate_bkt_cards(") :][:2400]
        assert "support_level: int | None = None" in seg
        assert "correctness_signal: str | None = None" in seg
        assert "correctness_signal=signal" in seg

    def test_doctrine_version_bumped_and_continuous_rule(self) -> None:
        assert 'BKT_COGNITIVE_DOCTRINE_VERSION: Final[str] = "3.0.0"' in _DOCTRINE_SRC
        assert "منحنى نسيان متّصل" in _DOCTRINE_SRC
        assert "فجوة الوهم = assisted − durable" in _DOCTRINE_SRC
