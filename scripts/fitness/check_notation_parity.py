"""بوّابة تكافؤ سجلّ الرموز — مصدر قانوني واحد لا نسخة ثالثة (D-185).

دستور الخدمات المصغّرة (القاعدتان 97/98) يمنع **مكتبة منطق مشتركة** بين الخدمات، ويقبل
التكرار حفظاً للاستقلال. فالخدمة `notation-service` تحمل نسخة مُوَرَّدة من السجلّ بدل أن
تستورد `shared/`. لكن التكرار بلا حارس ينقلب انجرافاً صامتاً: يُضاف رمز في جهة دون الأخرى
فيُجيب المونوليث ولا تُجيب الخدمة (أو العكس) — وهو بالضبط صنف العطب الذي وُلد منه ISS-138.

هذه البوّابة تُثبت أنّ النسختين **متطابقتان بايتاً ببايت**، على سابقة
`check_model_chain_parity.py` (D-174): «تكافؤ محروس آلياً بدل حرّر النسختين يدوياً».

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CANONICAL = REPO_ROOT / "shared/notation/registry.py"
VENDORED = REPO_ROOT / "microservices/notation_service/src/notation/registry.py"

#: أدلّة لا تُمسَح بحثاً عن نسخة ثالثة (تبعيات/بناء، ليست مصدر المشروع).
_SKIP_DIRS = frozenset({"node_modules", ".git", "migrations_archive", "site-packages", ".next"})


def _digest(path: Path) -> str:
    """بصمة محتوى الملف — المقارنة على البايتات لا على التمثيل."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    """يُرجع 0 عند التطابق، و1 عند الانجراف أو غياب أحد الملفّين."""
    missing = [p for p in (CANONICAL, VENDORED) if not p.is_file()]
    if missing:
        for path in missing:
            print(f"❌ Missing notation registry: {path.relative_to(REPO_ROOT)}")
        return 1

    canonical_digest = _digest(CANONICAL)
    vendored_digest = _digest(VENDORED)
    if canonical_digest != vendored_digest:
        print("❌ Notation registry drift — canonical and vendored copies differ.")
        print(f"   canonical {CANONICAL.relative_to(REPO_ROOT)}: {canonical_digest[:16]}")
        print(f"   vendored  {VENDORED.relative_to(REPO_ROOT)}: {vendored_digest[:16]}")
        print("   Fix: cp shared/notation/registry.py " + str(VENDORED.relative_to(REPO_ROOT)))
        return 1

    # لا نسخة ثالثة: أي ملف آخر يُعرّف `NOTATION_REGISTRY` يكسر «المصدر الواحد».
    needle = "NOTATION_REGISTRY: tuple[NotationEntry, ...] = ("
    extra: list[Path] = []
    for path in REPO_ROOT.rglob("*.py"):
        # هذا الملف نفسه يحمل النصّ المبحوث عنه كسلسلة حرفية — لا يُعدّ نسخة.
        if path in {CANONICAL, VENDORED, Path(__file__).resolve()}:
            continue
        if any(part.startswith(".venv") or part in _SKIP_DIRS for part in path.parts):
            continue
        # ملفّات المستودع قد تحوي بايتات غير UTF-8 (عيّنات/بيانات) — لا تُسقِط البوّابة.
        if needle in path.read_text(encoding="utf-8", errors="ignore"):
            extra.append(path)
    if extra:
        for path in extra:
            print(f"❌ Third notation registry copy found: {path.relative_to(REPO_ROOT)}")
        print("   The registry has exactly one canonical source and one vendored mirror.")
        return 1

    print(
        f"✅ Notation registry parity OK (sha256 {canonical_digest[:16]}, 1 canonical + 1 mirror)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
