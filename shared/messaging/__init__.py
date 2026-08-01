"""طبقة الرسائل المشتركة — ظرفٌ قانوني وانضباط تسليم حتمي (D-201)."""

from __future__ import annotations

from .bus import ConsumeOutcome, EventPublisher, InMemoryEventBus, consume_once
from .delivery import (
    DEFAULT_MAX_ATTEMPTS,
    Disposition,
    IdempotencyLedger,
    RetryPolicy,
    decide_disposition,
)
from .envelope import SCHEMA_VERSION, EventEnvelope, MessagingError, new_event_id
from .topics import TOPIC_SPECS, Topic, TopicSpec, UnknownTopicError, spec_for, validate_topic

__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "SCHEMA_VERSION",
    "TOPIC_SPECS",
    "ConsumeOutcome",
    "Disposition",
    "EventEnvelope",
    "EventPublisher",
    "IdempotencyLedger",
    "InMemoryEventBus",
    "MessagingError",
    "RetryPolicy",
    "Topic",
    "TopicSpec",
    "UnknownTopicError",
    "consume_once",
    "decide_disposition",
    "new_event_id",
    "spec_for",
    "validate_topic",
]
