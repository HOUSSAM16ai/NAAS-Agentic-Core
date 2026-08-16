"""ExerciseContextSkill — «أيّ تمرين نُدرّس الآن؟» بمصدرٍ واحد (D-191 · ISS-140 د/د-2).

## الكارثة التي يُغلقها هذا الملف

طالب كتب تمرينه بنفسه («كيس يحتوي 12 كرة: 5 حمراء و4 خضراء و3 صفراء») فتلقّى شرحاً
على **كيس آخر** («4 حمراء، 2 بيضاء، 5 خضراء») — أرقام تمرين بكالوريا 2024 المخزَّن
تُزيح معطياته بلا أيّ إشعار. وحين قال «لم أفهم» عن تمرينه، صُفِّر الموضوع إلى ردٍّ عامّ.

**الجذر** (مُتحقَّق في الشجرة): ``_load_canonical_combinations`` كانت تستقبل ``question``
و**ترميه**، فتُمرِّر حرفيّةً مُثبَّتة ``"اعطني تمرين الاحتمالات 2024"`` إلى الاسترجاع ثم
تُغذّي المحرّك الرمزي بنصّ التمرين **الرسمي**. وكانت تلك الحرفية مكرَّرة في **٧** مواضع
عبر ٤ ملفّات تُغذّي ١٢ موضع استدعاء — أي أن «التمرين قيد النقاش» لم يكن له مصدرٌ واحد
أصلاً، بل سبعة مصادر تتّفق صدفةً على الجواب الخطأ.

## القاعدة الدائمة التي يُرسيها

> **التمرين قيد النقاش مصدره واحد، وأوّلُه نصّ الطالب.**
> لا يُطبَع رقمٌ لم يذكره الطالب دون **تصريح** بأنه من تمرين مرجعي.

الترتيب (وهو العقد كلّه):

1. **نصّ الطالب الحالي** — تركيبة inline («كيس فيه 5 حمراء و4 خضراء»).
2. **تمرين الطالب في تاريخ المحادثة** — رسائل ``user`` فقط (D-102: رسالة النظام ليست
   دليلاً)، بالعكس من الأحدث. هذا ما يُغلق «د-2»: عند «لم أفهم» المجرّدة يكون التمرين
   قد ذُكِر قبل دورين، ولم يكن أيّ شيء يبحث عنه.
3. **التمرين المرجعي المخزَّن** — بشرط سياق احتمالي، و**بتصريح منطوق** يرافق الأرقام.
4. لا شيء ⇒ ``None`` (قرار صريح، لا صفر مضلِّل).

## لماذا Skill (§0.5)

كل قدرة تَرِث ``BaseSkill``: هوية موحَّدة، singleton كسول، ومقاييس Prometheus. وهذا
مسار الطالب الحيّ، فكل استدعاء يُقاس (``cogniforge_exercise_context_resolutions_total``
بعلامة ``source`` منخفضة الكاردينالية — لا نصّ سؤال ولا مُعرِّف مستخدم في العلامات).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.services.skills.base import BaseSkill, skill_counter
from app.services.skills.probability_models import (
    CombinationsModelOutput,
    ParsedEntities,
    ProbabilityInput,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CANONICAL_EXERCISE_QUERY",
    "ExerciseContextSkill",
    "ResolvedExercise",
    "resolve_exercise_context",
]

#: الحرفية القانونية لطلب التمرين المرجعي. **هذا موطنها الوحيد** — تكرارها في أيّ
#: ملفٍّ آخر يُفشِل ``scripts/fitness/check_exercise_context_single_source.py``.
CANONICAL_EXERCISE_QUERY = "اعطني تمرين الاحتمالات 2024"

#: التصريح المنطوق حين تأتي الأرقام من تمرين مرجعي لا من الطالب. بلا هذا التصريح
#: يظنّ الطالب أن الأعداد أعدادُه (ISS-140 د).
CANONICAL_DECLARATION = (
    "سأشرح على تمرين بكالوريا 2024 المرجعي (كيس فيه كرات بيضاء وحمراء وخضراء) "
    "لأنك لم تُعطِ أرقام تمرينك."
)

#: أقصى عدد رسائل مستخدم يُفحَص في التاريخ بحثاً عن تمرين الطالب. حدٌّ صريح: مسحٌ
#: مفتوح على تاريخ طويل يُبطئ كل دور، والتمرين قيد النقاش قريبٌ بطبيعته.
_HISTORY_SCAN_LIMIT = 12

_ENTITIES_DIR = Path(__file__).resolve().parents[3] / "knowledge_base" / "entities"


@dataclass(frozen=True)
class ResolvedExercise:
    """التمرين قيد النقاش: كياناته المهيكلة، تركيبته المحسوبة، ومن أين جاء."""

    entities: ParsedEntities
    combo: CombinationsModelOutput
    source: Literal["student", "canonical"]
    #: النصّ الذي أُخِذت منه التركيبة — يُعاد استعماله لبناء نموذج العرض مع نيّة
    #: الطالب (حيرة ⇒ قصّة شاملة) بلا إعادة حسم مصدر التمرين.
    composition_text: str = ""

    @property
    def declaration(self) -> str:
        """التصريح الواجب نطقه قبل طباعة أرقام لم يذكرها الطالب."""
        return CANONICAL_DECLARATION if self.source == "canonical" else ""

    @property
    def is_student_owned(self) -> bool:
        return self.source == "student"


class ExerciseContextSkill(BaseSkill[str, "ResolvedExercise | None"]):
    """يحسم **أيّ** تمرين يُدرَّس في هذا الدور — المصدر الواحد (D-191)."""

    name = "exercise_context"
    version = "1.0.0"

    _metric = skill_counter(
        "cogniforge_exercise_context_resolutions_total",
        "قرارات حسم التمرين قيد النقاش، مصنَّفة بالمصدر",
        ("source",),
    )

    # ── الواجهة العامّة ──────────────────────────────────────────────────────
    def resolve(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None = None,
        *,
        allow_canonical: bool = True,
        probability_context_established: bool = False,
    ) -> ResolvedExercise | None:
        """يُعيد التمرين قيد النقاش، أو ``None`` إن تعذّر حسمه.

        ``allow_canonical=False`` يمنع السقوط إلى التمرين المرجعي كلياً — يستعمله
        كل مسار يجب ألّا يرى أرقاماً ليست للطالب تحت أيّ ظرف.

        ``probability_context_established=True`` **تصريحٌ من المستدعي** بأن السياق
        الاحتمالي مُثبَت سلفاً بدليلٍ أقوى من نصّ السؤال (كاشف جزئية data-driven
        أطلق ``forced_subpart``، أو حدثٌ مُصنَّف بالفعل). يُستعمل حصراً حيث يكون
        الدليل خارج النصّ — لا للتحايل على حارس الموضوع: «اشرح لي قانون أوم» لا
        يملك مثل هذا الدليل ولن يملكه (ISS-140 أ · D-190).
        """
        resolved = self._resolve_student(question, history_messages)
        if resolved is None and allow_canonical:
            resolved = self._resolve_canonical(
                question, history_messages, assume_context=probability_context_established
            )
        self._metric.labels(source=resolved.source if resolved else "none").inc()
        return resolved

    def run(self, *args: object, **kwargs: object) -> ResolvedExercise | None:
        """نقطة الدخول الموحَّدة لـ``BaseSkill`` — تُفوِّض إلى ``resolve``."""
        return self.resolve(*args, **kwargs)  # type: ignore[arg-type]

    # ── (1) + (2) نصّ الطالب: الدور الحاضر ثمّ تاريخه ────────────────────────
    def _resolve_student(
        self, question: str, history_messages: list[dict[str, str]] | None
    ) -> ResolvedExercise | None:
        candidate = self._build(question, source="student")
        if candidate is not None:
            return candidate
        for text in self._student_history_texts(history_messages):
            # التركيبة من نصّ التمرين الذي كتبه الطالب سابقاً، و**النيّة** من سؤاله
            # الحاضر («لم أفهم» ⇒ حيرة ⇒ قصّة بصرية شاملة). فصلُهما هو ما يجعل
            # «لم أفهم» تبقى على تمرين الطالب بدل تصفير الموضوع (ISS-140 د-2).
            candidate = self._build(text, source="student")
            if candidate is not None:
                return candidate
        return None

    @staticmethod
    def _student_history_texts(
        history_messages: list[dict[str, str]] | None,
    ) -> list[str]:
        """نصوص الطالب من الأحدث إلى الأقدم — رسائل ``user`` **فقط** (D-102).

        رسالة النظام (برومبت النظام) ورسائل المساعد ليست دليلاً من المحادثة أبداً؛
        قراءتها كانت جذر تسمّم التوجيه في ISS-110/D-102.
        """
        if not history_messages:
            return []
        texts: list[str] = []
        for message in reversed(history_messages):
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            content = str(message.get("content", "")).strip()
            if content:
                texts.append(content)
            if len(texts) >= _HISTORY_SCAN_LIMIT:
                break
        return texts

    # ── (3) التمرين المرجعي المخزَّن — بكيانات مهيكلة لا بنثر ────────────────
    def _resolve_canonical(
        self,
        question: str,
        history_messages: list[dict[str, str]] | None,
        *,
        assume_context: bool = False,
    ) -> ResolvedExercise | None:
        if not assume_context and not self._is_probability_topic(question, history_messages):
            return None
        entry = self._canonical_entry(history_messages)
        if entry is None:
            return None
        entities = self._canonical_entities(entry)
        if entities is not None:
            built = self._build_from_entities(entities, source="canonical")
            if built is not None:
                return built
        # تدهور رشيق: بلا ملفّ كيانات مهيكلة، نقرأ **أسئلة-فقط** (حارس ISS-120)
        # ولا نلمس نثر الحلّ النموذجي إطلاقاً.
        official = self._canonical_questions_only(entry)
        if not official:
            return None
        return self._build(official, source="canonical")

    @staticmethod
    def _is_probability_topic(
        question: str, history_messages: list[dict[str, str]] | None = None
    ) -> bool:
        """هل يجوز السقوط إلى التمرين المرجعي؟ — **إشارة موجبة إلزامية** (D-190/D-191).

        حارسان، والترتيب مقصود:

        1. **موضوع آخر صريح** (دوال/أعداد مركبة/…) ⇒ رفض فوري.
        2. **سياق احتمالي موجب** في السؤال أو حوار الطالب ⇒ شرط لازم.

        الحارس الثاني هو الدرس المدفوع ثمنه في ISS-140 أ: «غياب موضوعٍ آخر» ليس
        إشارةً على الاحتمالات. «اشرح لي قانون أوم» لا يُصنَّف موضوعاً معروفاً، فلو
        اكتفينا بالحارس الأول لعاد سؤال الفيزياء يتلقّى كيس كرات — وهي الكارثة
        نفسها بمفتاحٍ جديد.
        """
        with_history = question
        if history_messages:
            # D-102: حوار الطالب/المساعد فقط — رسالة النظام ليست دليلاً.
            with_history = " ".join(
                [question]
                + [
                    str(message.get("content", ""))
                    for message in history_messages
                    if isinstance(message, dict) and message.get("role") in ("user", "assistant")
                ]
            )
        try:
            from app.services.capabilities.topic_authority import is_foreign_to_probability
            from app.services.skills.probability_brain.cognitive_verification import (
                CognitiveVerificationMixin,
            )
        except Exception:  # pragma: no cover — استيراد كسول واقٍ
            return False
        # D-266 (ISS-159): الحاسم الواحد — سؤال فيزياء/علوم كان يمرّ لأنّ سجلّ
        # الاسترجاع يصمت عنه، فيسقط الشرط القديم عند ساقه الأولى.
        if is_foreign_to_probability(question):
            return False
        # نفس المُسنِد المستعمل في العقل — لا نسخة ثالثة من علامات السياق.
        return bool(CognitiveVerificationMixin._is_prob_context(with_history))

    @staticmethod
    def _canonical_entry(history_messages: list[dict[str, str]] | None) -> object | None:
        try:
            from app.services.capabilities.exercise_retrieval import (
                ExerciseRetrievalRequest,
                detect_exercise_retrieval,
            )
        except Exception:  # pragma: no cover
            logger.warning("exercise_context_retrieval_import_failed", exc_info=True)
            return None
        decision = detect_exercise_retrieval(
            ExerciseRetrievalRequest(question=CANONICAL_EXERCISE_QUERY),
            history_messages=history_messages,
        )
        if not (decision.recognized and decision.matched_entry):
            return None
        return decision.matched_entry

    @staticmethod
    def _canonical_entities(entry: object) -> ParsedEntities | None:
        """يقرأ الكيانات المهيكلة المُلتزَمة للتمرين المرجعي (D-191).

        هذا هو القارئ الذي جعل «الكيانات المهيكلة لا النثر» صحيحاً: نفس الدالّة
        تقرأ ملفّ ``knowledge_base/entities/*.json`` وشكلَ عمود ``parsed_entities``
        (JSONB) — مصدرٌ واحد للتفسير.
        """
        file_path = str(getattr(entry, "file_path", "") or "")
        if not file_path:
            return None
        stem = Path(file_path).stem
        candidate = _ENTITIES_DIR / f"{stem}.entities.json"
        if not candidate.is_file():
            return None
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("exercise_context_entities_unreadable", exc_info=True)
            return None
        return ParsedEntities.from_mapping(payload)

    @staticmethod
    def _canonical_questions_only(entry: object) -> str:
        try:
            from app.services.capabilities.exercise_retrieval import load_exercise_questions_only

            return str(load_exercise_questions_only(entry) or "")
        except Exception:  # pragma: no cover
            logger.warning("exercise_context_questions_only_failed", exc_info=True)
            return ""

    # ── البناء: كيانات ⇒ تركيبة محسوبة ──────────────────────────────────────
    @classmethod
    def _build(
        cls,
        text: str,
        *,
        source: Literal["student", "canonical"],
    ) -> ResolvedExercise | None:
        """يستخرج الكيانات من نصٍّ حرّ ثمّ يبني التركيبة منها."""
        from app.services.skills.probability_skill import ProbabilityCalculatorSkill

        entities = ProbabilityCalculatorSkill.extract_parsed_entities(text)
        if entities is None:
            return None
        return cls._build_from_entities(entities, source=source, composition_text=text)

    @staticmethod
    def _build_from_entities(
        entities: ParsedEntities,
        *,
        source: Literal["student", "canonical"],
        composition_text: str = "",
    ) -> ResolvedExercise | None:
        """يُحوّل الكيانات المهيكلة إلى ``CombinationsModelOutput`` عبر المحرّك الرمزي.

        **التركيبة** من الكيانات (أو نصّها الأصلي)، و**النيّة** من سؤال الطالب
        الحاضر. الفصل مقصود: الأرقام لا تتغيّر بتغيّر الصياغة، لكن عمق العرض
        (قصّة شاملة عند الحيرة مقابل مُصوِّر تأليفات عند سؤالٍ مباشر) يقرّره سؤال
        الطالب. الأرقام كلّها من المحرّك الحتمي — لا LLM في هذا المسار (§6.7.د).
        """
        from app.services.skills.probability_skill import ProbabilityCalculatorSkill

        skill = ProbabilityCalculatorSkill()
        for candidate_text in (composition_text, entities.as_text()):
            if not candidate_text.strip():
                continue
            try:
                result = skill.analyze(ProbabilityInput(question=candidate_text, history=None))
            except Exception:
                logger.warning("exercise_context_analyze_failed", exc_info=True)
                continue
            if isinstance(result, CombinationsModelOutput):
                return ResolvedExercise(
                    entities=entities,
                    combo=result,
                    source=source,
                    composition_text=candidate_text,
                )
        return None


def resolve_exercise_context(
    question: str,
    history_messages: list[dict[str, str]] | None = None,
    *,
    allow_canonical: bool = True,
    probability_context_established: bool = False,
) -> ResolvedExercise | None:
    """اختصار على مستوى الوحدة — نقطة الاستهلاك الموحَّدة لكل المستدعين."""
    return ExerciseContextSkill.instance().resolve(
        question,
        history_messages,
        allow_canonical=allow_canonical,
        probability_context_established=probability_context_established,
    )
