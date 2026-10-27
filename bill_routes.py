"""Manual entry of individual bill obligations; no payments or reservations."""
from datetime import date
import secrets

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError

from bill_repository import create_bill, list_bills
from database import create_database_engine, session_scope
from income_repository import parse_net_cents, net_amount_text

bills = Blueprint("bills", __name__)


@bills.route("/bills", methods=["GET", "POST"])
def index():
    token = session.setdefault("bill_form_token", secrets.token_urlsafe(32))
    if request.method == "POST" and not secrets.compare_digest(token, request.form.get("token", "")):
        return "Form expired. Reopen Bills and try again.", 400
    error = None
    status = 200
    engine = create_database_engine(current_app.config.get("DATABASE_URL"))
    try:
        try:
            with session_scope(engine) as db:
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
                    create_bill(db, request.form.get("name", ""), amount, due, buffer_days,
                                kind=request.form.get("kind", "bill"))
                else:
                    records = list_bills(db)
            if request.method == "POST":
                return redirect(url_for("bills.index"), code=303)
        except ValueError as invalid:
            error, status = str(invalid), 400
            with session_scope(engine) as db:
                records = list_bills(db)
        return render_template("bills.html", bills=records, token=token, error=error,
                               values=request.form, net_amount_text=net_amount_text), status
    except SQLAlchemyError:
        current_app.logger.exception("Bill database unavailable")
        return render_template("bills.html", unavailable=True), 503
    finally:
        engine.dispose()
