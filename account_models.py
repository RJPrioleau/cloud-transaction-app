"""Named payment accounts, without balances or banking credentials."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class PaymentAccount(Base):
    __tablename__ = "payment_accounts"
    __table_args__ = (CheckConstraint("length(trim(name)) > 0", name="ck_accounts_name_not_blank"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
