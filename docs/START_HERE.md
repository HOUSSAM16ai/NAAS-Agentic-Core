# ابدأ من هنا — CogniForge

> **هذا هو المسار الحي للمطور الجديد.** إذا وجدت تعليمات مختلفة في وثيقة أقدم، اتبع مصدر الحقيقة المحدد في [`DOCUMENTATION_CONTRACT.md`](DOCUMENTATION_CONTRACT.md) ثم افتح Issue أو حدّث المصدر في نفس التغيير.

## 1. ما الذي ستتعامل معه؟

المستودع منصة تعليمية API-first تتكون من نواة FastAPI في `app/`، وخدمات مصغرة في `microservices/`، وواجهة في `frontend/`، واختبارات في `tests/`. التشغيل الكامل ليس هو المسار الأول للمبتدئ؛ ابدأ بفهم النواة ثم شغّل البوابات.

| تريد أن تفهم | ابدأ من |
|---|---|
| الهدف والحدود وما هو مبني فعلاً | [`README.md`](../README.md) |
| قواعد الوكلاء والمساهمين | [`AGENTS.md`](../AGENTS.md) ثم [`CONTRIBUTING.md`](../CONTRIBUTING.md) |
| بنية النواة والخدمات | [`ARCHITECTURE.md`](ARCHITECTURE.md) ثم [`guides/NEWCOMER_CODEBASE_MAP.md`](guides/NEWCOMER_CODEBASE_MAP.md) |
| الحقيقة التشغيلية الحالية | [`.memory/runtime_truth.md`](../.memory/runtime_truth.md) |
| قواعد التوثيق والوكلاء | [`DOCUMENTATION_CONTRACT.md`](DOCUMENTATION_CONTRACT.md) |
| الفهرس الكامل | [`DOCUMENTATION_INDEX.md`](DOCUMENTATION_INDEX.md) |

## 2. المتطلبات

للمسار المحلي تحتاج إلى Python 3.12 أو أحدث، Git، وبيئة افتراضية. تحتاج Docker وقاعدة بيانات PostgreSQL فقط عند تشغيل الخدمات أو التطبيق الذي يعتمد على قاعدة بيانات فعلية. لا تضع أسرارًا في المستودع.

## 3. تثبيت قابل لإعادة الإنتاج

نفّذ الأوامر من جذر المستودع:

```bash
git clone https://github.com/Houssam-lab/NAAS-Agentic-Core.git
cd NAAS-Agentic-Core
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -r requirements-test.txt
```

إذا كان اسم المستودع المستضاف مختلفًا في بيئتك، استخدم عنوان النسخة التي تعمل عليها؛ لا تستبدله باسم مشروع عام أو تاريخي.

## 4. أول تحقق — قبل تشغيل التطبيق

```bash
# فحص التوثيق والحوكمة والبوابات التي تمنع الانحراف
make gates

# الاختبارات مع حد التغطية الحالي الذي يطابق CI
make test
```

`make gates` هو مدخل البوابات الكامل. أما `make guardrails` فيشغّل مجموعة فرعية فقط، ولذلك لا يُستخدم كبديل للتحقق قبل فتح PR. الحد الحالي للتغطية هو **73%**؛ وهو حد مقصود وقابل للرفع تدريجيًا، وليس ادعاءً بأن التغطية 100%.

## 5. تشغيل النواة محليًا

يتطلب التطبيق متغير `DATABASE_URL` أو `APP_DATABASE_URL` في **بيئة العملية قبل إطلاق Uvicorn**. نسخ `.env.example` وحده لا يصدّر القيم إلى العملية. استخدم PostgreSQL صالحًا، وبصيغة `postgresql+asyncpg://` لا `postgresql://`:

```bash
cp .env.example .env
set -a
. ./.env
set +a
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

تحقق من الصحة في نافذة طرفية ثانية:

```bash
curl -s http://localhost:8000/health | python -m json.tool
```

إذا لم تملك قاعدة بيانات أو أسرار بيئة صالحة، لا تتجاوز الفشل بإضافة قيم وهمية إلى الإنتاج؛ نفّذ البوابات والاختبارات المعزولة فقط، ثم اتبع [`CONTRIBUTING.md`](../CONTRIBUTING.md).

## 6. كيف تتتبع ميزة؟

ابدأ من نقطة الدخول في `app/main.py`، ثم تابع تركيب التطبيق في `app/kernel.py`، ثم الراوتر أو الخدمة ذات الصلة، ثم الاختبارات. في الخدمات المصغرة، اقرأ العقد الملتزم به في `docs/contracts/` قبل قراءة التنفيذ. لا تستنتج أن ملفًا موجودًا يعني أن القدرة حية؛ ارجع إلى `.memory/runtime_truth.md`.

```bash
# عرض خريطة مختصرة للمستودع
python app/tooling/repository_map.py --max-depth 2

# العثور على نقاط تركيب التطبيق
rg -n "create_app|RealityKernel|FastAPI\(" app

# استعراض مجموعات الاختبارات
find tests -maxdepth 2 -type d | sort
```

## 7. إذا فشل شيء

احتفظ برسالة الخطأ والأمر والدليل الحالي، ثم تحقق أولًا من البيئة وقاعدة البيانات، وبعدها شغّل البوابة ذات الصلة. لا تعدّل بوابة التحقق لتخفي الفشل، ولا تعتبر نجاح أمر واحد دليلًا على نجاح النظام كله. افتح Issue يتضمن الخطوات القابلة لإعادة الإنتاج، أو أرفقها بوصف Pull Request.

## 8. مسار المساهمة المختصر

اقرأ [`CONTRIBUTING.md`](../CONTRIBUTING.md)، ثم افحص الحالة في `.memory/`, ثم عدّل أقل عدد من الملفات، وحدّث مصدر الحقيقة والفهرس عند الحاجة. قبل الدفع نفّذ:

```bash
git diff --check
make gates
make test
```

لا تُعتبر المهمة مكتملة إلا إذا كانت النتيجة قابلة للمراجعة ومذكورًا فيها ما لم يتم إثباته.
