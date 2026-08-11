#!/usr/bin/env python3
"""يُعيد توليد المرجع الذهبي لترانسكريبت WS (ISS-155).

## لماذا سكربتٌ لا رايةُ pytest

المرجع الذهبي يُثبت التكافؤ **قبل/بعد** التفكيك. وطريقةُ توليده يجب أن تكون
قابلةً للتشغيل من قِبل المراجع بأمرٍ واحد، وإلّا صار المرجع صندوقاً أسود يُصدَّق
ولا يُفنَّد. ورايةٌ داخل pytest تخلط «تحقّق» بـ«توليد» في نفس المسار، فتصير
لحظةُ السهو كافيةً لكتابة الواقع الخاطئ فوق العقد.

## الاستعمال

    python scripts/contracts/regenerate_ws_transcript_golden.py

⚠️ **لا يُشغَّل بعد نقلٍ يُراد إثبات تكافؤه.** البرهان هو أن يبقى الملفّ **بلا
تغيّر بايتٍ واحد**؛ فإعادة التوليد بعد النقل تمحو السؤال بدل أن تجيبه.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tests.microservices.test_chat_ws_transcript_contract import (
    GOLDEN_FILE,
    SCENARIOS,
    SCOPES,
    _run_scenario,
)


def main() -> int:
    """يُشغّل كلّ سيناريو في كلّ نطاق ويكتب الترانسكريبت المُجمَّد."""
    golden: dict[str, object] = {}
    for scope in SCOPES:
        for name in SCENARIOS:
            with pytest.MonkeyPatch.context() as monkeypatch:
                golden[f"{scope}::{name}"] = _run_scenario(monkeypatch, scope, name)

    GOLDEN_FILE.write_text(
        json.dumps(dict(sorted(golden.items())), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"✅ {len(golden)} ترانسكريبتاً → {GOLDEN_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
