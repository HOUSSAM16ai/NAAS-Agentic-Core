#!/usr/bin/env python3
"""حدّ المصداقية يمتدّ إلى ما يُشحَن — لا إلى الوثائق وحدها (D-270 L8).

**لماذا هذه البوّابة موجودة:**

D-227 أقرّ حدّ المصداقية: «عبارةٌ غير قابلة للتفنيد دَينٌ لا طموح — تُصدَّق مرّة، ثمّ
تُكتشَف، ثمّ يسقط معها كلُّ ما هو صحيح». وفُرِض الحدّ على **الوثائق المُعلَنة** في
``check_cognitive_twin`` (D-227) و``check_naas_verification`` (D-267 L10).

والقياس في 2026-08-19 أظهر ثغرتين، كلتاهما من صنفٍ يعرفه هذا المستودع جيّداً:

**① النطاق.** لا بوّابة تقرأ **ملفّات الإعداد**. فعاش في ملفّين يُشحَنان مع كل نسخة:

======================================  ==================================================
الملفّ                                    الادّعاء
======================================  ==================================================
``.github/dependabot.yml``               «SUPERHUMAN» · «LEGENDARY» · «This surpasses
                                         Renovate, Snyk, and WhiteSource in intelligence!»
                                         · «our proprietary AI models»
``.pre-commit-config.yaml``              «Superhuman Edition» · «Standards: Google,
                                         Microsoft, Meta (Facebook), OpenAI level» ·
                                         «CIA/NSA Level»
``.trivy.yml`` · ``Makefile``            «Superhuman Security Scanning» · «Surpassing
                                         enterprise standards» (٧ مواضع في ``Makefile``)
======================================  ==================================================

وهذه ليست زخرفاً: ملفٌّ يَعِد بما لا يفعله يُقرأ حمايةً. و``dependabot.yml`` نفسه كان
يَعِد بتغطيةٍ لمجلّد ``/ai_service`` **غير موجود** — أي أنّ النثر والوظيفة كذبا معاً.

**② المصدر.** قائمة العبارات الممنوعة كانت **ثلاث نسخ في ثلاث بوّابات** لا تتّفق أيّ
اثنتين منها: المشترك بينها **عبارتان فقط** (``صفر أخطاء`` · ``يغيّر البشرية``)، بينما
``guaranteed`` تعيش في واحدة، و``ذاكرة دائمة للطالب`` في أخرى، وصيغُ «دقّة ١٠٠» الأربع
موزّعةٌ بإملاءاتٍ مختلفة. وهذا **نفس صنف ISS-139** (ثلاث قوائم لنيّةٍ واحدة تتفرّق) —
لكنّه هذه المرّة **داخل الفوارض نفسها**. فكتابة قائمةٍ رابعة هنا كانت ستُفاقم العطب.

فالمصدر القانوني الآن ``docs/governance/CREDIBILITY_LIMIT.json``، وهذه البوّابة:

1. تفحص **ملفّات الإعداد المُشحَنة** ضدّ قائمته.
2. تُثبِت أنّ ما تحمله البوّابات الثلاث القائمة **مطابقٌ لما يُصرِّح به السجلّ** — بلا
   تغيير سلوكها. أيّ إدخالٍ يُضاف أو يُحذف من إحداها بلا تحديث السجلّ ⇒ CI أحمر.
   التوحيد الكامل يتطلّب قراراً مكتوباً، لأنّ توسعة قائمةٍ قد تُفشِل وثيقةً قائمة —
   والدَّين المُعلَن أشرف من التوحيد المتسرّع.

**قواعد الصدق التي تحكم البوّابة نفسها:**

* سطرٌ **يَنهى** عن عبارةٍ ليس ادّعاءً بها (درس D-206 — فحصٌ نصّي رفض التعليق الذي
  يشرح الحظر). علامات النهي مُصرَّحة في السجلّ لا مخبوءة في الكود.
* مطابقةٌ داخل معرِّفٍ أطول (``SUPERHUMAN_SIMPLICITY_ARCHITECTURE.md``) ليست ادّعاءً
  (D-206 L4: العلامة القصيرة لا تختبئ داخل كلمة أخرى).
* ⛔ ملفٌّ يتعذّر تحليله **يُبلَّغ عنه انتهاكاً** ولا يُعَدّ نظيفاً (D-208 §6: بوّابةٌ
  لا تقرأ ملفاً لا تُبلِّغ أنه نظيف).

تُشغَّل ضمن وظيفة ``guardrails`` في ``.github/workflows/ci.yml``.
Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
POLICY = REPO_ROOT / "docs" / "governance" / "CREDIBILITY_LIMIT.json"
GATE_HOME = REPO_ROOT / "scripts" / "fitness"

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _pass(msg: str) -> None:
    print(f"✅ {msg}")


# ──────────────────────────────────────────────────────────────────────────────
# ① نطاق المسح — مُعلَنٌ في السجلّ لا مُكتشَف هنا (نمط GATE_HOMES في D-266)
# ──────────────────────────────────────────────────────────────────────────────
def _files_in_directories(directories: tuple[str, ...], suffixes: tuple[str, ...]) -> list[Path]:
    """ملفّات المجلّدات المُعلَنة — ومجلّدٌ غير موجود انتهاكٌ لا تجاهُل."""
    found: list[Path] = []
    for directory in directories:
        root = REPO_ROOT / directory
        if not root.is_dir():
            _fail(f"`config_scopes.directories` يسمّي مجلّداً غير موجود: {directory}")
            continue
        found += [p for p in root.rglob("*") if p.is_file() and p.suffix in suffixes]
    return found


def _scoped_files(policy: dict) -> list[Path]:
    scopes = policy.get("config_scopes", {})
    skip = tuple(scopes.get("skip_fragments", ()))
    found = _files_in_directories(
        tuple(scopes.get("directories", ())), tuple(scopes.get("directory_suffixes", ()))
    )
    for pattern in scopes.get("root_globs", ()):
        found += [p for p in REPO_ROOT.glob(pattern) if p.is_file()]
    unique = sorted({p.resolve() for p in found})
    return [p for p in unique if not any(s in str(p.relative_to(REPO_ROOT)) for s in skip)]


#: نافذة النهي: سطرٌ ± سطر.
#:
#: ⚠️ اكتُشِف بتشغيل البوّابة على المستودع لا بالتحليل: `ci.yml` يشرح حظر D-227 على
#: **سطرين** — الأوّل يسرد العبارات (`"100% accuracy", "zero`) والثاني يحمل الفعل
#: (`errors" ... are banned in published docs`). ففحصُ السطر وحده رفض الشرحَ الذي
#: يُعلن الحظر — وهو حرفياً درس D-206 الذي جاءت هذه القاعدة منه، متكرّراً على نطاقٍ
#: أوسع بسطرٍ واحد. المقايضة مُعلَنة: ادّعاءٌ ملاصقٌ لسطر نهيٍ يُعفى.
_PROHIBITION_WINDOW = 1


def _is_prohibition_context(lines: list[str], index: int, markers: tuple[str, ...]) -> bool:
    """هل يقع السطر داخل نصٍّ يَنهى عن العبارة بدل أن يدّعيها؟"""
    lo = max(0, index - _PROHIBITION_WINDOW)
    hi = min(len(lines), index + _PROHIBITION_WINDOW + 1)
    context = "\n".join(lines[lo:hi])
    return any(marker in context for marker in markers)


def _inside_identifier(text: str, start: int, end: int) -> bool:
    """مطابقةٌ ملتصقةٌ بـ`_` أو داخل معرِّفٍ صارخ (`SUPERHUMAN_X.md`) ليست ادّعاءً."""
    before = text[start - 1] if start else ""
    after = text[end] if end < len(text) else ""
    return before == "_" or after == "_"


def _violations_in(
    text: str, rel: str, compiled: list[tuple[str, re.Pattern[str]]], markers: tuple[str, ...]
) -> list[str]:
    """ادّعاءات ملفٍّ واحد، بعد استثناء سطور النهي والمطابقات داخل معرِّف."""
    lines = text.splitlines()
    found: list[str] = []
    for claim_id, pattern in compiled:
        for match in pattern.finditer(text):
            index = text[: match.start()].count("\n")
            if _is_prohibition_context(lines, index, markers) or _inside_identifier(
                text, match.start(), match.end()
            ):
                continue
            found.append(f"{rel}:{index + 1} [{claim_id}] {match.group(0)[:48]!r}")
    return found


def _read_scoped(files: list[Path]) -> tuple[dict[str, str], list[str]]:
    """نصوص الملفّات المقروءة، ومعها ما تعذّرت قراءته — لا يُبتلَع الفشل."""
    texts: dict[str, str] = {}
    unreadable: list[str] = []
    for path in files:
        rel = str(path.relative_to(REPO_ROOT))
        try:
            texts[rel] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            # ⛔ لا `except: continue` — ملفٌّ لم يُقرأ ليس ملفّاً نظيفاً.
            unreadable.append(f"{rel}: {exc}")
    return texts, unreadable


def _scan_texts(texts: dict[str, str], policy: dict) -> list[str]:
    """ادّعاءات كل الملفّات المقروءة، بترتيبٍ حتمي."""
    compiled = [(claim["id"], re.compile(claim["pattern"])) for claim in policy["claims"]]
    markers = tuple(policy.get("prohibition_markers", ()))
    return [v for rel, text in texts.items() for v in _violations_in(text, rel, compiled, markers)]


def _report_scan(violations: list[str], unreadable: list[str], scanned: int) -> None:
    """⛔ ملفٌّ تعذّرت قراءته لا يُشهَد له بالنظافة (D-208 §6)."""
    if unreadable:
        _fail(f"ملفّات إعدادٍ تعذّرت قراءتها — لا تُعَدّ نظيفة (D-208 §6): {unreadable}")
    if violations:
        _fail(
            "ادّعاءات غير قابلة للتفنيد في ملفّاتٍ تُشحَن مع المستودع "
            f"({len(violations)}): {violations[:10]}"
        )
    elif not unreadable:
        _pass(f"حدّ المصداقية سليم عبر {scanned} ملفّ إعدادٍ مُشحَن")


def _scan_configs(policy: dict) -> None:
    if not policy.get("claims"):
        _fail("`claims` فارغة — سياسةٌ بلا محتوى تُقرأ حمايةً")
        return
    files = _scoped_files(policy)
    if not files:
        _fail("نطاق المسح لم يُطابِق أيّ ملفّ — نطاقٌ خاطئ يُقرأ نجاحاً")
        return
    texts, unreadable = _read_scoped(files)
    _report_scan(_scan_texts(texts, policy), unreadable, len(files))


# ──────────────────────────────────────────────────────────────────────────────
# ② تكافؤ القوائم المرآة — بلا تغيير سلوك أيّ بوّابة قائمة (نمط D-185)
# ──────────────────────────────────────────────────────────────────────────────
def _assigned_names(node: ast.stmt) -> list[str]:
    """أسماء ما يُسنَد إليه في عبارةٍ واحدة — `Assign` أو `AnnAssign`."""
    if isinstance(node, ast.Assign):
        targets: list[ast.expr] = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    else:
        return []
    return [t.id for t in targets if isinstance(t, ast.Name)]


def _constant_entries(value: ast.expr | None) -> list[str]:
    """مفاتيح dict أو عناصر tuple/list — نصوصاً حرفية فقط."""
    if isinstance(value, ast.Dict):
        return [str(k.value) for k in value.keys if isinstance(k, ast.Constant)]
    if isinstance(value, ast.Tuple | ast.List):
        return [e.value for e in value.elts if isinstance(e, ast.Constant)]
    return []


def _literal_entries(module: ast.Module, symbol: str) -> list[str] | None:
    """إدخالات إسنادٍ على مستوى الوحدة. `None` تعني «الرمز غير موجود»."""
    for node in module.body:
        if symbol in _assigned_names(node):
            return _constant_entries(getattr(node, "value", None))
    return None


def _mirror_drift(gate_name: str, spec: dict) -> str | None:
    """وصفُ التفرّق بين قائمة البوّابة والسجلّ — أو `None` إن تطابقا."""
    path = GATE_HOME / gate_name
    if not path.is_file():
        _fail(f"`mirrored_gate_lists` يسمّي بوّابة غير موجودة: {gate_name}")
        return None
    try:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        # ⛔ نفس القاعدة: بوّابة لم تُقرأ لا يُشهَد لها بالتطابق (D-208 §6).
        _fail(f"تعذّر تحليل {gate_name} — لا يُشهَد لها بالتكافؤ: {exc}")
        return None

    symbol = str(spec.get("symbol", ""))
    actual = _literal_entries(module, symbol)
    if actual is None:
        _fail(f"{gate_name}: الرمز `{symbol}` غير موجود — السجلّ يصف بوّابةً أخرى")
        return None

    declared = list(spec.get("entries", []))
    if actual == declared:
        return None
    added = sorted(set(actual) - set(declared))
    removed = sorted(set(declared) - set(actual))
    return f"{gate_name}: أُضيف {added} · حُذف {removed}"


def _check_mirrors(policy: dict) -> None:
    mirrored = policy.get("mirrored_gate_lists", {}).get("gates", {})
    if not mirrored:
        _fail("`mirrored_gate_lists.gates` فارغ — تكافؤٌ مُعلَن بلا مضمون")
        return

    drift = [d for name, spec in sorted(mirrored.items()) if (d := _mirror_drift(name, spec))]
    if drift:
        _fail(
            "تفرّقٌ صامت بين قوائم البوّابات والسجلّ القانوني — حدِّث "
            f"docs/governance/CREDIBILITY_LIMIT.json في نفس الـPR: {drift}"
        )
        return
    total = sum(len(s.get("entries", [])) for s in mirrored.values())
    _pass(f"تكافؤ القوائم المرآة: {len(mirrored)} بوّابة · {total} إدخالاً مُثبَّتاً")


def main() -> int:
    if not POLICY.is_file():
        print(f"❌ سياسة حدّ المصداقية مفقودة: {POLICY.relative_to(REPO_ROOT)}")
        return 1
    try:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ `CREDIBILITY_LIMIT.json` ليس JSON صالحاً: {exc}")
        return 1

    _scan_configs(policy)
    _check_mirrors(policy)

    if _FAILURES:
        print(f"\n❌ حدّ المصداقية (D-270 L8): {len(_FAILURES)} انتهاكاً")
        return 1
    print("\n✅ حدّ المصداقية (D-270 L8): ما يُشحَن يقول ما يفعله فقط.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
