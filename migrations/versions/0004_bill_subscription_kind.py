"""Classify obligations as bills or subscriptions, preserving existing bills."""
from alembic import op
import sqlalchemy as sa

revision = "0004_bill_subscription_kind"
down_revision = "0003_bill_occurrences"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("bill_occurrences", sa.Column(
        "kind", sa.String(16),
        sa.CheckConstraint("kind IN ('bill', 'subscription')", name="ck_bills_kind"),
        nullable=False, server_default="bill",
    ))


def downgrade():
    # A later SQLite table rebuild may reflect the inline check as a table check.
    # Explicitly remove it before removing its column in either representation.
    with op.batch_alter_table("bill_occurrences") as batch:
        batch.drop_constraint("ck_bills_kind", type_="check")
        batch.drop_column("kind")
