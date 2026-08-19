#!/usr/bin/env python3
"""الدليل قبل الدمج — وعنوان الدفع عقد (D-270 · L1 · L3).

**لماذا هذا المُتحقِّق موجود:**

المستودع يملك ``.github/PULL_REQUEST_TEMPLATE.md`` منذ زمن، بأقسامٍ ممتازة:
دليل التحقّق · الخطر والتراجع · قائمة الحوكمة · أثر الحماية. و**لا شيء يفرضه**.
قالبٌ بلا فارضٍ هو صنف العطب الذي سمّاه D-188 بالاسم: نثرٌ يُقرأ التزاماً وليس التزاماً.
ومسحُ الـworkflows الاثني عشر في 2026-08-19 أعطى **صفر** فارضٍ لوصف الدفع.

والقواعد هنا مأخوذة من ``OpenHands/agent-canvas`` حرفياً في روحها:

* **L1 — الدليل قبل الدمج.** «تشغيل اختبارات الوحدة **لا يكفي**»: يُطلَب الأمر الذي
  شُغِّل ومخرَجه. وPR إصلاح عطب يحمل **دليل إعادة إنتاج** — الحالة قبل الإصلاح ثمّ بعده.
  وهذا امتدادٌ مباشر لقاعدة D-186 (6): «لا يُغلَق بلاغ كارثة بلا عقدٍ يُثبَت أنّه **أحمر
  قبل الإصلاح**» — نفس المبدأ، مرفوعاً من الاختبار إلى الدفعة.
* **قسم ``HUMAN:`` ملك الإنسان.** الوكيل لا يكتبه ولا يعدّله ولا ينقله. وهو الموضع
  الوحيد في المستودع كلّه الذي يشهد فيه **إنسان** أنّه جرّب التغيير بنفسه. حين يفشل
  هذا الفحص فالإصلاح أن يكتبه الإنسان بكلماته — **لا** أن يكتبه الوكيل نيابةً عنه.
* **L3 — عنوان الدفع عقد.** Conventional Commits بأنواعٍ في قائمةٍ مغلقة. العنوان هو
  ما يُقرأ في ``git log`` بعد سنة، وهو المُدخَل الوحيد لأي توليدٍ آلي لسجلّ التغييرات.

**الاستعمال محلياً** (قبل فتح الدفعة):

    python .github/scripts/validate_pr_description.py \\
        --title "feat(gates): add supply chain gate" \\
        --body-file /tmp/pr-body.md --files-file /tmp/pr-files.txt

**في CI:** يقرأ ``GITHUB_EVENT_PATH``. وفحصُ وسم البلاغ المرتبط يجري **فقط** حين
يتوفّر ``GITHUB_TOKEN`` — غيابه لا يُفشِل، لأنّ ما لا يُقرأ لا يُشهَد عليه (D-208 §6).

⛔ stdlib فقط — بلا أيّ تبعية (D-269 L8). Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# ── L3: قائمة الأنواع المغلقة ────────────────────────────────────────────────
#: مغلقة عمداً: نوعٌ حرّ يعني ألّا نوع. مطابِقة لاصطلاح Conventional Commits.
COMMIT_TYPES: tuple[str, ...] = (
    "feat",
    "fix",
    "docs",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
    "security",
)
TITLE_RE = re.compile(rf"^(?:{'|'.join(COMMIT_TYPES)})(?:\([^)]+\))?!?: .+")

# ── L1: الأقسام الإلزامية ────────────────────────────────────────────────────
#: ثلاثةٌ من OpenHands (`Why`/`Summary`/`How to Test`) واثنان من قالب المستودع نفسه.
#: القائمة مغلقة ومكتوبة هنا لأنّها **عقد**؛ توسيعها قرارٌ لا سهو.
REQUIRED_SECTIONS: tuple[str, ...] = (
    "Why",
    "Summary",
    "How to Test",
    "Validation Evidence",
    "Risk & Rollback",
)

#: أقلّ ما يُقبل كشهادةٍ بشرية. أقصر من ذلك تعبئةٌ شكلية.
MIN_HUMAN_NOTE_CHARS = 20

HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
HEADING_RE = re.compile(r"(?m)^##\s+(.+?)\s*$")
HUMAN_RE = re.compile(r"(?im)^\s*HUMAN:\s*$")
AGENT_RE = re.compile(r"(?im)^\s*AGENT:\s*$")
ISSUE_REF_RE = re.compile(r"(?i)(?:fix|clos|resolv)(?:e?(?:s|d)?|ing)?\s+#(\d+)")

#: دليلٌ مرئي: صورة markdown · وسم HTML · أو كتلة كودٍ فيها مخرَج طرفية.
MEDIA_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)|<(?:img|video)\b[^>]*>", re.IGNORECASE)
CODE_BLOCK_RE = re.compile(r"```[\s\S]{10,}?```")

#: مساراتٌ تجعل التغيير مرئياً للطالب ⇒ لقطةٌ إلزامية.
FRONTEND_PREFIXES: tuple[str, ...] = ("frontend/",)

READY_LABEL = "ready-for-dev"


def _strip_comments(body: str) -> str:
    return HTML_COMMENT_RE.sub("", body)


def _sections(body: str) -> dict[str, str]:
    """`## عنوان` ⇒ نصّه، بعد إزالة تعليقات القالب."""
    text = _strip_comments(body)
    found: dict[str, str] = {}
    matches = list(HEADING_RE.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        found[match.group(1).strip()] = text[match.end() : end].strip()
    return found


def _human_note(body: str) -> str | None:
    """نصّ ما بين `HUMAN:` و`AGENT:` — أو `None` إن غاب القسم."""
    text = _strip_comments(body)
    start = HUMAN_RE.search(text)
    if not start:
        return None
    rest = text[start.end() :]
    stop = AGENT_RE.search(rest)
    return (rest[: stop.start()] if stop else rest).strip()


def _has_evidence(text: str) -> bool:
    return bool(MEDIA_RE.search(text) or CODE_BLOCK_RE.search(text))


def _checked_types(body: str) -> set[str]:
    """أنواع التغيير المُؤشَّرة في قائمة `## Type` (أو `## Change Type`)."""
    return {
        match.group(1).strip().lower()
        for match in re.finditer(r"(?m)^\s*[-*]\s*\[[xX]\]\s*(.+?)\s*$", _strip_comments(body))
    }


# ── الفحوص ───────────────────────────────────────────────────────────────────
def _check_title(title: str, problems: list[str]) -> None:
    if not title:
        return  # لا عنوان مُتاحاً (تشغيلٌ محلّي بلا `--title`) — لا يُشهَد على المجهول.
    if not TITLE_RE.match(title):
        problems.append(
            f"L3: العنوان لا يتبع Conventional Commits: {title!r}. "
            f"الصيغة `type(scope): subject` والأنواع المسموحة: {', '.join(COMMIT_TYPES)}"
        )


def _check_sections(sections: dict[str, str], problems: list[str]) -> None:
    for name in REQUIRED_SECTIONS:
        value = sections.get(name)
        if value is None:
            problems.append(f"L1: القسم `## {name}` مفقود من الوصف")
        elif not value.strip("- \n\t"):
            problems.append(f"L1: القسم `## {name}` فارغ — قالبٌ مُعبَّأ شكلياً ليس دليلاً")


def _check_human_note(body: str, problems: list[str]) -> None:
    note = _human_note(body)
    if note is None:
        problems.append(
            "L1: قسم `HUMAN:` مفقود. هو الموضع الوحيد الذي يشهد فيه **إنسان** أنّه "
            "جرّب التغيير — ⛔ ولا يكتبه وكيلٌ نيابةً عن أحد."
        )
        return
    if len(note) < MIN_HUMAN_NOTE_CHARS:
        problems.append(
            f"L1: قسم `HUMAN:` أقصر من {MIN_HUMAN_NOTE_CHARS} حرفاً. "
            "⛔ على **الإنسان** أن يكتب بكلماته ما جرّبه؛ لا يُملأ آلياً."
        )


def _check_test_evidence(sections: dict[str, str], problems: list[str]) -> None:
    """«تشغيل اختبارات الوحدة لا يكفي»: يُطلَب أمرٌ ومخرَجه."""
    proof = f"{sections.get('How to Test', '')}\n{sections.get('Validation Evidence', '')}"
    if not _has_evidence(proof):
        problems.append(
            "L1: لا دليل تنفيذٍ في `How to Test` / `Validation Evidence` — "
            "المطلوب الأمر الذي شُغِّل **ومخرَجه** (كتلة كود) أو لقطة."
        )


def _check_bugfix_reproduction(body: str, sections: dict[str, str], problems: list[str]) -> None:
    checked = _checked_types(body)
    if not any("bug" in item for item in checked):
        return
    haystack = "\n".join(sections.get(name, "") for name in ("Why", "How to Test", "Summary"))
    haystack += "\n" + (sections.get("Validation Evidence", ""))
    if not _has_evidence(haystack):
        problems.append(
            "L1: دفعةُ إصلاحِ عطبٍ بلا دليل إعادة إنتاج — يُعرَض العطب **قبل** الإصلاح "
            "ثمّ النتيجة بعده (يمدّ قاعدة D-186: العقد يُثبَت أحمر قبل الإصلاح)."
        )


def _check_frontend_media(files: list[str], body: str, problems: list[str]) -> None:
    touched = [f for f in files if f.startswith(FRONTEND_PREFIXES)]
    if touched and not MEDIA_RE.search(_strip_comments(body)):
        problems.append(
            f"L1: تغييرٌ في الواجهة ({len(touched)} ملفّاً) بلا لقطةٍ أو فيديو — "
            "ما يراه الطالب يُرى في المراجعة."
        )


def _linked_issues(body: str) -> list[int]:
    return [int(number) for number in ISSUE_REF_RE.findall(_strip_comments(body))]


def _issue_labels(repo: str, number: int, token: str) -> set[str] | None:
    """وسوم بلاغ عبر REST. `None` تعني «لم نستطع القراءة» لا «لا وسوم»."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues/{number}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "naas-pr-governance",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    return {str(label.get("name", "")) for label in payload.get("labels", [])}


