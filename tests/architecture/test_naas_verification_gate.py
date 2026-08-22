"""D-267 — تجارب سلبية مُثبَتة لبوّابة دستور طبقة التحقّق.

**بوّابةٌ لم تُرَ حمراء ليست بوّابة.** كل حالةٍ هنا تكسر بنداً واحداً من عقد
`check_naas_verification` على نسخةٍ من الشجرة وتُثبت أنّها تُفشِل CI.

ولماذا هذا الملفّ بهذا الحجم: الثمن الثالث في عقيدة الهندسة هو **صمتٌ يُقرأ نجاحاً**،
وهو يعيش داخل الفوارض نفسها (D-208). فبوّابةُ حوكمةٍ لم يُثبَت أنّها تصرخ هي بالضبط
الطمأنينة الكاذبة التي وُجدت لتمنعها.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts/fitness/check_naas_verification.py"

LAW_DOC = Path(".memory/naas_verification_constitution.md")
TRUTH_DOC = Path(".memory/naas_verification_truth.md")
ARCH_DOC = Path("docs/architecture/NAAS_VERIFICATION_LAYER.md")
LEDGER_DOC = Path("docs/governance/GATE_LEDGER.json")

#: ما تكسره الحالات فعلاً يُنسَخ نسخاً حقيقياً؛ وما عداه رابطٌ رمزي فيبقى الاختبار سريعاً
#: **ولا يفشل لسببٍ غير الذي يقيسه** (نفس درس `test_revenue_doctrine_gate`).
_MATERIALISED: tuple[str, ...] = (
    "scripts/fitness",
    "docs/governance",
    "docs/architecture/NAAS_VERIFICATION_LAYER.md",
    ".memory/naas_verification_constitution.md",
    ".memory/naas_verification_truth.md",
    # ⚠️ **إلزامي منذ أن صار للمنتج كود.** الحالات تُنشئ مسارات داخل `naas_verifier/`
    # (`billing` · `benchmarks` · مسارٌ محجوز)، وما دام المجلّد غير موجود كان يُنشَأ
    # داخل المرآة وحدها. فلمّا وُجد صار رابطاً رمزياً — و`mkdir` عبر الرابط **تكتب في
    # المستودع الحقيقي**: تسرّبت `naas_verifier/billing` إلى نسخة CI فأحمرّت اختبارَين
    # آخرَين لم يُنشئاها. النسخ الحقيقي يُبقي الحالة داخل صندوقها.
    "naas_verifier",
)


#: القرارات الثلاثة الممكنة لكل ابنٍ في الشجرة — قائمةٌ مغلقة لا سلاسل متناثرة.
_COPY, _DESCEND, _LINK = "copy", "descend", "link"

_ROOT_REL = Path(".")


def _materialised_paths() -> frozenset[Path]:
    return frozenset(Path(rel) for rel in _MATERIALISED)


def _parent_paths(materialised: frozenset[Path]) -> frozenset[Path]:
    """الآباء الذين يجب النزول إليهم — لا يُنسَخون ولا يُربَطون."""
    return frozenset(
        parent for rel in materialised for parent in rel.parents if parent != _ROOT_REL
    )


def _placement(child_rel: Path, materialised: frozenset[Path], parents: frozenset[Path]) -> str:
    """قرارٌ واحد لكل ابن — نقيّ، بلا أثرٍ جانبي وبلا تعشيش."""
    if child_rel in materialised:
        return _COPY
    if child_rel in parents:
        return _DESCEND
    return _LINK


def _copy_into(source: Path, target: Path) -> None:
    """نسخٌ حقيقي: الحالة ستُعدّل هذا المسار، فلا يجوز أن يكون رابطاً إلى المستودع."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)


