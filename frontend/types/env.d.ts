/**
 * env.d.ts — تعريف بيئة التشغيل الأدنى (D-185).
 *
 * الفحص (`npm run typecheck`) مكتفٍ بذاته عمداً: لا يعتمد على `@types/node`
 * فلا يتغيّر `package-lock.json` ولا يمكن أن ينحرف `npm ci`. أنواع الـDOM تأتي
 * من `lib: ["dom"]` في tsconfig، ولا يبقى إلا `process.env` الذي تقرؤه الواجهة
 * لمتغيّرات `NEXT_PUBLIC_*`.
 */

declare const process: {
    readonly env: Readonly<Record<string, string | undefined>>;
};
