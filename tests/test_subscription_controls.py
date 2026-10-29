from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from alembic import command
from alembic.config import Config
from flask import Flask
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from account_routes import accounts
from account_repository import create_account
from bill_models import BillOccurrence, SubscriptionChange
from bill_repository import create_bill, list_bills, set_subscription_state, update_bill
from bill_routes import bills
from database import PROJECT_ROOT, create_database_engine, session_scope
from income_routes import income


class SubscriptionControlTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.url = 'sqlite:///' + str(Path(temp.name) / 'synthetic.sqlite3')
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
        self.app = app
        self.client = app.test_client()
        with session_scope(self.engine) as db:
            self.sub = create_bill(db, 'Example subscription', 1599, date(2027, 1, 10), kind='subscription')
            self.parent = create_bill(db, 'Phone bill', 10000, date(2027, 1, 15))
        self.path = f'/bills/{self.sub.id}/subscription'

    def post(self, **fields):
        self.client.get(self.path)
        with self.client.session_transaction() as cookie:
            token = cookie['subscription_token_' + self.sub.id]
        return self.client.post(self.path, data={'token': token, **fields})

    def saved(self):
        with session_scope(self.engine) as db:
            return db.get(BillOccurrence, self.sub.id)

    def test_inactive_placeholder_requires_confirmation_and_excludes_funding(self):
        values = dict(state='inactive', charge_responsibility='not_owed')
        self.assertEqual(self.post(**values).status_code, 400)
        self.assertEqual(self.saved().subscription_state, 'active')
        self.assertEqual(self.post(**values, confirm_no_charge='yes').status_code, 303)
        saved = self.saved()
        self.assertEqual((saved.subscription_state, saved.charge_is_owed, saved.funding_needed_cents), ('inactive', False, 0))
        self.assertEqual((saved.amount_cents, saved.due_date), (1599, date(2027, 1, 10)))
        html = self.client.get('/bills').data
        self.assertIn(b'Inactive / paused', html)
        self.assertIn(b'Reference only', html)
        self.assertIn(b'Not required', html)

    def test_inactive_unpaid_charge_keeps_amount_and_records_confirmation_history(self):
        self.assertEqual(self.post(state='inactive', charge_responsibility='owed').status_code, 303)
        saved = self.saved()
        self.assertEqual(saved.funding_needed_cents, 1599)
        self.assertEqual(saved.funding_deadline, date(2027, 1, 7))
        self.assertIn(b'Unpaid charge retained', self.client.get('/bills').data)
        with session_scope(self.engine) as db:
            history = list(db.scalars(select(SubscriptionChange)))
            self.assertEqual(len(history), 1)
            self.assertEqual(json.loads(history[0].before_json)['state'], 'active')
            self.assertEqual(json.loads(history[0].after_json)['state'], 'inactive')

    def test_covered_entry_uses_link_and_has_no_separate_funding(self):
        self.assertEqual(self.post(state='covered', charge_responsibility='not_owed', confirm_no_charge='yes',
                                   covered_by_bill_id=self.parent.id).status_code, 303)
        saved = self.saved()
        self.assertEqual(saved.covered_by_bill_id, self.parent.id)
        with session_scope(self.engine) as db:
            self.assertEqual(sum(r.funding_needed_cents for r in list_bills(db)), 10000)
            parent = db.get(BillOccurrence, self.parent.id)
            update_bill(db, parent, 'Renamed phone', 10000, parent.due_date)
        self.assertIn(b'Covered by Renamed phone', self.client.get('/bills').data)
        self.assertEqual(self.post(state='covered', charge_responsibility='owed', covered_by_bill_id=self.parent.id).status_code, 303)
        self.assertEqual(self.saved().funding_needed_cents, 1599)

    def test_invalid_coverage_and_parent_reclassification_are_rejected(self):
        with session_scope(self.engine) as db:
            other = create_bill(db, 'Other subscription', 100, date(2027,1,15), kind='subscription')
        for target in ('missing', self.sub.id, other.id, ''):
            self.assertEqual(self.post(state='covered', charge_responsibility='not_owed', confirm_no_charge='yes', covered_by_bill_id=target).status_code, 400)
        self.post(state='covered', charge_responsibility='not_owed', confirm_no_charge='yes', covered_by_bill_id=self.parent.id)
        with self.assertRaises(ValueError):
            with session_scope(self.engine) as db:
                parent = db.get(BillOccurrence, self.parent.id)
                update_bill(db, parent, parent.name, parent.amount_cents, parent.due_date, kind='subscription')
        with self.assertRaises(ValueError):
            with session_scope(self.engine) as db:
                sub = db.get(BillOccurrence, self.sub.id)
                update_bill(db, sub, sub.name, sub.amount_cents, sub.due_date, kind='bill')

    def test_reactivation_requires_amount_date_confirmation_and_updates_placeholder_in_place(self):
        self.post(state='inactive', charge_responsibility='not_owed', confirm_no_charge='yes')
        for fields in ({'amount':'20.01','due_date':'2027-03-01'},
                       {'amount':'bad','due_date':'2027-03-01','confirm_activation':'yes'},
                       {'amount':'20.01','due_date':'bad','confirm_activation':'yes'}):
            self.assertEqual(self.post(state='active', **fields).status_code, 400)
            self.assertEqual(self.saved().subscription_state, 'inactive')
        self.assertEqual(self.post(state='active', amount='20.01', due_date='2027-03-01', confirm_activation='yes').status_code, 303)
        saved = self.saved()
        self.assertEqual((saved.id, saved.subscription_state, saved.amount_cents, saved.due_date, saved.charge_is_owed),
                         (self.sub.id, 'active', 2001, date(2027, 3, 1), True))

    def test_reactivation_retains_unpaid_occurrence_and_does_not_repeat_new_charge(self):
        self.post(state='inactive', charge_responsibility='owed')
        self.assertEqual(self.post(state='active', amount='25', due_date='2027-01-10', confirm_activation='yes').status_code, 400)
        fields = dict(state='active', amount='25', due_date='2027-02-10', confirm_activation='yes')
        self.assertEqual(self.post(**fields).status_code, 303)
        self.assertEqual(self.saved().amount_cents, 1599)
        self.assertEqual(self.saved().subscription_state, 'inactive')
        with session_scope(self.engine) as db:
            subscriptions = [r for r in list_bills(db) if r.kind == 'subscription']
            self.assertEqual(len(subscriptions), 2)
            self.assertEqual(sum(r.funding_needed_cents for r in subscriptions), 4099)
        self.assertEqual(self.post(**fields).status_code, 400)

    def test_csrf_unknown_targets_and_successful_submission_token_consumed(self):
        self.assertEqual(self.client.post(self.path, data={'state':'inactive'}).status_code, 400)
        self.client.get(self.path)
        with self.client.session_transaction() as cookie:
            token = cookie['subscription_token_' + self.sub.id]
        data = {'token': token, 'state':'inactive','charge_responsibility':'owed'}
        self.assertEqual(self.client.post(self.path, data=data).status_code, 303)
        self.assertEqual(self.client.post(self.path, data=data).status_code, 400)
        self.assertEqual(self.client.get('/bills/missing/subscription').status_code, 404)
        self.assertEqual(self.client.get(f'/bills/{self.parent.id}/subscription').status_code, 404)

    def test_covered_unpaid_reactivation_preserves_old_charge_and_copies_account(self):
        with session_scope(self.engine) as db:
            account = create_account(db, 'Synthetic checking')
            old = db.get(BillOccurrence, self.sub.id)
            old.payment_account_id = account.id
            set_subscription_state(db, old, 'covered', charge_is_owed=True,
                                   covered_by_bill_id=self.parent.id)
        with session_scope(self.engine) as db:
            old = db.get(BillOccurrence, self.sub.id)
            new = set_subscription_state(db, old, 'active', amount_cents=2001,
                                         due_date=date(2027, 2, 10), confirm_activation=True)
            self.assertNotEqual(new.id, old.id)
            self.assertEqual((old.subscription_state, old.covered_by_bill_id,
                              old.amount_cents, old.due_date, old.charge_is_owed),
                             ('covered', self.parent.id, 1599, date(2027, 1, 10), True))
            self.assertEqual((new.subscription_state, new.covered_by_bill_id,
                              new.payment_account_id, new.funding_buffer_days,
                              new.funding_needed_cents), ('active', None, account.id, 3, 2001))
            history = list(db.scalars(select(SubscriptionChange).where(
                SubscriptionChange.bill_id == old.id)))
            activation = [json.loads(h.after_json) for h in history
                          if json.loads(h.after_json).get('id') == new.id]
            self.assertEqual(len(activation), 1)
            self.assertEqual(activation[0]['retained_unpaid_occurrence_id'], old.id)

    def test_failed_reactivation_rolls_back_new_occurrence_and_history(self):
        self.assertEqual(self.post(state='inactive', charge_responsibility='owed').status_code, 303)
        with self.assertRaises(RuntimeError):
            with session_scope(self.engine) as db:
                set_subscription_state(db, db.get(BillOccurrence, self.sub.id), 'active',
                                       amount_cents=2500, due_date=date(2027, 2, 10),
                                       confirm_activation=True)
                raise RuntimeError('Synthetic failure after new occurrence and history flush')
        with session_scope(self.engine) as db:
            self.assertEqual(len(list(db.scalars(select(BillOccurrence)))), 2)
            self.assertEqual(len(list(db.scalars(select(SubscriptionChange)))), 1)
            old = db.get(BillOccurrence, self.sub.id)
            self.assertEqual((old.subscription_state, old.funding_needed_cents), ('inactive', 1599))

    def test_database_constraints_reject_invalid_state_and_missing_cover_link(self):
        for statement in ("subscription_state='bad'", "subscription_state='covered'", "charge_is_owed=0"):
            with self.assertRaises(IntegrityError):
                with self.engine.begin() as conn:
                    conn.execute(text('UPDATE bill_occurrences SET '+statement+' WHERE id=:id'), {'id':self.sub.id})

    def test_failed_status_operation_rolls_back_state_and_history(self):
        with self.assertRaises(RuntimeError):
            with session_scope(self.engine) as db:
                set_subscription_state(db, db.get(BillOccurrence,self.sub.id), 'inactive', charge_is_owed=True)
                raise RuntimeError('Synthetic failure')
        self.assertEqual(self.saved().subscription_state, 'active')
        with session_scope(self.engine) as db:
            self.assertEqual(list(db.scalars(select(SubscriptionChange))), [])
