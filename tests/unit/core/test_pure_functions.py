"""اختبارات شاملة للدوال النقية وفق معايير CS50 وSICP."""

import time
from datetime import UTC, datetime

import pytest
from fastapi import APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.core.app_blueprint import MiddlewareSpec, RouterSpec
from app.core.domain.models import MessageRole, MissionStatus, utc_now

EXPECTED_MESSAGE_ROLES = 4
EXPECTED_MISSION_STATUSES = 9
MAX_DURATION_SECONDS = 0.01


class TestUtcNow:
    """اختبارات دالة utc_now."""

    def test_returns_datetime(self):
        """يجب أن ترجع كائن datetime."""
        result = utc_now()
        assert isinstance(result, datetime)

    def test_returns_utc_timezone(self):
        """يجب أن يكون التوقيت UTC."""
        result = utc_now()
        assert result.tzinfo == UTC

    def test_returns_current_time(self):
        """يجب أن يكون الوقت قريباً من الوقت الحالي."""
        before = datetime.now(UTC)
        result = utc_now()
        after = datetime.now(UTC)

        assert before <= result <= after


class TestCaseInsensitiveEnum:
    """اختبارات CaseInsensitiveEnum."""

    def test_accepts_lowercase(self):
        """يجب قبول الأحرف الصغيرة."""
        role = MessageRole("user")
        assert role == MessageRole.USER

    def test_accepts_uppercase(self):
        """يجب قبول الأحرف الكبيرة."""
        role = MessageRole("USER")
        assert role == MessageRole.USER

    def test_accepts_mixed_case(self):
        """يجب قبول الأحرف المختلطة."""
        role = MessageRole("UsEr")
        assert role == MessageRole.USER

    def test_invalid_value_returns_none(self):
        """يجب إرجاع None للقيم غير الصحيحة."""
        with pytest.raises(ValueError):
            MessageRole("invalid_role")


class TestMessageRole:
    """اختبارات MessageRole enum."""

    def test_has_all_roles(self):
        """يجب أن يحتوي على جميع الأدوار المطلوبة."""
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.TOOL.value == "tool"
        assert MessageRole.SYSTEM.value == "system"

    def test_role_count(self):
        """يجب أن يحتوي على 4 أدوار فقط."""
        assert len(MessageRole) == EXPECTED_MESSAGE_ROLES


class TestMissionStatus:
    """اختبارات MissionStatus enum."""

    def test_has_all_statuses(self):
        """يجب أن يحتوي على جميع الحالات المطلوبة."""
        assert MissionStatus.PENDING.value == "pending"
        assert MissionStatus.PLANNING.value == "planning"
        assert MissionStatus.PLANNED.value == "planned"
        assert MissionStatus.RUNNING.value == "running"
        assert MissionStatus.ADAPTING.value == "adapting"

    def test_status_count(self):
        """يجب أن يطابق إجمالي الحالات التعاريف الثمانية الحالية."""
        assert len(MissionStatus) == EXPECTED_MISSION_STATUSES

    def test_case_insensitive_lookup(self):
        """يجب أن يعمل البحث بغض النظر عن حالة الأحرف."""
        status1 = MissionStatus("pending")
        status2 = MissionStatus("PENDING")
        status3 = MissionStatus("Pending")

        assert status1 == status2 == status3 == MissionStatus.PENDING


class TestKernelHelpers:
    """اختبارات دوال المساعدة في kernel.py."""

    def test_middleware_spec_structure(self):
        """يجب أن يكون MiddlewareSpec tuple من (class, dict)."""
        # اختبار البنية
        spec: MiddlewareSpec = (CORSMiddleware, {"allow_origins": ["*"]})
        middleware_class, options = spec

        assert middleware_class == CORSMiddleware
        assert isinstance(options, dict)
        assert "allow_origins" in options

    def test_router_spec_structure(self):
        """يجب أن يكون RouterSpec tuple من (router, prefix)."""
        # اختبار البنية
        router = APIRouter()
        spec: RouterSpec = (router, "/api/test")
        router_obj, prefix = spec

        assert router_obj == router
        assert isinstance(prefix, str)
        assert prefix.startswith("/")


# ==================== اختبارات التكامل البسيطة ====================


class TestEnumIntegration:
    """اختبارات تكامل بسيطة للـ Enums."""

    def test_message_role_in_dict(self):
        """يجب أن يعمل MessageRole في القواميس."""
        message = {"role": MessageRole.USER, "content": "Hello"}

        assert message["role"] == MessageRole.USER
        assert message["role"].value == "user"

    def test_mission_status_comparison(self):
        """يجب أن تعمل المقارنة بين الحالات."""
        status1 = MissionStatus.PENDING
        status2 = MissionStatus.RUNNING

        assert status1 != status2
        assert status1 == MissionStatus.PENDING

    def test_enum_serialization(self):
        """يجب أن يمكن تحويل Enum إلى string."""
        role = MessageRole.ASSISTANT

        assert str(role.value) == "assistant"
        assert role.value == "assistant"


# ==================== اختبارات الأداء ====================


class TestPerformance:
    """اختبارات أداء بسيطة."""

    def test_utc_now_performance(self):
        """يجب أن تكون utc_now سريعة."""
        start = time.perf_counter()
        for _ in range(1000):
            utc_now()
        duration = time.perf_counter() - start

        # يجب أن تكون أسرع من 10ms لـ 1000 استدعاء
        assert duration < MAX_DURATION_SECONDS

    def test_enum_lookup_performance(self):
        """يجب أن يكون البحث في Enum سريعاً."""

        start = time.perf_counter()
        for _ in range(1000):
            MessageRole("user")
        duration = time.perf_counter() - start

        # يجب أن يكون أسرع من 10ms لـ 1000 استدعاء
        assert duration < MAX_DURATION_SECONDS
