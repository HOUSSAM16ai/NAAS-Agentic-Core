# SOLID Audit (Gate 2)

## Architecture Map (Layers & Dependency Direction)

**Presentation / Interface**
- `app/api/routers/*` (FastAPI/HTTP interface)
- `app/api/schemas/*` (request/response DTOs)

**Application / Use Cases**
- `app/application/*`
- `app/services/*` (use case orchestration, application services)

**Domain / Core**
- `app/core/*` (shared domain patterns, protocols, domain events)
- `app/domain/*` (domain models)

**Infrastructure / Adapters**
- `app/infrastructure/*`
- `app/services/*/infrastructure/*`
- `app/core/database.py`

**Dependency Direction**
- Presentation → Application → Domain
- Infrastructure → Domain (implements ports)
- Composition root: `app/kernel.py` and `app/core` apply configuration and DI

## SOLID Violations (Before)

### SRP (Single Responsibility Principle)
- `app/services/overmind/knowledge.py` mixes DB I/O, schema composition, logging, and environment/structure collection. ✅ **Partially resolved**: schema assembly + logging split into `app/services/overmind/knowledge_schema.py`, environment/structure helpers split into `app/services/overmind/knowledge_environment.py` and `app/services/overmind/knowledge_structure.py`, timestamp helper split into `app/services/overmind/knowledge_timestamp.py`, query helpers split into `app/services/overmind/knowledge_queries.py` (tables/count + columns/keys), mapping helper split into `app/services/overmind/knowledge_mapping.py`.
- `app/services/system/resilience/service.py` combines policy selection, execution, and error handling.
- `app/services/overmind/code_intelligence/core.py` mixes orchestration, analysis, and report shaping.
- `app/services/project_context/application/context_analyzer.py` mixes IO scanning with analysis rendering.
- `app/services/admin/chat_streamer.py` combines persistence, streaming, and guardrails.
- `app/services/system/distributed_tracing.py` merges span storage, aggregation, and reporting.

### OCP (Open/Closed Principle)
- `app/services/system/resilience/retry.py` uses branching by policy type rather than strategy objects.
- `app/services/overmind/tool_canonicalizer.py` hard-coded intent matching rules.
- `app/application/use_cases/routing/routing_strategies.py` uses conditional selection without extension registry.
- `app/services/serving/application/model_invoker.py` mixes model selection and response shaping logic.

### LSP (Liskov Substitution Principle)
- `app/services/chat/handlers/strategy_handlers.py` defines async generators that do not conform to `Strategy` return type.
- `app/core/patterns/strategy_pattern/base.py` protocol expectations mismatched with implementers.
- `app/services/agent_tools/tool_model.py` allows handler callability mismatch (None vs callable).

### ISP (Interface Segregation Principle)
- `app/services/boundaries/admin_chat_boundary_service.py` exposes persistence + streaming methods in one surface.
- `app/core/protocols.py` contains broad protocols used by narrow consumers.
- `app/services/agent_tools/refactored/registry.py` exposes wide registry API with minimal consumers.

### DIP (Dependency Inversion Principle)
- `app/services/overmind/knowledge.py` directly instantiates DB sessions and reads env.
- `app/services/overmind/code_intelligence/core.py` depends on concrete reporters.
- `app/services/admin/chat_streamer.py` depends on concrete persistence and AI client.
- `app/services/system/distributed_tracing.py` depends on concrete data stores.
- `app/services/data_mesh/application/mesh_manager.py` constructs concrete governance policies inline.

## File-Path Violation Inventory (Detailed)

### SRP
- `app/services/overmind/knowledge.py`
- `app/services/overmind/code_intelligence/core.py`
- `app/services/project_context/application/context_analyzer.py`
- `app/services/system/resilience/service.py`
- `app/services/system/distributed_tracing.py`
- `app/services/admin/chat_streamer.py`

### OCP
- `app/services/system/resilience/retry.py`
- `app/services/overmind/tool_canonicalizer.py`
- `app/application/use_cases/routing/routing_strategies.py`
- `app/services/serving/application/model_invoker.py`

