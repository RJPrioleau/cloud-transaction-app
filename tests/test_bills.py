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
from account_routes import accounts
from account_repository import create_account, list_accounts
from bill_repository import update_bill


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
        app.register_blueprint(accounts)
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

    def test_subscription_classification_persists_and_sections_are_sorted_independently(self):
        self.assertEqual(self.post(name="Rent", kind="bill").status_code, 303)
        self.assertEqual(self.post(name="Music", kind="subscription", due_date="2027-01-10").status_code, 303)
        self.assertEqual(self.post(name="Streaming", kind="subscription", due_date="2027-01-05",
                                   funding_buffer_days="0").status_code, 303)
        response = self.make_app().test_client().get("/bills")
        html = response.get_data(as_text=True)
        bills_section, subscriptions = html.split('<h2 id="subscription-heading">Subscriptions</h2>')
        self.assertIn("Rent", bills_section)
        self.assertNotIn("Music", bills_section)
        self.assertNotIn("Rent", subscriptions)
        self.assertLess(subscriptions.index("Streaming"), subscriptions.index("Music"))
        with session_scope(self.engine) as db:
            records = {r.name: r for r in list_bills(db)}
            self.assertEqual(records["Rent"].kind, "bill")
            self.assertEqual(records["Music"].kind, "subscription")
            self.assertEqual(records["Music"].funding_deadline, date(2027, 1, 7))
            self.assertEqual(records["Streaming"].funding_deadline, date(2027, 1, 5))

    def test_invalid_kind_rejected_and_valid_selection_retained_on_other_error(self):
        for kind in ("", "other", "Subscription"):
            self.assertEqual(self.post(kind=kind).status_code, 400)
        response = self.post(kind="subscription", amount="bad")
        self.assertIn(b'value="subscription" selected', response.data)
        with session_scope(self.engine) as db:
            self.assertEqual(list_bills(db), [])
        with self.assertRaises(ValueError):
            with session_scope(self.engine) as db:
                create_bill(db, "Example", 100, date(2027, 1, 1), kind="other")
        with self.assertRaises(IntegrityError):
            with self.engine.begin() as conn:
                conn.execute(text("INSERT INTO bill_occurrences (id,name,amount_cents,due_date,created_at,kind) VALUES ('bad','Example',100,'2027-01-01','2026-01-01','other')"))

    def test_edit_reclassifies_same_record_and_recalculates_deadline(self):
        self.post()
        with session_scope(self.engine) as db:
            original = list_bills(db)[0]
            original_id, created = original.id, original.created_at
            account = create_account(db, "Checking")
        path = f"/bills/{original_id}/edit"
        self.assertIn(b'value="123.45"', self.client.get(path).data)
        response = self.client.post(path, data={"token": self.token, "kind": "subscription",
            "name": "Music", "amount": "15.99", "due_date": "2027-02-01",
            "funding_buffer_days": "5", "payment_account_id": account.id})
        self.assertEqual(response.status_code, 303)
        with session_scope(self.engine) as db:
            records = list_bills(db)
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual((record.id, record.created_at), (original_id, created))
            self.assertEqual((record.kind, record.amount_cents, record.funding_deadline),
                             ("subscription", 1599, date(2027, 1, 27)))
            self.assertEqual(record.payment_account_id, account.id)
        html = self.client.get('/bills').get_data(as_text=True)
        self.assertIn("Music", html.split('<h2 id="subscription-heading">Subscriptions</h2>')[1])
        self.assertIn("Checking", html)
        self.assertEqual(self.client.get('/bills/missing/edit').status_code, 404)
        self.assertEqual(self.client.post('/bills/missing/edit', data={'token': self.token}).status_code, 404)

    def test_invalid_edit_changes_nothing_and_retains_values(self):
        self.post()
        with session_scope(self.engine) as db:
            bill = list_bills(db)[0]
        path = f'/bills/{bill.id}/edit'
        values = dict(token=self.token, name='Changed', amount='1.001', due_date='2027-02-01', kind='subscription')
        response = self.client.post(path, data=values)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'value="Changed"', response.data)
        values.update(amount='25.01', payment_account_id='missing')
        self.assertEqual(self.client.post(path, data=values).status_code, 400)
        with session_scope(self.engine) as db:
            saved = list_bills(db)[0]
            self.assertEqual((saved.name, saved.amount_cents, saved.kind), ('Example bill', 12345, 'bill'))
        self.assertEqual(self.client.post(path, data={}).status_code, 400)

    def test_create_assign_unassign_and_rename_account_updates_links(self):
        self.client.get('/accounts')
        with self.client.session_transaction() as cookie:
            token = cookie['account_form_token']
        self.assertEqual(self.client.post('/accounts', data={'token': token, 'name': ' Original '}).status_code, 303)
        with session_scope(self.engine) as db:
            account = list_accounts(db)[0]
            self.assertEqual(account.name, 'Original')
        self.post(payment_account_id=account.id)
        self.post(name='Other obligation', payment_account_id=account.id)
        self.assertEqual(self.client.post(f'/accounts/{account.id}/rename', data={'token': token, 'name': '<New name>'}).status_code, 303)
        html = self.make_app().test_client().get('/bills').data
        self.assertEqual(html.count(b'&lt;New name&gt;'), 3)  # two rows plus the selector
        with session_scope(self.engine) as db:
            records = list_bills(db)
            self.assertTrue(all(r.payment_account_id == account.id for r in records))
            update_bill(db, records[0], records[0].name, records[0].amount_cents, records[0].due_date,
                        payment_account_id=None)
        self.assertIn(b'Unassigned', self.client.get('/bills').data)

    def test_account_validation_missing_token_and_unknown_rename(self):
        self.client.get('/accounts')
        with self.client.session_transaction() as cookie:
            token = cookie['account_form_token']
        self.assertEqual(self.client.post('/accounts', data={'name': 'No token'}).status_code, 400)
        for name in (' ', 'x' * 201):
            self.assertEqual(self.client.post('/accounts', data={'token': token, 'name': name}).status_code, 400)
        self.assertEqual(self.client.post('/accounts/missing/rename', data={'token': token, 'name': 'New'}).status_code, 404)
        with session_scope(self.engine) as db:
            self.assertEqual(list_accounts(db), [])
            account = create_account(db, 'Keep name')
        self.assertEqual(self.client.post(f'/accounts/{account.id}/rename', data={'token': token, 'name': ' '}).status_code, 400)
        with session_scope(self.engine) as db:
            self.assertEqual(list_accounts(db)[0].name, 'Keep name')

    def test_account_foreign_key_rejects_nonexistent_reference(self):
        self.post()
        with self.assertRaises(IntegrityError):
            with self.engine.begin() as conn:
                conn.execute(text("UPDATE bill_occurrences SET payment_account_id='missing'"))
