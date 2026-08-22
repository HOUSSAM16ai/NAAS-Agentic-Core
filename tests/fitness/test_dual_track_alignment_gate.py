"""البرهان السلبي لبوّابة المواءمة الثنائية — D-279 · ISS-196.

**لماذا هذا الملفّ:** `DUAL_TRACK_ALIGNMENT.json` يُصرِّح الحقل
`offer_id_or_foundation_exception` وقاعدةَ إصدارٍ تقول «أو وُجد استثناء تأسيسي مصرح به
**دون ادعاء إيراد**» — بينما الفارض كان يطلب `offer_id` حرفياً ويرفض ما ليس في كتالوج
العروض. فالباب الثاني كان **مُعلَناً في العقد ومُقفَلاً في الفارض**: نفس صنف ISS-148
(فارضٌ لا يبلغ مرماه المُسمَّى).

⚠️ كلّ التجارب على شجرةٍ مؤقّتة — لا تُلمَس شجرة المستودع.
⛔ «اختبارٌ يتوقّع النجاح» ليس برهاناً سلبياً؛ كلّ فحصٍ هنا يكسر مُدخَلاً ويؤكّد ≠ 0.
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

import check_dual_track_alignment as alignment_gate

OFFER_ID = "ai-red-teaming-multilingual"
DOMAIN = "security_privacy_trust"
EVIDENCE_ID = "nist-ai-rmf-1.0"
SOURCE_ID = "system-design-primer"


def _run(**overrides) -> tuple[int, str]:
    """يشغّل `main()` تحت مسارات بديلة ويُعيد (رمز الخروج، المخرَج)."""
    saved = {name: getattr(alignment_gate, name) for name in overrides}
    for name, value in overrides.items():
        setattr(alignment_gate, name, value)
    alignment_gate.FAILURES.clear()
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            code = alignment_gate.main()
    finally:
        for name, value in saved.items():
            setattr(alignment_gate, name, value)
        alignment_gate.FAILURES.clear()
    return code, buffer.getvalue()


def _record(**overrides) -> dict:
    """سجلُّ مواءمةٍ سليم مربوطٌ بعرضٍ من الكتالوج."""
    row = {
        "alignment_id": "ALIGN-PROBE",
        "capability": "قدرةٌ مُختبَرة",
        "offer_id": OFFER_ID,
        "buyer_or_user": "مشترٍ مؤسّسي خارج الجزائر",
        "paid_problem_or_social_problem": "مشكلةٌ مدفوعة",
        "standards": [SOURCE_ID],
        "curriculum_domains": [DOMAIN],
        "evidence": [EVIDENCE_ID],
        "engineering_status": "RESEARCH",
        "commercial_status": "PROPOSED",
        "owner": "product-security",
        "next_gate": "مقابلات عميل",
    }
    row.update(overrides)
    return {key: value for key, value in row.items() if value is not None}


@pytest.fixture
def tree(tmp_path: Path):
    """شجرةٌ صغيرة صالحة — ثمّ يكسرها كلّ فحصٍ بطريقته."""
    (tmp_path / "docs" / "governance").mkdir(parents=True)
    (tmp_path / "docs" / "commercial").mkdir(parents=True)
    (tmp_path / "docs" / "research").mkdir(parents=True)

    offers = tmp_path / "docs" / "commercial" / "OFFER_CATALOG.json"
    offers.write_text(json.dumps({"offers": [{"id": OFFER_ID}]}), encoding="utf-8")

    sources = tmp_path / "docs" / "governance" / "SOURCE_ADOPTION_MATRIX.json"
    sources.write_text(
        json.dumps({"sources": [{"source_id": SOURCE_ID, "status": "ADOPTED"}]}),
        encoding="utf-8",
    )

    curriculum = tmp_path / "docs" / "research" / "CURRICULUM_APPLICATION_MATRIX.json"
    curriculum.write_text(json.dumps({"courses": [{"domain_tags": [DOMAIN]}]}), encoding="utf-8")

    evidence = tmp_path / "docs" / "research" / "EVIDENCE_CATALOG.json"
    evidence.write_text(json.dumps({"evidence": [{"id": EVIDENCE_ID}]}), encoding="utf-8")

    alignment = tmp_path / "docs" / "governance" / "DUAL_TRACK_ALIGNMENT.json"

    def write(records: list[dict]) -> None:
        alignment.write_text(
            json.dumps(
                {
                    "engineering_track": {"constitution": "x"},
                    "production_track": {"operating_system": "y"},
                    "shared_alignment_contract": {
                        "required_fields": [
                            "alignment_id",
                            "capability",
                            "buyer_or_user",
                            "paid_problem_or_social_problem",
                            "offer_id_or_foundation_exception",
                            "standards",
                            "curriculum_domains",
                            "evidence",
                            "engineering_status",
                            "commercial_status",
                            "owner",
                            "next_gate",
                        ]
                    },
                    "alignment_records": records,
                }
            ),
            encoding="utf-8",
        )

    paths = {
        "ALIGNMENT": alignment,
        "OFFERS": offers,
        "SOURCES": sources,
        "CURRICULUM": curriculum,
        "EVIDENCE": evidence,
    }
    return write, paths


# ══════════════════════════════════════════════════════════════════════════════
# الباب الأول — العرض من الكتالوج (السلوك القائم: يجب ألّا ينحدر)
# ══════════════════════════════════════════════════════════════════════════════
def test_offer_backed_record_passes(tree):
    write, paths = tree
    write([_record()])
    code, output = _run(**paths)
    assert code == 0, output


def test_unknown_offer_is_blocked(tree):
    """حمايةٌ من الانحدار: فتحُ الباب الثاني لا يجوز أن يُرخي الأوّل."""
    write, paths = tree
    write([_record(offer_id="offer-that-does-not-exist")])
    code, output = _run(**paths)
    assert code == 1
    assert "unknown offer" in output


# ══════════════════════════════════════════════════════════════════════════════
# الباب الثاني — الاستثناء التأسيسي (كان مُعلَناً ومُقفَلاً)
# ══════════════════════════════════════════════════════════════════════════════
def test_neither_offer_nor_exception_is_blocked(tree):
    """⛔ سجلٌّ بلا بابٍ أصلاً — الفراغ لا يُقرأ نجاحاً (D-206 L11)."""
    write, paths = tree
    write([_record(offer_id=None)])
    code, output = _run(**paths)
    assert code == 1
    assert "offer_id" in output and "foundation_exception" in output


def test_both_offer_and_exception_is_blocked(tree):
    """⛔ البابان معاً يعنيان أنّ أحدهما زينة — والسجلّ يفقد معناه."""
    write, paths = tree
    write([_record(foundation_exception="مشكلةٌ اجتماعية")])
    code, output = _run(**paths)
    assert code == 1
    assert "never both" in output


def test_foundation_exception_claiming_revenue_is_blocked(tree):
    """⛔ ادّعاء إيرادٍ من الباب الخلفي — يخرق `release_rule_ar` نصّاً."""
    write, paths = tree
    write(
        [
            _record(
                offer_id=None,
                foundation_exception="مشكلةٌ اجتماعية بلا مشترٍ",
                commercial_status="PILOT",
            )
        ]
    )
    code, output = _run(**paths)
    assert code == 1
    assert "no revenue claim without an offer" in output


def test_foundation_exception_claiming_engineering_release_is_blocked(tree):
    write, paths = tree
    write(
        [
            _record(
                offer_id=None,
                foundation_exception="مشكلةٌ اجتماعية بلا مشترٍ",
                engineering_status="PILOT_READY",
            )
        ]
    )
    code, output = _run(**paths)
    assert code == 1
    assert "cannot claim" in output


def test_honest_foundation_exception_passes(tree):
    """الباب المفتوح أخيراً: مشكلةٌ اجتماعية · بلا عرض · بلا ادّعاء إيراد."""
    write, paths = tree
    write(
        [
            _record(
                offer_id=None,
                foundation_exception="أثرٌ اجتماعي بلا مشترٍ — لا يُدَّعى له إيراد",
                paid_problem_or_social_problem="مشكلةٌ اجتماعية",
            )
        ]
    )
    code, output = _run(**paths)
    assert code == 0, output


# ══════════════════════════════════════════════════════════════════════════════
# الشجرة الحقيقية تبقى خضراء
# ══════════════════════════════════════════════════════════════════════════════
def test_real_repository_tree_passes():
    code, output = _run()
    assert code == 0, output
