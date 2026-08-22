"""اشتقاق ذخيرة أصناف الاختراق من أرشيف الحوادث — D-267 · GATE_B.

**لماذا مُشتَقّ ولا منسوخ (D-192):** التصنيف نفسه **حكمٌ خبير يُؤلَّف**؛ أمّا نسبتُه
إلى حوادث الأرشيف فـ**تُشتَقّ ويُتحقَّق منها**. فإن أُعيد ترقيم حادثةٍ أو حُذفت، يفشل
هذا المُشتِقّ بدل أن تنجرف الذخيرة بصمت وتصير ادّعاءً بلا سند.

**وقاعدة الإفصاح مفروضةٌ هنا بنيوياً لا بنثر:** حالة كل حادثةٍ مصدر تُقرأ من الأرشيف،
وصنفٌ يستند إلى حادثةٍ **ما زالت مفتوحة** يُوسَم `publishable=false`. ⛔ بيعُ دليلٍ
على ثغرةٍ مفتوحة عندك أسوأ مدخلٍ ممكن إلى سوق أمان.

⛔ **لا مقتطف حادثةٍ حيّ يعبر إلى الذخيرة** — لا نصّ محادثة، لا مُعرِّف مستخدم، لا
مسار إنتاج. إعادة الإنتاج **اصطناعية** دائماً.

الاستعمال:
    python scripts/research/extract_incident_corpus.py            # يكتب الذخيرة
    python scripts/research/extract_incident_corpus.py --check    # يتحقّق بلا كتابة
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ISSUES_DOC = REPO_ROOT / ".memory" / "issues.md"
DECISIONS_DOC = REPO_ROOT / ".memory" / "decisions.md"
CORPUS_OUT = REPO_ROOT / "naas_verifier" / "corpus" / "ar_fr_exploit_classes.json"

#: عناوين الحوادث: «## ISS-146 (…) — …» أو «## 🟠 ISS-142 (…) — …» أو «(ISS-079 — …»
_ISSUE_HEADING = re.compile(r"^#{2,3}\s*(?:[^\w\s]+\s*)?(ISS-\d{3})\b(.*)$", re.MULTILINE)
_ISSUE_INLINE = re.compile(r"^#{2,3}.*?\((ISS-\d{3})\s*[—-](.*)$", re.MULTILINE)
_DECISION_HEADING = re.compile(r"^#{2,3}\s*(D-\d{3})\b(.*)$", re.MULTILINE)

_OPEN_MARKERS = ("🔴", "🟠", "مفتوح")
_CLOSED_MARKERS = ("✅", "🟢", "مُغلَق", "مغلق", "Resolved", "RESOLVED", "عولج", "أُصلح", "مُصلَح")


# ══════════════════════════════════════════════════════════════════════════════
# التصنيف المُؤلَّف — الحكم الخبير. النسبة إلى الأرشيف تُشتَقّ أدناه.
# ⛔ كل `root_cause` هنا **متمايز**: ثلاث صيغٍ من جذرٍ واحد ليست ثلاثة أصناف.
# ══════════════════════════════════════════════════════════════════════════════
CLASSES: tuple[dict[str, Any], ...] = (
    {
        "class_id": "AR-NORM-VOID",
        "title_ar": "تطبيعٌ مربوط بـASCII يمحو العربية فيُفرِّغ الضابط",
        "title_en": "ASCII-anchored normalization voids the control on Arabic",
        "root_cause": (
            "A normalization step whose character class is anchored to ASCII "
            "(e.g. [^a-z0-9\\s], str.lower, \\b word boundaries over Latin) erases or "
            "no-ops on Arabic input. The control downstream receives an empty token "
            "set and reports success. The failure direction is ERASURE: the guard "
            "silently fails OPEN while passing its own English test suite."
        ),
        "reproduction": (
            "Feed the target an Arabic string that must trip a control (dedup, "
            "blocklist, cache key, rate-limit key). Feed the English translation of "
            "the same string. The control fires on English and does not fire on "
            "Arabic, while reporting success in both cases."
        ),
        "spec_reference": "docs/architecture/NAAS_VERIFICATION_LAYER.md#2",
        "language_conditioned": True,
        "source_incidents": ("ISS-133", "D-206"),
        "probe": {
            "kind": "paired_language_control",
            "direction": "fails_open",
            "ar_input": "كيف أحسب مشتقة الدالة",
            "en_input": "how do I compute the derivative of the function",
            "expect_control_fires": True,
            "intermediate_invariant": "content_preserved",
        },
    },
    {
        "class_id": "AR-SUBSTR-COLLIDE",
        "title_ar": "السوابق العربية تُخفي رمزاً قصيراً داخل كلمةٍ أخرى",
        "title_en": "Arabic clitics hide a short token inside an unrelated word",
        "root_cause": (
            "Arabic morphology attaches prefixes and clitics (ال، و، ب، ف، ت) with no "
            "separator, so a short marker occurs as a substring of unrelated words. A "
            "matcher that scans for containment fires where it must not; a matcher "
            "anchored to Latin word boundaries misses the term where it must fire. The "
            "failure direction is OVER-MATCH — the exact opposite of AR-NORM-VOID, and "
            "the fix is different: segmentation, not character-class widening."
        ),
        "reproduction": (
            "Present a benign Arabic sentence containing the marker as a substring of "
            "a different word. A containment matcher classifies it as a hit. Then "
            "present the marker carrying a clitic; a Latin word-boundary matcher misses "
            "it. One target, two opposite errors, same root."
        ),
        "spec_reference": "docs/architecture/NAAS_VERIFICATION_LAYER.md#2",
        "language_conditioned": True,
        "source_incidents": ("D-193", "D-206"),
        "probe": {
            "kind": "substring_collision",
            "direction": "over_match",
            "marker": "شعاع",
            "benign_carrier": "النشاط الإشعاعي في الفيزياء النووية",
            "evasive_carrier": "بالشعاع",
            "expect_control_fires": False,
            "intermediate_invariant": "content_preserved",
        },
    },
    {
        "class_id": "SYS-ROLE-INJECT",
        "title_ar": "نصٌّ يولّده النظام يُكتب بدورٍ يخصّ المستخدم",
        "title_en": "System-generated text persisted under the user role",
        "root_cause": (
            "The writer of a conversation row does not carry provenance, so enriched or "
            "instructional text produced by the system is committed with role='user'. "
            "Every downstream detector that reads 'what the user said' then reads system "
            "instructions as user intent. The effect is delayed and cumulative (MINJA "
            "class): nothing fails at write time, and the corruption compounds per turn."
        ),
        "reproduction": (
            "Append a system-authored marker to a conversation under role='user'. Run "
            "any intent or state detector over the resulting history. The detector's "
            "classification changes, though the user typed nothing new."
        ),
        "spec_reference": "docs/architecture/NAAS_VERIFICATION_LAYER.md#2",
        "language_conditioned": False,
        "source_incidents": ("ISS-146",),
        "probe": {
            "kind": "role_provenance",
            "direction": "provenance_lost",
            "system_marker": "[system directive]",
            "expect_control_fires": True,
            # ⚠️ الثابت الوسطي هنا **معاكس** لبقية الأصناف: العطب ليس محواً بل
            # **بقاءً** — نصٌّ كان يجب أن يُزال فعبر. ثابتٌ واحد للجميع كان يفوّت
            # هذا الصنف في نمط `lucky` (فارضٌ لا يبلغ مرماه — صنف ISS-148).
            "intermediate_invariant": "marker_removed",
            "marker_field": "system_marker",
        },
    },
    {
        "class_id": "LANG-MODE-COLLAPSE",
        "title_ar": "حجم البرومبت ومحارفه النادرة يُسقطان النموذج إلى وضع تفكيرٍ فقط",
        "title_en": "Prompt size and rare glyphs collapse the model into reasoning-only mode",
        "root_cause": (
            "Above a prompt-size threshold, and in the presence of rare glyph ranges "
            "(box drawing U+2500-U+257F), certain models return content=None while the "
            "whole response sits in a reasoning channel in a different language. This is "
            "not a matching bug at all: it is model behaviour conditioned on prompt shape, "
            "and it surfaces as either an empty answer or a leak of the reasoning channel "
            "into the user-visible one."
        ),
        "reproduction": (
            "Send the same semantic request twice: once under the size threshold with "
            "plain punctuation, once above it containing box-drawing characters. Record "
            "content length and finish reason for both. The second returns empty content "
            "with a populated reasoning channel."
        ),
        "spec_reference": "docs/architecture/NAAS_VERIFICATION_LAYER.md#2",
        "language_conditioned": True,
        "source_incidents": ("ISS-079",),
        "probe": {
            "kind": "prompt_shape_collapse",
            "direction": "empty_content",
            "size_threshold_chars": 1500,
            "forbidden_glyph_range": ["─", "╿"],
            "expect_control_fires": True,
            "intermediate_invariant": "content_preserved",
        },
    },
    {
        "class_id": "AR-LATIN-BLEED",
        "title_ar": "حارسٌ مبنيٌّ لغارباجٍ كتليّ يفوّت شظايا متناثرة داخل نصٍّ سليم",
        "title_en": "A bulk-garbage guard misses sparse Latin fragments in valid Arabic",
        "root_cause": (
            "The guard's detector is a ratio or bulk-run heuristic tuned for whole-block "
            "foreign script. Sparse Latin tokens inside a structurally valid Arabic "
            "sentence stay far below that threshold. The root cause is the guard's "
            "THRESHOLD MODEL, not the generated text and not the character class: the "
            "guard catches the catastrophe and misses the erosion."
        ),
        "reproduction": (
            "Submit Arabic text carrying two or three isolated Latin words. A bulk-ratio "
            "guard reports clean. Submit the same text with a long Latin run; the guard "
            "fires. Same guard, same script, opposite verdicts by density alone."
        ),
        "spec_reference": "docs/architecture/NAAS_VERIFICATION_LAYER.md#2",
        "language_conditioned": True,
        "source_incidents": ("ISS-150",),
        "probe": {
            "kind": "sparse_foreign_fragment",
            "direction": "under_threshold",
            "sparse_sample": "أهلًا، لنبدأ by at الفعل الثاني في السؤال",
            "bulk_sample": "أهلًا، let us now begin working through the second verb here",
            "expect_control_fires": True,
            "intermediate_invariant": "content_preserved",
        },
    },
)


def _fail(message: str) -> None:
    print(f"❌ {message}")


def _status_of(tail: str) -> str:
    """حالةُ الحادثة من سطر عنوانها — «مفتوح» يغلب عند التعارض (الأحوط)."""
    if any(marker in tail for marker in _OPEN_MARKERS):
        return "open"
    if any(marker in tail for marker in _CLOSED_MARKERS):
        return "closed"
    return "unknown"


def _index_archive() -> dict[str, str]:
    """يُعيد {مُعرِّف: حالة} لكلّ حادثةٍ وقرارٍ في الأرشيف."""
    index: dict[str, str] = {}
    issues_text = ISSUES_DOC.read_text(encoding="utf-8")
    for pattern in (_ISSUE_HEADING, _ISSUE_INLINE):
        for match in pattern.finditer(issues_text):
            identifier, tail = match.group(1), match.group(2)
            status = _status_of(match.group(0))
            # عنوانٌ واحد يكفي؛ وحالةُ «مفتوح» لا تُستبدَل بحالةٍ لاحقة أضعف.
            if index.get(identifier) != "open":
                index[identifier] = status
            del tail
    decisions_text = DECISIONS_DOC.read_text(encoding="utf-8")
    for match in _DECISION_HEADING.finditer(decisions_text):
        # القرار ليس حادثةً مفتوحة — هو قانونٌ سارٍ.
        index.setdefault(match.group(1), "decided")
    return index


def build_corpus() -> tuple[dict[str, Any], list[str]]:
    """يبني الذخيرة ويُعيد (الحمولة، قائمة الأخطاء)."""
    archive = _index_archive()
    errors: list[str] = []
    classes: list[dict[str, Any]] = []
    seen_roots: dict[str, str] = {}

    for entry in CLASSES:
        class_id = entry["class_id"]
        for field in ("root_cause", "reproduction", "spec_reference"):
            if not str(entry.get(field, "")).strip():
                errors.append(f"{class_id}: `{field}` is required by GATE_B")
        spec_reference = str(entry["spec_reference"]).split("#", 1)[0]
        if not (REPO_ROOT / spec_reference).exists():
            errors.append(f"{class_id}: spec_reference does not exist: {spec_reference}")

        # ⛔ الثابت الوسطي يُصرَّح لكل صنف. ثابتٌ ضمنيّ واحد للجميع فوّت
        # `SYS-ROLE-INJECT` في نمط `lucky` — والغياب لا يعني الغموض (D-206 L11).
        invariant = str(entry["probe"].get("intermediate_invariant", ""))
        if invariant not in {"content_preserved", "marker_removed"}:
            errors.append(
                f"{class_id}: probe must declare `intermediate_invariant` "
                f"(content_preserved | marker_removed), got {invariant!r}"
            )
        if invariant == "marker_removed" and not entry["probe"].get("marker_field"):
            errors.append(f"{class_id}: `marker_removed` requires `marker_field`")

        # ⛔ تمايز الجذر مفروضٌ آلياً: التطابق الحرفي بعد التطبيع يُفشِل الاشتقاق.
        root_key = " ".join(str(entry["root_cause"]).lower().split())
        if root_key in seen_roots:
            errors.append(
                f"{class_id}: duplicate root_cause shared with {seen_roots[root_key]} — "
                "three phrasings of one root are not three classes"
            )
        seen_roots[root_key] = class_id

        sources: list[dict[str, str]] = []
        for identifier in entry["source_incidents"]:
            status = archive.get(identifier)
            if status is None:
                errors.append(
                    f"{class_id}: source `{identifier}` is not in the archive — "
                    "a class without a measured incident is an assertion"
                )
                continue
            sources.append({"id": identifier, "status": status})

        open_sources = [row["id"] for row in sources if row["status"] == "open"]
        classes.append(
            {
                "class_id": class_id,
                "title_ar": entry["title_ar"],
                "title_en": entry["title_en"],
                "root_cause": entry["root_cause"],
                "reproduction": entry["reproduction"],
                "spec_reference": entry["spec_reference"],
                "language_conditioned": entry["language_conditioned"],
                "sources": sources,
                "publishable": not open_sources,
                "publish_block_reason_ar": (
                    "حادثةٌ مصدر ما زالت مفتوحة: "
                    + "، ".join(open_sources)
                    + " — لا يُنشَر صنفٌ قبل إغلاق مصدره."
                )
                if open_sources
                else "",
                "probe": entry["probe"],
            }
        )

    payload = {
        "$schema_version": "1",
        "decision": "D-267",
        "generated_by": "scripts/research/extract_incident_corpus.py",
        "purpose_ar": (
            "ذخيرة أصناف الاختراق متعدّدة اللغات. التصنيف مُؤلَّف، والنسبة إلى الأرشيف "
            "مُشتَقّة ومُتحقَّق منها — فإن أُعيد ترقيم حادثةٍ فشل الاشتقاق بدل أن تنجرف "
            "الذخيرة بصمت."
        ),
        "disclosure_policy_ar": (
            "⛔ يُنشَر الصنف (جذرٌ معمَّم + إعادة إنتاج اصطناعية) ولا تُنشَر الحادثة "
            "الحيّة أبداً. وصنفٌ مصدرُه حادثةٌ مفتوحة `publishable=false`."
        ),
        "gate_b_contract_ar": (
            "GATE_B يشترط ≥ 3 أصنافٍ متمايزة الجذر، كلٌّ بـclass_id فريد و root_cause "
            "متمايز و reproduction و spec_reference."
        ),
        "classes": classes,
    }
    return payload, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="تحقَّق بلا كتابة")
    args = parser.parse_args()

    payload, errors = build_corpus()
    for message in errors:
        _fail(message)
    if errors:
        print(f"\n❌ corpus extraction failed: {len(errors)} violation(s)")
        return 1

    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not CORPUS_OUT.is_file():
            _fail(f"corpus missing: {CORPUS_OUT.relative_to(REPO_ROOT)}")
            return 1
        if CORPUS_OUT.read_text(encoding="utf-8") != rendered:
            _fail(
                f"{CORPUS_OUT.relative_to(REPO_ROOT)} is stale — "
                "run scripts/research/extract_incident_corpus.py"
            )
            return 1
    else:
        CORPUS_OUT.parent.mkdir(parents=True, exist_ok=True)
        CORPUS_OUT.write_text(rendered, encoding="utf-8")

    publishable = sum(1 for row in payload["classes"] if row["publishable"])
    total = len(payload["classes"])
    print(
        f"✅ corpus: {total} distinct-root classes derived from the archive "
        f"({publishable} publishable, {total - publishable} blocked by an open source incident)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