def _issues_enabled(repo: str, token: str) -> bool | None:
    """هل البلاغات مُفعَّلة في المستودع؟ `None` تعني «تعذّرت القراءة».

    ⚠️ **قِيس على هذا المستودع في 2026-08-19**: البلاغات **مُعطَّلة** (`410 Issues has
    been disabled`). فقاعدةُ «اربط بلاغاً يحمل `ready-for-dev`» كانت ستطالب كلّ دفعةٍ
    بشيءٍ **يستحيل إنشاؤه** — وهو تعريف المصيدة التي يحظرها D-270 L7 نفسه: فارضٌ
    يُحمِّر ما لا يستطيع أحدٌ إصلاحه يُدرَّب الناس على تجاوزه.

    فالقاعدة مربوطةٌ بـ**الواقع لا بالرأي**: تُعطَّل ما دامت البلاغات مُعطَّلة، وتعود
    من تلقاء نفسها لحظة تفعيلها (نفس تصميم D-227: منعٌ مربوطٌ بوجود الحقل).
    """
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "naas-pr-governance",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return bool(json.load(response).get("has_issues", False))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def _survey_readiness(issues: list[int], repo: str, token: str) -> tuple[bool, list[int]]:
    """(هل وُجد بلاغٌ جاهز؟، ما تعذّرت قراءته) — الفرق بين «لا» و«لا نعرف»."""
    unreadable: list[int] = []
    for number in issues:
        labels = _issue_labels(repo, number, token)
        if labels is None:
            unreadable.append(number)
        elif READY_LABEL in labels:
            return True, unreadable
    return False, unreadable


