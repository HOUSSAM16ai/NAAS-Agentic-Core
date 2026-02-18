"""
مخططات البيانات الأساسية (Core Schemas).
----------------------------------------
تحتوي هذه الوحدة على النماذج الأساسية التي تطبق مبدأ المتانة (Robustness Principle):
"كن مرناً فيما تستقبل، وصارماً فيما ترسل".

المعايير:
- CS50 2025: توثيق عربي احترافي.
- Postel's Law: استخدام `extra='ignore'` في النماذج لضمان التوافقية.
"""

from pydantic import BaseModel, ConfigDict

__all__ = ["RobustBaseModel"]


class RobustBaseModel(BaseModel):
    """
    النموذج الأساسي المتين (Robust Base Model).

    هذا النموذج يطبق مبدأ Postel's Law من خلال:
    1. تجاهل الحقول الإضافية عند استقبال البيانات (Flexible Input).
    2. الحفاظ على الصرامة في تعريف الحقول المطلوبة (Strict Validation).

    الاستخدام:
    يجب أن ترث جميع نماذج الطلبات (Request DTOs) من هذا الصنف.
    """

    model_config = ConfigDict(
        extra="ignore",  # تجاهل الحقول الزائدة بدلاً من إثارة خطأ
        from_attributes=True,  # دعم التحويل من كائنات ORM
        populate_by_name=True,  # السماح باستخدام الأسماء المستعارة
        json_schema_extra={
            "examples": [{"_comment": "Extra fields are ignored by design (Postel's Law)."}]
        },
    )

    def to_dict(self, **kwargs: dict[str, str | int | bool]) -> dict[str, object]:
        """
        تحويل النموذج إلى قاموس.
        """
        return self.model_dump(**kwargs)
