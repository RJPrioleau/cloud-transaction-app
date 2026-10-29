"""Recurring planning defaults and distinct, idempotent charge occurrences."""
from datetime import date, timedelta
import json

from sqlalchemy import select

from bill_models import BillOccurrence, SubscriptionChange, SubscriptionSchedule
from bill_repository import create_bill, validate_bill
from recurring_dates import scheduled_dates
from monthly_bill_repository import materialize_monthly_bills

_UNSET = object()


def schedule_snapshot(schedule):
    return {key: (value.isoformat() if isinstance(value, date) else value)
            for key in ("id", "name", "frequency", "anchor_date", "amount_cents",
                        "funding_buffer_days", "payment_account_id", "state",
                        "covered_by_bill_id", "coverage_label")
            for value in [getattr(schedule, key)]}


def configure_schedule(session, bill, frequency, amount_cents, anchor_date, state="active",
                       coverage_label=None, covered_by_bill_id=None, confirmed=False, today=None,
                       name=None, funding_buffer_days=None, payment_account_id=_UNSET):
    """Opt in explicitly; alter only occurrences dated after today's boundary."""
    today = today or date.today()
    if bill.kind != "subscription":
        raise ValueError("Recurrence applies only to subscriptions.")
    if frequency not in ("monthly", "yearly"):
        raise ValueError("Choose Monthly or Yearly recurrence.")
    if state not in ("active", "inactive", "covered"):
        raise ValueError("Choose Active, Inactive, or Covered.")
    if not confirmed:
        raise ValueError("Confirm the schedule, amount, and future funding changes.")
    saved = session.get(SubscriptionSchedule, bill.subscription_schedule_id) if bill.subscription_schedule_id else None
    defaults = saved or bill
    name = defaults.name if name is None else name
    funding_buffer_days = defaults.funding_buffer_days if funding_buffer_days is None else funding_buffer_days
    payment_account_id = defaults.payment_account_id if payment_account_id is _UNSET else payment_account_id
    validate_bill(session, name, amount_cents, anchor_date, funding_buffer_days,
                  "subscription", payment_account_id)
    coverage_label = (coverage_label or "").strip() or None
    if coverage_label and len(coverage_label) > 200:
        raise ValueError("Coverage label must contain at most 200 characters.")
    if state == "covered":
        parent = session.get(BillOccurrence, covered_by_bill_id) if covered_by_bill_id else None
        if covered_by_bill_id and (parent is None or parent.kind != "bill" or parent.id == bill.id):
            raise ValueError("Choose an existing regular bill for coverage.")
        if not parent and not coverage_label:
            raise ValueError("Enter who or what covers this subscription, or choose a covering bill.")
    else:
        covered_by_bill_id, coverage_label = None, None
    schedule = saved
    before = schedule_snapshot(schedule) if schedule else None
    if schedule is None:
        schedule = SubscriptionSchedule()
        session.add(schedule)
    schedule.name, schedule.frequency, schedule.anchor_date = name.strip(), frequency, anchor_date
    schedule.amount_cents, schedule.funding_buffer_days = amount_cents, funding_buffer_days
    schedule.payment_account_id = payment_account_id
    schedule.state, schedule.covered_by_bill_id, schedule.coverage_label = state, covered_by_bill_id, coverage_label
    session.flush()
    bill.subscription_schedule_id = schedule.id
    session.flush()
    # Future rows are retained, including dates no longer on the edited schedule,
    # but only dates on the new active schedule can require funding.
    for charge in session.scalars(select(BillOccurrence).where(
            BillOccurrence.subscription_schedule_id == schedule.id, BillOccurrence.due_date > today)):
        valid_date = next(scheduled_dates(anchor_date, frequency, charge.due_date,
                                         charge.due_date + timedelta(days=1)), None)
        charge.amount_cents = amount_cents
        charge.name, charge.funding_buffer_days, charge.payment_account_id = schedule.name, funding_buffer_days, payment_account_id
        charge.subscription_state = state if valid_date else "inactive"
        charge.charge_is_owed = state == "active" and valid_date is not None
        charge.covered_by_bill_id = covered_by_bill_id if charge.subscription_state == "covered" else None
        charge.coverage_label = coverage_label if charge.subscription_state == "covered" else None
    session.add(SubscriptionChange(bill_id=bill.id, before_json=json.dumps({"schedule": before}),
                                   after_json=json.dumps({"schedule": schedule_snapshot(schedule)})))
    session.flush()
    return schedule


def materialize_subscriptions(session, start, days):
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError("Choose a whole number of days from 1 to 365.")
    end = start + timedelta(days=days)
    for schedule in session.scalars(select(SubscriptionSchedule).where(SubscriptionSchedule.state == "active")):
        existing = {row.due_date for row in session.scalars(select(BillOccurrence).where(
            BillOccurrence.subscription_schedule_id == schedule.id))}
        for due in scheduled_dates(schedule.anchor_date, schedule.frequency, start, end):
            if due not in existing:
                charge = create_bill(session, schedule.name, schedule.amount_cents, due,
                                     schedule.funding_buffer_days, "subscription", schedule.payment_account_id)
                charge.subscription_schedule_id = schedule.id
                session.flush()


def outgoing_forecast(session, start, days):
    """Persist missing active charges, then total only owed amounts in the window."""
    materialize_subscriptions(session, start, days)
    materialize_monthly_bills(session, start, days)
    rows = list(session.scalars(select(BillOccurrence).where(
        BillOccurrence.due_date >= start, BillOccurrence.due_date < start + timedelta(days=days)
    ).order_by(BillOccurrence.due_date, BillOccurrence.name, BillOccurrence.id)))
    schedules = list(session.scalars(select(SubscriptionSchedule).order_by(SubscriptionSchedule.name, SubscriptionSchedule.id)))
    covering_bills = {bill.id: bill.name for bill in session.scalars(
        select(BillOccurrence).where(BillOccurrence.kind == "bill"))}
    return {"rows": rows, "total": sum(row.funding_needed_cents for row in rows),
            "schedules": schedules, "covering_bills": covering_bills}
