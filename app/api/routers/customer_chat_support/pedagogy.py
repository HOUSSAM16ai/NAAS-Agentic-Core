"""Pedagogy + BKT + sanitization helpers — sliced verbatim from customer_chat.py (D-173 Stage 2b).

قواعد D-168: هذه الوحدة لا تستورد `customer_chat` أبداً؛ الـ router يعيد
استيراد الرموز (re-export) فيبقى monkeypatch على `customer_chat.<name>`
فعّالاً لكل نداء يصدر من الـ handler (قانون late-binding).
"""

"""
واجهة برمجة تطبيقات محادثة العملاء القياسيين.

توفر نقاط النهاية الخاصة بالمستخدمين القياسيين للوصول إلى محادثة تعليمية
مع فرض سياسات الأمان والملكية.

## V46.0 — جدار الحماية المزدوج للقنوات

يُطبَّق OutputFirewall على complete_ai_response المُجمَّع قبل الحفظ في DB.
هذا يضمن أن أي HTML/JSX تسرَّب من LLM يُنظَّف قبل الوصول للطالب أو قاعدة البيانات.

D-086 (2026-05-23): تطبيق Protocol V46.0.
"""

import asyncio
import contextlib
from typing import NamedTuple

from app.core.database import async_session_factory
from app.core.di import get_logger
from app.core.domain.chat import MessageRole
from app.services.analytics.bkt_persistence import BKTAnalyticsService
from app.services.boundaries.customer_chat_boundary_service import (
    CustomerChatBoundaryService,
)
from shared.intent import markers_for

logger = get_logger(__name__)


def _semantic_tutor_enabled() -> bool:
    """D-142/D-158: علم تحميل+كتابة `tutor_state` — قارئ موحَّد (افتراض True).

    D-158: يُفوَّض إلى `app.core.feature_flags` (مصدر واحد لكل الأعلام، افتراض واحد) بدل
    التعريف المزدوج المتعارض الذي كان يُعطِّل سلطة الحوار في المُنسّق.
    """
    from app.core.feature_flags import semantic_tutor_enabled

    return semantic_tutor_enabled()


def _apply_complete_response_firewall(text: str) -> str:
    """D-086 (V46.0): يُطبِّق OutputFirewall على الإجابة المكتملة قبل الحفظ.

    يُنظِّف HTML/JSX من complete_ai_response بعد اكتمال البث.
    Fail-open: أي فشل يُعيد النص الأصلي دون كسر المسار.
    """
    if not text or not text.strip():
        return text
    try:
        from app.services.skills.output_firewall import apply_channel_b_firewall

        cleaned, was_rejected = apply_channel_b_firewall(text, intent="educational")
        if was_rejected:
            logger.warning("customer_chat.complete_response_firewall_rejected chars=%d", len(text))
            return text  # fail-open
        return cleaned
    except Exception as exc:
        logger.debug("customer_chat.firewall_non_fatal: %s", exc)
        return text


def _strip_display_garbage(text: str) -> str:
    """D-115: مُطهّر العرض الحيّ المُصفّح — يحذف فواصل ⟦⟧ المشوّهة + تعليمات
    system prompt المُسرَّبة + أي رموز غريبة قبل عرضها للطالب. شبكة أمان فوق
    تنظيف الـ orchestrator. fail-open (لا يكسر البثّ).
    """
    if not text:
        return text
    try:
        from app.services.skills.content_integrity_skill import _strip_garbage_markers

        return _strip_garbage_markers(text)
    except Exception:
        return text


def _apply_final_answer_redaction(text: str, support_level: int | None) -> str:
    """D-114: حجب الإجابة النهائية الواعي بالفواصل على الإجابة المحفوظة.

    support_level==1 ⇒ يُعفي كتلة المثال المحلول (الملفوفة بالفواصل) ويحجب ما
    عداها؛ غير ذلك ⇒ حجب كامل (شبكة أمان D-113 + إزالة أي علامات شاردة). fail-open.
    """
    if not text or not text.strip():
        return text
    try:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        redacted, _ = redact_final_answers(text, support_level)
        return redacted
    except Exception as exc:
        logger.debug("customer_chat.final_redaction_non_fatal: %s", exc)
        return text


def _card_component_name(card: object) -> str | None:
    """اسم المكوّن إن كانت البطاقة بالشكل السلكي، وإلّا ``None``."""
    if not isinstance(card, dict):
        return None
    name = card.get("component")
    return name if isinstance(name, str) and name else None


