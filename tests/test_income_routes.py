from pathlib import Path
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
