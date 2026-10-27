from datetime import date
from pathlib import Path
import tempfile
import unittest

from alembic import command
from alembic.config import Config
from flask import Flask
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from bill_repository import create_bill, list_bills
from bill_routes import bills
from database import PROJECT_ROOT, create_database_engine, session_scope
from income_routes import income


class BillTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.url = "sqlite:///" + str(Path(temporary.name) / "synthetic.sqlite3")
        self.config = Config(str(PROJECT_ROOT / "alembic.ini"))
        self.config.attributes["database_url"] = self.url
        command.upgrade(self.config, "head")
        self.engine = create_database_engine(self.url)
        self.addCleanup(self.engine.dispose)
        self.app = self.make_app()
        self.client = self.app.test_client()
        self.client.get("/bills")
        with self.client.session_transaction() as session:
            self.token = session["bill_form_token"]

    def make_app(self):
        app = Flask(__name__, template_folder=str(PROJECT_ROOT / "templates"))
        app.config.update(TESTING=True, SECRET_KEY="synthetic", DATABASE_URL=self.url)
        app.add_url_rule("/", endpoint="home", view_func=lambda: "Upload")
        app.register_blueprint(income)
        app.register_blueprint(bills)
        return app

    def post(self, **changes):
        values = {"token": self.token, "name": "Example bill", "amount": "123.45",
                  "due_date": "2027-01-02", "funding_buffer_days": ""}
        values.update(changes)
        return self.client.post("/bills", data=values)

    def test_bill_persists_exact_cents_deadline_and_refresh_does_not_resubmit(self):
        response = self.post(name="<Rent>")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["Location"], "/bills")
        for _ in range(2):
            html = self.make_app().test_client().get("/bills").data
            self.assertIn(b"&lt;Rent&gt;", html)
            self.assertIn(b"$123.45", html)
            self.assertIn(b"2026-12-30", html)
        with session_scope(self.engine) as db:
            records = list_bills(db)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].amount_cents, 12345)
            self.assertEqual(records[0].funding_buffer_days, 3)

    def test_calendar_boundaries_and_deadline_order_differ_from_due_date_order(self):
        with session_scope(self.engine) as db:
            later_due = create_bill(db, "Earlier deadline", 1, date(2028, 3, 5), 10)
            earlier_due = create_bill(db, "Later deadline", 0, date(2028, 3, 1), 0)
            leap = create_bill(db, "Leap boundary", 100, date(2028, 3, 1))
            self.assertEqual(leap.funding_deadline, date(2028, 2, 27))
            self.assertEqual([r.id for r in list_bills(db)], [later_due.id, leap.id, earlier_due.id])
        self.assertEqual(self.post(funding_buffer_days="0").status_code, 303)

    def test_validation_retains_entries_and_writes_nothing(self):
        for values in ({"name": " "}, {"name": "x" * 201}, {"amount": ""},
                       {"amount": "-1"}, {"amount": "1.001"}, {"amount": "NaN"},
                       {"due_date": "2027-02-30"}, {"funding_buffer_days": "-1"},
                       {"funding_buffer_days": "1.5"}, {"funding_buffer_days": "oops"},
                       {"due_date": "0001-01-01", "funding_buffer_days": "3"}):
            response = self.post(**values)
            self.assertEqual(response.status_code, 400)
            self.assertIn(b'role="alert"', response.data)
            with session_scope(self.engine) as db:
                self.assertEqual(list_bills(db), [])
        response = self.post(amount="bad", name="Retain this name")
        self.assertIn(b'value="Retain this name"', response.data)

    def test_missing_token_rejected_and_missing_schema_explained(self):
        self.assertEqual(self.client.post("/bills", data={"name": "No token"}).status_code, 400)
        command.downgrade(self.config, "0002_expected_net_pay")
        with self.assertLogs(self.app.logger, level="ERROR"):
            response = self.client.get("/bills")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"python -m alembic upgrade head", response.data)

    def test_failed_operation_rolls_back_bill(self):
        with self.assertRaises(RuntimeError):
            with session_scope(self.engine) as db:
                create_bill(db, "Example", 100, date(2027, 1, 2))
                raise RuntimeError("Synthetic failure")
        with session_scope(self.engine) as db:
            self.assertEqual(list_bills(db), [])

    def test_database_rejects_negative_amount_buffer_and_blank_name(self):
        for name, amount, buffer in (("Example", -1, 3), ("Example", 100, -1), (" ", 100, 3)):
            with self.assertRaises(IntegrityError):
                with self.engine.begin() as conn:
                    conn.execute(text("INSERT INTO bill_occurrences (id,name,amount_cents,due_date,funding_buffer_days,created_at) VALUES ('bad',:name,:amount,'2027-01-01',:buffer,'2026-01-01')"),
                                 {"name": name, "amount": amount, "buffer": buffer})

    def test_repository_rejects_noninteger_money_and_buffers(self):
        for amount, buffer in ((1.5, 3), (True, 3), (1, True), (1, 2.5), (None, 3)):
            with self.assertRaises(ValueError):
                with session_scope(self.engine) as db:
                    create_bill(db, "Example", amount, date(2027, 1, 2), buffer)
