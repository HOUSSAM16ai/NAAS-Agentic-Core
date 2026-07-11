"""probability_tutor — معلّم الاحتمالات الحتمي داخل الـ orchestrator (M10-S2.1 / D-154).

أول خطوة هجرة متحقَّقة من roadmap M10-S2: **port مستقل** (نسخ، stdlib فقط — لا أي
import من ``app.*`` ولا من microservices أخرى؛ نفس نمط ``response_sanitizer.py``)
لسُلّم الكشف التدريجي الحتمي لمعلّم الاحتمالات (BAC-2024 وفئته):

- ``parse_composition``: مستخرج تركيبة الألوان المصغّر (أعداد عربية + ألوان + مجموع
  صريح) — **محصَّن ضد نثر الحل** (يقصّ عند علامات الحل — درس ISS-120) ومُتحقَّق
  ببوّابة المقامات المُصرَّح بها (خام ``N/M`` و LaTeX ``\\frac`` — درس D-152/D-153).
- ``fmt_comb``: توسيع المضروب بصيغة LaTeX (``$C_{n}^{k} = \\dfrac{...}{...} = fav$``)
  — KaTeX يُصيّرها LTR-معزولة (يقتل بعثرة bidi — ISS-121) وتَنجو بنيوياً من حجب D-113.
- ``build_step`` / ``build_rescue``: خطوات السُّلّم بصيغة **صفر كشف للنتيجة النهائية**
  (roadmap §7) — كل نصّ ينتهي بسؤال توليد؛ تركيب النسبة النهائية يولّده الطالب.
- ``deterministic_turn``: قرار الدور — دور تدريسي (حيرة/«كيف»/إجابة قصيرة) على محتوى
  محقون (D-103) ⇒ أول نصّ سُلّم **غير مكرَّر** (تطبيع محايد للحجب) — صفر LLM.

D-163 (Stage 2): سُدّت فجوة split-brain — الـ port اكتسب النصف التربوي (التحقّق
الرقمي ``verify_numeric_answer``، الاعتراف والتقدّم ``build_symbolic_step``، الـ probe
التشخيصي ``build_diagnostic_probe``، وتفعيل ``support_level`` عبر ``_ladder_for_support``).

الحالة المُعلنة بصدق (§6.6): **ACTIVE (افتراضي ON منذ D-163 Stage 3)** خلف
``ORCHESTRATOR_PROB_TUTOR_ENABLED`` — مُثبَت حياً على :8006
(``scripts/verify_m10s2_port_live.py`` — 7/7). رافعة الرجوع الفوري:
``ORCHESTRATOR_PROB_TUTOR_ENABLED=0`` (بلا deploy — نمط D-025).
"""

from __future__ import annotations

import math
import re

# ── علامات أقسام الحل (port مصغّر من exercise_retrieval — ISS-120: الاستخراج لا يرى نثر الحل) ──
_SOLUTION_MARKERS: tuple[str, ...] = (
    "## عناصر الإجابة",
    "## الإجابة النموذجية",
    "## الحل",
    "## الإجابة",
    "## شرح الحل",
    "## Solution",
    "## Model Answer",
)

#: الأعداد العربية الأساسية (port مصغّر).
_CARDINALS: dict[str, int] = {
    "كرتان": 2,
    "كرتين": 2,
    "ثلاث": 3,
    "ثلاثة": 3,
    "اربع": 4,
    "أربع": 4,
    "اربعة": 4,
    "أربعة": 4,
    "خمس": 5,
    "خمسة": 5,
    "ست": 6,
    "ستة": 6,
    "سبع": 7,
    "سبعة": 7,
    "ثمان": 8,
    "ثماني": 8,
    "تسع": 9,
    "تسعة": 9,
    "عشر": 10,
    "عشرة": 10,
}

#: مجموعات الألوان: (كلمات المطابقة، التسمية).
_COLORS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("حمراء", "حمر", "الحمراء"), "كرة حمراء"),
    (("بيضاء", "بيض", "البيضاء", "بيضاوان"), "كرة بيضاء"),
    (("خضراء", "خضر", "الخضراء"), "كرة خضراء"),
    (("زرقاء", "زرق", "الزرقاء", "زرقاوان"), "كرة زرقاء"),
    (("صفراء", "صفر", "الصفراء"), "كرة صفراء"),
    (("سوداء", "السوداء"), "كرة سوداء"),
)

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

