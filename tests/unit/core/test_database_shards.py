"""اختبارات السلوك المطابق حرفيًّا بعد تفكيك hotspot `app/core/database.py` (D-261 · ISS-172).
القاعدة (نمط D-252/D-260): السلوك قبل وبعد التفكيك متطابق حرفيًّا — الشرائح دوالٌ
نقيةٌ بلا حالةٍ، والقشرة تفوِّض فقط. كل اختبار هنا يثبت أن السلوك المفكك
مطابق للسلوك الأصلي الموثّق في CodeScene/D-WS-FLAP-001.
"""

from __future__ import annotations

import ssl

import pytest

from app.core.database import create_session_factory, engine, get_db, get_db_session
from app.core.database_support import (
    _is_supabase_url,
    _rewrite_supabase_port,
    _strip_ssl_query,
    _upgrade_drivername,
    build_pool_kwargs,
    build_ssl_connect_args,
)


def _url(url: str):
    from sqlalchemy.engine.url import make_url

    return make_url(url)


# ── شريحة الـ URL ──────────────────────────────────────────────────────────────


def test_is_supabase_url_by_host() -> None:
    """مطابق حرفيًّا للأصل: `if host and "supabase.com" in host: return True`."""
    assert _is_supabase_url("aws-1-eu-west-3.pooler.supabase.com", 6543)
    assert _is_supabase_url("aws-1-eu-west-3.pooler.supabase.com", 5432)
    assert not _is_supabase_url(
        "db.example.com", None
    )  # بلا مضيف Supabase وبلا منفذ PgBouncer = False


def test_is_supabase_url_by_pgbouncer_port() -> None:
    """الأصل: `return port == 6543` — أي منفذ PgBouncer يُعدّ Supabase."""
    assert _is_supabase_url(None, 6543)
    assert not _is_supabase_url(None, 5432)
    assert _is_supabase_url("db.example.com", 6543)  # الأصل: port==6543 وحده كافٍ


def test_upgrade_drivername_postgres() -> None:
    url = _upgrade_drivername(_url("postgresql://u:p@h:5432/db"))
    assert url.drivername == "postgresql+asyncpg"
    url = _upgrade_drivername(_url("postgres://u:p@h:5432/db"))
    assert url.drivername == "postgresql+asyncpg"


def test_upgrade_drivername_already_async() -> None:
    url = _upgrade_drivername(_url("postgresql+asyncpg://u:p@h:5432/db"))
    assert url.drivername == "postgresql+asyncpg"


def test_upgrade_drivername_sqlite_untouched() -> None:
    url = _upgrade_drivername(_url("sqlite:///db.sqlite3"))
    assert url.drivername == "sqlite"


def test_strip_ssl_query_extracts_require() -> None:
    url, mode = _strip_ssl_query(_url("postgresql://u:p@h:5432/db?sslmode=require"))
    assert mode == "require"
    assert "sslmode" not in dict(url.query)


def test_strip_ssl_query_extracts_ssl_alias() -> None:
    url, mode = _strip_ssl_query(_url("postgresql://u:p@h:5432/db?ssl=require"))
    assert mode == "require"
    assert "ssl" not in dict(url.query)


def test_strip_ssl_query_no_ssl_params() -> None:
    url, mode = _strip_ssl_query(_url("postgresql://u:p@h:5432/db"))
    assert mode is None
    assert dict(url.query) == {}


def test_rewrite_supabase_port_rewrites_6543() -> None:
    url = _rewrite_supabase_port(_url("postgresql://u:p@h.supabase.com:6543/db"), True)
    assert url.port == 5432


def test_rewrite_supabase_port_leaves_5432() -> None:
    url = _rewrite_supabase_port(_url("postgresql://u:p@h.supabase.com:5432/db"), True)
    assert url.port == 5432


def test_rewrite_supabase_port_non_supabase_untouched() -> None:
    url = _rewrite_supabase_port(_url("postgresql://u:p@h.example.com:6543/db"), False)
    assert url.port == 6543


# ── شريحة SSL ───────────────────────────────────────────────────────────────────


def test_ssl_context_require_no_verify() -> None:
    args = build_ssl_connect_args("require")
    ctx = args["ssl"]
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE


@pytest.mark.parametrize("mode", ["verify-ca", "verify-full"])
def test_ssl_context_verify_modes(mode: str) -> None:
    ctx = build_ssl_connect_args(mode)["ssl"]
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED


def test_ssl_context_unknown_mode_empty() -> None:
    assert build_ssl_connect_args(None) == {}
    assert build_ssl_connect_args("bogus") == {}


# ── شريحة الـ pool ──────────────────────────────────────────────────────────────


def test_connect_args_disable_prepared_statement_caches() -> None:
    """`statement_cache_size=0` داخل `connect_args` — الشكل الذي تؤكده بوابتا الحراسة."""
    from app.core.database_support._pools import _connect_args

    args = _connect_args({"ssl": "ctx"})
    assert args["statement_cache_size"] == 0
    assert args["prepared_statement_cache_size"] == 0
    assert args["ssl"] == "ctx"


def test_supabase_pool_profile() -> None:
    kwargs = build_pool_kwargs(
        debug=False,
        is_supabase=True,
        environment="production",
        ssl_args={"ssl": "ctx"},
        port=5432,
    )
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 5
    assert kwargs["pool_recycle"] == 300
    assert kwargs["connect_args"]["ssl"] == "ctx"
    assert kwargs["connect_args"]["statement_cache_size"] == 0


def test_dev_pool_profile() -> None:
    kwargs = build_pool_kwargs(
        debug=False,
        is_supabase=False,
        environment="development",
        ssl_args={},
        port=None,
    )
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_recycle"] == 1800


def test_prod_pool_profile() -> None:
    kwargs = build_pool_kwargs(
        debug=False,
        is_supabase=False,
        environment="production",
        ssl_args={},
        port=None,
    )
    assert kwargs["pool_size"] == 40
    assert kwargs["max_overflow"] == 60


def test_staging_uses_prod_profile() -> None:
    kwargs = build_pool_kwargs(
        debug=False,
        is_supabase=False,
        environment="staging",
        ssl_args={},
        port=None,
    )
    assert kwargs["pool_size"] == 40


def test_supabase_beats_environment_for_pool_profile() -> None:
    """Supabase profile يُنصَّب حتى في وضع التطوير (D-WS-FLAP-001)."""
    kwargs = build_pool_kwargs(
        debug=False,
        is_supabase=True,
        environment="development",
        ssl_args={},
        port=5432,
    )
    assert kwargs["pool_size"] == 5


# ── القشرة: الأسماء القديمة محفوظة (no shadowing · late-binding D-252) ───────────


def test_legacy_names_re_exported() -> None:
    """كل اسمٍ واجهةٍ قديم يعمل — لا كاسر لأي مستورد/monkeypatch قائم."""
    from app.core.database import (  # noqa: F401
        async_session_factory,
        create_db_engine,
        create_session_factory,
        engine,
        get_db,
        get_db_session,
    )


def test_get_db_session_is_get_db_alias() -> None:
    """D-261 (ISS-172): alias الكنسي — المصدر الوحيد للمسار التربوي الزومبي."""
    assert get_db_session is get_db


def test_create_session_factory_unchanged() -> None:
    factory = create_session_factory(engine)
    assert factory.kw.get("expire_on_commit") is False
    assert factory.kw.get("autocommit") is False
    assert factory.kw.get("autoflush") is False
