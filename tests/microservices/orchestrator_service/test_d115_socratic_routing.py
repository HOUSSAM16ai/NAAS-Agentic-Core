"""D-115 — البروتوكول السقراطي المنضبط + المُطهّر المُصفّح (جانب الـ orchestrator).

يثبت (stdlib + source-inspection — يعمل في الـ sandbox):
1. المُطهّر المُصفّح يحذف كل أشكال ⟦⟧ المشوّهة + تعليمات system prompt المُسرَّبة
   + يحفظ العربية الطبيعية والـ LaTeX والفرنسية المشروعة — على sanitize_chunk والنهائي.
2. SynthesizerNode يطبّق البروتوكول السقراطي الطبيعي (D-117: تعليمات سلوكية بلا
   عناوين مُرقَّمة) ولا يحوي فرع المثال المكشوف (_worked_example_mode) — يَعكِس D-114.
3. routes.py يمرّر support_level في المُشغّلَين ولا يمرّر worked_example_directive.
4. AgentState يحمل support_level ولا يحمل worked_example_directive.
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
# D-168: routes.py decomposed — read the composed API source via the manifest
# (stdlib-only import chain; the package __init__ files are empty, sandbox-safe).
from microservices.orchestrator_service.src.api.api_sources import (
    read_api_source,
)

ROUTES_SRC = read_api_source()


def _load_response_sanitizer():
    p = REPO_ROOT / "microservices/orchestrator_service/src/services/overmind/response_sanitizer.py"
    spec = importlib.util.spec_from_file_location("rs_d115", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 1. المُطهّر المُصفّح ───────────────────────────────────────────────────────
class TestBulletproofSanitizer:
    def test_strips_all_mangled_brackets(self):
        rs = _load_response_sanitizer()
        for case in (
            "⟦/مثال_محلول⟧ الآن طبّق",
            "⟦مثال_محلول حدد النوع",  # no closer
            "⟦/مثال_محلول⟦ نص",  # mangled closer
            "⟦التوجيه التربوي – تفعيل الفهم⟧ نص",
            "نص ⟦مثال_محلول⟧ محتوى ⟦/مثال_محلول⟧ نهاية",
        ):
            out = rs.strip_garbage_markers(case)
            assert "⟦" not in out and "⟧" not in out, f"bracket leaked: {out!r}"
            assert "مثال_محلول" not in out, f"marker phrase leaked: {out!r}"

    def test_strips_leaked_english_instructions(self):
        rs = _load_response_sanitizer()
        leak = "WARM‑UP: The instruction must be rendered in a coalesced English form."
        assert "WARM" not in rs.strip_garbage_markers(leak)
        assert "instruction must" not in rs.strip_garbage_markers(leak)

    def test_preserves_natural_arabic_and_latex(self):
        rs = _load_response_sanitizer()
        # «مثال محلول» بمسافة = عربية طبيعية (ليست العلامة بالأندرسكور)
        assert "مثال محلول" in rs.strip_garbage_markers("هذا مثال محلول بسيط")
        assert "x^2" in rs.sanitize_chunk("النتيجة $x^2$ هنا")

    def test_sanitize_chunk_and_response_apply_stripper(self):
        rs = _load_response_sanitizer()
        assert "⟦" not in rs.sanitize_chunk("⟦مثال_محلول⟧ نص")
        assert "⟦" not in rs.sanitize_response("⟦/مثال_محلول⟧ نص", intent="educational")


# ── 2. البروتوكول السقراطي في SynthesizerNode ─────────────────────────────────
class TestSocraticProtocol:
    def test_disciplined_prompt_builder_present(self):
        assert "_build_socratic_prompt" in GRAPH_SEARCH
        assert "_SOCRATIC_CORE_PROMPT" in GRAPH_SEARCH
        assert "_SOCRATIC_DEPTH_CLAUSES" in GRAPH_SEARCH

    def test_prompt_is_behavioral_not_labeled_template(self):
        # D-117 (فصل الطبقات): البرومبت سلوكي طبيعي — لا قالب مُرقَّم بعناوين
        # يَنسخها النموذج. العناوين الداخلية تظهر فقط ضمن قائمة «ممنوع» + نمط طبيعي.
        # ممنوع: القالب المُرقَّم القديم (D-115) الذي سرّب العناوين حرفياً.
        assert "اتبع هذا القالب حرفياً" not in GRAPH_SEARCH
        assert "1) أعِد صياغة" not in GRAPH_SEARCH
        assert "فهمت المطلوب: ..." not in GRAPH_SEARCH
        # مطلوب: نمط طبيعي + قاعدة عدم الكشف + منع صريح للعناوين الداخلية
        assert "لننظر إلى هذا الجزء فقط" in GRAPH_SEARCH
        assert "لا تكشف الجواب النهائي" in GRAPH_SEARCH
        assert "لا يراها الطالب" in GRAPH_SEARCH
        for forbidden_label in ("نوع المسألة", "سؤال تشخيصي", "أصغر خطوة", "مستوى الدعم"):
            assert forbidden_label in GRAPH_SEARCH, (
                f"missing forbidden-label clause: {forbidden_label}"
            )

    def test_worked_example_reveal_removed(self):
        assert "_worked_example_mode" not in GRAPH_SEARCH
        assert "_we_system_prompt" not in GRAPH_SEARCH
        assert "worked_example_directive" not in GRAPH_SEARCH

    def test_synthesizer_reads_support_level(self):
        syn = GRAPH_SEARCH[GRAPH_SEARCH.index("class SynthesizerNode") :]
        assert '_support_level = int(state.get("support_level")' in syn
        assert "_build_socratic_prompt(_support_level)" in syn


# ── 3. التمرير في routes + AgentState ─────────────────────────────────────────
class TestRoutingThreading:
    def test_support_level_threaded_both_runners(self):
        assert ROUTES_SRC.count('inputs["support_level"]') >= 2

    def test_worked_example_directive_removed_from_routes(self):
        assert "worked_example_directive" not in ROUTES_SRC
        assert "_extract_worked_example_directive" not in ROUTES_SRC

    def test_agent_state_keeps_support_level_drops_directive(self):
        assert "support_level: int" in GRAPH_MAIN
        # يجب ألّا يكون حقلاً في AgentState (التحقق من شكل التعليق المُوثِّق لإزالته
        # «(worked_example_directive مُزال)» مسموح — نمنع فقط حقل الحالة الفعلي).
        assert "worked_example_directive:" not in GRAPH_MAIN
        assert 'state["worked_example_directive"]' not in GRAPH_MAIN
        assert 'get("worked_example_directive")' not in GRAPH_MAIN
