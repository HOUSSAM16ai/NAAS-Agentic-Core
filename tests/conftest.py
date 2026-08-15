"""إعدادات اختبارات مشتركة لمعالجة التحذيرات وضبط مسار الاستيراد.

D-258 (CodeScene X-Ray 2026-08-15): قشرة تفويض نصّية — كل المنطق انتقل إلى
`conftest_support/` (helpers · registry · schema · lifecycle · auth_shards ·
policy). الأسماء العامة كلها محفوظة حرفًا بـlate-binding (قانون D-252) —
**صفر تغيير سلوكي**: أي اختبارٍ يستورد `engine` أو `TestingSessionLocal` أو
`managed_test_session` أو يستخدم fixtureً عامًا يعمل كما كان تمامًا.
"""

from __future__ import annotations

import asyncio
import os
import sys
import warnings
from contextlib import asynccontextmanager, suppress

import pytest

# ── البيئة القانونية الموحَّدة (المستودع كاملًا) ───────────────────────────
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("LLM_MOCK_MODE", "1")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("PROJECT_NAME", "CogniForgeTest")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("PASSLIB_BUILTIN_BCRYPT", "enabled")
# Set a consistent SECRET_KEY for all tests and microservices
os.environ["SECRET_KEY"] = "test-secret-key-for-ci-pipeline-secure-length"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

