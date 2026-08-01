# Phase 4 — Zero Legacy Traffic Validation (30 Days)

> ⚠️ **تصحيح D-205 (2026-08-01): المرحلة 4 لم تُقَس بعد.**
> كانت لوحة النتائج أدناه تحمل أصفاراً وكأنّها قياس، ومصدرها ملفٌّ يقول عن نفسه
> `verified_by: "ops-placeholder"`. لم يُقَس شيء قطّ. والقيم الآن `null` لأنّ
> `null` تُقرأ «لم يُعَدّ» بينما `0` تُقرأ «عُدَّ فلم يوجد» — وواحدةٌ فقط منهما
> كانت صادقة (§0: المجهول أفضل من اليقين المزيّف).

## الهدف
تثبيت شرط الإنهاء النهائي: عدم وجود أي حركة legacy (`HTTP` و`WS`) لمدة لا تقل عن 30 يومًا.

## الدليل التشغيلي المطلوب
- ملف دليل القياس: `docs/architecture/LEGACY_TRAFFIC_30D_STATUS.json`
- حقول إلزامية:
  - `status = "measured"` و`verified_by` شخصٌ/نظامٌ حقيقي (D-205)
  - `window_days >= 30`
  - `legacy_request_total_30d = 0`
  - `legacy_ws_sessions_total_30d = 0`
  - `legacy_traffic_ratio_30d = 0.0`

## Enforcement
- `scripts/fitness/check_legacy_traffic_zero_window.py` — يميّز **القياس** من
  **النائب**: النائب يُبلَّغ `NOT MEASURED` ولا يُقبَل كبرهان، والصرامة الكاملة
  بـ`--require-measured` (شرطٌ قبل أيّ إنهاء فعلي).
- ⚠️ البوّابة **غير مربوطة بأيّ workflow** حتى تاريخه؛ مستهلكها الوحيد اختبارٌ في
  `tests/contracts/`. وهذا مذكورٌ هنا لا مُصلَحٌ هنا: ربطُها قبل أن يوجد قياسٌ حقيقي
  يجعلها تُبلّغ عن دَينٍ في كلّ PR بلا فعلٍ ممكن.

## Scoreboard (Phase 4)

**نطاق هذه اللوحة: طوبولوجيا `docker-compose.yml` وحدها** — وهي **وجهة** الهجرة لا
ما يخدم الطلبة. المونوليث اليوم يخدم **كلّ** دور طالب (`.devcontainer/supervisor.sh`
يُقلع `uvicorn app.main:app` على 8000)، وطرح `conversation-service` عند **0%**
و`CONVERSATION_CAPABILITY_LEVEL = "stub"`.

| Metric | Value | نطاق القياس |
|---|---|---|
| legacy_routes_count | 0 | بوّابة `api-gateway` — لا مُعالِج يشير إلى النواة القديمة |
| legacy_ws_sessions_total (30d) | **null (لم يُقَس)** | — |
| legacy_request_total (30d) | **null (لم يُقَس)** | — |
| legacy_traffic_ratio | **null (لم يُقَس)** | — |
| default-profile dependency on the legacy kernel | false | `docker-compose.yml` فقط — وهو ما لا ينشر المونوليث أصلاً |
| contract_gate | true | CI |
| tracing_gate | true | CI |
| ports_consistency | true | CI |

## ما ينقص للانتقال إلى المرحلة 5
1. عدّادات حقيقية من `legacy_acl` (HTTP + WS) مُصدَّرة على نافذة 30 يوماً.
2. طرحٌ فعلي > 0% لبديل المونوليث — فما دام 0%، «صفر حركة legacy» مستحيلٌ لا مُنجَز.
3. `--require-measured` أخضر، ثمّ ربط البوّابة بـCI.
