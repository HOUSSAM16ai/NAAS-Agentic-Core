# Architecture Audit — Docker Compose vs Reality (2026-05-21, D-080)

> تشخيص حي للفجوة بين البنية المكتوبة والبنية الفعلية.

## الخلاصة

المشروع **Distributed Monolith** لا Microservices حقيقية.
كل الخدمات تعمل كـ uvicorn processes داخل container واحد عبر supervisor.sh.

---

## ملفات docker-compose (6 ملفات)

### `.devcontainer/docker-compose.host.yml` ✅ يُستخدم فعلاً
- يبني container واحد (`web`) يحتوي كامل الكود
- `command: ["sleep", "infinity"]` — supervisor.sh هو من يُشغِّل uvicorn، لا docker-compose
- `network_mode: host` — يُعيد توجيه كل المنافذ مباشرةً للـ host

### `docker-compose.yml` (478 سطر) ❌ وهمي
يعرّف 9 خدمات + 8 قواعد بيانات Postgres منفصلة + 2 Redis:
```
redis, redis-orchestrator
postgres-planning, postgres-memory, postgres-user,
postgres-research, postgres-reasoning, postgres-observability, postgres-orchestrator
frontend, api-gateway
planning-agent, memory-agent, user-service, observability-service,
orchestrator-service, research-agent, auditor-service, reasoning-agent, conversation-service
```
**لم يُشغَّل قط في Codespaces.** قواعد البيانات المنفصلة غير موجودة — كل الخدمات تستخدم Supabase واحدة.

### `docker-compose.step3.yml` ❌ للتطوير خارج Codespaces
orchestrator-service مع postgres-orchestrator + redis مستقلين.
مفيد نظرياً للتطوير المحلي على جهاز المطوّر.

### `docker-compose.step6.yml` ❌ للتطوير خارج Codespaces
orchestrator + user-service + planning-agent.
نفس الملاحظة — لا يعمل في Codespaces.

### `docker-compose.legacy.yml` ❌ مهجور
يستخدم `profiles: ["legacy", "emergency"]` — لا يُشغَّل بدون `--profile legacy`.

### `observability/docker-compose.observability.yml` ❌ غير مستخدم
Grafana + Prometheus يعملان كـ native binaries مباشرةً عبر supervisor.sh، لا Docker.

---

## الفجوة: ما هو مكتوب vs ما يعمل

| الجانب | docker-compose.yml | الواقع (supervisor.sh) |
|--------|-------------------|----------------------|
| العزل | container مستقل لكل خدمة | process واحد لكل خدمة، نفس الـ container |
| قاعدة البيانات | Postgres منفصلة لكل خدمة | Supabase واحدة مشتركة |
| إعادة التشغيل | `restart: unless-stopped` | `pgrep` + `nohup` — لا restart تلقائي موثوق |
| الشبكة | bridge network معزولة | `localhost` مشترك |
| الـ secrets | env vars في docker-compose | `.devcontainer/secrets.env` |

---

## لماذا حدث هذا؟

**قيود Codespaces**: لا يدعم Docker-in-Docker بشكل مريح في البيئة المجانية.
**قرار عملي**: supervisor.sh كحل بديل سريع — يعمل، لكنه يكسر مبدأ العزل.
**التراكم**: كل خطوة (Step 3→12) أضافت خدمة جديدة لـ supervisor.sh بدلاً من Docker.

---

## التوصيات

### الخيار أ: ابقَ على supervisor.sh (الأكثر واقعية الآن)
- احذف أو أرشف `docker-compose.yml` الوهمي
- وثّق بوضوح أن supervisor.sh هو مسار التشغيل الوحيد
- ركّز على المحتوى التعليمي لا البنية التحتية

### الخيار ب: انتقل لـ Docker حقيقي (مستقبلاً)
- يحتاج ADR موثَّق
- يحتاج بيئة تدعم Docker-in-Docker (Gitpod Pro / VPS)
- كل خدمة تحصل على DB خاصة فعلاً

### القرار المطلوب (ADR)
`docs/architecture/adr/NNN_docker_compose_vs_supervisor.md`

---

## قواعد دائمة (D-080)

1. **supervisor.sh = مسار التشغيل الوحيد في Codespaces** — لا تُشغِّل docker-compose.yml
2. **لا خدمة جديدة بـ docker-compose** بدون ADR + حاجة scaling موثَّقة
3. **docker-compose.yml لا يُعدَّل** — إما يُفعَّل كاملاً أو يُحذف
4. **خدمة جديدة** → uvicorn في supervisor.sh أولاً، Docker لاحقاً عند الحاجة
