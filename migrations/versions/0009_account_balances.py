"""Account/vault labels, purposes, and dated manual balance history."""
from alembic import op
import sqlalchemy as sa

revision = "0009_account_balances"
down_revision = "0008_monthly_bills"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payment_accounts") as batch:
        batch.add_column(sa.Column("kind", sa.String(16), nullable=False, server_default="account"))
        batch.add_column(sa.Column("purpose", sa.String(200)))
        batch.create_check_constraint("ck_accounts_kind", "kind IN ('account','vault')")
        batch.create_check_constraint("ck_vault_purpose", "kind != 'vault' OR length(trim(coalesce(purpose, ''))) > 0")
    op.create_table(
        "account_balances",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("payment_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("balance_date", sa.Date(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.String(200)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount_cents >= 0", name="ck_account_balance_nonnegative"),
    )


def downgrade():
    conn = op.get_bind()
    if conn.scalar(sa.text("SELECT count(*) FROM account_balances")) or conn.scalar(sa.text("SELECT count(*) FROM payment_accounts WHERE kind != 'account' OR purpose IS NOT NULL")):
        raise RuntimeError("Restore a verified backup instead of discarding balances, vaults, or purposes.")
    op.drop_table("account_balances")
    with op.batch_alter_table("payment_accounts") as batch:
        batch.drop_constraint("ck_vault_purpose", type_="check")
        batch.drop_constraint("ck_accounts_kind", type_="check")
        batch.drop_column("purpose")
        batch.drop_column("kind")
