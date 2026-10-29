"""Manual account/vault setup and balance history; no bank connection."""
from datetime import date
import secrets
from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError
from account_models import PaymentAccount
from account_repository import (create_account, rename_account, list_accounts, update_account,
                                record_balance, balance_history, latest_balances)
from database import create_database_engine, session_scope
from income_repository import parse_net_cents, net_amount_text

accounts = Blueprint("accounts", __name__)


@accounts.route("/accounts", methods=["GET", "POST"])
@accounts.route("/accounts/<account_id>/rename", methods=["POST"])
def index(account_id=None):
    token = session.setdefault("account_form_token", secrets.token_urlsafe(32))
    if request.method == "POST" and not secrets.compare_digest(token, request.form.get("token", "")):
        return "Form expired. Reopen Payment accounts and try again.", 400
    engine = create_database_engine(current_app.config.get("DATABASE_URL"))
    error, status = None, 200
    try:
        try:
            with session_scope(engine) as db:
                if request.method == "POST":
                    if account_id:
                        account = db.get(PaymentAccount, account_id)
                        if account is None:
                            abort(404)
                        rename_account(db, account, request.form.get("name", ""))
                    else:
                        created = create_account(db, request.form.get("name", ""),
                                                 request.form.get("kind", "account"), request.form.get("purpose"))
                        amount = parse_net_cents(request.form.get("balance", ""))
                        if amount is not None:
                            save_balance_form(db, created, amount)
                else:
                    records = list_accounts(db)
                    balances = latest_balances(db)
            if request.method == "POST":
                session.pop("account_form_token", None)
                return redirect(url_for("accounts.index"), code=303)
        except ValueError as invalid:
            error, status = str(invalid), 400
            with session_scope(engine) as db:
                records = list_accounts(db)
                balances = latest_balances(db)
        return render_template("accounts.html", accounts=records, token=token, error=error,
                               values=request.form, renaming=account_id, balances=balances,
                               today=date.today().isoformat(), net_amount_text=net_amount_text), status
    except SQLAlchemyError:
        current_app.logger.exception("Payment accounts unavailable")
        return render_template("accounts.html", unavailable=True), 503
    finally:
        engine.dispose()


def save_balance_form(db, account, amount):
    if request.form.get("confirm_balance") != "yes":
        raise ValueError("Confirm that the balance is the amount held in this account or vault on that date.")
    try:
        as_of = date.fromisoformat(request.form.get("balance_date", ""))
    except ValueError:
        raise ValueError("Enter a valid balance date (YYYY-MM-DD).") from None
    record_balance(db, account, amount, as_of, request.form.get("note"))


@accounts.route("/accounts/<account_id>", methods=["GET", "POST"])
def detail(account_id):
    token_key = "account_detail_token_" + account_id
    token = session.setdefault(token_key, secrets.token_urlsafe(32))
    if request.method == "POST" and not secrets.compare_digest(token, request.form.get("token", "")):
        return "Form expired. Reopen this account or vault.", 400
    engine = create_database_engine(current_app.config.get("DATABASE_URL"))
    error, status = None, 200
    try:
        try:
            with session_scope(engine) as db:
                account = db.get(PaymentAccount, account_id)
                if account is None:
                    abort(404)
                if request.method == "POST":
                    action = request.form.get("action")
                    if action == "details":
                        update_account(db, account, request.form.get("name", ""),
                                       request.form.get("kind", "account"), request.form.get("purpose"))
                    elif action == "balance":
                        amount = parse_net_cents(request.form.get("balance", ""))
                        if amount is None:
                            raise ValueError("Enter the recorded balance; zero is allowed.")
                        save_balance_form(db, account, amount)
                    else:
                        raise ValueError("Choose Save details or Record balance.")
            if request.method == "POST":
                session.pop(token_key, None)
                return redirect(url_for("accounts.detail", account_id=account_id), code=303)
        except ValueError as invalid:
            error, status = str(invalid), 400
        with session_scope(engine) as db:
            account = db.get(PaymentAccount, account_id)
            history = balance_history(db, account_id)
        values = request.form if request.method == "POST" else {}
        return render_template("account_detail.html", account=account, history=history, values=values,
                               token=token, error=error, today=date.today().isoformat(),
                               net_amount_text=net_amount_text), status
    except SQLAlchemyError:
        current_app.logger.exception("Account balance history unavailable")
        return render_template("accounts.html", unavailable=True), 503
    finally:
        engine.dispose()
