"""يتحقق أن حركة legacy تساوي صفرًا لمدة نافذة لا تقل عن 30 يومًا قبل الإنهاء الكامل.

⚠️ **تصحيح D-205 (2026-08-01).** كانت هذه البوّابة تقرأ
`docs/architecture/LEGACY_TRAFFIC_30D_STATUS.json` — وهو ملفّ يقول عن نفسه حرفياً
`"verified_by": "ops-placeholder"` و«ملفّ دليل نائب… استبدله بقيم من التتبّع» —
ثمّ تطبع **«✅ صفر حركة legacy مُتحقَّق لـ≥30 يوماً»**. وفي الوقت نفسه المونوليث
(«legacy») هو ما يخدم **كلّ** طالب فعلياً (`.devcontainer/supervisor.sh:577` →
`uvicorn app.main:app`)، والبديل مطروح بنسبة **0%**
(`ROUTE_CHAT_*_ROLLOUT_PERCENT=0`، `CONVERSATION_CAPABILITY_LEVEL="stub"`).

فكان الرقم صفراً لأنّ أحداً لم يقس، لا لأنّ الحركة انعدمت — وهو بالضبط ما يحرّمه §0:
«المجهول أفضل من اليقين المزيّف». البوّابة الآن تميّز الحالتين:

* **قِيس وكان صفراً** ⇒ ✅ ويجوز الاستناد إليه.
* **لم يُقَس** ⇒ ⚠️ NOT MEASURED، والمرحلة 5 (الإنهاء) **مرفوضة**، والخروج يبقى صفراً
  حتى لا يحمرّ CI على دَينٍ توثيقي سابق. من أراد الصرامة يُمرّر `--require-measured`
  (وهو ما يجب أن يسبق أيّ حذف فعلي للنواة القديمة).

القراءة الصحيحة لهذا الملفّ اليوم: **مقياسٌ لم يبدأ بعد.**
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATUS_FILE = REPO_ROOT / "docs/architecture/LEGACY_TRAFFIC_30D_STATUS.json"

#: علاماتُ «هذا الرقم ليس قياساً». `verified_by` فارغاً أو نائباً يكفي وحده.
_PLACEHOLDER_MARKERS = ("placeholder", "todo", "tbd", "unknown", "n/a")


def is_measured(data: dict[str, object]) -> bool:
    """هل هذا الملفّ قياسٌ حقيقي أم نائبٌ يرتدي زيّ القياس؟"""
    if str(data.get("status", "")).strip().lower() == "not_measured":
        return False
    verified_by = str(data.get("verified_by") or "").strip().lower()
    if not verified_by:
        return False
    if any(marker in verified_by for marker in _PLACEHOLDER_MARKERS):
        return False
    return bool(str(data.get("verified_at") or "").strip())


def main(require_measured: bool = False) -> int:
    if not STATUS_FILE.exists():
        print("❌ Missing legacy traffic evidence file.")
        return 1

    data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))

    if not is_measured(data):
        print("⚠️  Legacy traffic: NOT MEASURED — no telemetry backs this file.")
        print("    The monolith still serves 100% of student traffic (supervisor.sh),")
        print("    so a zero here would mean 'nobody counted', not 'nobody called'.")
        print("    Phase 5 (decommission) is REFUSED until real telemetry replaces it.")
        return 1 if require_measured else 0

    window_days = int(data.get("window_days", 0))
    if window_days < 30:
        print(f"❌ Legacy traffic window too short: {window_days}d < 30d")
        return 1

    #: كل عدّاد يجب أن يكون صفراً. القيمة الافتراضية سالبة عمداً — الحقل الغائب فشلٌ
    #: لا صفر (§0: الغياب ليس قياساً).
    counters = (
        ("legacy_request_total_30d", float(data.get("legacy_request_total_30d", -1))),
        ("legacy_ws_sessions_total_30d", float(data.get("legacy_ws_sessions_total_30d", -1))),
        ("legacy_traffic_ratio_30d", float(data.get("legacy_traffic_ratio_30d", -1.0))),
    )
    failures = [(field, value) for field, value in counters if value != 0]
    if failures:
        for field, value in failures:
            print(f"❌ {field} must be zero over the 30d window: {value}")
        return 1

    print("✅ Legacy traffic hard-zero verified for >=30 days.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-measured",
        action="store_true",
        help="Fail when the evidence file is a placeholder rather than telemetry.",
    )
    raise SystemExit(main(require_measured=parser.parse_args().require_measured))
