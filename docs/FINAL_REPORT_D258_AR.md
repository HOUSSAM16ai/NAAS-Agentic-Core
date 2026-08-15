# تقرير نهائي: إصلاح hotspot بنية الاختبارات D-258 / ISS-170

**المستودع:** NAAS-Agentic-Core (Houssam-lab) · **التاريخ:** 15 أغسطس 2026 · **المرجع:** PR #20، الدمج في `main` عند `21663e1`

---

## 1. ملخص تنفيذي

نُفّذت في هذه المهمة معالجة عميقة لأخطر hotspot متبقٍ في المشروع حسب تقرير CodeScene X-Ray: ملف `tests/conftest.py` (416 سطرًا، درجة كود 9/10، مع إشارة «Bumpy Road Ahead» على دالة `db_lifecycle` بـ63 سطرًا و churn يعادل 12 تغييرًا مستقلًا). اعتمد الإصلاح قرارًا معماريًا جديدًا **D-258** استجابة لبلاغ الكارثة **ISS-170**، باتباع النمط الدستوري القائم في المشروع («القشرة + الشرائح + المانيفست المركّب» المتوارث من D-252→D-257) وبالتزام صارم بشرط **صفر تغيير سلوكي** وصفر كسر للاختبارات القائمة.

النتيجة النهائية: حزمة الاختبارات المحلية كاملة مطابقة للخط الأساس (4431/4431)، وبوابتا الدستور `check_memory_coherence` و`check_constitution_reality` خضراوان، والتجريب الحي الكامل E2E على قاعدة بيانات Supabase **الإنتاجية** نجح في كل مراحله الست، ودمج الـPR في `main` مع CI أخضر 100% (27 وظيفة GitHub Actions كلها ✅، بينها `test-monolith` بـ4400+ اختبار خلال 30 دقيقة).

| المحور | النتيجة |
|---|---|
| إصلاح hotspot (D-258/ISS-170) | ✅ قشرة تفويض + حزمة `tests/conftest_support/` (7 شرائح نقية) |
| الحزمة الكاملة للاختبارات | ✅ 4431/4431 مطابقة للخط الأساس على main |
| تحديث التوثيق السيادي | ✅ CLAUDE.md (1025/1025 سطرًا — shrink-only) + .memory + spec + docs |
| E2E حي على Supabase الإنتاجية | ✅ 6/6 أخضر (صحة، مصادقة، محادثة WS ذكية، حفظ فعلي) |
| GitHub Actions على main | ✅ أخضر 100% — 27/27 وظيفة |

---

## 2. التشخيص: كارثة hotspot في `tests/conftest.py`

أظهر تقرير CodeScene X-Ray أن `tests/conftest.py` ملف «hotspot» بدرجة كود 9 (الأسوأ في المشروع)، مع أكثر من 25 رمزًا ساخنًا مترابط التغيير. الأخطر منها:

| الرمز الساخن | churn | LOC | مؤشر CodeScene |
|---|---|---|---|
| `db_lifecycle` | 12 | 63 | **Complex Method + Bumpy Road Ahead** |
| `_ensure_schema` | 8 | 16 | 3 |
| `_should_skip_db_fixtures` | 2 | 12 | 3 |
| `register_and_login_test_user` | 1 | 54 | (كتلة تسجيل ضخمة) |
| `pytest_sessionfinish` / `pytest_pyfunc_call` | 1 | 23/13 | 5/4 |

مشكلة «Bumpy Road Ahead» تعني أن الملف يسلك طريقًا صعبًا: كل تعديل مستقبلي سيزيد تعقيده بدل أن يقلله، وكل تغيير عليه يكلف الفريق أكثر فأكثر. كان الحل المطلوب ليس «ترتيبًا تجميليًا» بل **تفكيكًا معماريًا عميقًا** مع الحفاظ التام على واجهات الاختبارات القائمة (كل fixtures: `client`، `db_session`، `admin_user`، `db_lifecycle`، `user_factory`... كلها 25+ رمزًا).

---

## 3. الحل المعماري (D-258)

### 3.1 النمط الدستوري: القشرة + الشرائح + المانيفست

التزم الإصلاح بالنمط الموثّق في المشروع (D-252→D-255):

