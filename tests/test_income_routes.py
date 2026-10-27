from pathlib import Path
import tempfile
import unittest

from alembic import command
from alembic.config import Config
from flask import Flask

from database import PROJECT_ROOT, create_database_engine, session_scope
from income_repository import list_income_sources, list_official_pay_dates
from income_routes import income


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
