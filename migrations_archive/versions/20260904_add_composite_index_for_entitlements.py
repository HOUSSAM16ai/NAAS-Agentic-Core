"""Add composite index for entitlements to optimize entitlement_status query

Revision ID: 20260904_add_entitlements_index
Revises:
Create Date: 2026-09-04

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260904_add_entitlements_index"
down_revision = "f2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use concurrent index creation to avoid locking the billing table
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_entitlements_user_id_expires_at_id",
            "entitlements",
            ["user_id", "expires_at", "id"],
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_entitlements_user_id",
            table_name="entitlements",
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        # Restore the single column index first
        op.create_index(
            "ix_entitlements_user_id",
            "entitlements",
            ["user_id"],
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_entitlements_user_id_expires_at_id",
            table_name="entitlements",
            postgresql_concurrently=True,
        )
