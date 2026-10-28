"""Individual planning obligations, separate from reservations and payments."""
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from account_models import PaymentAccount

from database import Base


class BillOccurrence(Base):
    __tablename__ = "bill_occurrences"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_bills_name_not_blank"),
        CheckConstraint("amount_cents >= 0", name="ck_bills_amount_nonnegative"),
        CheckConstraint("funding_buffer_days >= 0", name="ck_bills_buffer_nonnegative"),
        CheckConstraint("kind IN ('bill', 'subscription')", name="ck_bills_kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(16), default="bill", server_default="bill")
    payment_account_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("payment_accounts.id", ondelete="RESTRICT"))
    payment_account: Mapped[PaymentAccount | None] = relationship(lazy="selectin")
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    due_date: Mapped[date] = mapped_column(Date)
    funding_buffer_days: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    @property
    def funding_deadline(self):
        return self.due_date - timedelta(days=self.funding_buffer_days)
