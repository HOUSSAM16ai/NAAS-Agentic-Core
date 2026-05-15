# Math Types Registry — CogniForge Math Pipeline

> سجل 11 نوع مسألة رياضية مع patterns التصنيف والسياق التعليمي.
> المرجع الكامل لـ `_MATH_TYPES` و `_get_math_context()` في `math_pipeline.py`.

---

## Table of Contents
1. [derivative — الاشتقاق](#derivative)
2. [integral — التكامل](#integral)
3. [limit — النهايات](#limit)
4. [equation — المعادلات](#equation)
5. [function_study — دراسة الدالة](#function-study)
6. [probability — الاحتمالات](#probability)
7. [complex — الأعداد المركبة](#complex)
8. [matrix — المصفوفات](#matrix)
9. [geometry — الهندسة التحليلية](#geometry)
10. [sequence — المتتاليات](#sequence)
11. [differential_eq — المعادلات التفاضلية](#differential-eq)
12. [إضافة نوع جديد](#add-new-type)

---

## 1. derivative — الاشتقاق {#derivative}

**Patterns:**
```python
["مشتق", "اشتقاق", "مشتقة", "f'(", "dérivée", "dériver"]
```

**السياق التعليمي:**
```
مسألة اشتقاق — استخدم قواعد:
- الضرب: (uv)' = u'v + uv'
- السلسلة: (f∘g)' = f'(g)·g'
- القسمة: (u/v)' = (u'v - uv')/v²
- الأسية: (eˣ)' = eˣ، (aˣ)' = aˣ·ln(a)
- اللوغاريتمية: (ln x)' = 1/x
```

**أمثلة بكالوريا:**
- `f(x) = x²·e^(3x)` → قاعدة الضرب + السلسلة
- `f(x) = ln(x²+1)` → قاعدة السلسلة
- `f(x) = (2x+1)/(x-1)` → قاعدة القسمة

---

## 2. integral — التكامل {#integral}

**Patterns:**
```python
["تكامل", "∫", "intégrale", "intégrer", "primitive"]
```

**السياق التعليمي:**
```
مسألة تكامل — تقنيات:
- التكامل المباشر: ∫xⁿdx = xⁿ⁺¹/(n+1)
- التعويض: u = g(x)
- التجزئة: ∫u·dv = uv - ∫v·du
- التكامل بالكسور الجزئية
- التكامل المثلثي: sin²x = (1-cos2x)/2
```

**أمثلة بكالوريا:**
- `∫x·ln(x)dx` → تجزئة
- `∫x²·e^x dx` → تجزئة مرتين
- `∫sin²(x)dx` → صيغة التحويل المثلثي

---

## 3. limit — النهايات {#limit}

**Patterns:**
```python
["نهاية الدالة", "نهاية عند", "lim(", "lim ", "limite", "∞", "لانهاية"]
```

**ملاحظة:** لا تستخدم `"حد"` وحده — يتعارض مع `"محدد المصفوفة"`.

**السياق التعليمي:**
```
مسألة نهايات — تقنيات:
- رفع الإبهام: التحليل إلى عوامل
- قاعدة لوبيتال: lim f/g = lim f'/g' عند 0/0 أو ∞/∞
- المكافئات المقاربية: sin(x)~x، ln(1+x)~x عند x→0
- الضرب بالمرافق
- النهايات الجانبية
```

**أمثلة بكالوريا:**
- `lim(x→0) sin(x)/x = 1` → Squeeze theorem
- `lim(x→∞) (x²+1)/eˣ = 0` → لوبيتال أو مقارنة
- `lim(x→1) (x²-1)/(x-1)` → تحليل

---

## 4. equation — المعادلات {#equation}

**Patterns:**
```python
["معادلة", "حل المعادلة", "equation", "résoudre", "جذر", "حلول"]
```

**السياق التعليمي:**
```
مسألة معادلات — تقنيات:
- المعادلة التربيعية: x = (-b ± √(b²-4ac)) / 2a
- التحليل إلى عوامل
- العزل والتبسيط
- دراسة الإشارة
- المعادلات المثلثية: sin(x) = a → x = arcsin(a) + 2kπ
```

---

## 5. function_study — دراسة الدالة {#function-study}

**Patterns:**
```python
["ادرس", "دراسة الدالة", "tableau de variation", "تغيرات الدالة", "إشارة الدالة"]
```

**ملاحظة:** لا تستخدم `"ادرس"` وحده — يتعارض مع `"ادرس تقاربية المتتالية"`.

**السياق التعليمي:**
```
دراسة دالة — خطوات:
1. المجال (Df)
2. الحدود عند أطراف المجال
3. المشتق f'(x)
4. جدول التغيرات
5. النقاط الخاصة (قيم عظمى/صغرى، نقاط انعطاف)
6. الرسم البياني
```

---

## 6. probability — الاحتمالات {#probability}

**Patterns:**
```python
["احتمال", "probabilité", "عشوائي", "حادثة", "variable aléatoire"]
```

**السياق التعليمي:**
```
مسألة احتمالات — مفاهيم:
- الفضاء الاحتمالي Ω
- الاحتمال الشرطي: P(A|B) = P(A∩B)/P(B)
- الاستقلالية: P(A∩B) = P(A)·P(B)
- قانون الاحتمالات الكلية
- قانون بايز
- المتغير العشوائي والتوقع الرياضي
```

---

## 7. complex — الأعداد المركبة {#complex}

**Patterns:**
```python
["مركب", "complexe", "module", "argument", "conjugué"]
```

**السياق التعليمي:**
```
أعداد مركبة — عمليات:
- الشكل الجبري: z = a + ib
- المعامل: |z| = √(a²+b²)
- الوسيطة: arg(z) = arctan(b/a)
- الشكل المثلثي: z = r(cosθ + i·sinθ)
- الشكل الأسي: z = r·e^(iθ)
- صيغة دي موافر: zⁿ = rⁿ·e^(inθ)
```

---

## 8. matrix — المصفوفات {#matrix}

**Patterns:**
```python
["مصفوفة", "matrice", "déterminant", "عكسية المصفوفة", "محدد المصفوفة"]
```

**ملاحظة:** استخدم `"محدد المصفوفة"` لا `"محدد"` وحده.

**السياق التعليمي:**
```
مصفوفات — عمليات:
- الجمع والضرب
- المحدد: det(A) = ad - bc للمصفوفة 2×2
- المصفوفة العكسية: A⁻¹ = (1/det(A))·adj(A)
- الأنظمة الخطية: AX = B → X = A⁻¹B
- القيم الذاتية: det(A - λI) = 0
```

---

## 9. geometry — الهندسة التحليلية {#geometry}

**Patterns:**
```python
["هندسة", "géométrie", "مستقيم", "مستوى", "متجه", "vecteur"]
```

**السياق التعليمي:**
```
هندسة تحليلية — مفاهيم:
- المتجهات: الجمع، الضرب النقطي، الضرب الاتجاهي
- المستقيمات: المعادلة الديكارتية والمعلمية
- المستويات: المعادلة ax+by+cz+d=0
- المسافات: من نقطة لمستقيم، من نقطة لمستوى
- الزوايا بين مستقيمين أو مستويين
```

---

## 10. sequence — المتتاليات {#sequence}

**Patterns:**
```python
["متتالية", "suite", "تقاربية", "divergente", "حدود المتتالية"]
```

**ملاحظة:** استخدم `"حدود المتتالية"` لا `"حدود"` وحده.

**السياق التعليمي:**
```
متتاليات — أنواع:
- حسابية: uₙ = u₀ + n·r، Sₙ = n(u₀+uₙ)/2
- هندسية: uₙ = u₀·qⁿ، Sₙ = u₀(1-qⁿ)/(1-q)
- التقارب: lim(n→∞) uₙ = L
- الاستقراء الرياضي
- المتتاليات المعرَّفة بالتكرار
```

---

## 11. differential_eq — المعادلات التفاضلية {#differential-eq}

**Patterns:**
```python
["معادلة تفاضلية", "équation différentielle", "y''", "y' +", "y' ="]
```

**ملاحظة:** يجب أن يكون أول نوع في `_MATH_TYPES` لأنه الأكثر تحديداً.

**السياق التعليمي:**
```
معادلات تفاضلية — أنواع:
- الدرجة الأولى: y' + ay = b → y = Ce^(-ax) + b/a
- الدرجة الثانية: y'' + py' + qy = 0
- الحل العام = الحل المتجانس + الحل الخاص
- شروط ابتدائية لتحديد الثوابت
```

---

## 12. إضافة نوع جديد {#add-new-type}

لإضافة نوع مسألة جديد (مثلاً `trigonometry`):

### الخطوة 1: أضف في `_MATH_TYPES` (بترتيب صحيح)

```python
# في math_pipeline.py
_MATH_TYPES: dict[str, list[str]] = {
    "differential_eq": [...],  # أولاً دائماً
    "derivative": [...],
    "trigonometry": [           # ← أضف هنا بترتيب مناسب
        "مثلثات", "جيب", "جتا", "ظل",
        "sin(", "cos(", "tan(",
        "trigonométrie", "sinusoïde",
    ],
    ...
}
```

### الخطوة 2: أضف سياقاً في `_get_math_context`

```python
"trigonometry": (
    "مسألة مثلثات — قوانين: sin²x + cos²x = 1، "
    "صيغ التحويل، المعادلات المثلثية، الدوائر المثلثية"
),
```

### الخطوة 3: أضف header في `verification_node`

```python
type_labels = {
    ...
    "trigonometry": "📐 مسألة مثلثات",
}
```

### الخطوة 4: أضف في `_SUBJECT_PATTERNS["math"]` إذا لزم

```python
_SUBJECT_PATTERNS: dict[str, list[str]] = {
    "math": [
        ...,
        "مثلثات", "sin", "cos", "tan",  # ← أضف
    ],
}
```

### الخطوة 5: أضف اختبارات

```python
# في test_math_pipeline.py
def test_trigonometry(self):
    assert _classify_math_type("احسب sin(30°)") == "trigonometry"

def test_trigonometry_french(self):
    assert _classify_math_type("résoudre sin(x) = 0.5") == "trigonometry"
```

### الخطوة 6: شغِّل الاختبارات

```bash
PYTHONPATH=. python -m pytest \
  tests/microservices/conversation_service/test_math_pipeline.py \
  -v -k "trigonometry or classification"
```

### الخطوة 7: اختبر حياً

```bash
export OPENROUTER_API_KEY="..."
PYTHONPATH=. python3 -c "
import asyncio, sys
sys.path.insert(0, '.')
from microservices.conversation_service.src.math_pipeline import invoke_math_pipeline

async def test():
    r = await invoke_math_pipeline('احسب sin(π/6)', 'test-trig')
    print(f'type={r[\"math_type\"]} | boxed={\"boxed\" in r[\"final_response\"]}')
    print(r['final_response'][:300])

asyncio.run(test())
"
```
