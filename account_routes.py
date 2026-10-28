"""Create and rename payment account labels; no balances or bank connection."""
import secrets
from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError
from account_models import PaymentAccount
from account_repository import create_account, rename_account, list_accounts
from database import create_database_engine, session_scope

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
                        create_account(db, request.form.get("name", ""))
                else:
                    records = list_accounts(db)
            if request.method == "POST":
                return redirect(url_for("accounts.index"), code=303)
        except ValueError as invalid:
            error, status = str(invalid), 400
            with session_scope(engine) as db:
                records = list_accounts(db)
        return render_template("accounts.html", accounts=records, token=token, error=error,
                               values=request.form, renaming=account_id), status
    except SQLAlchemyError:
        current_app.logger.exception("Payment accounts unavailable")
        return render_template("accounts.html", unavailable=True), 503
    finally:
        engine.dispose()
