"""مُشغِّل المعيار — يقيس الفارق بين المُتحقِّق والأساس ويطبعه خاماً (D-267 · GATE_A).

    python -m naas_verifier.cli run --runs 3

⛔ **حدّ المصداقية (D-227 · L10):** ما يقيسه هذا المُشغِّل هو **بطاريةُ الاختبار على
أهدافٍ مرجعية تُعيد إنتاج جذور الأرشيف** — لا أداءٌ على نظام عميلٍ حقيقي. الرقم يُطبَع
مع هذا القيد ملتصقاً به، ولا يُقتبَس بدونه.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from naas_verifier.adapters.multilingual_probe import load_corpus, probe_class
from naas_verifier.baselines.english_only_suite import BASELINE_ID, detects
from naas_verifier.core.constraint import Outcome

__all__ = ["main", "measure"]

#: الأنماط المعطوبة التي يجب أن تُكشَف، والنمط السليم الذي يجب ألّا يُكشَف.
DEFECTIVE_VARIANTS = ("vulnerable", "lucky")
CLEAN_VARIANT = "hardened"

PROBE_LANGUAGE = "ar"

CAVEAT_EN = (
    "Measured against reference targets that reproduce the archived root causes. "
    "This measures the suite, not performance on any third-party production system."
)


def _verifier_detects(entry: Mapping[str, Any], variant: str) -> bool:
    """المُتحقِّق «يكتشف» حين يُصدر حكم انتهاك — لا حين يعجز عن الحكم."""
    return probe_class(entry, variant, PROBE_LANGUAGE).outcome is Outcome.VIOLATED


def measure(classes: Sequence[Mapping[str, Any]], runs: int) -> dict[str, Any]:
    """يُشغِّل المعيار `runs` مرّة ويُعيد تقريراً بالأرقام الخام."""
    if runs < 3:
        raise ValueError("GATE_A requires runs >= 3 — a single demonstration is not a measurement")

    per_run: list[dict[str, Any]] = []
    for index in range(runs):
        verifier_hits = 0
        baseline_hits = 0
        opportunities = 0
        for variant in DEFECTIVE_VARIANTS:
            for entry in classes:
                opportunities += 1
                verifier_hits += int(_verifier_detects(entry, variant))
                baseline_hits += int(detects(entry, variant))
        false_positives = {
            "verifier": sum(int(_verifier_detects(e, CLEAN_VARIANT)) for e in classes),
            "baseline": sum(int(detects(e, CLEAN_VARIANT)) for e in classes),
        }
        per_run.append(
            {
                "run": index + 1,
                "opportunities": opportunities,
                "verifier_detections": verifier_hits,
                "baseline_detections": baseline_hits,
                "false_positives_on_hardened": false_positives,
            }
        )

    opportunities = per_run[0]["opportunities"]
    verifier_rate = per_run[0]["verifier_detections"] / opportunities * 100
    baseline_rate = per_run[0]["baseline_detections"] / opportunities * 100
    identical = all(
        row["verifier_detections"] == per_run[0]["verifier_detections"]
        and row["baseline_detections"] == per_run[0]["baseline_detections"]
        for row in per_run
    )

    by_class = [
        {
            "class_id": entry["class_id"],
            "language_conditioned": bool(entry["language_conditioned"]),
            "publishable": bool(entry["publishable"]),
            "verifier": {
                variant: _verifier_detects(entry, variant)
                for variant in (*DEFECTIVE_VARIANTS, CLEAN_VARIANT)
            },
            "baseline": {
                variant: detects(entry, variant)
                for variant in (*DEFECTIVE_VARIANTS, CLEAN_VARIANT)
            },
        }
        for entry in classes
    ]

    return {
        "baseline_id": BASELINE_ID,
        "dataset_id": "ar_fr_exploit_classes_v1",
        "protocol": (
            "Each class is run against three reference variants (vulnerable, lucky, "
            "hardened). Detection on the two defective variants counts as a hit; "
            "detection on `hardened` counts as a false positive."
        ),
        "runs": runs,
        "opportunities_per_run": opportunities,
        "verifier_detection_pct": round(verifier_rate, 2),
        "baseline_detection_pct": round(baseline_rate, 2),
        "delta_pct": round(verifier_rate - baseline_rate, 2),
        "deterministic": identical,
        "confidence": (
            "deterministic: zero LLM in the measurement path, so repeated runs are "
            "identical and the variance is exactly zero. This makes the number fully "
            "reproducible; it is NOT a statistical confidence interval."
        )
        if identical
        else "non-deterministic: runs diverged — investigate before quoting the number",
        "reproduction_command": "python -m naas_verifier.cli run --runs 3",
        "caveat_en": CAVEAT_EN,
        "per_run": per_run,
        "by_class": by_class,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="شغّل المعيار واطبع التقرير")
    run.add_argument("--runs", type=int, default=3)
    run.add_argument("--json", action="store_true", help="اطبع JSON خاماً")
    args = parser.parse_args(argv)

    classes = load_corpus()
    report = measure(classes, args.runs)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"corpus            : {len(classes)} distinct-root classes")
    print(f"baseline          : {report['baseline_id']}")
    print(f"runs              : {report['runs']} (deterministic={report['deterministic']})")
    print(f"verifier detection: {report['verifier_detection_pct']}%")
    print(f"baseline detection: {report['baseline_detection_pct']}%")
    print(f"delta             : {report['delta_pct']} percentage points")
    fp = report["per_run"][0]["false_positives_on_hardened"]
    print(f"false positives   : verifier={fp['verifier']} baseline={fp['baseline']} (hardened)")
    print(f"\n⚠️  {report['caveat_en']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
