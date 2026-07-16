"""Single source of truth for the probability-tutor brain's source composition (D-168).

Mirror of ``tutor_sources.py`` (D-164) at the brain level: ``probability_tutor_brain.py``
is decomposed into cohesive mixins (verbatim moves), and every gate/test that used to
``read_text(brain)`` now reads the concatenation through this one manifest — so
extracting a new brain mixin is a **one-line append** to ``BRAIN_SOURCE_FILES``.

Stdlib-only (no pydantic / no heavy app imports) so degraded-sandbox gates
(`check_pedagogical_os.py`, `check_skills_doctrine.py`) can consume it textually
or import it — the same design constraint as ``tutor_sources.py``.

Invariant (guarded by check_pedagogical_os): every entry here must also appear in
``TUTOR_SOURCE_FILES`` so the composed monolith-tutor source never loses brain content.
"""

from __future__ import annotations

from pathlib import Path

# probability_brain/ -> skills -> services -> app -> <repo root>
_ROOT = Path(__file__).resolve().parents[4]

# Canonical, fixed order: the composition root first, then the mixins in base order.
BRAIN_SOURCE_FILES: tuple[str, ...] = (
    "app/services/skills/probability_tutor_brain.py",
    "app/services/skills/probability_brain/escape_hatch.py",  # D-168 Slice B1
    "app/services/skills/probability_brain/cognitive_verification.py",  # D-168 Slice B2
    "app/services/skills/probability_brain/cognitive_response.py",  # D-168 Slice B3
    "app/services/skills/probability_brain/socratic_narrative.py",  # D-168 Slice B4
    "app/services/skills/probability_brain/turn_engine.py",  # D-168 Slice B5
)


def read_brain_source() -> str:
    """Return the brain "source" = all `BRAIN_SOURCE_FILES` concatenated.

    Fixed order, ``\\n``-joined — byte-identical to the pre-D-168 brain read while
    the manifest holds a single file, so every existing substring assertion holds
    as mixins are extracted verbatim.
    """
    return "\n".join((_ROOT / rel).read_text(encoding="utf-8") for rel in BRAIN_SOURCE_FILES)
