"""ISS-102 (D-WS-PROXY-004 follow-up) — admin_messages schema registration.

كارثة مكتشَفة أثناء التجريب الحي (2026-05-31): دردشة الإدمن تفشل على أي قاعدة
بيانات جديدة بـ `no such table: admin_messages` لأن الجدول لم يكن مُسجَّلاً في
`REQUIRED_SCHEMA` ولا `_ALLOWED_TABLES` → `validate_schema_on_startup()` لا
يُنشئه. هذه الاختبارات تحرس التسجيل فلا تعود الثغرة.
"""

from app.core.db_schema import _ALLOWED_TABLES, REQUIRED_SCHEMA


def test_admin_messages_registered():
    # كلا السجلّين مطلوبان: _ALLOWED_TABLES (بوّابة الأمان) + REQUIRED_SCHEMA (الإنشاء).
    assert "admin_messages" in _ALLOWED_TABLES
    assert "admin_messages" in REQUIRED_SCHEMA


def test_admin_messages_columns_match_orm():
    # يطابق ORM في app/core/domain/chat.py:AdminMessage (بلا policy_flags).
    # D-WS-CARD-PERSIST-001 (ISS-106): عمود ``ui_component`` (JSON TEXT) أُضيف لحفظ
    # بطاقات Generative UI عبر الخروج/الدخول — بين ``content`` و ``created_at``.
    columns = REQUIRED_SCHEMA["admin_messages"]["columns"]
    assert columns == ["id", "conversation_id", "role", "content", "ui_component", "created_at"]
    assert "policy_flags" not in columns


def test_admin_messages_create_table_references_admin_conversations():
    create_sql = REQUIRED_SCHEMA["admin_messages"]["create_table"]
    assert 'CREATE TABLE IF NOT EXISTS "admin_messages"' in create_sql
    # FK إلى admin_conversations (ليس customer_conversations) + حذف متتالٍ.
    assert 'REFERENCES "admin_conversations"("id") ON DELETE CASCADE' in create_sql


def test_admin_messages_has_conversation_index():
    table = REQUIRED_SCHEMA["admin_messages"]
    assert "conversation_id" in table["indexes"]
    assert "ix_admin_messages_conversation_id" in table["indexes"]["conversation_id"]
    assert table["index_names"]["conversation_id"] == "ix_admin_messages_conversation_id"
