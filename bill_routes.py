"""Manual entry of individual bill obligations; no payments or reservations."""
from datetime import date
import secrets

from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError

from bill_repository import create_bill, update_bill, list_bills, set_subscription_state
from bill_models import BillOccurrence, SubscriptionSchedule
from subscription_repository import configure_schedule
from sqlalchemy import select
from account_repository import list_accounts
from database import create_database_engine, session_scope
from income_repository import parse_net_cents, net_amount_text

bills = Blueprint("bills", __name__)


@bills.route("/bills", methods=["GET", "POST"])
@bills.route("/bills/<bill_id>/edit", methods=["GET", "POST"])
def index(bill_id=None):
    token = session.setdefault("bill_form_token", secrets.token_urlsafe(32))
    if request.method == "POST" and not secrets.compare_digest(token, request.form.get("token", "")):
        return "Form expired. Reopen Bills and try again.", 400
    error = None
    status = 200
    engine = create_database_engine(current_app.config.get("DATABASE_URL"))
    try:
        try:
            with session_scope(engine) as db:
                editing = db.get(BillOccurrence, bill_id) if bill_id else None
                if bill_id and editing is None:
                    abort(404)
                if request.method == "POST":
                    try:
                        due = date.fromisoformat(request.form.get("due_date", ""))
                    except ValueError:
                        raise ValueError("Enter a valid bill due date (YYYY-MM-DD).") from None
                    raw_buffer = request.form.get("funding_buffer_days", "").strip()
                    try:
                        buffer_days = int(raw_buffer) if raw_buffer else 3
                    except ValueError:
                        raise ValueError("Funding buffer must be a nonnegative whole number of calendar days.") from None
                    amount = parse_net_cents(request.form.get("amount", ""))
                    if amount is None:
                        raise ValueError("Bill amount is required.")
                    fields = dict(name=request.form.get("name", ""), amount_cents=amount,
                                  due_date=due, funding_buffer_days=buffer_days,
                                  kind=request.form.get("kind", "bill"),
                                  payment_account_id=request.form.get("payment_account_id", "") or None)
                    if editing:
                        update_bill(db, editing, **fields)
                    else:
                        created = create_bill(db, **fields)
                        recurrence = request.form.get("recurrence", "once")
                        if recurrence != "once":
                            configure_schedule(db, created, recurrence, amount, due, confirmed=True)
                else:
                    records = list_bills(db)
                    accounts = list_accounts(db)
                    schedules = list(db.scalars(select(SubscriptionSchedule).order_by(SubscriptionSchedule.name)))
                    representatives = {r.subscription_schedule_id: r.id for r in records if r.subscription_schedule_id}
            if request.method == "POST":
                return redirect(url_for("bills.index"), code=303)
        except ValueError as invalid:
            error, status = str(invalid), 400
            with session_scope(engine) as db:
                editing = db.get(BillOccurrence, bill_id) if bill_id else None
                records = list_bills(db)
                accounts = list_accounts(db)
                schedules = list(db.scalars(select(SubscriptionSchedule).order_by(SubscriptionSchedule.name)))
                representatives = {r.subscription_schedule_id: r.id for r in records if r.subscription_schedule_id}
        values = request.form
        if editing and request.method == "GET":
            values = dict(name=editing.name, amount=net_amount_text(editing.amount_cents),
                          due_date=editing.due_date.isoformat(), funding_buffer_days=str(editing.funding_buffer_days),
                          kind=editing.kind, payment_account_id=editing.payment_account_id or "")
        return render_template("bills.html", bills=records, token=token, error=error,
                               values=values, editing=editing, accounts=accounts,
                               covering_bills={r.id: r.name for r in records if r.kind == "bill"},
                               schedules=schedules, representatives=representatives,
                               net_amount_text=net_amount_text), status
    except SQLAlchemyError:
        current_app.logger.exception("Bill database unavailable")
        return render_template("bills.html", unavailable=True), 503
    finally:
        engine.dispose()


