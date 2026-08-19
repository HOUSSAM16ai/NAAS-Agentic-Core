#!/usr/bin/env python3
"""المعيار المفتوح للمهارات — وكلمةٌ بمعنيين مُعلَنين (D-271 · L9 · L10 · L11).

**لماذا هذه البوّابة موجودة:**

في هذا المستودع كلمة «مهارة» تعني **شيئين مختلفين تماماً**:

============  =========================================================================
المعنى         ما هو
============  =========================================================================
``BaseSkill``  قدرةٌ برمجية تعمل في مسار الطالب، ترث ``app/services/skills/base.py``
               (D-179): مسؤوليةٌ واحدة · عقد · مقاييس Prometheus · اختبارات.
Agent Skill    مجلّدٌ بمواصفة **Agent Skills** المفتوحة (``agentskills.io``): ``SKILL.md``
               بترويسة YAML، يُحمَّل عند الحاجة لتوجيه وكيلٍ لغوي. **لا يعمل في مسار
               الطالب إطلاقاً.**
============  =========================================================================

واسمٌ واحد لبنيتين هو بالضبط ما يحذّر منه D-209: «خريطتان لنظامٍ واحد تعنيان وكيلَين
يقرآن بناءَين مختلفين» — وهو ما أنتج ISS-139 حين تفرّقت ثلاث قوائم لنيّةٍ واحدة.
فالمسرد هنا **مُعلَن ومفروض**، لا مفهومٌ ضمناً.

**L9 — المطابقة للمعيار المفتوح.** المصدر: ``anthropics/skills`` (``spec/`` →
``agentskills.io/specification`` · ``template/SKILL.md``). كل مهارة: ملفّ ``SKILL.md``
بترويسة YAML، ``name`` يطابق اسم المجلّد، ووصفٌ يحمل **شرط التشغيل** — لأنّ الوصف هو
سطح الاستدعاء كلّه: مهارةٌ لا يُعرَف متى تُستعمَل لا تُستعمَل أبداً.

**L11 — الساق السادسة.** §0.5 يشترط خمساً: ``import + call chain + runtime evidence
+ metrics + tests``. ومنصّة ``skill-creator`` في ``anthropics/skills`` تحمل ما يضيف
السادسة: ``run_eval.py`` · ``grader.md`` · ``comparator.md`` · ``aggregate_benchmark.py``
· ``improve_description.py`` — أي أنّ المهارة **تُقاس** ولا تُعلَن. فلكلّ مهارةٍ هنا
حالةٌ مُصرَّحة: مُقيَّمة بنتيجةٍ مؤرَّخة، أو غير مُقيَّمة **بسببٍ منطوق**.

⛔ **قيدان لا يُخفَّفان:** لا تقييم LLM في مسار الطالب ولا كحقيقة (§0.5: صفر LLM في
مسار الأرقام) · ولا يُعلَن أثرٌ تعليمي («+X٪») من أيّ تقييمٍ هنا (قفل D-263).

المصدر القانوني: ``docs/governance/AGENT_SKILLS.json``.
تُشغَّل ضمن وظيفة ``guardrails``. Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
POLICY = REPO_ROOT / "docs" / "governance" / "AGENT_SKILLS.json"

#: العدد **يُشتَقّ** من السجلّ ولا يُكتب (D-192) — نفس اشتقاق `check_constitution_reality`.
BASE_SKILL_REGISTRY = REPO_ROOT / "app" / "services" / "skills" / "registry.py"
BASE_SKILL_NAME = re.compile(r'name=["\']([a-z0-9_]+)["\']')

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _pass(msg: str) -> None:
    print(f"✅ {msg}")


def _frontmatter(path: Path) -> dict | None:
    """ترويسة YAML بين أوّل سياجَي `---`. `None` تعني «تعذّرت القراءة»."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        loaded = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _check_agent_skills(policy: dict) -> list[str]:
    spec = policy.get("agent_skills", {})
    home = REPO_ROOT / str(spec.get("home", ".claude/skills"))
    if not home.is_dir():
        _fail(f"موطن مهارات الوكيل غير موجود: {spec.get('home')}")
        return []

    required = set(spec.get("required_frontmatter", ()))
    allowed = set(spec.get("allowed_frontmatter", ()))
    markers = tuple(spec.get("trigger_markers", ()))

    names: list[str] = []
    for directory in sorted(p for p in home.iterdir() if p.is_dir()):
        label = directory.name
        names.append(label)
        skill_file = directory / "SKILL.md"
        if not skill_file.is_file():
            _fail(f"{label}: لا `SKILL.md` — المعيار المفتوح يشترطه")
            continue
        meta = _frontmatter(skill_file)
        if meta is None:
            # ⛔ ملفٌّ لم يُحلَّل لا يُشهَد له بالمطابقة (D-208 §6).
            _fail(f"{label}: ترويسة YAML مفقودة أو غير صالحة — لا يُشهَد لها بالمطابقة")
            continue
        if missing := sorted(required - set(meta)):
            _fail(f"{label}: حقولٌ إلزامية مفقودة من الترويسة: {missing}")
        if extra := sorted(set(meta) - allowed):
            _fail(f"{label}: حقولٌ خارج المواصفة: {extra} — القائمة مغلقة عمداً")
        if str(meta.get("name", "")) != label:
            _fail(f"{label}: `name` في الترويسة ({meta.get('name')!r}) لا يطابق اسم المجلّد")
        description = str(meta.get("description", ""))
        if not any(marker in description for marker in markers):
            _fail(
                f"{label}: الوصف بلا شرط تشغيلٍ صريح ({' · '.join(markers)}) — "
                "الوصف هو سطح الاستدعاء كلّه؛ مهارةٌ لا يُعرَف متى تُستعمَل لا تُستعمَل"
            )
    if not _FAILURES:
        _pass(f"مطابقة Agent Skills: {len(names)} مهارة على المعيار المفتوح")
    return names


