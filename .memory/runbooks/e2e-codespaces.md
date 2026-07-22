# 🧪 عُدّة التحقّق الحيّ E2E Full-Stack (Codespaces)

> الغرض: تشغيل **المكدس الكامل الحقيقي ضد Supabase** + OpenRouter والتأكّد من العقود
> الثورية (Socratic No-Answer / D-113 · BKT / D-074 · RAG / D-099 · الواجهات المولّدة ·
> استمرارية البطاقات / D-WS-CARD-PERSIST-001).
>
> **لماذا Codespaces لا الـ sandbox:** الـ sandbox يحجب منافذ Postgres (5432/6543) ويفتقد
> تبعيات التطبيق + `frontend/node_modules`، فلا يستطيع الـ uvicorn الوصول إلى Supabase.
> Codespaces يفتح egress ويثبّت التبعيات. (نمط موثّق: CLAUDE.md §6.55 / §6.83 / §6.98.)
>
> **D-179 (2026-07-22):** «يجيب على كل سؤال» مُتحقَّق منه حيّاً في الـ sandbox عبر مسار الإجابة
> المباشر (المفتاح الحقيقي + `MODEL_CHAIN` القانونية + منطق D-177 rate-limit): 4/4 أسئلة تعليمية
> عربي+LaTeX عبر PRIMARY `openai/gpt-oss-20b:free`. المكدس الكامل full-Postgres + WebSocket
> يُشغَّل هنا في Codespaces: `.devcontainer/supervisor.sh` (8 خدمات + Grafana:3001 + Prometheus:9090)
> ثم `python scripts/verify_full_stack_codespaces.py` (المونوليث:8000 + خدمات 8001-8009 `/health`
> + `/compose` pipeline_mode + دور WS حيّ). المنافذ: 8000 مونوليث · 5000 واجهة · 8001-8009 خدمات.

---

## 0. جاهزية قاعدة البيانات — مؤكَّدة حيّاً (2026-06-14، عبر جسر HTTPS)

تحقّقٌ حيّ حقيقي على Supabase الإنتاجي عبر `scripts/db_bridge.py` (منفذ 443):

| البند | النتيجة |
|------|---------|
| الجداول المطلوبة | **22/22** موجودة (مطابقة `db_schema_config.REQUIRED_SCHEMA`) |
| `customer_messages.ui_component` / `admin_messages.ui_component` | ✅ موجود (102 صفّ بطاقة مُعبّأ) |
| `student_bkt_analytics` (D-074) | ✅ كل الأعمدة + **298 صفّاً** append-only حيّ |
| RAG `bac_exercises` + `bac_exercise_questions` (parsed_entities) | ✅ 3 تمارين (2016 الدوال · 2024 الاحتمالات · 2024 الأعداد المركّبة) |
| الحسابان | ✅ أدمن `benmerahhoussam16` (id=1) · مستخدم `houssamannaba963` (id=7) |

**الخلاصة: قاعدة البيانات مستعدّة 100% لهذه المهمة.**

فحص سريع لإعادة التأكيد (من أي بيئة فيها الجسر):
```bash
set -a && . .devcontainer/secrets.env && set +a   # يوفّر SUPABASE_EDGE_FUNCTION_KEY
python3 scripts/db_bridge.py "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"
python3 scripts/db_bridge.py "SELECT exam_ref, topic, year FROM bac_exercises ORDER BY year;"
```

---

## 1. الأسرار (`.devcontainer/secrets.env` — git-ignored، لا تُلتزَم أبداً)

```bash
cp .devcontainer/secrets.env.example .devcontainer/secrets.env
# ثم املأ القيم الحقيقية:
#   OPENROUTER_API_KEY=sk-or-v1-...
#   TAVILY_API_KEY=tvly-dev-...
#   APP_DATABASE_URL=postgresql://...pooler.supabase.com:6543/postgres?sslmode=require
#   DATABASE_URL=${APP_DATABASE_URL}
#   SUPABASE_EDGE_FUNCTION_KEY=<bearer جسر claude-admin>
#   ENVIRONMENT=development
```

## 2. تشغيل المكدس الكامل
```bash
bash .devcontainer/supervisor.sh
# يُطلق: monolith :8000 + orchestrator :8006 + الخدمات المصغرة + frontend server.js :5000
curl -s localhost:8000/health        # {"application":"ok","database":"ok"}
curl -s localhost:8006/health        # {"status":"ok","graph_ready":true}
```

## 3. تسلسل التحقّق الحيّ (شغّلها بالترتيب)
```bash
set -a && . .devcontainer/secrets.env && set +a
export E2E_BACKEND=http://localhost:8000

# (أ) المكدس الثوري + الخدمات المصغرة (compose pipeline=full)
python3 scripts/verify_revolution_live.py            # متوقّع: 6/6

# (ب) لا اختطاف موضوع (D-101/ISS-110)
python3 scripts/verify_iss110_live.py                # متوقّع: 7/7

# (ج) BKT append-only حيّ (D-074)
python3 scripts/verify_bkt_live.py

# (د) توجيه orchestrator E2E (HTTP + WS + proxy)
python3 scripts/e2e_orchestrator_live.py "ما هو قانون نيوتن الثاني؟"

# (هـ) Socratic No-Answer + BKT + بطاقات (D-113) — الأهمّ لهذه المهمة
DIAG_EMAIL=houssamannaba963@gmail.com DIAG_PASSWORD=1111 \
python3 scripts/verify_d113_socratic_live.py         # متوقّع: كل الفحوص ✅
```

## 4. معايير النجاح (الإغلاق)
- `verify_d113_socratic_live.py`: **صفر** تسريب نتيجة نهائية (`\boxed{<عدد>}` / `P(A)=14/165`)
  في الشرح؛ «لم أفهم» ⇒ تشخيص لا إعادة اشتقاق؛ صفّ BKT جديد مُضاف؛ بطاقة مولّدة تُبثّ.
- `/health` (8000+8006) سليم طوال التشغيل.
- بعد الجولات، تأكيد عبر الجسر:
  ```bash
  python3 scripts/db_bridge.py "SELECT user_id, concept_id, round(student_mastery_probability::numeric,3) p, interaction_count FROM student_bkt_analytics WHERE user_id=7 ORDER BY interaction_timestamp DESC LIMIT 3;"
  python3 scripts/db_bridge.py "SELECT count(*) FROM customer_messages WHERE ui_component IS NOT NULL;"
  ```

## 5. تشخيص الأعطال
- WS لا يتصل / «متصل-غير متصل»: راجع `frontend/server.js` (D-WS-PROXY-004) + `curl -I` على `/api/chat/ws`.
- `pipeline=fallback` بدل `full`: تأكّد أن `OPENROUTER_API_KEY`/`TAVILY_API_KEY` في بيئة العملية قبل `supervisor.sh` (CLAUDE.md §6.25).
- تسريب جواب نهائي: راجع `app/services/skills/answer_redaction_skill.py` + `EXPLANATION_DOCTRINE` (D-113) + `response_sanitizer.redact_final_answers` (orchestrator).