### LSP
- `app/core/patterns/strategy_pattern/base.py`
- `app/services/chat/handlers/strategy_handlers.py`
- `app/services/agent_tools/tool_model.py`

### ISP
- `app/core/protocols.py`
- `app/services/boundaries/admin_chat_boundary_service.py`
- `app/services/agent_tools/refactored/registry.py`

### DIP
- `app/services/overmind/knowledge.py`
- `app/services/overmind/code_intelligence/core.py`
- `app/services/admin/chat_streamer.py`
- `app/services/system/distributed_tracing.py`
- `app/services/data_mesh/application/mesh_manager.py`

## Prioritized Refactor Plan (10–20 Slices)

1. **SRP Split: Database knowledge**
   - Scope: `app/services/overmind/knowledge.py`
   - Risk: High (DB + schema composition)
   - Tests: `tests/overmind/*`, add characterization.

2. **SRP Split: Project context analyzer**
   - Scope: `app/services/project_context/application/context_analyzer.py`
   - Risk: Medium
   - Tests: `tests/project_context/*` (add)

3. **DIP: Overmind knowledge ports**
   - Scope: `app/services/overmind/knowledge.py`, `app/core/protocols.py`
   - Risk: High
   - Tests: add port-level tests.

4. **OCP: Tool canonicalizer strategies**
   - Scope: `app/services/overmind/tool_canonicalizer.py`
   - Risk: Medium
   - Tests: `tests/overmind/test_tool_canonicalizer.py` (add)

5. **SRP + DIP: Resilience service**
   - Scope: `app/services/system/resilience/service.py`
   - Risk: High
   - Tests: `tests/system/resilience/*`

6. **OCP: Retry policies**
   - Scope: `app/services/system/resilience/retry.py`
   - Risk: Medium
   - Tests: `tests/system/resilience/test_retry.py`

7. **LSP: Strategy protocol alignment**
   - Scope: `app/core/patterns/strategy_pattern/base.py`, `app/services/chat/handlers/strategy_handlers.py`
   - Risk: High
   - Tests: `tests/chat/test_strategy_handlers.py`

8. **ISP: Admin chat boundary split**
   - Scope: `app/services/boundaries/admin_chat_boundary_service.py`, `app/services/admin/*`
   - Risk: Medium
   - Tests: `tests/admin/test_chat_boundary.py`

9. **DIP: Code intelligence reporters**
   - Scope: `app/services/overmind/code_intelligence/*`
   - Risk: High
   - Tests: `tests/overmind/test_code_intel_reporters.py`

10. **SRP: Overmind code intelligence core**
    - Scope: `app/services/overmind/code_intelligence/core.py`
    - Risk: High
    - Tests: `tests/overmind/test_code_intelligence.py`

11. **ISP: Protocol slicing**
    - Scope: `app/core/protocols.py`
    - Risk: Medium
    - Tests: dependent use-case tests.

12. **DIP: Environment info provider**
    - Scope: `app/services/overmind/knowledge.py`, new adapter
    - Risk: Medium
    - Tests: add env provider tests.

13. **OCP: Routing strategy registration**
    - Scope: `app/application/use_cases/routing/routing_strategies.py`
    - Risk: Medium
    - Tests: `tests/routing/test_strategies.py`

14. **LSP: Base strategy return types**
    - Scope: `app/core/patterns/strategy_pattern/*`
    - Risk: Medium
    - Tests: add substitutability tests.

15. **Cleanup: Dependency direction enforcement**
    - Scope: `app/kernel.py`, `app/core` imports
    - Risk: Low
    - Tests: smoke tests.

16. **Cleanup: Remove dead code**
    - Scope: `app/services/*` (unused paths found by lint)
    - Risk: Medium
    - Tests: module-specific tests.

17. **Documentation updates**
    - Scope: `docs/solid_*`
    - Risk: Low
    - Tests: none.

18. **Consistency pass**
    - Scope: formatting + imports in touched files
    - Risk: Low
    - Tests: lint.
