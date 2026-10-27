from pathlib import Path
from datetime import date, timedelta
import tempfile
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from flask import Flask

from database import PROJECT_ROOT, create_database_engine, session_scope
from income_repository import list_income_sources, list_official_pay_dates
from income_routes import income
from income_repository import create_official_pay_date
from income_repository import parse_net_cents, expected_net_cents, net_amount_text, income_forecast
from sqlalchemy.exc import SQLAlchemyError


class IncomeRouteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.url = "sqlite:///" + str(Path(temporary.name) / "synthetic.sqlite3")
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        config.attributes["database_url"] = self.url
        command.upgrade(config, "head")
        self.app = self.make_app()
        self.client = self.app.test_client()
        self.client.get("/income")
        with self.client.session_transaction() as session:
            self.token = session["income_form_token"]

    def make_app(self):
        app = Flask(__name__, template_folder=str(PROJECT_ROOT / "templates"))
        app.config.update(TESTING=True, SECRET_KEY="synthetic-test", DATABASE_URL=self.url)
        app.add_url_rule("/", endpoint="home", view_func=lambda: "Upload")
        app.register_blueprint(income)
        return app

    def post(self, path, **values):
        return self.client.post(path, data={"token": self.token, **values})

    def source(self, name="WSP"):
        response = self.post("/income", name=name)
        self.assertEqual(response.status_code, 303)
        return response.headers["Location"]

    def test_source_persists_in_new_application_and_refresh_does_not_repeat_post(self):
        location = self.source("<WSP>")
        for _ in range(2):
            response = self.client.get(location)
            self.assertIn(b"&lt;WSP&gt;", response.data)
            self.assertNotIn(b"<WSP>", response.data)
        self.assertIn(b"&lt;WSP&gt;", self.make_app().test_client().get("/income").data)
        engine = create_database_engine(self.url)
        try:
            with session_scope(engine) as db:
                self.assertEqual(len(list_income_sources(db)), 1)
        finally:
            engine.dispose()

    def test_dates_are_ordered_isolated_draft_and_survive_refresh(self):
        location = self.source()
        for day in ("2026-11-13", "2026-11-06"):
            response = self.post(location, official_pay_date=day,
                                 pay_period_start="2026-10-01", pay_period_end="2026-10-15",
                                 source_reference="Official calendar")
            self.assertEqual(response.status_code, 303)
        for _ in range(2):
            html = self.client.get(location).get_data(as_text=True)
            self.assertLess(html.index("2026-11-06"), html.index("2026-11-13"))
            self.assertIn("Official calendar", html)
            self.assertEqual(html.count("<td>Draft</td>"), 2)
        other = self.source("VA")
        self.assertNotIn(b"2026-11-06", self.client.get(other).data)
        self.assertIn(b"2026-11-06", self.make_app().test_client().get(location).data)

    def test_invalid_inputs_preserve_form_and_write_nothing(self):
        self.assertEqual(self.post("/income", name="   ").status_code, 400)
        location = self.source()
        for values in ({"official_pay_date": ""}, {"official_pay_date": "bad"},
                       {"official_pay_date": "2026-02-30"},
                       {"official_pay_date": "2026-11-06", "pay_period_start": "2026-11-10",
                        "pay_period_end": "2026-11-01"},
                       {"official_pay_date": "2026-11-06", "source_reference": "x" * 501}):
            self.assertEqual(self.post(location, **values).status_code, 400)
        engine = create_database_engine(self.url)
        try:
            with session_scope(engine) as db:
                self.assertEqual(list_official_pay_dates(db, location.rsplit("/", 1)[1]), [])
        finally:
            engine.dispose()

    def test_unknown_source_and_missing_form_token_are_rejected(self):
        self.assertEqual(self.client.get("/income/missing").status_code, 404)
        self.assertEqual(self.post("/income/missing", official_pay_date="2026-11-06").status_code, 404)
        self.assertEqual(self.client.post("/income", data={"name": "WSP"}).status_code, 400)

    def test_missing_schema_shows_setup_guidance(self):
        command_config = Config(str(PROJECT_ROOT / "alembic.ini"))
        command_config.attributes["database_url"] = self.url
        command.downgrade(command_config, "base")
        with self.assertLogs(self.app.logger, level="ERROR"):
            response = self.client.get("/income")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"python -m alembic upgrade head", response.data)

    def saved_dates(self, location):
        engine = create_database_engine(self.url)
        try:
            with session_scope(engine) as db:
                return list_official_pay_dates(db, location.rsplit("/", 1)[1])
        finally:
            engine.dispose()

    def test_year_calendar_label_leap_day_and_year_validation(self):
        location = self.source()
        response = self.client.get(location + "/paydates?year=2028")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Select pay dates for WSP — 2028", response.get_data(as_text=True))
        self.assertIn(b'value="2028-02-29"', response.data)
        self.assertEqual(response.data.count(b'type="checkbox"'), 366)
        for year in ("bad", "0", "10000"):
            self.assertEqual(self.client.get(location + "/paydates?year=" + year).status_code, 400)
        self.assertEqual(self.client.get("/income/missing/paydates").status_code, 404)

    def test_bulk_dates_persist_skip_existing_and_remain_source_specific(self):
        location = self.source()
        path = location + "/paydates"
        values = {"year": "2026", "pay_dates": ["2026-11-06", "2026-11-13", "2026-11-06"]}
        for _ in range(2):
            response = self.post(path, **values)
            self.assertEqual(response.status_code, 303)
            self.assertIn("year=2026", response.headers["Location"])
        records = self.saved_dates(location)
        self.assertEqual([str(item.official_pay_date) for item in records], ["2026-11-06", "2026-11-13"])
        self.assertTrue(all(item.review_status == "draft" for item in records))
        reopened = self.make_app().test_client().get(path + "?year=2026")
        self.assertIn(b"2026-11-06", reopened.data)
        self.assertNotIn(b'value="2026-11-06"', reopened.data)
        other = self.source("VA")
        self.assertEqual(self.saved_dates(other), [])
        self.assertEqual(self.post(other + "/paydates", **values).status_code, 303)
        self.assertEqual(len(self.saved_dates(other)), 2)

    def test_bulk_invalid_dates_and_token_save_nothing(self):
        location = self.source()
        path = location + "/paydates"
        for days in ([], ["2026-11-06", "bad"], ["2026-11-06", "2026-02-30"],
                     ["2026-11-06", "2027-01-01"]):
            self.assertEqual(self.post(path, year="2026", pay_dates=days).status_code, 400)
            self.assertEqual(self.saved_dates(location), [])
        self.assertEqual(self.client.post(path, data={"year": "2026", "pay_dates": "2026-11-06"}).status_code, 400)
        self.assertEqual(self.saved_dates(location), [])

    def test_bulk_failure_rolls_back_earlier_dates(self):
        location = self.source()
        def fail_second(db, source_id, day):
            if day.day == 13:
                raise SQLAlchemyError("Synthetic write failure")
            return create_official_pay_date(db, source_id, day)
        with patch("income_routes.create_official_pay_date", side_effect=fail_second):
            with self.assertLogs(self.app.logger, level="ERROR"):
                response = self.post(location + "/paydates", year="2026",
                                     pay_dates=["2026-11-06", "2026-11-13"])
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.saved_dates(location), [])

    def test_expected_net_pay_defaults_overrides_clear_and_persist(self):
        location = self.source()
        self.post(location + "/paydates", year="2026", pay_dates=["2026-11-06", "2026-11-13"])
        payday = self.saved_dates(location)[0]
        self.assertEqual(self.post(location, action="set_default", expected_net="2925.91").status_code, 303)
        self.assertEqual(self.post(location, action="set_override", payday_id=payday.id, expected_net="3000.01").status_code, 303)
        html = self.make_app().test_client().get(location).get_data(as_text=True)
        self.assertIn("$2925.91 (default)", html)
        self.assertIn("$3000.01 (override)", html)
        self.post(location, action="set_default", expected_net="2800.00")
        html = self.client.get(location).get_data(as_text=True)
        self.assertIn("$3000.01 (override)", html)
        self.assertIn("$2800.00 (default)", html)
        self.post(location, action="set_override", payday_id=payday.id, expected_net="0.00")
        self.assertIn(b"$0.00 (override)", self.client.get(location).data)
        self.post(location, action="set_override", payday_id=payday.id, expected_net="")
        self.assertEqual(self.client.get(location).data.count(b"$2800.00 (default)"), 2)
        self.post(location, action="set_default", expected_net="")
        self.assertIn(b"Not set (default)", self.client.get(location).data)
        self.assertTrue(all(r.review_status == "draft" for r in self.saved_dates(location)))

    def test_invalid_amount_does_not_change_default_and_other_source_cannot_edit_override(self):
        location = self.source()
        self.post(location, official_pay_date="2026-11-06")
        payday = self.saved_dates(location)[0]
        self.post(location, action="set_default", expected_net="2925.91")
        for value in ("-1", "NaN", "Infinity", "1e3", "1.001", "2,925.91", "abc", "99999999999999999999"):
            self.assertEqual(self.post(location, action="set_default", expected_net=value).status_code, 400)
            self.assertIn(b"$2925.91 (default)", self.client.get(location).data)
        other = self.source("Other")
        self.assertEqual(self.post(other, action="set_override", payday_id=payday.id, expected_net="1").status_code, 404)
        self.assertIsNone(self.saved_dates(location)[0].expected_net_override_cents)
        self.assertEqual(self.client.post(location, data={"action": "set_default", "expected_net": "1"}).status_code, 400)

    def test_integer_cents_are_exact_and_unknown_differs_from_zero(self):
        self.assertEqual(parse_net_cents("2925.91"), 292591)
        self.assertEqual(net_amount_text(292591), "2925.91")
        self.assertEqual(parse_net_cents("0.01"), 1)
        self.assertIsNone(parse_net_cents(""))
        from types import SimpleNamespace
        source = SimpleNamespace(expected_net_cents=292591)
        self.assertEqual(expected_net_cents(source, SimpleNamespace(expected_net_override_cents=0)), 0)
        self.assertEqual(expected_net_cents(source, SimpleNamespace(expected_net_override_cents=None)), 292591)

    def test_forecast_boundaries_multiple_sources_overrides_and_exact_total(self):
        start = date(2026, 12, 1)
        location = self.source("Employer")
        self.post(location, action="set_default", expected_net="100.01")
        for offset in (-1, 0, 89, 90):
            self.post(location, official_pay_date=str(start + timedelta(days=offset)))
        records = self.saved_dates(location)
        self.post(location, action="set_override", payday_id=records[2].id, expected_net="125.02")
        other = self.source("Benefits")
        self.post(other, official_pay_date=str(start))
        self.post(other, action="set_default", expected_net="0.01")
        unknown = self.source("Unknown")
        self.post(unknown, official_pay_date=str(start + timedelta(days=1)))
        zero = self.source("Zero")
        self.post(zero, official_pay_date=str(start + timedelta(days=2)))
        self.post(zero, action="set_override", payday_id=self.saved_dates(zero)[0].id, expected_net="0.00")
        engine = create_database_engine(self.url)
        try:
            with session_scope(engine) as db:
                result = income_forecast(db, start)
            self.assertEqual(result["total"], 22504)
            self.assertEqual(result["unknown"], 1)
            self.assertEqual(len(result["rows"]), 5)
            self.assertEqual(result["last_day"], start + timedelta(days=89))
            self.assertEqual([r["date"] for r in result["rows"]], sorted(r["date"] for r in result["rows"]))
        finally:
            engine.dispose()
        with patch("income_routes.date") as clock_date:
            clock_date.today.return_value = start
            response = self.client.get("/income/forecast")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"$225.04", response.data)
        self.assertIn(b"Incomplete estimate: 1", response.data)
        self.assertIn(b"$0.00", response.data)
        self.assertIn(b"Payday override", response.data)
        self.assertEqual(len(self.saved_dates(location)), 4)

    def test_empty_forecast_and_unknown_only_forecast(self):
        response = self.client.get("/income/forecast")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No saved pay dates", response.data)
        self.assertIn(b"$0.00", response.data)
        location = self.source("<Unknown>")
        self.post(location, official_pay_date=str(date.today()))
        response = self.client.get("/income/forecast")
        self.assertIn(b"Amount not set", response.data)
        self.assertIn(b"&lt;Unknown&gt;", response.data)
        self.assertIn(b"Incomplete estimate: 1", response.data)

    def test_forecast_does_not_accept_writes_and_handles_unavailable_schema(self):
        self.assertEqual(self.client.post("/income/forecast").status_code, 405)
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        config.attributes["database_url"] = self.url
        command.downgrade(config, "base")
        with self.assertLogs(self.app.logger, level="ERROR"):
            response = self.client.get("/income/forecast")
        self.assertEqual(response.status_code, 503)

    def test_horizon_updates_dates_totals_and_unknown_counts_without_changing_records(self):
        start = date(2027, 12, 31)
        location = self.source("Employer")
        self.post(location, action="set_default", expected_net="100.01")
        for offset in (0, 1, 89, 90, 364, 365):
            self.post(location, official_pay_date=str(start + timedelta(days=offset)))
        unknown = self.source("Unknown")
        self.post(unknown, official_pay_date=str(start + timedelta(days=90)))
        original_ids = [r.id for r in self.saved_dates(location)]
        with patch("income_routes.date") as clock_date:
            clock_date.today.return_value = start
            for days, count, unknown_count in ((1, 1, 0), (90, 3, 0), (365, 5, 1)):
                response = self.client.get(f"/income/forecast?days={days}")
                html = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(f"Next {days} Days", html)
                self.assertIn(f"{start} through {start + timedelta(days=days-1)}", html)
                self.assertIn(f"${net_amount_text(count * 10001)}", html)
                self.assertEqual("Incomplete estimate:" in html, bool(unknown_count))
            default = self.client.get("/income/forecast")
            self.assertIn(b"Next 90 Days", default.data)
        self.assertEqual([r.id for r in self.saved_dates(location)], original_ids)

    def test_invalid_horizons_show_actionable_error_without_a_misleading_total(self):
        for days in ("", "0", "-1", "366", "abc", "1.5", "1e2"):
            response = self.client.get("/income/forecast", query_string={"days": days})
            self.assertEqual(response.status_code, 400)
            self.assertIn(b"Choose a whole number of days from 1 to 365.", response.data)
            self.assertNotIn(b"Known expected net total:", response.data)
            self.assertIn(b"Update forecast", response.data)
        engine = create_database_engine(self.url)
        try:
            with session_scope(engine) as db:
                for days in (True, None, "90", 0, 366, 1.5):
                    with self.assertRaises(ValueError):
                        income_forecast(db, date(2026, 1, 1), days)
        finally:
            engine.dispose()
