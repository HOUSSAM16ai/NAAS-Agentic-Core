"""يشغّل المُتحقِّق على حارسٍ **خارجيّ** مفتوح المصدر — لا على أهدافنا المرجعية.

**لماذا هذه الأداة:** `GATE_LEDGER.json` يكتب بخطّ يدنا سببَ بقاء `GATE_A_TECHNICAL`
في `ABSENT`: «القياس … مقيسٌ على **أهدافٍ مرجعية** لا على نظام طرفٍ ثالث». وهذا أوّل
سؤالٍ يطرحه مشترٍ: **هل يجد عللاً في شيءٍ لم تكتبه أنت؟**

**الهدف المختار** `better_profanity` — بمعايير مُعلَنة (§`TARGET`): مفتوح المصدر ·
يعمل محلّياً · حارسُ محتوىً نصّي · قابل للتثبيت. ⛔ **ولا مسبار على خدمةٍ مستضافة
لطرفٍ ثالث**: ذاك فحصٌ عدائيّ لنظامٍ حيّ لا نملكه، وليس بحثاً مشروعاً.

⛔ **يعيش خارج `naas_verifier/`** إلزاماً: الحزمة صفر-شبكة وصفر-تبعية بحكم
`check_naas_verifier_boundary`، ونتيجةُ هدفٍ خارجيّ تدخل **بياناتٍ** لا استيراداً.

⚠️ **وحدُّ الصدق الذي يسبق أيّ قراءة (D-227):** قيدُ اللغة في هذا الهدف **موثَّقٌ من
صانعه** («Not all languages are supported yet, such as *Chinese*»). فالمقيس هنا
**ليس ثغرةً غير مُفصَح عنها**، وادّعاءُ اكتشافٍ هنا كذبٌ يُكتشَف في أوّل مراجعة.
المقيس هو ما يلي، وهو مختلفٌ تماماً:

    الحارس **يقبل قاعدة حظرٍ لا يستطيع فرضها، ويؤكّد قبولها** — بلا خطأ ولا تحذير،
    والكلمة تظهر في `CENSOR_WORDSET`، و`contains_profanity` تُرجِع `False` أبداً.

وهذا بالضبط الفرق بين **مُصحِّح** يقرأ المخرَج النهائي فيقول «نظيف»، و**مُتحقِّق**
يقرأ المسار فيقول «سياستُك أُبطِلت صامتةً» (D-267 L3).

    python3.12 scripts/research/probe_external_guard.py
    python3.12 scripts/research/probe_external_guard.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(ROOT))

from naas_verifier.core.constraint import (
    Constraint,
    ConstraintSet,
    Dimension,
    Outcome,
)
from naas_verifier.core.trajectory import Step, Trajectory
from naas_verifier.core.verdict import Verdict, verify

REPORT = ROOT / "docs/research/EXTERNAL_GUARD_PROBE.json"

#: ⚠️ الهدف تبعيةٌ خارجية عمداً — لا تُثبَّت في المستودع ولا تدخل `requirements`.
INSTALL_HINT = (
    "   python3.12 -m venv /tmp/extguard\n"
    "   /tmp/extguard/bin/pip install better_profanity\n"
    "   /tmp/extguard/bin/python scripts/research/probe_external_guard.py --json"
)

#: معايير اختيار الهدف — مُعلَنة كي لا يُبدَّل الهدف حتى «ينجح» أحدُهم (D-228).
TARGET = {
    "package": "better_profanity",
    "why_ar": "حارسُ محتوىً نصّي مفتوح المصدر، يعمل محلّياً، بلا شبكة وبلا نموذج.",
    "selection_criteria_ar": [
        "مفتوح المصدر وقابل للقراءة — الآلية تُثبَت من المصدر لا تُخمَّن",
        "يعمل محلّياً بالكامل — ⛔ لا مسبار على خدمةٍ مستضافة لطرفٍ ثالث",
        "يقدّم عقداً صريحاً: أضف قاعدة حظر، ثمّ اسأل هل يُطابِق",
        "قابل للتثبيت في بيئةٍ نظيفة بلا تبعياتٍ ثقيلة",
    ],
    "vendor_documents_language_limit": True,
    "vendor_quote_en": "Not all languages are supported yet, such as *Chinese*.",
}

#: الأصناف القابلة للنشر وحدها (`publishable=true`). ⛔ المحجوبان لا يدخلان.
ARABIC_TERM = "غبي"
ASCII_CONTROL_TERM = "zzqq"


class ProbeError(RuntimeError):
    """⛔ يُرفَع صراحةً — ولا يُعاد تقريرٌ ناقصٌ يبدو كاملاً."""


def _load_target() -> object | None:
    """يُحمِّل الهدف الخارجي، أو `None` إن تعذّر — ⚠️ ولا يُدَّعى قياسٌ لم يجرِ."""
    try:
        from better_profanity import profanity
    except ImportError:
        return None
    return profanity


def _uncased_scripts_excluded() -> dict[str, object]:
    """يقيس **الآلية** لا العَرَض: أيّ فئات يونيكود يقبلها مُجزِّئ الهدف.

    النتيجة تُعمّم الأثر إلى ما وراء العربية — وهي أصدق وأوسع من «العربية مكسورة».
    """
    from better_profanity.constants import ALLOWED_CHARACTERS

    allowed = set(ALLOWED_CHARACTERS)
    categories: dict[str, int] = {}
    for char in allowed:
        if len(char) == 1:
            key = unicodedata.category(char)
            categories[key] = categories.get(key, 0) + 1

    samples = {
        "arabic": "غ",
        "hebrew": "א",
        "chinese": "中",
        "japanese_kana": "あ",
        "devanagari": "क",
        "latin": "a",
        "greek": "α",
        "cyrillic": "д",
    }
    return {
        "allowed_character_count": len(allowed),
        "unicode_categories_admitted": dict(sorted(categories.items(), key=lambda row: -row[1])),
        "script_representable": {
            name: {
                "category": unicodedata.category(char),
                "tokenizable": char in allowed,
            }
            for name, char in samples.items()
        },
        "mechanism_ar": (
            "قائمة الحروف المسموحة مبنيّة من فئات يونيكود Ll·Lu·Mc·Mn، والفئة Lo "
            "(حروف غير ذات حالة: عربية · عبرية · صينية · كانا · ديفاناغاري) "
            "مستبعَدةٌ عملياً — فحروفُها تعمل كفواصل كلماتٍ ولا تُشكّل رمزاً قابلاً "
            "للمطابقة. فالقاعدة تُقبَل ولا تُفرَض أبداً."
        ),
    }


def _observe(profanity: object, term: str) -> dict[str, object]:
    """يرصد سلوك الهدف الحقيقي لقاعدةٍ واحدة — كل حقلٍ مقروءٌ من تشغيل."""
    profanity.load_censor_words([term])  # type: ignore[attr-defined]
    wordset = {str(item) for item in profanity.CENSOR_WORDSET}  # type: ignore[attr-defined]
    return {
        "term": term,
        "rule_accepted_without_error": True,
        "term_present_in_wordset": term in wordset,
        "fires_on_bare_term": bool(
            profanity.contains_profanity(term)  # type: ignore[attr-defined]
        ),
        "censor_output": str(profanity.censor(term)),  # type: ignore[attr-defined]
    }


def _build_trajectory(observation: dict[str, object]) -> Trajectory:
    """يبني مساراً من سلوكٍ **مرصود** — لا من افتراض.

    الخطوتان تفصلان ما يخلطه المُصحِّح: قبولُ القاعدة شيء، وقابليتُها للفرض شيءٌ آخر.
    """
    accepted = bool(observation["term_present_in_wordset"])
    fired = bool(observation["fires_on_bare_term"])
    return Trajectory(
        trajectory_id="external/better_profanity/ar-norm-void",
        language="ar",
        steps=[
            Step(
                index=0,
                action="operator registers an Arabic blocklist rule",
                state_before="policy_empty",
                state_after="policy_registered" if accepted else "policy_rejected",
                tool="load_censor_words",
                tool_args={"words": [observation["term"]]},
                output="accepted" if accepted else "rejected",
            ),
            Step(
                index=1,
                action="guard screens the exact blocked term",
                state_before="policy_registered" if accepted else "policy_rejected",
                state_after="screened",
                tool="contains_profanity",
                tool_args={"text": observation["term"]},
                output="fired" if fired else "clean",
            ),
        ],
        final_output=str(observation["censor_output"]),
        metadata={"target": TARGET["package"]},
    )


def _predicate_rule_enforceable(trajectory: Trajectory) -> Outcome:
    """البُعد الوسطي: القاعدة المقبولة **يجب** أن تكون قابلةً للفرض.

    ⛔ هذا القيد بالضبط هو ما لا يستطيع المُصحِّح رؤيته: المخرَج النهائي «نظيف».
    """
    registered = any(step.output == "accepted" for step in trajectory.steps)
    fired = any(step.output == "fired" for step in trajectory.steps)
    if not registered:
        return Outcome.INCONCLUSIVE
    return Outcome.HOLDS if fired else Outcome.VIOLATED


def _predicate_states_legal(trajectory: Trajectory) -> Outcome:
    legal = {
        ("policy_empty", "policy_registered"),
        ("policy_empty", "policy_rejected"),
        ("policy_registered", "screened"),
        ("policy_rejected", "screened"),
    }
    return (
        Outcome.HOLDS if all(pair in legal for pair in trajectory.transitions) else Outcome.VIOLATED
    )


def _predicate_tools(trajectory: Trajectory) -> Outcome:
    expected = ("load_censor_words", "contains_profanity")
    return Outcome.HOLDS if trajectory.tools_used == expected else Outcome.VIOLATED


def _predicate_outputs_observable(trajectory: Trajectory) -> Outcome:
    return (
        Outcome.HOLDS
        if all(str(item).strip() for item in trajectory.outputs())
        else Outcome.VIOLATED
    )


def _predicate_final_censored(trajectory: Trajectory) -> Outcome:
    """المخرَج النهائي وحده — وهو **يمرّ** هنا، وذلك هو بيت القصيد.

    المُصحِّح يقف عند هذا القيد فيقول «نظيف»؛ والمُتحقِّق يقرأ البُعد الوسطي فيكشف
    أنّ السياسة أُبطِلت. القيد يُقاس بأن الحارس أعاد النصّ **كما هو** بلا حجب.
    """
    censored = "*" in trajectory.final_output
    return Outcome.HOLDS if censored else Outcome.VIOLATED


def _constraint_set() -> ConstraintSet:
    def _c(
        cid: str, dim: Dimension, desc: str, pred: Callable[[Trajectory], Outcome]
    ) -> Constraint:
        return Constraint(constraint_id=cid, dimension=dim, description=desc, predicate=pred)

    return ConstraintSet(
        constraints=(
            _c(
                "observable/outputs-present",
                Dimension.OBSERVABLE_OUTCOMES,
                "every observed step yields a non-empty output",
                _predicate_outputs_observable,
            ),
            _c(
                "intermediate/rule-enforceable",
                Dimension.INTERMEDIATE_CONSTRAINTS,
                "a rule the guard accepted must actually be enforceable",
                _predicate_rule_enforceable,
            ),
            _c(
                "state/legal-transitions",
                Dimension.STATE_TRANSITIONS,
                "policy lifecycle follows the declared transitions",
                _predicate_states_legal,
            ),
            _c(
                "tool/expected-sequence",
                Dimension.TOOL_USE,
                "registration precedes screening, in that order",
                _predicate_tools,
            ),
            _c(
                "final/term-censored",
                Dimension.FINAL_OUTCOME,
                "the blocked term does not survive verbatim in the output",
                _predicate_final_censored,
            ),
        )
    )


def _class_rows(profanity: object | None) -> list[dict[str, object]]:
    """صفٌّ لكلّ صنفٍ قابل للنشر — ⛔ وكلّ غيابٍ يُصرَّح بسببه (D-206 L11)."""
    rows: list[dict[str, object]] = []

    if profanity is None:
        verdict_payload: dict[str, object] | None = None
        observation: dict[str, object] | None = None
        ascii_control: dict[str, object] | None = None
        status = "target_unavailable"
    else:
        observation = _observe(profanity, ARABIC_TERM)
        ascii_control = _observe(profanity, ASCII_CONTROL_TERM)
        verdict: Verdict = verify(_build_trajectory(observation), _constraint_set())
        verdict_payload = verdict.as_dict()
        status = "measured"

    rows.append(
        {
            "class_id": "AR-NORM-VOID",
            "applicability": "applicable",
            "status": status,
            "observation": observation,
            "ascii_control": ascii_control,
            "control_meaning_ar": (
                "نفس الواجهة بمصطلحٍ ASCII **تُطابِق** — فالعطب ليس في إعدادنا "
                "ولا في كيفية استدعائنا، بل في تمثيل الحروف."
            ),
            "verdict": verdict_payload,
        }
    )
    rows.append(
        {
            "class_id": "AR-SUBSTR-COLLIDE",
            "applicability": "not_reachable",
            "status": "precondition_absent",
            "reason_ar": (
                "الصنف يقيس **فرطَ المطابقة** حين تلتصق سابقةٌ عربية بالمصطلح. وشرطه "
                "أن يكون المصطلح قابلاً للمطابقة أصلاً — وهو غير قابل هنا. ⛔ ولا "
                "يُقرأ ذلك سلامةً: الحارس لا يُفرِط لأنه لا يُطابِق شيئاً."
            ),
            "verdict": None,
        }
    )
    rows.append(
        {
            "class_id": "LANG-MODE-COLLAPSE",
            "applicability": "not_applicable",
            "status": "out_of_target_scope",
            "reason_ar": (
                "الصنف مشروطٌ بعتبة حجم مُوجِّهٍ وبوجود نموذج لغوي. والهدف قائمةُ حظرٍ "
                "ساكنة بلا نموذج وبلا مُوجِّه — فالصنف خارج نطاقه بنيوياً."
            ),
            "verdict": None,
        }
    )
    return rows


def probe() -> dict[str, object]:
    """يُعيد التقرير كاملاً. حتميّ: نفس البيئة تُعطي نفس الأرقام."""
    profanity = _load_target()
    mechanism = _uncased_scripts_excluded() if profanity is not None else None
    rows = _class_rows(profanity)
    measured = [row for row in rows if row["status"] == "measured"]
    violated = [
        row
        for row in measured
        if isinstance(row["verdict"], dict) and row["verdict"]["outcome"] == "violated"
    ]

    return {
        "$schema_version": "1",
        "decision": "D-285",
        "target": TARGET,
        "target_available": profanity is not None,
        "mechanism": mechanism,
        "classes": rows,
        "classes_measured": len(measured),
        "classes_violated": len(violated),
        "honest_limits_ar": [
            "⛔ قيدُ اللغة **موثَّقٌ من صانع الهدف** — فهذا ليس اكتشافَ ثغرةٍ مكتومة.",
            "المقيس: الحارس يقبل قاعدةً لا يفرضها ويؤكّد قبولها، بلا خطأٍ ولا تحذير.",
            "صنفٌ واحدٌ من ثلاثةٍ قابلٍ للقياس على هذا الهدف — والاثنان مُصرَّحان بسببهما.",
            "هدفٌ خارجيٌّ واحد ليس مسحاً للسوق. ⛔ ولا يُعمَّم منه حكمٌ على حرّاسٍ آخرين.",
            # ⛔ تصحيحُ ادّعاءٍ كِدتُ أرتكبه: القياس نفسه فنّده.
            "⛔ **ولا يُقال إنّ مُصحِّحاً كان سيفوت هذا**: البُعد النهائي مُنتهَكٌ هنا "
            "أيضاً، فاختبارٌ بسيط («حظرتُ س ثمّ أرسلتُ س، هل اشتعل؟») يكشفه. القيمة "
            "المُضافة على هذا الهدف **تشخيصية لا كشفية**: المُتحقِّق يسمّي القيد المنكسر "
            "(قاعدةٌ مقبولة غير قابلة للفرض) بدل «فشل الاختبار».",
        ],
        "reproduction_command": "python3.12 scripts/research/probe_external_guard.py --json",
    }


def _render(report: dict[str, object]) -> str:
    lines = [
        f"target            : {TARGET['package']} (open source, local, no network)",
        f"target available  : {report['target_available']}",
        f"classes measured  : {report['classes_measured']} / 3 publishable",
        f"classes violated  : {report['classes_violated']}",
        "",
    ]
    mechanism = report["mechanism"]
    if isinstance(mechanism, dict):
        scripts: dict[str, object] = mechanism["script_representable"]  # type: ignore[assignment]
        lines.append("script tokenizable by the target's own character class:")
        for name, info in scripts.items():
            assert isinstance(info, dict)
            mark = "yes" if info["tokenizable"] else "NO "
            lines.append(f"  {mark}  {name:14} (unicode category {info['category']})")
        lines.append("")

    rows: Sequence[dict[str, object]] = report["classes"]  # type: ignore[assignment]
    for row in rows:
        verdict = row["verdict"]
        outcome = verdict["outcome"] if isinstance(verdict, dict) else row["status"]
        lines.append(f"{row['class_id']:<20} {row['applicability']:<16} {outcome}")
        if isinstance(verdict, dict):
            for dim in verdict["dimensions"]:
                assert isinstance(dim, dict)
                lines.append(f"    {dim['dimension']:<26} {dim['outcome']}")
    lines += ["", "⛔ الحدود تُقرأ قبل الجدول لا بعده:"]
    limits: Sequence[str] = report["honest_limits_ar"]  # type: ignore[assignment]
    lines += [f"   - {item}" for item in limits]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="probe an external open-source guard")
    parser.add_argument("--json", action="store_true", help="اكتب التقرير الخام إلى القرص")
    args = parser.parse_args(argv)

    try:
        report = probe()
    except ProbeError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.json:
        # ⛔ تشغيلٌ بلا الهدف لا يدهس قياساً حقيقياً بتقريرٍ فارغ. الفشل يُقال
        # ولا يُكتب: أداةٌ تُتلف دليلها الملتزَم حين تُشغَّل في المُفسِّر الخطأ
        # أسوأ من أداةٍ لا تعمل، لأنّ الإتلاف صامت.
        if not report["target_available"]:
            print(
                "❌ الهدف الخارجي غير مثبَّت في هذا المُفسِّر — ولن يُكتب تقريرٌ فارغ\n"
                f"   فوق قياسٍ حقيقي.\n{INSTALL_HINT}",
                file=sys.stderr,
            )
            return 1
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"✅ {REPORT.relative_to(ROOT) if REPORT.is_relative_to(ROOT) else REPORT}")
    else:
        print(_render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
