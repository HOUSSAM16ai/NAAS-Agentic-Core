"""D-114 — المثال المحلول المُتدرّج: تمرير support_level + الحجب الواعي بالفواصل.

يثبت (جانب الـ orchestrator، stdlib فقط — يعمل في الـ sandbox):
1. `support_level` + `worked_example_directive` مُصرَّحان في `ChatRunContext`
   ومُوصَّلان في كلا المُشغّلَين (WS + HTTP).
2. `_extract_support_level` يحدّ (1..5) ويفترض 5 (محجوب) آمناً عند الغياب/الخطأ.
3. `AgentState` يحمل الحقلين؛ `SynthesizerNode` يفرّع على support_level==1.
4. الحجب الواعي بالفواصل (port المايكروسيرفِس): يُعفي ما داخل الفواصل عند
   support_level==1، ويحجب ما عداها (fail-closed) عند الغياب/المستويات الأخرى.
5. `sanitize_chunk` يستبدل الكلمات الأجنبية ويحفظ LaTeX/الفرنسية المشروعة.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GRAPH_MAIN = (
    REPO_ROOT / "microservices/orchestrator_service/src/services/overmind/graph/main.py"
).read_text(encoding="utf-8")
GRAPH_SEARCH = (
    REPO_ROOT / "microservices/orchestrator_service/src/services/overmind/graph/search.py"
).read_text(encoding="utf-8")
ROUTES_SRC = (REPO_ROOT / "microservices/orchestrator_service/src/api/routes.py").read_text(
    encoding="utf-8"
)


def _load_response_sanitizer():
    """يحمّل response_sanitizer.py standalone (stdlib فقط — لا pydantic)."""
    p = REPO_ROOT / "microservices/orchestrator_service/src/services/overmind/response_sanitizer.py"
    spec = importlib.util.spec_from_file_location("rs_d114", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 1. البنية: التصريح والتوصيل ───────────────────────────────────────────────
class TestSupportLevelPlumbing:
    def test_chat_run_context_declares_fields(self):
        assert "support_level: int" in ROUTES_SRC
        assert "worked_example_directive: str" in ROUTES_SRC

    def test_extractors_defined(self):
        assert "_extract_support_level" in ROUTES_SRC
        assert "_extract_worked_example_directive" in ROUTES_SRC

    def test_plumbed_into_both_runners(self):
        # WS + HTTP كلاهما يضبط inputs["support_level"]
        assert ROUTES_SRC.count('inputs["support_level"]') >= 2, (
            "support_level must be plumbed into graph inputs on BOTH HTTP and WS paths"
        )

    def test_agent_state_has_fields(self):
        assert "support_level: int" in GRAPH_MAIN
        assert "worked_example_directive: str" in GRAPH_MAIN

    def test_synthesizer_branches_on_support_level(self):
        syn_start = GRAPH_SEARCH.index("class SynthesizerNode")
        syn_src = GRAPH_SEARCH[syn_start:]
        assert "_support_level == 1" in syn_src, "SynthesizerNode must branch on support_level==1"
        assert "_worked_example_mode" in syn_src
        # support_level يُمرَّر إلى sanitize_response (وإلا الـ orchestrator يُعيد الحجب)
        assert "support_level=_support_level" in syn_src


# ── 2. _extract_support_level — clamp + افتراض آمن 5 ──────────────────────────
class TestExtractSupportLevel:
    """تُعيد تعريف المنطق حرفياً من المصدر (الدالة نقية، حتمية)."""

    @staticmethod
    def _extract(context):
        # نسخة طبق الأصل من routes.py:_extract_support_level (verification)
        if not isinstance(context, dict):
            return 5
        raw = context.get("support_level")
        try:
            level = int(raw)
        except (TypeError, ValueError):
            return 5
        return level if 1 <= level <= 5 else 5

    def test_default_when_missing(self):
        assert self._extract(None) == 5
        assert self._extract({}) == 5

    def test_clamp_out_of_range(self):
        assert self._extract({"support_level": 0}) == 5
        assert self._extract({"support_level": 9}) == 5

    def test_invalid_type_defaults_safe(self):
        assert self._extract({"support_level": "abc"}) == 5
        assert self._extract({"support_level": None}) == 5

    def test_valid_levels_pass(self):
        for lvl in (1, 2, 3, 4, 5):
            assert self._extract({"support_level": lvl}) == lvl

    def test_source_matches_safe_default(self):
        # الافتراض الآمن 5 موجود في المصدر (لا 1)
        assert "return 5" in ROUTES_SRC


# ── 3. الحجب الواعي بالفواصل (port المايكروسيرفِس) ─────────────────────────────
class TestSentinelRedaction:
    def test_exempt_inside_redact_outside(self):
        rs = _load_response_sanitizer()
        text = (
            "مقدمة. "
            + rs._WE_OPEN
            + "مثال مماثل: P(A)=4/9 إذن النتيجة = 0.44"
            + rs._WE_CLOSE
            + " طبّق على تمرينك. (تسريب) P(B)=14/165"
        )
        out = rs.redact_final_answers(text, support_level=1)
        assert "4/9" in out, "inside-sentinel worked example must survive"
        assert "14/165" not in out, "leaked graded answer outside must be redacted"
        assert rs._WE_OPEN not in out and rs._WE_CLOSE not in out, "markers stripped"

    def test_full_redaction_at_level_5(self):
        rs = _load_response_sanitizer()
        text = rs._WE_OPEN + "P(A)=4/9" + rs._WE_CLOSE + " P(B)=14/165"
        out = rs.redact_final_answers(text, support_level=5)
        assert "4/9" not in out and "14/165" not in out
        assert rs._WE_OPEN not in out and rs._WE_CLOSE not in out

    def test_no_sentinels_fail_closed(self):
        rs = _load_response_sanitizer()
        out = rs.redact_final_answers("الجواب: P(A)=3/7", support_level=1)
        assert "3/7" not in out, "no sentinels => full redaction (fail-closed)"

    def test_unterminated_sentinel_fail_closed(self):
        rs = _load_response_sanitizer()
        # فاصل مفتوح بلا إغلاق ⇒ يُحجب الباقي
        out = rs.redact_final_answers(rs._WE_OPEN + "P(A)=4/9", support_level=1)
        assert "4/9" not in out

    def test_sanitize_response_threads_support_level(self):
        rs = _load_response_sanitizer()
        text = rs._WE_OPEN + "P(A)=4/9" + rs._WE_CLOSE
        out = rs.sanitize_response(text, intent="educational", support_level=1)
        assert "4/9" in out and rs._WE_OPEN not in out


# ── 4. sanitize_chunk — تقوية الكلمات الأجنبية + حفظ LaTeX/الفرنسية ───────────
class TestSanitizeChunkHardening:
    def test_replaces_foreign_words(self):
        rs = _load_response_sanitizer()
        out = rs.sanitize_chunk("الدالة функция هنا")
        assert "دالة" in out and "функция" not in out

    def test_preserves_latex(self):
        rs = _load_response_sanitizer()
        out = rs.sanitize_chunk("النتيجة $x^2 + 1$ نهاية")
        assert "x^2 + 1" in out

    def test_preserves_legit_french(self):
        rs = _load_response_sanitizer()
        out = rs.sanitize_chunk("نحسب probabilité الحدث")
        assert "probabilité" in out
