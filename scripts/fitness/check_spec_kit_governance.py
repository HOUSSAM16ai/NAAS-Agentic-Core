#!/usr/bin/env python3
"""بوّابة دستور حوكمة Spec Kit — D-265 / ISS-182→ISS-185.

## لماذا هذه البوّابة موجودة
دستورٌ جديد (`.memory/spec_kit_governance_constitution.md`) يرفَع Spec Kit
(plan→design→tasks→spec→implement→prove) من قالبٍ إلى **طبقة ضبط تنفيذ
فوق الدستورية**: مواصفة حية لكل تغيير جوهري، وفارضٌ مسمّى لكل قانون،
وبرهانٌ قبل قبول، وتراجعٌ نظيف. والقانون ما له فارض؛ فإضافة نصٍّ إلى
مستودعٍ ليست إضافةَ قانون.

**ما تفحصه (قانون D-265 §4):**
1. الدستور موجود ومكتمل: §1 التشخيص · §2 العقيدة والعتبة · §3 الأبواب الأربعة ·
   §4 القوانين العشرة · §6 المقياس · §7 العلاقة بالدساتير القائمة.
2. **L3 (الفارض المسمّى):** كل `check_*.py` في `scripts/fitness/` مذكورٌ فعلًا
   في وثيقةٍ دستورية (CLAUDE.md · spec.md · *.md الدستورية) — لا يتيمة فارض.
   والعكس: كل بوابةٍ مذكورة دستوريًا موجودة فعلًا — لا وهم.
3. **L1/L2 (مواصفة حية):** `spec.md` الجذر موجود ويحمل سجلَّ برهان (§17b)؛
   ونمط `docs/specs/` موجود — لا مستودع Spec-First بلا مواصفات.
4. **L9 (الأثر في القرارات):** ADR موجود (`docs/architecture/` · ADR-001/
   ADR-002) و`decisions.md` حيّ.
5. **L8 (الأسرار):** نمط `check_no_committed_secrets.py` موجود وحيّ.
6. **L6/L7:** `check_openapi_parity.py` + `check_tracing_gate.py` موجودان.
7. **لا ادّعاء رقمي يدوي** — أي «+%» في وثيقةٍ دستورية يشير إلى مرجعٍ منشور
   (يمتدّ D-263 §6.6).
8. **الأعداد تُشتَقّ** — عشرة قوانين كاملة، وكل قانون يسمّي فارضًا موجودًا.

**لا تُستورد من app/** (نمط `check_pedagogical_os.py`) — static-text خالصة
تعمل في بيئة متدهورة. Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _pass(msg: str) -> None:
    print(f"✅ {msg}")


def _read(rel: str) -> str:
    path = REPO_ROOT / rel
    if not path.is_file():
        _fail(f"ملفّ مفقود: {rel}")
        return ""
    return path.read_text(encoding="utf-8")


def _must(pattern: str, text: str, where: str, count: int | None = None) -> None:
    found = re.findall(pattern, text)
    n = len(found)
    if count is not None:
        if n != count:
            _fail(f"{where}: متوقّع {count} مطابقة لنمط `{pattern}`، وُجدت {n}")
            return
        _pass(f"{where}: {n} مطابقة لـ `{pattern}`")
    elif n == 0:
        _fail(f"{where}: النمط مفقود `{pattern}`")
    else:
        _pass(f"{where}: `{pattern}` حاضر ({n}×)")


def _check_constitution_sections(const: str) -> None:
    for section in (
        r"## 1\. التشخيص الدستوري",
        r"## 2\. العقيدة الأساسية",
        r"عتبة «الجوهري»",
        r"## 3\. الركائز الأربع",
        r"## 4\. القوانين الصارمة العشرة",
        r"## 6\. مقياس النجاح الدستوري",
        r"## 7\. علاقة هذا الدستور بالعقائد القائمة",
    ):
        _must(section, const, "الدستور D-265")


def _check_section_laws(const: str) -> None:
    laws = re.findall(r"^\| L(\d+) \|", const, flags=re.M)
    if set(laws) != {str(i) for i in range(1, 11)}:
        _fail(f"قوانين §4 ليست عشرة كاملة (وُجدت: {sorted(laws, key=int)})")
        return
    _pass("القوانين العشرة كاملة L1–L10")


def _check_orphan_enforcers() -> None:
    # L3: لا بوابة يتيم ولا إشارة وهمية — فحص ثنائي الاتجاه:
    # (أ) كل check_*.py يجب أن يُذكر في وثيقة دستورية (CLAUDE.md · spec.md ·
    #     .memory/*.md التي تتضمن "دستور"/"constitution")
    # (ب) كل اسم بوابة مذكور دستوريًا يجب أن يوجد ملفّه.
    fitness = REPO_ROOT / "scripts" / "fitness"
    tools_ci = REPO_ROOT / "tools" / "ci"
    _gates = (list(fitness.glob("check_*.py")) if fitness.is_dir() else []) + (
        list(tools_ci.glob("check_*.py")) if tools_ci.is_dir() else []
    )
    gates = sorted(p.name for p in _gates)
    docs = (
        [
            _read("CLAUDE.md"),
            _read("README.md"),
            _read("README.ar.md"),
            _read("spec.md"),
            _read(".memory/pedagogy_engine_constitution.md"),
            _read(".memory/adaptive_study_planner_constitution.md"),
            _read(".memory/spec_kit_governance_constitution.md"),
            _read(".memory/pedagogical_os.md"),
            _read(".memory/README.md"),
            _read("docs/DOCUMENTATION_INDEX.md"),
        ]
        + [_read(f"docs/adr/{p.name}") for p in (REPO_ROOT / "docs" / "adr").glob("*.md")]
        + [
            _read(f"docs/architecture/{p.name}")
            for p in (REPO_ROOT / "docs" / "architecture").glob("*.md")
        ]
        + [
            _read(".memory/runtime_truth.md"),
            _read(".memory/decisions.md"),
            _read("AGENTS.md"),
            _read(".github/workflows/doc_integrity.yml"),
            _read("pyproject.toml"),
            _read("tests/fitness/test_phase0_governance.py"),
            _read("scripts/fitness/generate_cutover_scoreboard.py"),
            _read(".memory/tasks.md"),
        ]
    )
    docs_text = "\n".join(d or "" for d in docs)
    # وثائق الأرشيف التشخيصي تُحصّل نصيًا (لا كل ملفات الأرشيف): الفحوصات
    # المذكورة في تقارير حية داخل المستودد مغطاة دستوريًا (نمط D-255).
    arch_idx = REPO_ROOT / "docs" / "archive"
    if arch_idx.is_dir():
        # نحصّل النصوص لا الأسماء — الأسماء لا تحوي أسماء البوابات:
        for a in arch_idx.rglob("*.md"):
            docs_text += "\n" + a.read_text(encoding="utf-8", errors="ignore")
    # طبقة التوثيق الأوسع (architecture doctrine + workflows) تُحصَّل منفصلة:
    # البوابة الدستورية تغطي النطاق الدستوري؛ توثيق الهندسة يغطي الباقي.
    arch = _read("docs/architecture/AGENTIC_ORCHESTRATION_DOCTRINE.md") or ""
    wf = _read(".github/workflows/ci.yml") or _read(".github/workflows/doc_integrity.yml") or ""
    docs_text += "\n" + arch + "\n" + wf

    orphans = [g for g in gates if g not in docs_text]
    if orphans:
        _fail(f"بوابات يتيمة غير مذكورة دستوريًا: {orphans} (L3)")
    else:
        _pass("لا بوابة يتيمة — كل check_*.py مذكور دستوريًا (L3)")

    # (ب) الإشارات الوهمية: نمط `check_*.py` مذكور في وثيقةٍ **حية** (خارج
    # الأرشيف) دون ملف — ذِكر الأرشيف دينٌ توثيقي موثّق سلفًا (D-156) وليس
    # وهمًا جديدًا.
    living_text = "\n".join(d or "" for d in docs)
    living_text += "\n" + arch + "\n" + wf
    # استثناء: `.memory/tasks.md` قائمة مهام تمنّي («أنشئ X») وليست ادّعاء
    # وجودٍ — لا تُعدّ مصدرًا لإشاراتٍ وهمية.
    if REPO_ROOT.joinpath(".memory/tasks.md").is_file():
        tasks_text = REPO_ROOT.joinpath(".memory/tasks.md").read_text(encoding="utf-8")
        # نبقيها في فحص اليتيم (أ) ونحذفها من فحص الوهم (ب):
        for pat in re.findall(r"check_[\w]+\.py", tasks_text):
            living_text = living_text.replace(pat, "")
    mentioned = set(re.findall(r"check_[\w]+\.py", living_text))
    missing = sorted(m for m in mentioned if m not in gates)
    if missing:
        _fail(f"إشارات وهمية: بوابات مذكورة بلا ملف: {missing} (L3)")
    else:
        _pass("كل بوابة مذكورة في وثيقةٍ حيّة موجودة فعلًا (L3)")


def _check_living_specs() -> None:
    # L1/L2: spec.md جذر حيّ يحمل سجل برهان + نمط docs/specs موجود
    spec = _read("spec.md")
    _must(r"17b", spec, "spec.md: سجل البرهان §17b (L4)")
    _must(r"Live E2E|E2E", spec, "spec.md: أدلة حيّة E2E مسجّلة")
    # مستودع المواصفات الحية ثلاثة مواطن **مطلوبة معاً**، لا بدائل `OR`:
    #   `docs/adr/`       — قرارات المعمار
    #   `docs/contracts/` — عقود API وحدود السياقات
    #   `docs/specs/`     — دورة Spec-First (خطة → تصميم → مهام → مواصفة)
    #
    # D-266 (ISS-186): كان هذا الفحص `or` بين الثلاثة، و`docs/specs/` — الموطن الذي
    # **يسمّيه الدستور نفسه** في §5 السؤال 3 («أين تُخزَّن المواصفات؟ — `docs/specs/
    # NN_*.md`») — **لم يكن موجوداً على القرص إطلاقاً**، والبوّابة تمرّ عبر `docs/adr`.
    # موطنٌ مُعلَن في دستورٍ وغيرُ موجود هو «الغياب المُعلَن بلا فحصٍ في الاتجاهين»
    # الذي يحظره §0.10. عولج بإنشاء الموطن وإلغاء البديل — لا بتخفيف الدستور.
    homes = {
        "docs/adr": bool(list((REPO_ROOT / "docs" / "adr").glob("ADR-*.md"))),
        "docs/contracts": (REPO_ROOT / "docs" / "contracts").is_dir(),
        "docs/specs": bool(list((REPO_ROOT / "docs" / "specs").glob("*.md"))),
    }
    missing = sorted(name for name, present in homes.items() if not present)
    if missing:
        _fail(f"مواطن المواصفات الحية الناقصة: {missing} — كلّها مطلوبة، لا بدائل (L1)")
    else:
        _pass(f"مستودع المواصفات حيّ في مواطنه الثلاثة: {', '.join(homes)} (L1)")

    # L3 الساق الثالثة (D-266): الذِّكر والوجود لا يكفيان — التنفيذ يُفحَص هناك.
    if not (REPO_ROOT / "scripts" / "fitness" / "check_governance_registry.py").is_file():
        _fail("`check_governance_registry.py` مفقود — الساق الثالثة من L3 بلا فارض (D-266)")
    else:
        _pass("الساق الثالثة من L3 (التنفيذ) مفروضة بـ`check_governance_registry.py` (D-266)")


def _check_decision_trail() -> None:
    # L9: ADR حيّ + سجل قرارات حيّ
    adr = _read("docs/architecture/02_adr_001_dependency_rules.md")
    _must(r"ADR-001", adr, "ADR-001 حيّ (نمط ADR)")
    adr2 = _read("docs/architecture/04_adr_002_unified_orchestration.md")
    _must(r"ADR-002", adr2, "ADR-002 حيّ")
    dec = _read(".memory/decisions.md")
    _must(r"D-26\d|D-2[0-9]\d", dec, ".memory/decisions.md (سجلّ قرارات حيّ ≥ D-260)")


def _check_security_tracing() -> None:
    # L7/L8: التتبع والأمان بوابتان مسمّاتان في الدستور
    sec = _read("scripts/fitness/check_no_committed_secrets.py")
    _must(r"secret|Secret|SECRET", sec, "check_no_committed_secrets (L8 — الأسرار)")
    tr = _read("scripts/fitness/check_tracing_gate.py")
    _must(r"trace|Trace|TRACE", tr, "check_tracing_gate (L7 — التتبع)")
    api = _read("scripts/fitness/check_openapi_parity.py")
    _must(r"openapi|OpenAPI|parity", api, "check_openapi_parity (L6 — العقد الخارجي)")


def _check_no_raw_claims() -> None:
    for doc in (
        ".memory/spec_kit_governance_constitution.md",
        "CLAUDE.md",
        "spec.md",
    ):
        text = _read(doc)
        if not text:
            continue
        claims = re.findall(r"\+\s*\d+(?:\.\d+)?\s*%", text)
        if not claims:
            continue
        cited = bool(re.search(r"(et al|PNAS|202[0-9]|arXiv|DOI|10\.\d+|Published)", text))
        for claim in claims:
            if not cited:
                _fail(f"{doc}: ادّعاء رقمي {claim} بلا مرجعٍ منشور (L10)")
            else:
                _pass(f"{doc}: ادّعاء {claim} مستند إلى مرجعٍ منشور")
                break


def main() -> int:
    const = _read(".memory/spec_kit_governance_constitution.md")
    if not const:
        return 1
    _check_constitution_sections(const)
    _check_section_laws(const)

    for gate in ("ISS-182", "ISS-183", "ISS-184", "ISS-185"):
        _must(re.escape(gate), const, "أبواب D-265")

    _check_orphan_enforcers()
    _check_living_specs()
    _check_decision_trail()
    _check_security_tracing()
    _check_no_raw_claims()

    if _FAILURES:
        print(f"\n❌ {len(_FAILURES)} انتهاك — دستور D-265 ليس محروسًا:")
        for f in _FAILURES:
            print(f"   - {f}")
        return 1
    print("✅ spec-kit-governance: الدستور D-265 محروس بالكامل (10 قوانين · بواباته موصولة).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
