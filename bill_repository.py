"""Bill planning operations; caller owns the database transaction."""
from datetime import date, datetime
import json

from sqlalchemy import select

from bill_models import BillOccurrence, SubscriptionChange, SubscriptionSchedule
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
    if bill.subscription_schedule_id:
        raise ValueError("Use Recurrence settings to change this subscription's future planning. Existing charge records are preserved.")
    validate_bill(session, name, amount_cents, due_date, funding_buffer_days, kind, payment_account_id)
    if kind != bill.kind:
        if bill.subscription_state != "active":
            raise ValueError("Reactivate this subscription before changing it to a bill.")
        if session.scalar(select(BillOccurrence.id).where(BillOccurrence.covered_by_bill_id == bill.id).limit(1)):
            raise ValueError("This bill covers a subscription. Remove that coverage link before changing its type.")
        if session.scalar(select(SubscriptionSchedule.id).where(SubscriptionSchedule.covered_by_bill_id == bill.id).limit(1)):
            raise ValueError("This bill covers a subscription schedule. Remove that coverage link before changing its type.")
    bill.name, bill.amount_cents, bill.due_date = name.strip(), amount_cents, due_date
    bill.funding_buffer_days, bill.kind = funding_buffer_days, kind
    bill.payment_account_id = payment_account_id
    session.flush()
    return bill


def list_bills(session):
    return sorted(session.scalars(select(BillOccurrence)),
                  key=lambda bill: (not bill.charge_is_owed, bill.funding_deadline, bill.due_date, bill.name, bill.id))


def subscription_snapshot(bill):
    return dict(id=bill.id, state=bill.subscription_state, charge_is_owed=bill.charge_is_owed,
                covered_by_bill_id=bill.covered_by_bill_id, amount_cents=bill.amount_cents,
                due_date=bill.due_date.isoformat(), coverage_label=bill.coverage_label)


def set_subscription_state(session, bill, state, charge_is_owed=None, covered_by_bill_id=None,
                           confirm_no_charge=False, amount_cents=None, due_date=None, confirm_activation=False,
                           coverage_label=None):
    if bill.subscription_schedule_id:
        raise ValueError("Use Recurrence settings for this subscription.")
    if bill.kind != "subscription":
        raise ValueError("Subscription settings apply only to subscriptions.")
    if state not in ("active", "inactive", "covered"):
        raise ValueError("Choose Active, Inactive, or Covered by another bill.")
    before = subscription_snapshot(bill)
    coverage_label = (coverage_label or "").strip() or None
    if coverage_label and len(coverage_label) > 200:
        raise ValueError("Coverage label must contain at most 200 characters.")
    result = bill
    if state == "active":
        if not confirm_activation:
            raise ValueError("Confirm the amount and next charge date to activate this subscription.")
        validate_bill(session, bill.name, amount_cents, due_date, bill.funding_buffer_days,
                      "subscription", bill.payment_account_id)
        if bill.subscription_state != "active" and bill.charge_is_owed:
            if due_date <= bill.due_date:
                raise ValueError("An unpaid charge remains. The new charge date must follow it.")
            for change in session.scalars(select(SubscriptionChange).where(SubscriptionChange.bill_id == bill.id)):
                prior = json.loads(change.after_json)
                if prior.get("retained_unpaid_occurrence_id") == bill.id and prior.get("due_date") == due_date.isoformat():
                    raise ValueError("That next charge was already created. Edit its active occurrence instead.")
            # Preserve the real outstanding occurrence; the newly confirmed charge is distinct.
            result = create_bill(session, bill.name, amount_cents, due_date, bill.funding_buffer_days,
                                 kind="subscription", payment_account_id=bill.payment_account_id)
            result.subscription_state, result.charge_is_owed = "active", True
        else:
            bill.amount_cents, bill.due_date = amount_cents, due_date
            bill.subscription_state, bill.charge_is_owed, bill.covered_by_bill_id = "active", True, None
            bill.coverage_label = None
    else:
        if type(charge_is_owed) is not bool:
            raise ValueError("Specify whether the recorded charge is actually owed.")
        if not charge_is_owed and not confirm_no_charge:
            raise ValueError("Confirm that this is a placeholder or included charge with no separate amount owed.")
        if state == "covered":
            parent = session.get(BillOccurrence, covered_by_bill_id) if covered_by_bill_id else None
            if (covered_by_bill_id and (parent is None or parent.id == bill.id or parent.kind != "bill")) or (parent is None and not coverage_label):
                raise ValueError("Choose an existing bill that covers this subscription.")
        else:
            covered_by_bill_id = None
            coverage_label = None
        bill.subscription_state, bill.charge_is_owed = state, charge_is_owed
        bill.covered_by_bill_id = covered_by_bill_id
        bill.coverage_label = coverage_label
    session.flush()
    after = subscription_snapshot(result)
    if result.id != bill.id:
        after["retained_unpaid_occurrence_id"] = bill.id
    session.add(SubscriptionChange(bill_id=bill.id, before_json=json.dumps(before), after_json=json.dumps(after)))
    session.flush()
    return result
