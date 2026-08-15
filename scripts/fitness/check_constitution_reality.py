#!/usr/bin/env python3
"""يفرض أن الدستور **يساوي** الواقع — ولا يناقض نفسه (D-192).

**لماذا هذه البوّابة موجودة:**

بوّابة D-188 (``check_memory_coherence``) أوقفت انحراف **الفهرس والترتيب والحجم**.
لكنها لا ترى صنفاً أخطر: **رقماً مكتوباً باليد في النثر**. وقد وجدنا في 2026-07-31 أن
``CLAUDE.md`` يناقض **نفسه** في موضعين، وأن كلا الرقمين خاطئ:

* §0.5 يقول «٢٤ مهارة اليوم» بينما §0.7 يقول «Skills Engine (27 skills)» — والعدد
  الحقيقي يُشتَقّ من ``app/services/skills/registry.py`` (ولا يُكتب هنا: docstringٌ
  يُثبِّت كمّيةً متحرّكة هو العطبُ نفسه — أصلحه D-209).
* §3 وD-185 يقولان «API-first **13/13**» بينما §6.7.ط يقول «**11/11** حقيقي» —
  والعدد يُشتَقّ من ``docs/contracts/openapi/``.

الجذر واحد: **رقمٌ يُكتب يدوياً في نثرٍ لا يعرف مصدره**. كل تغييرٍ في الكود يجعله
أقدم، ولا شيء يلاحظ. الدواء ليس «تصحيح الرقم» — فسيتقادم غداً — بل **اشتقاقه**:
الرقم يُحسَب من المصدر، والنثر يحمل مؤشراً لا قيمة.

**توسعة D-209 — النطاق كان الثغرة الحقيقية:**

بقيت هذه البوّابة تقرأ **``CLAUDE.md`` وحده** حتى 2026-08-03. فكانت قاعدة «كمّية واحدة
لا تحمل قيمتين» مفروضةً داخل ملفٍّ واحد ومخروقةً في كل ما حوله — وCI خضراء:

===========================  ==========================================================
الكمّية                       القيم المتعايشة
===========================  ==========================================================
عقود API-first               ``11/11`` (EXTENSION_SEAMS) · ``12/12`` (runtime_truth)
                             · ``13/13`` (CLAUDE.md)
عدد المهارات                  ``23`` (context.md) · ``27`` (agentic_runtime_doctrine)
عدد الخدمات المصغّرة           ``8`` (context.md) · العدد الحقيقي في الكتالوج
أقصى قرارٍ مُسجَّل             ``D-189`` (DOCUMENTATION_INDEX) بينما السجلّ أبعد
أرضية التغطية                 ``80.0`` (.julesrc) · ``73`` (ci.yml)
===========================  ==========================================================

وهذا **نفس صنف ISS-148**: فارضٌ بلا مرمى. والأخطر أن ``.claude/settings.json`` يحقن
``context.md`` أوّلَ كل جلسة — أي أن أوّل ما يقرأه كل وكيل كان أكذبَ ملفّ في المستودع.
فالنطاق الآن **كل وثائق السلطة** (``_AUTHORITY_DOCS``)، والدَّين المُجمَّد **فارغ**.

⛔ **السجلّات التاريخية خارج النطاق عمداً** (``decisions.md`` · ``issues.md`` ·
``docs/archive/``): سجلٌّ يروي «كان العدد 27 يومها» يقول صدقاً عن الماضي، وفرضُ الحاضر
عليه يُحوّل التاريخ إلى كذب.

**ما تفرضه:**

1. **الأرقام مشتقّة**: أيّ عددٍ للمهارات/العقود/الخدمات/القرارات/التغطية في **أيّ**
   وثيقة سلطة يجب أن يطابق المُشتقّ من مصدره.
2. **لا تناقض ذاتي**: الكمّية نفسها لا تظهر بقيمتين — لا في ملفٍّ واحد ولا عبر الملفّات.
3. **ادّعاءات الرموز صحيحة**: كل قاعدة تسمّي رمزاً في الكود تُختبَر على المصدر —
   فلا تعود «القاعدة المعلنة بنصفها» (``math_explanation_card`` كانت مُسجَّلة في
   الواجهة وغائبة عن عقد الخادم، فلا تصل الطالب أبداً).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
OPENAPI_DIR = REPO_ROOT / "docs/contracts/openapi"

#: وثائق السلطة — من يقرأها يبني عليها قراراً، فتلزمها القاعدة نفسها (D-209).
#: ⛔ السجلّات التاريخية (`decisions.md` · `issues.md` · `docs/archive/`) مُستثناة عمداً:
#: سجلٌّ يروي رقماً قديماً يقول صدقاً عن الماضي.
_AUTHORITY_DOCS: tuple[str, ...] = (
    "CLAUDE.md",
    "spec.md",
    "AGENTS.md",
    "README.md",
    # المرآة العربية للواجهة الأولى: الأرقام فيها مكتوبة بالخانات نفسها، والبوّابة
    # تُترجم الأرقام العربية-الهندية — فلا تصير النسخة الثانية موطناً لرقمٍ بائت.
    "README.ar.md",
    "replit.md",
    ".memory/README.md",
    ".memory/context.md",
    ".memory/runtime_truth.md",
    ".memory/ci-gates.md",
    ".memory/agentic_runtime_doctrine.md",
    "docs/DOCUMENTATION_INDEX.md",
    "docs/architecture/EXTENSION_SEAMS.md",
    "docs/architecture/CS_KNOWLEDGE_MAP.md",
    "docs/architecture/AGENTIC_ORCHESTRATION_DOCTRINE.md",
)

#: دَينٌ مُجمَّد — **فارغ عمداً**، يتقلّص فقط (سابقة D-105).
#: المفتاح `"<doc>:<quantity>"`، والقيمة القيمةُ البائتة المسموح بها مؤقّتاً.
_FROZEN_DEBT: dict[str, str] = {}

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _skill_count() -> int:
    """يشتقّ عدد المهارات المُسجَّلة من سجلّ المهارات نفسه (بلا استيراد التطبيق).

    نقرأ استدعاءات ``register(...)`` نصّياً: استيراد ``app`` يتطلّب إعدادات وقاعدة
    بيانات، والبوّابات يجب أن تعمل في sandbox مُتدهور (نفس قيد ``db_bridge``).
    """
    registry = (REPO_ROOT / "app/services/skills/registry.py").read_text(encoding="utf-8")
    return len(set(re.findall(r'name=["\']([a-z0-9_]+)["\']', registry)))


def _contract_count() -> int:
    """عدد عقود الخدمات المُلتزَمة — المصدر: الملفّات على القرص."""
    return len(sorted(OPENAPI_DIR.glob("*-openapi.json")))


def _service_count() -> int:
    """عدد الخدمات المصغّرة — المصدر: كتالوج الخدمات المحكوم ببوّابة التكافؤ."""
    catalog = REPO_ROOT / "config/microservice_catalog.json"
    if not catalog.is_file():
        return 0
    # نقرأ نصّياً: البوّابة يجب أن تعمل بلا تبعيات (نفس قيد `db_bridge`).
    return len(re.findall(r'"service_dir"\s*:', catalog.read_text(encoding="utf-8")))


def _max_log_id(rel: str, prefix: str) -> int:
    """أقصى مُعرَّف في سجلٍّ (`D-###` أو `ISS-###`) — المصدر: السجلّ نفسه."""
    path = REPO_ROOT / rel
    if not path.is_file():
        return 0
    ids = re.findall(rf"^## {prefix}-(\d{{3}})\b", path.read_text(encoding="utf-8"), re.MULTILINE)
    return max((int(i) for i in ids), default=0)


def _coverage_floor() -> int:
    """أرضية التغطية — المصدر: `ci.yml` وحده، فهي التي تُفشِل الدمج فعلاً."""
    workflow = REPO_ROOT / ".github/workflows/ci.yml"
    if not workflow.is_file():
        return 0
    floors = re.findall(r"--cov-fail-under=(\d+)", workflow.read_text(encoding="utf-8"))
    return max((int(f) for f in floors), default=0)


def _required_ci_job_count() -> int:
    """عدد الوظائف التي يجمعها `required-ci` — المصدر: قائمة `needs:` نفسها.

    `.memory/ci-gates.md` كان يقول «تسع» بينما القائمة عشر، **وهو نفسه** يُصرّح أن
    «`needs:` هي الحقيقة» — أي وثيقةٌ تُناقض القاعدة التي تُعلنها في السطر نفسه.
    """
    workflow = REPO_ROOT / ".github/workflows/ci.yml"
    if not workflow.is_file():
        return 0
    text = workflow.read_text(encoding="utf-8")
    match = re.search(r"^  required-ci:.*?needs:\s*\n\s*\[(.*?)\]", text, re.S | re.M)
    if not match:
        return 0
    body = re.sub(r"#[^\n]*", "", match.group(1))  # تعليقات داخل القائمة ليست وظائف
    return len([job for job in (j.strip() for j in body.split(",")) if job])


#: أعدادٌ منطوقة بالكلمات — تظهر في النثر العربي والإنجليزي وتتقادم كما تتقادم الأرقام.
_WORD_NUMBERS: dict[str, int] = {
    "تسع": 9,
    "عشر": 10,
    "إحدى عشرة": 11,
    "احدى عشرة": 11,
    "اثنتي عشرة": 12,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
}


def _quantities() -> tuple[tuple[str, str, int, str], ...]:
    """(اسم الكمّية، النمط، القيمة المُشتقّة، المصدر) — تُفحَص عبر كل وثائق السلطة."""
    return (
        (
            # النمط يتسامح مع نصٍّ يحمل أرقاماً بينهما («API-first **100%:** … (11/11 …)»)،
            # فالنسخة الضيّقة كانت تفوّت بالضبط الموضع الذي وُلد منه D-209.
            # والمرجع الخلفي `\1` يشترط **نسبةً متساوية** (13/13) فلا يُخطَف
            # «D-173 Stage 4/5» — نمطٌ فضفاض يُنتج ضجيجاً، والضجيج يُعلِّم تجاهل البوّابة.
            "عقود API-first",
            r"API-first[^\n]{0,40}?(\d{1,3})\s*/\s*\1(?!\d)",
            _contract_count(),
            "docs/contracts/openapi/*-openapi.json",
        ),
        (
            "عقود تحت بوّابة التكافؤ",
            r"check_openapi_parity[^\n]{0,40}?(\d{1,3})\s*/\s*\1(?!\d)",
            _contract_count(),
            "docs/contracts/openapi/*-openapi.json",
        ),
        (
            "عدد المهارات",
            r"\(?([0-9٠-٩]{1,3})\s*(?:مهارة|skills\b|registered descriptors)",
            _skill_count(),
            "app/services/skills/registry.py",
        ),
        (
            "عدد الخدمات المصغّرة",
            r"([0-9٠-٩]{1,3})\s*(?:microservices\b|خدمة مصغّرة|خدمات مصغّرة)",
            _service_count(),
            "config/microservice_catalog.json",
        ),
        (
            "أقصى قرار مُسجَّل",
            r"D-001\s*(?:→|->)\s*\*{0,2}D-(\d{3})",
            _max_log_id(".memory/decisions.md", "D"),
            ".memory/decisions.md",
        ),
        (
            "أقصى بلاغ مُسجَّل",
            r"ISS-001\s*(?:→|->)\s*\*{0,2}ISS-(\d{3})",
            _max_log_id(".memory/issues.md", "ISS"),
            ".memory/issues.md",
        ),
        (
            "أرضية التغطية",
            r"cov-fail-under=(\d{2,3})",
            _coverage_floor(),
            ".github/workflows/ci.yml",
        ),
        (
            "وظائف required-ci",
            # `[^\n]` لا `[^.\n]`: النقطة تظهر داخل «ci.yml» فكان الاستثناء يقتل المطابقة
            # قبل أن تصل إلى «nine jobs» — بوّابةٌ لا تصل إلى نصّها لا تحرسه.
            r"required-ci[^\n]{0,60}?\*{0,2}(\d{1,2}|"
            + "|".join(re.escape(w) for w in _WORD_NUMBERS)
            + r")\*{0,2}\s*(?:jobs|وظائف|وظيفة)",
            _required_ci_job_count(),
            ".github/workflows/ci.yml (needs:)",
        ),
    )


def _check_authority_docs() -> list[str]:
    """القاعدة نفسها، مطبَّقةً على **كل** وثيقة سلطة لا على الدستور وحده (D-209)."""
    errors: list[str] = []
    for name, pattern, derived, source in _quantities():
        if derived <= 0:  # مصدرٌ لم يُقرأ: نقول ذلك ولا نمرّ بصمت
            errors.append(
                f"❌ تعذّر اشتقاق «{name}» من {source} — بوّابةٌ لا تقرأ مصدرها "
                f"لا تُبلِّغ أن الوثائق نظيفة (D-208)."
            )
            continue
        for rel in _AUTHORITY_DOCS:
            path = REPO_ROOT / rel
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for line_no, raw in _claims(text, pattern):
                value = _WORD_NUMBERS.get(raw.strip())
                if value is None:
                    value = int(raw.translate(_AR_DIGITS))
                if value == derived:
                    continue
                if _FROZEN_DEBT.get(f"{rel}:{name}") == raw:
                    continue
                errors.append(
                    f"❌ {rel}:{line_no}: «{name}» مكتوبةً {raw!r} بينما المُشتَقّ "
                    f"{derived} من {source}.\n"
                    f"   الرقم يُشتَقّ ولا يُكتب — والكمّية الواحدة لا تحمل قيمتين (D-192/D-209)."
                )
    return errors


def _claims(text: str, pattern: str) -> list[tuple[int, str]]:
    """يُعيد (رقم السطر، القيمة) لكل مطابقة — لتقارير تُشير إلى الموضع."""
    out: list[tuple[int, str]] = []
    for match in re.finditer(pattern, text):
        line_no = text[: match.start()].count("\n") + 1
        out.append((line_no, match.group(1)))
    return out


def _check_no_self_contradiction(text: str) -> list[str]:
    """القاعدة 2: الكمّية نفسها لا تظهر بقيمتين مختلفتين في الدستور."""
    errors: list[str] = []

    # (أ) نسبة API-first «N/N».
    ratios = {value for _, value in _claims(text, r"API-first\s+\*{0,2}(\d+)/\d+")}
    if len(ratios) > 1:
        errors.append(
            f"❌ CLAUDE.md يناقض نفسه في نسبة API-first: {sorted(ratios)}.\n"
            f"   كمّيةٌ واحدة بقيمتين — استبدل الأرقام بمؤشرٍ إلى المصدر المُشتقّ."
        )

    # (ب) عدد المهارات (عربي أو إنجليزي).
    skill_claims = {
        value.translate(_AR_DIGITS)
        for _, value in _claims(text, r"\(?([0-9٠-٩]{1,3})\s*(?:مهارة|skills)")
    }
    if len(skill_claims) > 1:
        errors.append(
            f"❌ CLAUDE.md يناقض نفسه في عدد المهارات: {sorted(skill_claims)}.\n"
            f"   كمّيةٌ واحدة بقيمتين — العدد يُشتَقّ من `registry.py` لا يُكتب يدوياً."
        )
    return errors


def _check_derived_numbers(text: str) -> list[str]:
    """القاعدة 1: أيّ رقم مذكور يجب أن يطابق المُشتقّ من الكود."""
    errors: list[str] = []
    real_contracts = _contract_count()
    for line_no, value in _claims(text, r"API-first\s+\*{0,2}(\d+)/\d+"):
        if int(value) != real_contracts:
            errors.append(
                f"❌ CLAUDE.md:{line_no}: API-first {value}/… بينما المُشتقّ "
                f"{real_contracts} عقداً في docs/contracts/openapi/."
            )
    real_skills = _skill_count()
    for line_no, value in _claims(text, r"\(?([0-9٠-٩]{1,3})\s*(?:مهارة|skills)"):
        if int(value.translate(_AR_DIGITS)) != real_skills:
            errors.append(
                f"❌ CLAUDE.md:{line_no}: «{value} مهارة» بينما المُسجَّل فعلياً "
                f"{real_skills} مهارة في app/services/skills/registry.py."
            )
    return errors


#: ادّعاءات الرموز: (وصف، ملف، نصّ يجب أن يوجد). كل واحدة قاعدةٌ في الدستور
#: كان يمكن أن تُكتب وتبقى كاذبة — والاختبار يجعلها صادقةً بالبناء.
_SYMBOL_CLAIMS: tuple[tuple[str, str, str], ...] = (
    (
        "D-080: math_explanation_card قابلة للتسليم من الخادم لا من الواجهة وحدها",
        "app/contracts/streaming.py",
        '"math_explanation_card"',
    ),
    (
        "D-097: مُقطِّع نثر LLM يبقى مُعطَّلاً دائماً",
        "app/api/routers/customer_chat_support/frames.py",
        "return None",
    ),
    (
        "D-191: الكيانات المهيكلة نوعٌ حقيقي له قارئ حيّ",
        "app/services/skills/probability_models.py",
        "class ParsedEntities",
    ),
    (
        "D-191: التمرين قيد النقاش له مُحلٌّ واحد",
        "app/services/skills/exercise_context.py",
        "CANONICAL_EXERCISE_QUERY",
    ),
    (
        "D-116: كل مكوّنات الاحتمالات تُنهي المسار (يَعلو على شرط D-085)",
        "app/infrastructure/clients/orchestrator/probability_ui.py",
        '"terminate_pipeline": True',
    ),
)


def _check_symbol_claims() -> list[str]:
    errors: list[str] = []
    for description, rel, needle in _SYMBOL_CLAIMS:
        path = REPO_ROOT / rel
        if not path.is_file():
            errors.append(f"❌ {description}\n   الملفّ مفقود: {rel}")
            continue
        if needle not in path.read_text(encoding="utf-8"):
            errors.append(
                f"❌ ادّعاء دستوري لم يعد صحيحاً: {description}\n"
                f"   لم أجد {needle!r} في {rel}. صحّح الكود أو صحّح الدستور — "
                f"لا تتركهما متناقضين."
            )
    return errors


def main() -> int:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    errors = (
        _check_no_self_contradiction(text)
        + _check_derived_numbers(text)
        + _check_symbol_claims()
        + _check_authority_docs()
    )
    if errors:
        print("\n".join(errors))
        print(
            "\n📌 D-192: الدستور عقدٌ يساوي الواقع. الرقم يُشتَقّ ولا يُكتب يدوياً،\n"
            "   والكمّية الواحدة لا تحمل قيمتين، وكل رمزٍ يُذكَر يُختبَر على المصدر."
        )
        return 1
    print(
        f"✅ constitution = reality عبر {len(_AUTHORITY_DOCS)} وثيقة سلطة: بلا تناقض ذاتي · "
        f"الأرقام مشتقّة ({_skill_count()} مهارة · {_contract_count()} عقداً · "
        f"{_service_count()} خدمة · D-{_max_log_id('.memory/decisions.md', 'D'):03d} · "
        f"تغطية {_coverage_floor()} · {_required_ci_job_count()} وظائف required-ci) · "
        f"{len(_SYMBOL_CLAIMS)} ادّعاءات رموز مُتحقَّقة · دَينٌ مُجمَّد: {len(_FROZEN_DEBT)}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
