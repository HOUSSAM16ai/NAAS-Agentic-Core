"""شرائح نواة الواقع (D-260 — تفكيك hotspot `app/kernel.py` — CodeScene X-Ray).

`app/kernel.py` كان hotspotًا بتردد تغييرٍ عالٍ (`__init__`=18 ·
`_handle_lifespan_events`=9/13/Bumpy Road · `_construct_app`=7/50 ·
`_validate_contract_alignment`=2/35/Complex Method — radon B(8)/B(7)) وقوّة
ارتباطٍ داخلية مرتفعة بين دورة الحياة والعقود والـ OTel. فُكِّك إلى قشرةٍ
تفويضٍ في `app/kernel.py` + حزمة شرائح نقية هنا — صفر تغيير سلوكي.

القاعدة المعمارية (نمط D-255/D-258): القشرة تبقى المرجع التنفيذي الوحيد؛
الشرائح دوالٌ نقيةٌ بلا حالةٍ تُستورد وتفوَّض إليها القشرة بالاسم نفسه
(لا أسماء أعيد تعريفها — no shadowing) ليبقى كل monkeypatch واختبارٍ قديم
فعالًا (قانون late-binding من D-252).
"""

from app.core.kernel_support._sources import KERNEL_SOURCE_FILES, read_kernel_source
from app.core.kernel_support.compose import (
    _apply_middleware,
    _configure_static_files,
    _mount_routers,
)
from app.core.kernel_support.contracts import (
    _validate_contract_alignment,
    build_contract_violations,
)
from app.core.kernel_support.lifecycle import (
    _announce_startup_health,
    _start_messaging_relay,
    _stop_messaging_relay,
    run_shutdown_phase,
    run_startup_phase,
)
from app.core.kernel_support.otel import (
    _bootstrap_otel_sdk,
    _instrument_app,
)

__all__ = [
    "KERNEL_SOURCE_FILES",
    "_announce_startup_health",
    "_apply_middleware",
    "_bootstrap_otel_sdk",
    "_configure_static_files",
    "_instrument_app",
    "_mount_routers",
    "_start_messaging_relay",
    "_stop_messaging_relay",
    "_validate_contract_alignment",
    "build_contract_violations",
    "read_kernel_source",
    "run_shutdown_phase",
    "run_startup_phase",
]