#: إشارات الحيرة/الإجراء/الإجابة (دور تدريسي).
_CONFUSION = ("لم افهم", "لم أفهم", "مفهمتش", "ما فهمت", "لا افهم", "لا أفهم", "مش فاهم")
_PROCEDURE = ("كيف", "كيفاش", "ما هي الخطوات", "خطوات الحل", "طريقة الحساب")

#: D-162 (ISS-128) — port متكافئ مع monolith (بوّابة تكافؤ split-brain): بادئات
#: استفهامية تجعل الرسالة سؤالاً لا إجابةً/دوراً سُلّمياً. «هل» مستثناة عمداً
#: (D-155: «هل هي 14 من 165» إجابة تطلب تأكيداً).
QUESTION_OPENERS_NOT_ANSWERS: tuple[str, ...] = (
    "لماذا",
    "ليش",
    "علاش",
    "كيف",
    "كيفاش",
    "ماذا",
    "ما هو",
    "ما هي",
    "ماهو",
    "ماهي",
    "ما اسم",
    "ما الفرق",
    "ما معنى",
    "ما المقصود",
    "متى",
    "أين",
    "اين",
    "من أين",
    "من اين",
    "شنو",
    "واش",
)

#: D-162 (ISS-128): علامات نية التسمية («ماذا **نسمي** حساب 4 و 10؟») — الطالب
#: يطلب **اسم** العملية (التوافيق)، لا نتيجتها.
NAMING_MARKERS: tuple[str, ...] = (
    "نسمي",
    "ما اسم",
    "ما إسم",
    "يسمى",
    "تسمى",
    "تسميه",
    "تسمية",
)

#: D-155/D-163 (WP: parity): علامات قوالب الأسئلة التي نطرحها نحن — تُستنبط منها
#: بؤرة السؤال المعلّق (بلا أرقام ⇒ تَنجو من حجب D-113 في النسخة المحفوظة). port
#: متكافئ مع monolith ``_STEP_QUESTION_MARKERS`` (بوّابة تكافؤ split-brain).
STEP_QUESTION_MARKERS: tuple[tuple[str, str], ...] = (
    ("كم عدد **كل** الطرق الممكنة", "denominator"),
    ("كم عدد كل الطرق الممكنة", "denominator"),
    ("كيف تُكوّن منهما الاحتمال", "ratio"),
    ("فما قيمة P(A)", "ratio"),
    ("ما قيمة P(A) التي حصلت عليها", "ratio"),
    ("أيّ الألوان يمكن أن تعطينا", "colors"),
)

#: D-155/D-163: علامات أي خطوة تدريس بُثّت سابقاً (probe/سُلّم/إنقاذ) — تحكم
#: «التشخيص قبل الشرح» (لا probe مكرَّر بعد بدء التدريس).
TUTORING_STEP_MARKERS: tuple[str, ...] = (
    "الحالات الملائمة",
    "كم عدد **كل** الطرق",
    "كيف تُكوّن منهما الاحتمال",
    "أيّ الألوان يمكن أن تعطينا",
    "لنُكمل معاً خطوة بخطوة",
    "فما قيمة P(A)",
    "لنبدأ من فهمك أنت",
)

#: D-155: أول طلب مساعدة عام يستحق probe التشخيص قبل أي محتوى محسوب.
_FIRST_HELP_MARKERS: tuple[str, ...] = (
    "كيف افهم",
    "كيف نفهم",
    "كيف احل",
    "كيف نحل",
    "من اين ابدا",
    "من اين نبدا",
    "كيف ابدا",
    "كيف نبدا",
)