def _link_into(source: Path, target: Path) -> None:
    """رابطٌ رمزي: يبقى الاختبار سريعاً ولا يفشل لسببٍ غير الذي يقيسه."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source)


def _children_of(rel: Path) -> list[tuple[Path, Path]]:
    """(المسار المطلق، المسار النسبي) لأبناء مستوىً واحد."""
    source = REPO_ROOT / rel if rel != _ROOT_REL else REPO_ROOT
    return [
        (child, rel / child.name if rel != _ROOT_REL else Path(child.name))
        for child in sorted(source.iterdir())
    ]


def _build_level(
    root: Path, rel: Path, materialised: frozenset[Path], parents: frozenset[Path]
) -> list[Path]:
    """يبني مستوىً واحداً ويُرجع المستويات التي تحتاج نزولاً — بلا استدعاءٍ ذاتي."""
    descend: list[Path] = []
    for child, child_rel in _children_of(rel):
        target = root / child_rel
        placement = _placement(child_rel, materialised, parents)
        if placement == _COPY:
            _copy_into(child, target)
        elif placement == _DESCEND:
            target.mkdir(parents=True, exist_ok=True)
            descend.append(child_rel)
        else:
            _link_into(child, target)
    return descend


def _mirror(tmp_path: Path) -> Path:
    """شجرةٌ قابلة للتعديل: نسخٌ حقيقي لما يُكسَر، وروابط رمزية لما عداه.

    ⚠️ `scripts/` يجب أن يكون مجلَّداً حقيقياً: البوّابة تشتقّ جذر المستودع من
    ``Path(__file__).resolve()``، و`resolve()` تتبع الروابط — فرابطٌ رمزي يعيدها إلى
    المستودع الحقيقي وتُصبح كل الحالات بلا أثر.

    ⚠️ **وقائمةُ عملٍ تكرارية لا استدعاءٌ ذاتي**: النسخة الأولى نُقلت حرفياً من
    `test_revenue_doctrine_gate` فورثت «طريق المطبّات» (حلقة ← ثلاث شُعَب ← شرطٌ ثانٍ
    ← نزولٌ ذاتي)، وردّها CodeScene على ملفٍّ **جديد** بحقّ. والقرار كان الإصلاح لا
    الإسكات (D-266 L9).
    """
    root = tmp_path / "repo"
    root.mkdir()
    materialised = _materialised_paths()
    parents = _parent_paths(materialised)
    pending = [_ROOT_REL]
    while pending:
        pending.extend(_build_level(root, pending.pop(), materialised, parents))
    return root


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    """`sys.executable` لا `python` — قاعدة نظافة الاختبارات (D-105)."""
    return subprocess.run(
        [sys.executable, str(root / GATE.relative_to(REPO_ROOT))],
        capture_output=True,
        text=True,
        check=False,
    )


def _ledger(root: Path) -> dict:
    return json.loads((root / LEDGER_DOC).read_text(encoding="utf-8"))


def _write_ledger(root: Path, ledger: dict) -> None:
    (root / LEDGER_DOC).write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _gate_of(ledger: dict, gate_id: str) -> dict:
    return next(gate for gate in ledger["gates"] if gate["gate_id"] == gate_id)


def _record(**overrides: object) -> dict:
    """سجلّ دليلٍ مكتمل وصالح — الحالات تكسر حقلاً واحداً منه فيظهر أثرُه وحده."""
    base = {
        "evidence_id": "EV-TEST-001",
        "issuer": "Cabinet Juridique Exemple",
        "qualification": "avocat agréé",
        "jurisdiction": "DZ",
        "scope": "export de services numériques",
        "decision": "favorable",
        "issued_at": "2026-08-01",
        "validity_days": 365,
        "expires_at": "2027-08-01",
        "evidence_location": "external://dossier-2026-08-01",
        "reviewer": "Houssam Benmerah",
        "review_status": "passed",
        "evidence_kind": "legal_opinion",
    }
    base.update(overrides)
    return base


def _exploit_class(index: int, root_cause: str | None = None) -> dict:
    return {
        "class_id": f"EC-{index}",
        "root_cause": root_cause or f"root-cause-{index}",
        "reproduction": f"scripts/repro_{index}.sh",
        "spec_reference": f"spec#{index}",
    }


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return _mirror(tmp_path)


# ── خطّ الأساس ──────────────────────────────────────────────────────────────────


def test_pristine_mirror_is_green(repo: Path) -> None:
    """لولا هذا لكانت كل الحالات التالية «حمراء لسببٍ آخر»."""
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


# ── ① آلة الحالات ───────────────────────────────────────────────────────────────


def test_vague_state_token_is_red(repo: Path) -> None:
    """«ربّما اجتزنا» ليست حالة — الغموض إذنٌ ضمنيّ بالتجاوز."""
    ledger = _ledger(repo)
    _gate_of(ledger, "GATE_0_LEGAL")["state"] = "probably-cleared"
    _write_ledger(repo, ledger)
    result = _run(repo)
    assert result.returncode == 1
    assert "حالةٌ خارج الستّ" in result.stdout


def test_jump_from_absent_to_cleared_is_red(repo: Path) -> None:
    """لا مراجعة = لا اعتماد."""
    ledger = _ledger(repo)
    _gate_of(ledger, "GATE_0_LEGAL")["state"] = "CLEARED"
    _write_ledger(repo, ledger)
    result = _run(repo)
    assert result.returncode == 1
    assert "بلا سجلٍّ مُراجَعٍ ناجح" in result.stdout


def test_empty_reason_is_red(repo: Path) -> None:
    """الخانة الفارغة تُقرأ نجاحاً (D-206 L11)."""
    ledger = _ledger(repo)
    _gate_of(ledger, "GATE_0_LEGAL")["reason_ar"] = "   "
    _write_ledger(repo, ledger)
    result = _run(repo)
    assert result.returncode == 1
    assert "`reason_ar` فارغ" in result.stdout


# ── ② الدليل ────────────────────────────────────────────────────────────────────


def test_machine_as_issuer_is_red(repo: Path) -> None:
    """⛔ آلةٌ تعتمد نفسها توقيعٌ على بياض — CI لا يقرّر القانون."""
    ledger = _ledger(repo)
    gate = _gate_of(ledger, "GATE_0_LEGAL")
    gate["state"] = "CLEARED"
    gate["evidence"] = [_record(issuer="CI")]
    _write_ledger(repo, ledger)
    result = _run(repo)
    assert result.returncode == 1
    assert "CI لا يقرّر القانون" in result.stdout


def test_missing_required_field_is_red(repo: Path) -> None:
    record = _record()
    record.pop("qualification")
    ledger = _ledger(repo)
    gate = _gate_of(ledger, "GATE_0_LEGAL")
    gate["state"] = "CLEARED"
    gate["evidence"] = [record]
    _write_ledger(repo, ledger)
    result = _run(repo)
    assert result.returncode == 1
    assert "ناقص الحقول" in result.stdout


def test_expiry_not_derived_is_red(repo: Path) -> None:
    """`expires_at` يُشتَقّ من `issued_at + validity_days` ولا يُكتب (D-192)."""
    ledger = _ledger(repo)
    gate = _gate_of(ledger, "GATE_0_LEGAL")
    gate["state"] = "CLEARED"
    gate["evidence"] = [_record(expires_at="2030-01-01")]
    _write_ledger(repo, ledger)
    result = _run(repo)
    assert result.returncode == 1
    assert "الرقم يُشتَقّ ولا يُكتب" in result.stdout


def test_cleared_after_expiry_is_red(repo: Path) -> None:
    """الانقضاء لا يُحمِّر CI — الادّعاءُ الكاذب بعده يُحمِّره."""
    ledger = _ledger(repo)
    gate = _gate_of(ledger, "GATE_0_LEGAL")
    gate["state"] = "CLEARED"
    gate["evidence"] = [_record(issued_at="2020-01-01", validity_days=30, expires_at="2020-01-31")]
    _write_ledger(repo, ledger)
    result = _run(repo)
    assert result.returncode == 1
    assert "انقضت" in result.stdout


def test_missing_evidence_location_inside_repo_is_red(repo: Path) -> None:
    """خريطةٌ تكذب أسوأ من غياب خريطة (ISS-149)."""
    ledger = _ledger(repo)
    gate = _gate_of(ledger, "GATE_0_LEGAL")
    gate["state"] = "CLEARED"
    gate["evidence"] = [_record(evidence_location="docs/governance/ملفّ-غير-موجود.md")]
    _write_ledger(repo, ledger)
    result = _run(repo)
    assert result.returncode == 1
    assert "`evidence_location` لا يوجد" in result.stdout


# ── ③ العتبات الكمّية ───────────────────────────────────────────────────────────


def _clear(repo: Path, gate_id: str, fields: dict) -> subprocess.CompletedProcess[str]:
    """ينقل بوّابةً إلى `CLEARED` بسجلٍّ صالحٍ ثمّ يكسر منه حقلاً واحداً."""
    ledger = _ledger(repo)
    gate = _gate_of(ledger, gate_id)
    gate["state"] = "CLEARED"
    gate["evidence"] = [_record(**fields)]
    _write_ledger(repo, ledger)
    return _run(repo)


def _clear_gate_a(repo: Path, **overrides: object) -> subprocess.CompletedProcess[str]:
    fields: dict = {
        "evidence_kind": "benchmark_run",
        "baseline_id": "unit_test_grader",
        "dataset_id": "ds-001",
        "protocol": "protocol-v1",
        "delta_pct": 22,
        "runs": 5,
        "confidence": "95%CI [12,31]",
        "reproduction_command": "python -m naas_verifier.bench",
    }
    fields.update(overrides)
    return _clear(repo, "GATE_A_TECHNICAL", fields)


def test_delta_below_threshold_is_red(repo: Path) -> None:
    """عرضٌ واحد ليس قياساً، وتحسّنٌ دون العتبة ليس تفوّقاً."""
    result = _clear_gate_a(repo, delta_pct=12)
    assert result.returncode == 1
    assert "دون العتبة" in result.stdout


def test_too_few_runs_is_red(repo: Path) -> None:
    result = _clear_gate_a(repo, runs=1)
    assert result.returncode == 1
    assert "دون الحدّ الأدنى للتكرار" in result.stdout


def test_gate_a_missing_extra_field_is_red(repo: Path) -> None:
    ledger = _ledger(repo)
    gate = _gate_of(ledger, "GATE_A_TECHNICAL")
    gate["state"] = "CLEARED"
    gate["evidence"] = [_record(evidence_kind="benchmark_run")]
    _write_ledger(repo, ledger)
    result = _run(repo)
    assert result.returncode == 1
    assert "بحقولٍ ناقصة" in result.stdout


def _clear_gate_b(repo: Path, classes: list[dict]) -> subprocess.CompletedProcess[str]:
    fields: dict = {"evidence_kind": "exploit_reproduction", "exploit_classes": classes}
    return _clear(repo, "GATE_B_EXPLOIT_BREADTH", fields)


def test_shared_root_cause_is_not_three_classes(repo: Path) -> None:
    """⛔ ثلاث صيغٍ من جذرٍ واحد ليست ثلاثة أصناف — الاتّساع يُقاس بالجذور."""
    same = [_exploit_class(i, root_cause="test-leakage") for i in range(1, 4)]
    result = _clear_gate_b(repo, same)
    assert result.returncode == 1
    assert "تتشارك `root_cause`" in result.stdout


def test_two_classes_below_minimum_is_red(repo: Path) -> None:
    result = _clear_gate_b(repo, [_exploit_class(1), _exploit_class(2)])
    assert result.returncode == 1
    assert "دون الحدّ الأدنى" in result.stdout


def _clear_gate_c(repo: Path, **overrides: object) -> subprocess.CompletedProcess[str]:
    fields: dict = {
        "evidence_kind": "settled_transaction",
        "transaction_id": "TX-1",
        "buyer": "Lab Example",
        "amount_usd": 2500,
        "settled_at": "2026-08-10",
    }
    fields.update(overrides)
    return _clear(repo, "GATE_C_COMMERCIAL", fields)


def test_unpaid_loi_is_rejected_as_evidence(repo: Path) -> None:
    """خطابُ نيّةٍ غير مدفوع انطباعٌ لا دليل."""
    result = _clear_gate_c(repo, evidence_kind="unpaid_loi")
    assert result.returncode == 1
    assert "مرفوضٌ كدليل" in result.stdout


def test_zero_amount_is_red(repo: Path) -> None:
    """أعلى إشارةٍ ممكنة معاملةٌ مُسوّاة بمبلغٍ موجب."""
    result = _clear_gate_c(repo, amount_usd=0)
    assert result.returncode == 1
    assert "الدليل الوحيد المقبول" in result.stdout


# ── ④ الحجب المحدود (L8) ────────────────────────────────────────────────────────


def test_commercial_artifact_without_legal_gate_is_red(repo: Path) -> None:
    """الفعل التجاري الخارجي محجوبٌ ما دام `GATE_0` غير مُعتمَد."""
    (repo / "naas_verifier/billing").mkdir(parents=True)
    (repo / "naas_verifier/billing/stripe.py").write_text("# ...\n", encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 1
    assert "أثرٌ تجاريّ خارجي" in result.stdout


def test_research_work_stays_green_while_legal_gate_is_absent(repo: Path) -> None:
    """⛔ **الحوكمة تمنع خداع الذات لا العمل** — وهذا هو البند الذي يمنع البيروقراطية."""
    (repo / "naas_verifier/benchmarks").mkdir(parents=True)
    (repo / "naas_verifier/benchmarks/run_bench.py").write_text(
        "import json\n\n\ndef main() -> None:\n    print(json.dumps({'ok': True}))\n",
        encoding="utf-8",
    )
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


# ── ⑤ وثيقة الحالة ──────────────────────────────────────────────────────────────


#: حالات «غير مبنيّة» كما يعرّفها الفارض (`UNBUILT_STATUSES`).
_UNBUILT = frozenset({"ABSENT", "PLANNED", "SEAM"})


def _truth_rows(repo: Path) -> list[tuple[str, list[str]]]:
    """(السطر الخام، خلاياه) لصفوف وحدات وثيقة الحالة المرقَّمة."""
    rows: list[tuple[str, list[str]]] = []
    for line in (repo / TRUTH_DOC).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip().strip("`*").strip() for cell in stripped.strip("|").split("|")]
        if len(cells) >= 6 and cells[0].isdigit():
            rows.append((line, cells))
    return rows


def _first_unbuilt_reserved_path(repo: Path) -> Path:
    """مسارٌ محجوز لوحدةٍ ما زالت مُصنَّفة غير مبنيّة — **مُشتَقٌّ لا مُثبَّت يدوياً**.

    النسخة الأولى ثبّتت `naas_verifier/corpus`. ولمّا بُنيت الذخيرة ورُقّيت إلى
    `ACTIVE` بدليلها، صار المسار موجوداً فانفجر `mkdir` بـ`FileExistsError` — أي أنّ
    الاختبار توقّف عن قياس أيّ شيء لأن **فرضيّته** تقادمت لا لأن القاعدة انكسرت.
    والاشتقاق من وثيقة الحالة يمنع تكرار ذلك (D-192: الرقم يُشتَقّ ولا يُكتب).
    """
    for _line, cells in _truth_rows(repo):
        if cells[4] not in _UNBUILT:
            continue
        reserved = repo / cells[2].rstrip("/")
        if not reserved.exists():
            return reserved
    raise AssertionError(
        "no unbuilt unit left in the truth table — this rule can no longer be exercised"
    )


def _first_non_active_row(repo: Path) -> tuple[str, list[str]]:
    """صفٌّ تنطبق عليه قاعدة «الفجوة الفارغة» — أي **غير** `ACTIVE`.

    الفارض يعفي `ACTIVE` صراحةً (`status != "ACTIVE" and gap in {"", "—"}`)، فتثبيت
    الصفّ الأوّل جعل الحالة تنهار لحظة ترقيته. نفس علاج التقادم: اشتقاقٌ من الوثيقة.
    """
    for line, cells in _truth_rows(repo):
        if cells[4] != "ACTIVE":
            return line, cells
    raise AssertionError("every unit is ACTIVE — the empty-gap rule cannot be exercised")


def test_unbuilt_unit_with_code_is_red(repo: Path) -> None:
    """الاتجاه المعاكس: كودٌ حيّ بلا حارسٍ أسوأ من الغياب (D-210)."""
    reserved = _first_unbuilt_reserved_path(repo)
    reserved.mkdir(parents=True)
    (reserved / "classes.py").write_text("CLASSES = []\n", encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 1
    assert "ولها كودٌ على القرص" in result.stdout


def test_empty_gap_cell_is_red(repo: Path) -> None:
    doc = repo / TRUTH_DOC
    text = doc.read_text(encoding="utf-8")
    line, _cells = _first_non_active_row(repo)
    cells = line.strip().strip("|").split("|")
    cells[5] = "  "  # عمود «الفجوة الصادقة»
    doc.write_text(text.replace(line, "|" + "|".join(cells) + "|"), encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 1
    assert "خانةُ فجوةٍ فارغة" in result.stdout


def test_silent_unit_deletion_is_red(repo: Path) -> None:
    doc = repo / TRUTH_DOC
    text = doc.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("| 5 |"))
    doc.write_text(text.replace(line + "\n", ""), encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 1
    assert "حذفٌ صامت" in result.stdout


def test_invented_status_is_red(repo: Path) -> None:
    doc = repo / TRUTH_DOC
    doc.write_text(
        doc.read_text(encoding="utf-8").replace("| `SEAM` |", "| `قيد العمل` |", 1),
        encoding="utf-8",
    )
    result = _run(repo)
    assert result.returncode == 1
    assert "حالةٌ خارج السُّلَّم" in result.stdout


# ── ⑥ القانون والمصداقية ────────────────────────────────────────────────────────


def test_law_doc_carrying_unit_state_is_red(repo: Path) -> None:
    """⛔ خريطتان لنظامٍ واحد = وكيلان يقرآن بناءَين مختلفين (ISS-139)."""
    doc = repo / ARCH_DOC
    doc.write_text(
        doc.read_text(encoding="utf-8")
        + "\n\n| الوحدة | الحالة |\n|---|---|\n| القلب | ACTIVE |\n",
        encoding="utf-8",
    )
    result = _run(repo)
    assert result.returncode == 1
    assert "رموز حالةٍ" in result.stdout


def test_missing_verification_dimension_is_red(repo: Path) -> None:
    """الحكم على المخرَج وحده مُصحِّح لا مُتحقِّق (L3)."""
    doc = repo / ARCH_DOC
    doc.write_text(
        doc.read_text(encoding="utf-8").replace("intermediate constraints", "—"),
        encoding="utf-8",
    )
    result = _run(repo)
    assert result.returncode == 1
    assert "الأبعاد الخمسة ناقصة" in result.stdout


def test_unfalsifiable_claim_is_red(repo: Path) -> None:
    """تُصدَّق مرّة، ثمّ تُكتشَف، ثمّ يسقط معها كلُّ ما هو صحيح (D-227)."""
    doc = repo / LAW_DOC
    doc.write_text(
        doc.read_text(encoding="utf-8") + "\n\nنجاحُ هذا المُتحقِّق مضمون.\n",
        encoding="utf-8",
    )
    result = _run(repo)
    assert result.returncode == 1
    assert "غير قابلة للتفنيد" in result.stdout


def test_price_without_hypothesis_marker_is_red(repo: Path) -> None:
    """فرضيةُ سعرٍ ليست دليلَ تسعير — والرقم بلا وسمٍ يُقرأ بعد أسبوعين دليلاً."""
    doc = repo / LAW_DOC
    doc.write_text(
        doc.read_text(encoding="utf-8") + "\n\nسعر التدقيق الأوّلي $5000 للدفعة.\n",
        encoding="utf-8",
    )
    result = _run(repo)
    assert result.returncode == 1
    assert "رقمُ مالٍ بلا وسم" in result.stdout


def test_law_missing_a_law_row_is_red(repo: Path) -> None:
    """القوانين عشرة — والعدد يُشتَقّ من النصّ لا يُكتب."""
    doc = repo / LAW_DOC
    text = doc.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("| L7 |"))
    doc.write_text(text.replace(line + "\n", ""), encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 1
    assert "ليست عشرة كاملة" in result.stdout


def test_scientific_distinction_removed_is_red(repo: Path) -> None:
    """⛔ «اختبارٌ معيب» ليست «اختراق مكافأة» — والخلط يُسقِط الأطروحة العلمية."""
    doc = repo / LAW_DOC
    doc.write_text(
        doc.read_text(encoding="utf-8").replace("verifier exploitability", "—"),
        encoding="utf-8",
    )
    result = _run(repo)
    assert result.returncode == 1
    assert "التمييز العلمي ناقص" in result.stdout