def _renderable_cards(
    cards: list[dict[str, object]], *, conversation_id: int
) -> list[dict[str, object]]:
    """البطاقات التي **تعرف الواجهة رسمها** وحدها (ISS-145).

    ما لا يجتاز ``KNOWN_UI_COMPONENTS`` يُسجَّل كي يُشخَّص ولا يُخزَّن كي لا يَصمت:
    صفٌّ فارغ يحمل مكوّناً لا يُرسَم هو دورٌ صامت لا بطاقة.
    """
    from app.contracts.streaming import KNOWN_UI_COMPONENTS

    renderable: list[dict[str, object]] = []
    for card in cards:
        name = _card_component_name(card)
        if name is None:
            continue
        if name in KNOWN_UI_COMPONENTS:
            renderable.append(card)
        else:
            logger.warning(
                "ui_component_card_dropped_unrenderable",
                extra={"component": name, "conversation_id": conversation_id},
            )
    return renderable


async def _persist_ui_component_cards(
    *,
    conversation_id: int,
    cards: list[dict[str, object]],
) -> None:
    """يحفظ بطاقات الـ Generative UI المستقلة كصفوف مساعد content="" (ISS-106).

    غير حرج: أي فشل يُسجَّل ولا يكسر الدور. كل بطاقة صف مستقل يحمل ui_component
    بالشكل السلكي ({component, props, fallback_text}) فتُصيَّر من التاريخ بعد إعادة الدخول.

    ─────────────────────────────────────────────────────────────────
    ISS-145 (D-230): **الإرفاق ليس تسليماً**
    ─────────────────────────────────────────────────────────────────
    كان الفلتر يقبل أيّ سلسلةٍ غير فارغة اسماً للمكوّن. ونتيجته في الإنتاج: **٧ صفوف**
    بـ`content=""` تحمل `worked_example_card` — وهو اسمٌ لا يعرفه سجلّ التصيير، فرأى
    الطالب «تعذّر عرض المكوّن التفاعلي» **ولا شيء غيره**. سبعةُ أدوارٍ صامتة فعلاً.

    وISS-145 أُغلق حينها «بالتفنيد» بادّعاء `truly_silent = 0`، لأن الفحص تحقّق من أنّ
    مكوّناً **مُرفَق** لا من أنه **قابل للرسم**. صفٌّ فارغ + مكوّنٌ لا يُرسَم = دورٌ صامت.

    فالمصدر الوحيد لـ«قابل للرسم» هو ``KNOWN_UI_COMPONENTS`` (يحرس تطابقه مع سجلّ
    التصيير `scripts/fitness/check_ui_component_parity.py`)، والصفّ الفارغ الذي لا
    يجتازه **لا يُكتب** — دورٌ نصّيٌّ صادق أفضل من وعدٍ بصريٍّ لا يصل (D-191 ج).
    """
    renderable = _renderable_cards(cards, conversation_id=conversation_id)
    if not renderable:
        return
    try:
        async with async_session_factory() as db:
            persistence_service = CustomerChatBoundaryService(db)
            for card in renderable:
                await persistence_service.save_message(
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT,
                    content="",
                    ui_component=card,
                )
    except Exception as exc:
        logger.warning("ui_component_card_persist_failed: %s", exc, exc_info=True)


def _derive_correctness_override(
    question: str, history_messages: list[dict[str, str]]
) -> str | None:
    """D-157 (A1b): إشارة صواب مُتحقَّقة رمزياً لأدوار الاحتمالات — الأوراكل الحتمي
    (D-155) يحكم بدل التخمين اللفظي. يُرجِع ``"correct"`` عند تأكيد رمزي حاسم لإجابة
    صحيحة (⇒ يرفع الإتقان الدائم بصدق)، وإلا ``None`` (⇒ الإشارة اللفظية الثلاثية).
    عالي الدقة: لا يُرجِع ``"incorrect"`` (غياب التأكيد ≠ خطأ — قد لا يُجيب الطالب
    أصلاً). fail-open مطلق — أي تعذّر يُرجِع None.
    """
    try:
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        combo = OrchestratorClient._load_canonical_combinations(question, history_messages)
        if combo is None:
            return None
        pending = OrchestratorClient._pending_focus_from_history(history_messages)
        if OrchestratorClient._verify_numeric_answer(question, combo, pending) in (
            "final_ratio",
            "step_correct",
            "direction",
        ):
            return "correct"
        if OrchestratorClient._verify_answer_against_combo(question, combo):
            return "correct"
    except Exception:  # pragma: no cover - fail-open
        return None
    return None


