#!/usr/bin/env python3
"""يمنع التزام الأسرار في الشجرة المُتتبَّعة — القاعدة المكتوبة تصير مفروضة (ISS-141).

**لماذا هذه البوّابة موجودة:**

في 2026-07-30 كشف مسحٌ أمني ختامي أن الشجرة المُتتبَّعة تحمل **كلمة سرّ Supabase
الإنتاجية** داخل ``DATABASE_URL`` كامل (في ملفَّي سكربت/اختبار، وأحدهما كان **يطبعها**
على stdout)، ومفتاح Tavily داخل أرشيف التوثيق. المنصّة تخدم 800,000+ طالباً وقاعدة
البيانات هي مخزن حالة التعلّم كلّه.

نُظِّفت الشجرة في ``d3fa566``، لكن البلاغ سجّل بندًا رابعاً **لم يُنفَّذ**: «فحص أنماط
أسرار على الملفّات المُتتبَّعة ضمن guardrails — القاعدة القائمة (الأسرار من البيئة
حصراً) **مكتوبة ولا تُفرَض آلياً**، وهذا بالضبط صنف العطب الذي عالجه D-188 في
التوثيق: قاعدةٌ بلا بوّابة تنحرف بصمت.» هذه هي تلك البوّابة.

**ما لا تفعله:** لا تُبطِل تسريباً وقع. القيم تبقى في **تاريخ git**، والإغلاق يتطلّب
**تدوير المفاتيح** لدى مُصدِريها. البوّابة تمنع التسريب **القادم** فقط.

**الدَّين المُجمَّد فارغ ويتقلّص فقط** — الشجرة نظيفة اليوم، فتبقى كذلك.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: أنماط الأسرار الحقيقية. كل نمط يستهدف **شكل المفتاح** لا اسم المتغيّر — فالاسم
#: وحده (``OPENROUTER_API_KEY=``) مشروع في المثال والوثيقة، والقيمة هي التسريب.
SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"sk-or-v1-(?P<secret>[A-Za-z0-9]{32,})", "مفتاح OpenRouter حقيقي"),
    (r"tvly-(?:dev-)?(?P<secret>[A-Za-z0-9]{16,})", "مفتاح Tavily حقيقي"),
    (
        r"postgres(?:ql)?://[A-Za-z0-9._%-]+:(?P<secret>[^@\s:/]{8,})@(?P<host>[A-Za-z0-9.-]+)",
        "رابط قاعدة بيانات يحمل كلمة سرّ",
    ),
    (
        r"(?P<secret>eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})",
        "توكن JWT مُوقَّع",
    ),
    (r"sk-(?:proj-)?(?P<secret>[A-Za-z0-9]{40,})", "مفتاح OpenAI حقيقي"),
    (r"ghp_(?P<secret>[A-Za-z0-9]{30,})", "توكن GitHub شخصي"),
)

#: كلمات تدلّ على **قالب** لا سرّ. بوّابةٌ تصرخ على `ghp_xxxxxxxx` تُعطَّل بعد أسبوع،
#: وبوّابةٌ مُعطَّلة أسوأ من غيابها — فالنائب يُستبعَد صراحةً.
_PLACEHOLDER_TOKENS: tuple[str, ...] = (
    "xxx",
    "password",
    "passwd",
    "your",
    "changeme",
    "change_me",
    "example",
    "placeholder",
    "redacted",
    "dummy",
    "fake",
    "sample",
    "abcdef",
    "123456",
    "project-ref",
    "<",
    "{",
    "$",
    "%s",
)


#: مُضيفات وهمية: رابطٌ إليها لا يصل إلى نظامٍ حقيقي، فكلمة سرّه ليست سرّاً.
_PLACEHOLDER_HOSTS = frozenset({"host", "localhost", "db", "postgres", "127.0.0.1", "example.com"})


def _is_placeholder(value: str, host: str = "") -> bool:
    """هل القيمة قالبٌ توضيحي لا سرّاً حقيقياً؟"""
    if host and host.lower() in _PLACEHOLDER_HOSTS:
        return True
    lowered = value.lower()
    if any(token in lowered for token in _PLACEHOLDER_TOKENS):
        return True
    if any(token in host.lower() for token in _PLACEHOLDER_TOKENS):
        return True
    # سلسلة من حرفٍ واحد مكرَّر (xxxxxxxx / 00000000).
    if len(set(lowered)) <= 2:
        return True
    # قوالب الوثائق تُكتب بأحرفٍ كبيرة كاملة (PASSWORD, YOUR_TOKEN).
    if value.isupper():
        return True
    # سرٌّ حقيقي يخلط الأرقام والحروف؛ كلمةٌ خالصة («pass%40word») قالبُ اختبار.
    return not (any(c.isdigit() for c in value) and any(c.isalpha() for c in value))


#: امتدادات نصّية تُفحَص. الثنائيات (PDF/صور) خارج النطاق — لا تُقرأ أصلاً.
TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".md",
        ".yml",
        ".yaml",
        ".json",
        ".sh",
        ".env",
        ".txt",
        ".toml",
        ".ini",
        ".cfg",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".sql",
        ".example",
        ".mjs",
    }
)

#: ملفّات يُسمح لها (مؤقتاً) بمطابقة نمطٍ ما. **فارغ — ويتقلّص فقط.**
FROZEN_DEBT: frozenset[str] = frozenset()

#: هذا الملفّ نفسه يحمل الأنماط، لا الأسرار.
SELF = "scripts/fitness/check_no_committed_secrets.py"


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    compiled = [(re.compile(pattern), label) for pattern, label in SECRET_PATTERNS]
    errors: list[str] = []
    hit_files: set[str] = set()

    for rel in _tracked_files():
        if rel == SELF:
            continue
        path = REPO_ROOT / rel
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:  # pragma: no cover
            continue
        for regex, label in compiled:
            match = next(
                (
                    found
                    for found in regex.finditer(text)
                    if not _is_placeholder(
                        found.group("secret"),
                        (found.groupdict().get("host") or ""),
                    )
                ),
                None,
            )
            if match is None:
                continue
            hit_files.add(rel)
            if rel in FROZEN_DEBT:
                continue
            line_no = text[: match.start()].count("\n") + 1
            errors.append(
                f"❌ {rel}:{line_no}: {label} مُلتزَم في الشجرة.\n"
                f"   الأسرار من **البيئة حصراً** (CLAUDE.md §6.7.ز). انقل القيمة إلى\n"
                f"   `.devcontainer/secrets.env` (git-ignored) أو متغيّر بيئة، ثم **دوِّر\n"
                f"   المفتاح** — الإزالة من الشجرة لا تُبطِل التسريب (ISS-141)."
            )

    for rel in sorted(FROZEN_DEBT - hit_files):
        errors.append(f"❌ {rel} نظيف الآن — احذفه من FROZEN_DEBT (الدَّين يتقلّص فقط).")

    if errors:
        print("\n".join(errors))
        return 1
    print("✅ no committed secrets: الشجرة المُتتبَّعة خالية من أنماط الأسرار المعروفة.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