@bills.route("/bills/<bill_id>/subscription", methods=["GET", "POST"])
def subscription(bill_id):
    token_key = "subscription_token_" + bill_id
    if request.method == "GET":
        session[token_key] = secrets.token_urlsafe(32)
    token = session.get(token_key)
    if request.method == "POST" and (not token or not secrets.compare_digest(token, request.form.get("token", ""))):
        return "Form expired. Reopen Subscription settings and try again.", 400
    error, status = None, 200
    engine = create_database_engine(current_app.config.get("DATABASE_URL"))
    try:
        try:
            with session_scope(engine) as db:
                record = db.get(BillOccurrence, bill_id)
                if record is None or record.kind != "subscription":
                    abort(404)
                if record.subscription_schedule_id:
                    return redirect(url_for("bills.recurrence", bill_id=bill_id), code=303)
                parents = [r for r in list_bills(db) if r.kind == "bill"]
                if request.method == "POST":
                    state = request.form.get("state", "")
                    amount, due = None, None
                    if state == "active":
                        amount = parse_net_cents(request.form.get("amount", ""))
                        try:
                            due = date.fromisoformat(request.form.get("due_date", ""))
                        except ValueError:
                            raise ValueError("Confirm a valid next charge date.") from None
                    responsibility = request.form.get("charge_responsibility")
                    set_subscription_state(
                        db, record, state,
                        charge_is_owed={"owed": True, "not_owed": False}.get(responsibility),
                        covered_by_bill_id=request.form.get("covered_by_bill_id") or None,
                        confirm_no_charge=request.form.get("confirm_no_charge") == "yes",
                        amount_cents=amount, due_date=due,
                        confirm_activation=request.form.get("confirm_activation") == "yes",
                        coverage_label=request.form.get("coverage_label"),
                    )
            if request.method == "POST":
                session.pop(token_key, None)
                return redirect(url_for("bills.index"), code=303)
        except ValueError as invalid:
            error, status = str(invalid), 400
            with session_scope(engine) as db:
                record = db.get(BillOccurrence, bill_id)
                parents = [r for r in list_bills(db) if r.kind == "bill"]
        values = request.form if request.method == "POST" else dict(
            state=record.subscription_state, charge_responsibility="owed" if record.charge_is_owed else "not_owed",
            covered_by_bill_id=record.covered_by_bill_id or "", amount=net_amount_text(record.amount_cents),
            due_date=record.due_date.isoformat(), coverage_label=record.coverage_label or "")
        return render_template("subscription_settings.html", record=record, parents=parents,
                               values=values, token=token, error=error), status
    except SQLAlchemyError:
        current_app.logger.exception("Subscription settings unavailable")
        return render_template("bills.html", unavailable=True), 503
    finally:
        engine.dispose()


@bills.route("/bills/<bill_id>/recurrence", methods=["GET", "POST"])
def recurrence(bill_id):
    token = session.setdefault("recurrence_form_token", secrets.token_urlsafe(32))
    if request.method == "POST" and not secrets.compare_digest(token, request.form.get("token", "")):
        return "Form expired. Reopen recurrence settings.", 400
    engine = create_database_engine(current_app.config.get("DATABASE_URL"))
    error, status = None, 200
    try:
        try:
            with session_scope(engine) as db:
                record = db.get(BillOccurrence, bill_id)
                if record is None or record.kind != "subscription":
                    abort(404)
                saved = db.get(SubscriptionSchedule, record.subscription_schedule_id) if record.subscription_schedule_id else None
                if request.method == "POST":
                    try:
                        anchor = date.fromisoformat(request.form.get("anchor_date", ""))
                    except ValueError:
                        raise ValueError("Enter a valid first or next charge date.") from None
                    try:
                        buffer_days = int(request.form.get("funding_buffer_days", "3"))
                    except ValueError:
                        raise ValueError("Funding buffer must be a nonnegative whole number.") from None
                    configure_schedule(db, record, request.form.get("frequency"),
                                       parse_net_cents(request.form.get("amount", "")), anchor,
                                       state=request.form.get("state", "active"),
                                       coverage_label=request.form.get("coverage_label"),
                                       covered_by_bill_id=request.form.get("covered_by_bill_id") or None,
                                       confirmed=request.form.get("confirm") == "yes",
                                       name=request.form.get("name", saved.name if saved else record.name),
                                       funding_buffer_days=buffer_days,
                                       payment_account_id=request.form.get("payment_account_id", saved.payment_account_id if saved else record.payment_account_id) or None)
            if request.method == "POST":
                session.pop("recurrence_form_token", None)
                return redirect(url_for("bills.index"), code=303)
        except ValueError as invalid:
            error, status = str(invalid), 400
        with session_scope(engine) as db:
            record = db.get(BillOccurrence, bill_id)
            saved = db.get(SubscriptionSchedule, record.subscription_schedule_id) if record.subscription_schedule_id else None
            parents = [r for r in list_bills(db) if r.kind == "bill"]
            accounts = list_accounts(db)
        values = request.form if request.method == "POST" else dict(
            frequency=saved.frequency if saved else "monthly", state=saved.state if saved else record.subscription_state,
            amount=net_amount_text(saved.amount_cents if saved else record.amount_cents),
            anchor_date=(saved.anchor_date if saved else record.due_date).isoformat(),
            coverage_label=(saved.coverage_label if saved else record.coverage_label) or "",
            covered_by_bill_id=(saved.covered_by_bill_id if saved else record.covered_by_bill_id) or "",
            name=saved.name if saved else record.name,
            funding_buffer_days=str(saved.funding_buffer_days if saved else record.funding_buffer_days),
            payment_account_id=(saved.payment_account_id if saved else record.payment_account_id) or "")
        return render_template("subscription_recurrence.html", record=record, saved=saved, parents=parents,
                               values=values, token=token, error=error, accounts=accounts), status
    except SQLAlchemyError:
        current_app.logger.exception("Subscription recurrence unavailable")
        return render_template("bills.html", unavailable=True), 503
    finally:
        engine.dispose()
