"""بوّابة «الوسيط لا يعلن عن نفسه» (D-206 · L8 — جماليات الغياب).

## القاعدة

> الأداة الجيدة تختفي أثناء استعمالها، ولا تراها إلّا حين تتعطّل (هايدغر).

المنتج العادي يعلن عن نفسه باستمرار: «أنا هنا، وأنا أعمل، فتقبّلني كما أنا». والمعلّم
الجيّد يتراجع ليمنح فعل الطالب مساحته. فكلّ نصٍّ حتميّ يصل الطالب ويتحدّث عن **النظام**
(«سنشرح الآن…» · «سأقوم…» · «كنظام…») بدل أن يتحدّث عن **مسألته** هو احتكاكٌ زائد بين
الطالب وتفكيره.

## لماذا الآن — بدليلٍ من الإنتاج

في المحادثة 836 (`customer_messages`):

```
4598 assistant «سنشرح الآن خطوة الحدث المطلوب فقط مع ربطها بالواجهة مباشرة.»
4599 assistant «»                                            ← فارغة تماماً
```

إعلانُ أجندةٍ ثمّ **لا شيء**. الطالب سمع «سنشرح الآن» ولم يصله شرح. وهذا يجمع خرقَين:
إعلانُ الوسيط عن نفسه (L8)، ووعدٌ لا يصل (§0 — أسوأ من خطأ صريح).

## تعميمُ D-117 من حالةٍ إلى صنف

D-117 حظر عبارةً **واحدة** (`[توجيه تربوي]`) بعد كارثتها. هذه البوّابة تحظر **الصنف**:
كل خطاب ذاتٍ في النصّ الحتمي المُوجَّه للطالب. علاجُ العَرَض يُبقي الصنف — وهو الدرس
المتكرّر في ISS-128/138/139/141.

## ماذا تفحص

مسحٌ **بـAST على سلاسل النصّ وحدها** عبر المصدر المُركَّب للمعلّم الحتمي
(`TUTOR_SOURCE_FILES` — §6.7.أ: الفحص السلبي يقرأ المُركَّب لا الملفّ، وإلّا مرّ زوراً على
ملفٍّ تقلّص محتواه).

**لماذا AST لا مسحٌ نصّي:** القانون يخصّ ما **يصل الطالب**، لا ما نكتبه عن أنفسنا في
التعليقات. النسخة النصّية الأولى من هذه البوّابة رفضت التعليق الذي يشرح المنع نفسه —
فجعلت توثيقَ القاعدة خرقاً لها. والتعليق الذي يحفظ سببَ المنع أنفعُ من صمتٍ يُنسيه.

⚠️ **التمييز الجوهري:** «سأشرح على تمرين بكالوريا المرجعي **لأنك لم تُعطِ أرقام تمرينك**»
ليست خطاباً ذاتياً بل **تصريحاً إلزامياً** تفرضه D-191 (لئلّا يتعلّم الطالب مسألةً ليست
مسألته). الشفافية عن مصدر الأرقام (L11) ضدّ إعلان الأجندة (L8) — والبوّابة تفرّق بينهما
بقائمة سماحٍ مُعلَّلة، لا بحدس.

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.infrastructure.clients.orchestrator.tutor_sources import (  # noqa: E402
    TUTOR_SOURCE_FILES,
)

#: عبارات خطاب الذات المحظورة في النصّ الحتمي المُوجَّه للطالب.
_SELF_ANNOUNCEMENT: tuple[str, ...] = (
    "سنشرح الآن",
    "سأشرح لك الآن",
    "سنقوم الآن",
    "سأقوم الآن",
    "دعني أشرح",
    "دعني أوضح",
    "اسمح لي أن",
    "كنظام",
    "بصفتي",
    "أنا هنا لمساعدتك",
)

#: اعتذارٌ زائد — «التواضع المبالَغ فيه» الذي يضع صورة الأداة بين الطالب والفكرة.
_EXCESS_APOLOGY: tuple[str, ...] = (
    "أعتذر عن",
    "عذراً على",
    "آسف على",
    "المعذرة على",
)

#: استثناءات مُعلَّلة — كلٌّ بسببه المكتوب، لا سماحَ ضمني.
_ALLOWED: dict[str, str] = {
    "سأشرح على تمرين بكالوريا": (
        "تصريح D-191 الإلزامي عن مصدر الأرقام — شفافية (L11) لا إعلان أجندة (L8). "
        "بدونه يتعلّم الطالب مسألةً ليست مسألته (ISS-140)."
    ),
}

#: **دَين مُجمَّد — يتقلّص فقط** (سابقة D-105). نصوصٌ مرافقة تُعلن الأجندة، وُثّقت هنا
#: بدل أن تُصلَح في جولةٍ تحمل إصلاحاً تربوياً لمسارٍ آخر (سابقة D6/D-192: لا يُفكَّك
#: أخطرُ مسارٍ حيّ في جولةٍ مشغولة). كلٌّ منها مرشَّح لإعادة صياغة تتحدّث عن سؤال
#: الطالب لا عن نيّة النظام.
_FROZEN_DEBT: dict[str, str] = {
    "سنركّز الآن": "نصّ مرافق للبؤرة البصرية — مرشَّح لإعادة الصياغة.",
    "سنبدأ من فضاء العينة": "نصّ مرافق للبؤرة البصرية — مرشَّح لإعادة الصياغة.",
    "سنركّز على السحب المتتالي": "نصّ مرافق للبؤرة البصرية — مرشَّح لإعادة الصياغة.",
}


def _student_strings() -> list[tuple[str, int, str]]:
    """(المسار، السطر، النصّ) لكل سلسلة حرفية في المصدر المُركَّب.

    السلاسل وحدها — لا التعليقات ولا أسماء المتغيّرات. docstrings مُستثناة: هي توثيقٌ
    للمطوّر لا نصٌّ يصل الطالب، وإدراجُها يجعل شرحَ القاعدة خرقاً لها.
    """
    out: list[tuple[str, int, str]] = []
    for rel in TUTOR_SOURCE_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
            ):
                out.append((rel, node.lineno, node.value))
    return out


def main() -> int:
    """يفشل عند وجود خطاب ذاتٍ أو اعتذارٍ زائد في سلاسل المعلّم الحتمي."""
    strings = _student_strings()
    if not strings:
        print("❌ المصدر المُركَّب فارغ — تحقّق من TUTOR_SOURCE_FILES.")
        return 1

    violations = 0
    banned = _SELF_ANNOUNCEMENT + _EXCESS_APOLOGY

    for rel, lineno, value in strings:
        if any(allowed in value for allowed in _ALLOWED):
            continue
        if any(debt in value for debt in _FROZEN_DEBT):
            continue
        for phrase in banned:
            if phrase in value:
                violations += 1
                print(f"❌ خطاب ذاتٍ في نصّ المعلّم: {rel}:{lineno}")
                print(f"   العبارة: {phrase!r} داخل {value[:70]!r}")
                print("   الإصلاح: تحدّث عن مسألة الطالب لا عن نيّة النظام (L8).")

    # الدَّين ثنائي الاتجاه: عبارةٌ أُصلحت ولم تُحذف من الخريطة تُفشِل أيضاً (درس D-189).
    all_values = [value for _, _, value in strings]
    for phrase, reason in sorted(_FROZEN_DEBT.items()):
        if not any(phrase in value for value in all_values):
            violations += 1
            print(f"❌ دَين مُجمَّد لم يعد موجوداً: {phrase!r} ({reason})")
            print("   الإصلاح: احذف المدخل من `_FROZEN_DEBT` — الخريطة تتقلّص فقط.")

    if violations:
        print(f"\n❌ check_no_self_announcement: {violations} مخالفة.")
        return 1

    print("✅ check_no_self_announcement: الوسيط لا يعلن عن نفسه، والدَّين محصور.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
