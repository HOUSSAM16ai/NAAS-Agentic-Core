"""اختبارات مسبار الطبقة الخامسة — D-269.

القاعدة التي تحرسها هذه الاختبارات قبل غيرها: **المسبار لا يرفع في وجه المُنادي
أبداً**. فهو يُنادى من `lifespan`، وطرفٌ ثالثٌ يُسقط إقلاع منصّةٍ تخدم 800,000 طالب
عطبٌ أسوأ بكثيرٍ من غياب الطبقة نفسها (نمط D-074: البنية المعرفية لا تكسر الدردشة).

والقاعدة الثانية: **`not_configured` ليست صحّة** — هي «لا نعرف لأنّنا لم نُسأل».
وخلطُها بالنجاح هو ما يحظره D-215 حرفياً.
"""

from __future__ import annotations

import httpx
import pytest

from shared.ambient_memory import AmbientMemoryConfig, probe_ambient_memory
from shared.ambient_memory.contract import AmbientMemoryProbeResult

pytestmark = pytest.mark.asyncio


def _transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """يستبدل تنفيذ الطلب في `httpx` — فلا شبكة في الاختبار."""
    monkeypatch.setattr(httpx.AsyncClient, "post", handler)


# ─────────────────────────────────────────────────────────────────────────────
# العقد
# ─────────────────────────────────────────────────────────────────────────────
def test_url_uses_measured_version() -> None:
    """`v3` قيسَ حيّاً (200) و`v2`/`v1` ردّا 404 — فالإصدار بيانٌ لا تخمين."""
    config = AmbientMemoryConfig(api_key="hch-v3-x")
    assert config.workspaces_list_url() == "https://api.honcho.dev/v3/workspaces/list"


def test_trailing_slash_does_not_double() -> None:
    config = AmbientMemoryConfig(api_key="x", base_url="https://api.honcho.dev/")
    assert "//v3" not in config.workspaces_list_url()


def test_contract_carries_no_content_field() -> None:
    """L2: المنعُ بالنوع لا بالمُرشِّح — لا حقلَ يمكن أن يحمل نصّ محادثة."""
    fields = set(AmbientMemoryProbeResult.__dataclass_fields__)
    assert fields == {"state", "detail", "workspace_count", "status_code"}


def test_not_configured_is_not_healthy() -> None:
    """D-215: «لا نعرف» ليست «سليم»."""
    result = AmbientMemoryProbeResult(state="not_configured", detail="")
    assert result.healthy is False
    assert AmbientMemoryProbeResult(state="reachable", detail="").healthy is True


# ─────────────────────────────────────────────────────────────────────────────
# المسبار
# ─────────────────────────────────────────────────────────────────────────────
async def test_missing_key_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    """بلا مفتاحٍ لا نداءَ شبكةٍ أصلاً — والغياب ليس عطلاً."""

    async def _explode(*args: object, **kwargs: object) -> httpx.Response:
        raise AssertionError("يجب ألّا يقع نداءُ شبكةٍ بلا مفتاح")

    _transport(monkeypatch, _explode)
    result = await probe_ambient_memory(AmbientMemoryConfig(api_key=None))
    assert result.state == "not_configured"


async def test_blank_key_is_not_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _explode(*args: object, **kwargs: object) -> httpx.Response:
        raise AssertionError("الفراغ ليس مفتاحاً")

    _transport(monkeypatch, _explode)
    assert (
        await probe_ambient_memory(AmbientMemoryConfig(api_key="   "))
    ).state == "not_configured"


async def test_success_reads_only_a_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """⛔ لا يُقرأ من الجسم شيءٌ سوى عدد — لا أسماء ولا بيانات."""

    async def _ok(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, json={"items": [{"id": "ETAALIM"}], "total": 1})

    _transport(monkeypatch, _ok)
    result = await probe_ambient_memory(AmbientMemoryConfig(api_key="hch-v3-x"))
    assert result.state == "reachable"
    assert result.workspace_count == 1


async def test_unexpected_body_leaves_count_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """شكلٌ غير متوقَّع ⇒ بلا عدد — المجهول أفضل من يقينٍ زائف (§0)."""

    async def _odd(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, json=["not", "a", "dict"])

    _transport(monkeypatch, _odd)
    result = await probe_ambient_memory(AmbientMemoryConfig(api_key="hch-v3-x"))
    assert result.state == "reachable"
    assert result.workspace_count is None


@pytest.mark.parametrize("status", [401, 403])
async def test_rejected_key_is_unauthorized(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    """مفتاحٌ مرفوض عطلُ إعدادٍ صريح، لا انقطاعُ شبكة — والتمييز يوفّر ساعةَ تشخيص."""

    async def _denied(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(status, json={"detail": "nope"})

    _transport(monkeypatch, _denied)
    result = await probe_ambient_memory(AmbientMemoryConfig(api_key="hch-v3-bad"))
    assert result.state == "unauthorized"
    assert result.status_code == status


async def test_timeout_is_unknown_not_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-215: انتهاء المهلة يعني «لا نعرف» — ولا يُقرأ نجاحاً."""

    async def _slow(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow")

    _transport(monkeypatch, _slow)
    result = await probe_ambient_memory(AmbientMemoryConfig(api_key="hch-v3-x"))
    assert result.state == "unreachable"
    assert result.healthy is False


async def test_network_error_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """L4: طرفٌ ثالثٌ لا يُسقط إقلاع المنصّة."""

    async def _broken(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("dns")

    _transport(monkeypatch, _broken)
    result = await probe_ambient_memory(AmbientMemoryConfig(api_key="hch-v3-x"))
    assert result.state == "unreachable"


async def test_server_error_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _boom(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(503, text="down")

    _transport(monkeypatch, _boom)
    result = await probe_ambient_memory(AmbientMemoryConfig(api_key="hch-v3-x"))
    assert result.state == "unreachable"
    assert result.status_code == 503


async def test_unparseable_body_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _garbage(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, text="<html>nope</html>")

    _transport(monkeypatch, _garbage)
    assert (
        await probe_ambient_memory(AmbientMemoryConfig(api_key="hch-v3-x"))
    ).state == "unreachable"


async def test_key_never_appears_in_any_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    """⛔ لا يُطبَع المفتاح ولا جزءٌ منه — ولا حتى في نصّ خطأ.

    نصُّ استثناء `httpx` قد يحمل الطلبَ بترويساته، ولذلك يُقرأ **اسمُ الصنف** لا نصُّه.
    """
    secret = "hch-v3-supersecretvaluethatmustnotleak"

    async def _broken(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.ConnectError(f"failed with Authorization: Bearer {secret}")

    _transport(monkeypatch, _broken)
    result = await probe_ambient_memory(AmbientMemoryConfig(api_key=secret))
    assert secret not in result.detail
    assert secret not in str(result.summarize())


async def test_summarize_is_display_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _ok(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, json={"total": 3})

    _transport(monkeypatch, _ok)
    summary = (await probe_ambient_memory(AmbientMemoryConfig(api_key="hch-v3-x"))).summarize()
    assert summary["status"] == "reachable"
    assert summary["workspaces"] == 3
