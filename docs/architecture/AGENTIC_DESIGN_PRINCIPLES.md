# مبادئ تصميم الأنظمة الوكيلية (D-272) — وثيقة القانون المعماري

> **الدستور:** [`.memory/agentic_design_principles_constitution.md`](../../.memory/agentic_design_principles_constitution.md) ·
> **الحالة:** [`.memory/agentic_design_principles_truth.md`](../../.memory/agentic_design_principles_truth.md) ·
> **الفارض:** `check_agentic_design_principles.py` ·
> **المصدر العلمي:** [arXiv:2512.08296](https://arxiv.org/abs/2512.08296)

هذه الوثيقة **قانونٌ** لا شرحًا: أي وصفٍ لبنيةٍ وكيليةٍ في هذا المستودع يُثبِت امتثالَه بهذه الحقول.
البوابة `check_agentic_design_principles.py` تقرأ هذه الحقول حرفيًا، وغيابُ حقلٍ إلزاميٍّ ⇒ CI أحمر.

## الحالة الحالية (تُحدَّث بقرارٍ مكتوب + قياسٍ حيّ)

```yaml
governed_by: D-272
multi_agent_status: prohibited_pending_baseline
single_agent_baseline:
  measured: false
  baseline_success_pct: null
  benchmark: null
  measured_at: null
task_taxonomy:
  cogniforge_tutoring:
    decomposable: false
    sequential: true
    tool_count: 16
    permitted_architecture: single_agent
    domain_measured: false
  research_retrieval:
    decomposable: true
    sequential: false
    tool_count: 2
    permitted_architecture: centralized_verifier
    domain_measured: false
    justification_ar: "لا بنيةً متعددةً مسموحةً الآن — قياس الورقة (39–70% تراجعًا على التسلسلي و17.2× تضخيمًا في المستقل) يجعل التعدد فوق عتبةٍ غير مقاسةٍ تحسينًا غير مثبتٍ؛ التوصيف هنا استشرافيٌ لحين أول قياسٍ حيّ"
  research_retrieval:
    decomposable: true
    sequential: false
    tool_count: 2
    permitted_architecture: centralized_verifier
    domain_measured: false
    justification_ar: "نطاقٌ قابل للتقسيم — قياس الورقة المرجعي: +80.8% للتنسيق المركزي على مهامٍ قابلة للتقسيم (Finance-Agent)؛ يُفعَّل فقط بعد قياس خط أساس الوكيل الواحد"
central_verifier:
  max_agents: 4
  tokens_per_task_ratio: null
last_recalibration:
  model_version: current
  baseline_rechecked: null
notes:
  - "لا بنيةً متعددةً فوق المهام التسلسلية — قياس الورقة: 39–70% تراجعًا."
  - "لا مسوداتٍ مشتركةً بين وكلاءٍ مستقلين — قياس الورقة: تضخيم أخطاء 17.2×."
  - "فوق عتبة 45% نجاحًا للوكيل الواحد: التعدد تحسينٌ غير مثبتٍ يحتاج تبريرًا مقاسًا."
```

## القرار المكتوب (ADR مرجعي)

- **2026-08-20:** تبنّي مبادئ arXiv:2512.08296 (Google Research · DeepMind · MIT · 260 تشكيلةً)
  دستورًا ملزمًا (D-272). السبب: التصميم الوكيلي بنيةٌ حرةٌ ظلت تُختار بالذوق؛ الورقة أعطتها
  معيارًا كميًا. ما رُفض ولماذا: «فريقٌ كاملٌ من الوكلاء منذ البداية» — رفض لأن القياس المرجعي
  أظهر متوسط تحسّنٍ لا يتجاوز الصفر وعوائدًا سالبةً عند تشبّع القدرات.
