"""Add named payment accounts and optional obligation references."""
from alembic import op
import sqlalchemy as sa

revision = "0005_payment_accounts"
down_revision = "0004_bill_subscription_kind"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("payment_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_accounts_name_not_blank"))
    with op.batch_alter_table("bill_occurrences") as batch:
        batch.add_column(sa.Column("payment_account_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_bills_payment_account", "payment_accounts", ["payment_account_id"], ["id"], ondelete="RESTRICT")


def downgrade():
    with op.batch_alter_table("bill_occurrences") as batch:
        batch.drop_constraint("fk_bills_payment_account", type_="foreignkey")
        batch.drop_column("payment_account_id")
    op.drop_table("payment_accounts")