def is_question_not_answer(message: str) -> bool:
    """D-162 (ISS-128): بوّابة الفعل الكلامي — سؤال الطالب لا يُعامل كإجابة/دور سُلّمي.

    port متكافئ مع ``OrchestratorClient._is_question_not_answer`` (monolith) —
    العقلان لا يفترقان (بوّابة تكافؤ split-brain في ``check_pedagogical_os``).
    """
    try:
        q = _norm(message)
        if not q:
            return False
        if q.startswith("و "):
            q = q[2:].lstrip()
        if q.startswith(QUESTION_OPENERS_NOT_ANSWERS):
            return True
        return any(m in q for m in NAMING_MARKERS)
    except Exception:
        return False


def _norm(text: str) -> str:
    return (text or "").translate(_AR_DIGITS).strip().lower()


def norm_for_dedup(text: str) -> str:
    """تطبيع محايد لتحويل الحجب (ISS-121): الأرقام و«؟/?» ⇒ عنصر نائب موحّد."""
    return re.sub(r"[\d؟?]+", "#", _norm(text))


def _near_dup(a: str, b: str, *, threshold: float = 0.8) -> bool:
    na, nb = norm_for_dedup(a), norm_for_dedup(b)
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return True
    ta, tb = set(na.split()), set(nb.split())
    return bool(ta) and len(ta & tb) / len(ta) >= threshold


def _trim_solution(content: str) -> str:
    cut = None
    for marker in _SOLUTION_MARKERS:
        idx = content.find(marker)
        if idx != -1 and (cut is None or idx < cut):
            cut = idx
    return content[:cut].rstrip() if cut is not None else content


def _stated_denominators(text: str) -> set[int]:
    """المقامات المُصرَّح بها — خام ``N/M`` و LaTeX ``\\frac{N}{M}`` (درس D-152/D-153)."""
    denoms: set[int] = set()
    for _, den in re.findall(r"(\d+)\s*/\s*(\d+)", text):
        if int(den) > 1:
            denoms.add(int(den))
    for _, den in re.findall(r"\\d?frac\{(\d+)\}\{(\d+)\}", text):
        if int(den) > 1:
            denoms.add(int(den))
    return denoms


def parse_composition(exercise_content: str) -> dict | None:
    """يستخرج تركيبة الألوان من نص التمرين (أسئلة-فقط) — حتمي، fail-open ⇒ None."""
    try:
        text = _trim_solution(exercise_content or "")
        if not text:
            return None
        norm = _norm(text)
        tokens = re.split(r"[\s،,.\-؛:؟?!()\[\]{}«»\"'*\\$#_~`|/]+", norm)
        groups: list[dict] = []
        seen: set[str] = set()
        for i, tok in enumerate(tokens):
            for keywords, label in _COLORS:
                if label in seen or not any(kw in tok for kw in keywords):
                    continue
                count = None
                for back in range(1, 5):
                    j = i - back
                    if j < 0:
                        break
                    prev = tokens[j]
                    if prev in ("كرتان", "كرتين") or "بيضاوان" in tok or "زرقاوان" in tok:
                        count = 2
                        break
                    stripped = prev.lstrip("وفب")
                    if stripped.isdigit():
                        count = int(stripped)
                        break
                    if stripped in _CARDINALS:
                        count = _CARDINALS[stripped]
                        break
                if count and count > 0:
                    seen.add(label)
                    groups.append({"label": label, "count": count})
        if len(groups) < 2:
            return None
        n = sum(g["count"] for g in groups)
        # المجموع الصريح («11 كرة») يجب ألا يناقض مجموع الألوان.
        m = re.search(r"(\d{1,3})\s*(?:كرة|كرات)", norm)
        if m and int(m.group(1)) >= 3 and int(m.group(1)) != n:
            return None
        k = 3 if re.search(r"(?:3|ثلاث)\s*كرات", norm) else 2
        if k > n:
            return None
        total = math.comb(n, k)
        # بوّابة المقامات (D-152/D-153): تناقض مع المُصرَّح ⇒ رفض (صفر هلوسة).
        denoms = _stated_denominators(exercise_content)
        if denoms and not any(total % d == 0 or d % total == 0 for d in denoms):
            return None
        for g in groups:
            g["possible"] = g["count"] >= k
            g["fav"] = math.comb(g["count"], k) if g["possible"] else 0
        same = sum(g["fav"] for g in groups)
        return {"n": n, "k": k, "total": total, "same": same, "groups": groups}
    except Exception:
        return None


