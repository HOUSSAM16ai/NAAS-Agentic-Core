"""اختبارات قياس التطابق بين المستودعين النظيرين (ISS-198).

مصدرُ البيانات مُصرَّحٌ به لكلّ عيّنة، فلا يُقرأ المُختلَق دليلاً على الواقع:

* ``LOCAL_HEADS_LIVE`` و``PEER_HEADS_LIVE`` **منقولان حرفيّاً** من مخرَج
  ``git ls-remote --heads`` على الريموتين في 2026-08-30.
* ``LOCAL_HEADS_ISS197`` و``PEER_HEADS_ISS197`` يعيدان تمثيل حالة كارثة ISS-197 بصيغة
  ``ls-remote``، ومُعرّفاتهما **مُسجَّلة في هذا المستودع**: ``d9cd0925`` هو رأس المرآة
  العالق (تشغيل ``32587444306``) و``feb81385`` هو الرأس المرفوض في سجلّ الوظيفة
  ``99129715678``. أي أنّ الأرقام واقعٌ مقيس، والتنسيق وحده هو المُعاد بناؤه — وهذا
  يُقال ولا يُترَك للقارئ ليفترض (D-206 L11).

واختبارٌ يُثبت أنّ الفارض «يعمل» لا يكفي: لكلّ قاعدةٍ هنا **تجربة سلبية** تُثبت أنّه
يُبلِّغ عمّا يجب أن يُبلِّغ عنه، وأنّ استثناءه لا يبتلع ما هو خارجه (D-270 L4 · ISS-148).
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if REPO_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, REPO_ROOT.as_posix())

from scripts.ci import repo_sync_parity as parity

MAIN_SHA = "3ceef8ff823ee7bac9c847f9ee14f9d1ae8f4db1"
DEAD_BRANCH_SHA = "5c2281bb42bcd113b2fe8a5be173a5761defdf10"

LOCAL_HEADS_LIVE = f"""\
{DEAD_BRANCH_SHA}\trefs/heads/claude/merge-branch-ozolxi
{MAIN_SHA}\trefs/heads/main
"""

PEER_HEADS_LIVE = f"""\
{DEAD_BRANCH_SHA}\trefs/heads/claude/merge-branch-ozolxi
{MAIN_SHA}\trefs/heads/main
{MAIN_SHA}\trefs/heads/mirror/main
"""

ISS197_LOCAL_MAIN = "feb81385509462facd4832391adb91b05f366e91"
ISS197_PEER_MAIN = "d9cd09253e6380703f0de4f43c5bfaceddbd16ab"

LOCAL_HEADS_ISS197 = f"{ISS197_LOCAL_MAIN}\trefs/heads/main\n"
PEER_HEADS_ISS197 = (
    f"{ISS197_PEER_MAIN}\trefs/heads/main\n{ISS197_LOCAL_MAIN}\trefs/heads/mirror/main\n"
)


def _compare(local: str, peer: str) -> parity.ParityReport:
    return parity.compare(parity.parse_heads(local), parity.parse_heads(peer))


class TestLiveState(unittest.TestCase):
    """الحالة الحيّة المقيسة اليوم على الريموتين."""

    def test_live_remotes_are_in_sync(self) -> None:
        """``main`` متساوٍ ولا انحراف مُحتسَب — و``mirror/main`` مُستثنى بتصريح."""
        report = _compare(LOCAL_HEADS_LIVE, PEER_HEADS_LIVE)
        self.assertEqual(report.status, parity.IN_SYNC)
        self.assertEqual(report.deltas, [])
        self.assertEqual([delta.name for delta in report.exempt], [parity.RESCUE_REF])

    def test_live_report_names_the_exemption_instead_of_hiding_it(self) -> None:
        """الاستثناء يظهر في التقرير: ما لا يُرى لا يُساءَل عنه."""
        report = _compare(LOCAL_HEADS_LIVE, PEER_HEADS_LIVE)
        rendered = parity.render(report, "local", "peer")
        self.assertIn(parity.RESCUE_REF, rendered)
        self.assertIn("excluded by declaration, not by silence", rendered)


class TestIss197Divergence(unittest.TestCase):
    """الحالة التي بقيت سبعة أيامٍ بلا مقياس."""

    def test_stuck_mirror_is_reported_as_main_diverged(self) -> None:
        """رؤوس ``main`` المختلفة ⇒ ``main_diverged`` — الإشارة الوحيدة التي غابت."""
        report = _compare(LOCAL_HEADS_ISS197, PEER_HEADS_ISS197)
        self.assertEqual(report.status, parity.MAIN_DIVERGED)
        self.assertEqual(report.local_main, ISS197_LOCAL_MAIN)
        self.assertEqual(report.peer_main, ISS197_PEER_MAIN)

    def test_divergence_report_carries_both_shas(self) -> None:
        """التقرير يحمل الرقمين: «غير متطابق» بلا مقدارٍ لا يُفرِّق دفعةً عن ستّين."""
        rendered = parity.render(_compare(LOCAL_HEADS_ISS197, PEER_HEADS_ISS197), "local", "peer")
        self.assertIn(ISS197_LOCAL_MAIN[:7], rendered)
        self.assertIn(ISS197_PEER_MAIN[:7], rendered)


class TestOutOfContractDetection(unittest.TestCase):
    """تجارب سلبية: الفارض يُبلِّغ عمّا يجب، لا «يعمل» فحسب."""

    def test_same_named_branch_at_different_sha_is_reported(self) -> None:
        """فرعٌ بالاسم نفسه ورأسٍ مختلف انحرافٌ حقيقي — وهذا ما لم يكن يُقاس أبداً."""
        peer = PEER_HEADS_LIVE.replace(DEAD_BRANCH_SHA, "0" * 40)
        report = _compare(LOCAL_HEADS_LIVE, peer)
        self.assertEqual(report.status, parity.OUT_OF_CONTRACT)
        self.assertEqual([delta.name for delta in report.deltas], ["claude/merge-branch-ozolxi"])
        self.assertEqual(report.deltas[0].kind, "diverged")

    def test_branch_present_on_one_side_only_is_reported(self) -> None:
        """فرعٌ عند جانبٍ دون الآخر يُبلَّغ عنه بجهته الصحيحة."""
        local = LOCAL_HEADS_LIVE + f"{MAIN_SHA}\trefs/heads/feature/x\n"
        report = _compare(local, PEER_HEADS_LIVE)
        self.assertEqual(report.status, parity.OUT_OF_CONTRACT)
        self.assertEqual([delta.name for delta in report.deltas], ["feature/x"])
        self.assertEqual(report.deltas[0].kind, "local_only")

    def test_equal_main_does_not_mask_drift_elsewhere(self) -> None:
        """تساوي ``main`` وحده لا يُقرأ تطابقاً — وهو الادّعاء الذي وُلد منه هذا الملفّ."""
        peer = PEER_HEADS_LIVE + f"{MAIN_SHA}\trefs/heads/stray\n"
        report = _compare(LOCAL_HEADS_LIVE, peer)
        self.assertEqual(report.local_main, report.peer_main)
        self.assertNotEqual(report.status, parity.IN_SYNC)

    def test_main_divergence_outranks_out_of_contract(self) -> None:
        """الأسبقيّة عقدٌ: انحراف ``main`` لا يختبئ خلف فرعٍ ميزةٍ عابر.

        لو ابتلع الفرعُ العابر إشارةَ ``main`` لعاد عطبُ الأسبقيّة نفسه الذي أنتج
        ISS-144 وISS-149 — كشفٌ سليم وترتيبٌ خاطئ.
        """
        local = LOCAL_HEADS_ISS197 + f"{MAIN_SHA}\trefs/heads/feature/y\n"
        report = _compare(local, PEER_HEADS_ISS197)
        self.assertEqual(report.status, parity.MAIN_DIVERGED)
        self.assertEqual([delta.name for delta in report.deltas], ["feature/y"])


class TestRescueExemptionIsNarrow(unittest.TestCase):
    """الاستثناء المنطوق لا يتمدّد: يشمل مرجع الإنقاذ على النظير وحده."""

    def test_rescue_ref_on_the_local_side_is_not_exempt(self) -> None:
        """``mirror/main`` عند جانبنا ليس أثر إنقاذٍ من النظير ⇒ يُحتسَب انحرافاً.

        الوظيفة تُنشئه على **النظير** حين يُرفَض الدفع؛ ظهورُه عندنا واقعةٌ أخرى، وإعفاؤه
        بالاسم وحده يجعل الاستثناء باباً يمرّ منه ما لم يُقصَد.
        """
        local = LOCAL_HEADS_LIVE + f"{MAIN_SHA}\trefs/heads/{parity.RESCUE_REF}\n"
        peer = PEER_HEADS_LIVE.replace(f"{MAIN_SHA}\trefs/heads/mirror/main\n", "")
        report = _compare(local, peer)
        self.assertEqual(report.status, parity.OUT_OF_CONTRACT)
        self.assertEqual([delta.name for delta in report.deltas], [parity.RESCUE_REF])
        self.assertEqual(report.exempt, [])

    def test_operational_looking_name_is_not_exempt(self) -> None:
        """اسمٌ يشبه التشغيلي ليس مُعفى — الإعفاء بالحرفية المُصرَّحة لا بالانطباع."""
        peer = PEER_HEADS_LIVE + f"{MAIN_SHA}\trefs/heads/mirror/backup\n"
        report = _compare(LOCAL_HEADS_LIVE, peer)
        self.assertEqual([delta.name for delta in report.deltas], ["mirror/backup"])

    def test_stale_rescue_ref_stays_exempt_but_visible(self) -> None:
        """مرجع إنقاذٍ متأخّر يبقى مُستثنى من الاحتساب ويبقى **ظاهراً** في التقرير."""
        peer = PEER_HEADS_LIVE.replace(
            f"{MAIN_SHA}\trefs/heads/mirror/main", f"{DEAD_BRANCH_SHA}\trefs/heads/mirror/main"
        )
        report = _compare(LOCAL_HEADS_LIVE, peer)
        self.assertEqual(report.status, parity.IN_SYNC)
        self.assertIn(parity.RESCUE_REF, parity.render(report, "local", "peer"))


class TestParsing(unittest.TestCase):
    """قراءة مخرَج ``ls-remote`` لا تخترع مرجعاً ولا تسقط واحداً."""

    def test_ignores_non_head_refs_and_malformed_lines(self) -> None:
        """الوسوم وأسطر التحذير ليست فروعاً — ولا تُحسَب انحرافاً."""
        noisy = (
            LOCAL_HEADS_LIVE
            + f"{MAIN_SHA}\trefs/tags/v1\n"
            + "warning: redirecting to https://github.com/x/y.git\n"
            + "\n"
        )
        self.assertEqual(parity.parse_heads(noisy), parity.parse_heads(LOCAL_HEADS_LIVE))

    def test_empty_output_yields_no_refs(self) -> None:
        """مخرَجٌ فارغ يُرجع خريطةً فارغة، ولا يُقرأ تطابقاً."""
        self.assertEqual(parity.parse_heads(""), {})

    def test_missing_main_on_one_side_is_divergence_not_equality(self) -> None:
        """غياب ``main`` عند جانبٍ ليس تساوياً — ``None`` لا تعني «متطابق»."""
        report = _compare(LOCAL_HEADS_LIVE, "")
        self.assertEqual(report.status, parity.MAIN_DIVERGED)
        self.assertIsNone(report.peer_main)


class TestStatusSetIsClosed(unittest.TestCase):
    """لا رمز حالةٍ خارج القائمة المغلقة، ولكلّ حالةٍ عنوانٌ معروض."""

    def test_every_status_is_a_member(self) -> None:
        samples = (
            (LOCAL_HEADS_LIVE, PEER_HEADS_LIVE),
            (LOCAL_HEADS_ISS197, PEER_HEADS_ISS197),
            (LOCAL_HEADS_LIVE, ""),
            ("", ""),
        )
        for local, peer in samples:
            self.assertIn(_compare(local, peer).status, parity.STATUSES)

    def test_every_status_has_a_heading(self) -> None:
        """حالةٌ بلا عنوان تُفشِل العرض وقت التشغيل بدل أن تُكشَف هنا."""
        for status in parity.STATUSES:
            self.assertIn(status, parity._HEADINGS)


class TestCommandLine(unittest.TestCase):
    """العقد الذي يقرأه الـworkflow: السطر الأوّل حالةٌ وما بعده تقرير."""

    def _run(self, argv: list[str]) -> list[str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = parity.main(argv)
        self.assertEqual(exit_code, 0)
        return buffer.getvalue().splitlines()

    def test_prints_status_first_and_always_exits_zero(self) -> None:
        """الخروج بالرمز 0 دائماً كي لا يقتل ``set -e`` خطوةً ناجحة أصلاً."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmp = Path(tmpdirname)
            (tmp / "local.txt").write_text(LOCAL_HEADS_ISS197, encoding="utf-8")
            (tmp / "peer.txt").write_text(PEER_HEADS_ISS197, encoding="utf-8")
            lines = self._run(
                [
                    "--local",
                    (tmp / "local.txt").as_posix(),
                    "--peer",
                    (tmp / "peer.txt").as_posix(),
                    "--peer-name",
                    "Houssam-lab/NAAS-Agentic-Core",
                ]
            )

        self.assertEqual(lines[0], parity.MAIN_DIVERGED)
        self.assertIn("Houssam-lab/NAAS-Agentic-Core", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
