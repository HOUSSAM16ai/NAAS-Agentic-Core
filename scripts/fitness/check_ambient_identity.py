#!/usr/bin/env python3
"""بوّابة دستور الهوية المعرفية المحيطة — D-269 / ISS-192 · ISS-193.

## لماذا هذه البوّابة موجودة

مفتاحُ طرفٍ ثالث (Honcho) دخل المستودع، وهو يخدم **نمذجة المستخدم** — أي أنّه يلامس
§0.12 (التوأم المعرفي) و§0.14 (معمارية الذاكرة) في صميمهما. والمنصّة تخدم **قاصرين**.

فالخطر ليس أن يُوصَل خطأً، بل أن يُوصَل **بالتدريج وبلا قرار**: سطرٌ يرسل مُعرَّفاً،
ثمّ سطرٌ يرسل مقتطفاً «للسياق»، ثمّ يكتشف أحدهم بعد أشهرٍ أنّ محادثات الطلبة تعبر إلى
طرفٍ ثالث. وهذا بالضبط شكلُ العطب الذي قِيس مرّتين في هذا المستودع: ISS-146 (نصُّ نظامٍ
كُتب بدور الطالب **٢٨ مرّة** قبل أن يلاحظه أحد) وISS-145 (قدرةٌ تدهورت من 36.6٪ إلى
3.4٪ بلا قرار، لأنّ لا شيء كان يحرسها).

ولذلك القانون هنا مفروضٌ **بالبناء** لا بالنيّة، وهذه البوّابة هي الفارض.

## ما تفرضه

1. **فصل القانون عن الحالة** (D-188/D-209): وثيقة القانون لا تحمل رمزَ حالةٍ من
   سُلَّم §6.6؛ ووثيقة الحالة كلّ صفٍّ فيها بحالةٍ صالحة ودليلٍ **موجود** وفجوةٍ
   **غير فارغة** وشرط ترقية.
2. **`SEAM`/`ABSENT` في الاتجاهين** (قاعدة D-210): وحدةٌ مُصنَّفة كذلك **ولها كود**
   ⇒ أحمر. كودٌ حيٌّ بلا حارسٍ ولا اختبار أسوأ من الغياب المُعلَن.
3. **جدار الحجب بنيويّ** (L2 · يمدّد D-196): وحدة الطبقة لا تلمس `content` ولا أيّ
   قارئ رسائل. AST لا نصّ — النسخة النصّية كانت سترفض التعليق الذي يشرح المنع.
4. **صفر تبعيةٍ جديدة** (L8): ⛔ لا `honcho` ولا `honcho-ai` في أيّ ملفّ متطلّبات.
5. **حدّ المصداقية** (L10 · D-227): لا عبارة غير قابلة للتفنيد في وثائق الطبقة.
6. **الفوارض المُستشهَد بها موجودة** (ISS-148): بوّابةٌ تُذكَر ولا توجد ⇒ أحمر.
7. **لا حذف صامت**: عدد صفوف وثيقة الحالة مُصرَّح — من يحذف وحدةً يُحدِّث الرقم هنا.

**صدق التحليل (D-208):** ملفٌّ يتعذّر تحليله يُبلَّغ عنه انتهاكاً — ⛔ لا
`except SyntaxError: return []`.

**لا تُستورد من `app/`.** Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

LAW_DOCS: tuple[str, ...] = (
    ".memory/ambient_identity_constitution.md",
    "docs/architecture/AMBIENT_COGNITIVE_IDENTITY.md",
)
STATE_DOC = ".memory/ambient_identity_truth.md"
ADR_DOC = "docs/adr/ADR-010-deepseek-harness-adoption.md"
SEAMS_DOC = "docs/architecture/EXTENSION_SEAMS.md"

#: حزمة الطبقة. كلّ ما تحته يخضع لجدار الحجب.
LAYER_PACKAGE = REPO_ROOT / "shared" / "ambient_memory"

#: عدد صفوف وثيقة الحالة. مُصرَّحٌ كي يصير **حذفُ صفٍّ بصمت** أحمر: من يحذف وحدةً
#: يجب أن يُحدِّث الرقم هنا، فيصير الحذف قراراً مرئياً لا تسرّباً (نمط
#: `check_research_doctrines`).
EXPECTED_STATE_ROWS = 9

VALID_STATUSES = frozenset({"ACTIVE", "PARTIAL", "DORMANT", "ZOMBIE", "PLANNED", "SEAM", "ABSENT"})
_STATUS_TOKEN = re.compile(r"\b(ACTIVE|PARTIAL|DORMANT|ZOMBIE|PLANNED|SEAM|ABSENT)\b")
_BACKTICKED = re.compile(r"`([^`]+)`")
_GATE_NAME = re.compile(r"\bcheck_[a-z0-9_]+\b")

#: عباراتٌ غير قابلة للتفنيد. حدّ المصداقية (D-227): تُصدَّق مرّة، ثمّ تُكتشَف، ثمّ
#: يسقط معها كلُّ ما هو صحيح — والمنصّة تخدم قاصرين وأولياءَ يقرّرون بناءً على ما نقول.
_UNFALSIFIABLE: tuple[str, ...] = (
    "يقرأ الأفكار",
    "يقرأ أفكار",
    "دقّة ١٠٠",
    "دقة 100",
    "100% دقة",
    "صفر أخطاء",
    "يغيّر البشرية",
    "ذاكرة دائمة للطالب",
    "يفهم الطالب تماماً",
)

#: أسماءٌ تدلّ على قراءة محتوى محادثة. جدار الحجب (L2) يمنع ملامستها من داخل الحزمة.
_CONTENT_NAMES: frozenset[str] = frozenset(
    {"content", "customer_messages", "admin_messages", "message_content", "transcript"}
)

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _ok(msg: str) -> None:
    print(f"✅ {msg}")


def _read(rel: str) -> str | None:
    path = REPO_ROOT / rel
    if not path.is_file():
        _fail(f"ملفٌّ مفقود: {rel} — خريطةٌ تكذب أسوأ من غياب الخريطة (ISS-149).")
        return None
    return path.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 1 — فصل القانون عن الحالة
# ─────────────────────────────────────────────────────────────────────────────
def _check_law_docs() -> None:
    for rel in LAW_DOCS:
        text = _read(rel)
        if text is None:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith(">") or "⛔" in line:
                continue  # ترويسةٌ تشرح المنع، أو سطرٌ يستشهد بالقاعدة
            if "|" not in line:
                continue
            found = _STATUS_TOKEN.findall(line)
            if found:
                _fail(
                    f"{rel}:{line_no}: وثيقة قانونٍ تحمل عمود حالة {sorted(set(found))}.\n"
                    f"   القانون بلا حالة (D-188/D-209) — الحالةُ في {STATE_DOC}، "
                    f"وخريطتان لنظامٍ واحد تعنيان وكيلَين يقرآن بناءَين مختلفين."
                )


def _table_rows(text: str) -> list[tuple[int, list[str]]]:
    rows: list[tuple[int, list[str]]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 5 or not cells[0].isdigit():
            continue
        rows.append((line_no, cells))
    return rows


def _looks_like_path(candidate: str) -> bool:
    return "/" in candidate and not candidate.startswith(("http", "#"))


def _check_state_doc() -> list[tuple[str, str]]:
    """يُعيد (اسم الوحدة، الحالة) لكل صفٍّ — لاستعماله في الفحص العكسي."""
    text = _read(STATE_DOC)
    if text is None:
        return []

    rows = _table_rows(text)
    if len(rows) != EXPECTED_STATE_ROWS:
        _fail(
            f"{STATE_DOC}: عدد الصفوف {len(rows)} والمتوقَّع {EXPECTED_STATE_ROWS}.\n"
            f"   إضافةُ صفٍّ أو حذفه قرارٌ يُعلَن: حدِّث EXPECTED_STATE_ROWS ودوِّن "
            f"السبب في .memory/decisions.md. ⛔ لا حذف صامت."
        )

    units: list[tuple[str, str]] = []
    seen: set[int] = set()
    for line_no, cells in rows:
        number = int(cells[0])
        where = f"{STATE_DOC}:{line_no} (الصفّ {number})"
        if number in seen:
            _fail(f"{where}: رقم صفٍّ مكرَّر — الترقيم مُعرِّف لا زينة.")
        seen.add(number)

        unit, evidence, status, gap = cells[1], cells[2], cells[3], cells[4]
        status_clean = status.strip("`* ")
        if status_clean not in VALID_STATUSES:
            _fail(f"{where}: حالةٌ خارج السُّلَّم: {status!r}. ⛔ لا سُلَّم ثانٍ (§6.6).")
        if not gap.strip():
            _fail(f"{where}: خانةُ الفجوة فارغة — الفراغ يُقرأ نجاحاً (D-206 L11).")
        if len(cells) < 6 or not cells[5].strip():
            _fail(f"{where}: بلا شرط ترقيةٍ منطوق — الطموح يُصنَّف ولا يُكتَم (D-209).")

        for candidate in _BACKTICKED.findall(evidence):
            if _looks_like_path(candidate) and not (REPO_ROOT / candidate).exists():
                _fail(
                    f"{where}: الدليل «{candidate}» غير موجود على القرص.\n"
                    f"   دليلٌ يجب أن يوجد (D-207) — وإلّا فالجدول يشهد بما لم يره."
                )
        units.append((unit, status_clean))
    return units


# ─────────────────────────────────────────────────────────────────────────────
# 2 — `SEAM`/`ABSENT` في الاتجاهين
# ─────────────────────────────────────────────────────────────────────────────
#: (نصٌّ يميّز الوحدة في الجدول، مسارٌ يجب أن **يخلو** من كودٍ حيّ ما دامت غير مُرقّاة)
_ZERO_CODE_UNITS: tuple[tuple[str, str], ...] = (
    ("كتابة إشاراتٍ مجهولة", "shared/ambient_memory/writer.py"),
    ("قراءة النمذجة", "shared/ambient_memory/dialectic.py"),
)


def _check_declared_absence(units: list[tuple[str, str]]) -> None:
    for marker, forbidden_path in _ZERO_CODE_UNITS:
        row = next((row for row in units if marker in row[0]), None)
        if row is None:
            continue
        if row[1] in {"SEAM", "ABSENT", "PLANNED"} and (REPO_ROOT / forbidden_path).exists():
            _fail(
                f"«{marker}» مُصنَّفة {row[1]} بينما {forbidden_path} موجودٌ على القرص.\n"
                f"   ⛔ الغياب يُفحَص في الاتجاهين (قاعدة D-210): كودٌ حيٌّ بلا حارسٍ "
                f"ولا اختبارٍ أسوأ من الغياب المُعلَن. رقِّ الصفَّ أو احذف الكود."
            )


# ─────────────────────────────────────────────────────────────────────────────
# 3 — جدار الحجب بنيويّ
# ─────────────────────────────────────────────────────────────────────────────
def _check_content_wall() -> None:
    if not LAYER_PACKAGE.is_dir():
        _fail(f"حزمة الطبقة مفقودة: {LAYER_PACKAGE.relative_to(REPO_ROOT)}.")
        return

    for path in sorted(LAYER_PACKAGE.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        source = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            _fail(f"{rel}: تعذّر تحليله ({exc.msg}) — بوّابةٌ لا تقرأ ملفاً لا تشهد بنظافته.")
            continue

        for node in ast.walk(tree):
            # `x.content` أو `x["content"]` أو تعريفُ حقلٍ اسمه content
            if isinstance(node, ast.Attribute) and node.attr in _CONTENT_NAMES:
                _fail(_wall_message(rel, node.lineno, node.attr))
            elif isinstance(node, ast.Constant) and node.value in _CONTENT_NAMES:
                _fail(_wall_message(rel, node.lineno, str(node.value)))
            elif isinstance(node, ast.arg) and node.arg in _CONTENT_NAMES:
                _fail(_wall_message(rel, node.lineno, node.arg))
            elif isinstance(node, ast.Name) and node.id in _CONTENT_NAMES:
                _fail(_wall_message(rel, node.lineno, node.id))
            elif isinstance(node, ast.ImportFrom) and node.module and "app." in node.module:
                _fail(f"{rel}:{node.lineno}: `shared/` يستورد من `app` — ممنوع (D-189 البند 5).")


def _wall_message(rel: str, line_no: int, name: str) -> str:
    return (
        f"{rel}:{line_no}: الطبقة تلامس «{name}» — جدار الحجب مخروق (L2).\n"
        f"   ⛔ لا يعبر هذا المسار حرفٌ واحد من نصّ المحادثة. والمنعُ بالنوع لا "
        f"بالمُرشِّح (يمدّد D-196): مُرشِّحٌ يُعدَّل بسطر، ونوعٌ بلا حقلٍ يُراجَع."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4 — صفر تبعيةٍ جديدة
# ─────────────────────────────────────────────────────────────────────────────
_FORBIDDEN_PACKAGES = ("honcho-ai", "honcho_ai")


def _check_no_new_dependency() -> None:
    for path in sorted(REPO_ROOT.glob("requirements*.txt")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            name = line.split("#", 1)[0].strip().lower()
            if not name:
                continue
            if any(pkg in name for pkg in _FORBIDDEN_PACKAGES) or name.startswith("honcho"):
                _fail(
                    f"{path.name}: حزمة «{line.strip()}» ممنوعة (L8).\n"
                    f"   النداء عبر `shared/http_client` — وSDK يبني عميلَه فيقطع سلسلة "
                    f"`X-Correlation-ID` بدل أن يمدّها (D-189)، ويوسّع سطح الهجوم على "
                    f"منصّةٍ تخدم قاصرين."
                )


# ─────────────────────────────────────────────────────────────────────────────
# 5 + 6 — حدّ المصداقية · الفوارض المُستشهَد بها موجودة
# ─────────────────────────────────────────────────────────────────────────────
def _check_credibility_and_gates() -> None:
    gate_dirs = (REPO_ROOT / "scripts" / "fitness", REPO_ROOT / "tools" / "ci")
    on_disk = {
        path.stem
        for directory in gate_dirs
        if directory.is_dir()
        for path in directory.glob("check_*.py")
    }

    for rel in (*LAW_DOCS, STATE_DOC, ADR_DOC):
        text = _read(rel)
        if text is None:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            # سطرٌ يحمل علامة المنع ⛔ هو **حظرُ** العبارة لا ادّعاؤها. بلا هذا
            # الاستثناء ترفض البوّابةُ النصَّ الذي يشرح القاعدة نفسها — وهو عطبٌ
            # وقع حرفياً في `check_no_self_announcement` (D-206 L8) قبل أن يُصحَّح
            # بالانتقال إلى فحصٍ يعي السياق.
            if "⛔" in line:
                continue
            for phrase in _UNFALSIFIABLE:
                if phrase in line:
                    _fail(
                        f"{rel}:{line_no}: عبارةٌ غير قابلة للتفنيد: «{phrase}» — "
                        f"حدّ المصداقية (D-227).\n"
                        f"   تُصدَّق مرّة، ثمّ تُكتشَف، ثمّ يسقط معها كلُّ ما هو صحيح."
                    )
        for gate in sorted(set(_GATE_NAME.findall(text))):
            if gate not in on_disk:
                _fail(f"{rel}: يستشهد بـ«{gate}» وهي غير موجودة على القرص (ISS-148).")


def _check_seam_recorded() -> None:
    text = _read(SEAMS_DOC)
    if text is None:
        return
    if "deepseek-harness" not in text:
        _fail(f"{SEAMS_DOC}: مقعد `deepseek-harness` غير مُسجَّل — تبنٍّ بلا مقعدٍ مُعلَن (ISS-193).")
    if "ADR-010" not in text:
        _fail(f"{SEAMS_DOC}: المقعد لا يُحيل إلى ADR-010 — القرار يُوثَّق أو لا يُعتبَر (D-209).")


def main() -> int:
    _check_law_docs()
    units = _check_state_doc()
    _check_declared_absence(units)
    _check_content_wall()
    _check_no_new_dependency()
    _check_credibility_and_gates()
    _check_seam_recorded()

    if _FAILURES:
        print(f"\n❌ ambient-identity: {len(_FAILURES)} انتهاكاً.")
        return 1

    _ok(f"القانون بلا حالة، والحالة {len(units)} صفّاً بدليلٍ موجودٍ وفجوةٍ منطوقة وشرط ترقية")
    _ok("الغياب المُعلَن مفروضٌ في الاتجاهين — لا كودَ خلف تصنيف `SEAM`/`PLANNED`")
    _ok("⛔ جدار الحجب سليم: لا `content` ولا استيرادَ من `app` داخل الطبقة")
    _ok("صفر تبعيةٍ جديدة · لا عبارة غير قابلة للتفنيد · كل فارضٍ مُستشهَدٍ به موجود")
    print("\n✅ ambient-identity: الطبقة الخامسة تُقرأ ولا تحكم، وتُثبَت بمسبارٍ لا بمفتاح.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
