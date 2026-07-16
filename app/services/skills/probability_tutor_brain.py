"""عقل الاحتمالات الحتمي — ProbabilityTutorBrain (D-163 / M13).

الوحدة المستخرَجة من God-file «orchestrator_client.py» (كان 6,154 سطراً — D-160/D-162
أجّلا التفكيك مرتين بسبب نصف قطر الانفجار الاختباري؛ D-163 نفّذه): كل منطق المعلّم
الحتمي للاحتمالات — الكشف (`_detect_*`)، التحقق الرمزي (`_verify_*`)، البُناة
(`_build_*`)، محرّك الدور المعرفي (`_cognitive_turn`)، dedup، والثوابت الصفّية —
**نقل حرفي verbatim** بنفس الأسماء (صفر إعادة صياغة، صفر تغيير سلوكي).

العقد المعماري (لا يُكسر بدون ADR):
- `OrchestratorClient` يرث هذه الفئة (mixin) — كل `cls._x` تُحل عبر الـ MRO كما كانت.
- **ممنوع** الاستيراد من `microservices/` هنا (الحدود المعمارية — HTTP فقط).
- **ممنوع** إعادة أي من هذه الدوال إلى `orchestrator_client.py` (عودة الـ God-file).
- هذه الوحدة هي «عقل المونوليث» في بوّابة تكافؤ split-brain
  (`scripts/fitness/check_pedagogical_os.py:check_split_brain_parity`) مقابل port
  الخدمة المصغرة `microservices/orchestrator_service/src/services/overmind/probability_tutor.py`.
- وحدة محرّك داخلية (سابقة `kc_progress_schema.py`) — ليست Skill مُسجَّلاً في الـ registry؛
  مستهلكها الحي الوحيد `OrchestratorClient` (لا ZOMBIE — import + call chain + runtime).
- الأرقام من المحرك الرمزي حصراً (صفر LLM في مسار الأرقام)؛ الدوال `_generate_*` الوحيدة
  التي تلمس LLM محروسة (redaction + garbage-strip + timeout + fail-open) — D-128.
"""

from __future__ import annotations

import logging

# نفس اسم الـ logger القديم عمداً — استمرارية السجلات وصفر تغيير رصدي (D-163).
logger = logging.getLogger("orchestrator-client")


from app.services.skills.probability_brain.cognitive_response import CognitiveResponseMixin
from app.services.skills.probability_brain.cognitive_verification import (
    CognitiveVerificationMixin,
)
from app.services.skills.probability_brain.escape_hatch import EscapeHatchMixin
from app.services.skills.probability_brain.socratic_narrative import SocraticNarrativeMixin
from app.services.skills.probability_brain.turn_engine import CognitiveTurnEngineMixin


class ProbabilityTutorBrain(
    EscapeHatchMixin,
    CognitiveVerificationMixin,
    CognitiveResponseMixin,
    SocraticNarrativeMixin,
    CognitiveTurnEngineMixin,
):
    """عقل الاحتمالات الحتمي المشترك — يُستهلك حصراً بوراثة `OrchestratorClient`.

    D-168: الفئة صارت جذر تركيب (composition root) — الأعضاء نُقلوا حرفياً إلى
    mixins حزمة `probability_brain/` (المانيفست: `brain_sources.BRAIN_SOURCE_FILES`).
    ترتيب الـ bases = الترتيب المتجاور الأصلي للأسطر — يحفظ مراسي أول-الظهور في
    المصدر المُركَّب. **ممنوع** إعادة أي عضو إلى هذا الملف (عودة الـ God-file).
    """
