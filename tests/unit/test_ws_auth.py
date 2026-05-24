"""
اختبارات WebSocket Auth — نظام الاستخراج متعدد الطبقات (ISS-WS-001).

تغطي هذه الاختبارات:
- استخراج token عبر cookie
- استخراج token عبر query parameter (مُفعَّل في production)
- استخراج token عبر Authorization header
- استخراج token عبر sec-websocket-protocol
- محاكاة proxy-stripped headers (Codespaces/mobile)
- defensive parsing للـ headers المشوهة
- ترتيب الأولوية بين الطبقات
- logging عند الفشل
"""

from __future__ import annotations

import pytest

from app.api.routers.ws_auth import (
    TokenSource,
    WebSocketAuthResult,
    _extract_from_auth_header,
    _extract_from_cookie,
    _extract_from_query_param,
    _extract_from_subprotocol,
    _extract_token_from_protocols,
    _parse_protocol_header,
    extract_websocket_auth,
    extract_websocket_auth_detailed,
)


# ─── Fake WebSocket ──────────────────────────────────────────────────────────


class _FakeClient:
    def __init__(self, host: str = "127.0.0.1") -> None:
        self.host = host


class _FakeWebSocket:
    """
    محاكاة مبسطة لـ FastAPI WebSocket لأغراض الاختبار.
    يدعم تخصيص headers و query_params و client.
    """

    def __init__(
        self,
        headers: dict[str, str] | None = None,
        query_params: dict[str, str] | None = None,
        client_host: str = "127.0.0.1",
    ) -> None:
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.client = _FakeClient(client_host)


# ─── _parse_protocol_header ──────────────────────────────────────────────────


class TestParseProtocolHeader:
    """يختبر تحليل ترويسة sec-websocket-protocol."""

    def test_none_returns_empty(self) -> None:
        assert _parse_protocol_header(None) == []

    def test_empty_string_returns_empty(self) -> None:
        assert _parse_protocol_header("") == []

    def test_whitespace_only_returns_empty(self) -> None:
        assert _parse_protocol_header("   ") == []

    def test_single_protocol(self) -> None:
        assert _parse_protocol_header("jwt") == ["jwt"]

    def test_two_protocols(self) -> None:
        assert _parse_protocol_header("jwt, mytoken") == ["jwt", "mytoken"]

    def test_strips_whitespace(self) -> None:
        assert _parse_protocol_header("  jwt  ,  mytoken  ") == ["jwt", "mytoken"]

    def test_removes_duplicates_preserves_order(self) -> None:
        result = _parse_protocol_header("jwt, mytoken, jwt")
        assert result == ["jwt", "mytoken"]

    def test_skips_empty_parts(self) -> None:
        result = _parse_protocol_header("jwt,,mytoken,")
        assert result == ["jwt", "mytoken"]

    def test_malformed_commas(self) -> None:
        result = _parse_protocol_header(",,,jwt,,,")
        assert result == ["jwt"]


# ─── _extract_token_from_protocols ──────────────────────────────────────────


class TestExtractTokenFromProtocols:
    """يختبر استخراج token من قائمة البروتوكولات."""

    def test_empty_list_returns_none(self) -> None:
        assert _extract_token_from_protocols([]) is None

    def test_no_jwt_returns_none(self) -> None:
        assert _extract_token_from_protocols(["custom-proto"]) is None

    def test_jwt_without_token_returns_none(self) -> None:
        assert _extract_token_from_protocols(["jwt"]) is None

    def test_jwt_followed_by_token(self) -> None:
        assert _extract_token_from_protocols(["jwt", "mytoken123"]) == "mytoken123"

    def test_jwt_not_first(self) -> None:
        assert _extract_token_from_protocols(["other", "jwt", "mytoken"]) == "mytoken"

    def test_empty_token_after_jwt_returns_none(self) -> None:
        assert _extract_token_from_protocols(["jwt", ""]) is None

    def test_whitespace_token_after_jwt_returns_none(self) -> None:
        assert _extract_token_from_protocols(["jwt", "  "]) is None


# ─── _extract_from_cookie ────────────────────────────────────────────────────


