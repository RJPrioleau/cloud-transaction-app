from datetime import date
from pathlib import Path
import tempfile
import unittest

from alembic import command
from alembic.config import Config
from flask import Flask
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from account_routes import accounts
from bill_models import BillOccurrence, BillSchedule
from bill_repository import create_bill, update_bill
from bill_routes import bills
from database import PROJECT_ROOT, backup_sqlite_database, create_database_engine, session_scope
from income_routes import income
from monthly_bill_repository import (enable_monthly_bill, confirm_month_amount,
                                     estimate_amount, amount_basis_text)
from subscription_repository import outgoing_forecast


class MonthlyBillTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.url = 'sqlite:///' + str(self.root / 'synthetic.sqlite3')
        self.config = Config(str(PROJECT_ROOT / 'alembic.ini'))
        self.config.attributes['database_url'] = self.url
        command.upgrade(self.config, 'head')
        self.engine = create_database_engine(self.url)
        self.addCleanup(self.engine.dispose)
        app = Flask(__name__, template_folder=str(PROJECT_ROOT / 'templates'))
        app.config.update(TESTING=True, SECRET_KEY='synthetic', DATABASE_URL=self.url)
        app.add_url_rule('/', endpoint='home', view_func=lambda: 'Upload')
        for blueprint in (income, bills, accounts):
            app.register_blueprint(blueprint)
        self.client = app.test_client()
        with session_scope(self.engine) as db:
            self.seed = create_bill(db, 'Synthetic utility', 5000, date(2027, 4, 30))
        self.path = f'/bills/{self.seed.id}/monthly'

    def enable(self):
        with session_scope(self.engine) as db:
            self.schedule = enable_monthly_bill(db, db.get(BillOccurrence, self.seed.id),
                                                5000, confirmed=True, today=date(2027, 1, 1))

    def confirm(self, year, month, amount, today=date(2027, 3, 31), **kwargs):
        with session_scope(self.engine) as db:
            return confirm_month_amount(db, db.get(BillSchedule, self.schedule.id),
                                        date(year, month, 1), amount, confirmed=True, today=today, **kwargs)

    def test_explicit_opt_in_and_idempotent_monthly_forecast(self):
        with session_scope(self.engine) as db:
            self.assertEqual(len(outgoing_forecast(db, date(2027, 4, 1), 365)['rows']), 1)
        self.enable()
        with session_scope(self.engine) as db:
            first = outgoing_forecast(db, date(2027, 4, 1), 365)
            self.assertEqual(len(first['rows']), 12)
            self.assertEqual(first['total'], 60000)
            self.assertEqual(len(outgoing_forecast(db, date(2027, 4, 1), 365)['rows']), 12)
            self.assertTrue(all(r.amount_confirmed_at is None for r in first['rows']))
            self.assertTrue(all(r.amount_basis == 'starting' for r in first['rows']))

    def test_previous_three_calendar_months_excludes_estimates_and_old_history(self):
        self.enable()
        self.confirm(2026, 12, 99999)
        self.confirm(2027, 1, 10000)
        self.confirm(2027, 2, 20000)
        with session_scope(self.engine) as db:
            schedule = db.get(BillSchedule, self.schedule.id)
            self.assertEqual(estimate_amount(db, schedule, date(2027, 4, 1)), (15000, 'history_2'))
            self.assertEqual(estimate_amount(db, schedule, date(2027, 5, 1)), (20000, 'history_1'))
            self.assertEqual(estimate_amount(db, schedule, date(2027, 6, 1)), (5000, 'starting'))
        self.confirm(2027, 3, 30000)
        with session_scope(self.engine) as db:
            schedule = db.get(BillSchedule, self.schedule.id)
            self.assertEqual(estimate_amount(db, schedule, date(2027, 4, 1)), (20000, 'history_3'))

    def test_zero_half_cent_rounding_and_year_boundary(self):
        self.enable()
        self.confirm(2026, 11, 0)
        self.confirm(2026, 12, 1)
        with session_scope(self.engine) as db:
            self.assertEqual(estimate_amount(db, db.get(BillSchedule, self.schedule.id), date(2027, 1, 1)),
                             (1, 'history_2'))

    def test_history_correction_updates_future_estimates_but_preserves_today_past_and_confirmed(self):
        self.enable()
        with session_scope(self.engine) as db:
            outgoing_forecast(db, date(2027, 4, 1), 150)
        self.confirm(2027, 5, 12345, today=date(2027, 4, 30))
        self.confirm(2027, 3, 9000, today=date(2027, 4, 30))
        with session_scope(self.engine) as db:
            rows = {r.bill_month.month: r for r in db.scalars(select(BillOccurrence).where(
                BillOccurrence.bill_schedule_id == self.schedule.id))}
            self.assertEqual(rows[4].amount_cents, 5000)  # due today: retain earlier estimate
            self.assertEqual(rows[5].amount_cents, 12345)  # explicit future confirmation
            self.assertEqual(rows[6].amount_cents, 10673)  # March + May, half-cent up
            self.assertEqual(rows[7].amount_cents, 12345)  # April unconfirmed, May confirmed
        self.confirm(2027, 3, 10000, today=date(2027, 4, 30))
        with session_scope(self.engine) as db:
            june = db.scalar(select(BillOccurrence).where(BillOccurrence.bill_schedule_id == self.schedule.id,
                                                         BillOccurrence.bill_month == date(2027, 6, 1)))
            self.assertEqual(june.amount_cents, 11173)

    def test_confirm_existing_bill_is_explicit_same_month_and_preserves_identity(self):
        self.enable()
        with session_scope(self.engine) as db:
            old = create_bill(db, 'Manually entered old utility', 1234, date(2027, 2, 12))
            identity = old.id, old.created_at, old.due_date
        confirmed = self.confirm(2027, 2, 2345, existing_bill_id=old.id)
        self.assertEqual((confirmed.id, confirmed.created_at, confirmed.due_date), identity)
        self.assertEqual(confirmed.amount_basis, 'confirmed')
        with self.assertRaises(ValueError):
            self.confirm(2027, 3, 3456, existing_bill_id=old.id)
        with session_scope(self.engine) as db:
            duplicate = create_bill(db, 'Duplicate same month', 100, date(2027, 2, 2))
        with self.assertRaises(ValueError):
            self.confirm(2027, 2, 100, existing_bill_id=duplicate.id)

    def test_other_bill_history_never_contributes_and_duplicate_month_is_constrained(self):
        self.enable()
        with session_scope(self.engine) as db:
            other = create_bill(db, 'Other utility', 100, date(2027, 3, 15))
            other_schedule = enable_monthly_bill(db, other, 100, confirmed=True)
            confirm_month_amount(db, other_schedule, date(2027, 3, 1), 99999, confirmed=True)
            self.assertEqual(estimate_amount(db, db.get(BillSchedule, self.schedule.id), date(2027, 4, 1)),
                             (5000, 'starting'))
        with self.assertRaises(IntegrityError):
            with session_scope(self.engine) as db:
                duplicate = create_bill(db, 'Duplicate month', 1, date(2027, 4, 10))
                duplicate.bill_schedule_id, duplicate.bill_month = self.schedule.id, date(2027, 4, 1)

    def test_failed_confirmation_rolls_back_new_history_and_recalculation(self):
        self.enable()
        with self.assertRaises(RuntimeError):
            with session_scope(self.engine) as db:
                confirm_month_amount(db, db.get(BillSchedule, self.schedule.id), date(2027, 3, 1),
                                     9999, confirmed=True, today=date(2027, 1, 1))
                raise RuntimeError('Synthetic write failure')
        with session_scope(self.engine) as db:
            rows = list(db.scalars(select(BillOccurrence)))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].amount_cents, 5000)
            self.assertIsNone(rows[0].amount_confirmed_at)

    def test_route_validation_tokens_history_and_forecast_basis(self):
        self.assertEqual(self.client.post(self.path, data={}).status_code, 400)
        self.client.get(self.path)
        with self.client.session_transaction() as cookie:
            token = cookie['monthly_bill_token_' + self.seed.id]
        fields = dict(token=token, starting_estimate='50', confirm='yes')
        self.assertEqual(self.client.post(self.path, data={**fields, 'starting_estimate': 'bad'}).status_code, 400)
        self.assertEqual(self.client.post(self.path, data=fields).status_code, 303)
        self.assertEqual(self.client.post(self.path, data=fields).status_code, 400)
        self.client.get(self.path)
        with self.client.session_transaction() as cookie:
            token = cookie['monthly_bill_token_' + self.seed.id]
        values = dict(token=token, month='2027-03', amount='12.34', confirm='yes')
        self.assertEqual(self.client.post(self.path, data={**values, 'month': 'bad'}).status_code, 400)
        self.assertEqual(self.client.post(self.path, data=values).status_code, 303)
        html = self.client.get(self.path)
        self.assertIn(b'Confirmed amount (not payment status)', html.data)
        self.assertIn(b'available history (1 of previous 3 months)', html.data)
        self.assertEqual(self.client.get('/bills/missing/monthly').status_code, 404)

    def test_validation_and_direct_edit_guard(self):
        with self.assertRaises(ValueError):
            with session_scope(self.engine) as db:
                enable_monthly_bill(db, db.get(BillOccurrence, self.seed.id), 1)
        self.enable()
        for amount in (None, -1, True, 1.5):
            with self.assertRaises(ValueError):
                self.confirm(2027, 3, amount)
        with self.assertRaises(ValueError):
            with session_scope(self.engine) as db:
                old = db.get(BillOccurrence, self.seed.id)
                update_bill(db, old, old.name, old.amount_cents, old.due_date)

    def test_backup_preserves_schedule_confirmation_and_guarded_downgrade(self):
        self.enable()
        self.confirm(2027, 3, 4321)
        backup = self.root / 'backup.sqlite3'
        backup_sqlite_database(self.engine, backup)
        restored = create_database_engine('sqlite:///' + str(backup))
        try:
            with session_scope(restored) as db:
                schedule = db.get(BillSchedule, self.schedule.id)
                self.assertEqual(estimate_amount(db, schedule, date(2027, 4, 1)), (4321, 'history_1'))
                historical = db.scalar(select(BillOccurrence).where(BillOccurrence.bill_month == date(2027, 3, 1)))
                self.assertIsNotNone(historical.amount_confirmed_at)
            with restored.connect() as conn:
                self.assertEqual(conn.scalar(text('PRAGMA integrity_check')), 'ok')
                self.assertEqual(conn.execute(text('PRAGMA foreign_key_check')).all(), [])
        finally:
            restored.dispose()
        with self.assertRaises(RuntimeError):
            command.downgrade(self.config, '0007_subscription_schedules')
        with self.engine.connect() as conn:
            self.assertEqual(conn.scalar(text('SELECT version_num FROM alembic_version')), '0008_monthly_bills')

    def test_migration_preserves_old_columns_and_starts_unconfirmed(self):
        command.downgrade(self.config, '0007_subscription_schedules')
        with self.engine.connect() as conn:
            columns = ','.join(row[1] for row in conn.execute(text('PRAGMA table_info(bill_occurrences)')))
            before = conn.execute(text('SELECT '+columns+' FROM bill_occurrences')).all()
        command.upgrade(self.config, 'head')
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text('SELECT '+columns+' FROM bill_occurrences')).all(), before)
            self.assertEqual(conn.scalar(text('SELECT count(*) FROM bill_schedules')), 0)
            self.assertEqual(conn.scalar(text('SELECT count(*) FROM bill_occurrences WHERE amount_confirmed_at IS NOT NULL OR bill_schedule_id IS NOT NULL')), 0)

    def test_new_bill_entry_monthly_and_short_month_anchor(self):
        self.client.get('/bills')
        with self.client.session_transaction() as cookie:
            token = cookie['bill_form_token']
        values = dict(token=token, kind='bill', name='Monthly example', amount='10.01',
                      due_date='2027-01-31', funding_buffer_days='0', recurrence='monthly')
        self.assertEqual(self.client.post('/bills', data={**values, 'recurrence': 'yearly'}).status_code, 400)
        self.assertEqual(self.client.post('/bills', data=values).status_code, 303)
        with session_scope(self.engine) as db:
            rows = [r for r in outgoing_forecast(db, date(2027, 1, 1), 90)['rows']
                    if r.name == 'Monthly example']
            self.assertEqual([r.due_date for r in rows], [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31)])
            self.assertEqual([r.amount_cents for r in rows], [1001, 1001, 1001])
            self.assertTrue(all(r.amount_confirmed_at is None for r in rows))

    def test_confirmation_metadata_and_schedule_kind_are_database_constrained(self):
        self.enable()
        for statement in ("amount_basis='confirmed'", "amount_confirmed_at='2027-01-01'",
                          "kind='subscription'", "bill_month=NULL"):
            with self.assertRaises(IntegrityError):
                with self.engine.begin() as conn:
                    conn.execute(text('UPDATE bill_occurrences SET '+statement+' WHERE id=:id'), {'id': self.seed.id})
