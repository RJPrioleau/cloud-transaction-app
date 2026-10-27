"""Bill planning operations; caller owns the database transaction."""
from datetime import date, datetime

from sqlalchemy import select

from bill_models import BillOccurrence


def create_bill(session, name, amount_cents, due_date, funding_buffer_days=3):
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        raise ValueError("Bill name must contain 1–200 characters.")
    if type(amount_cents) is not int or not 0 <= amount_cents <= 9223372036854775807:
        raise ValueError("Enter a nonnegative bill amount in whole cents.")
    if not isinstance(due_date, date) or isinstance(due_date, datetime):
        raise ValueError("Enter a valid bill due date.")
    if type(funding_buffer_days) is not int or funding_buffer_days < 0:
        raise ValueError("Funding buffer must be a nonnegative whole number of calendar days.")
    if funding_buffer_days >= due_date.toordinal():
        raise ValueError("Funding buffer places the deadline before the supported calendar.")
    bill = BillOccurrence(name=name.strip(), amount_cents=amount_cents, due_date=due_date,
                          funding_buffer_days=funding_buffer_days)
    session.add(bill)
    session.flush()
    return bill


def list_bills(session):
    return sorted(session.scalars(select(BillOccurrence)),
                  key=lambda bill: (bill.funding_deadline, bill.due_date, bill.name, bill.id))
