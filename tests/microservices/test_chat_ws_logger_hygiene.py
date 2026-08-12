"""نظافة السجلّ والوثيقة في معالِجات `routes.py` — حارسٌ بنيويّ لصنفٍ لا لحالة.

## العطب الذي وُلد منه هذا الملفّ (ISS-155 · الالتزام الأوّل)

كان توأم العميل يبدأ هكذا:

```python
async def chat_ws_stategraph(websocket: WebSocket) -> None:
    from microservices.orchestrator_service.src.core.logging import get_logger

    logger = get_logger("routes")
    \"\"\"يشغّل WebSocket chat فوق LangGraph...\"\"\"
```

عطبان مستقلّان في أربعة أسطر:

1. **النصّ ليس docstring.** يلي جملتين، فهو **تعبيرٌ ميت** يُقيَّم ويُرمى —
   `chat_ws_stategraph.__doc__ is None` بينما التوأم الإداري يملك وثيقةً حقيقية.
   ووثيقةٌ يظنّها كاتبُها موجودة أسوأ من غيابها المُعلَن (§0: المجهول أفضل من يقين زائف).

2. **الـ`logger` المحلّي يحجب logger الوحدة.** `get_logger("routes")` تُرجِع
   `logging.getLogger("routes")` — وهو logger **جذريّ** بهذا الاسم، لا
   `logging.getLogger("microservices.orchestrator_service.src.api.routes")` الذي
   تستعمله بقيّة الوحدة (`routes.py:140`). فكلّ سجلّات `[CONV_LIFECYCLE]` على مسار
   الطالب الحيّ تعبر شجرةَ معالِجاتٍ ومستوىً وتنسيقاً **مختلفة** عن نظيرتها الإدارية
   الحرفيّة. وهذا يفسّر ظهور السطر نفسه في طوبولوجيا واختفاءه في أخرى — وهو بالضبط
   صنف العطب الذي يجعل التشخيص مستحيلاً وقت الحادثة.

## لماذا الحارس على الصنف لا على الحالة

القاعدة المفروضة هنا ليست «أصلِح هاتين الدالّتين» بل **«لا معالِج في `routes.py`
يُعيد ربط الاسم `logger` محلّياً، وكلّ معالِج يملك وثيقة»**. حارسٌ يسمّي حالتين
يُنسى عند الثالثة (D-207 · «الثمن الثالث»: ما لا يُرى لا يُساءَل).

المسح بالـAST لا بالنصّ: `grep` عن `get_logger` يطابق تعليقاً يشرح غيابها، وتلك
بوّابةٌ تشهد بما لم تقرأ (D-208 · البند ٦).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROUTES = (
    Path(__file__).resolve().parents[2] / "microservices/orchestrator_service/src/api/routes.py"
)

#: أسماء الديكوريتر التي تجعل الدالّة معالِج مسار.
_ROUTE_DECORATORS = frozenset({"get", "post", "put", "patch", "delete", "websocket", "api_route"})

#: دَينٌ مُجمَّد **يتقلّص فقط** — معالِجاتٌ بلا docstring اليوم وخارج نطاق ISS-155.
#:
#: لماذا دَينٌ لا تضييقُ الحارس على التوأمين: حارسٌ يسمّي حالتين يُنسى عند الثالثة
#: (D-207 · «الثمن الثالث»). والقائمة تجعل الفجوة **مرئية ومعدودة** بدل أن تختفي.
#:
#: ولماذا لا تُسَدّ هنا: `create_mission_endpoint` و`get_mission_endpoint` منشورتان في
#: `docs/contracts/openapi/orchestrator_service-openapi.json` بـ`description: null`؛
#: وdocstring المُعالِج **هي** حقل `description` المنشور (D-237 · البند ٤)، فإضافتها
#: تُحدِث انحرافاً في عقدٍ منشور من أجل سطرٍ تجميلي. و`stream_mission_ws` خارج نطاق
#: هذا الـPR بقرار المالك. الثلاثة تُسَدّ في الـPR الذي يمسّها أصلاً.
_DOCSTRING_DEBT: frozenset[str] = frozenset(
    {
        "create_mission_endpoint",
        "get_mission_endpoint",
        "stream_mission_ws",
    }
)


def _is_route_decorator(deco: ast.expr) -> bool:
    """هل هذا الديكوريتر يُعرِّف دالّته معالِج مسارٍ؟"""
    func = deco.func if isinstance(deco, ast.Call) else deco
    if not isinstance(func, ast.Attribute):
        return False
    return func.attr in _ROUTE_DECORATORS


def _route_handlers() -> list[ast.AsyncFunctionDef | ast.FunctionDef]:
    """يعيد كلّ معالِج مسار على المستوى الأعلى في `routes.py`."""
    tree = ast.parse(ROUTES.read_text(encoding="utf-8"))
    handlers: list[ast.AsyncFunctionDef | ast.FunctionDef] = []
    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        if any(_is_route_decorator(deco) for deco in node.decorator_list):
            handlers.append(node)
    return handlers


def _handler_ids() -> list[str]:
    return [handler.name for handler in _route_handlers()]


def _target_names(node: ast.AST) -> list[str]:
    """أسماء الأهداف في إسنادٍ — فارغةٌ لما ليس إسناداً."""
    if isinstance(node, ast.Assign):
        return [target.id for target in node.targets if isinstance(target, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def _imported_names(node: ast.AST) -> list[str]:
    """الأسماء التي يُدخِلها سطر استيراد — بعد `as` إن وُجد."""
    if isinstance(node, ast.ImportFrom | ast.Import):
        return [alias.asname or alias.name.split(".")[-1] for alias in node.names]
    return []


def _binds_logger(node: ast.AST) -> bool:
    """هل تربط هذه العقدة الاسم `logger` — إسناداً عادياً أو مُعَنوَناً أو استيراداً؟"""
    return "logger" in _target_names(node) or "logger" in _imported_names(node)


def _rebinds_logger(handler: ast.AsyncFunctionDef | ast.FunctionDef) -> bool:
    """هل يُعيد المعالِج ربط الاسم `logger` داخل جسده؟"""
    return any(_binds_logger(node) for node in ast.walk(handler))


@pytest.mark.parametrize("handler", _route_handlers(), ids=_handler_ids())
def test_no_route_handler_shadows_the_module_logger(
    handler: ast.AsyncFunctionDef | ast.FunctionDef,
) -> None:
    """معالِجٌ يبني logger خاصّاً به يبثّ في شجرةٍ أخرى — فيختفي سطرُه دون تفسير."""
    assert not _rebinds_logger(handler), (
        f"{handler.name} (routes.py:{handler.lineno}) يُعيد ربط الاسم `logger` محلّياً.\n"
        f"   `logger` الوحدة هو `logging.getLogger(__name__)` (routes.py:140)؛ و"
        f"`get_logger('routes')` تُرجِع logger **جذرياً** بهذا الاسم — شجرة معالِجات "
        f"ومستوىً وتنسيق مختلفة. فيظهر نفس السطر في طوبولوجيا ويختفي في أخرى.\n"
        f"   استعمل `logger` الوحدة."
    )


@pytest.mark.parametrize("handler", _route_handlers(), ids=_handler_ids())
def test_every_route_handler_has_a_real_docstring(
    handler: ast.AsyncFunctionDef | ast.FunctionDef,
) -> None:
    """نصٌّ يلي جملةً ليس وثيقة — و`ast.get_docstring` هو الحَكَم لا العينُ المجرّدة.

    الدَّين ثنائي الاتجاه (سابقة D-189): المُجمَّد لا يُلام، **والمُجمَّد الذي سُدّ
    ولم يُحذَف من القائمة يُفشِل أيضاً** — وإلّا تقادمت الخريطة بصمت (D-188).
    """
    documented = bool((ast.get_docstring(handler) or "").strip())

    if handler.name in _DOCSTRING_DEBT:
        assert not documented, (
            f"{handler.name} صار يملك docstring — احذفه من `_DOCSTRING_DEBT`.\n"
            f"   الدَّين يتقلّص فقط، ودَينٌ أُغلق بلا تحديث القائمة خريطةٌ تكذب.\n"
            f"   ⚠️ إن كان المُعالِج منشوراً في عقد OpenAPI فأعِد توليد العقد في نفس الـPR "
            f"(docstring المُعالِج **هي** حقل `description` — D-237 · البند ٤)."
        )
        return

    assert documented, (
        f"{handler.name} (routes.py:{handler.lineno}) بلا docstring حقيقية.\n"
        f"   إن بدا في الملفّ نصٌّ ثلاثيّ الاقتباس فتحقّق من موضعه: النصّ الذي يلي "
        f"جملةً تنفيذية **تعبيرٌ ميت** يُقيَّم ويُرمى، و`__doc__` تبقى None.\n"
        f"   ارفعه ليكون أوّل جملة في الجسد."
    )


def test_the_docstring_debt_names_only_real_handlers() -> None:
    """دَينٌ يسمّي معالِجاً محذوفاً أو مُعاد التسمية يحرس العدم (D-208 · البند ٨)."""
    unknown = _DOCSTRING_DEBT - set(_handler_ids())
    assert not unknown, (
        f"`_DOCSTRING_DEBT` يسمّي ما ليس معالِجاً في routes.py: {sorted(unknown)}.\n"
        f"   إن حُذف أو أُعيدت تسميته فحدِّث القائمة."
    )
