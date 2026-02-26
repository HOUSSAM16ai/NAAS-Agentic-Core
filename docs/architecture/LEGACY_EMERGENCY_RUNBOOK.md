# Legacy Emergency Re-Enable Runbook (Time-Boxed)

## الهدف
إعادة تمكين `core-kernel` بشكل طارئ ومؤقت فقط عند فشل حرج في الخدمات البديلة.

## القاعدة
- التشغيل الافتراضي يجب أن يكون بدون `core-kernel`.
- أي إعادة تمكين Legacy لها نافذة زمنية قصوى: **24 ساعة**.
- بعد 24 ساعة يجب تنفيذ خطة إغلاق Legacy أو طلب استثناء موثق.

## خطوات التفعيل الطارئ
1. شغّل ملف Legacy:
   ```bash
   docker compose -f docker-compose.legacy.yml up -d
   ```
2. شغّل Gateway مع متغير:
   ```bash
   export CORE_KERNEL_URL=http://core-kernel:8000
   ```
3. فعّل فقط المسارات المتأثرة عبر flags:
   - `ROUTE_*_USE_LEGACY=true`
4. راقب أحجام الطلبات legacy ومعرّفات route_id.

## خطوات الإيقاف والعودة للوضع الطبيعي
1. أعد flags إلى المسارات الجديدة (`false`).
2. احذف متغير `CORE_KERNEL_URL` من بيئة التشغيل.
3. أوقف stack الطوارئ:
   ```bash
   docker compose -f docker-compose.legacy.yml down
   ```
4. وثّق الحادثة وسبب التفعيل ومدته.