async def _evaluate_bkt_cards(
    *,
    user_id: int,
    conversation_id: int | None,
    question: str,
    history_messages: list[dict[str, str]],
    support_level: int | None = None,
    novel_item: bool = False,
    correctness_signal: str | None = None,
) -> None:
    """D-119: تتبّع معرفي خلف الكواليس — بلا أي بطاقة تظهر للطالب.

    يُجري كتابة BKT التحليلية append-only (D-074 — تغذّي ``support_level``
    والبيداغوجيا التكيفية) ويشتقّ المسار التعلّمي (D-111) ويُسجِّله
    (telemetry / لوحة المعلم مستقبلاً) — ثم **يُرجِع ``None``**. قرار المالك
    (D-119): «تتبّع المعرفة» و«ترسيخ المهارة» خلف الكواليس، لا في سطح الطالب —
    كانتا تظهران بعد كل دور فتُكرَّران وتُشوّشان. سطح الطالب = تعليم نظيف فقط.

    D-126: يُمرِّر ``support_level`` (إن توفّر) لحساب **القناة الدائمة الصادقة**
    (durable). في الدردشة الحرة ``support_level=None`` ⇒ durable يُحمَل دون تضخيم
    (لا نمنح إتقاناً دائماً بلا دليل أداء غير مدعوم — يُغذَّى من وضع التحقق M8).

    معزول كلياً: أي فشل (DB أو غيره) يُسجَّل ولا يكسر مسار المحادثة (D-074).
    """
    try:
        # D-157 (A1b): الأوراكل الرمزي يُحسَب هنا (داخل المهمة الخلفية، خارج المسار
        # الحيّ) — إشارة صواب مُتحقَّقة رمزياً لأدوار الاحتمالات تفوق التخمين اللفظي.
        signal = correctness_signal or _derive_correctness_override(question, history_messages)
        async with async_session_factory() as bkt_db:
            evaluation = await BKTAnalyticsService(bkt_db).evaluate_and_record(
                user_id=user_id,
                session_id=conversation_id,
                question=question,
                history=history_messages,
                support_level=support_level,
                novel_item=novel_item,
                correctness_signal=signal,
            )
        # D-119/D-126: التتبّع خلف الكواليس — نُسجِّل القناتين + فجوة الوهم بدل بطاقة.
        logger.info(
            "bkt_tracking concept=%s assisted=%.2f durable=%.2f illusion_gap=%.2f "
            "load=%s (behind-the-scenes, no card)",
            evaluation.concept_id,
            evaluation.student_mastery_probability,
            evaluation.durable_mastery,
            evaluation.illusion_gap,
            evaluation.cognitive_load_estimate,
        )
        # D-194: التكرار المتباعد — الطرف المستقبِل لإشارات BKT التي كانت تُرمى.
        # `durable_mastery` و`support_level` و`evidence_correct` تُحسَب أعلاه ثم كانت
        # تنتهي عند `logger.info`؛ هنا تصير **موعد مراجعة**. جلسة مستقلّة وعزل تامّ:
        # الجدولة لا تكسر دور الطالب أبداً (نفس عقد BKT — D-074).
        with contextlib.suppress(Exception):
            from app.services.review import schedule_review_after_evaluation

            await schedule_review_after_evaluation(
                user_id=user_id,
                concept_id=evaluation.concept_id,
                evidence_correct=evaluation.evidence_correct,
                correctness_signal=evaluation.correctness_signal,
                durable_mastery=evaluation.durable_mastery,
                support_level=support_level,
            )

        # D-111: المسار التعلّمي التكيفي — يُشتقّ فوق إتقان BKT ويُسجَّل (telemetry).
        # مُستهلَك خلف الكواليس (لا بطاقة طالب — D-119)؛ معزول داخل suppress.
        with contextlib.suppress(Exception):
            from app.services.skills.learning_path_skill import (
                LearningPathInput,
                get_learning_path_skill,
            )

            path = get_learning_path_skill().derive(
                LearningPathInput(
                    concept_id=evaluation.concept_id,
                    mastery=evaluation.student_mastery_probability,
                )
            )
            logger.info(
                "learning_path next=%s difficulty=%s reco=%s (behind-the-scenes, no card)",
                path.next_concept,
                path.target_difficulty,
                path.recommendation_text,
            )
    except Exception as exc:
        # BKT must never break chat — log and continue (no student-facing impact).
        logger.warning("bkt_tracking_failed: %s", exc, exc_info=True)
    # D-119: لا بطاقات للطالب — التتبّع خلف الكواليس حصراً (return None).


_PEDAGOGY_DIRECTIVE_TIMEOUT_S = 2.0

