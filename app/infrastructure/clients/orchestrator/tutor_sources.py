"""Single source of truth for the monolith tutor's source-file composition (D-164).

The monolith deterministic tutor is composed (by inheritance) of the client + the
extracted `ProbabilityTutorBrain` + the cohesive mixins. ~25 source-inspection CI gates
and tests assert substrings across that composed "source". Before D-164 each of them
hardcoded ``read_text(client) + read_text(brain)`` — a DRY violation that turned every
God-file extraction into a ~25-file change. They now read the concatenation through this
one manifest, so extracting a new mixin is a **one-line append** to ``TUTOR_SOURCE_FILES``.

Stdlib-only (no pydantic / no heavy app imports) so the degraded-sandbox gates
(`check_pedagogical_os.py`, `check_skills_doctrine.py`) can import it — the same design
constraint as `db_bridge.py`.
"""

from __future__ import annotations

from pathlib import Path

# orchestrator/ -> clients -> infrastructure -> app -> <repo root>
_ROOT = Path(__file__).resolve().parents[4]

# Canonical, fixed order: client first (transport + `chat_with_agent` orchestration),
# then the extracted deterministic brain (D-163), then cohesive mixins (D-164 — append
# each new extraction below, in the same order it appears in the class bases).
TUTOR_SOURCE_FILES: tuple[str, ...] = (
    "app/infrastructure/clients/orchestrator_client.py",
    "app/services/skills/probability_tutor_brain.py",
)


def read_tutor_source() -> str:
    """Return the monolith tutor "source" = all `TUTOR_SOURCE_FILES` concatenated.

    Fixed order, ``\\n``-joined — byte-identical to the pre-D-164 ``client + "\\n" + brain``
    concatenation so every existing substring / ordering / count assertion still holds.
    """
    return "\n".join((_ROOT / rel).read_text(encoding="utf-8") for rel in TUTOR_SOURCE_FILES)
