"""ما الذي يُميّز مقبس العميل عن مقبس الإدمن — الفروق الستّة، مُرمَّزةً (ISS-155).

## العطب الذي وُلدت منه هذه الوحدة

`chat_ws_stategraph` (148 سطراً · cc 20) و`admin_chat_ws_stategraph` (153 · cc 23)
كانتا شبه متطابقتين. قياسٌ آليّ بـ`difflib` أثبت أنّ الفرق **ستّة أشياء لا غير**
وأنّ ~120 سطراً بينهما متطابقة **بالبايت**:

| # | الفرق | أين يعيش الآن |
|---|-------|----------------|
| 1 | بادئة المصادقة (رمز العميل مقابل JWT الإدمن) | الغلاف في `routes.py` |
| 2 | بوّابة 4403 الإدارية | الغلاف في `routes.py` |
| 3 | `chat_scope` | `ChatWsScope.name` |
| 4 | تمرير `admin_payload` | وسيط `serve_chat_ws` |
| 5 | `route_name` | `ChatWsScope.route_name` |
| 6 | حرفيّات السجلّ (`role=` · رسالة الانقطاع) | `ChatWsScope` |

وهذا الازدواج هو مصدر «Internal Change Coupling 33» في تقرير CodeScene: كلّ تعديل
على مسار الدردشة كان يُطبَّق مرّتين — وهي بالضبط آلية D-013 التي أنتجت ISS-126
وISS-139 حين تفرّقت النسختان.

## لماذا وحدةٌ مستقلّة عن آلة الدور

الوحدة تجيب سؤال ISS-155 المركزي — «بمَ يختلف المساران؟» — في مكانٍ واحد يُقرأ بلا
قراءة الآلة. وهي **ورقة**: لا تستورد إلّا `dataclasses`، فيأخذها أيّ مستهلك (اختبار
· مسارٌ ثالث لاحقاً) بلا أن يجرّ المحرّك ولا قاعدة البيانات.

## قراران يُصرَّحان لا يُذابان (D-206 · L12)

**`name` حقلٌ واحد لا اثنان.** `chat_scope` وحرفيّة `role=` في السجلّ هما **نفس
السلسلة في المواضع السبعة كلّها** — القياس الآليّ يُثبته. حقلان كانا سيُرمّزان
تمييزاً لم يعرفه الكود قطّ. إن أراد مراجعٌ فصلهما فبقرارٍ مكتوب، لا باختراع تباينٍ
أثناء نقلٍ حرفيّ.

**`WsTurnState` قابلة للتغيير**، بخلاف `TurnIdentity`/`AgentChatCall` المُجمَّدتين
في D-237. الزوج اللاصق متغيّرا حلقة تكتبهما دالّتان مستخرَجتان؛ وتجميدهما يفرض
رقصة إعادة-إسنادٍ عبر ثلاث إطارات نداء تُخفي النيّة بدل أن تُظهرها. التغييريّة هنا
**النموذج الصادق**، وتُقال كي لا تُقرأ سهواً ضدّ سابقة D-237.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ChatWsScope:
    """الفروق الثلاثة التي تُميّز مسار العميل عن مسار الإدمن، مجموعةً في كائن.

    الوسائط التي تُسافر معاً تُجمَّع (سابقة D-237 · `TurnIdentity`/`AgentChatCall`)،
    فينزل عدد الوسائط ويصير الفرق بين المسارين **قيمةً واحدة** تُقرأ في سطر.
    """

    #: `chat_scope` المُمرَّر للمحرّك، **وهو نفسه** حرفيّة `role=` في السجلّ.
    name: str
    #: المسار كما يظهر في سجلّ تشخيص الهويّة.
    route_name: str
    #: ما يُسجَّل عند انقطاع المقبس.
    disconnect_message: str


@dataclass(slots=True)
class WsTurnState:
    """الحالة اللاصقة عبر أدوار مقبسٍ واحد — قابلة للتغيير عمداً (انظر وثيقة الوحدة)."""

    sticky_conversation_id: int | None = None
    sticky_thread_id: str | None = None


@dataclass(slots=True)
class WsTurnBundle:
    """ما يسافر معاً في نداءات آلة الدور — النطاق والحالة اللاصقة والمُعرِّف.

    يُجمَّع (سابقة D-237 · `TurnIdentity`/`AgentChatCall`): هذه الحقول الثلاثة
    تظهر معاً في `_resolve_turn_conversation_id` و`_ensure_turn_conversation`
    و`_build_turn_context` و`_run_turn`، فتنزّل العدد البيني للوسائط ويصير
    «الدور» قيمةً واحدة تُقرأ في سطر. والهدف (`objective`) فيه لأنّه يلتحق
    به عند اكتمال قراءة الدور — والقيمة الفارغة **تُحظر** (يُبنى الكائن بعد
    نجاح `_read_turn` فقط).
    """

    scope: ChatWsScope
    state: WsTurnState
    user_id: int
    objective: str = field(default="")


CUSTOMER_WS_SCOPE = ChatWsScope(
    name="customer",
    route_name="orchestrator_ws_customer",
    disconnect_message="Customer chat websocket disconnected",
)

ADMIN_WS_SCOPE = ChatWsScope(
    name="admin",
    route_name="orchestrator_ws_admin",
    disconnect_message="Admin chat websocket disconnected",
)
