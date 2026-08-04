#!/usr/bin/env python3
"""بوّابة محرّك التنفيذ المعرفي — الطبقات عقدٌ مفروض، والقفل الأمني آليّ (D-224/D-225).

## لماذا هذه البوّابة موجودة

وثيقةٌ تصف «كيف يصير هذا النظام محرّك تعلّمٍ قابلاً للتحقّق» تتحوّل حتماً إلى كذبٍ مهذَّب
إن لم يحرسها شيء — وقد حدث ذلك مرّتين في هذا المستودع (D-188 · D-209). لكن هنا يوجد خطرٌ
أكبر من انحراف التوثيق، وهو سببُ وجود البند الأخير:

**قفل D-187.** القانون القائم يمنع توصيل أيّ مُخطِّط أو نموذج لغوي بالأدوات قبل استكمال
M1→M4 (عقد قدرات · مسبار حيّ · ميزانيات وسجلّ تدقيق · حوكمة). والصندوق التنفيذي **مبنيّ
بالفعل ويشغّل `python` و`pip` و`git` و`npm`**. فالمسافة بين «قدرة» و«حادثة أمنية» هي
سطرُ استيرادٍ واحد يكتبه وكيلٌ متحمّس بعد أشهر — على منصّةٍ تخدم **قاصرين**.

ولذلك لا يكفي أن يكون القفل نصّاً في وثيقة: كل قانونٍ نثري في هذا المستودع خُرِق مرّةً
على الأقلّ (D-013 هو المثال المُوثَّق). فالقفل هنا **مفروضٌ بـAST**: أيّ وحدة تجمع
استيراد مُنفِّذ الصندوق مع عميل نموذجٍ لغوي تُفشِل CI، ما لم تكن في قائمة إعفاءٍ
**مُصرَّحة بسببها**.

## ما تفرضه

1. **الدليل الملفّي موجود فعلاً** — لا حالة أمام ملفٍّ محذوف.
2. **الحالة من السُّلَّم القانوني** (§6.6) — لا سُلَّم ثانٍ.
3. **لا خانة فجوةٍ فارغة** — الفراغ يُقرأ نجاحاً.
4. **لا حذف صامت** — ثلاث عشرة طبقة وأربعة آفاق، والعدد يُقارَن بالمقروء.
5. **كل بوّابةٍ يُسمّيها القانون موجودة** (أو مُعلَنة مُخطَّطة) — قانونٌ يَعِد بحراسةٍ
   غير قائمة أسوأ من قانونٍ بلا فارض (ISS-149 · F3).
6. **⛔ لا حالات في وثيقة القانون** — خريطتان لنظامٍ واحد أنتجتا ISS-139.
7. **⛔ قفل D-187** — لا نموذج لغوي في وحدةٍ تستورد مُنفِّذ الصندوق.

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_DOC = REPO_ROOT / ".memory/cognitive_execution_truth.md"
LAW_DOC = REPO_ROOT / "docs/architecture/COGNITIVE_EXECUTION_ENGINE.md"
FITNESS_DIR = REPO_ROOT / "scripts/fitness"

VALID_STATUSES = frozenset({"ACTIVE", "PARTIAL", "DORMANT", "ZOMBIE", "PLANNED", "SEAM", "ABSENT"})

#: العدّادات المُعلَنة. تغييرها قرارٌ يُسجَّل، لا رقمٌ يُحرَّر.
EXPECTED_LAYERS = 13
EXPECTED_HORIZONS = 4

_ROW = re.compile(r"^\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$")
_EVIDENCE = re.compile(r"`([^`]+)`")
_GATE_MENTION = re.compile(r"`(check_[a-z0-9_]+)`")
_LAW_SECTION = re.compile(r"^## (\d+)\) (.+)$", re.MULTILINE)

#: بوّاباتٌ **مُخطَّطة** — تُذكَر في القانون لأنها جزءٌ من عقد الطبقة ولم تُبنَ بعد.
#: مفروضةٌ في الاتجاهين: اسمٌ هنا موجودٌ فعلاً ⇒ CI أحمر (وثيقةٌ تُقلّل من حراستها).
_PLANNED_GATES: frozenset[str] = frozenset(
    {
        "check_symbolic_no_timeout_pass",  # D-215
        "check_optimizer_constraints",  # D-218
        "check_agent_self_modification",  # M4
        "check_llm_sandbox_interlock",  # بندٌ داخل هذه البوّابة نفسها (أدناه)
    }
)

# ─────────────────────────────────────────────────────────────────────────────
# قفل D-187 — نموذجٌ لغوي + مُنفِّذ صندوق = ممنوع
# ─────────────────────────────────────────────────────────────────────────────

#: وحداتٌ يعني استيرادُها امتلاكَ قدرة تنفيذٍ فعلية.
_SANDBOX_MARKERS: tuple[str, ...] = (
    "agent_tools.sandbox",
    "run_sandboxed",
)

#: وحداتٌ/أسماء يعني استيرادُها امتلاكَ نموذجٍ لغوي يولّد نصّاً حرّاً.
_LLM_MARKERS: tuple[str, ...] = (
    "get_ai_client",
    "SimpleAIClient",
    "simple_client",
    "ai_gateway",
    "openrouter",
)

#: إعفاءاتٌ مُصرَّحة: المسار ← السبب المنطوق. ⛔ إعفاءٌ بلا سبب مرفوض بنيويّاً
#: (القيمة تُفحَص غير فارغة)، وإعفاءٌ لمسارٍ غير موجود يُفشِل أيضاً — لئلّا تتراكم
#: أذوناتٌ لملفّاتٍ حُذفت.
_INTERLOCK_EXEMPTIONS: dict[str, str] = {}

#: أشجارٌ تُفحَص. `tests/` مُستثناة: اختبارٌ يستورد الاثنين ليُثبت أنهما لا يلتقيان
#: هو الحارس لا الخرق.
_INTERLOCK_ROOTS: tuple[str, ...] = ("app", "microservices", "shared", "scripts")


def _imported_names(tree: ast.AST) -> set[str]:
    """كل الأسماء والوحدات المستورَدة في ملفّ — نصّياً بعد التحليل لا بـgrep."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.add(module)
            for alias in node.names:
                names.add(f"{module}.{alias.name}")
                names.add(alias.name)
    return names