| المكوّن | الموقع | الدور |
|---|---|---|
| **القشرة** | `tests/conftest.py` (~130 سطرًا بدل 416) | كل fixtures والـhooks تبقّى بأسمائها القديمة كقشور late-binding تفوّض للشرائح |
| **الشرائح النقية** | `tests/conftest_support/` (7 ملفات) | منطق نقي بلا حالة: `helpers.py`، `registry.py` (عزل حقيقي + قفل متزامن)، `schema.py` (مراحل Bumpy Road المغلقة: dedupe indexes → drop → create → validate)، `lifecycle.py`، `auth_shards.py`، `policy.py` |
| **المانيفست المركّب** | `tests/conftest_support/_sources.py` | تركيب القشرة + الشرائح لحراس النصوص (`check_legacy_invariants` / `check_skills_doctrine`) |
| **القشرة الجذرية** | root `conftest.py` | سطر استيراد واحد `from tests.conftest import *` مع حذف ازدواج تاريخي كان يعيد تعريف hooks |

### 3.2 الاكتشاف المعماري الحاسم (مضاف للقرار D-258)

خلال التفكيك ثُبت تجريبيًا أن **pytest لا يفعّل `autouse` للـfixtures المعرَّفة في وحدات عادية حتى لو استُوردت إلى namespace الـconftest**. هذا كشف معماري ملزم لكل التفكيكات المستقبلية: كل fixture في المشروع يجب أن يبقى تعريفًا في ملف `conftest.py` نفسه، بينما يُستخرج منطقُه النقي إلى الشرائح. أُدرج هذا القانون في §6.7(أ) من CLAUDE.md (القواعد الدائمة).

### 3.3 صفر تغيير سلوكي — الإثبات

| التحقق | النتيجة |
|---|---|
| `ruff 0.14.0` (كل الملفات الجديدة) | ✅ All checks passed + format |
| `check_test_hygiene` | ✅ 505 ملفًا نظيفًا |
| `tests/unit` | ✅ 656/656 (قبل وبعد متطابق) |
| `tests/api + guardian + product` | ✅ 102/103 (الفشل الوحيد `flaky` موجود مسبقًا على main — ثابت عبر `git stash`، مُستبعد أصلًا في CI) |
| الحزمة الكاملة (نفس قائمة CI) | ✅ 4431/4431 |
| `check_memory_coherence` | ✅ |
| `check_constitution_reality` | ✅ |

---

## 4. تحديث التوثيق السيادي

التزم كل تحديث بقوانين الدستور: سقف أسطر CLAUDE.md (1025 سطرًا — shrink-only)، وترتيب newest-first في سجلات الذاكرة، وتحديث الجدول السيادي للفهرس.

| الملف | التعديل |
|---|---|
| `CLAUDE.md` | إضافة بند D-258 في §6.7(أ) (قانون تسجيل fixtures) وسطر D-258 في §6.9، عبر ضغط legend للحفاظ على السقف 1025/1025 بالضبط |
| `.memory/issues.md` | ISS-170 في الرأس: Bumpy Road في `db_lifecycle` (churn=12 · LOC=63) |
| `.memory/decisions.md` | D-258 في الرأس (القشرة + الشرائح + الاكتشاف المعماري) |
| `.memory/README.md` | سطرا الجدول السيادي (D-258 / ISS-170) |
| `spec.md` | إضافة D-258 وD-257 لقائمة hotspots المنجزة |
| `docs/DOCUMENTATION_INDEX.md` + `README.md` + `README.ar.md` | D-257→D-258 حيث تشير الإحالات للحاضر |
| `scripts/fitness/check_constitution_reality.py` | إصلاح SIM910 (ruff) |
| `scripts/e2e_d258_supabase_live.py` | سكربت تجريب حي جديد (صحة + مصادقة + محادثة WS + تحقق حفظ فعلي) |

---

## 5. التجريب الحي الكامل E2E (Supabase الإنتاجية)

عُيِّشت الخدمات الثلاث في بيئة التجريب (monolith :8000 · user_service :8003 · orchestrator :8006) وأجري التجريب على قاعدة بيانات Supabase **الإنتاجية** عبر pooler:

