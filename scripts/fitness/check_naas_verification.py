#!/usr/bin/env python3
"""بوّابة دستور طبقة التحقّق — D-267 / ISS-187→ISS-190.

## لماذا هذه البوّابة موجودة

القرار المعماري (2026-08-18) جعل `NAAS Verification Layer` منتجاً بحدٍّ مستقلّ. وأضعف
حلقةٍ في سلسلة أدلّته أعلنها التقرير الذي أقرّه بنفسه: **لا عقد تدقيقٍ خارجيّ مدفوع
مؤكّد** — أي أنّ السلسلة تنكسر عند **الدفع الحقيقي** لا عند المشكلة ولا عند الميزانية.

وهذا صنف العطب الذي يحرسه المستودع منذ §6.6: قدرةٌ تُقرأ مُثبَتة وهي ناقصةٌ ساقاً.
فإضافةُ نصٍّ إلى مستودعٍ ليست إضافةَ قانون (D-265)، وفارضٌ لا يُنفَّذ ليس فارضاً (D-266).

## ما تفحصه (قانون D-267 §4 — L1→L10)

1. **اكتمال الوثائق**: الدستور + المواصفة المعمارية + قانون البوّابات + المخطّط +
   السجلّ + وثيقة الحالة — كلّها موجودة، والقوانين عشرة تماماً (عددٌ يُشتَقّ لا يُكتب).
2. **الفصل بين القانون والحالة** (D-188): وثيقتا القانون لا تحملان عمود حالة.
3. **الأبعاد الخمسة** (L3): المواصفة تُعلنها مجتمعةً — أو ليس مُتحقِّقاً.
4. **وثيقة الحالة**: حالةٌ من السُّلَّم القانوني · فجوةٌ غير فارغة · دليلٌ موجود ·
   ⛔ ووحدةٌ مُعلَنة غير مبنيّة **يجب ألّا يوجد لها كود** (الاتجاه المعاكس — نمط
   `check_revenue_doctrine`) · ولا حذف صامت لأيّ وحدة.
5. **آلة الحالات** (L6): ستّ حالاتٍ لا غير، ولا رمز حالةٍ غامض (`probably-cleared`…).
6. **الدليل** (L7): حقولٌ إلزامية كاملة · `evidence_kind` من القائمة البيضاء ·
   ⛔ و`issuer`/`reviewer` **ليسا آلة** — آلةٌ تعتمد نفسها توقيعٌ على بياض.
7. **الانتهاء** (§5): `expires_at` **مُشتَقّ** من `issued_at + validity_days`؛ وادّعاء
   `CLEARED` بعد انقضائه ⇒ أحمر. والانقضاء بذاته لا يُحمِّر — الادّعاء الكاذب يُحمِّر.
8. **العتبات** (L9): `delta_pct ≥ 15` و`runs ≥ 3` · `≥ 3` أصناف اختراقٍ **متمايزة
   الجذر** · معاملةٌ مُسوّاة بمبلغٍ موجب. ومرفوضٌ كدليل: نجومٌ · اجتماع · خطاب نيّةٍ
   غير مدفوع · تجربةٌ مجّانية.
9. **الحجب المحدود** (L8): أثرٌ تجاريّ خارجي بلا `GATE_0 = CLEARED` ⇒ أحمر. ⛔ ومسارات
   البحث والتطوير **خارج المسح صراحةً** — الحوكمة تمنع خداع الذات لا العمل.
10. **الحدود البنيوية** (L1/L2/L5/L4 — AST): لا استيراد عابر بين مسار المنتج ومسار
    الطالب · لا مجال داخل القلب · لا ذخيرةٍ في مسار الطالب · لا حَكَم نموذجٍ في القلب.
11. **حدّ المصداقية** (L10 · يمدّد D-227): لا عبارة غير قابلة للتفنيد، ولا رقم سعرٍ
    بلا وسم فرضية.

**لا تُستورد من `app/`** (نمط `check_pedagogical_os.py`) — نصّية/AST خالصة تعمل في بيئة
متدهورة. Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ast_util import parse_source, run_gate

REPO_ROOT = Path(__file__).resolve().parents[2]

LAW_DOC = ".memory/naas_verification_constitution.md"
ARCH_DOC = "docs/architecture/NAAS_VERIFICATION_LAYER.md"
GATE_LAW_DOC = "docs/governance/GATE_STATE_MACHINE.md"
SCHEMA_DOC = "docs/governance/evidence_schema.json"
LEDGER_DOC = "docs/governance/GATE_LEDGER.json"
TRUTH_DOC = ".memory/naas_verification_truth.md"

#: وثائق §0.19 كلّها — نطاق حدّ المصداقية وفحص الروابط.
DOCS = (LAW_DOC, ARCH_DOC, GATE_LAW_DOC, SCHEMA_DOC, LEDGER_DOC, TRUTH_DOC)

#: السُّلَّم القانوني الوحيد (§6.6 + SEAM/ABSENT من D-207 + PLANNED من D-146).
VALID_STATUSES = frozenset({"ACTIVE", "PARTIAL", "DORMANT", "ZOMBIE", "PLANNED", "SEAM", "ABSENT"})

#: حالاتٌ تعني «لم يُبنَ بعد» — فوجودُ كودٍ لها تناقضٌ يُفشِل CI (الاتجاه المعاكس).
UNBUILT_STATUSES = frozenset({"ABSENT", "PLANNED", "SEAM"})

#: الأبعاد الخمسة (L3) — مجتمعةً أو ليس مُتحقِّقاً.
VERIFICATION_DIMENSIONS = (
    "observable outcomes",
    "intermediate constraints",
    "state transitions",
    "tool use",
    "final outcome",
)

#: وحدات طبقة التحقّق — الحذف الصامت لأيّ منها يُفشِل CI (D-209).
REQUIRED_UNITS = (
    "القلب المستقلّ عن المجال",
    "مُحوِّل المجال (السلّم)",
    "ذخيرة أصناف الاختراق",
    "خطوط الأساس للمقارنة",
    "طبقة المعايرة القياسية",
    "التحقّق الصوريّ المساعد",
    "حزمة الأدلّة والحوكمة",
    "تنفيذ الرقع العدائية في صندوق",
)

#: البوّابات الأربع — أسماؤها عقدٌ لا تسمية.
REQUIRED_GATES = (
    "GATE_0_LEGAL",
    "GATE_A_TECHNICAL",
    "GATE_B_EXPLOIT_BREADTH",
    "GATE_C_COMMERCIAL",
)

#: آثارٌ تجارية خارجية — وجودُ أيٍّ منها بلا `GATE_0 = CLEARED` ⇒ أحمر (L8).
COMMERCIAL_ARTIFACT_MARKERS = (
    "naas_verifier/billing",
    "naas_verifier/contracts/signed",
    "infra/deploy/naas_verifier_production.yml",
)

#: ⛔ مسارات البحث والتطوير — **خارج المسح صراحةً** (L8 · GATE_STATE_MACHINE §7).
#: تُكتب هنا كي يكون السماحُ مُعلَناً لا مُستنتَجاً (D-206 L11).
RESEARCH_PATHS_ALWAYS_ALLOWED = (
    "naas_verifier/core",
    "naas_verifier/adapters",
    "naas_verifier/baselines",
    "naas_verifier/corpus",
    "naas_verifier/calibration",
    "naas_verifier/formal",
    "naas_verifier/benchmarks",
)

#: عباراتٌ غير قابلة للتفنيد (يمدّد D-227). سطرُ **نهيٍ** يبدأ بـ⛔ مُستثنى منطوقاً:
#: القانون يجب أن يستطيع تسمية ما يحظره (D-208 §7 — الاستثناء يُصرَّح ولا يُصمَت عنه).
UNFALSIFIABLE_CLAIMS = (
    "مضمون",
    "guaranteed",
    "صفر أخطاء",
    "يغيّر البشرية",
    "دقّة تامّة",
    "100%",
    "١٠٠٪",
)

#: أنماط المال — كل سطرٍ يحملها يجب أن يحمل وسم الفرضية (L10).
_MONEY = re.compile(r"[$＄]\s?\d")
_HYPOTHESIS_MARKERS = ("PRICING HYPOTHESIS", "MARKET HYPOTHESIS")

#: استيراداتٌ ممنوعة داخل قلب المُتحقِّق (L1/L2/L4).
CORE_FORBIDDEN_IMPORT_ROOTS = ("app", "microservices", "shared", "openai", "anthropic", "httpx")

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _ok(msg: str) -> None:
    print(f"✅ {msg}")


def _note(msg: str) -> None:
    """غيابٌ مُعلَن — يُقال ولا يُقرأ نجاحاً (D-206 L11)."""
    print(f"ℹ️  {msg}")


def _ok_unless_failed(mark: int, msg: str) -> None:
    """✅ بعد ❌ في الفحص نفسه تقريرٌ يناقض نفسه — فلا تُطبَع إلّا عند نظافةٍ فعلية."""
    if len(_FAILURES) == mark:
        _ok(msg)


def _read(rel: str) -> str:
    path = REPO_ROOT / rel
    if not path.is_file():
        _fail(f"ملفّ مفقود: {rel}")
        return ""
    return path.read_text(encoding="utf-8")


def _load_json(rel: str) -> dict:
    text = _read(rel)
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        _fail(f"{rel}: ليس JSON صالحاً — {exc}")
        return {}


def _table_rows(text: str) -> list[list[str]]:
    """صفوف جداول ماركداون المرقَّمة: `| 1 | … |` ⇒ قائمة خلايا."""
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and cells[0].isdigit():
            rows.append(cells)
    return rows


# ── ① اكتمال القانون ────────────────────────────────────────────────────────────


def _check_law_completeness(law: str) -> None:
    for heading in (
        r"## 1\. التشخيص الدستوري",
        r"## 2\. العقيدة الأساسية",
        r"## 3\. الطبقات الثلاث",
        r"## 4\. القوانين العشرة",
        r"## 5\. الأسئلة الدستورية",
        r"## 6\. علاقة هذا الدستور بالعقائد القائمة",
        r"## 7\. قاعدة التحديث",
    ):
        if not re.search(heading, law):
            _fail(f"{LAW_DOC}: قسمٌ مفقود `{heading}`")

    laws = re.findall(r"^\| L(\d+) \|", law, flags=re.M)
    if set(laws) != {str(i) for i in range(1, 11)}:
        _fail(f"{LAW_DOC}: القوانين ليست عشرة كاملة (وُجدت: {sorted(laws, key=int)})")
        return
    _ok("الدستور D-267 مكتمل — سبعة أقسام والقوانين L1–L10")


def _check_scientific_distinction(law: str) -> None:
    """§4.2 — الخلط بين «اختبارٍ معيب» و«اختراق المكافأة» يُسقِط الأطروحة العلمية."""
    for term in ("flawed test", "reward hacking", "verifier exploitability"):
        if term not in law:
            _fail(f"{LAW_DOC}: التمييز العلمي ناقص — المصطلح `{term}` غائب (§4.2)")
            return
    _ok("التمييز العلمي الثلاثي حاضر (§4.2)")


#: إسنادُ حالةٍ لبوّابةٍ بعينها — `GATE_X = CLEARED`. الشرطُ (`≠`) وصفُ قانونٍ لا حالة.
_GATE_STATE_ASSIGNMENT = re.compile(
    r"GATE_[0A-Z_]+\s*=\s*(?:ABSENT|PENDING|CLEARED|BLOCKED|EXPIRED|REASSESS_REQUIRED)"
)

#: رموز سُلَّم §6.6 ككلماتٍ قائمة بذاتها.
_RUNTIME_STATUS_TOKEN = re.compile(r"\b(?:ACTIVE|PARTIAL|DORMANT|ZOMBIE|PLANNED|SEAM)\b")


def _check_law_carries_no_state() -> None:
    """D-188: وثيقةُ قانونٍ تحمل حالةً تتقادم ثمّ تكذب.

    ⚠️ التمييز المقصود: **تعريفُ** الحالات الستّ وظيفةُ وثيقة قانون البوّابات — وهو
    قانونٌ لا حالة. الممنوع هو **إسنادُ** حالةٍ لبوّابةٍ بعينها، أو رمزُ سُلَّم §6.6
    لوحدةٍ بعينها؛ فموطن ذلك السجلّ ووثيقة الحالة.
    """
    arch = _read(ARCH_DOC)
    leaked = _RUNTIME_STATUS_TOKEN.findall(arch)
    if leaked:
        _fail(
            f"{ARCH_DOC}: رموز حالةٍ {sorted(set(leaked))} في وثيقة قانون — موطنها {TRUTH_DOC} (D-188)"
        )
        return
    assigned = _GATE_STATE_ASSIGNMENT.findall(_read(GATE_LAW_DOC))
    if assigned:
        _fail(f"{GATE_LAW_DOC}: إسنادُ حالةٍ {assigned} في وثيقة قانون — موطنها {LEDGER_DOC} (D-188)")
        return
    _ok("فصلٌ نظيف: وثائق القانون تُعرِّف الحالات ولا تُسندها")


def _check_five_dimensions(arch: str) -> None:
    missing = [dim for dim in VERIFICATION_DIMENSIONS if dim not in arch]
    if missing:
        _fail(f"{ARCH_DOC}: الأبعاد الخمسة ناقصة {missing} — الحكم على المخرَج وحده ليس تحقّقاً (L3)")
        return
    _ok("الأبعاد الخمسة للتحقّق مُعلَنة مجتمعةً (L3)")


# ── ② وثيقة الحالة ──────────────────────────────────────────────────────────────


def _cell(value: str) -> str:
    """خليّةٌ مُجرَّدة من زينة الماركداون — العلامة الفارقة قيمةٌ لا شكل."""
    return value.strip().strip("`*").strip()


def _check_truth_row(cells: list[str]) -> None:
    number, unit = _cell(cells[0]), _cell(cells[1])
    reserved, evidence = _cell(cells[2]), _cell(cells[3])
    status, gap = _cell(cells[4]), _cell(cells[5])
    if status not in VALID_STATUSES:
        _fail(f"{TRUTH_DOC}#{number} «{unit}»: حالةٌ خارج السُّلَّم `{status}`")
    if status != "ACTIVE" and gap in {"", "—"}:
        _fail(f"{TRUTH_DOC}#{number} «{unit}»: خانةُ فجوةٍ فارغة — الفراغ يُقرأ نجاحاً (L6)")
    if evidence and not (REPO_ROOT / evidence).exists():
        _fail(f"{TRUTH_DOC}#{number} «{unit}»: دليلٌ لا يوجد `{evidence}` (ISS-149)")
    _check_unbuilt_has_no_code(number, unit, reserved, status)


def _check_unbuilt_has_no_code(number: str, unit: str, reserved: str, status: str) -> None:
    """الاتجاه المعاكس: وحدةٌ مُعلَنة غير مبنيّة ولها كود ⇒ الإعلان يكذب."""
    if status not in UNBUILT_STATUSES:
        return
    path = REPO_ROOT / reserved.rstrip("/")
    if path.exists():
        _fail(
            f"{TRUTH_DOC}#{number} «{unit}»: مُعلَنة `{status}` ولها كودٌ على القرص "
            f"`{reserved}` — كودٌ حيّ بلا حارسٍ أسوأ من الغياب (D-210)"
        )


def _check_truth_doc(truth: str) -> None:
    mark = len(_FAILURES)
    rows = _table_rows(truth)
    if not rows:
        _fail(f"{TRUTH_DOC}: لا صفوف وحداتٍ مقروءة — بوّابةٌ لا تقرأ مصدرها لا تشهد بنظافته")
        return
    for cells in rows:
        if len(cells) < 7:
            _fail(f"{TRUTH_DOC}: صفٌّ ناقص الأعمدة {cells[:2]}")
            continue
        _check_truth_row(cells)

    declared = {cells[1] for cells in rows if len(cells) >= 2}
    missing = [unit for unit in REQUIRED_UNITS if unit not in declared]
    if missing:
        _fail(f"{TRUTH_DOC}: حذفٌ صامت لوحدات {missing} — لا صفَّ يُحذف بصمت (D-209)")
        return
    _ok_unless_failed(mark, f"وثيقة الحالة: {len(rows)} وحدة، كلٌّ بدليلٍ موجود وفجوةٍ منطوقة")


# ── ③ آلة الحالات والدليل ───────────────────────────────────────────────────────


def _check_ledger_shape(ledger: dict, schema: dict) -> list[dict]:
    gates = ledger.get("gates")
    if not isinstance(gates, list):
        _fail(f"{LEDGER_DOC}: المفتاح `gates` يجب أن يكون قائمة")
        return []
    ids = [str(gate.get("gate_id")) for gate in gates]
    missing = [gate_id for gate_id in REQUIRED_GATES if gate_id not in ids]
    if missing:
        _fail(f"{LEDGER_DOC}: بوّاباتٌ مفقودة {missing}")
    valid_states = set(schema.get("gate_states", []))
    for gate in gates:
        _check_gate_state_token(gate, valid_states)
    return gates


def _check_gate_state_token(gate: dict, valid_states: set[str]) -> None:
    gate_id = gate.get("gate_id")
    state = str(gate.get("state", ""))
    if state not in valid_states:
        _fail(f"{LEDGER_DOC} · {gate_id}: حالةٌ خارج الستّ `{state}` — الغموض إذنٌ ضمنيّ بالتجاوز (L6)")
    if not str(gate.get("reason_ar", "")).strip():
        _fail(f"{LEDGER_DOC} · {gate_id}: `reason_ar` فارغ — الخانة الفارغة تُقرأ نجاحاً (L6)")


def _check_forbidden_state_tokens(schema: dict) -> None:
    text = _read(LEDGER_DOC).lower()
    hits = [token for token in schema.get("forbidden_state_tokens", []) if token.lower() in text]
    if hits:
        _fail(f"{LEDGER_DOC}: رموز حالةٍ غامضة {hits} — ممنوعة نصّياً (L6)")
        return
    _ok("سجلّ البوّابات: الحالات من الستّ حصراً، ولكلٍّ سببٌ منطوق")


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _check_record_fields(gate_id: str, record: dict, schema: dict) -> None:
    missing = [field for field in schema.get("required_fields", []) if field not in record]
    if missing:
        _fail(f"{LEDGER_DOC} · {gate_id}: سجلّ دليلٍ ناقص الحقول {missing} (L7)")
    kind = str(record.get("evidence_kind", ""))
    if kind in schema.get("rejected_evidence_kinds", []):
        _fail(
            f"{LEDGER_DOC} · {gate_id}: `{kind}` مرفوضٌ كدليل — أعلى إشارةٍ معاملةٌ "
            f"مُسوّاة، وما دونها انطباع (L9)"
        )
    elif kind and kind not in schema.get("allowed_evidence_kinds", []):
        _fail(f"{LEDGER_DOC} · {gate_id}: `evidence_kind` خارج القائمة البيضاء `{kind}`")
    _check_evidence_location(gate_id, record)


#: بادئاتٌ تعني «الدليل داخل المستودع» — فيجب أن يوجد (ISS-149: خريطةٌ تكذب أسوأ من لا خريطة).
_IN_REPO_PREFIXES = ("docs/", ".memory/", "scripts/", "tests/", "naas_verifier/")


def _check_evidence_location(gate_id: str, record: dict) -> None:
    location = str(record.get("evidence_location", "")).strip()
    if not location.startswith(_IN_REPO_PREFIXES):
        return
    if not (REPO_ROOT / location).exists():
        _fail(f"{LEDGER_DOC} · {gate_id}: `evidence_location` لا يوجد `{location}` (ISS-149)")


def _check_record_authorship(gate_id: str, record: dict, schema: dict) -> None:
    """⛔ آلةٌ تعتمد نفسها ليست مراجعة — هي توقيعٌ على بياض (L7)."""
    forbidden = {name.lower() for name in schema.get("forbidden_issuers", [])}
    for field in ("issuer", "reviewer"):
        value = str(record.get(field, "")).strip().lower()
        if value in forbidden:
            _fail(
                f"{LEDGER_DOC} · {gate_id}: `{field}` = `{value}` — CI لا يقرّر القانون، "
                f"يتحقّق من دليلٍ مطابقٍ للمخطّط فقط (L7)"
            )


def _check_record_expiry(gate_id: str, record: dict) -> None:
    issued = _parse_date(str(record.get("issued_at", "")))
    expires = _parse_date(str(record.get("expires_at", "")))
    validity = record.get("validity_days")
    if issued is None or expires is None:
        _fail(f"{LEDGER_DOC} · {gate_id}: تاريخٌ غير صالح في سجلّ الدليل (YYYY-MM-DD)")
        return
    if not isinstance(validity, int) or validity <= 0:
        _fail(f"{LEDGER_DOC} · {gate_id}: `validity_days` يجب أن يكون عدداً موجباً")
        return
    derived = issued + timedelta(days=validity)
    if expires != derived:
        _fail(
            f"{LEDGER_DOC} · {gate_id}: `expires_at` مكتوبٌ {expires} بينما المُشتَقّ "
            f"{derived} — الرقم يُشتَقّ ولا يُكتب (D-192)"
        )


def _check_records(gates: list[dict], schema: dict) -> None:
    count = 0
    for gate in gates:
        gate_id = str(gate.get("gate_id"))
        records = gate.get("evidence", [])
        if not isinstance(records, list):
            _fail(f"{LEDGER_DOC} · {gate_id}: `evidence` يجب أن يكون قائمة")
            continue
        for record in records:
            count += 1
            _check_record_fields(gate_id, record, schema)
            _check_record_authorship(gate_id, record, schema)
            _check_record_expiry(gate_id, record)
    _ok(f"سجلّات الأدلّة: {count} سجلّاً مفحوصاً (الصفر حالةٌ ابتدائية صادقة)")


# ── ④ اتّساق الحالة مع الدليل + العتبات ─────────────────────────────────────────


def _passed_records(gate: dict) -> list[dict]:
    records = gate.get("evidence", [])
    if not isinstance(records, list):
        return []
    return [rec for rec in records if str(rec.get("review_status")) == "passed"]


def _check_state_consistency(gate: dict) -> None:
    gate_id = str(gate.get("gate_id"))
    state = str(gate.get("state"))
    records = gate.get("evidence", []) if isinstance(gate.get("evidence"), list) else []
    if state == "ABSENT" and records:
        _fail(f"{LEDGER_DOC} · {gate_id}: `ABSENT` مع سجلّات دليل — الحالة تكذب على سجلّها")
    if state in {"CLEARED", "EXPIRED"} and not _passed_records(gate):
        _fail(
            f"{LEDGER_DOC} · {gate_id}: `{state}` بلا سجلٍّ مُراجَعٍ ناجح — "
            f"القفزة `ABSENT → CLEARED` ممنوعة (§3)"
        )
    if state == "BLOCKED":
        _check_blocked_has_decision(gate_id, records)


def _check_blocked_has_decision(gate_id: str, records: list[dict]) -> None:
    failed = [rec for rec in records if str(rec.get("review_status")) == "failed"]
    if not failed:
        _fail(f"{LEDGER_DOC} · {gate_id}: `BLOCKED` بلا سجلّ مراجعةٍ فاشلة")
        return
    if not any(str(rec.get("decision", "")).strip() for rec in failed):
        _fail(f"{LEDGER_DOC} · {gate_id}: `BLOCKED` بلا قرارٍ منطوق")


def _check_cleared_not_stale(gate: dict) -> None:
    """`CLEARED` بعد انقضاء الصلاحية ادّعاءٌ كاذب — والانقضاء بذاته لا يُحمِّر (§4)."""
    if str(gate.get("state")) != "CLEARED":
        return
    today = datetime.now(UTC).date()
    gate_id = str(gate.get("gate_id"))
    for record in _passed_records(gate):
        expires = _parse_date(str(record.get("expires_at", "")))
        if expires is not None and today > expires:
            _fail(
                f"{LEDGER_DOC} · {gate_id}: `CLEARED` وصلاحيةُ دليله انقضت في {expires} — "
                f"حدِّثها إلى `EXPIRED` (§4)"
            )


def _check_gate_extra_fields(gate: dict, schema: dict) -> None:
    gate_id = str(gate.get("gate_id"))
    if str(gate.get("state")) != "CLEARED":
        return
    required = schema.get("gate_extra_fields", {}).get(gate_id, [])
    for record in _passed_records(gate):
        missing = [field for field in required if field not in record]
        if missing:
            _fail(f"{LEDGER_DOC} · {gate_id}: `CLEARED` بحقولٍ ناقصة {missing} (§5)")


def _check_technical_threshold(gate: dict, schema: dict) -> None:
    limits = schema.get("thresholds", {}).get("GATE_A_TECHNICAL", {})
    for record in _passed_records(gate):
        delta = record.get("delta_pct")
        runs = record.get("runs")
        if isinstance(delta, (int, float)) and delta < limits.get("delta_pct_min", 15):
            _fail(
                f"{LEDGER_DOC} · GATE_A: `delta_pct = {delta}` دون العتبة — عرضٌ واحد ليس قياساً (L9)"
            )
        if isinstance(runs, int) and runs < limits.get("runs_min", 3):
            _fail(f"{LEDGER_DOC} · GATE_A: `runs = {runs}` دون الحدّ الأدنى للتكرار (L9)")


def _check_exploit_breadth(gate: dict, schema: dict) -> None:
    limits = schema.get("thresholds", {}).get("GATE_B_EXPLOIT_BREADTH", {})
    fields = schema.get("exploit_class_required_fields", [])
    for record in _passed_records(gate):
        classes = record.get("exploit_classes", [])
        if not isinstance(classes, list) or len(classes) < limits.get("exploit_classes_min", 3):
            _fail(f"{LEDGER_DOC} · GATE_B: أصنافُ الاختراق دون الحدّ الأدنى (L9)")
            continue
        _check_classes_distinct(classes, fields)


def _check_classes_distinct(classes: list[dict], fields: list[str]) -> None:
    roots = [str(item.get("root_cause", "")).strip() for item in classes]
    if len(set(roots)) != len(roots):
        _fail(
            f"{LEDGER_DOC} · GATE_B: أصنافٌ تتشارك `root_cause` — ثلاث صيغٍ من جذرٍ "
            f"واحد ليست ثلاثة أصناف (L9)"
        )
    ids = [str(item.get("class_id", "")).strip() for item in classes]
    if len(set(ids)) != len(ids):
        _fail(f"{LEDGER_DOC} · GATE_B: `class_id` مكرَّر")
    for item in classes:
        missing = [field for field in fields if not str(item.get(field, "")).strip()]
        if missing:
            _fail(f"{LEDGER_DOC} · GATE_B: صنفٌ ناقص الحقول {missing}")


def _check_commercial_evidence(gate: dict) -> None:
    for record in _passed_records(gate):
        amount = record.get("amount_usd")
        if not isinstance(amount, (int, float)) or amount <= 0:
            _fail(
                f"{LEDGER_DOC} · GATE_C: `amount_usd = {amount}` — الدليل الوحيد المقبول "
                f"معاملةٌ مُسوّاة بمبلغٍ موجب (L9)"
            )
        if not str(record.get("transaction_id", "")).strip():
            _fail(f"{LEDGER_DOC} · GATE_C: `transaction_id` فارغ")


_THRESHOLD_CHECKS = {
    "GATE_A_TECHNICAL": _check_technical_threshold,
    "GATE_B_EXPLOIT_BREADTH": _check_exploit_breadth,
}


def _check_thresholds(gates: list[dict], schema: dict) -> None:
    for gate in gates:
        gate_id = str(gate.get("gate_id"))
        _check_state_consistency(gate)
        _check_cleared_not_stale(gate)
        _check_gate_extra_fields(gate, schema)
        checker = _THRESHOLD_CHECKS.get(gate_id)
        if checker is not None:
            checker(gate, schema)
        if gate_id == "GATE_C_COMMERCIAL":
            _check_commercial_evidence(gate)
    _ok("اتّساق الحالة مع دليلها + العتبات الكمّية (L9)")


# ── ⑤ الحجب المحدود (L8) ────────────────────────────────────────────────────────


def _gate_state(gates: list[dict], gate_id: str) -> str:
    for gate in gates:
        if str(gate.get("gate_id")) == gate_id:
            return str(gate.get("state"))
    return "ABSENT"


def _check_commercial_block(gates: list[dict]) -> None:
    legal = _gate_state(gates, "GATE_0_LEGAL")
    present = [marker for marker in COMMERCIAL_ARTIFACT_MARKERS if (REPO_ROOT / marker).exists()]
    if legal != "CLEARED" and present:
        _fail(
            f"أثرٌ تجاريّ خارجي {present} و`GATE_0_LEGAL = {legal}` — المحجوب هو الفعل "
            f"التجاري وحده (L8)"
        )
        return
    _ok(
        f"الحجب محدود: `GATE_0_LEGAL = {legal}` · صفر أثرٍ تجاريّ خارجي · "
        f"{len(RESEARCH_PATHS_ALWAYS_ALLOWED)} مسار بحثٍ مسموحٌ صراحةً"
    )


# ── ⑥ الحدود البنيوية (AST) ─────────────────────────────────────────────────────


def _imported_roots(path: Path) -> set[str]:
    """جذور الوحدات المستورَدة.

    ⛔ لا تبتلع خطأ التحليل: `parse_source` ترفع، و`run_gate` تُحوّلها فشلاً صريحاً —
    فملفٌّ لم يُقرأ لا يُشهَد بنظافته (ISS-149·F1).
    """
    tree = parse_source(path)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _check_core_boundary() -> None:
    core = REPO_ROOT / "naas_verifier/core"
    if not core.is_dir():
        _note(
            "قلب المُتحقِّق غير موجود بعد — فحص الحدود بنيويّ ويصير حيّاً فور وجوده "
            "(L1/L2/L4 · الغياب مُعلَن لا مسكوتٌ عنه)"
        )
        return
    for path in sorted(core.rglob("*.py")):
        forbidden = sorted(_imported_roots(path) & set(CORE_FORBIDDEN_IMPORT_ROOTS))
        if forbidden:
            _fail(
                f"{path.relative_to(REPO_ROOT)}: القلب يستورد {forbidden} — القلب مستقلّ "
                f"عن المجال وعن المنصّة (L1/L2/L4)"
            )


def _mentions_product_path(path: Path) -> bool:
    """مرشّحٌ نصّي قبل التحليل — استيرادٌ يستحيل بلا ذِكر الاسم حرفياً.

    ولماذا مرشّحٌ أصلاً: المستودع يستهدف Python 3.12، ومُفسِّرٌ أقدم يعجز عن تحليل
    نحوٍ حديث في ملفّاتٍ لا علاقة لها بهذا القانون — فيصير التقرير ضجيجَ إصدارٍ لا
    انتهاكاً. المرشّح يُبقي الفحص **حقيقياً**: كل ملفٍّ يذكر الاسم يُحلَّل ويُحاسَب،
    وتعذُّر تحليله يُبلَّغ انتهاكاً (D-208 §6).
    """
    try:
        return "naas_verifier" in path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return True


def _check_student_path_boundary() -> None:
    """L5 · D-113: الذخيرة والحلول النموذجية لا تصل مسار الطالب أبداً."""
    app_dir = REPO_ROOT / "app"
    if not app_dir.is_dir():
        _note("مجلّد `app/` غير موجود في هذه الشجرة — فحص جدار الحجب مُعطَّل هنا ويُقال ذلك")
        return
    candidates = [path for path in sorted(app_dir.rglob("*.py")) if _mentions_product_path(path)]
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in candidates
        if "naas_verifier" in _imported_roots(path)
    ]
    if offenders:
        _fail(f"مسار الطالب يستورد طبقة التحقّق {offenders[:5]} — جدار الحجب يمتدّ (L5 · D-113)")
        return
    _ok(f"الحدود البنيوية: صفر استيرادٍ عابر بين المسارين ({len(candidates)} ملفّاً مرشّحاً فُحص فعلاً)")


# ── ⑦ حدّ المصداقية (L10) ───────────────────────────────────────────────────────


def _claim_lines(text: str) -> list[tuple[int, str]]:
    """أسطر الادّعاء وحدها.

    ⛔ **استثناءٌ منطوق (D-208 §7):** سطرٌ يحمل علامة النهي `⛔` مُستثنى — لأنّ القانون
    يجب أن يستطيع **تسمية** ما يحظره، وبوّابةٌ تعاقب النصّ الذي يعرّف المحظور تجعل
    كتابة القانون مستحيلة. والاستثناء يُصرَّح هنا ولا يُصمَت عنه.
    """
    return [
        (number, raw) for number, raw in enumerate(text.splitlines(), start=1) if "⛔" not in raw
    ]


def _check_credibility_limit() -> None:
    mark = len(_FAILURES)
    for rel in DOCS:
        if not rel.endswith(".md"):
            continue
        for number, line in _claim_lines(_read(rel)):
            _check_line_claims(rel, number, line)
    _ok_unless_failed(
        mark, "حدّ المصداقية: صفر عبارةٍ غير قابلة للتفنيد · كل رقم مالٍ موسومٌ فرضيةً (L10)"
    )


def _check_line_claims(rel: str, number: int, line: str) -> None:
    for claim in UNFALSIFIABLE_CLAIMS:
        if claim in line:
            _fail(
                f"{rel}:{number}: عبارةٌ غير قابلة للتفنيد `{claim}` — تُصدَّق مرّة ثمّ "
                f"تُكتشَف فيسقط معها كلُّ ما هو صحيح (D-227)"
            )
    if _MONEY.search(line) and not any(marker in line for marker in _HYPOTHESIS_MARKERS):
        _fail(
            f"{rel}:{number}: رقمُ مالٍ بلا وسم `PRICING HYPOTHESIS` — فرضيةُ سعرٍ ليست "
            f"دليلَ تسعير (L10)"
        )


# ── التشغيل ────────────────────────────────────────────────────────────────────


def _run_document_checks() -> None:
    law = _read(LAW_DOC)
    arch = _read(ARCH_DOC)
    truth = _read(TRUTH_DOC)
    if law:
        _check_law_completeness(law)
        _check_scientific_distinction(law)
    if arch:
        _check_five_dimensions(arch)
    if truth:
        _check_truth_doc(truth)
    _check_law_carries_no_state()


def _run_ledger_checks() -> None:
    schema = _load_json(SCHEMA_DOC)
    ledger = _load_json(LEDGER_DOC)
    if not schema or not ledger:
        return
    gates = _check_ledger_shape(ledger, schema)
    _check_forbidden_state_tokens(schema)
    _check_records(gates, schema)
    _check_thresholds(gates, schema)
    _check_commercial_block(gates)


def main() -> int:
    _run_document_checks()
    _run_ledger_checks()
    _check_core_boundary()
    _check_student_path_boundary()
    _check_credibility_limit()

    if _FAILURES:
        print(f"\n❌ {len(_FAILURES)} انتهاك — دستور D-267 ليس محروساً:")
        for failure in _FAILURES:
            print(f"   - {failure}")
        return 1
    print("\n✅ naas-verification: المُتحقِّق محكوم — الدليل قبل الادّعاء، والحجب لا يوقف البحث.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_gate(main))
