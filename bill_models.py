"""Individual planning obligations, separate from reservations and payments."""
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, Integer, String, ForeignKey, Text, UniqueConstraint, true
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
        CheckConstraint("subscription_state IN ('active','inactive','covered')", name="ck_bills_subscription_state"),
        CheckConstraint("(subscription_state = 'covered' AND (covered_by_bill_id IS NOT NULL OR length(trim(coalesce(coverage_label, ''))) > 0)) OR (subscription_state != 'covered' AND covered_by_bill_id IS NULL AND coverage_label IS NULL)", name="ck_bills_coverage_link"),
        UniqueConstraint("subscription_schedule_id", "due_date", name="uq_subscription_charge_date"),
        CheckConstraint("covered_by_bill_id IS NULL OR covered_by_bill_id != id", name="ck_bills_no_self_coverage"),
        CheckConstraint("subscription_state != 'active' OR charge_is_owed = true", name="ck_bills_active_charge"),
        CheckConstraint("kind = 'subscription' OR subscription_state = 'active'", name="ck_bills_regular_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(16), default="bill", server_default="bill")
    subscription_state: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    charge_is_owed: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    covered_by_bill_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("bill_occurrences.id", name="fk_bills_coverage", ondelete="RESTRICT"))
    coverage_label: Mapped[str | None] = mapped_column(String(200))
    subscription_schedule_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("subscription_schedules.id", ondelete="RESTRICT"))
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

    @property
    def funding_needed_cents(self):
        return self.amount_cents if self.charge_is_owed else 0


class SubscriptionChange(Base):
    """Append-only confirmations; no update/delete UI."""
    __tablename__ = "subscription_changes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    bill_id: Mapped[str] = mapped_column(String(36), ForeignKey("bill_occurrences.id", ondelete="RESTRICT"))
    before_json: Mapped[str] = mapped_column(Text)
    after_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class SubscriptionSchedule(Base):
    """Planning defaults; charges retain their own financial fields."""
    __tablename__ = "subscription_schedules"
    __table_args__ = (
        CheckConstraint("frequency IN ('monthly','yearly')", name="ck_schedule_frequency"),
        CheckConstraint("state IN ('active','inactive','covered')", name="ck_schedule_state"),
        CheckConstraint("amount_cents >= 0", name="ck_schedule_amount"),
        CheckConstraint("funding_buffer_days >= 0", name="ck_schedule_buffer"),
        CheckConstraint("length(trim(name)) > 0", name="ck_schedule_name"),
        CheckConstraint("(state = 'covered' AND (covered_by_bill_id IS NOT NULL OR length(trim(coalesce(coverage_label, ''))) > 0)) OR (state != 'covered' AND covered_by_bill_id IS NULL AND coverage_label IS NULL)", name="ck_schedule_coverage"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    frequency: Mapped[str] = mapped_column(String(16))
    anchor_date: Mapped[date] = mapped_column(Date)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    funding_buffer_days: Mapped[int] = mapped_column(Integer)
    payment_account_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("payment_accounts.id", ondelete="RESTRICT"))
    state: Mapped[str] = mapped_column(String(16), default="active")
    covered_by_bill_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("bill_occurrences.id", ondelete="RESTRICT", use_alter=True))
    coverage_label: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
