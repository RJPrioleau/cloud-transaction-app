"""Create/read operations; the caller owns the transaction via session_scope."""
from datetime import date, datetime, timedelta
from decimal import Decimal
import re

from sqlalchemy import select

from income_models import IncomeSource, OfficialPayDate


def parse_net_cents(value):
    """Blank means unknown/inherit; zero is an explicit zero estimate."""
    value = value.strip()
    if not value:
        return None
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value) or len(value) > 22:
        raise ValueError("Enter a nonnegative dollar amount with at most two decimal places, without commas.")
    cents = int(Decimal(value) * 100)
    if cents > 9223372036854775807:
        raise ValueError("Expected pay amount is too large.")
    return cents


def net_amount_text(cents):
    return "" if cents is None else f"{cents // 100}.{cents % 100:02d}"


def expected_net_cents(source, payday):
    return (payday.expected_net_override_cents if payday.expected_net_override_cents is not None
            else source.expected_net_cents)


def income_forecast(session, start):
    """Project saved occurrences for today plus the following 89 calendar days."""
    end = start + timedelta(days=90)
    query = (
        select(IncomeSource, OfficialPayDate)
        .join(OfficialPayDate, OfficialPayDate.income_source_id == IncomeSource.id)
        .where(OfficialPayDate.official_pay_date >= start, OfficialPayDate.official_pay_date < end)
        .order_by(OfficialPayDate.official_pay_date, IncomeSource.name, OfficialPayDate.id)
    )
    rows = []
    total = 0
    unknown = 0
    for source, payday in session.execute(query):
        amount = expected_net_cents(source, payday)
        rows.append({"source_id": source.id, "source_name": source.name,
                     "date": payday.official_pay_date, "amount": amount,
                     "override": payday.expected_net_override_cents is not None})
        if amount is None:
            unknown += 1
        else:
            total += amount
    return {"start": start, "last_day": end - timedelta(days=1), "rows": rows,
            "total": total, "unknown": unknown}


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
