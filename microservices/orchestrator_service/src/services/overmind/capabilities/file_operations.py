"""
عمليات الملفات الآمنة (Safe File Operations).

يوفر عمليات آمنة ومُسجلة للتعامل مع الملفات والمجلدات.

المبادئ:
- Safety First: التحقق من الصلاحيات والأمان
- Single Responsibility: فقط عمليات الملفات
- Logging: تسجيل جميع العمليات
"""

from pathlib import Path

from app.core.di import get_logger

logger = get_logger(__name__)


class FileOperations:
    """
    عمليات الملفات (File Operations).

    توفر عمليات آمنة ومُسجلة للتعامل مع الملفات والمجلدات.

    الأمان:
        - التحقق من المسارات (لا وصول خارج المشروع)
        - تسجيل جميع العمليات
        - منع حذف ملفات حساسة (.env, .git, إلخ)
    """

    def __init__(self, project_root: Path | None = None) -> None:
        """
        تهيئة نظام عمليات الملفات.

        Args:
            project_root: المجلد الجذر للمشروع (افتراضياً: المجلد الحالي)
        """
        self.project_root = (project_root or Path.cwd()).resolve()
        self.safe_paths = [
            self.project_root / "app",
            self.project_root / "tests",
            self.project_root / "scripts",
            self.project_root / "docs",
        ]

        # الملفات المحمية من الحذف (Protected Files)
        self.protected_files = {
            ".env",
            ".env.local",
            ".git",
            ".gitignore",
            "requirements.txt",
            "pyproject.toml",
        }

        logger.info(f"FileOperations initialized with root: {self.project_root}")

    def _is_safe_path(self, path: Path) -> bool:
        """التحقق من أن المسار آمن للوصول."""
        resolved_path = path.resolve()

        if not resolved_path.is_relative_to(self.project_root):
            logger.warning(f"Unsafe path (outside project): {resolved_path}")
            return False

        if ".git" in resolved_path.parts:
            logger.warning(f"Unsafe path (.git directory): {resolved_path}")
            return False

        return True

    def _is_protected(self, path: Path) -> bool:
        """التحقق من أن الملف محمي من الحذف."""
        return path.name in self.protected_files

    async def read_file(self, file_path: str | Path) -> str:
        """قراءة محتوى ملف."""
        path = Path(file_path)
        if not path.is_absolute():
            path = self.project_root / path

        if not self._is_safe_path(path):
            raise ValueError(f"Unsafe path: {path}")

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        logger.info(f"Read file: {path} ({len(content)} chars)")
        return content

    async def write_file(
        self,
        file_path: str | Path,
        content: str,
        overwrite: bool = False,
    ) -> bool:
        """كتابة محتوى إلى ملف."""
        path = Path(file_path)
        if not path.is_absolute():
            path = self.project_root / path

        if not self._is_safe_path(path):
            raise ValueError(f"Unsafe path: {path}")

        if path.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {path}. Use overwrite=True to replace it.")

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Wrote file: {path} ({len(content)} chars)")
        return True

    async def edit_file(
        self,
        file_path: str | Path,
        old_text: str,
        new_text: str,
    ) -> bool:
        """تعديل نص في ملف موجود."""
        content = await self.read_file(file_path)

        if old_text not in content:
            raise ValueError(
                f"Old text not found in file: {file_path}\nLooking for: {old_text[:100]}..."
            )

        new_content = content.replace(old_text, new_text)
        await self.write_file(file_path, new_content, overwrite=True)

        logger.info(f"Edited file: {file_path}")
        return True

    async def delete_file(self, file_path: str | Path, force: bool = False) -> bool:
        """حذف ملف."""
        path = Path(file_path)
        if not path.is_absolute():
            path = self.project_root / path

        if not self._is_safe_path(path):
            raise ValueError(f"Unsafe path: {path}")

        if self._is_protected(path) and not force:
            raise ValueError(
                f"Protected file: {path}. Use force=True to delete anyway (NOT RECOMMENDED)."
            )

        if path.exists():
            path.unlink()
            logger.warning(f"Deleted file: {path}")
            return True
        logger.info(f"File doesn't exist (nothing to delete): {path}")
        return False

    async def create_directory(self, dir_path: str | Path) -> bool:
        """إنشاء مجلد جديد."""
        path = Path(dir_path)
        if not path.is_absolute():
            path = self.project_root / path

        if not self._is_safe_path(path):
            raise ValueError(f"Unsafe path: {path}")

        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {path}")
        return True

    async def list_directory(self, dir_path: str | Path = ".") -> list[str]:
        """عرض محتويات مجلد."""
        path = Path(dir_path)
        if not path.is_absolute():
            path = self.project_root / path

        if not self._is_safe_path(path):
            raise ValueError(f"Unsafe path: {path}")

        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")

        items = [item.name for item in path.iterdir()]
        logger.info(f"Listed directory: {path} ({len(items)} items)")
        return sorted(items)
