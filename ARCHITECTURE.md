# Architecture: Single Control Plane (Orchestrator Service) — TARGET STATE

> ⚠️ **TARGET STATE — NOT CURRENT RUNTIME.**
> This document describes the *intended* architecture, not what executes today.
> In default Codespaces deployment, the orchestrator-service is **DORMANT**
> (not started by `.devcontainer/docker-compose.host.yml`). The Monolith is the
> de-facto handler — see decisions D-001 / D-006 and the authoritative
> capability table in `.memory/runtime_truth.md` (mirrored as CLAUDE.md §6.6).
> Any contradiction between this file and `.memory/runtime_truth.md` is resolved
> in favor of the truth table. Update this header before promoting any of the
> below from target → live.

## Core Principle
نقطة التحكم الواحدة للتشغيل (Control Plane) هي خدمة **`microservices/orchestrator_service`** عبر بوابة API Gateway فقط.

- Gateway (`microservices/api_gateway`) هو نقطة الدخول العامة الوحيدة.
- `orchestrator-service` هو المالك القانوني لتدفقات chat/missions.
- مسارات المونوليث في `app/api/routers/customer_chat.py` و`app/api/routers/admin.py` تعمل كـ **Compatibility Facades** فقط.

## Operational Rules
1. يمنع تنفيذ منطق الدردشة أو المهام محلياً داخل المونوليث.
2. أي تكامل بين الخدمات يتم عبر HTTP/WebSocket/Event Bus فقط.
3. `X-Correlation-ID` يجب أن ينتقل من Gateway إلى orchestrator-service عبر كل الطلبات.

## Rollback Strategy
- الإرجاع السريع يتم عبر revert commit الخاص بالقطع أو عبر feature flags للـ rollout.
- واجهات التوافق تبقى مفعلة حتى اكتمال parity وtelemetry.
