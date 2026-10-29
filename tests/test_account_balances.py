from datetime import date, datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from alembic import command
from alembic.config import Config
from flask import Flask
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from account_models import AccountBalance, PaymentAccount
from account_repository import (create_account, update_account, record_balance,
                                balance_history, latest_balances)
from account_routes import accounts
from bill_repository import create_bill
from bill_models import BillOccurrence
from bill_routes import bills
from database import PROJECT_ROOT, backup_sqlite_database, create_database_engine, session_scope
from income_routes import income


class AccountBalanceTests(unittest.TestCase):
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
            self.account = create_account(db, 'Synthetic checking')
        self.path = f'/accounts/{self.account.id}'

    def token(self, path='/accounts', key='account_form_token'):
        self.client.get(path)
        with self.client.session_transaction() as cookie:
            return cookie[key]

    def detail_post(self, **values):
        token = self.token(self.path, 'account_detail_token_' + self.account.id)
        return self.client.post(self.path, data={'token': token, **values})

    def test_account_without_balance_is_unknown_and_explicit_zero_is_preserved(self):
        self.assertIn(b'Not recorded', self.client.get('/accounts').data)
        with session_scope(self.engine) as db:
            self.assertEqual(latest_balances(db), {})
            record_balance(db, self.account, 0, date.today())
        self.assertIn(b'$0.00', self.client.get('/accounts').data)
        self.assertIn(b'Recorded balance: $0.00', self.client.get(self.path).data)

    def test_snapshot_corrections_backdates_and_account_vault_balances_are_separate(self):
        with session_scope(self.engine) as db:
            vault = create_account(db, 'Emergency vault', 'vault', 'Emergency savings')
            old = record_balance(db, self.account, 10000, date(2026, 1, 2))
            correction = record_balance(db, self.account, 9000, date(2026, 1, 2))
            old.created_at = correction.created_at = datetime(2026, 1, 2)
            record_balance(db, self.account, 50000, date(2026, 1, 1))
            record_balance(db, vault, 20000, date(2026, 1, 2))
            latest = latest_balances(db)
            self.assertEqual(latest[self.account.id].amount_cents, 9000)
            self.assertEqual(latest[vault.id].amount_cents, 20000)
            self.assertEqual(len(balance_history(db, self.account.id)), 3)

    def test_rename_type_and_purpose_preserve_balance_history_and_bill_links(self):
        with session_scope(self.engine) as db:
            account = db.get(PaymentAccount, self.account.id)
            created_at = account.created_at
            snapshot = record_balance(db, account, 12345, date.today())
            bill = create_bill(db, 'Synthetic bill', 1234, date.today(), 0, payment_account_id=account.id)
            update_account(db, account, 'Renamed vault', 'vault', 'Car insurance')
        with session_scope(self.engine) as db:
            account = db.get(PaymentAccount, self.account.id)
            self.assertEqual((account.created_at, account.kind, account.purpose), (created_at, 'vault', 'Car insurance'))
            self.assertEqual(balance_history(db, account.id)[0].id, snapshot.id)
            self.assertEqual(db.get(BillOccurrence, bill.id).payment_account_id, account.id)
        self.assertIn(b'Renamed vault', self.client.get('/bills').data)

    def test_creation_with_balance_is_atomic_and_replay_is_rejected(self):
        token = self.token()
        fields = dict(token=token, name='Synthetic vault', kind='vault', purpose='Savings',
                      balance='123.45', balance_date=date.today().isoformat())
        self.assertEqual(self.client.post('/accounts', data=fields).status_code, 400)
        fields['confirm_balance'] = 'yes'
        self.assertEqual(self.client.post('/accounts', data=fields).status_code, 303)
        self.assertEqual(self.client.post('/accounts', data=fields).status_code, 400)
        with session_scope(self.engine) as db:
            vaults = list(db.scalars(select(PaymentAccount).where(PaymentAccount.kind == 'vault')))
            self.assertEqual(len(vaults), 1)
            self.assertEqual(latest_balances(db)[vaults[0].id].amount_cents, 12345)

    def test_balance_route_retains_invalid_values_and_consumes_success_token(self):
        self.assertEqual(self.client.post(self.path, data={}).status_code, 400)
        response = self.detail_post(action='balance', balance='12.345', balance_date=date.today().isoformat(), confirm_balance='yes')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'value="12.345"', response.data)
        token = self.token(self.path, 'account_detail_token_' + self.account.id)
        values = dict(token=token, action='balance', balance='12.34', balance_date=date.today().isoformat(), confirm_balance='yes')
        self.assertEqual(self.client.post(self.path, data=values).status_code, 303)
        self.assertEqual(self.client.post(self.path, data=values).status_code, 400)
        self.assertEqual(self.client.get('/accounts/missing').status_code, 404)

    def test_validation_and_rollback(self):
        for amount, day in ((None, date.today()), (-1, date.today()), (True, date.today()),
                            (1.1, date.today()), (1, datetime.now()), (1, date.today() + timedelta(days=1))):
            with self.assertRaises(ValueError):
                with session_scope(self.engine) as db:
                    record_balance(db, self.account, amount, day)
        for kind, purpose in (('other', 'Savings'), ('vault', ''), ('vault', 'x' * 201)):
            with self.assertRaises(ValueError):
                with session_scope(self.engine) as db:
                    create_account(db, 'Bad entry', kind, purpose)
        with self.assertRaises(RuntimeError):
            with session_scope(self.engine) as db:
                record_balance(db, self.account, 12345, date.today())
                raise RuntimeError('Synthetic failure after balance flush')
        with session_scope(self.engine) as db:
            self.assertEqual(balance_history(db, self.account.id), [])

    def test_metadata_and_notes_are_escaped(self):
        response = self.detail_post(action='details', name='<Vault>', kind='vault', purpose='<Savings>')
        self.assertEqual(response.status_code, 303)
        self.detail_post(action='balance', balance='1', balance_date=date.today().isoformat(),
                         confirm_balance='yes', note='<Correction>')
        html = self.client.get(self.path).data
        self.assertIn(b'&lt;Vault&gt;', html)
        self.assertIn(b'&lt;Savings&gt;', html)
        self.assertIn(b'&lt;Correction&gt;', html)

    def test_database_constraints_enforce_vault_purpose_and_balance_references(self):
        for statement in ("kind='bad'", "kind='vault',purpose=NULL", "kind='vault',purpose=' '"):
            with self.assertRaises(IntegrityError):
                with self.engine.begin() as conn:
                    conn.execute(text('UPDATE payment_accounts SET '+statement+' WHERE id=:id'), {'id': self.account.id})
        for account_id, amount in ((self.account.id, -1), ('missing', 100)):
            with self.assertRaises(IntegrityError):
                with session_scope(self.engine) as db:
                    db.add(AccountBalance(account_id=account_id, amount_cents=amount, balance_date=date.today()))

    def test_populated_backup_and_guarded_downgrade(self):
        with session_scope(self.engine) as db:
            account = db.get(PaymentAccount, self.account.id)
            update_account(db, account, 'Vault', 'vault', 'Savings')
            snapshot = record_balance(db, account, 98765, date.today(), 'Synthetic opening balance')
        backup = self.root / 'backup.sqlite3'
        backup_sqlite_database(self.engine, backup)
        restored = create_database_engine('sqlite:///' + str(backup))
        try:
            with session_scope(restored) as db:
                self.assertEqual(db.get(PaymentAccount, self.account.id).purpose, 'Savings')
                self.assertEqual(balance_history(db, self.account.id)[0].id, snapshot.id)
                self.assertEqual(latest_balances(db)[self.account.id].amount_cents, 98765)
            with restored.connect() as conn:
                self.assertEqual(conn.scalar(text('PRAGMA integrity_check')), 'ok')
                self.assertEqual(conn.execute(text('PRAGMA foreign_key_check')).all(), [])
        finally:
            restored.dispose()
        with self.assertRaises(RuntimeError):
            command.downgrade(self.config, '0008_monthly_bills')
        with self.engine.connect() as conn:
            self.assertEqual(conn.scalar(text('SELECT version_num FROM alembic_version')), '0009_account_balances')

    def test_migration_preserves_account_id_and_existing_bill_references_without_inventing_balances(self):
        with session_scope(self.engine) as db:
            bill = create_bill(db, 'Synthetic bill', 100, date.today(), 0, payment_account_id=self.account.id)
        command.downgrade(self.config, '0008_monthly_bills')
        with self.engine.connect() as conn:
            accounts_before = conn.execute(text('SELECT id,name,created_at FROM payment_accounts')).all()
            bills_before = conn.execute(text('SELECT * FROM bill_occurrences')).all()
        command.upgrade(self.config, 'head')
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text('SELECT id,name,created_at FROM payment_accounts')).all(), accounts_before)
            self.assertEqual(conn.execute(text('SELECT * FROM bill_occurrences')).all(), bills_before)
            self.assertEqual(conn.scalar(text('SELECT kind FROM payment_accounts')), 'account')
            self.assertEqual(conn.scalar(text('SELECT count(*) FROM account_balances')), 0)
            self.assertEqual(conn.execute(text('PRAGMA foreign_key_check')).all(), [])
