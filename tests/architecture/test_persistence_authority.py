"""حواجز معمارية لتثبيت ملكية الكتابة وحلقة الإنهاء (D-006 / D-009).

Prevents regression of:
  - ISS-014/015: dual-write to customer_messages / admin_messages
  - ISS-016: silent failure in fallback path (no terminal frame)
  - ISS-017: terminal-event corruption by the unified-envelope normalizer
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_monolith_routers_use_compatibility_facade_handshake() -> None:
    """The handshake that makes Monolith the sole user-message writer must remain."""
    customer = _read("app/api/routers/customer_chat.py")
    admin = _read("app/api/routers/admin.py")

    assert '"compatibility_facade": True' in customer, (
        "customer_chat must signal compatibility_facade=True so Orchestrator skips "
        "user-message INSERT (D-006)."
    )
    assert '"compatibility_facade": True' in admin, (
        "admin must signal compatibility_facade=True so Orchestrator skips "
        "user-message INSERT (D-006)."
    )


def test_monolith_routers_read_persisted_signal() -> None:
    """Monolith must read `persisted: true` to skip duplicate assistant writes."""
    customer = _read("app/api/routers/customer_chat.py")
    admin = _read("app/api/routers/admin.py")

    for source, label in ((customer, "customer_chat"), (admin, "admin")):
        assert 'normalized_event.get("persisted") is True' in source, (
            f"{label} must check the orchestrator's persisted signal (write-guard for ISS-014)."
        )
        assert "orchestrator_persisted = True" in source, (
            f"{label} must mark orchestrator_persisted when the signal arrives."
        )


def test_orchestrator_client_preserves_persisted_flag() -> None:
    """The normalizer in OrchestratorClient must NOT drop the persisted flag."""
    # D-164: `_normalize_stream_event` lives in the StreamNormalizationMixin now; read the
    # full tutor source (client + brain + mixins) via the single manifest.
    from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source

    source = read_tutor_source()
    assert 'result["persisted"] = bool(raw_event["persisted"])' in source, (
        "OrchestratorClient._normalize_stream_event must preserve event['persisted'] "
        "through the envelope; otherwise the Monolith cannot coordinate writes."
    )


def test_terminal_frame_emitter_is_single_source() -> None:
    """Each WS chat router must funnel terminal frames through _emit_terminal_frames."""
    customer = _read("app/api/routers/customer_chat.py")
    admin = _read("app/api/routers/admin.py")

    for source, label in ((customer, "customer_chat"), (admin, "admin")):
        assert "async def _emit_terminal_frames(" in source, (
            f"{label} must define _emit_terminal_frames so terminal-event emission "
            "is centralized (D-009 / ISS-016)."
        )
        assert "await _emit_terminal_frames(" in source, (
            f"{label} must call _emit_terminal_frames from the WS finally block."
        )


def test_event_protocol_normalizer_passes_through_control_events() -> None:
    """Pass-through guard prevents ISS-017 terminal-event corruption."""
    source = _read("shared/chat_protocol/event_protocol.py")
    assert '{"complete", "persisted", "conversation_init"}' in source, (
        "normalize_streaming_event must pass control events through unchanged so "
        "the WS router can detect terminal events (ISS-017)."
    )


def test_critical_data_loss_logging_present_in_both_routers() -> None:
    """Fail-safe write failure must be loud, not silent."""
    customer = _read("app/api/routers/customer_chat.py")
    admin = _read("app/api/routers/admin.py")

    for source, label in ((customer, "customer_chat"), (admin, "admin")):
        assert "[CRITICAL_DATA_LOSS]" in source, (
            f"{label} must log [CRITICAL_DATA_LOSS] when fail-safe persistence "
            "fails after retries (ISS-016)."
        )
        assert "[WRITE_DECISION]" in source, (
            f"{label} must log [WRITE_DECISION] for every persistence decision "
            "(observability of D-006)."
        )
