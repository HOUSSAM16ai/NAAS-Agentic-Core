"""
D-158 (ISS-124) — Cognitive Turn Engine regression tests.

Proves the three symptoms of the probability catastrophe are dead once
`COGNITIVE_TURN_ENABLED` routes the turn through `_cognitive_turn` over persisted
`tutor_state.kc_progress`:

  S1  never dumps numerator + denominator together (one step per turn)
  S2  a correct "14 على 165" is confirmed even after a >600-char prior message
      (the `_in_socratic_dialogue` 600-char prison is bypassed)
  S3  first "كيف نحسب الحادثة A" yields a diagnostic question, not a dump

Plus: `record_turn` deep-merges `kc_progress` (was loaded-never-written), the
unified flag reader has a single default, and `_build_symbolic_reveal(delivered=)`
drops already-delivered blocks while the default stays byte-identical.

Deterministic + zero-LLM: `_load_canonical_combinations` is monkeypatched to a
faithful BAC-2024 combo; no network, no DB for the decision-logic tests.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.infrastructure.clients.orchestrator_client import OrchestratorClient


def _bac2024_combo():
    """كيس BAC-2024: 4 حمراء + 5 خضراء + 2 بيضاء (n=11, k=3, C(11,3)=165, same=14)."""
    groups = [
        SimpleNamespace(label="كرة حمراء", count=4, is_possible=True, favorable_combinations=4),
        SimpleNamespace(label="كرة خضراء", count=5, is_possible=True, favorable_combinations=10),
        SimpleNamespace(label="كرة بيضاء", count=2, is_possible=False, favorable_combinations=0),
    ]
    return SimpleNamespace(
        n=11, k=3, total_combinations=165, same_group_favorable=14, groups=groups
    )


@pytest.fixture
def combo(monkeypatch):
    c = _bac2024_combo()
    monkeypatch.setattr(
        OrchestratorClient,
        "_load_canonical_combinations",
        classmethod(lambda _cls, _q, _h: c),
    )
    return c


def _run_turn(state: dict, history: list[dict], question: str, prior_assistant: str | None = None):
    """يشغّل دوراً واحداً ويحاكي دمج record_turn للـ kc_progress (كما يفعل customer_chat)."""
    if prior_assistant is not None:
        history.append({"role": "assistant", "content": prior_assistant})
    text, delta = OrchestratorClient._cognitive_turn(question, list(history), state, None)
    merged = dict(state.get("kc_progress") or {})
    for k, v in (delta or {}).items():
        merged[k] = v
    state["kc_progress"] = merged
    state["turn_count"] = int(state.get("turn_count") or 0) + 1
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": text or ""})
    return text or ""


# ── Flag readers ─────────────────────────────────────────────────────────────
def test_semantic_tutor_flag_single_default_true(monkeypatch):
    monkeypatch.delenv("SEMANTIC_TUTOR_ENABLED", raising=False)
    from app.core.feature_flags import semantic_tutor_enabled

    assert semantic_tutor_enabled() is True
    # كلا الموقعين يفوّضان لنفس القارئ (لا افتراض متعارض بعد D-158).
    assert OrchestratorClient._semantic_tutor_enabled() is True


def test_cognitive_turn_flag_default_on_with_rollback_lever(monkeypatch):
    # D-159: الافتراض True (قرار المالك بعد نجاح E2E الحي — قاعدة D-158-f استوفيت).
    monkeypatch.delenv("COGNITIVE_TURN_ENABLED", raising=False)
    from app.core.feature_flags import cognitive_turn_enabled

    assert cognitive_turn_enabled() is True
    assert OrchestratorClient._cognitive_turn_enabled() is True
    # رافعة الرجوع الفوري بلا deploy: env=0 يتقدّم على الافتراض.
    monkeypatch.setenv("COGNITIVE_TURN_ENABLED", "0")
    assert cognitive_turn_enabled() is False
    assert OrchestratorClient._cognitive_turn_enabled() is False


# ── S3: diagnose before explain ──────────────────────────────────────────────
def test_s3_first_help_is_diagnostic_not_dump(combo):
    state: dict = {"kc_progress": {}, "turn_count": 0}
    text = _run_turn(state, [], "كيف نحسب الحادثة A")
    assert "أيّ الألوان يمكن أن تعطينا" in text  # سؤال تشخيصي
    assert "نجمع الحالات الممكنة فقط" not in text and "= 14" not in text  # لا تفريغ بسط
    assert "كل الطرق الممكنة" not in text  # لا تفريغ مقام


# ── S1: progressive single-step disclosure ───────────────────────────────────
def test_s1_one_step_per_turn_no_double_dump(combo):
    state: dict = {"kc_progress": {}, "turn_count": 0}
    history: list[dict] = []
    _run_turn(state, history, "كيف نحسب الحادثة A")  # probe
    t2 = _run_turn(state, history, "الحمراء و الخضراء فقط")  # colours → numerator step
    assert "الحالات الملائمة" in t2 and "14" in t2
    assert "كل الطرق الممكنة" not in t2  # المقام لا يُفرَّغ في نفس الدور (تدريجي)


# ── S2: correct answer confirmed despite >600-char prior (prison bypassed) ────
def test_s2_correct_ratio_confirmed_after_long_prior(combo):
    state: dict = {"kc_progress": {}, "turn_count": 0}
    history: list[dict] = []
    _run_turn(state, history, "كيف نحسب الحادثة A")
    _run_turn(state, history, "الحمراء و الخضراء فقط")
    long_dump = "لنُكمل معاً خطوة بخطوة: " + ("الحالات الملائمة والمقام " * 60)
    assert len(long_dump) > 600
    t3 = _run_turn(state, history, "14 على 165", prior_assistant=long_dump)
    assert "أحسنت" in t3  # اعتراف صريح
    assert "الحادثة B" in t3  # تقدّم للسؤال التالي
    assert "نجمع الحالات الممكنة فقط" not in t3  # لا إعادة تفريغ


def test_no_step_key_emitted_twice(combo):
    state: dict = {"kc_progress": {}, "turn_count": 0}
    history: list[dict] = []
    _run_turn(state, history, "كيف نحسب الحادثة A")
    _run_turn(state, history, "الحمراء و الخضراء فقط")
    _run_turn(state, history, "لم أفهم")
    delivered = (state["kc_progress"].get(OrchestratorClient._KC_PROB_A) or {}).get(
        "representations_delivered", []
    )
    assert len(delivered) == len(set(delivered))  # لا تكرار عبر الكتل


def test_cognitive_turn_fail_open_on_no_state(combo):
    # tutor_state ليس dict ⇒ تسليم للكتل القائمة (None, None)، لا استثناء.
    text, delta = OrchestratorClient._cognitive_turn("كيف نحسب الحادثة A", [], None, None)
    assert text is None and delta is None


# ── _build_symbolic_reveal(delivered=) hardening ─────────────────────────────
def test_reveal_empty_ledger_contains_pins(combo):
    # ISS-148: `delivered` صار إلزامياً — سجلٌّ فارغ يُمرَّر **صراحةً**. كان
    # اختيارياً، فنسيه سبعةٌ من ثمانية مواضع نداء وأعادوا تفريغ ما رآه الطالب.
    out = OrchestratorClient._build_symbolic_reveal("س", [], acknowledge=False, delivered=set())
    assert "ركّب الاحتمال **بنفسك**" in out  # ذيل التوليد المُثبَّت (gate)
    assert "الحالات الملائمة" in out and "كل الطرق الممكنة" in out  # كل الكتل (سجلّ فارغ)
    assert "من كل" not in out  # لا كشف نسبة نهائية


def test_reveal_delivered_drops_shown_blocks(combo):
    # كتلةٌ واحدة مُسلَّمة ⇒ تُحذف هي وحدها، ويبقى ما لم يُسلَّم + الذيل.
    out = OrchestratorClient._build_symbolic_reveal("س", [], delivered={"numerator"})
    assert "الحالات الملائمة" not in out  # البسط مُسلَّم ⇒ محذوف
    assert "كل الطرق الممكنة" in out  # المقام لم يُسلَّم ⇒ يبقى
    assert "ركّب الاحتمال **بنفسك**" in out


def test_reveal_returns_none_when_every_block_was_already_delivered(combo):
    """ISS-148 — وعدٌ بشرحٍ لا يصل أسوأ من خطأ صريح (§0).

    كان هذا الاختبار نفسه يضمن العطب: يمرّر `{numerator, ratio}` ثمّ يؤكّد أن
    الناتج نصٌّ فيه الذيل وحده. وهو **بالحرف** ما تلقّاه طالبٌ في الإنتاج
    (المحادثة 837، الرسالة 4613): «لنُكمل معاً خطوة بخطوة حتى النهاية:» ثمّ ولا
    خطوة — ١٣٦ حرفاً من العدم. العطب لم يكن سهواً؛ كان **محروساً باختبار**.

    القانون الآن: لا شيء ليُقال ⇒ `None`، فيُصعِّد المُنادي إلى خطوةٍ حقيقية.
    """
    out = OrchestratorClient._build_symbolic_reveal("س", [], delivered={"numerator", "ratio"})
    assert out is None


# ── record_turn deep-merges kc_progress (was loaded-never-written) ────────────
@pytest.mark.asyncio
async def test_record_turn_merges_kc_progress():
    import json

    from app.services.analytics.tutor_state_service import TutorStateService

    row = SimpleNamespace(
        active_concept="",
        last_step_emitted="",
        turn_count=0,
        socratic_count_by_concept="{}",
        kc_progress=json.dumps({"prob_event_a": {"attempts": 1}, "keep": {"x": 1}}),
        updated_at=None,
    )

    class _FakeDB:
        def add(self, *_):
            pass

        async def commit(self):
            pass

        async def rollback(self):
            pass

    class _Svc(TutorStateService):
        async def _row(self, _cid):
            return row

    await _Svc(_FakeDB()).record_turn(
        conversation_id=1,
        user_id=1,
        active_concept="prob_event_a",
        assistant_text="خطوة",
        is_socratic_question=False,
        kc_progress={"prob_event_a": {"attempts": 2, "representations_delivered": ["numerator"]}},
    )
    merged = json.loads(row.kc_progress)
    assert merged["prob_event_a"]["attempts"] == 2  # الدلتا تحلّ محلّ المفتاح
    assert merged["prob_event_a"]["representations_delivered"] == ["numerator"]
    assert merged["keep"] == {"x": 1}  # المفاتيح الأخرى محفوظة


@pytest.mark.asyncio
async def test_record_turn_survives_malformed_kc_progress_json():
    from app.services.analytics.tutor_state_service import TutorStateService

    row = SimpleNamespace(
        active_concept="",
        last_step_emitted="",
        turn_count=0,
        socratic_count_by_concept="{}",
        kc_progress="{not valid json",
        updated_at=None,
    )

    class _FakeDB:
        def add(self, *_):
            pass

        async def commit(self):
            pass

        async def rollback(self):
            pass

    class _Svc(TutorStateService):
        async def _row(self, _cid):
            return row

    # لا استثناء (fail-open) — المُدخل التالف يُعامَل كـ {} ثم يُدمَج.
    await _Svc(_FakeDB()).record_turn(
        conversation_id=1,
        user_id=1,
        active_concept="c",
        assistant_text="t",
        is_socratic_question=False,
        kc_progress={"a": {"attempts": 1}},
    )
    import json

    assert json.loads(row.kc_progress)["a"]["attempts"] == 1
