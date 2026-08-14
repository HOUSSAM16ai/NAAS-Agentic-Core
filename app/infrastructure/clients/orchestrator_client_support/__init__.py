"""حزمة شرائح العميل النقية — `orchestrator_client.py` قشرة تفويض فقط (D-256).

نمط D-164/D-173/D-252/D-255: الشرائح نقية بلا حالة ولا استيراد داخلي للـ app،
و`_sources.py` هو المانيفست المركّب الذي تتغذى عليه كل الحراس النصية.
"""

from app.infrastructure.clients.orchestrator_client_support.missions import (
    MissionRequestArgs,
    ServiceJwtPayload,
    _request_mission,
)
from app.infrastructure.clients.orchestrator_client_support.preempts import (
    IndexedMatchDecision,
    resolve_explanation_with_context,
    resolve_indexed_anchor,
)

__all__ = [
    "IndexedMatchDecision",
    "MissionRequestArgs",
    "ServiceJwtPayload",
    "_request_mission",
    "resolve_explanation_with_context",
    "resolve_indexed_anchor",
]