def fmt_comb(c: int, k: int, fav: int) -> str:
    r"""توسيع المضروب بصيغة LaTeX — LTR-معزول (bidi) وناجٍ من حجب D-113."""
    if k < 1 or c < k:
        return f"$C_{{{c}}}^{{{k}}} = {fav}$"
    num = r"\times ".join(str(c - i) for i in range(k))
    den = r"\times ".join(str(k - i) for i in range(k))
    return f"$C_{{{c}}}^{{{k}}} = \\dfrac{{{num}}}{{{den}}} = {fav}$"


def build_step(comp: dict, focus: str | None) -> str:
    """خطوة سُلّم تنتهي بسؤال توليد — صفر كشف للنتيجة النهائية."""
    k, n = comp["k"], comp["n"]
    if focus == "ratio":
        return (
            f"**كل الطرق الممكنة** لسحب {k} من {n}:\n\n"
            f"{fmt_comb(n, k, comp['total'])}\n\n"
            "الآن لديك البسط والمقام — كيف تُكوّن منهما الاحتمال؟"
        )
    lines = "\n".join(
        (
            f"- {g['label']}: {fmt_comb(g['count'], k, g['fav'])}"
            if g["possible"]
            else f"- {g['label']}: مستحيلة (العدد {g['count']} أصغر من {k})"
        )
        for g in comp["groups"]
    )
    favs = " + ".join(str(g["fav"]) for g in comp["groups"] if g["possible"])
    return (
        f"بما أننا اقتصرنا على الألوان الممكنة، نحسب **الحالات الملائمة**:\n\n"
        f"{lines}\n\n"
        f"نجمعها: ${favs} = {comp['same']}$\n\n"
        f"والآن سؤالٌ يقودنا للخطوة التالية: كم عدد **كل** الطرق الممكنة لسحب {k} كرات من {n}؟"
    )


def build_rescue(comp: dict) -> str:
    """إنقاذ الاستنفاد (D-129): كل المكوّنات scaffold — تركيب النسبة يولّده الطالب."""
    k, n = comp["k"], comp["n"]
    lines = "\n".join(
        (
            f"- {g['label']} (العدد {g['count']}): {fmt_comb(g['count'], k, g['fav'])}"
            if g["possible"]
            else f"- {g['label']} (العدد {g['count']}): مستحيلة (أقل من {k})"
        )
        for g in comp["groups"]
    )
    favs = " + ".join(str(g["fav"]) for g in comp["groups"] if g["possible"])
    return (
        f"لنُكمل معاً خطوة بخطوة حتى النهاية:\n\n"
        f"**الحالات الملائمة** ({k} كرات من نفس اللون) — لكل لون:\n\n"
        f"{lines}\n\n"
        f"نجمع الحالات الممكنة فقط: ${favs} = {comp['same']}$\n\n"
        f"**كل الطرق الممكنة** لسحب {k} من {n}:\n\n"
        f"{fmt_comb(n, k, comp['total'])}\n\n"
        "الآن أمامك كل المكوّنات — ركّب الاحتمال **بنفسك**: البسط على المقام. "
        "فما قيمة P(A) التي تحصل عليها؟"
    )


def detect_naming_question(question: str, comp: dict) -> bool:
    """D-162 (ISS-128): سؤال تسمية عن قيم خطوات التمرين — data-driven من ``comp``."""
    try:
        q = _norm(question)
        if not any(m in q for m in NAMING_MARKERS):
            return False
        nums = {int(m) for m in re.findall(r"\d+", q)}
        if nums:
            values = {int(comp["n"]), int(comp["k"]), int(comp["total"]), int(comp["same"])}
            for g in comp.get("groups", []):
                values.add(int(g["count"]))
                values.add(int(g["fav"]))
            return nums <= values
        return any(w in q for w in ("حساب", "الحساب", "العملية", "الطريقة", "c("))
    except Exception:
        return False