| المرحلة | النتيجة |
|---|---|
| 1. فحص الصحة `/health` | ✅ `database=ok` |
| 2. مصادقة الأدمن (`benmerahhoussam16@gmail.com`) | ✅ 200 — `user_id=1` |
| 3. مصادقة المستخدم (`houssamannaba963@gmail.com`) | ✅ 200 — `user_id=7` |
| 4. REST محمي بتوكن الأدمن (`/api/security/user/me`) | ✅ 200 |
| 5. محادثة حيّة عبر WebSocket (`/api/chat/ws`) | ✅ round-trip كامل بـ`terminal=complete` وإجابة صحيحة للنسبة الذهبية φ≈1.618 (أجابت شبكة graph الكاملة، لا fallback) |
| 6. تحقق الحفظ الفعلي على Supabase (جدول `customer_conversations`) | ✅ 917→918 صف — المحادثة حُفظت فعليًا في قاعدة الإنتاج |

**ملاحظة تشخيصية موثّقة:** واجهنا تباطؤًا سببه **حد معدل OpenRouter المجاني (429)** داخل بيئة التجريب فقط — عولج باتباع دورة الإعادة الطبيعية للحد. هذا قيّد بيئي خارجي وليس عيبًا في بنية المشروع.

---

## 6. GitHub Actions — الصح الخضراء 100%

فُتح **PR #20** (`feat/d258-conftest-hotspot`) على أساس `main`. واجهت عملية الدفع مؤقتًا مشكلة مصادقة مع بوابة git عبر اتصال GitHub connector، فحُلّت عبر GitHub Contents API حتى استقر الاتصال. أكملت كل الفحوصات الخضراء على الفرع قبل الدمج، ثم دُمج الـPR في `main` (squash، `21663e1`).

**نتيجة CI #138 على `main` (success في 30د56ث): كل الوظائف الـ27 خضراء ✅** — ومنها:

| الوظائف الحرجة | المدة | الحالة |
|---|---|---|
| `test-monolith` (4400+ اختبار حقيقي بقاعدة بيانات) | 30د30ث | ✅ |
| `test-microservices` | 6د12ث | ✅ |
| `lint` · `contracts` · `guardrails` | 20ث–3د | ✅ |
| `frontend-tests` · `skills-structural` · `codescene-coverage` · `required-ci` | 4ث–31ث | ✅ |
| مصفوفة بناء 15 صورة (monolith, orchestrator, planning-agent, ...) | حتى 20د | ✅ |
| `Event stack` (إقلاع حقيقي) | 38ث | ✅ |

---

## 7. ملاحظات تشغيلية مستقبلية

عند تشغيل حزمة الاختبارات محليًا داخل حاوية (مثل بيئة sandbox الحالية) يلزم الضبط `ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR=1` لاختباري `test_d112` (هما يفشلان محليًا فقط بسبب وجود `/.dockerenv` ويمران في CI). الاختباران الـflaky المسجلان في قائمة `MONOLITH_DESELECTS` بـ`ci.yml` موجودان مسبقًا على `main` ولم يُعدَّلا (خارج نطاق هذا الإصلاح).

---

## 8. ⚠️ تنبيه أمني عاجل

نُشرت في نص المهمة **مفاتيح حية** بشكل مكشوف: مفتاح OpenRouter، مفتاح Tavily، عنوان اتصال قاعدة بيانات Supabase بكلمة المرور، وكلمات مرور حسابَي الأدمن والمستخدم. هذه المفاتيح الآن في سجلات محادثة قد تكون متاحة لأطراف متعددة. **يجب فورًا:**

1. **تدوير** `OPENROUTER_API_KEY` من [openrouter.ai/keys](https://openrouter.ai/keys)
2. **تدوير** مفتاح Tavily من [tavily.com](https://tavily.com)
3. **تغيير كلمة مرور** مستخدم قاعدة بيانات Supabase من إعدادات المشروع في [supabase.com](https://supabase.com) (مع تحديث `DATABASE_URL` في إعدادات النشر بعد التدوير)
4. **تغيير كلمات المرور** لحسابَي `benmerahhoussam16@gmail.com` و`houssamannaba963@gmail.com`
5. تفضيلًا: **عدم إدخال المفاتيح الحية في نص المهام** مستقبلًا، واستخدام اتصال Manus connector أو ملفات بيئة مشفرة بدلًا منها
