# Control Plane Cutover Plan (Strangler Fig)

## الهدف
جعل `api-gateway` هو مستوى التحكم الوحيد في الإنتاج، مع عزل `core-kernel` خلف ACL واحدة ثم إزالته من التشغيل الأساسي بشكل آمن وقابل للرجوع.

## المبادئ الحاكمة
- لا تغيير لدلالات منطق الأعمال.
- كل cutover يكون قابلًا للرجوع عبر feature flags لكل مسار.
- أي اتصال بـ `core-kernel` يجب أن يمر حصريًا عبر `microservices/api_gateway/legacy_acl`.

## المرحلة 0 — Freeze & Instrument
### التنفيذ
1. إنشاء سجل ملكية المسارات `config/routes_registry.json`.
2. عزل جميع اتصالات legacy داخل `LegacyACL`.
3. إضافة feature flags للمسارات legacy.
4. تمرير `traceparent` من البوابة إلى الخدمات.
5. إضافة Fitness Functions في CI لمنع الارتداد المعماري.

### معايير الخروج
- 100% من حركة legacy تمر عبر ACL واحدة.
- توفر قياس legacy traffic عبر route_id.
- تفعيل gate يمنع أي مسارات CORE_KERNEL جديدة خارج ACL.

### الرجوع (Rollback)
- قلب متغيرات `ROUTE_*_USE_LEGACY=true` فورًا دون نشر كود جديد.

## المرحلة 1 — استخراج chat/content
### التنفيذ
- تفعيل المسارات الجديدة افتراضيًا لـ `/api/chat/*` و`/v1/content/*` مع fallback legacy.
- ترجمة payload quirks داخل ACL فقط.
- اعتماد contract tests consumer/provider.

### معايير الخروج
- >= 80% traffic للـ chat/content عبر الخدمات الجديدة.
- fallback legacy في هبوط مستمر أسبوعيًا.

### الرجوع
- إعادة flags إلى legacy لكل endpoint متأثر.

## المرحلة 2 — Drain لباقي legacy
### التنفيذ
- نقل `system` و`data-mesh` والعائلات المتبقية لخدمات مالكة.
- منع زيادة عدد legacy routes عبر gate monotonic.

### معايير الخروج
- 0 traffic إلى core-kernel لمدة 30 يومًا متواصلة.

### الرجوع
- إعادة تمكين legacy profile مؤقتًا ضمن Runbook الطوارئ.

## المرحلة 3 — إزالة core-kernel من التشغيل الأساسي
### التنفيذ
- compose profiles: افتراضي بلا core-kernel وlegacy/emergency بمدة صلاحية محددة.
- إزالة `CORE_KERNEL_URL` من env الافتراضي.

### معايير الخروج
- جميع الخدمات قابلة للنشر المستقل.
- Runbook طوارئ موقّع ويحتوي مدة زمنية قصوى لإعادة legacy.

## بوابات السلامة (Fitness Functions)
- F1: منع استخدام CORE_KERNEL خارج LegacyACL.
- F2: عدد legacy routes لا يزيد (Monotonic Decrease).
- F3: اتساق المنافذ بين compose وMakefile ووثيقة مصدر الحقيقة.
- F4: اختبار تكامل لتأكيد تمرير `traceparent`.
- F5: تحقق العقود (consumer/provider) كشرط دمج.


## مخرجات المرحلة 3
- تم اعتماد runbook للطوارئ: `docs/architecture/LEGACY_EMERGENCY_RUNBOOK.md`.
- يجب أن يعمل التشغيل الافتراضي بدون `CORE_KERNEL_URL` في compose الأساسي.