class TestExtractFromCookie:
    """يختبر استخراج token من cookies."""

    def test_no_cookie_header(self) -> None:
        ws = _FakeWebSocket()
        assert _extract_from_cookie(ws) is None  # type: ignore[arg-type]

    def test_access_token_cookie(self) -> None:
        ws = _FakeWebSocket(headers={"cookie": "access_token=abc123"})
        assert _extract_from_cookie(ws) == "abc123"  # type: ignore[arg-type]

    def test_auth_token_cookie(self) -> None:
        ws = _FakeWebSocket(headers={"cookie": "auth_token=xyz789"})
        assert _extract_from_cookie(ws) == "xyz789"  # type: ignore[arg-type]

    def test_token_cookie(self) -> None:
        ws = _FakeWebSocket(headers={"cookie": "token=tok999"})
        assert _extract_from_cookie(ws) == "tok999"  # type: ignore[arg-type]

    def test_multiple_cookies_picks_access_token(self) -> None:
        ws = _FakeWebSocket(
            headers={"cookie": "session=sess1; access_token=mytoken; other=val"}
        )
        assert _extract_from_cookie(ws) == "mytoken"  # type: ignore[arg-type]

    def test_irrelevant_cookies_return_none(self) -> None:
        ws = _FakeWebSocket(headers={"cookie": "session=abc; csrftoken=xyz"})
        assert _extract_from_cookie(ws) is None  # type: ignore[arg-type]

    def test_empty_cookie_value_skipped(self) -> None:
        ws = _FakeWebSocket(headers={"cookie": "access_token="})
        assert _extract_from_cookie(ws) is None  # type: ignore[arg-type]

    def test_case_insensitive_cookie_name(self) -> None:
        """Cookie name يُقارَن بعد lowercase — ACCESS_TOKEN يُطابق access_token."""
        ws = _FakeWebSocket(headers={"cookie": "ACCESS_TOKEN=upper"})
        # الكود يُحوِّل الاسم إلى lowercase قبل المقارنة → يُطابق "access_token"
        assert _extract_from_cookie(ws) == "upper"  # type: ignore[arg-type]


# ─── _extract_from_query_param ───────────────────────────────────────────────


class TestExtractFromQueryParam:
    """يختبر استخراج token من query parameters."""

    def test_no_token_param(self) -> None:
        ws = _FakeWebSocket()
        assert _extract_from_query_param(ws) is None  # type: ignore[arg-type]

    def test_token_present(self) -> None:
        ws = _FakeWebSocket(query_params={"token": "mytoken123"})
        assert _extract_from_query_param(ws) == "mytoken123"  # type: ignore[arg-type]

    def test_empty_token_returns_none(self) -> None:
        ws = _FakeWebSocket(query_params={"token": ""})
        assert _extract_from_query_param(ws) is None  # type: ignore[arg-type]

    def test_whitespace_token_returns_none(self) -> None:
        ws = _FakeWebSocket(query_params={"token": "   "})
        assert _extract_from_query_param(ws) is None  # type: ignore[arg-type]

    def test_token_with_whitespace_stripped(self) -> None:
        ws = _FakeWebSocket(query_params={"token": "  tok  "})
        assert _extract_from_query_param(ws) == "tok"  # type: ignore[arg-type]


# ─── _extract_from_auth_header ───────────────────────────────────────────────


