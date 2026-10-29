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
from bill_models import BillOccurrence, SubscriptionSchedule, SubscriptionChange
from bill_repository import create_bill, set_subscription_state, update_bill
from bill_routes import bills
from database import PROJECT_ROOT, create_database_engine, session_scope, backup_sqlite_database
from income_routes import income
from subscription_repository import scheduled_dates, configure_schedule, outgoing_forecast


class SubscriptionRecurrenceTests(unittest.TestCase):
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
            self.seed = create_bill(db, 'Synthetic service', 1599, date(2027, 1, 31), kind='subscription')

    def configure(self, **changes):
        fields = dict(frequency='monthly', amount_cents=1599, anchor_date=date(2027, 1, 31),
                      confirmed=True, today=date(2027, 1, 1))
        fields.update(changes)
        with session_scope(self.engine) as db:
            return configure_schedule(db, db.get(BillOccurrence, self.seed.id), **fields)

    def test_month_end_and_leap_year_anchors_return_to_original_day(self):
        self.assertEqual(list(scheduled_dates(date(2027, 1, 31), 'monthly', date(2027, 1, 1), date(2027, 5, 1))),
                         [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31), date(2027, 4, 30)])
        self.assertEqual(list(scheduled_dates(date(2024, 2, 29), 'yearly', date(2025, 1, 1), date(2029, 1, 1))),
                         [date(2025, 2, 28), date(2026, 2, 28), date(2027, 2, 28), date(2028, 2, 29)])

    def test_opt_in_generation_horizon_and_database_duplicate_protection(self):
        with session_scope(self.engine) as db:
            outgoing_forecast(db, date(2027, 1, 1), 365)
            self.assertEqual(len(list(db.scalars(select(BillOccurrence)))), 1)
        schedule = self.configure()
        with session_scope(self.engine) as db:
            first = outgoing_forecast(db, date(2027, 1, 1), 59)
            self.assertEqual(first['total'], 3198)
            self.assertEqual([r.due_date for r in first['rows']], [date(2027, 1, 31), date(2027, 2, 28)])
            outgoing_forecast(db, date(2027, 1, 1), 59)
            expanded = outgoing_forecast(db, date(2027, 1, 1), 365)
            self.assertEqual(len(expanded['rows']), 12)
            self.assertEqual(expanded['total'], 12 * 1599)
        with self.assertRaises(IntegrityError):
            with session_scope(self.engine) as db:
                duplicate = create_bill(db, 'Duplicate', 1599, date(2027, 1, 31), kind='subscription')
                duplicate.subscription_schedule_id = schedule.id

    def test_amount_changes_and_pause_preserve_today_and_past(self):
        self.configure()
        with session_scope(self.engine) as db:
            outgoing_forecast(db, date(2027, 1, 1), 150)
        self.configure(amount_cents=2500, today=date(2027, 2, 28))
        with session_scope(self.engine) as db:
            charges = list(db.scalars(select(BillOccurrence).order_by(BillOccurrence.due_date)))
            self.assertEqual([r.amount_cents for r in charges], [1599, 1599, 2500, 2500])
        self.configure(state='inactive', amount_cents=2500, today=date(2027, 2, 28))
        with session_scope(self.engine) as db:
            projection = outgoing_forecast(db, date(2027, 1, 1), 365)
            self.assertEqual(len(projection['rows']), 4)
            self.assertEqual(projection['total'], 3198)
            self.assertEqual(projection['schedules'][0].state, 'inactive')

    def test_external_coverage_visible_without_bill_and_reactivation_no_duplicates(self):
        self.configure()
        with session_scope(self.engine) as db:
            outgoing_forecast(db, date(2027, 1, 1), 90)
        self.configure(state='covered', coverage_label='T-Mobile', today=date(2027, 2, 1))
        html = self.client.get('/bills').data
        self.assertIn(b'Recurring subscriptions covered by someone or something else', html)
        self.assertIn(b'T-Mobile', html)
        with session_scope(self.engine) as db:
            rows = outgoing_forecast(db, date(2027, 2, 1), 300)['rows']
            self.assertEqual(len(rows), 2)
            self.assertEqual(sum(r.funding_needed_cents for r in rows), 0)
        self.configure(amount_cents=2000, anchor_date=date(2027, 4, 30), today=date(2027, 2, 1))
        with session_scope(self.engine) as db:
            result = outgoing_forecast(db, date(2027, 2, 1), 150)
            self.assertEqual([r.due_date for r in result['rows'] if r.charge_is_owed],
                             [date(2027, 4, 30), date(2027, 5, 30), date(2027, 6, 30)])
            again = outgoing_forecast(db, date(2027, 2, 1), 150)
            self.assertEqual(len(again['rows']), len(result['rows']))

    def test_validation_and_complete_rollback(self):
        for values in ({'frequency': 'weekly'}, {'confirmed': False}, {'state': 'covered'},
                       {'amount_cents': None}, {'state': 'covered', 'covered_by_bill_id': self.seed.id}):
            with self.assertRaises(ValueError):
                self.configure(**values)
        with self.assertRaises(RuntimeError):
            with session_scope(self.engine) as db:
                configure_schedule(db, db.get(BillOccurrence, self.seed.id), 'monthly', 1599,
                                   date(2027, 1, 31), confirmed=True, today=date(2027, 1, 1))
                outgoing_forecast(db, date(2027, 1, 1), 365)
                raise RuntimeError('Synthetic rollback')
        with session_scope(self.engine) as db:
            self.assertEqual(list(db.scalars(select(SubscriptionSchedule))), [])
            self.assertEqual(list(db.scalars(select(SubscriptionChange))), [])
            self.assertIsNone(db.get(BillOccurrence, self.seed.id).subscription_schedule_id)

    def test_route_validation_csrf_and_yearly_creation(self):
        path = f'/bills/{self.seed.id}/recurrence'
        self.assertEqual(self.client.post(path, data={}).status_code, 400)
        self.assertEqual(self.client.get(path).status_code, 200)
        with self.client.session_transaction() as cookie:
            token = cookie['recurrence_form_token']
        fields = dict(token=token, frequency='yearly', amount='100.01', anchor_date='2027-01-31',
                      state='covered', coverage_label='Girlfriend', confirm='yes')
        self.assertEqual(self.client.post(path, data={**fields, 'amount': 'bad'}).status_code, 400)
        self.assertEqual(self.client.post(path, data=fields).status_code, 303)
        self.assertEqual(self.client.post(path, data=fields).status_code, 400)
        html = self.client.get('/income/forecast?days=365')
        self.assertEqual(html.status_code, 200)
        self.assertIn(b'Expected outgoing charges:', html.data)
        self.assertIn(b'Girlfriend', html.data)
        self.assertEqual(self.client.get('/bills/missing/recurrence').status_code, 404)

    def test_populated_backup_restore_and_downgrade_guard(self):
        schedule = self.configure()
        with session_scope(self.engine) as db:
            outgoing_forecast(db, date(2027, 1, 1), 365)
        backup = self.root / 'backup.sqlite3'
        backup_sqlite_database(self.engine, backup)
        restored = create_database_engine('sqlite:///' + str(backup))
        try:
            with session_scope(restored) as db:
                self.assertEqual(db.get(SubscriptionSchedule, schedule.id).anchor_date, date(2027, 1, 31))
                self.assertEqual(len(list(db.scalars(select(BillOccurrence)))), 12)
            with restored.connect() as conn:
                self.assertEqual(conn.scalar(text('PRAGMA integrity_check')), 'ok')
                self.assertEqual(conn.execute(text('PRAGMA foreign_key_check')).all(), [])
        finally:
            restored.dispose()
        with self.assertRaises(RuntimeError):
            command.downgrade(self.config, '0006_subscription_controls')
        with self.engine.connect() as conn:
            self.assertEqual(conn.scalar(text('SELECT version_num FROM alembic_version')), '0009_account_balances')
            self.assertEqual(conn.scalar(text('SELECT count(*) FROM bill_occurrences')), 12)

    def test_new_subscription_entry_can_enable_yearly_recurrence_and_reject_regular_bill(self):
        self.client.get('/bills')
        with self.client.session_transaction() as cookie:
            token = cookie['bill_form_token']
        fields = dict(token=token, kind='subscription', name='Annual example', amount='99.99',
                      due_date='2030-06-01', recurrence='yearly', funding_buffer_days='0')
        self.assertEqual(self.client.post('/bills', data={**fields, 'kind': 'bill'}).status_code, 400)
        self.assertEqual(self.client.post('/bills', data=fields).status_code, 303)
        with session_scope(self.engine) as db:
            schedules = list(db.scalars(select(SubscriptionSchedule)))
            self.assertEqual(len(schedules), 1)
            self.assertEqual((schedules[0].frequency, schedules[0].amount_cents), ('yearly', 9999))
            self.assertEqual(len(list(db.scalars(select(BillOccurrence)))), 2)

    def test_inclusive_horizon_and_annual_next_charge(self):
        self.configure(frequency='yearly')
        with session_scope(self.engine) as db:
            before = outgoing_forecast(db, date(2028, 1, 1), 30)
            self.assertEqual(before['total'], 0)
            through = outgoing_forecast(db, date(2028, 1, 1), 31)
            self.assertEqual(through['total'], 1599)
            self.assertEqual([r.due_date for r in through['rows']], [date(2028, 1, 31)])
            for days in (0, 366, True):
                with self.assertRaises(ValueError):
                    outgoing_forecast(db, date(2028, 1, 1), days)

    def test_upgrade_preserves_populated_coverage_history_and_all_old_fields(self):
        # This isolated database has no recurrence or external labels yet.
        command.downgrade(self.config, '0006_subscription_controls')
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO bill_occurrences (id,name,kind,subscription_state,charge_is_owed,amount_cents,due_date,funding_buffer_days,created_at) VALUES ('parent','Synthetic parent','bill','active',1,10000,'2027-02-01',3,'2026-01-01')"))
            conn.execute(text("UPDATE bill_occurrences SET subscription_state='covered',covered_by_bill_id='parent',charge_is_owed=0 WHERE id=:id"), {'id': self.seed.id})
            conn.execute(text("INSERT INTO subscription_changes (id,bill_id,before_json,after_json,created_at) VALUES ('history',:id,'{}','{}','2026-01-01')"), {'id': self.seed.id})
            columns = ','.join(row[1] for row in conn.execute(text('PRAGMA table_info(bill_occurrences)')))
            before = conn.execute(text('SELECT '+columns+' FROM bill_occurrences ORDER BY id')).all()
            history = conn.execute(text('SELECT * FROM subscription_changes')).all()
        command.upgrade(self.config, 'head')
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text('SELECT '+columns+' FROM bill_occurrences ORDER BY id')).all(), before)
            self.assertEqual(conn.execute(text('SELECT * FROM subscription_changes')).all(), history)
            self.assertEqual(conn.scalar(text('SELECT count(*) FROM subscription_schedules')), 0)
            self.assertEqual(conn.scalar(text('SELECT count(*) FROM bill_occurrences WHERE subscription_schedule_id IS NOT NULL')), 0)
            self.assertEqual(conn.execute(text('PRAGMA foreign_key_check')).all(), [])

    def test_schedule_blocks_old_edit_and_status_paths_and_parent_reclassification(self):
        with session_scope(self.engine) as db:
            parent = create_bill(db, 'Synthetic phone bill', 5000, date(2027, 2, 1))
        self.configure(state='covered', covered_by_bill_id=parent.id)
        with self.assertRaises(ValueError):
            with session_scope(self.engine) as db:
                old = db.get(BillOccurrence, self.seed.id)
                update_bill(db, old, old.name, old.amount_cents, old.due_date, kind='subscription')
        with self.assertRaises(ValueError):
            with session_scope(self.engine) as db:
                set_subscription_state(db, db.get(BillOccurrence, self.seed.id), 'inactive', charge_is_owed=True)
        with self.assertRaises(ValueError):
            with session_scope(self.engine) as db:
                old = db.get(BillOccurrence, parent.id)
                update_bill(db, old, old.name, old.amount_cents, old.due_date, kind='subscription')