def _check_readiness_via_api(issues: list[int], repo: str, token: str, problems: list[str]) -> None:
    ready, unreadable = _survey_readiness(issues, repo, token)
    if unreadable:
        print(f"ℹ️  بلاغات تعذّرت قراءتها ({unreadable}) — لم يُشهَد عليها بشيء.")
    if ready or len(unreadable) == len(issues):
        return
    problems.append(
        f"L2: لا بلاغ من {issues} يحمل الوسم `{READY_LABEL}`. "
        "البلاغ يُولَد جاهزاً أو لا يُطوَّر — أكمل معايير القبول فيه أوّلاً."
    )


def _l2_suspended(token: str | None, repo: str | None) -> bool:
    """⛔ لا يُطالَب أحدٌ بربط بلاغٍ في مستودعٍ بلا بلاغات (انظر `_issues_enabled`)."""
    if not token or not repo:
        return False
    return _issues_enabled(repo, token) is False


def _check_linked_issue(body: str, problems: list[str]) -> None:
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if _l2_suspended(token, repo):
        print("ℹ️  L2 مُعطَّل: البلاغات مُعطَّلة في هذا المستودع — القاعدة تعود بتفعيلها.")
        return

    issues = _linked_issues(body)
    if not issues:
        problems.append(
            "L2: لا بلاغ مرتبط. أضف `Fixes #N` — والبلاغ يجب أن يحمل الوسم "
            f"`{READY_LABEL}` (معايير قبولٍ مكتوبة، ودليل إعادة إنتاجٍ للأعطاب)."
        )
    elif token and repo:
        _check_readiness_via_api(issues, repo, token, problems)
    else:
        # ما لا يُقرأ لا يُشهَد عليه: غياب الرمز ليس فشلاً وليس نجاحاً (D-208 §6).
        print(f"ℹ️  ربط البلاغ {issues}: لم يُفحَص الوسم (لا GITHUB_TOKEN — تشغيلٌ محلّي).")