class TestExtractFromAuthHeader:
    """يختبر استخراج token من Authorization header."""

    def test_no_auth_header(self) -> None:
        ws = _FakeWebSocket()
        assert _extract_from_auth_header(ws) is None  # type: ignore[arg-type]

    def test_bearer_token(self) -> None:
        ws = _FakeWebSocket(headers={"authorization": "Bearer mytoken123"})
        assert _extract_from_auth_header(ws) == "mytoken123"  # type: ignore[arg-type]

    def test_bearer_lowercase(self) -> None:
        ws = _FakeWebSocket(headers={"authorization": "bearer mytoken123"})
        assert _extract_from_auth_header(ws) == "mytoken123"  # type: ignore[arg-type]

    def test_bearer_mixed_case(self) -> None:
        ws = _FakeWebSocket(headers={"authorization": "BEARER mytoken123"})
        assert _extract_from_auth_header(ws) == "mytoken123"  # type: ignore[arg-type]

    def test_non_bearer_scheme_returns_none(self) -> None:
        ws = _FakeWebSocket(headers={"authorization": "Basic dXNlcjpwYXNz"})
        assert _extract_from_auth_header(ws) is None  # type: ignore[arg-type]

    def test_empty_token_after_bearer_returns_none(self) -> None:
        ws = _FakeWebSocket(headers={"authorization": "Bearer "})
        assert _extract_from_auth_header(ws) is None  # type: ignore[arg-type]

    def test_strips_whitespace_from_token(self) -> None:
        ws = _FakeWebSocket(headers={"authorization": "Bearer  tok  "})
        assert _extract_from_auth_header(ws) == "tok"  # type: ignore[arg-type]


# ─── _extract_from_subprotocol ───────────────────────────────────────────────


class TestExtractFromSubprotocol:
    """يختبر استخراج token من sec-websocket-protocol."""

    def test_no_subprotocol_header(self) -> None:
        ws = _FakeWebSocket()
        token, proto = _extract_from_subprotocol(ws)  # type: ignore[arg-type]
        assert token is None
        assert proto is None

    def test_valid_jwt_protocol(self) -> None:
        ws = _FakeWebSocket(
            headers={"sec-websocket-protocol": "jwt, mytoken123"}
        )
        token, proto = _extract_from_subprotocol(ws)  # type: ignore[arg-type]
        assert token == "mytoken123"
        assert proto == "jwt"

    def test_token_before_jwt_still_works(self) -> None:
        ws = _FakeWebSocket(
            headers={"sec-websocket-protocol": "mytoken123, jwt"}
        )
        # jwt ليس في الموضع الصحيح — لا يوجد token بعده
        token, proto = _extract_from_subprotocol(ws)  # type: ignore[arg-type]
        assert token is None

    def test_no_jwt_in_protocols(self) -> None:
        ws = _FakeWebSocket(
            headers={"sec-websocket-protocol": "custom-proto"}
        )
        token, proto = _extract_from_subprotocol(ws)  # type: ignore[arg-type]
        assert token is None
        assert proto is None

    def test_empty_subprotocol_header(self) -> None:
        ws = _FakeWebSocket(headers={"sec-websocket-protocol": ""})
        token, proto = _extract_from_subprotocol(ws)  # type: ignore[arg-type]
        assert token is None
        assert proto is None

    def test_malformed_header_with_only_commas(self) -> None:
        ws = _FakeWebSocket(headers={"sec-websocket-protocol": ",,,,"})
        token, proto = _extract_from_subprotocol(ws)  # type: ignore[arg-type]
        assert token is None


# ─── extract_websocket_auth — ترتيب الأولوية ────────────────────────────────


class TestExtractWebsocketAuthPriority:
    """
    يختبر ترتيب الأولوية بين الطبقات الأربع.

    القانون: Cookie > Query param > Auth header > Subprotocol
    """

    def test_cookie_wins_over_all(self) -> None:
        """Cookie يأخذ الأولوية على كل المصادر الأخرى."""
        ws = _FakeWebSocket(
            headers={
                "cookie": "access_token=cookie_tok",
                "authorization": "Bearer auth_tok",
                "sec-websocket-protocol": "jwt, proto_tok",
            },
            query_params={"token": "query_tok"},
        )
        token, _ = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token == "cookie_tok"

    def test_query_param_wins_over_auth_and_subprotocol(self) -> None:
        """Query param يأخذ الأولوية على Authorization header و subprotocol."""
        ws = _FakeWebSocket(
            headers={
                "authorization": "Bearer auth_tok",
                "sec-websocket-protocol": "jwt, proto_tok",
            },
            query_params={"token": "query_tok"},
        )
        token, _ = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token == "query_tok"

    def test_auth_header_wins_over_subprotocol(self) -> None:
        """Authorization header يأخذ الأولوية على subprotocol."""
        ws = _FakeWebSocket(
            headers={
                "authorization": "Bearer auth_tok",
                "sec-websocket-protocol": "jwt, proto_tok",
            },
        )
        token, _ = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token == "auth_tok"

    def test_subprotocol_used_as_last_resort(self) -> None:
        """subprotocol يُستخدم فقط عند غياب كل المصادر الأخرى."""
        ws = _FakeWebSocket(
            headers={"sec-websocket-protocol": "jwt, proto_tok"},
        )
        token, proto = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token == "proto_tok"
        assert proto == "jwt"

    def test_no_token_anywhere_returns_none(self) -> None:
        """عند غياب كل المصادر يُرجع (None, None)."""
        ws = _FakeWebSocket()
        token, proto = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token is None
        assert proto is None


