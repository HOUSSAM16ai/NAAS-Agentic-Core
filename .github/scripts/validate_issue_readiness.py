#!/usr/bin/env python3
"""البلاغ يُولَد جاهزاً أو لا يُطوَّر (D-270 L2).

**لماذا هذا المُتحقِّق موجود:**

سجلّ ``.memory/issues.md`` يشترط على كل بلاغٍ مغلق ثلاثة أشياء: **جذرٌ** ودليلٌ
**حيّ** وشرط **إغلاق**. وهو أعلى معيارٍ رأيتُه في مستودعٍ من هذا الحجم — لكنّه مفروضٌ
على **السجلّ** بعد المعالجة، لا على **البلاغ** عند ولادته. فما يدخل من الباب لا يُسأل
شيئاً، وما يُكتب في السجلّ يُسأل كلّ شيء.

والثمن معروفٌ في هذا المستودع بالاسم: ISS-145 أُغلقت «بالتفنيد» على **معيارٍ خطأ**
(فحصَت أنّ مكوّناً مُرفَق لا أنّه قابل للرسم). ومعيارُ إغلاقٍ خطأ يولد من بلاغٍ بلا
**معايير قبولٍ مكتوبة** — لأنّ من لا يكتب شرط النجاح مُسبَقاً يخترعه بعد الإصلاح.

فالقاعدة (من ``OpenHands/agent-canvas``): الوسم ``ready-for-dev`` **تديره الآلة**،
ولا يُمنَح إلّا لبلاغٍ يحمل:

* **عطب** (``type:bug``): خطوات إعادة إنتاج · دليل (سجلّ/أثر/لقطة) · معايير قبول
  بقائمةٍ مؤشَّرة واحدة على الأقلّ.
* **ميزة** (``type:feature``): الحلّ المقترح · معايير قبول بقائمةٍ مؤشَّرة.

⛔ ولا يُمنَح الوسم لبلاغٍ بلا نوعٍ مُصرَّح — النوع المجهول لا يُقاس عليه شيء.

**الاستعمال محلياً:**

    python .github/scripts/validate_issue_readiness.py \\
        --body-file /tmp/issue.md --labels type:bug --json

⛔ stdlib فقط — بلا أيّ تبعية (D-269 L8). Exit 0 = جاهز · 1 = غير جاهز.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

BUG_LABEL = "type:bug"
FEATURE_LABEL = "type:feature"
READY_LABEL = "ready-for-dev"

#: نماذج البلاغات في GitHub تُصيّر كل حقلٍ عنواناً من الرتبة الثالثة `### Label`.
HEADING_RE = re.compile(r"(?m)^###\s+(.+?)\s*$")

#: ما يكتبه GitHub لحقلٍ اختياري فارغ.
NO_RESPONSE = "_No response_"

#: بندٌ في قائمةٍ مؤشَّرة — مُؤشَّراً كان أو غير مُؤشَّر: المهمّ أنّ الشرط **مكتوب**.
CHECKLIST_RE = re.compile(r"(?m)^\s*[-*]\s*\[[ xX]\]\s*\S+")

#: دليلٌ ملموس: صورة · فيديو · أو كتلة كودٍ غير فارغة (أثر أو سجلّ).
#: الحدّ الأدنى يمنع السياج الفارغ ولا يعاقب أثراً قصيراً صادقاً — ضُبِط بعد أن
#: رفضت النسخةُ الأولى سطرَ فشلٍ حقيقياً من ٢٥ حرفاً.
EVIDENCE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)|<(?:img|video)\b[^>]*>", re.IGNORECASE)
CODE_BLOCK_RE = re.compile(r"```[\s\S]{10,}?```")

#: الحقول المطلوبة لكل نوع: (عنوان الحقل، هل يشترط قائمةً مؤشَّرة؟)
BUG_FIELDS: tuple[tuple[str, bool], ...] = (
    ("Reproduction steps", False),
    ("Acceptance criteria", True),
)
FEATURE_FIELDS: tuple[tuple[str, bool], ...] = (
    ("Proposed solution", False),
    ("Acceptance criteria", True),
)


def _fields(body: str) -> dict[str, str]:
    found: dict[str, str] = {}
    matches = list(HEADING_RE.finditer(body))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        found[match.group(1).strip().lower()] = body[match.end() : end].strip()
    return found


def _value(fields: dict[str, str], label: str) -> str:
    value = fields.get(label.lower(), "")
    return "" if value.strip() == NO_RESPONSE else value


def _has_evidence(text: str) -> bool:
    return bool(EVIDENCE_RE.search(text) or CODE_BLOCK_RE.search(text))


def _check_fields(
    fields: dict[str, str], required: tuple[tuple[str, bool], ...], reasons: list[str]
) -> None:
    for label, needs_checklist in required:
        value = _value(fields, label)
        if not value:
            reasons.append(f"الحقل «{label}» فارغ أو مفقود")
        elif needs_checklist and not CHECKLIST_RE.search(value):
            reasons.append(
                f"«{label}» بلا بندٍ واحد في قائمةٍ مؤشَّرة (`- [ ] …`) — "
                "من لا يكتب شرط النجاح مُسبَقاً يخترعه بعد الإصلاح (ISS-145)"
            )


def evaluate(body: str, labels: set[str]) -> tuple[bool, list[str]]:
    fields = _fields(body)
    reasons: list[str] = []

    if BUG_LABEL in labels:
        _check_fields(fields, BUG_FIELDS, reasons)
        evidence = "\n".join(
            _value(fields, name) for name in ("Logs / traces / screenshots", "Reproduction steps")
        )
        if not _has_evidence(evidence):
            reasons.append("لا دليل ملموس (أثر · سجلّ · لقطة) — «انظر الوصف» ليست دليلاً")
    elif FEATURE_LABEL in labels:
        _check_fields(fields, FEATURE_FIELDS, reasons)
    else:
        reasons.append(
            f"بلا نوعٍ مُصرَّح (`{BUG_LABEL}` أو `{FEATURE_LABEL}`) — النوع المجهول لا يُقاس عليه شيء"
        )

    return not reasons, reasons


def _from_event() -> tuple[str, set[str]]:
    path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not path or not Path(path).is_file():
        return "", set()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    issue = payload.get("issue", {})
    return str(issue.get("body") or ""), {
        str(label.get("name", "")) for label in issue.get("labels", [])
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="D-270 L2 — جاهزية البلاغ")
    parser.add_argument("--body-file", type=Path, default=None)
    parser.add_argument("--labels", default=None, help="مفصولة بفواصل")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    event_body, event_labels = _from_event()
    body = args.body_file.read_text(encoding="utf-8") if args.body_file else event_body
    labels = (
        {item.strip() for item in args.labels.split(",") if item.strip()}
        if args.labels is not None
        else event_labels
    )

    ready, reasons = evaluate(body, labels)

    if args.json:
        print(json.dumps({"ready": ready, "reasons": reasons}, ensure_ascii=False))
    elif ready:
        print(f"✅ البلاغ جاهز — يستحقّ الوسم `{READY_LABEL}`.")
    else:
        print(f"❌ البلاغ ليس جاهزاً ({len(reasons)}):")
        for reason in reasons:
            print(f"   - {reason}")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
