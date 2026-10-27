"""Add optional projected net amounts, stored as integer cents."""
from alembic import op
import sqlalchemy as sa

revision = "0002_expected_net_pay"
down_revision = "0001_income_calendar"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("income_sources", sa.Column(
        "expected_net_cents", sa.BigInteger(),
        sa.CheckConstraint("expected_net_cents >= 0", name="ck_income_sources_expected_nonnegative"),
        nullable=True,
    ))
    op.add_column("official_pay_dates", sa.Column(
        "expected_net_override_cents", sa.BigInteger(),
        sa.CheckConstraint("expected_net_override_cents >= 0", name="ck_pay_dates_expected_nonnegative"),
        nullable=True,
    ))


def downgrade():
    op.drop_column("official_pay_dates", "expected_net_override_cents")
    op.drop_column("income_sources", "expected_net_cents")