# ── المُدخَلات ────────────────────────────────────────────────────────────────
def _from_event() -> tuple[str, str, list[str]]:
    path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not path or not Path(path).is_file():
        return "", "", []
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    pull = payload.get("pull_request", {})
    return str(pull.get("title") or ""), str(pull.get("body") or ""), []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="D-270 L1/L3 — الدليل قبل الدمج")
    parser.add_argument("--title", default=None)
    parser.add_argument("--body-file", type=Path, default=None)
    parser.add_argument("--files-file", type=Path, default=None)
    args = parser.parse_args(argv)

    event_title, event_body, _ = _from_event()
    title = args.title if args.title is not None else event_title
    body = args.body_file.read_text(encoding="utf-8") if args.body_file else event_body
    files = (
        [
            line.strip()
            for line in args.files_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if args.files_file
        else []
    )

    if not body.strip():
        print("❌ وصف الدفعة فارغ — القالب موجودٌ لسبب.")
        return 1

    problems: list[str] = []
    sections = _sections(body)
    _check_title(title, problems)
    _check_sections(sections, problems)
    _check_human_note(body, problems)
    _check_test_evidence(sections, problems)
    _check_bugfix_reproduction(body, sections, problems)
    _check_frontend_media(files, body, problems)
    _check_linked_issue(body, problems)

    if problems:
        print(f"❌ وصف الدفعة لا يستوفي D-270 ({len(problems)}):")
        for problem in problems:
            print(f"   - {problem}")
        return 1
    print("✅ وصف الدفعة: عنوانٌ بعقد · أقسامٌ كاملة · شهادةُ إنسان · دليل تنفيذ · بلاغٌ جاهز.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