def _check_llm_sandbox_interlock() -> list[str]:
    """⛔ قفل D-187: لا وحدةَ تجمع نموذجاً لغوياً مع مُنفِّذ الصندوق."""
    problems: list[str] = []
    seen_exemptions: set[str] = set()

    for root in _INTERLOCK_ROOTS:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError) as exc:
                # بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ أنه نظيف (D-208).
                problems.append(f"تعذّر تحليل {rel}: {exc} — البوّابة لا تشهد بما لم تقرأ.")
                continue
            names = _imported_names(tree)
            has_sandbox = any(any(m in n for n in names) for m in _SANDBOX_MARKERS)
            if not has_sandbox:
                continue
            has_llm = any(any(m in n for n in names) for m in _LLM_MARKERS)
            if not has_llm:
                continue
            if rel in _INTERLOCK_EXEMPTIONS:
                seen_exemptions.add(rel)
                continue
            problems.append(
                f"⛔ قفل D-187 مخروق في {rel}: الوحدة تستورد مُنفِّذ الصندوق **و** عميل "
                f"نموذجٍ لغوي معاً.\n"
                f"     توصيل مُخطِّط/LLM بالأدوات ممنوع قبل استكمال M1→M4 "
                f"(عقد قدرات · مسبار حيّ · ميزانيات وسجلّ تدقيق · حوكمة).\n"
                f"     القدرة ≠ الأمان: الصندوق يشغّل python/pip/git/npm، والمستخدمون قاصرون."
            )

    for rel, reason in sorted(_INTERLOCK_EXEMPTIONS.items()):
        if not reason.strip():
            problems.append(f"إعفاء {rel!r} بلا سببٍ منطوق — الصمت يُقرأ إذناً.")
        if not (REPO_ROOT / rel).exists():
            problems.append(f"إعفاءٌ لمسارٍ غير موجود: {rel!r} — احذفه من القائمة.")
        elif rel not in seen_exemptions:
            problems.append(f"إعفاء {rel!r} لم يعد لازماً (الوحدة لم تعد تجمع الاثنين) — احذفه.")
    return problems


# ─────────────────────────────────────────────────────────────────────────────
# فحص الوثيقتين
# ─────────────────────────────────────────────────────────────────────────────


