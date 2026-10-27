"""Income-calendar projections; these records never represent actual deposits."""
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def new_id():
    return str(uuid4())


def utc_timestamp():
    # Store UTC consistently; SQLite does not preserve timezone offsets.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class IncomeSource(Base):
    __tablename__ = "income_sources"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_income_sources_name_not_blank"),
        CheckConstraint("expected_net_cents >= 0", name="ck_income_sources_expected_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_timestamp)
    expected_net_cents: Mapped[int | None] = mapped_column(BigInteger)


class OfficialPayDate(Base):
    __tablename__ = "official_pay_dates"
    __table_args__ = (
        CheckConstraint(
            "pay_period_start IS NULL OR pay_period_end IS NULL OR pay_period_start <= pay_period_end",
            name="ck_official_pay_dates_period_order",
        ),
        CheckConstraint("review_status = 'draft'", name="ck_official_pay_dates_draft_only"),
        CheckConstraint("expected_net_override_cents >= 0", name="ck_pay_dates_expected_nonnegative"),
        Index("ix_official_pay_dates_source_date", "income_source_id", "official_pay_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    income_source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("income_sources.id", ondelete="RESTRICT"), nullable=False
    )
    official_pay_date: Mapped[date] = mapped_column(Date)
    pay_period_start: Mapped[date | None] = mapped_column(Date)
    pay_period_end: Mapped[date | None] = mapped_column(Date)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    expected_net_override_cents: Mapped[int | None] = mapped_column(BigInteger)
    review_status: Mapped[str] = mapped_column(String(16), default="draft", server_default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_timestamp)
