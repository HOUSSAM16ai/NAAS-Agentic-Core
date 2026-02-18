import subprocess
from pathlib import Path


class GitAnalyzer:
    """Git History Analyzer"""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def analyze_file_history(self, file_path: str) -> dict[str, object]:
        """
        تحليل تاريخ تعديلات الملف.

        Note: تم تقسيم الدالة إلى helper methods لتطبيق KISS و SRP
        """
        try:
            total_commits = self._get_total_commits(file_path)
            commits_6m = self._get_commits_since(file_path, "6 months ago")
            commits_12m = self._get_commits_since(file_path, "12 months ago")
            num_authors = self._get_author_count(file_path)
            bugfix_commits = self._get_bugfix_commits(file_path)
            branches_modified = self._get_branch_count(file_path)

            return {
                "total_commits": total_commits,
                "commits_last_6months": commits_6m,
                "commits_last_12months": commits_12m,
                "num_authors": num_authors,
                "bugfix_commits": bugfix_commits,
                "branches_modified": branches_modified,
            }
        except Exception:
            return self._get_empty_analysis()

    def _get_total_commits(self, file_path: str) -> int:
        """الحصول على إجمالي عدد الـ commits للملف."""
        result = subprocess.run(
            ["git", "log", "--follow", "--oneline", "--", file_path],
            check=False,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

    def _get_commits_since(self, file_path: str, since: str) -> int:
        """الحصول على عدد الـ commits منذ فترة معينة."""
        result = subprocess.run(
            ["git", "log", "--follow", f"--since={since}", "--oneline", "--", file_path],
            check=False,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

    def _get_author_count(self, file_path: str) -> int:
        """الحصول على عدد المطورين الذين عدّلوا الملف."""
        result = subprocess.run(
            ["git", "log", "--follow", "--format=%an", "--", file_path],
            check=False,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        authors = set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()
        return len(authors)

    def _get_bugfix_commits(self, file_path: str) -> int:
        """الحصول على عدد الـ commits المتعلقة بإصلاح الأخطاء."""
        result = subprocess.run(
            [
                "git",
                "log",
                "--follow",
                "--oneline",
                "--grep=fix",
                "--grep=bug",
                "--grep=hotfix",
                "-i",
                "--",
                file_path,
            ],
            check=False,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

    def _get_branch_count(self, file_path: str) -> int:
        """الحصول على عدد الـ branches التي عُدّل فيها الملف."""
        result = subprocess.run(
            ["git", "log", "--follow", "--all", "--format=%D", "--", file_path],
            check=False,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        branches: set[str] = set()
        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                if line:
                    # استخراج أسماء الـ branches من صيغة "HEAD -> main, origin/main"
                    parts = [p.strip() for p in line.split(",")]
                    for part in parts:
                        if "origin/" in part or "->" in part:
                            continue
                        if part and not part.startswith("tag:"):
                            branches.add(part)

        return len(branches)

    def _get_empty_analysis(self) -> dict[str, int]:
        """إرجاع تحليل فارغ في حالة الفشل."""
        return {
            "total_commits": 0,
            "commits_last_6months": 0,
            "commits_last_12months": 0,
            "num_authors": 0,
            "bugfix_commits": 0,
            "branches_modified": 0,
        }