def build_naming_answer(comp: dict) -> str:
    """D-162 (ISS-128): يُجيب سؤال التسمية بالاسم (التوافيق) + إعادة طرح سؤال المقام.

    حتمي صفر-LLM؛ ``fmt_comb`` LaTeX يَنجو من حجب D-113 بنيوياً (D-154)، ونصّ
    إعادة السؤال يطابق قوالب الخطوات فيبقى السؤال المعلّق مرئياً للتحقّق.
    """
    k, n = comp["k"], comp["n"]
    possible = [g for g in comp.get("groups", []) if g.get("possible")]
    sample = ""
    if possible:
        g0 = possible[0]
        sample = "\n\nمثلاً القيمة التي وجدناها لهذه المجموعة هي عدد التوافيق: " + fmt_comb(
            int(g0["count"]), k, int(g0["fav"])
        )
    return (
        "هذا الحساب نسمّيه **التوافيق** (Combinations) ويُرمز له $C_{n}^{k}$: "
        "عدد طرق اختيار k عناصر من بين n عنصراً **دون اهتمام بالترتيب** — "
        "نستخدمه هنا لأن السحب «دفعة واحدة» لا ترتيب فيه."
        f"{sample}\n\n"
        f"والآن نعود لسؤالنا: كم عدد كل الطرق الممكنة لسحب {k} كرات من {n}؟"
    )


def extract_answer_numbers(text: str) -> set[int]:
    """D-155/D-163: أعداد رسالة الطالب (أرقام عربية ⇒ لاتينية أولاً)."""
    return {int(m) for m in re.findall(r"\d+", _norm(text))}


def pending_focus_from_history(history: list[str] | None) -> str | None:
    """D-155/D-163: بؤرة السؤال المعلّق — أيّ خطوة سألنا عنها الطالب آخر مرة؟

    history في الـ port قوائم نصوص مسبوقة بـ ``"Assistant: "`` — نفحص أحدث رسالة
    مساعد ضد قوالبنا (بلا أرقام ⇒ تَنجو من حجب D-113). port متكافئ مع monolith
    ``_pending_focus_from_history``.
    """
    for line in reversed(history or []):
        if not isinstance(line, str):
            continue
        if line.startswith("Assistant: ") or line.startswith("assistant:"):
            for marker, focus in STEP_QUESTION_MARKERS:
                if marker in line:
                    return focus
            return None
    return None


def has_prior_tutoring_step(history: list[str] | None) -> bool:
    """D-155/D-163: هل بُثّت أي خطوة تدريس (probe/سُلّم/إنقاذ) سابقاً؟"""
    for line in history or []:
        if (
            isinstance(line, str)
            and line.startswith(("Assistant: ", "assistant:"))
            and any(m in line for m in TUTORING_STEP_MARKERS)
        ):
            return True
    return False


def verify_numeric_answer(answer: str, comp: dict, pending_focus: str | None) -> str | None:
    """D-155/D-163: الحقيقة الرمزية تحكم إجابة الطالب **الرقمية**.

    الأرقام من ``comp`` حصراً (صفر hardcoding). يُرجِع: ``"final_ratio"`` (النسبة
    النهائية بأي صياغة) | ``"step_correct"`` (خطوة السؤال المعلّق) | ``"direction"``
    (اتجاه صحيح — «نفس الشئ مع 11») | ``None`` (غير مؤكَّدة ⇒ للمُقيّم). port متكافئ
    مع monolith ``_verify_numeric_answer`` (بوّابة تكافؤ split-brain).
    """
    try:
        # D-162 (ISS-128): بوّابة الفعل الكلامي أولاً — السؤال ليس إجابة أبداً
        # (عدا «هل» — D-155)؛ «ماذا نسمي حساب 4 و 10» يحمل أرقاماً لكنه سؤال.
        if is_question_not_answer(answer):
            return None
        nums = extract_answer_numbers(answer)
        if not nums:
            return None
        same = int(comp["same"])
        total = int(comp["total"])
        n = int(comp["n"])
        favs = {int(g["fav"]) for g in comp.get("groups", []) if g.get("possible")}
        if same in nums and total in nums:
            return "final_ratio"
        if pending_focus == "denominator":
            if total in nums:
                return "step_correct"
            if n in nums:  # «نفس الشئ مع 11» — الاتجاه صحيح، نُكمل الحساب معاً.
                return "direction"
            return None
        if pending_focus in (None, "numerator") and (same in nums or (favs and favs <= nums)):
            return "step_correct"
        return None
    except Exception:
        return None


