"""اختبارات سلبية لعقد التوثيق الحي."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.fitness import check_documentation_contract as gate


def test_check_documentation_contract_rejects_missing_manifest_document(
    tmp_path: Path, monkeypatch
) -> None:
    """الوثيقة الحية المسجلة لكنها غير موجودة يجب أن تُسقط البوابة."""
    docs = tmp_path / "docs"
    docs.mkdir()
    manifest = docs / "DOCUMENTATION_MANIFEST.json"
    manifest.write_text(
        json.dumps({"documents": [{"path": "docs/missing.md", "status": "live", "role": "test"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gate, "MANIFEST", manifest)

    failures: list[str] = []
    entries = gate._check_manifest(failures)

    assert entries == [("docs/missing.md", "test")]
    assert any("وثيقة manifest مفقودة" in failure for failure in failures)
    assert len(failures) >= 1


def test_check_manifest_rejects_escape_path_and_missing_authority(
    tmp_path: Path, monkeypatch
) -> None:
    """لا يُسمح للmanifest بتسجيل وثيقة خارج الجذر أو بلا سلطة حاكمة."""
    docs = tmp_path / "docs"
    docs.mkdir()
    manifest = docs / "DOCUMENTATION_MANIFEST.json"
    manifest.write_text(
        json.dumps(
            {
                "scan_globs": ["docs/**/*.md"],
                "exclude_globs": ["docs/archive/**"],
                "documents": [
                    {
                        "path": "../outside.md",
                        "status": "live",
                        "role": "test",
                        "audience": "agent",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gate, "MANIFEST", manifest)

    failures: list[str] = []
    gate._check_manifest(failures)

    assert any("خارج جذر المستودع" in failure for failure in failures)
    assert any("authority" in failure for failure in failures)
    assert len(failures) >= 1


def test_check_documentation_contract_rejects_broken_live_link(tmp_path: Path, monkeypatch) -> None:
    """الرابط المكسور داخل وثيقة حية يجب أن ينتج فشلًا صريحًا."""
    docs = tmp_path / "docs"
    docs.mkdir()
    live_doc = docs / "live.md"
    live_doc.write_text("[missing](missing.md)\n", encoding="utf-8")
    manifest = docs / "DOCUMENTATION_MANIFEST.json"
    manifest.write_text(
        json.dumps(
            {
                "scan_globs": ["docs/**/*.md"],
                "exclude_globs": ["docs/archive/**"],
                "documents": [
                    {
                        "path": "docs/live.md",
                        "status": "live",
                        "role": "test",
                        "audience": "agent",
                        "authority": "supporting",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gate, "MANIFEST", manifest)

    failures: list[str] = []
    entries = gate._check_manifest(failures)
    gate._check_links_and_stale_text(entries, failures)

    assert any("رابط محلي مكسور" in failure for failure in failures)
    assert len(failures) >= 1
