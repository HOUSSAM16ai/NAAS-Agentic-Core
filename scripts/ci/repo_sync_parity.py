"""قياس التطابق بين المستودعين النظيرين — تقريرٌ حتميّ، بلا شبكة وبلا تخمين.

**لماذا هذا الملفّ (ISS-198):** رأس ``.github/workflows/repo-sync.yml`` كان يَعِد نصّاً بأنّه
``keeping the two repos 100% identical``، بينما تنفيذه يحمل ``on: push: branches: [main]``
و``git push origin HEAD:main --force`` — أي **فرعٌ واحد**. فكلّ مرجعٍ خارج ``main`` كان بلا
حارسٍ ولا مقياس: لا يُزامَن، ولا يُبلَّغ عن اختلافه، ولا يعرف قارئُ الوظيفة الخضراء أنّ ثمّة
سطحاً لم يُنظر إليه أصلاً. وهو **نفس صنف ISS-197 بمقياسٍ آخر**: تطابقٌ يُدَّعى ولا يُقاس —
والفرق أنّ ISS-197 كُشِف بعد سبعة أيامٍ و60 دفعة، وهذا لم يكن ليُكشَف أبداً لأنّ لا أحد ينظر.

**لماذا سكربت لا سطرُ ``diff`` داخل الـYAML:** منطقٌ في YAML لا يُختبَر إلّا بدفعةٍ حيّة إلى
``main``. هنا يُغذّى القياس بمخرَج ``git ls-remote --heads`` **المُلتقَط من الريموتين
الحقيقيَّين** ويُثبَت سلوكه على العدّاء المحلّي — بتجارب سلبية تُثبت أنّه **يُبلِّغ** عن
الانحراف لا أنّه «يعمل» فقط (D-270 L4).

**القاعدة الدائمة — التقرير لا يُفشِل:** الفرع الميزة العابر على جانبٍ واحد أمرٌ مشروع، وليس
انحرافاً يستحقّ ❌. وإفشالُ كلّ دفعةٍ لأجله يُدرّب الناس على تجاهل الوظيفة — وهو الخطر الذي
يحذّر منه رأس الـworkflow نفسه حرفيّاً (``failing every commit … trains people to ignore the
job``) والذي وقع فعلاً في ISS-197. فالمخرَج **معلومة لا حكم**، والخروج دائماً بالرمز 0،
والقرار للمُنادي — نفس عقد ``repo_sync_classify.py`` الشقيق.

الاستعمال:

    python3 scripts/ci/repo_sync_parity.py --local local.txt --peer peer.txt \\
        --peer-name Houssam-lab/NAAS-Agentic-Core

المخرَج: السطر الأوّل رمزُ الحالة من القائمة المغلقة، وما بعده تقريرُ Markdown جاهزٌ
لـ``GITHUB_STEP_SUMMARY``.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

#: الفرع **الوحيد** الذي تزامنه الوظيفة فعلاً. مشتقٌّ من تنفيذ الـworkflow لا من نيّته:
#: ``on: push: branches: [main]`` ثمّ ``git push origin HEAD:main --force``. تغييرُ نطاق
#: المزامنة يوجب تغيير هذه القيمة معه، وإلّا عاد الوعد يفارق التنفيذ من جديد.
SYNCED_REF = "main"

#: مرجعُ إنقاذ المحتوى الذي **تُنشئه الوظيفة نفسها** على النظير حين يُرفَض الدفع إلى ``main``
#: المحميّ (``RESCUE_REF`` في ``repo-sync.yml``). وجودُه على جانبٍ واحد ليس انحرافاً بل أثرٌ
#: مقصود لبنيةٍ عاملة — لكنّه **يُعلَن ولا يُسكَت**: يُعرَض في التقرير بحالته ولا يُحتسَب
#: انحرافاً (D-206 L11 — الاستثناء يُصرَّح بسببه، والصمت يُقرأ نجاحاً كاذباً).
RESCUE_REF = "mirror/main"

#: القائمة المغلقة لحالات التطابق. لا رمز خارجها — ``mostly-in-sync`` وأخواتها ممنوعة
#: نصّياً (نمط D-267 L6: آلة حالاتٍ حتمية لا عبارةٌ ضبابية).
IN_SYNC = "in_sync"
OUT_OF_CONTRACT = "out_of_contract"
MAIN_DIVERGED = "main_diverged"

STATUSES: tuple[str, ...] = (IN_SYNC, OUT_OF_CONTRACT, MAIN_DIVERGED)

_HEADS_PREFIX = "refs/heads/"


@dataclass(frozen=True)
class RefDelta:
    """اختلافُ مرجعٍ واحد بين الجانبين."""

    name: str
    local_sha: str | None
    peer_sha: str | None

    @property
    def kind(self) -> str:
        """``local_only`` · ``peer_only`` · ``diverged`` — قائمةٌ مغلقة كذلك."""
        if self.local_sha is None:
            return "peer_only"
        if self.peer_sha is None:
            return "local_only"
        return "diverged"


@dataclass
class ParityReport:
    """نتيجة القياس كاملةً — الحالة والانحرافات والاستثناء المُصرَّح به."""

    status: str
    local_main: str | None
    peer_main: str | None
    deltas: list[RefDelta] = field(default_factory=list)
    exempt: list[RefDelta] = field(default_factory=list)


def parse_heads(output: str) -> dict[str, str]:
    """يحوّل مخرَج ``git ls-remote --heads`` إلى ``{اسم الفرع: SHA}``.

    الأسطر التالفة أو غير المُنتمية لـ``refs/heads/`` تُتجاهَل بصمت **عن قصد**: مخرَج
    ``ls-remote`` قد يحمل تحذيراتٍ من git على stderr مدموجةً، وسطرٌ لا يطابق الشكل ليس
    مرجعاً. أمّا الغياب الكامل فيُعالَج في ``compare`` لا هنا.
    """
    heads: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        sha, ref = parts[0].strip(), parts[1].strip()
        if not ref.startswith(_HEADS_PREFIX) or not sha:
            continue
        heads[ref[len(_HEADS_PREFIX) :]] = sha
    return heads


def compare(local: dict[str, str], peer: dict[str, str]) -> ParityReport:
    """يقارن خريطتي الفروع ويُنتج التقرير.

    الترتيب جزءٌ من العقد: ``main`` يُفحَص **أوّلاً** ووحده يقرّر ``MAIN_DIVERGED``. فلو
    خُلط مع بقية المراجع لابتلع فرعٌ ميزةٌ عابر إشارةَ الانحراف الحقيقي الوحيدة التي تعني
    أنّ النسخة الاحتياطية لم تصل — وهي بالضبط الإشارة التي غابت سبعة أيام في ISS-197.
    """
    local_main = local.get(SYNCED_REF)
    peer_main = peer.get(SYNCED_REF)

    deltas: list[RefDelta] = []
    exempt: list[RefDelta] = []
    for name in sorted(set(local) | set(peer)):
        if name == SYNCED_REF:
            continue
        local_sha = local.get(name)
        peer_sha = peer.get(name)
        if local_sha == peer_sha:
            continue
        delta = RefDelta(name=name, local_sha=local_sha, peer_sha=peer_sha)
        # الاستثناء المنطوق: مرجع الإنقاذ الذي تُنشئه الوظيفة نفسها على النظير.
        # يُعرَض ولا يُحتسَب — وأيّ اسمٍ آخر يُحتسَب مهما بدا تشغيلياً.
        if name == RESCUE_REF and local_sha is None:
            exempt.append(delta)
        else:
            deltas.append(delta)

    if local_main != peer_main:
        status = MAIN_DIVERGED
    elif deltas:
        status = OUT_OF_CONTRACT
    else:
        status = IN_SYNC

    return ParityReport(
        status=status,
        local_main=local_main,
        peer_main=peer_main,
        deltas=deltas,
        exempt=exempt,
    )


def _short(sha: str | None) -> str:
    """صيغةُ عرضٍ قصيرة؛ و``—`` تعني **غياب المرجع** لا SHA فارغاً."""
    return f"`{sha[:7]}`" if sha else "—"


_HEADINGS = {
    IN_SYNC: "### ✅ Mirror parity — `main` in sync, nothing out of contract",
    OUT_OF_CONTRACT: "### ℹ️ Mirror parity — `main` in sync; refs outside the sync contract differ",
    MAIN_DIVERGED: "### ⚠️ Mirror parity — `main` DIVERGED",
}


def render(report: ParityReport, local_name: str, peer_name: str) -> str:
    """يصوغ التقرير بصيغة Markdown صالحة لملخّص التشغيل."""
    main_row = f"| `{SYNCED_REF}` (synchronized) "
    main_row += f"| {_short(report.local_main)} | {_short(report.peer_main)} |"
    lines = [_HEADINGS[report.status], ""]
    lines += [
        "| ref | " + local_name + " | " + peer_name + " |",
        "|---|---|---|",
        main_row,
    ]
    for delta in report.deltas + report.exempt:
        lines.append(f"| `{delta.name}` | {_short(delta.local_sha)} | {_short(delta.peer_sha)} |")
    lines.append("")

    if report.status == MAIN_DIVERGED:
        lines += [
            f"`{SYNCED_REF}` differs after the push step reported success. That is the one",
            "signal meaning the backup did not arrive — the signal that was missing for",
            "seven days in ISS-197. A concurrent peer push can produce it benignly, so this",
            "step reports and does not fail; confirm with `git ls-remote --heads` on both.",
            "",
        ]

    if report.deltas:
        lines += [
            f"The refs above other than `{SYNCED_REF}` are **outside the sync contract**:",
            f"this workflow synchronizes `{SYNCED_REF}` only, so nothing keeps them equal.",
            "They are reported, not failed — a transient feature branch on one side is",
            "legitimate, and failing every push for it trains people to ignore this job.",
            "",
        ]

    if report.exempt:
        lines += [
            f"`{RESCUE_REF}` is excluded by declaration, not by silence: this workflow",
            "creates it on the peer when a protected `main` rejects the push, so the work",
            "arrives instead of nothing arriving.",
            "",
        ]

    return "\n".join(lines)


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def main(argv: list[str] | None = None) -> int:
    """يقرأ مخرَجَي ``ls-remote`` ويطبع الحالة ثمّ التقرير. يخرج دائماً بالرمز 0."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", required=True, help="ls-remote --heads لهذا المستودع")
    parser.add_argument("--peer", required=True, help="ls-remote --heads للمستودع النظير")
    parser.add_argument("--local-name", default="this repository")
    parser.add_argument("--peer-name", default="peer")
    args = parser.parse_args(argv)

    report = compare(parse_heads(_read(args.local)), parse_heads(_read(args.peer)))
    print(report.status)
    print(render(report, args.local_name, args.peer_name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
