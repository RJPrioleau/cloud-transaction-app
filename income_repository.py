"""Create/read operations; the caller owns the transaction via session_scope."""
from datetime import date, datetime

from sqlalchemy import select

from income_models import IncomeSource, OfficialPayDate


def create_income_source(session, name):
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        raise ValueError("Income source name must contain 1–200 characters.")
    record = IncomeSource(name=name.strip())
    session.add(record)
    session.flush()
    return record


def list_income_sources(session):
    return list(session.scalars(select(IncomeSource).order_by(IncomeSource.name, IncomeSource.id)))


def create_official_pay_date(
    session, income_source_id, official_pay_date,
    pay_period_start=None, pay_period_end=None, source_reference=None,
):
    if not isinstance(income_source_id, str) or not income_source_id.strip():
        raise ValueError("An income source ID is required.")
    for value, required in ((official_pay_date, True), (pay_period_start, False), (pay_period_end, False)):
        if value is None and not required:
            continue
        if not isinstance(value, date) or isinstance(value, datetime):
            raise ValueError("Payday and pay-period values must be calendar dates.")
    if pay_period_start and pay_period_end and pay_period_start > pay_period_end:
        raise ValueError("Pay-period start must not follow its end.")
    if source_reference is not None:
        if not isinstance(source_reference, str) or len(source_reference.strip()) > 500:
            raise ValueError("Source reference must be text of at most 500 characters.")
        source_reference = source_reference.strip() or None
    record = OfficialPayDate(
        income_source_id=income_source_id,
        official_pay_date=official_pay_date,
        pay_period_start=pay_period_start,
        pay_period_end=pay_period_end,
        source_reference=source_reference,
    )
    session.add(record)
    session.flush()
    return record


def list_official_pay_dates(session, income_source_id):
    query = select(OfficialPayDate).where(OfficialPayDate.income_source_id == income_source_id)
    return list(session.scalars(query.order_by(OfficialPayDate.official_pay_date, OfficialPayDate.id)))

