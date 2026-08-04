"""يفرض تماسك الذاكرة المؤسسية: الفهرس يطابق الواقع، والسجلّات مرتَّبة، والدستور عقدٌ لا موسوعة.

**لماذا هذه البوّابة موجودة (D-188 · 2026-07-29):**

بين 2026-05 و2026-07 انحرفت الذاكرة عن نفسها بصمت، ولم تلاحظ ذلك أيُّ بوّابة:

- ``.memory/README.md`` — الفهرس السيادي — كان يعلن ``D-001→D-184`` و``ISS-001→ISS-137``
  بينما الواقع ``D-187`` و``ISS-139``.
- ``decisions.md`` كان يحمل ``D-185`` **بعد** ``D-180`` (خرق ترتيب «الأحدث أولاً»)، ومثله
  ``ISS-138`` في ``issues.md`` — فقارئُ الرأس يظنّ أنه رأى الأحدث وقد فاته قرارٌ كامل.
- ``CLAUDE.md`` بلغ 1,127 سطراً وحمل جدول حقيقة مؤرَّخاً بـ2026-05-09 يناقض
  ``runtime_truth.md`` (2026-07-28).
- ``.runtime/truth_table.lock.json`` بقي مولَّداً على فرعٍ قديم وتاريخٍ أقدم من آخر قرار —
  وقاعدة CLAUDE.md نفسها تقول «تقادم القفل هو finding».

``doc-integrity`` كان يفحص **الوجود** (هل الملف موجود وغير فارغ) لا **التماسك**. هذه البوّابة
تسدّ ذلك: الانحراف يصير فشلاً في CI لا اكتشافاً بعد شهرين.

**قاعدة الـratchet:** أرقام الدَّين المُجمَّدة أدناه **تتقلّص فقط** — رفعُها ممنوع (سابقة
D-105 «قوائم deselect تتقلّص فقط» وD-187 ``_FROZEN_DEBT``). التاريخ العميق للسجلّات مرتَّب
تصاعديًّا في ذيلها لأسبابٍ تاريخية؛ نحرس **النافذة الحديثة** ونمنع تضخّم الباقي.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
MEMORY_README = REPO_ROOT / ".memory/README.md"
DECISIONS = REPO_ROOT / ".memory/decisions.md"
ISSUES = REPO_ROOT / ".memory/issues.md"
TRUTH_LOCK = REPO_ROOT / ".runtime/truth_table.lock.json"

# ── الدَّين المُجمَّد (يتقلّص فقط — ممنوع رفع أيّ رقم) ────────────────────────────
# سقف أسطر الدستور: القيمة المقيسة بعد جراحة D-188 (1,127 → 949). كل تقليص لاحق يُخفّض
# هذا الرقم. البوّابة أوقفت كاتبها فعلاً أثناء D-189 حين حاول إضافة قاعدة تتجاوز السقف،
# فكان الحلّ حذف **جدولَي حالة** مكرَّرين من الدستور لا رفع الرقم — وهذا هو المقصود.
#
# ── D-209: رُفِع مرّةً 887 → 910، وهذا هو التمييز الذي يجب ألّا يضيع ─────────────
# غرضُ هذا المِسنَن هو منع **التضخّم السردي**: «Known fix applied <تاريخ>»، وجداول الحالة
# المكرَّرة، والموسوعية التي تتقادم ثمّ تكذب (D-188). ولم يكن غرضه قطّ منع **قانونٍ دائمٍ
# جديد** — ولو كان كذلك لكان الدستور مُغلَقاً أمام D-192 وD-206 وD-207 وD-208 نفسها، وكلّها
# أضافت إلى §0. الفرق عمليّ لا بلاغيّ:
#   • تضخّمٌ سردي  ⇒ يُنقَل إلى `.memory/` أو `docs/archive/` ويُترك مؤشّر. لا يُرفَع السقف.
#   • قانونٌ دائم جديد ⇒ يجوز رفع السقف **مرّةً** بقرارٍ مكتوب في `.memory/decisions.md`
#     يُسمّي السبب، فيبقى الرفع مكلفاً ومرئياً بدل أن يكون صامتاً (D-209 · الطبقة 9:
#     «رفعُ مِسنَنٍ مُعلَن قرارُ إنسان»).
# وبعد الرفع يعود المِسنَن «يتقلّص فقط» من القيمة الجديدة. ⛔ رفعٌ بلا إدخالٍ في
# `decisions.md` هو بالضبط الصمت الذي تحرسه هذه البوّابة.
#
# ── D-210: رُفِع مرّةً 910 → 943 لقانونٍ دائمٍ جديد (§0.10) ─────────────────────
# السبب المنطوق: طبقة **القيمة والإيراد** لم تكن ممثَّلة في العقد أصلاً — لا فجوة وهمٍ
# كمخرَج، ولا حدٌّ يمنع عرض قياسٍ غير ناضج، ولا قاعدة «`TIMEOUT` ليس نجاحاً»، ولا حدٌّ
# أخلاقي لما يراه الوليّ. وهي قوانين تحكم ما **يُعرَض على قاصرٍ ووليّه**، فمكانها العقد
# لا ملحقٌ يُقرأ اختيارياً. والسرد كلّه (12 طبقة · 14 وحدة · 32 مرجعاً) ذهب إلى
# `docs/VALUE_DOCTRINE.md` و`docs/REVENUE_ENGINE_SPEC.md` وحالتُه إلى
# `.memory/revenue_engine_truth.md` — أي أن الدستور أخذ **القاعدة** وحدها، وهو التمييز
# الذي يحرسه هذا المِسنَن. القرار مكتوب في `.memory/decisions.md` (D-210).
#
# ── D-224: رُفِع ثانيةً 943 → 964 (§0.11 — محرّك التنفيذ المعرفي) ────────────────
# ⚠️ **رفعان في جلسةٍ واحدة، وهذا بذاته إشارةٌ تستحقّ الانتباه** — فالمِسنَن وُجد ليجعل
# النموّ مكلفاً ومرئياً، ومرئيّته تعني أن يُقال هذا صراحةً لا أن يمرّ. ما يبرّر الثاني:
# §0.11 يحمل **قفلاً أمنياً** (ممنوع توصيل نموذجٍ لغوي بمُنفِّذ الصندوق قبل M1→M4)، وقفلٌ
# أمني يحكم منصّةً تخدم قاصرين مكانُه العقد لا ملحقٌ يُقرأ اختيارياً. والسرد كلّه (١٣ طبقة
# + ٤ آفاق سوق) ذهب إلى `docs/architecture/COGNITIVE_EXECUTION_ENGINE.md` وحالتُه إلى
# `.memory/cognitive_execution_truth.md`. القرار في `.memory/decisions.md` (D-224).
# ⛔ رفعٌ ثالث في هذه الجلسة يتطلّب سبباً أقوى من «قانونٌ جديد» — أو نقلاً إلى `.memory/`.
#
# ── D-226: رُفِع ثالثةً 964 → 986 (§0.12 — التوأم الرقمي المعرفي) ────────────────
# ⛔ **ثلاثة رفعات في جلسةٍ واحدة، وقد قلتُ في D-224 إن الثالث يتطلّب سبباً أقوى.** فهذا
# هو السبب، ويُحكَم عليه لا يُقبَل مجاملةً: §0.12 وُلد من **عطبٍ مقيس أُصلح في نفس الـPR**
# لا من عقيدةٍ مُضافة — `diagnose_root` كان يقرأ رسماً من اثنين، فبقيت ٢٦ حافّة شرطٍ مسبق
# غير مرئية والتقاطع صفر. وقانونٌ يمنع عودة عطبٍ حيّ ليس تضخّماً سردياً.
# ويحمل §0.12 أيضاً **حدّ المصداقية** (D-227) الذي يحكم ما يُقال لأولياء قاصرين.
# ⛔ **ولا رفع رابع في هذه الجلسة.** ما بعده يُنقَل إلى `.memory/` أو يُختصَر — والسقف
# يعود «يتقلّص فقط» من هنا. القرار في `.memory/decisions.md` (D-226).
CLAUDE_MD_MAX_LINES = 986
# أزواج التواريخ غير المرتَّبة في ذيل السجلّات التاريخي (قبل النافذة الحديثة).
FROZEN_ORDER_DEBT = {"decisions.md": 52, "issues.md": 46}
# حجم النافذة الحديثة التي يجب أن تكون مرتَّبة ترتيباً صارماً.
RECENT_WINDOW = 20

_DATE = re.compile(r"(20\d\d-\d\d-\d\d)")
_DECISION_ID = re.compile(r"\bD-(\d{3})\b")
_ISSUE_ID = re.compile(r"\bISS-(\d{3})\b")


def _dated_headings(path: Path) -> list[tuple[str, str]]:
    """يُرجع عناوين المستوى الثاني الحاملة تاريخاً، بترتيب ورودها في الملف."""
    out: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("## "):
            continue
        match = _DATE.search(line)
        if match:
            out.append((line, match.group(1)))
    return out


def _max_id(path: Path, pattern: re.Pattern[str]) -> int:
    """يستخرج أكبر مُعرَّف رقمي مذكور في الملف (D-### أو ISS-###)."""
    text = path.read_text(encoding="utf-8")
    values = [int(m) for m in pattern.findall(text)]
    return max(values) if values else 0


def _out_of_order_count(dated: list[tuple[str, str]]) -> int:
    """يعدّ الأزواج المتتالية التي يكون فيها الأحدث بعد الأقدم (خرق «الأحدث أولاً»)."""
    return sum(1 for i in range(1, len(dated)) if dated[i][1] > dated[i - 1][1])


def _index_row(row_key: str) -> str | None:
    """يلتقط صفّ الجدول السيادي الخاص بملفٍ بعينه في ``.memory/README.md``.

    المطابقة مقصورة على **الصفّ** لا على الملف كلّه: ذِكرُ المُعرَّف في أي فقرة أخرى
    (نصّ قاعدة، سطر شرح) لا يُثبت أن الفهرس نفسه مُحدَّث — وهذا بالضبط ما كشفته
    التجربة السلبية أثناء بناء البوّابة.
    """
    needle = f"`{row_key}`"
    for line in MEMORY_README.read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and needle in line:
            return line
    return None


def _check_index_freshness(failures: list[str]) -> None:
    """يتأكد أن **صفّ الفهرس السيادي** يذكر أحدث قرار وأحدث كارثة فعلاً."""
    checks = (
        ("decisions.md", DECISIONS, _DECISION_ID, "D", "قرار"),
        ("issues.md", ISSUES, _ISSUE_ID, "ISS", "كارثة"),
    )
    for row_key, path, pattern, prefix, noun in checks:
        row = _index_row(row_key)
        if row is None:
            failures.append(
                f".memory/README.md: لا صفّ في الجدول السيادي لـ `{row_key}` — "
                "الفهرس فقد أحد سجلّاته الملزِمة."
            )
            continue
        newest = _max_id(path, pattern)
        token = f"{prefix}-{newest:03d}"
        if token not in row:
            failures.append(
                f".memory/README.md: صفّ `{row_key}` لا يذكر أحدث {noun} {token} "
                "(الفهرس السيادي متقادم — هذا هو عطب D-188 بعينه)."
            )


def _check_recent_ordering(failures: list[str]) -> None:
    """يفرض ترتيب «الأحدث أولاً» على النافذة الحديثة، ويمنع تضخّم دَين الذيل."""
    for path in (DECISIONS, ISSUES):
        dated = _dated_headings(path)
        window = dated[:RECENT_WINDOW]
        for i in range(1, len(window)):
            if window[i][1] > window[i - 1][1]:
                failures.append(
                    f"{path.name}: خرق ترتيب «الأحدث أولاً» في النافذة الحديثة — "
                    f"{window[i - 1][1]} يليه {window[i][1]} عند «{window[i][0][:70]}». "
                    "أدرِج الإدخال الجديد في رأس الملف، لا في وسطه."
                )

        actual = _out_of_order_count(dated)
        frozen = FROZEN_ORDER_DEBT[path.name]
        if actual > frozen:
            failures.append(
                f"{path.name}: دَين الترتيب التاريخي ارتفع {frozen} → {actual}. "
                "القاعدة: يتقلّص فقط (D-105)."
            )


def _check_constitution_size(failures: list[str]) -> None:
    """يمنع عودة الدستور موسوعةً — السقف ratchet ينزل ولا يرتفع."""
    line_count = len(CLAUDE_MD.read_text(encoding="utf-8").splitlines())
    if line_count > CLAUDE_MD_MAX_LINES:
        failures.append(
            f"CLAUDE.md صار {line_count} سطراً > السقف {CLAUDE_MD_MAX_LINES}. "
            "الدستور عقدٌ لا موسوعة (DOC-DEBT-001 · spec.md §15): انقل السرد إلى "
            ".memory/ أو docs/archive/ بدل رفع السقف."
        )


def _check_truth_lock_freshness(failures: list[str]) -> None:
    """يتأكد أن قفل جدول الحقيقة ليس أقدم من آخر قرار مُسجَّل."""
    lock = json.loads(TRUTH_LOCK.read_text(encoding="utf-8"))
    generated = lock.get("generated_at_utc", "")
    match = _DATE.search(generated)
    if not match:
        failures.append(f"{TRUTH_LOCK.name}: لا يحمل generated_at_utc صالحاً.")
        return

    lock_date = date.fromisoformat(match.group(1))
    dated = _dated_headings(DECISIONS)
    if not dated:
        return
    newest_decision_date = date.fromisoformat(max(d for _, d in dated[:RECENT_WINDOW]))
    if lock_date < newest_decision_date:
        failures.append(
            f"{TRUTH_LOCK.name} مولَّد في {lock_date} بينما آخر قرار في {newest_decision_date}. "
            "شغّل `python scripts/runtime_truth.py --update` — تقادم القفل finding (CLAUDE.md §0)."
        )


def main() -> int:
    """يشغّل فحوص تماسك الذاكرة ويرجع 0 عند السلامة و1 عند أي انحراف."""
    failures: list[str] = []

    _check_index_freshness(failures)
    _check_recent_ordering(failures)
    _check_constitution_size(failures)
    _check_truth_lock_freshness(failures)

    if failures:
        print("❌ تماسك الذاكرة مخروق (D-188):")
        for failure in failures:
            print(f"   • {failure}")
        return 1

    print(
        "✅ memory coherence: index fresh, recent order strict, constitution bounded, lock current."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