# ─── محاكاة بيئات حقيقية ────────────────────────────────────────────────────


class TestRealWorldScenarios:
    """
    يحاكي سيناريوهات حقيقية تسبب الانهيار في الإنتاج.
    """

    def test_codespaces_proxy_strips_subprotocol(self) -> None:
        """
        GitHub Codespaces edge proxy يحذف sec-websocket-protocol.
        الحل: query token fallback يجب أن يعمل.
        """
        ws = _FakeWebSocket(
            # لا يوجد sec-websocket-protocol — حُذف من proxy
            query_params={"token": "valid_jwt_token"},
            client_host="10.0.0.1",
        )
        token, proto = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token == "valid_jwt_token"
        assert proto is None

    def test_mobile_network_carrier_nat(self) -> None:
        """
        شبكات الهاتف (carrier NAT) تحذف subprotocol headers.
        الحل: query token fallback.
        """
        ws = _FakeWebSocket(
            # لا headers خاصة بـ WebSocket — حُذفت من carrier NAT
            query_params={"token": "mobile_user_token"},
            client_host="41.200.0.1",  # IP جزائري
        )
        token, _ = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token == "mobile_user_token"

    def test_brave_mobile_no_subprotocol(self) -> None:
        """
        Brave Mobile يُقيِّد subprotocol headers.
        الحل: query token fallback.
        """
        ws = _FakeWebSocket(
            headers={
                "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0) Brave/1.50",
            },
            query_params={"token": "brave_user_token"},
        )
        token, _ = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token == "brave_user_token"

    def test_vpn_environment_subprotocol_works(self) -> None:
        """
        عبر VPN (بيئة نظيفة) sec-websocket-protocol يعمل بشكل طبيعي.
        """
        ws = _FakeWebSocket(
            headers={"sec-websocket-protocol": "jwt, vpn_user_token"},
        )
        token, proto = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token == "vpn_user_token"
        assert proto == "jwt"

    def test_gateway_injected_auth_header(self) -> None:
        """
        Gateway يحقن Authorization header بعد التحقق من الـ token.
        """
        ws = _FakeWebSocket(
            headers={"authorization": "Bearer gateway_injected_token"},
        )
        token, proto = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token == "gateway_injected_token"
        assert proto == "jwt"

    def test_cookie_session_most_reliable(self) -> None:
        """
        Cookie session يعمل عبر كل الشبكات والـ proxies.
        """
        ws = _FakeWebSocket(
            headers={"cookie": "access_token=session_cookie_token; session=abc"},
        )
        token, _ = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token == "session_cookie_token"

    def test_production_query_token_enabled(self) -> None:
        """
        query token مُفعَّل في production — لا يُرجع None.
        هذا هو الإصلاح الجوهري لـ ISS-WS-001.
        """
        ws = _FakeWebSocket(
            query_params={"token": "prod_user_token"},
        )
        token, _ = extract_websocket_auth(ws)  # type: ignore[arg-type]
        # يجب أن يعمل بغض النظر عن ENVIRONMENT
        assert token == "prod_user_token"
        assert token is not None

    def test_all_sources_missing_returns_none_with_no_exception(self) -> None:
        """
        عند غياب كل المصادر يُرجع (None, None) بدون exception.
        """
        ws = _FakeWebSocket(client_host="unknown")
        token, proto = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token is None
        assert proto is None

    def test_malformed_subprotocol_falls_through_gracefully(self) -> None:
        """
        ترويسة subprotocol مشوهة لا تُسبب exception — تُعامَل كـ missing.
        """
        ws = _FakeWebSocket(
            headers={"sec-websocket-protocol": ",,,,"},
            query_params={"token": "fallback_token"},
        )
        token, _ = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token == "fallback_token"

    def test_duplicate_protocols_handled(self) -> None:
        """
        بروتوكولات مكررة في الـ header لا تُسبب مشكلة.
        """
        ws = _FakeWebSocket(
            headers={"sec-websocket-protocol": "jwt, mytoken, jwt, mytoken"},
        )
        token, proto = extract_websocket_auth(ws)  # type: ignore[arg-type]
        assert token == "mytoken"
        assert proto == "jwt"


