"""الذخيرة والمسابر والأساس — GATE_B + قاعدة الإفصاح + برهان الفارق (D-267).

⛔ **البرهان السلبي المقصود:** لكلّ صنفٍ يُثبَت أنّ المسبار **يمسك** العطب، وأنّ
الأساس الإنجليزي **يفوّته**. «اختبارٌ يتوقّع نجاح البوّابة» ليس برهاناً.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from naas_verifier.adapters.multilingual_probe import (
    CorpusError,
    load_corpus,
    probe_class,
)
from naas_verifier.baselines.english_only_suite import detects
from naas_verifier.cli import measure
from naas_verifier.core import Outcome
from naas_verifier.targets.reference import UnknownProbeError, run_target

CORPUS = load_corpus()
CLASS_IDS = [entry["class_id"] for entry in CORPUS]


def _entry(class_id: str) -> dict:
    return next(row for row in CORPUS if row["class_id"] == class_id)


# ══════════════════════════════════════════════════════════════════════════════
# GATE_B — الاتّساع يُقاس بالجذور لا بالحالات
# ══════════════════════════════════════════════════════════════════════════════
def test_at_least_three_classes():
    assert len(CORPUS) >= 3


def test_root_causes_are_distinct():
    """⛔ ثلاث صيغٍ من جذرٍ واحد ليست ثلاثة أصناف."""
    roots = [" ".join(row["root_cause"].lower().split()) for row in CORPUS]
    assert len(set(roots)) == len(roots)


def test_every_class_has_the_gate_b_fields():
    for row in CORPUS:
        for field in ("class_id", "root_cause", "reproduction", "spec_reference"):
            assert str(row.get(field, "")).strip(), f"{row.get('class_id')} missing {field}"


def test_every_spec_reference_resolves_to_a_file():
    """ISS-149: خريطةٌ تكذب أسوأ من لا خريطة."""
    for row in CORPUS:
        target = REPO_ROOT / str(row["spec_reference"]).split("#", 1)[0]
        assert target.exists(), f"{row['class_id']}: {target} does not exist"


def test_every_source_incident_is_recorded_with_a_status():
    for row in CORPUS:
        assert row["sources"], f"{row['class_id']} has no measured source incident"
        for source in row["sources"]:
            assert source["status"] in {"open", "closed", "decided", "unknown"}


# ══════════════════════════════════════════════════════════════════════════════
# قاعدة الإفصاح — مفروضةٌ بنيوياً لا بنثر
# ══════════════════════════════════════════════════════════════════════════════
def test_class_with_an_open_source_is_not_publishable():
    """⛔ بيعُ دليلٍ على ثغرةٍ مفتوحة عندك أسوأ مدخلٍ إلى سوق أمان."""
    for row in CORPUS:
        has_open = any(source["status"] == "open" for source in row["sources"])
        assert row["publishable"] is not has_open
        if has_open:
            assert row["publish_block_reason_ar"].strip(), (
                f"{row['class_id']}: blocked without a spoken reason — "
                "an empty cell reads as success"
            )


def test_no_live_incident_text_leaks_into_the_corpus():
    """⛔ يُنشَر الصنف ولا تُنشَر الحادثة: لا مُعرِّف محادثةٍ ولا مسار إنتاج."""
    raw = (REPO_ROOT / "naas_verifier/corpus/ar_fr_exploit_classes.json").read_text("utf-8")
    for forbidden in ("customer_messages", "conversation_id", "user_id", "supabase", "@"):
        assert forbidden not in raw.lower(), f"corpus leaks `{forbidden}`"


# ══════════════════════════════════════════════════════════════════════════════
# البرهان السلبي لكل صنف: المسبار يمسك، والأساس يفوّت
# ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("class_id", CLASS_IDS)
@pytest.mark.parametrize("variant", ["vulnerable", "lucky"])
def test_probe_catches_every_defective_variant(class_id: str, variant: str):
    assert probe_class(_entry(class_id), variant, "ar").outcome is Outcome.VIOLATED


@pytest.mark.parametrize("class_id", CLASS_IDS)
def test_probe_clears_the_hardened_variant(class_id: str):
    """⛔ لا إيجابياتٍ كاذبة: بوّابةٌ تُحمِّر كلّ شيء لا تُباع."""
    assert probe_class(_entry(class_id), "hardened", "ar").outcome is not Outcome.VIOLATED


@pytest.mark.parametrize(
    "class_id", [cid for cid in CLASS_IDS if _entry(cid)["language_conditioned"]]
)
def test_english_baseline_misses_every_language_conditioned_class(class_id: str):
    """القصور الأوّل للأساس: لا يُشغِّل العربية أصلاً."""
    assert detects(_entry(class_id), "vulnerable") is False


@pytest.mark.parametrize("class_id", CLASS_IDS)
def test_english_baseline_misses_the_lucky_variant(class_id: str):
    """القصور الثاني، وهو مستقلٌّ عن اللغة: يقرأ النتيجة النهائية وحدها."""
    assert detects(_entry(class_id), "lucky") is False


def test_language_neutral_class_is_caught_by_the_baseline_too():
    """صدقٌ في الاتّجاه المعاكس: الأساس ليس أعمى تماماً، ويُقال ذلك."""
    assert detects(_entry("SYS-ROLE-INJECT"), "vulnerable") is True


# ══════════════════════════════════════════════════════════════════════════════
# القياس — GATE_A
# ══════════════════════════════════════════════════════════════════════════════
def test_measurement_is_deterministic_and_reproducible():
    first = measure(CORPUS, runs=3)
    second = measure(CORPUS, runs=3)
    assert first["deterministic"] is True
    assert first["delta_pct"] == second["delta_pct"]


def test_measurement_rejects_fewer_than_three_runs():
    """⛔ عرضٌ واحد ليس قياساً."""
    with pytest.raises(ValueError, match="runs >= 3"):
        measure(CORPUS, runs=1)


def test_report_carries_its_caveat():
    """⛔ حدّ المصداقية (D-227): الرقم لا يُقتبَس بلا قيده."""
    report = measure(CORPUS, runs=3)
    assert "not performance on any third-party production system" in report["caveat_en"]
    assert report["confidence"].startswith("deterministic")


def test_no_false_positives_on_hardened_targets():
    report = measure(CORPUS, runs=3)
    assert report["per_run"][0]["false_positives_on_hardened"]["verifier"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# لا سقوط صامت
# ══════════════════════════════════════════════════════════════════════════════
def test_missing_corpus_raises_instead_of_returning_empty():
    with pytest.raises(CorpusError, match="corpus not found"):
        load_corpus(Path("/nonexistent/corpus.json"))


def test_unknown_probe_kind_raises():
    with pytest.raises(UnknownProbeError, match="no reference target"):
        run_target({"kind": "not-a-real-kind"}, "vulnerable", "ar")


def test_unknown_variant_raises():
    with pytest.raises(UnknownProbeError, match="unknown variant"):
        run_target(_entry(CLASS_IDS[0])["probe"], "made-up", "ar")


def test_corpus_on_disk_matches_the_extractor():
    """⛔ الذخيرة مُشتَقّة: نسخةٌ محرَّرة يدوياً تتقادم ثمّ تكذب (D-192)."""
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "research"))
    import extract_incident_corpus as extractor

    payload, errors = extractor.build_corpus()
    assert errors == []
    on_disk = json.loads(
        (REPO_ROOT / "naas_verifier/corpus/ar_fr_exploit_classes.json").read_text("utf-8")
    )
    assert on_disk == payload