#: D-114: علامات الحيرة — تكرارها (2+) يفرض المثال المحلول (support_level=1).
#: D-186: الأساس من المصدر القانوني الواحد، وتُضاف إليه صيغتا العجز الخاصّتان بهذا
#: المسار («ماقدرت») — إضافةٌ فوق المصدر لا نسخةٌ منه.
_CONFUSION_MARKERS: tuple[str, ...] = (*markers_for("confusion"), "ماقدرت", "ما قدرت")


class _PedagogySnapshot(NamedTuple):
    """D-114: صورة المتعلم المُجمَّعة — تُمرَّر للسياق وتقود بوّابة المثال المحلول.

    ``support_level`` الافتراض الآمن = 5 (محجوب كلياً) عند أي تعذّر — لا 1 — كي
    لا يكشف فشلٌ واحد كل الإجابات (fail-closed).
    """

    directive_text: str
    support_level: int
    confusion_count: int
    concept_id: str
    mastery: float | None


def _count_confusion_signals(history_messages: list[dict[str, str]] | None, question: str) -> int:
    """يَعُدّ رسائل الطالب التي تُعبّر عن حيرة (السؤال الحالي + سجل المحادثة).

    حتمي، بلا I/O. تكرار الحيرة (≥2) ⇒ المبتدئ عالق ويحتاج مثالاً محلولاً.
    """
    texts: list[str] = [str(question or "")]
    for msg in history_messages or []:
        if isinstance(msg, dict) and msg.get("role") == "user":
            texts.append(str(msg.get("content") or ""))
    count = 0
    for text in texts:
        low = text.strip()
        if any(marker in low for marker in _CONFUSION_MARKERS):
            count += 1
    return count


async def _build_pedagogy_directive(
    *,
    user_id: int,
    question: str,
    history_messages: list[dict[str, str]],
) -> _PedagogySnapshot:
    """D-104/D-114: يقرأ صورة المتعلم من BKT ويشتق توجيهاً تربوياً + support_level.

    «المنسّق يملك صورة المتعلم» — قراءة الإتقان تقود سلوك المعلم: سقراطي للمتمكن،
    مثال محلول كامل للمبتدئ المطلق (D-114)، والتقاط المفاهيم الخاطئة قبل أن تتجذر.
    fail-open مطلق: أي تعذّر (DB/مهلة/تصنيف) ⇒ snapshot آمن (directive=""،
    support_level=5 محجوب كلياً) — التوجيه لا يكسر دور الطالب أبداً.
    """
    try:
        from app.services.skills.adaptive_pedagogy_skill import (
            PedagogyInput,
            get_adaptive_pedagogy_skill,
        )
        from app.services.skills.bkt_engine import (
            classify_concept_with_context,
            estimate_cognitive_load,
        )

        # ISS-112: تصنيف واعٍ بالسياق — «اشرح السؤال 2» يلتصق بمفهوم الحوار
        concept_id = classify_concept_with_context(question, history_messages)

        async def _read_snapshot() -> tuple[float | None, int]:
            async with async_session_factory() as ped_db:
                service = BKTAnalyticsService(ped_db)
                mastery = await service.latest_mastery(user_id, concept_id)
                count = await service.interaction_count(user_id, concept_id)
                return mastery, count

        mastery, interaction_count = await asyncio.wait_for(
            _read_snapshot(), timeout=_PEDAGOGY_DIRECTIVE_TIMEOUT_S
        )
        directive = get_adaptive_pedagogy_skill().derive(
            PedagogyInput(
                question=question,
                concept_id=concept_id,
                mastery=mastery,
                interaction_count=interaction_count,
                cognitive_load=estimate_cognitive_load(question),
            )
        )
        # D-114: الحيرة المتكرّرة تفرض المثال المحلول حتى لو الإتقان غير منخفض.
        confusion = _count_confusion_signals(history_messages, question)
        support_level = directive.support_level
        if confusion >= 2:
            support_level = 1
        logger.info(
            "pedagogy_directive level=%s support_level=%s concept=%s mastery=%s confusion=%s",
            directive.guidance_level,
            support_level,
            concept_id,
            f"{mastery:.2f}" if mastery is not None else "none",
            confusion,
        )
        return _PedagogySnapshot(
            directive_text=directive.directive_text,
            support_level=support_level,
            confusion_count=confusion,
            concept_id=concept_id,
            mastery=mastery,
        )
    except Exception as exc:
        logger.debug("pedagogy_directive_failed (fail-open): %s", exc)
        # fail-closed على support_level: 5 = محجوب كلياً (لا كشف عند الخطأ).
        return _PedagogySnapshot("", 5, 0, "general", None)
