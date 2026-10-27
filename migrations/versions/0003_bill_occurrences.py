"""Add individual bill-planning occurrences."""
from alembic import op
import sqlalchemy as sa

revision = "0003_bill_occurrences"
down_revision = "0002_expected_net_pay"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bill_occurrences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("funding_buffer_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_bills_name_not_blank"),
        sa.CheckConstraint("amount_cents >= 0", name="ck_bills_amount_nonnegative"),
        sa.CheckConstraint("funding_buffer_days >= 0", name="ck_bills_buffer_nonnegative"),
    )


def downgrade():
    op.drop_table("bill_occurrences")
