"""Monthly bill schedules and explicitly confirmed amount history."""
from alembic import op
import sqlalchemy as sa

revision = "0008_monthly_bills"
down_revision = "0007_subscription_schedules"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bill_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("anchor_date", sa.Date(), nullable=False),
        sa.Column("starting_estimate_cents", sa.BigInteger(), nullable=False),
        sa.Column("funding_buffer_days", sa.Integer(), nullable=False),
        sa.Column("payment_account_id", sa.String(36), sa.ForeignKey("payment_accounts.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_monthly_bill_name"),
        sa.CheckConstraint("starting_estimate_cents >= 0", name="ck_monthly_bill_amount"),
        sa.CheckConstraint("funding_buffer_days >= 0", name="ck_monthly_bill_buffer"),
    )
    with op.batch_alter_table("bill_occurrences") as batch:
        batch.add_column(sa.Column("bill_schedule_id", sa.String(36)))
        batch.add_column(sa.Column("bill_month", sa.Date()))
        batch.add_column(sa.Column("amount_confirmed_at", sa.DateTime()))
        batch.add_column(sa.Column("amount_basis", sa.String(16)))
        batch.create_foreign_key("fk_charge_bill_schedule", "bill_schedules", ["bill_schedule_id"], ["id"], ondelete="RESTRICT")
        batch.create_unique_constraint("uq_bill_schedule_month", ["bill_schedule_id", "bill_month"])
        batch.create_check_constraint("ck_bill_schedule_link", "(bill_schedule_id IS NULL AND bill_month IS NULL) OR (bill_schedule_id IS NOT NULL AND bill_month IS NOT NULL AND kind = 'bill' AND subscription_schedule_id IS NULL)")
        batch.create_check_constraint("ck_bill_amount_basis", "amount_basis IS NULL OR amount_basis IN ('starting','history_1','history_2','history_3','confirmed')")
        batch.create_check_constraint("ck_bill_confirmation", "(amount_confirmed_at IS NULL AND (amount_basis IS NULL OR amount_basis != 'confirmed')) OR (amount_confirmed_at IS NOT NULL AND coalesce(amount_basis, '') = 'confirmed')")


def downgrade():
    conn = op.get_bind()
    if conn.scalar(sa.text("SELECT count(*) FROM bill_schedules")) or conn.scalar(sa.text("SELECT count(*) FROM bill_occurrences WHERE amount_confirmed_at IS NOT NULL")):
        raise RuntimeError("Restore a verified backup instead of discarding monthly bill schedules or confirmations.")
    with op.batch_alter_table("bill_occurrences") as batch:
        for name in ("ck_bill_schedule_link", "ck_bill_amount_basis", "ck_bill_confirmation"):
            batch.drop_constraint(name, type_="check")
        batch.drop_constraint("uq_bill_schedule_month", type_="unique")
        batch.drop_constraint("fk_charge_bill_schedule", type_="foreignkey")
        for name in ("bill_schedule_id", "bill_month", "amount_confirmed_at", "amount_basis"):
            batch.drop_column(name)
    op.drop_table("bill_schedules")
