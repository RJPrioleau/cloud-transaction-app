"""Monthly bill estimates use only explicitly confirmed calendar-month history."""
import calendar
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from bill_models import BillOccurrence, BillSchedule
from bill_repository import create_bill, validate_bill
from recurring_dates import scheduled_dates


def month_start(day):
    return day.replace(day=1)


def estimate_amount(session, schedule, target_month):
    target_month = month_start(target_month)
    ordinal = (target_month.year - 1) * 12 + target_month.month - 1
    year, month = divmod(max(0, ordinal - 3), 12)
    lower = date(year + 1, month + 1, 1)
    amounts = list(session.scalars(select(BillOccurrence.amount_cents).where(
        BillOccurrence.bill_schedule_id == schedule.id,
        BillOccurrence.bill_month >= lower, BillOccurrence.bill_month < target_month,
        BillOccurrence.amount_confirmed_at.is_not(None))))
    if not amounts:
        return schedule.starting_estimate_cents, "starting"
    # All values are nonnegative integer cents. Round a half-cent upward.
    count = len(amounts)
    return (2 * sum(amounts) + count) // (2 * count), f"history_{count}"


def amount_basis_text(charge):
    if charge.amount_confirmed_at:
        return "Confirmed amount (not payment status)"
    if charge.amount_basis == "starting":
        return "Estimated — starting estimate"
    if charge.amount_basis and charge.amount_basis.startswith("history_"):
        count = int(charge.amount_basis[-1])
        return ("Estimated — three-month average" if count == 3 else
                f"Estimated — available history ({count} of previous 3 months)")
    return "Unconfirmed amount" if charge.kind == "bill" else "Scheduled amount"


def refresh_estimates(session, schedule, today=None):
    today = today or date.today()
    session.flush()
    for charge in session.scalars(select(BillOccurrence).where(
            BillOccurrence.bill_schedule_id == schedule.id,
            BillOccurrence.due_date > today, BillOccurrence.amount_confirmed_at.is_(None))):
        charge.amount_cents, charge.amount_basis = estimate_amount(session, schedule, charge.bill_month)
    session.flush()


def enable_monthly_bill(session, bill, starting_estimate_cents, confirmed=False, today=None):
    if bill.kind != "bill" or bill.subscription_schedule_id:
        raise ValueError("Monthly bill recurrence applies only to regular Bills.")
    if bill.bill_schedule_id:
        raise ValueError("This bill already has a monthly schedule. Use its monthly history.")
    if not confirmed:
        raise ValueError("Confirm the monthly schedule and starting estimate.")
    validate_bill(session, bill.name, starting_estimate_cents, bill.due_date,
                  bill.funding_buffer_days, "bill", bill.payment_account_id)
    schedule = BillSchedule(name=bill.name, anchor_date=bill.due_date,
                            starting_estimate_cents=starting_estimate_cents,
                            funding_buffer_days=bill.funding_buffer_days,
                            payment_account_id=bill.payment_account_id)
    session.add(schedule)
    session.flush()
    bill.bill_schedule_id, bill.bill_month = schedule.id, month_start(bill.due_date)
    # Enrollment is not confirmation of the existing charge's amount.
    refresh_estimates(session, schedule, today)
    return schedule


def materialize_monthly_bills(session, start, days):
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError("Choose a whole number of days from 1 to 365.")
    end = start + timedelta(days=days)
    for schedule in session.scalars(select(BillSchedule)):
        existing = {r.bill_month for r in session.scalars(select(BillOccurrence).where(
            BillOccurrence.bill_schedule_id == schedule.id))}
        for due in scheduled_dates(schedule.anchor_date, "monthly", start, end):
            month = month_start(due)
            if month in existing:
                continue
            amount, basis = estimate_amount(session, schedule, month)
            charge = create_bill(session, schedule.name, amount, due,
                                 schedule.funding_buffer_days, "bill", schedule.payment_account_id)
            charge.bill_schedule_id, charge.bill_month, charge.amount_basis = schedule.id, month, basis
            session.flush()


def confirm_month_amount(session, schedule, month, amount_cents, confirmed=False,
                         existing_bill_id=None, today=None):
    if not isinstance(month, date) or isinstance(month, datetime) or month.day != 1:
        raise ValueError("Choose a valid billing month (YYYY-MM).")
    if not confirmed:
        raise ValueError("Confirm that this month's amount is accurate; this does not mark it paid.")
    due = date(month.year, month.month, min(schedule.anchor_date.day, calendar.monthrange(month.year, month.month)[1]))
    validate_bill(session, schedule.name, amount_cents, due, schedule.funding_buffer_days,
                  "bill", schedule.payment_account_id)
    charge = session.scalar(select(BillOccurrence).where(
        BillOccurrence.bill_schedule_id == schedule.id, BillOccurrence.bill_month == month))
    if existing_bill_id:
        existing = session.get(BillOccurrence, existing_bill_id)
        if (existing is None or existing.kind != "bill" or existing.subscription_schedule_id
                or (existing.bill_schedule_id and existing.bill_schedule_id != schedule.id)
                or month_start(existing.due_date) != month):
            raise ValueError("Choose an unlinked regular Bill from the selected month.")
        if charge is not None and charge.id != existing.id:
            raise ValueError("This month already has a charge. Confirm that charge instead; no records were merged.")
        charge = existing
    if charge is None:
        charge = create_bill(session, schedule.name, amount_cents, due,
                             schedule.funding_buffer_days, "bill", schedule.payment_account_id)
    charge.bill_schedule_id, charge.bill_month = schedule.id, month
    charge.amount_cents, charge.amount_basis = amount_cents, "confirmed"
    charge.amount_confirmed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.flush()
    refresh_estimates(session, schedule, today)
    return charge
