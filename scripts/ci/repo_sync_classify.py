"""تصنيف سبب رفض الدفع إلى المستودع النظير — قائمة مغلقة، بلا تخمين.

**لماذا هذا الملفّ (ISS-197):** حلقة إعادة المحاولة في ``.github/workflows/repo-sync.yml``
كُتبت لسببٍ واحد منطوق في تعليقها: سباق ``cannot lock ref`` حين تعمل المزامنتان معاً. لكنّها
كانت تُعاد على **كلّ** فشل، ومنها رفضُ حماية الفرع — وهو رفضٌ **حتميّ**: خمس محاولاتٍ وخمسون
ثانية نومٍ لا تغيّر قاعدةً في إعدادات المستودع. فكانت الوظيفة تحرق ~60 ثانية عدّاء في كل دفعة
ثمّ تطبع ``push failed after 5 attempts`` بلا سببٍ ولا مقدار انحراف — أي بالضبط ما يحذّر منه
رأس الـworkflow نفسه: ``failing every commit … trains people to ignore the job``.

**لماذا سكربت لا سطرُ ``grep`` داخل الـYAML:** منطقٌ في YAML لا يُختبَر إلا بدفعةٍ حيّة إلى
``main``. هنا يُغذّى التصنيف **بنصّ الرفض الحقيقي** المُلتقَط من الوظيفة ``99129715678``
ويُثبَت سلوكه أحمر-قبل/أخضر-بعد على العدّاء المحلّي (D-270 L4 — الفارض يُثبت أنّه يحجب،
لا أنّه يعمل فقط).

**القاعدة الدائمة:** الحتميّ يُبلَّغ عنه فوراً، والعابر يُعاد. وما لا نعرفه يُعاد أيضاً —
الأمان في أن يكون المجهول **قابلاً لإعادة المحاولة** لا أن يُصنَّف حتميّاً بالتخمين
(D-206 L11: السبب يُصرَّح، والغياب لا يُقرأ نجاحاً).

الاستعمال:

    python3 scripts/ci/repo_sync_classify.py push.log
    python3 scripts/ci/repo_sync_classify.py < push.log

المخرَج: السطر الأول رمزُ التصنيف من القائمة المغلقة، وما بعده أسطرُ القاعدة المخروقة كما
نطق بها الريموت (قد تكون فارغة). ويخرج دائماً بالرمز 0 — فالتصنيف معلومة لا حكم، والقرار
للمُنادي.
"""

from __future__ import annotations

import re
import sys

#: القائمة المغلقة للتصنيفات. لا رمز خارجها — ``probably-transient`` وأخواتها ممنوعة
#: نصّياً (نمط D-267 L6: آلة حالاتٍ حتمية لا عبارةٌ ضبابية).
PROTECTED_BRANCH = "protected_branch"
AUTH_DENIED = "auth_denied"
TRANSIENT_LOCK = "transient_lock"
UNKNOWN = "unknown"

CLASSIFICATIONS: tuple[str, ...] = (
    PROTECTED_BRANCH,
    AUTH_DENIED,
    TRANSIENT_LOCK,
    UNKNOWN,
)

#: التصنيفات التي **لا تُعاد المحاولة** عليها: إعادةُ الدفع لا تغيّر قاعدةً في الإعدادات
#: ولا تمنح صلاحيةً غائبة. كلّ ما عداها — بما فيه ``unknown`` — يبقى قابلاً لإعادة المحاولة.
DETERMINISTIC: frozenset[str] = frozenset({PROTECTED_BRANCH, AUTH_DENIED})

_PROTECTED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"protected branch hook declined", re.IGNORECASE),
    re.compile(r"\bGH006\b"),
    re.compile(r"Protected branch update failed", re.IGNORECASE),
)

_AUTH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Authentication failed", re.IGNORECASE),
    re.compile(r"could not read (?:Username|Password)", re.IGNORECASE),
    re.compile(r"remote: Permission to .+ denied", re.IGNORECASE),
    re.compile(r"fatal: Authentication", re.IGNORECASE),
)

_TRANSIENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"cannot lock ref", re.IGNORECASE),
    re.compile(r"failed to lock", re.IGNORECASE),
    re.compile(r"failed to update ref", re.IGNORECASE),
    re.compile(r"Unable to create .+\.lock", re.IGNORECASE),
)

#: أسطر القاعدة التي يطبعها GitHub تحت ``remote:`` على هيئة نقاطٍ تبدأ بـ``-``.
_RULE_LINE = re.compile(r"^\s*remote:\s*-\s*(?P<rule>\S.*?)\s*$")


def classify(output: str) -> str:
    """يُرجع رمز التصنيف لمخرَج ``git push``.

    الترتيب جزءٌ من العقد: رفضُ الحماية يُفحَص أوّلاً لأنّ نصّه يحمل أيضاً
    ``! [remote rejected]`` الذي تطابقه أنماط العابر — فلو انعكس الترتيب لصُنِّفت
    كارثةٌ حتمية «سباقاً عابراً» وعادت الحلقة الخمسية من الباب الذي أُغلق.
    """
    for pattern in _PROTECTED_PATTERNS:
        if pattern.search(output):
            return PROTECTED_BRANCH
    for pattern in _AUTH_PATTERNS:
        if pattern.search(output):
            return AUTH_DENIED
    for pattern in _TRANSIENT_PATTERNS:
        if pattern.search(output):
            return TRANSIENT_LOCK
    return UNKNOWN


def is_deterministic(classification: str) -> bool:
    """هل يُعدّ هذا التصنيف حتميّاً فتتوقّف إعادة المحاولة فوراً؟"""
    return classification in DETERMINISTIC


def extract_rules(output: str) -> list[str]:
    """يستخرج أسطر القاعدة المخروقة كما نطق بها الريموت، بترتيبها وبلا تكرار.

    تُنقل حرفيّاً ولا تُعاد صياغتها: الرسالة التي يكتبها GitHub هي الدليل، وإعادةُ
    صياغتها تُدخل قراءتنا محلّ ما قاله الريموت فعلاً.
    """
    rules: list[str] = []
    for line in output.splitlines():
        match = _RULE_LINE.match(line)
        if match is None:
            continue
        rule = match.group("rule")
        if rule not in rules:
            rules.append(rule)
    return rules


def main(argv: list[str] | None = None) -> int:
    """يقرأ مخرَج الدفع من ملفٍّ أو من المدخل القياسي ويطبع التصنيف ثمّ القواعد."""
    args = sys.argv[1:] if argv is None else argv
    if args:
        with open(args[0], encoding="utf-8", errors="replace") as handle:
            output = handle.read()
    else:
        output = sys.stdin.read()

    print(classify(output))
    for rule in extract_rules(output):
        print(rule)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
