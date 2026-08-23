"""البرهان السلبي لمِسنَنة المصادر غير المُصنَّفة — D-283 · D-270 L4.

⛔ **القاعدة المُختبَرة:** «اختبارٌ يستدعي البوّابة ويتوقّع نجاحها ليس برهاناً سلبياً —
يُثبِت أنّها تعمل لا أنّها **تحجب**» (`NEGATIVE_PROOFS.json` القاعدة الثالثة). فكلّ فحصٍ
هنا يكسر مُدخَلاً ويؤكّد رمز خروجٍ ≠ 0، **في الاتجاهين**:

1. `test_growing_unclassified_debt_is_blocked` — مصدرٌ جديد يدخل غير مُصنَّف ⇒ أحمر.
2. `test_shrinking_without_lowering_the_ceiling_is_blocked` — دَينٌ أُغلق بصمتٍ يكذب
   كالدَّين المكتوم (نمط D-189) ⇒ أحمر أيضاً.

⚠️ كلّ التجارب على شجرةٍ مؤقّتة — لا تُلمَس شجرة المستودع.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_source_adoption_matrix as gate

BACKBONE_URL = "https://github.com/probe-owner/backbone-repo"
PENDING_URL = "https://github.com/probe-owner/pending-repo"


def _run(**overrides) -> tuple[int, str]:
    """يشغّل `main()` تحت مسارات/ثوابت بديلة ويُعيد (رمز الخروج، المخرَج)."""
    saved = {name: getattr(gate, name) for name in overrides}
    for name, value in overrides.items():
        setattr(gate, name, value)
    gate.FAILURES.clear()
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            code = gate.main()
    finally:
        for name, value in saved.items():
            setattr(gate, name, value)
        gate.FAILURES.clear()
    return code, buffer.getvalue()


def _card(url: str, status: str, **extra) -> dict[str, object]:
    """بطاقةُ مصدرٍ مستوفيةٌ لكل الحقول — كي يكون الفشل من المِسنَنة وحدها."""
    card: dict[str, object] = {
        "url": url,
        "status": status,
        "purpose_ar": "غرضٌ مُختبَر",
        "application_ar": "تطبيقٌ مُختبَر",
        "upgrade_condition_ar": "شرطُ ترقيةٍ مُختبَر",
        "owner": "probe-owner",
        "local_evidence_paths": ["README.md"],
        "enforcers": ["check_source_adoption_matrix.py"],
        "runtime_allowed": False,
    }
    if status == "PENDING_CLASSIFICATION":
        card["primary_source_review"] = False
        card["source_id"] = "unclassified"
    else:
        card["primary_source_review"] = True
        card["source_id"] = url.rsplit("/", 1)[-1]
    card.update(extra)
    return card


@pytest.fixture
def tree(tmp_path: Path):
    """شجرةٌ صغيرة صالحة؛ يضبط كلّ فحصٍ عددَ المُعلَّق فيها."""
    (tmp_path / "docs" / "governance").mkdir(parents=True)
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "README.md").write_text("probe", encoding="utf-8")
    (tmp_path / "scripts" / "fitness").mkdir(parents=True)
    (tmp_path / "scripts" / "fitness" / "check_source_adoption_matrix.py").write_text(
        "probe", encoding="utf-8"
    )

    matrix = tmp_path / "docs" / "governance" / "SOURCE_ADOPTION_MATRIX.json"
    inventory = tmp_path / "docs" / "research" / "ALL_GITHUB_SOURCES_INVENTORY.json"
    backbone = tmp_path / "docs" / "governance" / "REFERENCE_BACKBONE.json"
    backbone.write_text(json.dumps({"references": [{"repo": BACKBONE_URL}]}), encoding="utf-8")

    def write(pending_count: int) -> None:
        rows = [_card(BACKBONE_URL, "MANDATORY_REFERENCE")]
        rows += [
            _card(f"{PENDING_URL}-{index}", "PENDING_CLASSIFICATION")
            for index in range(pending_count)
        ]
        matrix.write_text(
            json.dumps(
                {
                    "total_sources": len(rows),
                    "required_card_fields": [
                        "purpose_ar",
                        "application_ar",
                        "local_evidence_paths",
                        "enforcers",
                        "runtime_allowed",
                        "primary_source_review",
                        "upgrade_condition_ar",
                        "owner",
                    ],
                    "sources": rows,
                }
            ),
            encoding="utf-8",
        )
        inventory.write_text(
            json.dumps({"sources": [{"url": row["url"]} for row in rows]}), encoding="utf-8"
        )

    return write, {"ROOT": tmp_path, "MATRIX": matrix, "INVENTORY": inventory, "BACKBONE": backbone}


# ══════════════════════════════════════════════════════════════════════════════
# ⭐ البراهين السلبية — أنّ المِسنَنة **تحجب**
# ══════════════════════════════════════════════════════════════════════════════
def test_growing_unclassified_debt_is_blocked(tree):
    """⛔ مصدرٌ جديد يدخل غير مُصنَّف — العدد يكبر والنسبة المُصادَقة تصغر."""
    write, paths = tree
    write(3)
    code, output = _run(**paths, MAX_PENDING_CLASSIFICATION=2)
    assert code == 1
    assert "unclassified debt grew" in output


def test_shrinking_without_lowering_the_ceiling_is_blocked(tree):
    """⛔ دَينٌ أُغلق بصمتٍ يكذب كالدَّين المكتوم — القيد ثنائي الاتجاه (D-189)."""
    write, paths = tree
    write(1)
    code, output = _run(**paths, MAX_PENDING_CLASSIFICATION=2)
    assert code == 1
    assert "shrank" in output and "same change" in output


def test_exact_ceiling_passes(tree):
    """السقف المضبوط يمرّ — وإلّا كانت المِسنَنة تحجب كلّ شيءٍ ولا تقيس شيئاً."""
    write, paths = tree
    write(2)
    code, output = _run(**paths, MAX_PENDING_CLASSIFICATION=2)
    assert code == 0, output
    assert "shrink-only" in output


# ══════════════════════════════════════════════════════════════════════════════
# الشجرة الحقيقية تبقى خضراء — والسقف يساوي الواقع المقيس
# ══════════════════════════════════════════════════════════════════════════════
def test_real_repository_tree_passes():
    code, output = _run()
    assert code == 0, output


def test_declared_ceiling_equals_the_measured_reality():
    """⛔ السقف رقمٌ مُشتَقّ من القرص لا أمنية (D-192)."""
    matrix = json.loads(gate.MATRIX.read_text(encoding="utf-8"))
    pending = sum(
        1
        for row in matrix["sources"]
        if isinstance(row, dict) and row.get("status") == "PENDING_CLASSIFICATION"
    )
    assert pending == gate.MAX_PENDING_CLASSIFICATION
