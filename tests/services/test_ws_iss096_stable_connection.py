"""
ISS-096 regression gate — WebSocket يجب ألا ينقطع عند تغيير wsUrl/token.
يشمل أيضاً D-WS-GITPOD-002: Gitpod Flex يستخدم same-host proxy (port 5000)
بدلاً من الاتصال المباشر بـ port 8000 الذي يُغلقه Gitpod proxy بعد idle.

المشكلة (2026-05-28):
  connect useCallback كان يعتمد على [wsUrl, token, eventNamespace] كـ closure.
  عند تغيير wsUrl (null → URL حقيقي عند أول render) أو token:
    1. connect يتغير (useCallback يُعيد الإنشاء)
    2. useEffect الرئيسي [connect, stopHeartbeat] يُعيد التشغيل
    3. cleanup يُغلق الـ WebSocket الحالي (ws.close(1000))
    4. اتصال جديد يُفتح
    5. النتيجة: WebSocket يُغلق فور فتحه → kick-to-login loop

الإصلاح:
  wsUrl/token/eventNamespace تُخزَّن في refs (wsUrlRef, tokenRef, eventNamespaceRef).
  connect يقرأ منها مباشرة بدلاً من closure.
  dependencies connect = [startHeartbeat, stopHeartbeat] فقط — لا تتغير.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WS_HOOK = REPO_ROOT / "frontend" / "app" / "hooks" / "useRealtimeConnection.js"
WS_URL_UTIL = REPO_ROOT / "frontend" / "app" / "utils" / "wsUrl.js"


def _src() -> str:
    return WS_HOOK.read_text(encoding="utf-8")


def _wsurl_src() -> str:
    return WS_URL_UTIL.read_text(encoding="utf-8")


class TestISS096RefPattern:
    """connect يجب أن يقرأ wsUrl/token من refs لا من closure."""

    def test_wsurl_ref_declared(self) -> None:
        """wsUrlRef يجب أن يكون مُعرَّفاً."""
        assert "wsUrlRef" in _src(), (
            "ISS-096: wsUrlRef غير موجود في useRealtimeConnection.js. "
            "يجب تخزين wsUrl في ref لمنع إعادة إنشاء connect."
        )

    def test_token_ref_declared(self) -> None:
        """tokenRef يجب أن يكون مُعرَّفاً."""
        assert "tokenRef" in _src(), (
            "ISS-096: tokenRef غير موجود في useRealtimeConnection.js. "
            "يجب تخزين token في ref لمنع إعادة إنشاء connect."
        )

    def test_event_namespace_ref_declared(self) -> None:
        """eventNamespaceRef يجب أن يكون مُعرَّفاً."""
        assert "eventNamespaceRef" in _src(), (
            "ISS-096: eventNamespaceRef غير موجود في useRealtimeConnection.js."
        )

    def test_connect_reads_wsurl_from_ref(self) -> None:
        """connect يجب أن يقرأ wsUrl من wsUrlRef.current لا من closure."""
        src = _src()
        # يجب أن يكون هناك سطر: const wsUrl = wsUrlRef.current;
        assert "wsUrlRef.current" in src, (
            "ISS-096: connect لا يقرأ wsUrl من wsUrlRef.current. "
            "هذا يعني أن wsUrl لا يزال closure → connect يتغير عند كل render."
        )

    def test_connect_reads_token_from_ref(self) -> None:
        """connect يجب أن يقرأ token من tokenRef.current لا من closure."""
        src = _src()
        assert "tokenRef.current" in src, "ISS-096: connect لا يقرأ token من tokenRef.current."

    def test_connect_deps_exclude_wsurl_token(self) -> None:
        """dependencies connect يجب ألا تحتوي على wsUrl أو token."""
        src = _src()
        # ابحث عن سطر dependencies الـ connect useCallback
        # النمط: }, [startHeartbeat, stopHeartbeat]);
        # يجب ألا يحتوي على wsUrl أو token
        deps_pattern = re.compile(
            r"}\s*,\s*\[([^\]]*)\]\s*\)\s*;",
            re.MULTILINE,
        )
        matches = deps_pattern.findall(src)

        # ابحث عن الـ deps التي تحتوي على startHeartbeat (هذه هي deps connect)
        connect_deps = [m for m in matches if "startHeartbeat" in m or "stopHeartbeat" in m]

        assert connect_deps, (
            "ISS-096: لم يُعثر على dependencies connect useCallback. "
            "يجب أن تكون [startHeartbeat, stopHeartbeat]."
        )

        for deps in connect_deps:
            assert "wsUrl" not in deps, (
                f"ISS-096: wsUrl لا يزال في dependencies connect: [{deps}]. "
                "هذا يُسبب إعادة إنشاء connect عند كل تغيير في wsUrl → قطع الـ WebSocket."
            )
            assert "token" not in deps, (
                f"ISS-096: token لا يزال في dependencies connect: [{deps}]. "
                "هذا يُسبب إعادة إنشاء connect عند كل تغيير في token → قطع الـ WebSocket."
            )
            assert "eventNamespace" not in deps or "eventNamespaceRef" in deps, (
                f"ISS-096: eventNamespace لا يزال في dependencies connect: [{deps}]."
            )

    def test_refs_synced_via_useeffect(self) -> None:
        """يجب أن تكون هناك useEffect تُزامن wsUrlRef/tokenRef مع القيم الجديدة."""
        src = _src()
        assert "wsUrlRef.current = wsUrl" in src, (
            "ISS-096: لا يوجد useEffect يُزامن wsUrlRef مع wsUrl الجديد."
        )
        assert "tokenRef.current = token" in src, (
            "ISS-096: لا يوجد useEffect يُزامن tokenRef مع token الجديد."
        )

    def test_reconnect_on_wsurl_change_useeffect_exists(self) -> None:
        """يجب أن يكون هناك useEffect يُعيد الاتصال عند تغيير wsUrl/token."""
        src = _src()
        # يجب أن يكون هناك useEffect يعتمد على [wsUrl, token, connect]
        assert re.search(r"\[wsUrl\s*,\s*token\s*,\s*connect\]", src), (
            "ISS-096: لا يوجد useEffect([wsUrl, token, connect]) يُعيد الاتصال "
            "عند تغيير wsUrl من null إلى URL حقيقي."
        )


class TestISS096GitpodProxyFix:
    """D-WS-GITPOD-002: Gitpod Flex يجب أن يستخدم same-host proxy لا port 8000 مباشرة.

    الجذر: Gitpod proxy يُغلق WebSocket على port 8000 بعد ~10s idle.
    الحل: wsUrl.js يُعيد null لـ *.gitpod.dev → getWsBase يستخدم window.location.host
    (port 5000) → server.js يُمرِّر WS إلى localhost:8000 داخلياً.
    """

    def test_gitpod_dev_returns_null_not_8000(self) -> None:
        """*.gitpod.dev يجب أن يُعيد null (same-host) لا 8000-- host."""
        src = _wsurl_src()
        # يجب أن يكون هناك شرط يُعيد null لـ gitpod.dev
        assert "gitpod.dev" in src, "wsUrl.js يجب أن يتعامل مع *.gitpod.dev"
        # يجب ألا يكون هناك rewrite من 5000-- إلى 8000-- لـ gitpod.dev
        # (الـ rewrite القديم كان: host.match(/^5000-/) → replace 5000- بـ 8000-)
        # الآن يجب أن يكون محصوراً في Replit فقط
        assert "replit" in src.lower(), "wsUrl.js يجب أن يحصر port rewrite في Replit فقط."

    def test_gitpod_io_returns_null(self) -> None:
        """*.gitpod.io (Classic) يجب أن يُعيد null أيضاً."""
        src = _wsurl_src()
        assert "gitpod.io" in src, (
            "D-WS-GITPOD-002: wsUrl.js يجب أن يتعامل مع *.gitpod.io (Gitpod Classic)."
        )

    def test_replit_still_gets_port_rewrite(self) -> None:
        """Replit يجب أن يحصل على port rewrite (server.js لا يعمل هناك)."""
        src = _wsurl_src()
        # يجب أن يكون هناك rewrite خاص بـ replit
        assert re.search(r"replit.*8000|8000.*replit", src, re.IGNORECASE), (
            "D-WS-GITPOD-002: Replit يجب أن يحصل على port rewrite إلى 8000."
        )

    def test_same_host_comment_documents_reason(self) -> None:
        """يجب أن يكون هناك تعليق يوضح سبب استخدام same-host لـ Gitpod."""
        src = _wsurl_src()
        assert "server.js" in src, "wsUrl.js يجب أن يوثق أن server.js يُمرِّر WS داخلياً."
        assert "idle" in src.lower() or "proxy" in src.lower(), (
            "wsUrl.js يجب أن يوثق سبب تجنب الاتصال المباشر بـ port 8000."
        )
