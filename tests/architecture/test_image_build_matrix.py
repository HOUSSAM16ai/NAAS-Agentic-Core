"""اختبارات مصفوفة بناء الصور وبوّابة تكافؤها — D-205.

الصور نفسها لا تُبنى هنا (لا Docker daemon في هذه البيئة)؛ المُختبَر هو ما **يمكن**
إثباته بلا خفيّ: أنّ المصفوفة تصف الواقع، وأنّ البوّابة تعضّ عند الانحراف.

بوّابةٌ تمرّ دائماً لا تحرس شيئاً — فكلّ فحصٍ هنا مقرونٌ بتجربة سلبية.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts/fitness/check_image_matrix_parity.py"
MATRIX = REPO_ROOT / "config/image_build_matrix.json"


def _load_gate():
    spec = importlib.util.spec_from_file_location("image_matrix_gate", GATE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _entries() -> list[dict]:
    return json.loads(MATRIX.read_text(encoding="utf-8"))["images"]


# ── المصفوفة تصف الواقع ─────────────────────────────────────────────────────────


def test_the_gate_passes_on_the_repository_as_it_stands() -> None:
    assert _load_gate().main() == 0


def test_every_declared_dockerfile_exists() -> None:
    for entry in _entries():
        context, dockerfile = entry["context"], entry["dockerfile"]
        base = REPO_ROOT if context in {".", "./"} else REPO_ROOT / context
        assert (base / dockerfile).is_file(), f"{entry['name']}: {dockerfile} missing"


def test_every_smoke_module_exists_on_disk() -> None:
    """
    مسارُ استيرادٍ مكتوبٌ خطأً لا يظهر إلّا بعد بناء الصورة كاملةً في CI — أي بعد
    دقائق من العمل لسببٍ يمكن كشفه هنا في جزء من الثانية.

    القرار يتبع شكل الصورة: ما يبدأ بـ`microservices.`/`app.` يُحَلّ من جذر
    المستودع، والباقي (`main`) من مجلّد سياق البناء لأنّ صورته مسطّحة.
    """
    for entry in _entries():
        smoke = entry.get("smoke")
        if not smoke:
            continue
        parts = str(smoke).split(".")
        root = (
            REPO_ROOT if parts[0] in {"microservices", "app"} else REPO_ROOT / str(entry["context"])
        )
        module = root.joinpath(*parts).with_suffix(".py")
        assert module.is_file(), f"{entry['name']}: smoke module {smoke} → {module} not found"


def test_the_monolith_is_built_from_the_production_image_not_the_devcontainer_one() -> None:
    """
    العطب الذي وُلِد منه D-205: الـDockerfile الوحيد الذي يُشغّل `app.main:app` كان
    صورةَ بيئة التطوير (Grafana + Prometheus + Node + torch). لا يُبنى المونوليث منها.
    """
    monolith = next(e for e in _entries() if e["name"] == "monolith")
    assert monolith["dockerfile"] == "Dockerfile.prod"
    assert monolith["smoke"] == "app.main"


def test_no_smoke_env_value_looks_like_a_real_secret() -> None:
    """
    قيم الاستيراد دُمى مُعلَنة — مصفوفةٌ ملتزَمة ليست مكاناً لسرّ.

    القاعدة على **اسم المفتاح** لا على طول القيمة: أوّل صياغة اشترطت أن تحمل كل
    قيمة تتجاوز عشرين محرفاً كلمةَ `smoke`، فسقط عليها `SERVICE_NAME=
    observability-service` (٢١ محرفاً) — قاعدةٌ تُنذر على اسم خدمة لا تحرس سرّاً.
    """
    secretish = ("SECRET", "KEY", "TOKEN", "PASSWORD", "CREDENTIAL")
    for entry in _entries():
        for key, value in (entry.get("smoke_env") or {}).items():
            if value and any(marker in key.upper() for marker in secretish):
                assert "smoke" in value.lower(), f"{entry['name']}.{key} is not a declared dummy"


def test_an_entry_without_a_smoke_import_must_say_why() -> None:
    """
    «البناء نجح» ليس دليلاً على أنّ التطبيق يستورد. الإعفاء مسموح — صامتاً لا.
    """
    for entry in _entries():
        if not entry.get("smoke"):
            assert entry.get("smoke_skip_reason"), f"{entry['name']} skips the smoke silently"


# ── البوّابة تعضّ ────────────────────────────────────────────────────────────────


def _write_matrix(tmp_path: Path, images: list[dict]) -> Path:
    path = tmp_path / "image_build_matrix.json"
    path.write_text(json.dumps({"version": 1, "images": images}), encoding="utf-8")
    return path


def test_a_compose_build_context_with_no_matrix_entry_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """الحالة التي وُلِدت لها البوّابة: خدمة جديدة تُبنى في compose ولا تُبنى في CI."""
    gate = _load_gate()
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        "services:\n"
        "  ghost:\n"
        "    build:\n"
        "      context: ./microservices/api_gateway\n"
        "      dockerfile: Dockerfile\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "DEFAULT_COMPOSE", compose)
    monkeypatch.setattr(gate, "MATRIX_FILE", _write_matrix(tmp_path, []))
    monkeypatch.setattr(gate, "MICROSERVICES_ROOT", tmp_path / "empty")

    assert gate.main() == 1


def test_a_dockerfile_on_disk_with_no_matrix_entry_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = _load_gate()
    services = tmp_path / "microservices"
    (services / "ghost_service").mkdir(parents=True)
    (services / "ghost_service" / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(gate, "DEFAULT_COMPOSE", compose)
    monkeypatch.setattr(gate, "MATRIX_FILE", _write_matrix(tmp_path, []))
    monkeypatch.setattr(gate, "MICROSERVICES_ROOT", services)

    assert gate.main() == 1


def test_an_entry_pointing_at_a_missing_dockerfile_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = _load_gate()
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    matrix = _write_matrix(
        tmp_path,
        [{"name": "phantom", "context": ".", "dockerfile": "Dockerfile.nope", "smoke": "app.main"}],
    )
    monkeypatch.setattr(gate, "DEFAULT_COMPOSE", compose)
    monkeypatch.setattr(gate, "MATRIX_FILE", matrix)
    monkeypatch.setattr(gate, "MICROSERVICES_ROOT", tmp_path / "empty")

    assert gate.main() == 1


def test_a_silent_smoke_skip_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gate = _load_gate()
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    matrix = _write_matrix(
        tmp_path,
        [{"name": "quiet", "context": ".", "dockerfile": "Dockerfile.prod", "smoke": None}],
    )
    monkeypatch.setattr(gate, "DEFAULT_COMPOSE", compose)
    monkeypatch.setattr(gate, "MATRIX_FILE", matrix)
    monkeypatch.setattr(gate, "MICROSERVICES_ROOT", tmp_path / "empty")

    assert gate.main() == 1


def test_the_notation_service_root_context_is_not_a_false_positive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    عطبٌ وقع فعلاً أثناء كتابة البوّابة: `notation-service` يبني من جذر المستودع،
    فمقارنةُ الأزواج (سياق، ملفّ) أعلنته «غير مبنيّ» وهو مبنيّ. الإنذار الكاذب
    يُدرِّب الناس على تجاهل البوّابة — فتصير أسوأ من غيابها.
    """
    gate = _load_gate()
    services = tmp_path / "microservices"
    (services / "notation_service").mkdir(parents=True)
    (services / "notation_service" / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")

    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gate, "DEFAULT_COMPOSE", compose)
    monkeypatch.setattr(gate, "MICROSERVICES_ROOT", services)
    monkeypatch.setattr(
        gate,
        "MATRIX_FILE",
        _write_matrix(
            tmp_path,
            [
                {
                    "name": "notation-service",
                    "context": ".",
                    "dockerfile": "microservices/notation_service/Dockerfile",
                    "smoke": "microservices.notation_service.main",
                }
            ],
        ),
    )

    assert gate.main() == 0
