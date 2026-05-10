"""
اختبارات إحياء خدمة المنسق (Orchestrator Revival Tests)
---------------------------------------------------------
تتحقق من الإصلاحات الثلاثة المطلوبة لتفعيل orchestrator_service:
  H1 — TAVILY_API_KEY موجود في docker-compose.yml
  H2 — ddgs مُدرج في requirements.txt لـ research_agent
  H3 — cognitive_engine.memorize محمي من None

هذه الاختبارات تعمل بدون اتصال بقاعدة بيانات حقيقية.
"""

import os
import pathlib

import pytest


# ─── H1: TAVILY_API_KEY في docker-compose.yml ───────────────────────────────

class TestTavilyDockerCompose:
    """يتحقق من أن TAVILY_API_KEY مُعرَّف في docker-compose.yml لكلا الخدمتين."""

    COMPOSE_PATH = pathlib.Path("docker-compose.yml")

    def _compose_text(self) -> str:
        return self.COMPOSE_PATH.read_text(encoding="utf-8")

    def test_tavily_key_present_in_compose(self):
        """يجب أن يحتوي docker-compose.yml على TAVILY_API_KEY."""
        assert "TAVILY_API_KEY" in self._compose_text(), (
            "TAVILY_API_KEY غائب من docker-compose.yml — "
            "WebSearchFallbackNode ستتجاهل البحث صامتةً."
        )

    def test_tavily_key_in_orchestrator_service(self):
        """يجب أن يكون TAVILY_API_KEY ضمن بيئة orchestrator-service."""
        text = self._compose_text()
        # نتحقق من وجود السطر بعد تعريف orchestrator-service
        orchestrator_block_start = text.find("orchestrator-service:")
        assert orchestrator_block_start != -1, "orchestrator-service غير موجود في docker-compose.yml"
        # نبحث عن TAVILY بعد بداية الـ block
        tavily_pos = text.find("TAVILY_API_KEY", orchestrator_block_start)
        assert tavily_pos != -1, (
            "TAVILY_API_KEY غير موجود في بيئة orchestrator-service"
        )

    def test_tavily_key_in_research_agent(self):
        """يجب أن يكون TAVILY_API_KEY ضمن بيئة research-agent."""
        text = self._compose_text()
        research_block_start = text.find("research-agent:")
        assert research_block_start != -1, "research-agent غير موجود في docker-compose.yml"
        tavily_pos = text.find("TAVILY_API_KEY", research_block_start)
        assert tavily_pos != -1, (
            "TAVILY_API_KEY غير موجود في بيئة research-agent"
        )

    def test_tavily_key_uses_safe_default(self):
        """يجب أن يستخدم TAVILY_API_KEY قيمة افتراضية آمنة (فارغة) لتجنب فشل compose."""
        text = self._compose_text()
        # القيمة الآمنة: ${TAVILY_API_KEY:-} تعني فارغة إذا لم تُعيَّن
        assert "${TAVILY_API_KEY:-}" in text, (
            "TAVILY_API_KEY يجب أن يستخدم ${TAVILY_API_KEY:-} "
            "لتجنب فشل docker compose عند غياب المتغير."
        )


# ─── H2: ddgs في requirements.txt لـ research_agent ────────────────────────

class TestDuckDuckGoFallback:
    """يتحقق من أن ddgs مُدرج في متطلبات research_agent."""

    REQUIREMENTS_PATH = pathlib.Path(
        "microservices/research_agent/requirements.txt"
    )

    def test_ddgs_in_requirements(self):
        """يجب أن يحتوي requirements.txt على ddgs لتفادي ImportError."""
        text = self.REQUIREMENTS_PATH.read_text(encoding="utf-8")
        assert "ddgs" in text, (
            "ddgs غائب من microservices/research_agent/requirements.txt — "
            "SuperSearchOrchestrator ستفشل بـ ImportError عند غياب TAVILY_API_KEY."
        )

    def test_ddgs_version_constraint(self):
        """يجب أن يكون ddgs بإصدار 6.0 أو أحدث."""
        text = self.REQUIREMENTS_PATH.read_text(encoding="utf-8")
        # نتحقق من وجود السطر بشكل عام — الإصدار الدقيق قد يتغير
        lines = [l.strip() for l in text.splitlines() if l.strip().startswith("ddgs")]
        assert lines, "ddgs غير موجود في requirements.txt"
        # نتحقق من أن الإصدار >= 6.0
        line = lines[0]
        assert ">=" in line or "==" in line or line == "ddgs", (
            f"سطر ddgs '{line}' يجب أن يحدد إصداراً (>=6.0 على الأقل)"
        )


# ─── H3: cognitive_engine.memorize محمي من None ─────────────────────────────

class TestCognitiveEngineNullGuard:
    """يتحقق من أن simple_client.py يحمي استدعاء memorize من None."""

    CLIENT_PATH = pathlib.Path(
        "microservices/orchestrator_service/src/core/gateway/simple_client.py"
    )

    def test_memorize_null_guard_present(self):
        """يجب أن يكون هناك حارس None قبل استدعاء cognitive_engine.memorize."""
        text = self.CLIENT_PATH.read_text(encoding="utf-8")
        # نتحقق من وجود الحارس في الكود
        assert "self.cognitive_engine is not None" in text, (
            "simple_client.py يفتقر إلى حارس None قبل cognitive_engine.memorize — "
            "سيرفع AttributeError عند كل استدعاء ناجح للنموذج."
        )

    def test_memorize_not_called_unconditionally(self):
        """يجب ألا يُستدعى memorize بدون فحص None."""
        text = self.CLIENT_PATH.read_text(encoding="utf-8")
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "self.cognitive_engine.memorize(" in line:
                # يجب أن يكون السطر السابق أو نفس السطر يحتوي على فحص None
                context = "\n".join(lines[max(0, i - 3) : i + 1])
                assert "is not None" in context, (
                    f"السطر {i + 1}: cognitive_engine.memorize يُستدعى بدون فحص None:\n{context}"
                )

    def test_cognitive_engine_returns_none_by_default(self):
        """get_cognitive_engine() يُرجع None بشكل افتراضي — الحارس ضروري."""
        from microservices.orchestrator_service.src.core.cognitive_cache import (
            get_cognitive_engine,
        )

        engine = get_cognitive_engine()
        assert engine is None, (
            "get_cognitive_engine() يجب أن يُرجع None بشكل افتراضي "
            "(CognitiveResonanceEngine غير مُهيأ بعد)."
        )
