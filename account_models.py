"""Named accounts/vaults and manually recorded balance snapshots."""
from datetime import date, datetime, timezone
from uuid import uuid4
from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class PaymentAccount(Base):
    __tablename__ = "payment_accounts"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_accounts_name_not_blank"),
        CheckConstraint("kind IN ('account','vault')", name="ck_accounts_kind"),
        CheckConstraint("kind != 'vault' OR length(trim(coalesce(purpose, ''))) > 0", name="ck_vault_purpose"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(16), default="account", server_default="account")
    purpose: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class AccountBalance(Base):
    """An absolute balance as of a date, not a transaction or a delta."""
    __tablename__ = "account_balances"
    __table_args__ = (CheckConstraint("amount_cents >= 0", name="ck_account_balance_nonnegative"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("payment_accounts.id", ondelete="RESTRICT"))
    balance_date: Mapped[date] = mapped_column(Date)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
