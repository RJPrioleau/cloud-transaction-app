"""Recurring subscription schedules and optional external coverage labels."""
from alembic import op
import sqlalchemy as sa

revision = "0007_subscription_schedules"
down_revision = "0006_subscription_controls"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "subscription_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("frequency", sa.String(16), nullable=False),
        sa.Column("anchor_date", sa.Date(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("funding_buffer_days", sa.Integer(), nullable=False),
        sa.Column("payment_account_id", sa.String(36), sa.ForeignKey("payment_accounts.id", ondelete="RESTRICT")),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("covered_by_bill_id", sa.String(36), sa.ForeignKey("bill_occurrences.id", ondelete="RESTRICT")),
        sa.Column("coverage_label", sa.String(200)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("frequency IN ('monthly','yearly')", name="ck_schedule_frequency"),
        sa.CheckConstraint("state IN ('active','inactive','covered')", name="ck_schedule_state"),
        sa.CheckConstraint("amount_cents >= 0", name="ck_schedule_amount"),
        sa.CheckConstraint("funding_buffer_days >= 0", name="ck_schedule_buffer"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_schedule_name"),
        sa.CheckConstraint("(state = 'covered' AND (covered_by_bill_id IS NOT NULL OR length(trim(coalesce(coverage_label, ''))) > 0)) OR (state != 'covered' AND covered_by_bill_id IS NULL AND coverage_label IS NULL)", name="ck_schedule_coverage"),
    )
    with op.batch_alter_table("bill_occurrences") as batch:
        batch.add_column(sa.Column("coverage_label", sa.String(200)))
        batch.add_column(sa.Column("subscription_schedule_id", sa.String(36)))
        batch.create_foreign_key("fk_charge_schedule", "subscription_schedules", ["subscription_schedule_id"], ["id"], ondelete="RESTRICT")
        batch.create_unique_constraint("uq_subscription_charge_date", ["subscription_schedule_id", "due_date"])
        batch.drop_constraint("ck_bills_coverage_link", type_="check")
        batch.create_check_constraint("ck_bills_coverage_link", "(subscription_state = 'covered' AND (covered_by_bill_id IS NOT NULL OR length(trim(coalesce(coverage_label, ''))) > 0)) OR (subscription_state != 'covered' AND covered_by_bill_id IS NULL AND coverage_label IS NULL)")


def downgrade():
    # Dropping recurrence would discard schedule intent and external coverage.
    # Refuse populated downgrades; recovery is from a verified backup.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT count(*) FROM subscription_schedules")) or connection.scalar(sa.text("SELECT count(*) FROM bill_occurrences WHERE coverage_label IS NOT NULL")):
        raise RuntimeError("Restore a verified backup instead of discarding subscription schedules or coverage.")
    with op.batch_alter_table("bill_occurrences") as batch:
        batch.drop_constraint("uq_subscription_charge_date", type_="unique")
        batch.drop_constraint("fk_charge_schedule", type_="foreignkey")
        batch.drop_constraint("ck_bills_coverage_link", type_="check")
        batch.drop_column("subscription_schedule_id")
        batch.drop_column("coverage_label")
        batch.create_check_constraint("ck_bills_coverage_link", "(subscription_state = 'covered' AND covered_by_bill_id IS NOT NULL) OR (subscription_state != 'covered' AND covered_by_bill_id IS NULL)")
    op.drop_table("subscription_schedules")
