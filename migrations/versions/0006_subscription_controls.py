"""Subscription state, explicit charge responsibility, and confirmation history."""
from alembic import op
import sqlalchemy as sa

revision = "0006_subscription_controls"
down_revision = "0005_payment_accounts"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("bill_occurrences") as batch:
        batch.add_column(sa.Column("subscription_state", sa.String(16), nullable=False, server_default="active"))
        batch.add_column(sa.Column("charge_is_owed", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("covered_by_bill_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_bills_coverage", "bill_occurrences", ["covered_by_bill_id"], ["id"], ondelete="RESTRICT")
        batch.create_check_constraint("ck_bills_subscription_state", "subscription_state IN ('active','inactive','covered')")
        batch.create_check_constraint("ck_bills_coverage_link", "(subscription_state = 'covered' AND covered_by_bill_id IS NOT NULL) OR (subscription_state != 'covered' AND covered_by_bill_id IS NULL)")
        batch.create_check_constraint("ck_bills_no_self_coverage", "covered_by_bill_id IS NULL OR covered_by_bill_id != id")
        batch.create_check_constraint("ck_bills_active_charge", "subscription_state != 'active' OR charge_is_owed = true")
        batch.create_check_constraint("ck_bills_regular_active", "kind = 'subscription' OR subscription_state = 'active'")
    op.create_table("subscription_changes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bill_id", sa.String(36), sa.ForeignKey("bill_occurrences.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=False),
        sa.Column("after_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))


def downgrade():
    op.drop_table("subscription_changes")
    # Downgrade removes coverage semantics. Clear self-references before SQLite
    # rebuilds/drops the old table while foreign-key enforcement stays enabled.
    op.execute("UPDATE bill_occurrences SET covered_by_bill_id=NULL, subscription_state='active', charge_is_owed=true WHERE covered_by_bill_id IS NOT NULL")
    with op.batch_alter_table("bill_occurrences") as batch:
        for name in ("ck_bills_subscription_state", "ck_bills_coverage_link", "ck_bills_no_self_coverage", "ck_bills_active_charge", "ck_bills_regular_active"):
            batch.drop_constraint(name, type_="check")
        batch.drop_constraint("fk_bills_coverage", type_="foreignkey")
        batch.drop_column("covered_by_bill_id")
        batch.drop_column("charge_is_owed")
        batch.drop_column("subscription_state")
