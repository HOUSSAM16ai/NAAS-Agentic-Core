import re
from typing import Optional, Dict, Any
from fastapi import Request
from dataclasses import dataclass

@dataclass
class OrchestratorTraceContext:
    trace_id: str
    span_id: str
    sampled: bool = True
    flags: str = "01"

    @property
    def traceparent(self) -> str:
        return f"00-{self.trace_id}-{self.span_id}-{self.flags}"

def extract_trace_context(request: Request) -> Optional[OrchestratorTraceContext]:
    traceparent = request.headers.get("traceparent")
    if not traceparent:
        return None

    # Format: 00-traceid(32 hex)-spanid(16 hex)-flags(2 hex)
    match = re.match(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$", traceparent)
    if not match:
        return None

    trace_id, span_id, flags = match.groups()
    sampled = flags.endswith("1")
    return OrchestratorTraceContext(trace_id=trace_id, span_id=span_id, sampled=sampled, flags=flags)
