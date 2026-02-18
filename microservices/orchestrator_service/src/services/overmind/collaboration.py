"""
نظام التعاون بين الوكلاء (Agent Collaboration System).

هذا الملف يوفر آليات متقدمة للتنسيق والتعاون بين الوكلاء المختلفة.
يضمن تدفق المعلومات بشكل سلس وفعال بين جميع أعضاء الفريق.

المبادئ المطبقة:
- Observer Pattern: الوكلاء تراقب تغييرات الحالة
- Mediator Pattern: وسيط مركزي للتواصل
- Command Pattern: تمرير الأوامر بين الوكلاء

الميزات الرئيسية:
- ذاكرة مشتركة محسّنة (Enhanced Shared Memory)
- آلية الإشعارات بين الوكلاء (Inter-Agent Notifications)
- تتبع المساهمات (Contribution Tracking)
- حل النزاعات (Conflict Resolution)
"""

import time
from collections import defaultdict

from app.core.di import get_logger

logger = get_logger(__name__)


class AgentContribution:
    """
    تمثيل لمساهمة وكيل واحد في المهمة.

    يتتبع ما قام به كل وكيل، متى، وما كانت النتيجة.
    هذا يساعد في التدقيق والتحليل اللاحق.

    Attributes:
        agent_name: اسم الوكيل (مثلاً "strategist")
        action: الإجراء الذي قام به (مثلاً "create_plan")
        timestamp: وقت المساهمة (Unix timestamp)
        input_data: البيانات التي استقبلها الوكيل
        output_data: النتيجة التي أنتجها الوكيل
        success: هل نجحت المساهمة أم لا
        error_message: رسالة الخطأ إن وُجدت
    """

    def __init__(
        self,
        agent_name: str,
        action: str,
        input_data: object = None,
        output_data: object = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """
        إنشاء مساهمة وكيل جديدة.

        ملاحظة:
            - self تشير إلى الكائن الحالي (instance)
            - -> None تعني أن الدالة لا تُرجع قيمة
            - | تعني "أو" في type hints (str أو None)
        """
        self.agent_name = agent_name  # اسم الوكيل
        self.action = action  # الإجراء
        self.timestamp = time.time()  # الوقت الحالي
        self.input_data = input_data  # المدخلات
        self.output_data = output_data  # المخرجات
        self.success = success  # النجاح/الفشل
        self.error_message = error_message  # رسالة الخطأ

    def to_dict(self) -> dict[str, object]:
        """
        تحويل المساهمة إلى dictionary.

        Returns:
            dict: تمثيل JSON-friendly للمساهمة

        ملاحظة:
            - {} تُنشئ dictionary فارغ
            - "key": value تحدد زوج مفتاح-قيمة
            - الفاصلة (,) تفصل بين الأزواج
        """
        return {
            "agent_name": self.agent_name,
            "action": self.action,
            "timestamp": self.timestamp,
            "success": self.success,
            "error_message": self.error_message,
            # لا نُضمن input/output لتجنب البيانات الضخمة
        }


class CollaborationHub:
    """
    مركز التعاون بين الوكلاء (Collaboration Hub).

    يعمل كوسيط (Mediator) بين جميع الوكلاء، يسهل:
    - تبادل المعلومات
    - تتبع المساهمات
    - إدارة الذاكرة المشتركة
    - الإشعارات بين الوكلاء

    هذا يمنع الوكلاء من الاعتماد مباشرة على بعضها البعض،
    ويحسن قابلية الاختبار والصيانة.
    """

    def __init__(self) -> None:
        """
        تهيئة مركز التعاون.

        ملاحظة:
            - {} تُنشئ dictionary فارغ
            - [] تُنشئ list فارغة
            - defaultdict(list) تُنشئ dict يُنشئ list تلقائياً للمفاتيح الجديدة
        """
        # الذاكرة المشتركة بين جميع الوكلاء
        self.shared_memory: dict[str, object] = {}

        # تاريخ المساهمات من كل وكيل
        self.contributions: list[AgentContribution] = []

        # الإشعارات المعلقة لكل وكيل
        # defaultdict يُنشئ list فارغة تلقائياً عند أول وصول
        self.pending_notifications: dict[str, list[dict[str, object]]] = defaultdict(list)

        # إحصائيات الأداء
        self.stats: dict[str, int] = {
            "total_contributions": 0,  # إجمالي المساهمات
            "successful_contributions": 0,  # المساهمات الناجحة
            "failed_contributions": 0,  # المساهمات الفاشلة
        }

    def store_data(self, key: str, value: object) -> None:
        """
        تخزين بيانات في الذاكرة المشتركة.

        Args:
            key: مفتاح البيانات (مثلاً "current_plan")
            value: القيمة المراد تخزينها (أي نوع)

        مثال:
            >>> hub.store_data("user_id", 123)
            >>> hub.store_data("plan", {"steps": [...]})

        ملاحظة:
            - [key] = value تُخزن القيمة في dictionary
            - أي وكيل يمكنه قراءة هذه البيانات لاحقاً
        """
        self.shared_memory[key] = value
        logger.debug(f"Stored '{key}' in shared memory")

    def retrieve_data(self, key: str, default: object = None) -> object:
        """
        استرجاع بيانات من الذاكرة المشتركة.

        Args:
            key: مفتاح البيانات المطلوبة
            default: القيمة الافتراضية إذا لم يُوجد المفتاح

        Returns:
            القيمة المخزنة أو default

        مثال:
            >>> user_id = hub.retrieve_data("user_id", 0)
            >>> plan = hub.retrieve_data("plan")

        ملاحظة:
            - .get() method آمنة، لا ترفع KeyError إذا لم يُوجد المفتاح
            - تُرجع default بدلاً من ذلك
        """
        return self.shared_memory.get(key, default)

    def record_contribution(
        self,
        agent_name: str,
        action: str,
        input_data: object = None,
        output_data: object = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """
        تسجيل مساهمة وكيل في المهمة.

        يُستخدم لتتبع ما قام به كل وكيل للتحليل والتدقيق.

        Args:
            agent_name: اسم الوكيل ("strategist", "architect", إلخ)
            action: الإجراء الذي قام به
            input_data: البيانات التي استقبلها
            output_data: النتيجة التي أنتجها
            success: هل نجح الإجراء
            error_message: رسالة الخطأ إن فشل

        مثال:
            >>> hub.record_contribution(
            ...     agent_name="strategist",
            ...     action="create_plan",
            ...     output_data=plan,
            ...     success=True
            ... )

        ملاحظة:
            - القوس () ينشئ كائن AgentContribution جديد
            - .append() تُضيف العنصر إلى نهاية القائمة
            - += 1 تزيد القيمة بمقدار 1
        """
        # إنشاء كائن المساهمة
        contribution = AgentContribution(
            agent_name=agent_name,
            action=action,
            input_data=input_data,
            output_data=output_data,
            success=success,
            error_message=error_message,
        )

        # إضافة المساهمة للقائمة
        self.contributions.append(contribution)

        # تحديث الإحصائيات
        self.stats["total_contributions"] += 1
        if success:
            self.stats["successful_contributions"] += 1
        else:
            self.stats["failed_contributions"] += 1

        logger.info(f"Agent '{agent_name}' contributed: {action} ({'✓' if success else '✗'})")

    def notify_agent(self, target_agent: str, message: dict[str, object]) -> None:
        """
        إرسال إشعار لوكيل معين.

        يُستخدم للتواصل غير المتزامن بين الوكلاء.

        Args:
            target_agent: اسم الوكيل المستهدف
            message: رسالة الإشعار (dict)

        مثال:
            >>> hub.notify_agent("operator", {
            ...     "type": "priority_task",
            ...     "task_id": 42,
            ...     "urgency": "high"
            ... })

        ملاحظة:
            - [] تصل إلى القيمة في dictionary
            - .append() تضيف العنصر للقائمة
            - defaultdict تُنشئ list تلقائياً إذا لم تكن موجودة
        """
        self.pending_notifications[target_agent].append(message)
        logger.debug(f"Notification queued for '{target_agent}'")

    def get_notifications(self, agent_name: str) -> list[dict[str, object]]:
        """
        استرجاع جميع الإشعارات المعلقة لوكيل معين.

        Args:
            agent_name: اسم الوكيل

        Returns:
            list: قائمة الإشعارات (قد تكون فارغة)

        مثال:
            >>> notifications = hub.get_notifications("operator")
            >>> for notif in notifications:
            ...     logger.info(notif)

        ملاحظة:
            - .pop() تُرجع وتحذف العنصر من dictionary
            - [] تُرجع list فارغة كقيمة افتراضية
        """
        # استرجاع وحذف الإشعارات دفعة واحدة
        notifications = self.pending_notifications.pop(agent_name, [])
        if notifications:
            logger.debug(f"Retrieved {len(notifications)} notification(s) for '{agent_name}'")
        return notifications

    def get_agent_summary(self, agent_name: str) -> dict[str, object]:
        """
        الحصول على ملخص مساهمات وكيل معين.

        Args:
            agent_name: اسم الوكيل

        Returns:
            dict: إحصائيات وملخص المساهمات

        مثال:
            >>> summary = hub.get_agent_summary("strategist")
            >>> logger.info("Contributions: %s", summary['total_contributions'])

        ملاحظة:
            - List comprehension: [x for x in list if condition]
            - len() تُرجع عدد العناصر في القائمة
            - الفاصلة (,) في list comprehension تفصل الشروط
        """
        # جمع جميع مساهمات هذا الوكيل
        agent_contributions = [c for c in self.contributions if c.agent_name == agent_name]

        # حساب النجاحات والفشل
        successes = sum(1 for c in agent_contributions if c.success)
        failures = len(agent_contributions) - successes

        return {
            "agent_name": agent_name,
            "total_contributions": len(agent_contributions),
            "successful": successes,
            "failed": failures,
            "success_rate": successes / len(agent_contributions) if agent_contributions else 0.0,
        }

    def get_full_report(self) -> dict[str, object]:
        """
        الحصول على تقرير شامل لجميع الأنشطة.

        Returns:
            dict: تقرير كامل يشمل جميع المساهمات والإحصائيات

        مثال:
            >>> report = hub.get_full_report()
            >>> logger.info(json.dumps(report, indent=2))

        ملاحظة:
            - [c.to_dict() for c in list] تحول كل عنصر إلى dict
            - ** operator تفكك dictionary إلى key-value pairs
        """
        return {
            "total_agents": len({c.agent_name for c in self.contributions}),
            "contributions": [c.to_dict() for c in self.contributions],
            "stats": self.stats,
            "shared_memory_keys": list(self.shared_memory.keys()),
        }
