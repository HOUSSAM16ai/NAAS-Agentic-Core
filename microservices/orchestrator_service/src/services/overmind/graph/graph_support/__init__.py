"""graph_support — شرائح الرسم الموحَّد (D-262).

نمط D-164/D-168/D-261: الشرائح نقية بلا حالة والقشرة `main.py` تفوَّض
بالاسم نفسه. الحزمة تصدر أسماء القشرة القديمة كاملة (compat بدون تغيير
سلوكي) + المانيفست المركّب `GRAPH_SOURCE_FILES`.
"""

from microservices.orchestrator_service.src.services.overmind.graph.graph_support._conditions import (
    FAILURE_PHRASES,
    ROUTING_MAP,
    check_quality,
    check_results,
    route_intent,
)
from microservices.orchestrator_service.src.services.overmind.graph.graph_support._graph import (
    build_graph,
    compile_graph,
    compile_with_checkpointer,
)
from microservices.orchestrator_service.src.services.overmind.graph.graph_support._search_shards import (
    _PassthroughNode,
    load_search_nodes,
)
from microservices.orchestrator_service.src.services.overmind.graph.graph_support._sources import (
    GRAPH_SOURCE_FILES,
    read_graph_source,
)

__all__ = (
    "FAILURE_PHRASES",
    "GRAPH_SOURCE_FILES",
    "ROUTING_MAP",
    "_PassthroughNode",
    "build_graph",
    "check_quality",
    "check_results",
    "compile_graph",
    "compile_with_checkpointer",
    "load_search_nodes",
    "read_graph_source",
    "route_intent",
)