def _known_gate_names() -> set[str]:
    names: set[str] = set()
    for path in sorted(FITNESS_DIR.glob("*.py")):
        names.add(path.stem)
        for match in re.finditer(
            r"^def (check_[a-z0-9_]+)\(", path.read_text(encoding="utf-8"), re.MULTILINE
        ):
            names.add(match.group(1))
    return names


def _section(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        return ""
    end = text.find(end_marker, start + len(start_marker))
    return text[start:] if end == -1 else text[start:end]


def _read_rows(text: str) -> list[tuple[int, str, str, str, str]]:
    rows: list[tuple[int, str, str, str, str]] = []
    for line in text.splitlines():
        match = _ROW.match(line.strip())
        if not match:
            continue
        number, name, _carrier, evidence, status, gap = match.groups()
        rows.append((int(number), name, evidence, status, gap))
    return rows


def _check_row(number: int, name: str, evidence: str, status: str, gap: str) -> list[str]:
    where = f"الصفّ {number} ({name.strip()})"
    problems: list[str] = []

    clean_status = status.strip("`* ")
    if clean_status not in VALID_STATUSES:
        problems.append(
            f"{where}: الحالة {clean_status!r} خارج السُّلَّم القانوني "
            f"({', '.join(sorted(VALID_STATUSES))}) — لا سُلَّم ثانٍ (§6.6)."
        )

    clean_gap = gap.strip()
    if not clean_gap or clean_gap in ("-", "—"):
        problems.append(
            f"{where}: خانة الفجوة فارغة. الفراغ يُقرأ نجاحاً — اكتب الفجوة أو «لا فجوة معروفة»."
        )

    evidence_match = _EVIDENCE.search(evidence)
    if not evidence_match:
        problems.append(f"{where}: بلا دليل ملفّي داخل `backticks`.")
        return problems

    evidence_path = evidence_match.group(1).strip()
    if not (REPO_ROOT / evidence_path).exists():
        problems.append(
            f"{where}: الدليل {evidence_path!r} غير موجود في المستودع. "
            f"حالةٌ أمام ملفٍّ غير موجود ادّعاءٌ لا برهان."
        )
    return problems


def _check_law_gates(text: str) -> list[str]:
    """كل بوّابةٍ مذكورة موجودة أو مُعلَنة مُخطَّطة — والقائمة مفروضة في الاتجاهين."""
    problems: list[str] = []
    known = _known_gate_names()
    for gate in sorted(set(_GATE_MENTION.findall(text))):
        if gate in known or gate in _PLANNED_GATES:
            continue
        problems.append(
            f"{LAW_DOC.name} تستشهد بالبوّابة {gate!r} وهي غير موجودة ولا مُعلَنة "
            f"في `_PLANNED_GATES` — قانونٌ يَعِد بحراسةٍ غير قائمة (ISS-149 · F3)."
        )
    for gate in sorted(_PLANNED_GATES & known):
        if gate == "check_llm_sandbox_interlock":
            continue  # بندٌ داخل هذه البوّابة، لا ملفّ مستقلّ
        problems.append(
            f"البوّابة {gate!r} مُعلَنة «مُخطَّطة» وهي موجودة فعلاً — احذفها من "
            f"`_PLANNED_GATES`. القائمة تتقلّص فقط."
        )
    return problems


def _check_law_sections(text: str) -> list[str]:
    """عدد الطبقات ثابت، وكلٌّ تُسمّي فارضها أو تُعلن غيابه (D-206 · L11)."""
    problems: list[str] = []
    # الطبقات 1→13 أقسامٌ مرقّمة؛ §0 و§14 خارج العدّ (أطروحة + تسلسل سوق).
    sections = [(n, t) for n, t in _LAW_SECTION.findall(text) if 1 <= int(n) <= EXPECTED_LAYERS]
    if len(sections) != EXPECTED_LAYERS:
        problems.append(
            f"وثيقة القانون تحمل {len(sections)} طبقة بينما المُعلَن {EXPECTED_LAYERS} — "
            f"حذفُ طبقةٍ أو إضافتها قرارٌ يُسجَّل في .memory/decisions.md."
        )
    for number, title in sections:
        start = text.find(f"## {number}) {title}")
        if start == -1:
            continue
        nxt = text.find("\n## ", start + 1)
        body = text[start:] if nxt == -1 else text[start:nxt]
        if "**الفارض:**" not in body and "بلا فارض" not in body:
            problems.append(
                f"{LAW_DOC.name}: الطبقة «{number}) {title}» بلا سطر «**الفارض:**» ولا "
                f"إعلانِ «بلا فارض» — الصمت يُقرأ انضباطاً وهو ليس كذلك."
            )
    return problems


def _check_law_carries_no_status(text: str) -> list[str]:
    """⛔ لا سُلَّم ثانٍ: القانون لا يحمل حالات — موطنها ملفّ الحالة وحده."""
    problems: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        for cell in stripped.strip("|").split("|"):
            if cell.strip("`* ") in VALID_STATUSES:
                problems.append(
                    f"{LAW_DOC.name}:{line_no}: خانةُ جدولٍ تحمل الحالة {cell.strip()!r}. "
                    f"القانون لا يحمل حالات (D-188) — موطنها {STATE_DOC.name} وحده."
                )
    return problems


def _check_law() -> list[str]:
    if not LAW_DOC.is_file():
        return [f"{LAW_DOC.name} غير موجودة — القانون جزء من العقد لا ملحقاً."]
    text = LAW_DOC.read_text(encoding="utf-8")
    return _check_law_gates(text) + _check_law_sections(text) + _check_law_carries_no_status(text)


def main() -> int:
    failures: list[str] = []

    if not STATE_DOC.is_file():
        print(f"❌ {STATE_DOC.relative_to(REPO_ROOT)} غير موجود — الخريطة جزء من العقد.")
        return 1

    text = STATE_DOC.read_text(encoding="utf-8")
    layers = _read_rows(_section(text, "### 2.a", "### 2.b"))
    horizons = _read_rows(_section(text, "### 2.b", "\n## 3."))

    if not layers:
        print("❌ لم يُقرأ أيّ صفّ من جدول الطبقات (§2.a) — تغيّر شكل الجدول؟")
        return 1
    if not horizons:
        print("❌ لم يُقرأ أيّ صفّ من جدول الآفاق (§2.b) — تغيّر شكل الجدول؟")
        return 1

    if len(layers) != EXPECTED_LAYERS:
        failures.append(
            f"عدد الطبقات {len(layers)} ≠ المُعلَن {EXPECTED_LAYERS}. "
            f"الحذف أو الإضافة قرارٌ يُسجَّل — لا حذف صامت."
        )
    if len(horizons) != EXPECTED_HORIZONS:
        failures.append(
            f"عدد آفاق السوق {len(horizons)} ≠ المُعلَن {EXPECTED_HORIZONS}. "
            f"الطموح لا يُحذف بصمت — يُصنَّف أو يُسجَّل قرارُ إسقاطه."
        )

    seen: set[int] = set()
    for number, name, evidence, status, gap in layers + horizons:
        if number in seen:
            failures.append(f"الصفّ {number} ({name.strip()}): رقمٌ مكرَّر.")
        seen.add(number)
        failures.extend(_check_row(number, name, evidence, status, gap))

    failures.extend(_check_law())
    failures.extend(_check_llm_sandbox_interlock())

    if failures:
        print("❌ محرّك التنفيذ المعرفي مخروق:\n")
        for failure in failures:
            print(f"  • {failure}")
        print(
            "\n📌 D-224: الحقيقة تُنفَّذ ويُتحقَّق منها، واللغة تصفها ولا تُقرّرها.\n"
            "   والقدرة ≠ الأمان: تصنيع البرنامج حمولةُ M1→M4 لا التفافٌ عليها (D-187)."
        )
        return 1

    active = sum(1 for _, _, _, s, _ in layers if s.strip("`* ") == "ACTIVE")
    print(
        f"✅ محرّك التنفيذ المعرفي: {len(layers)} طبقة + {len(horizons)} آفاق سوق، "
        f"كلّ دليلٍ موجود، {active} طبقات ACTIVE بالبرهان الملفّي، والقانون يُسمّي فوارضَ "
        f"قائمة بلا سُلَّمٍ ثانٍ · قفل D-187 سليم (صفر وحدة تجمع نموذجاً بمُنفِّذ)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
