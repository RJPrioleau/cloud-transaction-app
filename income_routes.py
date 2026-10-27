"""Draft calendar interface; database access is limited to calendar requests."""
from datetime import date
import calendar as year_calendar
import secrets

from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError

from database import create_database_engine, session_scope
from income_models import IncomeSource, OfficialPayDate
from income_repository import (
    create_income_source, create_official_pay_date,
    list_income_sources, list_official_pay_dates,
    parse_net_cents, net_amount_text, expected_net_cents,
    income_forecast,
)

income = Blueprint("income", __name__)


@income.route("/income/forecast", methods=["GET", "POST"])
def forecast():
    # Reserve the static path so POST cannot match /income/<source_id>.
    if request.method == "POST":
        abort(405)
    raw_days = request.args.get("days", "90")
    try:
        days = int(raw_days)
        if not 1 <= days <= 365:
            raise ValueError
    except ValueError:
        return render_template(
            "income_forecast.html", projection=None, days=raw_days,
            error="Choose a whole number of days from 1 to 365.",
        ), 400
    engine = create_database_engine(current_app.config.get("DATABASE_URL"))
    try:
        with session_scope(engine) as db:
            projection = income_forecast(db, date.today(), days)
        return render_template("income_forecast.html", projection=projection, days=days, net_amount_text=net_amount_text)
    except SQLAlchemyError:
        current_app.logger.exception("Income forecast database unavailable")
        return render_template("income_calendar.html", unavailable=True), 503
    finally:
        engine.dispose()


@income.route("/income/<source_id>/paydates", methods=["GET", "POST"])
def select_paydates(source_id):
    token = session.setdefault("income_form_token", secrets.token_urlsafe(32))
    if request.method == "POST" and not secrets.compare_digest(
        token, request.form.get("token", "")
    ):
        return "Form expired. Reopen the income calendar and try again.", 400
    try:
        year = int(request.values.get("year", date.today().year))
        if not 1 <= year <= 9999:
            raise ValueError
    except (ValueError, TypeError):
        return "Choose a year from 1 to 9999.", 400

    selected = set(request.form.getlist("pay_dates"))
    error = None
    status = 200
    engine = create_database_engine(current_app.config.get("DATABASE_URL"))
    try:
        with session_scope(engine) as db:
            source = db.get(IncomeSource, source_id)
            if source is None:
                abort(404)
            existing = {item.official_pay_date for item in list_official_pay_dates(db, source_id)}
            if request.method == "POST":
                try:
                    if not selected:
                        raise ValueError("Select at least one pay date.")
                    try:
                        parsed = {date.fromisoformat(value) for value in selected}
                    except ValueError:
                        raise ValueError("Select valid calendar dates.") from None
                    if any(day.year != year for day in parsed):
                        raise ValueError("Select dates within the displayed year.")
                except ValueError as invalid:
                    error = str(invalid)
                    status = 400
                else:
                    for day in sorted(parsed - existing):
                        create_official_pay_date(db, source_id, day)
        if request.method == "POST" and not error:
            return redirect(url_for("income.select_paydates", source_id=source_id, year=year), code=303)
        months = [
            (year_calendar.month_name[month], [
                [date(year, month, day) if day else None for day in week]
                for week in year_calendar.Calendar(firstweekday=6).monthdayscalendar(year, month)
            ]) for month in range(1, 13)
        ]
        return render_template(
            "income_year.html", source=source, year=year, months=months,
            existing=existing, selected=selected, token=token, error=error,
        ), status
    except SQLAlchemyError:
        current_app.logger.exception("Income calendar database unavailable")
        return render_template("income_calendar.html", unavailable=True), 503
    finally:
        engine.dispose()


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
                        action = request.form.get("action", "add_date")
                        if action == "set_default":
                            source.expected_net_cents = parse_net_cents(request.form.get("expected_net", ""))
                        elif action == "set_override":
                            payday = db.get(OfficialPayDate, request.form.get("payday_id", ""))
                            if payday is None or payday.income_source_id != source.id:
                                abort(404)
                            payday.expected_net_override_cents = parse_net_cents(request.form.get("expected_net", ""))
                        elif action == "add_date":
                            create_official_pay_date(
                                db, source.id, calendar_date("official_pay_date", required=True),
                                calendar_date("pay_period_start"), calendar_date("pay_period_end"),
                                request.form.get("source_reference"),
                            )
                        else:
                            raise ValueError("Choose a valid income action.")
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
            net_amount_text=net_amount_text, expected_net_cents=expected_net_cents,
        ), status
    except SQLAlchemyError:
        current_app.logger.exception("Income calendar database unavailable")
        return render_template("income_calendar.html", unavailable=True), 503
    finally:
        engine.dispose()
