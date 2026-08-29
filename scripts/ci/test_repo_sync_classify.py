"""اختبارات تصنيف رفض الدفع إلى المستودع النظير (ISS-197).

النصّ المستعمَل في ``PROTECTED_BRANCH_OUTPUT`` **منقولٌ حرفيّاً** من سجلّ الوظيفة الحيّة
``99129715678`` (الدفعة ``feb81385`` على ``bakabala27-svg/NAAS-Agentic-Core``، 2026-08-29)
بعد نزع الطوابع الزمنية فقط. اختبارٌ على نصٍّ مُختلَق يُثبت أنّ المُصنِّف يعمل على ما تخيّلناه،
لا على ما حدث فعلاً — وهذا بالضبط صنف ISS-148 (فارضٌ خارج مرماه).
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

from scripts.ci import repo_sync_classify as classifier

PROTECTED_BRANCH_OUTPUT = """\
remote: error: GH006: Protected branch update failed for refs/heads/main.
remote:
remote: - This branch must not contain merge commits.
remote:   Found 1 violation:
remote:
remote:   feb81385509462facd4832391adb91b05f366e91
remote:
remote: - Changes must be made through a pull request.
remote:
remote: - 2 of 2 required status checks are expected.
To https://github.com/Houssam-lab/NAAS-Agentic-Core.git
 ! [remote rejected]   HEAD -> main (protected branch hook declined)
error: failed to push some refs to 'https://github.com/Houssam-lab/NAAS-Agentic-Core.git'
"""

TRANSIENT_LOCK_OUTPUT = """\
error: cannot lock ref 'refs/heads/main': is at 41ff84ce but expected 8f658a36
 ! [remote rejected] HEAD -> main (failed to update ref)
error: failed to push some refs to 'https://github.com/Houssam-lab/NAAS-Agentic-Core.git'
"""

AUTH_DENIED_OUTPUT = """\
remote: Permission to Houssam-lab/NAAS-Agentic-Core.git denied to some-actor.
fatal: unable to access 'https://github.com/Houssam-lab/NAAS-Agentic-Core.git/': \
The requested URL returned error: 403
"""

UNKNOWN_OUTPUT = """\
fatal: unable to access 'https://github.com/Houssam-lab/NAAS-Agentic-Core.git/': \
Could not resolve host: github.com
"""


class TestClassification(unittest.TestCase):
    """يثبت أنّ كل صنفٍ يُصنَّف كما يجب، وأنّ الحتميّ وحده يوقف إعادة المحاولة."""

    def test_real_protected_branch_rejection_is_deterministic(self) -> None:
        """الرفض الحقيقي المُلتقَط من الوظيفة الحيّة حتميّ — لا تُعاد المحاولة عليه."""
        classification = classifier.classify(PROTECTED_BRANCH_OUTPUT)
        self.assertEqual(classification, classifier.PROTECTED_BRANCH)
        self.assertTrue(classifier.is_deterministic(classification))

    def test_transient_lock_race_still_retries(self) -> None:
        """تجربة سلبية: السباق العابر — سببُ وجود الحلقة — يبقى قابلاً لإعادة المحاولة.

        لا نُصلح عطباً بكسر ما كان يعمل: لو صار العابر حتميّاً لفقدت الحلقةُ غرضها
        الوحيد المنطوق في تعليق الـworkflow.
        """
        classification = classifier.classify(TRANSIENT_LOCK_OUTPUT)
        self.assertEqual(classification, classifier.TRANSIENT_LOCK)
        self.assertFalse(classifier.is_deterministic(classification))

    def test_auth_denial_is_deterministic(self) -> None:
        """رفض الصلاحية حتميّ: إعادة الدفع لا تمنح تفويضاً غائباً."""
        classification = classifier.classify(AUTH_DENIED_OUTPUT)
        self.assertEqual(classification, classifier.AUTH_DENIED)
        self.assertTrue(classifier.is_deterministic(classification))

    def test_unknown_failure_stays_retryable(self) -> None:
        """المجهول يُعاد ولا يُصنَّف حتميّاً بالتخمين — الغياب ليس دليلاً."""
        classification = classifier.classify(UNKNOWN_OUTPUT)
        self.assertEqual(classification, classifier.UNKNOWN)
        self.assertFalse(classifier.is_deterministic(classification))

    def test_protected_branch_wins_over_transient_markers(self) -> None:
        """الترتيب عقدٌ: نصٌّ يحمل الإشارتين يُصنَّف حتميّاً لا عابراً.

        رسالة الحماية تحمل ``! [remote rejected]``، ولو سبق فحصُ العابر لعادت الحلقة
        الخمسية من الباب الذي أُغلق — وهو عطبُ أسبقيّةٍ لا كشف (نمط ISS-144 / ISS-149).
        """
        mixed = PROTECTED_BRANCH_OUTPUT + "\nerror: cannot lock ref 'refs/heads/main'\n"
        self.assertEqual(classifier.classify(mixed), classifier.PROTECTED_BRANCH)

    def test_classification_set_is_closed(self) -> None:
        """كل تصنيفٍ يُرجعه المُصنِّف عضوٌ في القائمة المغلقة."""
        samples = (
            PROTECTED_BRANCH_OUTPUT,
            TRANSIENT_LOCK_OUTPUT,
            AUTH_DENIED_OUTPUT,
            UNKNOWN_OUTPUT,
            "",
        )
        for sample in samples:
            self.assertIn(classifier.classify(sample), classifier.CLASSIFICATIONS)


class TestRuleExtraction(unittest.TestCase):
    """يثبت أنّ القاعدة المخروقة تصل التقرير كما نطق بها الريموت."""

    def test_extracts_the_three_violated_rules_verbatim(self) -> None:
        """القواعد الثلاث تُستخرَج بترتيبها ونصّها، ولا يُستخرَج سطر الـSHA."""
        rules = classifier.extract_rules(PROTECTED_BRANCH_OUTPUT)
        self.assertEqual(
            rules,
            [
                "This branch must not contain merge commits.",
                "Changes must be made through a pull request.",
                "2 of 2 required status checks are expected.",
            ],
        )

    def test_no_rules_when_remote_printed_none(self) -> None:
        """غياب أسطر القاعدة يُرجع قائمة فارغة لا يخترع سبباً."""
        self.assertEqual(classifier.extract_rules(TRANSIENT_LOCK_OUTPUT), [])


class TestCommandLine(unittest.TestCase):
    """يثبت العقد الذي يقرأه الـworkflow: السطر الأول تصنيف، وما بعده قواعد."""

    def _run(self, argv: list[str]) -> list[str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = classifier.main(argv)
        self.assertEqual(exit_code, 0)
        return buffer.getvalue().splitlines()

    def test_reads_file_and_prints_classification_then_rules(self) -> None:
        """يخرج دائماً بالرمز 0 كي لا يقتل ``set -e`` الخطوةَ قبل طباعة التشخيص."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            log_path = Path(tmpdirname) / "push.log"
            log_path.write_text(PROTECTED_BRANCH_OUTPUT, encoding="utf-8")
            lines = self._run([log_path.as_posix()])

        self.assertEqual(lines[0], classifier.PROTECTED_BRANCH)
        self.assertEqual(lines[1], "This branch must not contain merge commits.")
        self.assertEqual(len(lines), 4)


if __name__ == "__main__":
    unittest.main()
