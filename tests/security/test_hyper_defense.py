from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request, status

from app.security.chrono_shield import ChronoShield


@pytest.fixture
def mock_request():
    req = MagicMock(spec=Request)
    req.client.host = "192.168.1.100"
    return req


@pytest.fixture
def fresh_shield():
    """Returns a fresh instance of ChronoShield for testing."""
    return ChronoShield()


@pytest.mark.asyncio
async def test_chrono_shield_allowance_under_limit(fresh_shield, mock_request):
    """Test that requests are allowed when under the limit."""
    # Should pass without exception
    await fresh_shield.check_allowance(mock_request, "test@example.com")


@pytest.mark.asyncio
async def test_chrono_shield_exponential_backoff(fresh_shield, mock_request):
    """Test that requests trigger sleep (dilation) after MAX_FREE_ATTEMPTS."""
    identifier = "attack@example.com"

    # Fill up free attempts
    for _ in range(fresh_shield.MAX_FREE_ATTEMPTS + 1):
        fresh_shield.record_failure(mock_request, identifier)

    # The next check should trigger a sleep
    # We mock asyncio.sleep to verify it's called and check duration
    with patch("asyncio.sleep", new_callable=MagicMock) as mock_sleep:
        # We need check_allowance to be an async function (which it is)
        # However, asyncio.sleep is a coroutine, so the mock must be awaitable?
        # Or simply patching it with a AsyncMock?
        # Standard MagicMock isn't awaitable. Use AsyncMock or make the return value a future.

        # Actually, python 3.8+ asyncio.sleep is a coroutine function.
        # Let's use an AsyncMock.
        async def async_sleep_mock(delay):
            return None

        mock_sleep.side_effect = async_sleep_mock

        await fresh_shield.check_allowance(mock_request, identifier)

        # Verify call
        # Failures: MAX_FREE (5) + 1 = 6.
        # Threat Level = 6.
        # Exponent = 6 - 5 = 1.
        # Delay = 0.1 * (2^1) = 0.2s.
        mock_sleep.assert_called_with(0.2)


@pytest.mark.asyncio
async def test_chrono_shield_hard_lockout(fresh_shield, mock_request):
    """Test that requests are blocked (429) after LOCKOUT_THRESHOLD."""
    identifier = "locked@example.com"

    # Fill up to lockout
    for _ in range(fresh_shield.LOCKOUT_THRESHOLD):
        fresh_shield.record_failure(mock_request, identifier)

    # Next check should raise 429
    with pytest.raises(HTTPException) as excinfo:
        await fresh_shield.check_allowance(mock_request, identifier)

    assert excinfo.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "suspended" in excinfo.value.detail


@pytest.mark.asyncio
async def test_chrono_shield_reset(fresh_shield, mock_request):
    """Test that successful login resets the target counter."""
    identifier = "valid@example.com"

    # Create some failures
    fresh_shield.record_failure(mock_request, identifier)
    fresh_shield.record_failure(mock_request, identifier)
    assert len(fresh_shield._failures[f"target:{identifier}"]) == 2

    # Reset
    fresh_shield.reset_target(identifier)

    # Should be empty
    assert f"target:{identifier}" not in fresh_shield._failures


@pytest.mark.asyncio
async def test_chrono_shield_ip_persistence(fresh_shield, mock_request):
    """Test that IP failures persist even if target is reset (Anti-Rotation)."""
    identifier = "user1@example.com"
    ip = "192.168.1.100"  # defined in mock_request

    fresh_shield.record_failure(mock_request, identifier)

    # Reset target
    fresh_shield.reset_target(identifier)

    # Target history gone
    assert f"target:{identifier}" not in fresh_shield._failures

    # IP history remains
    assert len(fresh_shield._failures[f"ip:{ip}"]) == 1

    # D-236 · ISS-152 — القصد الدفاعي محفوظ، والمعايرة صُحِّحت.
    #
    # هذا الاختبار هو ما حمى مضادّ التدوير: أوّل صياغة للإصلاح حذفت متّجه العنوان
    # من الإبطاء بالكامل، فأسقطه الاختبار — وكان مُحقّاً. العطب كان في **القفل
    # الصلب** (429) لا في الإبطاء: الإبطاء يُكلِّف ثوانيَ ولا يمنع أحداً.
    #
    # ما تغيّر: عتبة الإبطاء على العنوان صارت `IP_MAX_FREE_ATTEMPTS` (20) بدل
    # مشاركة عتبة الهوية (5). القديمة كانت تفترض «عنوان = مستخدم واحد»، وهو
    # افتراض خاطئ خلف بروكسي Next.js وcarrier-NAT الجزائري — وهو أصل قفل المنصّة.
    #
    # ⚠️ الإخفاقات تُوزَّع على **هويات مختلفة** عمداً: هذا هو معنى «التدوير»
    # حرفياً، ويُبقي كل متّجه هوية تحت عتبته فيُقاس متّجه العنوان وحده.
    for index in range(fresh_shield.IP_MAX_FREE_ATTEMPTS):
        fresh_shield.record_failure(mock_request, f"rotated-{index}@example.com")

    # Total IP failures: 1 (user1) + 20 (rotated) = 21 → تجاوزٌ قدره 1 فوق عتبة
    # العنوان، وكل هوية منفردة عند إخفاق واحد فقط.
    probe_identity = "rotated-0@example.com"

    with patch("asyncio.sleep", new_callable=MagicMock) as mock_sleep:

        async def async_sleep_mock(delay):
            return None

        mock_sleep.side_effect = async_sleep_mock

        await fresh_shield.check_allowance(mock_request, probe_identity)

        # تجاوزٌ قدره 1 ⇒ 0.1 * 2^1 = 0.2s — نفس زمن الإبطاء الذي كان يفرضه
        # الاختبار الأصلي، على العتبة المُصحَّحة.
        mock_sleep.assert_called_with(0.2)