def build_diagnostic_probe(comp: dict) -> str:
    """D-155/D-163: سؤال تشخيصي واحد قبل أي محتوى محسوب — «التشخيص قبل الشرح».

    صفر قيم محسوبة (لا C، لا مجاميع) — الطالب يولّد بصيرة «البيضاء مستحيلة» بنفسه
    (generation effect). يَنجو من حجب D-113 بنيوياً. port متكافئ مع monolith.
    """
    k = int(comp["k"])
    parts = "، ".join(
        f"{g['count']} {str(g['label']).replace('كرة ', '')}" for g in comp.get("groups", [])
    )
    return (
        f"لنبدأ من فهمك أنت — نسحب {k} كرات دفعة واحدة من كيس فيه: {parts}.\n\n"
        f"سؤال واحد قبل أي حساب: أيّ الألوان يمكن أن تعطينا {k} كرات "
        f"من نفس اللون؟ ولماذا؟"
    )


def build_symbolic_step(comp: dict, focus: str | None, *, acknowledge: bool = False) -> str:
    """D-155/D-163: الخطوة الرمزية المتدرّجة — اعتراف + تقدّم (لا الحل كاملاً).

    عند إجابة صحيحة نكشف **خطوة المفهوم الحالي** + سؤال المتابعة، يبقى السُّلّم
    السقراطي حياً. يَنجو من حجب D-113. port متكافئ مع monolith ``_build_symbolic_step``.
    """
    prefix = "إجابتك في الطريق الصحيح — " if acknowledge else ""
    n, k, total = comp["n"], comp["k"], comp["total"]
    if focus == "ratio":
        return (
            f"{prefix}**كل الطرق الممكنة** لسحب {k} من {n}:\n\n"
            f"{fmt_comb(n, k, total)}\n\n"
            f"الآن لديك البسط والمقام — كيف تُكوّن منهما الاحتمال؟"
        )
    # الافتراضي: خطوة البسط (الحالات الملائمة) — الأكثر شيوعاً بعد فهم «نفس اللون».
    return f"{prefix}{build_step(comp, None)}"


def _ladder_for_support(comp: dict, support_level: int) -> tuple[str, ...]:
    """D-115/D-163: مستوى الدعم يشكّل السُّلّم (المعامل لم يعد ميتاً).

    القاعدة تحفظ **كل** الرُّتب للجميع (لا إسقاط سقالة ⇒ لا فقدان قدرة): الطالب
    الواثق (≥ 4) يتلقّى تلميحاً افتتاحياً أخفّ **يسبق** السقالة الكاملة ليقود
    نفسه؛ المتعثّر (≤ 3) يبدأ مباشرةً بخطوة البسط الكاملة. نظير D-115 (عمق الدعم).
    """
    base = (
        build_step(comp, None),
        build_step(comp, "ratio"),
        build_rescue(comp),
        "أنت تملك الآن كل المعطيات — جرّب بنفسك: ركّب البسط على المقام، "
        "وأخبرني ما قيمة P(A) التي حصلت عليها، وسأخبرك إن أصبت.",
    )
    try:
        lvl = int(support_level)
    except (TypeError, ValueError):
        lvl = 3
    if lvl >= 4:
        k = int(comp["k"])
        light = (
            "لنبدأ بتلميح خفيف: ركّز على الألوان الممكنة فقط — أيّ الألوان عددها "
            f"يكفي لسحب {k} كرات من نفس اللون؟ ابدأ بعدّها، وسأرافقك خطوةً بخطوة."
        )
        return (light, *base)
    return base


def _is_tutoring_turn(question: str) -> bool:
    """دور تدريسي: حيرة مجرّدة، «كيف»، أو إجابة قصيرة — لا طلب شرح غني (للـ LLM)."""
    q = _norm(question)
    if not q or len(q) > 200:
        return False
    if any(m in q for m in _CONFUSION) or any(q.startswith(m) or m in q for m in _PROCEDURE):
        return True
    # إجابة قصيرة (≤ 6 كلمات، لا تبدأ بأداة استفهام طويلة).
    return len(q.split()) <= 6 and not q.endswith("؟")


