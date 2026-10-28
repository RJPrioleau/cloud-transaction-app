"""Bill planning operations; caller owns the database transaction."""
from datetime import date, datetime

from sqlalchemy import select

from bill_models import BillOccurrence
from account_models import PaymentAccount


def validate_bill(session, name, amount_cents, due_date, funding_buffer_days, kind, payment_account_id):
    if kind not in ("bill", "subscription"):
        raise ValueError("Choose Bill or Subscription.")
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
    if payment_account_id is not None and session.get(PaymentAccount, payment_account_id) is None:
        raise ValueError("Choose an existing payment account, or leave it unassigned.")


def create_bill(session, name, amount_cents, due_date, funding_buffer_days=3, kind="bill", payment_account_id=None):
    validate_bill(session, name, amount_cents, due_date, funding_buffer_days, kind, payment_account_id)
    bill = BillOccurrence(name=name.strip(), amount_cents=amount_cents, due_date=due_date,
                          funding_buffer_days=funding_buffer_days, kind=kind, payment_account_id=payment_account_id)
    session.add(bill)
    session.flush()
    return bill


def update_bill(session, bill, name, amount_cents, due_date, funding_buffer_days=3, kind="bill", payment_account_id=None):
    validate_bill(session, name, amount_cents, due_date, funding_buffer_days, kind, payment_account_id)
    bill.name, bill.amount_cents, bill.due_date = name.strip(), amount_cents, due_date
    bill.funding_buffer_days, bill.kind = funding_buffer_days, kind
    bill.payment_account_id = payment_account_id
    session.flush()
    return bill


def list_bills(session):
    return sorted(session.scalars(select(BillOccurrence)),
                  key=lambda bill: (bill.funding_deadline, bill.due_date, bill.name, bill.id))