def _check_glossary(policy: dict) -> None:
    glossary = policy.get("glossary_ar", {})
    for key in ("base_skill", "agent_skill"):
        entry = glossary.get(key)
        if not isinstance(entry, dict) or not str(entry.get("meaning_ar", "")).strip():
            _fail(f"المسرد: `{key}` بلا معنى منطوق — كلمةٌ بمعنيين بلا إعلانٍ = سُلَّم ثانٍ خفيّ")
            continue
        home = str(entry.get("home", ""))
        if home and not (REPO_ROOT / home).exists():
            _fail(f"المسرد: `{key}.home` يشير إلى مسارٍ غير موجود: {home}")
    if not glossary.get("rule_ar", "").strip():
        _fail("المسرد بلا قاعدةٍ منطوقة تفصل المعنيين (D-209: لا سُلَّم ثانٍ)")


def _base_skill_names() -> set[str]:
    if not BASE_SKILL_REGISTRY.is_file():
        _fail("سجلّ المهارات غير موجود — لا يُشتَقّ العدد")
        return set()
    return set(BASE_SKILL_NAME.findall(BASE_SKILL_REGISTRY.read_text(encoding="utf-8")))


def _check_evaluation(policy: dict, agent_skills: list[str]) -> None:
    spec = policy.get("skill_evaluation", {})
    evaluated: dict = spec.get("evaluated", {})
    unevaluated: dict = spec.get("unevaluated", {})

    known = _base_skill_names() | set(agent_skills)
    covered = set(evaluated) | set(unevaluated)

    if missing := sorted(known - covered):
        _fail(
            f"مهارات بلا حالة تقييمٍ مُصرَّحة ({len(missing)}): {missing[:8]} — "
            "الخانة الفارغة تُقرأ نجاحاً (D-206 L11)"
        )
    if ghost := sorted(covered - known):
        _fail(f"السجلّ يسمّي مهارات غير موجودة: {ghost[:8]}")
    if both := sorted(set(evaluated) & set(unevaluated)):
        _fail(f"مهارات في `evaluated` و`unevaluated` معاً: {both} — حالةٌ واحدة لا اثنتان")
    if empty := sorted(name for name, reason in unevaluated.items() if not str(reason).strip()):
        _fail(f"غير مُقيَّمة بلا سببٍ منطوق: {empty[:8]}")

    for name, record in sorted(evaluated.items()):
        if not isinstance(record, dict) or not str(record.get("verified_on", "")).strip():
            _fail(f"{name}: مُعلَنٌ مُقيَّماً بلا `verified_on` — دعوى قياسٍ بلا تاريخ")
        elif not str(record.get("evidence", "")).strip():
            _fail(f"{name}: مُعلَنٌ مُقيَّماً بلا `evidence` — الدليل قبل الادّعاء (D-266)")

    if not _FAILURES:
        _pass(
            f"الساق السادسة مُصرَّحة لكلّ مهارة: {len(evaluated)} مُقيَّمة · "
            f"{len(unevaluated)} مُعلَنٌ أنّها غير مُقيَّمة"
        )


def main() -> int:
    if not POLICY.is_file():
        print(f"❌ سجلّ معايير المهارات مفقود: {POLICY.relative_to(REPO_ROOT)}")
        return 1
    try:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ `AGENT_SKILLS.json` ليس JSON صالحاً: {exc}")
        return 1

    agent_skills = _check_agent_skills(policy)
    _check_glossary(policy)
    _check_evaluation(policy, agent_skills)

    if _FAILURES:
        print(f"\n❌ معايير المهارات المفتوحة (D-271 L9/L10/L11): {len(_FAILURES)} انتهاكاً")
        return 1
    print("\n✅ معايير المهارات المفتوحة (D-271): معيارٌ مُطابَق · مسردٌ مُعلَن · قياسٌ مُصرَّح.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