def deterministic_turn(
    question: str,
    exercise_content: str,
    history: list[str] | None = None,
    support_level: int = 5,
) -> str | None:
    """قرار الدور الحتمي: أول نصّ سُلّم **غير مكرَّر** أو None (fail-open ⇒ LLM).

    السُّلّم: خطوة البسط ⇒ خطوة المقام ⇒ الإنقاذ ⇒ مُوجّه توليد. التكرار يُقاس
    بتطبيع محايد للحجب ضد كل أسطر الـ history (لا بثّ مكرَّر بنيوياً — ISS-121).
    """
    try:
        comp = parse_composition(exercise_content)
        if comp is None:
            return None
        prior = [h for h in (history or []) if isinstance(h, str) and h.strip()]

        def _dup(text: str) -> bool:
            return any(_near_dup(text, p) for p in prior)

        # D-162 (ISS-128): بوّابة الفعل الكلامي — سؤال التسمية يُجاب بالاسم (حتمي)،
        # وأي سؤال آخر غير إجرائي («ماذا/لماذا/ما هو...») لا يدخل السُّلّم الأعمى
        # (يسقط للـ LLM المحروس). أسئلة «كيف/كيفاش» الإجرائية تبقى للسُّلّم (غايته).
        # port متكافئ مع monolith `_cognitive_turn` (بوّابة تكافؤ split-brain).
        if detect_naming_question(question, comp):
            _naming = build_naming_answer(comp)
            return _naming if not _dup(_naming) else None
        if is_question_not_answer(question) and not _norm(question).startswith(("كيف", "كيفاش")):
            return None

        # D-155/D-163: التحقّق الرقمي — إجابة الطالب الصحيحة تُعترَف وتتقدّم (لا يُعاد
        # سؤال ما أُجيب للتو). يسبق السُّلّم الأعمى — «هل هي 14 من 165» إجابة لا حيرة.
        _pending = pending_focus_from_history(prior)
        _verdict = verify_numeric_answer(question, comp, _pending)
        if _verdict == "final_ratio":
            _ack = (
                "أحسنت! ✅ إجابتك صحيحة تماماً: هذا هو احتمال الحادثة الأولى. "
                "الآن سؤالٌ يقودنا للحادثة التالية: متى يكون جداء ثلاثة أعداد فردياً؟"
            )
            return _ack if not _dup(_ack) else None
        if _verdict in ("step_correct", "direction"):
            _nxt = "ratio" if _pending == "denominator" else None
            _step = build_symbolic_step(comp, _nxt, acknowledge=True)
            if not _dup(_step):
                return _step

        if not _is_tutoring_turn(question):
            return None

        # D-155/D-163: التشخيص قبل الشرح — أول طلب مساعدة عام (بلا خطوة تدريس سابقة)
        # ⇒ سؤال تشخيصي واحد (صفر قيم محسوبة) يقود الطالب لبصيرة «البيضاء مستحيلة».
        _q = _norm(question)
        if any(m in _q for m in _FIRST_HELP_MARKERS) and not has_prior_tutoring_step(prior):
            _probe = build_diagnostic_probe(comp)
            if not _dup(_probe):
                return _probe

        # D-115/D-163: مستوى الدعم يشكّل السُّلّم (تلميح افتتاحي للواثق — لا إسقاط رُتبة).
        for text in _ladder_for_support(comp, support_level):
            if not _dup(text):
                return text
        return None
    except Exception:
        return None


__all__ = [
    "build_diagnostic_probe",
    "build_naming_answer",
    "build_rescue",
    "build_step",
    "build_symbolic_step",
    "detect_naming_question",
    "deterministic_turn",
    "extract_answer_numbers",
    "fmt_comb",
    "has_prior_tutoring_step",
    "is_question_not_answer",
    "norm_for_dedup",
    "parse_composition",
    "pending_focus_from_history",
    "verify_numeric_answer",
]
