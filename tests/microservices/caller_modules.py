"""أين تُرقَّع الأسماء أثناء تفكيك `routes.py` — موطنٌ واحد لآلية late-binding (D-168).

## المشكلة التي تحلّها هذه الوحدة

`routes.py` يُعيد تصدير كلّ ما يُستخرَج منه (`# noqa: F401`) كي تبقى الاستيرادات
الحيّة تعمل. وهذا بالضبط ما يجعل `monkeypatch.setattr(routes, "…")` **خطراً**:

بعد نقل جسمٍ إلى وحدةٍ شقيقة، تُحَلّ أسماؤه من globals الوحدة **الجديدة**. لكنّ
`routes` ما زال يملك الاسم (إعادة التصدير)، فالترقيع عليه **ينجح** ولا يفعل شيئاً —
والاختبار يمسّ قاعدة بيانات حقيقية بدل أن يفشل بصوتٍ عالٍ. شبكةُ أمانٍ بثقبٍ لا
يعرفه أحد أسوأ من غيابها (D-207 · البند ٥).

`_patch_caller` تُغلق ذلك: تُرقّع **كلّ** وحدةٍ تملك الاسم، و**ترفع** إن لم تملكه
أيّ وحدة. فالهجرة تصير سطراً واحداً في `CALLER_MODULES`، والهجرة المنسيّة فشلاً صريحاً.

## لماذا وحدة مستقلّة لا كتلة داخل ملفّ اختبار

كانت الآلية تعيش في `test_agent_chat_differential.py` (D-237). ومع ISS-155 صار
ملفّان يحتاجانها، واستيراد اختبارٍ من اختبار اعتماديّةٌ خاطئة تجعل ترتيب الجمع
جزءاً من العقد. الموطن الواحد هنا هو نفس قاعدة «المصدر الواحد» التي يفرضها المستودع
على الكود (D-186 · D-191).

⚠️ هذه الوحدة **ليست** ملفّ اختبار (لا تبدأ بـ`test_`)، فلا يجمعها pytest.
"""

from __future__ import annotations

from typing import Any

import pytest

from microservices.orchestrator_service.src.api import (
    agent_chat_admin_stream,
    agent_chat_customer_stream,
    chat_stream_engine,
    chat_turn_context,
    chat_ws_turn,
    routes,
)

#: الوحدات التي تُحَلّ منها أسماء المُستدعي. عند استخراج وحدةٍ جديدة تُضاف هنا —
#: **سطر واحد، موضع واحد**. لا تحذف `routes`: الأغلفة الرفيعة تبقى فيه وتستدعي
#: المصادقة و`OrchestratorAgent`.
#: تكامل هذه القائمة مفروضٌ آلياً — راجع
#: `test_agent_chat_differential.test_caller_modules_covers_every_module_that_calls_a_patched_name`.
CALLER_MODULES: tuple[Any, ...] = (
    routes,
    agent_chat_admin_stream,
    agent_chat_customer_stream,
    # مسار WS لا يمرّ به `/agent/chat`، لكنّه يستدعي `_persist_assistant_message`
    # فيدخل القائمة كي يبقى الثابت البنيوي صادقاً بالكامل. ترقيعه لا-عمليةٌ هناك.
    chat_stream_engine,
    # ISS-155: بعد استخراج التوأمين صارت هاتان تملكان المُستدعين الحقيقيين.
    # الحارس البنيوي هو الذي طلبهما بالاسم — لم تُضافا استباقاً، فبقي مُثبَتاً حيّاً
    # أنّ الآلية تصرخ فعلاً (D-207 · حارسٌ لا يُثبَت أنه يصرخ ليس حارساً).
    chat_ws_turn,
    chat_turn_context,
)

#: الأسماء التي تُرقّعها اختبارات هذه الحزمة لعزل قاعدة البيانات والشبكة والبثّ.
#: كلّ اسمٍ هنا يُوسِّع مرمى الفحص البنيوي — فأيّ وحدةٍ تستدعيه ولم تُدرَج تُفشِل CI.
PATCHED_NAMES = (
    "_ensure_conversation",
    "_persist_assistant_message",
    "_decode_auth_payload_or_401",
    "get_ai_client",
    "OrchestratorAgent",
    # ISS-155: عقد الترانسكريبت يُرقّع محرّك البثّ وكاشفَي السياق والهوية كي يقيس
    # **وسائط** الدور بدل مخرَجات الرسم — فتصير الفروق الستّة بين التوأمين مقيسة.
    "_stream_chat_langgraph",
    "_extract_client_context_messages",
    "_emit_identity_diagnostic_log",
)


def patch_caller(monkeypatch: pytest.MonkeyPatch, name: str, value: object) -> None:
    """يُرقّع الاسم في كلّ وحدةٍ تملكه — ويرفع إن لم تملكه أيّ وحدة."""
    patched = [module for module in CALLER_MODULES if hasattr(module, name)]
    if not patched:
        raise AssertionError(
            f"لا وحدة في CALLER_MODULES تملك {name!r}.\n"
            f"   إن نُقل المُستدعي إلى وحدةٍ جديدة فأضِفها إلى CALLER_MODULES "
            f"(D-168 · قاعدة late-binding). الترقيع على وحدةٍ لا تملك الاسم "
            f"لا-عمليةٌ صامتة، والاختبار عندها يمسّ قاعدة بيانات حقيقية."
        )
    for module in patched:
        monkeypatch.setattr(module, name, value)