# ─── extract_websocket_auth_detailed ────────────────────────────────────────


class TestExtractWebsocketAuthDetailed:
    """يختبر النسخة الموسَّعة التي تُرجع WebSocketAuthResult."""

    def test_cookie_source(self) -> None:
        ws = _FakeWebSocket(headers={"cookie": "access_token=tok"})
        result = extract_websocket_auth_detailed(ws)  # type: ignore[arg-type]
        assert isinstance(result, WebSocketAuthResult)
        assert result.token == "tok"
        assert result.source == TokenSource.COOKIE

    def test_query_param_source(self) -> None:
        ws = _FakeWebSocket(query_params={"token": "qtok"})
        result = extract_websocket_auth_detailed(ws)  # type: ignore[arg-type]
        assert result.token == "qtok"
        assert result.source == TokenSource.QUERY_PARAM

    def test_auth_header_source(self) -> None:
        ws = _FakeWebSocket(headers={"authorization": "Bearer htok"})
        result = extract_websocket_auth_detailed(ws)  # type: ignore[arg-type]
        assert result.token == "htok"
        assert result.source == TokenSource.AUTH_HEADER
        assert result.selected_protocol == "jwt"

    def test_subprotocol_source(self) -> None:
        ws = _FakeWebSocket(
            headers={"sec-websocket-protocol": "jwt, stok"}
        )
        result = extract_websocket_auth_detailed(ws)  # type: ignore[arg-type]
        assert result.token == "stok"
        assert result.source == TokenSource.SUBPROTOCOL

    def test_none_source_when_no_token(self) -> None:
        ws = _FakeWebSocket()
        result = extract_websocket_auth_detailed(ws)  # type: ignore[arg-type]
        assert result.token is None
        assert result.source == TokenSource.NONE

    def test_result_is_frozen(self) -> None:
        """WebSocketAuthResult يجب أن يكون immutable."""
        ws = _FakeWebSocket(query_params={"token": "tok"})
        result = extract_websocket_auth_detailed(ws)  # type: ignore[arg-type]
        with pytest.raises((AttributeError, TypeError)):
            result.token = "other"  # type: ignore[misc]


# ─── logging ─────────────────────────────────────────────────────────────────


class TestLogging:
    """يتحقق من أن logging يعمل بدون تسريب token."""

    def test_no_token_triggers_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        ws = _FakeWebSocket()
        with caplog.at_level(logging.WARNING, logger="app.api.routers.ws_auth"):
            extract_websocket_auth(ws)  # type: ignore[arg-type]

        assert any("no_token_found" in r.message for r in caplog.records)

    def test_token_value_not_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """التأكد من أن قيمة token لا تظهر في logs."""
        import logging

        secret_token = "super_secret_jwt_value_12345"
        ws = _FakeWebSocket(query_params={"token": secret_token})

        with caplog.at_level(logging.DEBUG, logger="app.api.routers.ws_auth"):
            extract_websocket_auth(ws)  # type: ignore[arg-type]

        for record in caplog.records:
            assert secret_token not in record.message, (
                f"Token value leaked in log: {record.message}"
            )

    def test_successful_extraction_logs_source(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        ws = _FakeWebSocket(query_params={"token": "tok"})
        with caplog.at_level(logging.INFO, logger="app.api.routers.ws_auth"):
            extract_websocket_auth(ws)  # type: ignore[arg-type]

        assert any("source=query_param" in r.message for r in caplog.records)
