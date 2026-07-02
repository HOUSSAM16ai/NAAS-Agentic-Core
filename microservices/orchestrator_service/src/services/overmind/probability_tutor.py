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

الحالة المُعلنة بصدق (§6.6): **FLAGGED** خلف ``ORCHESTRATOR_PROB_TUTOR_ENABLED``
(افتراضي معطَّل) حتى التحقق الحي في Codespaces — قاعدة الصدق في roadmap M10.
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
        if not _is_tutoring_turn(question):
            return None
        comp = parse_composition(exercise_content)
        if comp is None:
            return None
        prior = [h for h in (history or []) if isinstance(h, str) and h.strip()]

        def _dup(text: str) -> bool:
            return any(_near_dup(text, p) for p in prior)

        ladder = (
            build_step(comp, None),
            build_step(comp, "ratio"),
            build_rescue(comp),
            "أنت تملك الآن كل المعطيات — جرّب بنفسك: ركّب البسط على المقام، "
            "وأخبرني ما قيمة P(A) التي حصلت عليها، وسأخبرك إن أصبت.",
        )
        for text in ladder:
            if not _dup(text):
                return text
        return None
    except Exception:
        return None


__all__ = [
    "build_rescue",
    "build_step",
    "deterministic_turn",
    "fmt_comb",
    "norm_for_dedup",
    "parse_composition",
]
