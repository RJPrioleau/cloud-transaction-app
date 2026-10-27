"""Draft calendar interface; database access is limited to calendar requests."""
from datetime import date
import secrets

from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError

from database import create_database_engine, session_scope
from income_models import IncomeSource
from income_repository import (
    create_income_source, create_official_pay_date,
    list_income_sources, list_official_pay_dates,
)

income = Blueprint("income", __name__)


def calendar_date(field, required=False):
    value = request.form.get(field, "").strip()
    if not value and not required:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Enter a valid calendar date (YYYY-MM-DD).") from None


@income.route("/income", methods=["GET", "POST"])
@income.route("/income/<source_id>", methods=["GET", "POST"])
def calendar(source_id=None):
    token = session.setdefault("income_form_token", secrets.token_urlsafe(32))
    error = None
    status = 200
    if request.method == "POST" and not secrets.compare_digest(
        token, request.form.get("token", "")
    ):
        return "Form expired. Reopen the income calendar and try again.", 400

    engine = create_database_engine(current_app.config.get("DATABASE_URL"))
    try:
        try:
            with session_scope(engine) as db:
                source = db.get(IncomeSource, source_id) if source_id else None
                if source_id and source is None:
                    abort(404)
                if request.method == "POST":
                    if source is None:
                        created = create_income_source(db, request.form.get("name", ""))
                        destination = created.id
                    else:
                        create_official_pay_date(
                            db, source.id, calendar_date("official_pay_date", required=True),
                            calendar_date("pay_period_start"), calendar_date("pay_period_end"),
                            request.form.get("source_reference"),
                        )
                        destination = source.id
                else:
                    sources = list_income_sources(db)
                    dates = list_official_pay_dates(db, source_id) if source else []
            if request.method == "POST":
                return redirect(url_for("income.calendar", source_id=destination), code=303)
        except ValueError as invalid:
            error, status = str(invalid), 400
            with session_scope(engine) as db:
                source = db.get(IncomeSource, source_id) if source_id else None
                sources = list_income_sources(db)
                dates = list_official_pay_dates(db, source_id) if source else []
        return render_template(
            "income_calendar.html", sources=sources, source=source, dates=dates,
            token=token, error=error, values=request.form,
        ), status
    except SQLAlchemyError:
        current_app.logger.exception("Income calendar database unavailable")
        return render_template("income_calendar.html", unavailable=True), 503
    finally:
        engine.dispose()
