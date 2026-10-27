"""Create income sources and draft official pay dates."""
from alembic import op
import sqlalchemy as sa


revision = "0001_income_calendar"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "income_sources",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_income_sources_name_not_blank"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "official_pay_dates",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("income_source_id", sa.String(36), nullable=False),
        sa.Column("official_pay_date", sa.Date(), nullable=False),
        sa.Column("pay_period_start", sa.Date(), nullable=True),
        sa.Column("pay_period_end", sa.Date(), nullable=True),
        sa.Column("source_reference", sa.String(500), nullable=True),
        sa.Column("review_status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "pay_period_start IS NULL OR pay_period_end IS NULL OR pay_period_start <= pay_period_end",
            name="ck_official_pay_dates_period_order",
        ),
        sa.CheckConstraint("review_status = 'draft'", name="ck_official_pay_dates_draft_only"),
        sa.ForeignKeyConstraint(["income_source_id"], ["income_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_official_pay_dates_source_date", "official_pay_dates", ["income_source_id", "official_pay_date"])


def downgrade():
    op.drop_index("ix_official_pay_dates_source_date", table_name="official_pay_dates")
    op.drop_table("official_pay_dates")
    op.drop_table("income_sources")
