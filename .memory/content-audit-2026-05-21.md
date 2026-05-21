# Content Audit — 2026-05-21
> تحقق حي من حالة تخزين التمارين في المستودع وقاعدة البيانات.

## نتائج الفحص الحي

### content_items (3 سجلات)

| id | type | subject | year | branch | content_len | source |
|----|------|---------|------|--------|-------------|--------|
| `bac-2024-exp-math-s1-ex1` | exercise | mathematics | 2024 | experimental_sciences | 4189 chars | `content/ar/math/bac_2024_exp_sci_subject_1_ex_1.md` |
| `bac_2024_probability` | تمرين مع الحل والشرح | Mathematics | 2024 | Experimental Sciences | 1184 chars | `data/knowledge/bac_2024_probability.md` |
| `probability_exercise` | exercise | general | NULL | *(فارغ)* | 4347 chars | `data/knowledge/probability_exercise.md` |

**ملاحظة**: الثلاثة سجلات تصف نفس التمرين (احتمالات BAC 2024).

### content_solutions (2 سجلات)

| content_id | solution_md | steps_json | final_answer | verified_by_human |
|------------|-------------|------------|--------------|-------------------|
| `bac-2024-exp-math-s1-ex1` | 3314 chars | NULL | NULL | False |
| `bac_2024_probability` | 4730 chars | NULL | NULL | False |

### content_search (1 سجل)

| content_id | plain_text | embedding |
|------------|------------|-----------|
| `bac-2024-exp-math-s1-ex1` | 4288 chars | ✅ موجود |

التمرينان الآخران (`bac_2024_probability`, `probability_exercise`) **بدون embedding** → لا يمكن البحث الدلالي فيهما.

### knowledge_nodes (16 عقدة)

عقد مرتبطة بتمرين الاحتمالات فقط:
- `Topic` → Probability
- `Exercise` → تمرين الاحتمالات بكالوريا 2024
- `Object` → كيس
- `Entity` → كرات بيضاء / حمراء / خضراء
- `Event` → الحادثة A / B / C / D
- ... (16 عقدة إجمالاً)

**مشكلة**: لا يوجد `foreign key` يربط هذه العقد بـ `content_items`. جدول `knowledge_edges` فارغ.

---

## المشاكل المُشخَّصة

### 1. تكرار البيانات
نفس التمرين موجود 3 مرات بـ IDs مختلفة. لا يوجد `UNIQUE constraint` يمنع هذا.

### 2. عدم اتساق metadata
```
subject:  "mathematics" vs "Mathematics" vs "general"
branch:   "experimental_sciences" vs "Experimental Sciences" vs ""
type:     "exercise" vs "تمرين مع الحل والشرح"
year:     2024 vs NULL
```
لا يوجد `ENUM` أو `CHECK constraint` يُوحّد القيم.

### 3. steps_json فارغ
الحل موجود كـ Markdown خام في `solution_md` فقط. `steps_json` = NULL في كل السجلات.
هذا يعني أن النظام لا يستطيع تقديم الحل خطوة بخطوة بشكل مُهيكل.

### 4. embeddings ناقصة
فقط 1 من 3 تمارين لديه embedding في `content_search`.
الـ 2 الباقيان لا يظهران في نتائج البحث الدلالي.

### 5. knowledge_nodes منفصلة
16 عقدة موجودة لكن بدون ربط بـ `content_items` → لا يمكن الاستعلام "أعطني عقد المعرفة لهذا التمرين".

---

## التوصيات

1. **حذف التكرار**: الإبقاء على `bac-2024-exp-math-s1-ex1` فقط (الأكثر اكتمالاً) وحذف السجلين الآخرين.
2. **إضافة constraints**: `CHECK (subject IN ('mathematics','physics','chemistry',...))` + `CHECK (branch IN ('experimental_sciences','mathematics','literary',...))`.
3. **ملء steps_json**: تحويل الحل من Markdown إلى JSON مُهيكل `[{"step": 1, "title": "...", "content": "..."}]`.
4. **توليد embeddings**: تشغيل pipeline لتوليد embeddings لكل التمارين في `content_search`.
5. **ربط knowledge_nodes**: إضافة `content_id` كـ foreign key في `knowledge_nodes`.
6. **إضافة محتوى**: 3 تمارين فقط (كلها احتمالات) — يحتاج المشروع محتوى لمواد أخرى.