project_root = os.path.dirname(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

warnings.filterwarnings("ignore", category=PendingDeprecationWarning)

# Pre-load Monolith domain models to ensure they claim the Table definitions first.
# This prevents "Table already defined" errors when Microservice models (with
# extend_existing=True) are loaded later in the same process.
with suppress(ImportError):
    from app.core.domain import audit, chat, content, mission, notification, user  # noqa: F401

# ── القشرة + الشرائح (D-258) ──────────────────────────────────────────────
# الشرائح تُثبت كل الأسماء الخاصة والنقية عند استيرادها؛ الأسماء العامة
# (engine · TestingSessionLocal · fixtures · hooks) تُعرَّف أدناه كقشور.
# ملاحظة معمارية حاسمة (D-258): pytest **لا يفعّل autouse** لfixtures معرَّفة في
# وحداتٍ عاديةٍ تُستورد إلى namespace الـconftest (اختبارٌ تجريبي مثبت). لذلك كل
# fixtureٍ يبقى **تعريفًا هنا** — القشرة تفوض لمنطق الشرائح النقي. الشرائح هنا
# تحمل المنطق والدوال النقية فقط (وhooks تسجَّل من policy عبر الاستيراد لأنها
# hooks وليست fixtures — hooks تُسجَّل بأي استيراد).
from tests.conftest_support import policy  # noqa: F401 — hooks
from tests.conftest_support.auth_shards import _register_user_and_mint_token
from tests.conftest_support.helpers import _run_async
from tests.conftest_support.lifecycle import (
    run_db_lifecycle,
)
from tests.conftest_support.registry import (  # noqa: F401
    TestingSessionLocal,
    _get_engine,
    _get_session_factory,
)
from tests.conftest_support.schema import _ensure_schema

# D-258 follow-up: بيئاتٌ بلا اعتمادات قواعد البيانات (مثل بوابة Skills Doctrine
# Gate في CI — D-069) يجب أن تُجمَّع دون فشلٍ عند التحميل؛ التهيئة تُجمَّع هنا
# فقط عند توفر الاعتمادات وإلا يبقى الاسم محروسًا (importorskip داخل fixtures).
try:
    engine = _get_engine()
except ModuleNotFoundError:  # pragma: no cover — بيئات بلا اعتمادات فقط
    engine = None

# ── managed_test_session (كان fixture داليًا) ──────────────────────────────


@asynccontextmanager
async def managed_test_session():
    """جلسة قاعدة بيانات للاختبارات تعتمد على SQLite داخل الذاكرة."""
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("sqlmodel")
    await _ensure_schema()
    factory = _get_session_factory()
    async with factory() as session:
        yield session


# ── fixtures العامة (قشور تفويض نصّية — التوقيعات كما كانت) ────────────────


@pytest.fixture
def event_loop():
    """حلقة asyncio مخصصة للاختبارات."""
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _global_state_isolation():
    """D-105 (ISS-113): عزل الحالة العالمية لكل اختبار — يقتل فئة بق «يمرّ
    منفردًا ويفشل بترتيب الحزمة الكاملة».

    - snapshot/restore كامل لـ ``os.environ``: أي تسريب env من اختبار (كتابة
      عارية بدون monkeypatch) يُمحى قبل الاختبار التالي.
    - عند رصد تسريب، يُصفَّر كاش ``get_settings`` (lru_cache) لأن قيمه اشتُقت
      من بيئة ملوثة — الاختبار التالي يبني settings نظيفة من البيئة القانونية.
    - الاسترجاع يحدث بعد teardown كل الـ fixtures الدالية الأخرى (autouse setup
      أولاً ⇒ teardown أخيرًا) فلا يتعارض مع monkeypatch.
    """
    env_snapshot = dict(os.environ)
    yield
    leaked = dict(os.environ) != env_snapshot
    if leaked:
        os.environ.clear()
        os.environ.update(env_snapshot)
        with suppress(Exception):
            from app.core.settings.base import get_settings

            get_settings.cache_clear()


@pytest.fixture(autouse=True)
def db_lifecycle(event_loop, request):
    """قشرة تسجيل دورة الحياة — المنطق النقي في `conftest_support.lifecycle` (D-258).

    **لماذا القشرة هنا بدل استيراد مباشر من الشريحة:** pytest لا يفعّل autouse
    لfixtures معرَّفة في وحداتٍ عاديةٍ تُستورد إلى namespace الـconftest
    (اختبارٌ تجريبي مثبت). المنطق النقي في الشريحة وتبقى هذه نقطة التسجيل.
    """
    yield from run_db_lifecycle(event_loop, request)


@pytest.fixture(scope="session")
def static_dir(tmp_path_factory: pytest.TempPathFactory):
    """بناء بنية ملفات ثابتة افتراضية لاختبارات الواجهة."""
    base_dir = tmp_path_factory.mktemp("static")
    (base_dir / "index.html").write_text(
        '<!DOCTYPE html><html><body><div id="root"></div></body></html>',
        encoding="utf-8",
    )
    (base_dir / "css").mkdir()
    (base_dir / "js").mkdir()
    (base_dir / "css" / "superhuman-ui.css").write_text("body{}", encoding="utf-8")
    (base_dir / "js" / "script.js").write_text("console.log('ok');", encoding="utf-8")
    return base_dir


@pytest.fixture
def db_session(event_loop):
    """إرجاع جلسة قاعدة بيانات للاختبار الحالي."""
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("sqlmodel")
    _run_async(event_loop, _ensure_schema())

    async def _open_session():
        factory = _get_session_factory()
        return factory()

    loop = event_loop
    session = loop.run_until_complete(_open_session())
    try:
        yield session
    finally:
        _run_async(event_loop, session.close())


@pytest.fixture
def test_app(static_dir):
    """تهيئة تطبيق الاختبار مع تجاوز اتصال قاعدة البيانات."""
    pytest.importorskip("fastapi")
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("sqlmodel")
    os.environ.setdefault(
        "SECRET_KEY",
        "test-secret-key-that-is-very-long-and-secure-enough-for-tests-v4",
    )
    factory = _get_session_factory()
    from app.core.database import get_db
    from app.core.settings.base import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    settings = get_settings()
    app = create_app(
        settings_override=settings,
        static_dir=str(static_dir),
        enable_static_files=True,
    )

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
def register_and_login_test_user():
    """ينشئ مستخدم اختبار مباشرةً ويعيد رمز JWT صالحًا دون الاعتماد على خدمات خارجية."""

    async def _register(db_session, email: str = "test-user@example.com") -> str:
        return await _register_user_and_mint_token(db_session, email=email)

    return _register


@pytest.fixture
def client(test_app):
    """عميل HTTP متزامن للاختبارات السريعة."""
    from fastapi.testclient import TestClient

    with TestClient(test_app) as test_client:
        yield test_client


@pytest.fixture
def async_client(test_app, event_loop):
    """عميل HTTP غير متزامن للاختبارات التكاملية."""
    from httpx import ASGITransport, AsyncClient

    client_instance = AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    )
    try:
        yield client_instance
    finally:
        _run_async(event_loop, client_instance.aclose())


@pytest.fixture
def admin_user(db_session, event_loop):
    """إنشاء مستخدم إداري للاختبارات."""
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("sqlmodel")
    from app.core.domain.user import User

    async def _create_user():
        from sqlalchemy import select

        stmt = select(User).where(User.email == "admin@example.com")
        existing = (await db_session.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing

        user = User(full_name="Admin", email="admin@example.com", is_admin=True)
        user.set_password("AdminPass123!")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _run_async(event_loop, _create_user())


@pytest.fixture
def admin_auth_headers(db_session, admin_user, event_loop):
    """إنشاء ترويسات مصادقة لمستخدم إداري."""
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("sqlmodel")
    from app.services.auth import AuthService

    async def _issue_tokens():
        auth = AuthService(db_session)
        await auth.rbac.ensure_seed()
        tokens = await auth.issue_tokens(admin_user)
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    return _run_async(event_loop, _issue_tokens())


@pytest.fixture
def user_factory():
    """مصنع مستخدمين للاختبارات."""
    pytest.importorskip("sqlmodel")
    from tests.factories.base import UserFactory

    return UserFactory()


@pytest.fixture
def mission_factory():
    """مصنع مهام للاختبارات."""
    pytest.importorskip("sqlmodel")
    from tests.factories.base import MissionFactory

    return MissionFactory()
