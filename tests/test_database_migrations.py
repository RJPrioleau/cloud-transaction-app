from datetime import date
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from database import PROJECT_ROOT, backup_sqlite_database, create_database_engine, session_scope
from income_repository import (
    create_income_source, create_official_pay_date,
    list_income_sources, list_official_pay_dates,
)
from bill_repository import create_bill, list_bills
from account_repository import create_account, list_accounts


class DatabaseMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.path = self.root / "synthetic income % calendar.sqlite3"
        self.url = "sqlite:///" + str(self.path)
        self.config = self.migration_config(self.url)

    def migration_config(self, url):
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        config.attributes["database_url"] = url
        return config

    def test_module_imports_do_not_create_database_or_parent_directory(self):
        environment = dict(os.environ)
        environment["DATABASE_URL"] = "sqlite:///" + str(self.root / "not-created" / "income.sqlite3")
        result = subprocess.run(
            [sys.executable, "-c", "import database, income_models, income_repository, bill_models, bill_repository, bill_routes"],
            cwd=PROJECT_ROOT, env=environment, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_upgrade_creates_only_initial_records_and_repeat_preserves_data(self):
        command.upgrade(self.config, "head")
        engine = create_database_engine(self.url)
        try:
            self.assertEqual(set(inspect(engine).get_table_names()), {
                "alembic_version", "income_sources", "official_pay_dates", "bill_occurrences", "payment_accounts",
            })
            self.assertEqual(
                {c["name"] for c in inspect(engine).get_columns("official_pay_dates")},
                {"id", "income_source_id", "official_pay_date", "pay_period_start", "pay_period_end",
                 "source_reference", "review_status", "created_at", "expected_net_override_cents"},
            )
            with session_scope(engine) as session:
                source = create_income_source(session, "Example Employer")
                payday = create_official_pay_date(session, source.id, date(2027, 1, 8))
            command.upgrade(self.config, "head")
            with session_scope(engine) as session:
                self.assertEqual(list_income_sources(session)[0].id, source.id)
                self.assertEqual(list_official_pay_dates(session, source.id)[0].id, payday.id)
        finally:
            engine.dispose()

    def test_empty_schema_can_downgrade_and_upgrade_again(self):
        command.upgrade(self.config, "head")
        command.downgrade(self.config, "base")
        engine = create_database_engine(self.url)
        try:
            self.assertNotIn("income_sources", inspect(engine).get_table_names())
            self.assertNotIn("official_pay_dates", inspect(engine).get_table_names())
        finally:
            engine.dispose()
        command.upgrade(self.config, "head")
        engine = create_database_engine(self.url)
        try:
            self.assertIn("official_pay_dates", inspect(engine).get_table_names())
        finally:
            engine.dispose()

    def test_migrated_schema_matches_declared_models(self):
        command.upgrade(self.config, "head")
        with redirect_stdout(io.StringIO()):
            command.check(self.config)

    def test_amount_migration_preserves_existing_calendar_and_enforces_nonnegative(self):
        command.upgrade(self.config, "0001_income_calendar")
        engine = create_database_engine(self.url)
        try:
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO income_sources (id,name,created_at) VALUES ('s','Example','2026-01-01')"))
                connection.execute(text("INSERT INTO official_pay_dates (id,income_source_id,official_pay_date,created_at,review_status) VALUES ('p','s','2026-11-06','2026-01-01','draft')"))
            command.upgrade(self.config, "head")
            with engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT id, expected_net_cents FROM income_sources")).one(), ('s', None))
                self.assertEqual(connection.execute(text("SELECT id, income_source_id, official_pay_date, expected_net_override_cents FROM official_pay_dates")).one(), ('p', 's', '2026-11-06', None))
            from sqlalchemy.exc import IntegrityError
            for statement in ("UPDATE income_sources SET expected_net_cents=-1", "UPDATE official_pay_dates SET expected_net_override_cents=-1"):
                with self.assertRaises(IntegrityError):
                    with engine.begin() as connection:
                        connection.execute(text(statement))
            command.upgrade(self.config, "head")
            # On a synthetic populated database, removing only amount columns preserves identity.
            command.downgrade(self.config, "0001_income_calendar")
            with engine.connect() as connection:
                self.assertEqual(connection.scalar(text("SELECT id FROM official_pay_dates")), 'p')
            command.upgrade(self.config, "head")
        finally:
            engine.dispose()

    def test_backup_restores_records_relationships_and_migration_version_after_source_loss(self):
        command.upgrade(self.config, "head")
        engine = create_database_engine(self.url)
        backup_path = self.root / "backup.sqlite3"
        try:
            with session_scope(engine) as session:
                source = create_income_source(session, "Example Employer")
                payday = create_official_pay_date(
                    session, source.id, date(2027, 1, 8),
                    date(2026, 12, 21), date(2027, 1, 3), "Synthetic official calendar",
                )
                source.expected_net_cents = 123456
                payday.expected_net_override_cents = 125001
                bill = create_bill(session, "Synthetic bill", 12345, date(2027, 1, 2), kind="subscription")
                account = create_account(session, "Synthetic account")
                bill.payment_account_id = account.id
            backup_sqlite_database(engine, backup_path)
        finally:
            engine.dispose()
        # Only a synthetic database in this test's temporary directory is removed.
        self.path.unlink()
        restored_path = self.root / "restored.sqlite3"
        shutil.copy2(backup_path, restored_path)
        restored_url = "sqlite:///" + str(restored_path)
        command.upgrade(self.migration_config(restored_url), "head")
        restored = create_database_engine(restored_url)
        try:
            with session_scope(restored) as session:
                self.assertEqual(list_income_sources(session)[0].id, source.id)
                self.assertEqual(list_income_sources(session)[0].expected_net_cents, 123456)
                saved = list_official_pay_dates(session, source.id)[0]
                self.assertEqual(saved.expected_net_override_cents, 125001)
                restored_bill = list_bills(session)[0]
                self.assertEqual(restored_bill.kind, "subscription")
                self.assertEqual(restored_bill.payment_account_id, account.id)
                self.assertEqual(restored_bill.payment_account.name, "Synthetic account")
                self.assertEqual(list_accounts(session)[0].id, account.id)
                self.assertEqual((restored_bill.id, restored_bill.name, restored_bill.amount_cents,
                                  restored_bill.due_date, restored_bill.funding_deadline),
                                 (bill.id, "Synthetic bill", 12345, date(2027, 1, 2), date(2026, 12, 30)))
                self.assertEqual(
                    (saved.id, saved.income_source_id, saved.official_pay_date, saved.pay_period_start,
                     saved.pay_period_end, saved.source_reference, saved.review_status, saved.created_at),
                    (payday.id, source.id, date(2027, 1, 8), date(2026, 12, 21), date(2027, 1, 3),
                     "Synthetic official calendar", "draft", payday.created_at),
                )
            with restored.connect() as connection:
                self.assertEqual(connection.scalar(text("PRAGMA integrity_check")), "ok")
                self.assertEqual(connection.execute(text("PRAGMA foreign_key_check")).all(), [])
                self.assertEqual(connection.scalar(text("SELECT version_num FROM alembic_version")), "0005_payment_accounts")
        finally:
            restored.dispose()

    def test_backup_refuses_to_replace_source_or_existing_backup(self):
        command.upgrade(self.config, "head")
        engine = create_database_engine(self.url)
        try:
            with self.assertRaises(FileExistsError):
                backup_sqlite_database(engine, self.path)
            destination = self.root / "already-exists.sqlite3"
            destination.write_bytes(b"preserve existing file")
            with self.assertRaises(FileExistsError):
                backup_sqlite_database(engine, destination)
            self.assertEqual(destination.read_bytes(), b"preserve existing file")
        finally:
            engine.dispose()

    def test_bill_migration_preserves_populated_income_and_repeat_upgrade_preserves_bills(self):
        command.upgrade(self.config, "0002_expected_net_pay")
        engine = create_database_engine(self.url)
        try:
            with session_scope(engine) as db:
                source = create_income_source(db, "Example")
                source.expected_net_cents = 123456
                payday = create_official_pay_date(db, source.id, date(2027, 1, 8))
                payday.expected_net_override_cents = 120001
            with engine.connect() as connection:
                before_source = connection.execute(text("SELECT * FROM income_sources")).all()
                before_dates = connection.execute(text("SELECT * FROM official_pay_dates")).all()
            command.upgrade(self.config, "head")
            with engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT * FROM income_sources")).all(), before_source)
                self.assertEqual(connection.execute(text("SELECT * FROM official_pay_dates")).all(), before_dates)
            with session_scope(engine) as db:
                bill = create_bill(db, "Example bill", 12345, date(2027, 1, 2))
            command.upgrade(self.config, "head")
            with session_scope(engine) as db:
                self.assertEqual(list_bills(db)[0].id, bill.id)
        finally:
            engine.dispose()

    def test_kind_migration_preserves_old_bills_and_defaults_their_classification(self):
        command.upgrade(self.config, "0003_bill_occurrences")
        engine = create_database_engine(self.url)
        try:
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO bill_occurrences (id,name,amount_cents,due_date,funding_buffer_days,created_at) VALUES ('old','Existing bill',12345,'2027-01-02',5,'2026-01-01')"))
            old_columns = "id,name,amount_cents,due_date,funding_buffer_days,created_at"
            with engine.connect() as conn:
                before = conn.execute(text('SELECT '+old_columns+' FROM bill_occurrences')).all()
            command.upgrade(self.config, "head")
            command.upgrade(self.config, "head")
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text('SELECT '+old_columns+' FROM bill_occurrences')).all(), before)
                self.assertEqual(conn.scalar(text('SELECT kind FROM bill_occurrences')), 'bill')
            command.downgrade(self.config, "0003_bill_occurrences")
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text('SELECT '+old_columns+' FROM bill_occurrences')).all(), before)
            command.upgrade(self.config, "head")
        finally:
            engine.dispose()

    def test_account_migration_preserves_obligation_fields_and_starts_unassigned(self):
        command.upgrade(self.config, "0004_bill_subscription_kind")
        engine = create_database_engine(self.url)
        try:
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO bill_occurrences (id,name,kind,amount_cents,due_date,funding_buffer_days,created_at) VALUES ('old','Example subscription','subscription',1599,'2027-02-01',5,'2026-01-01')"))
            columns = 'id,name,kind,amount_cents,due_date,funding_buffer_days,created_at'
            with engine.connect() as conn:
                before = conn.execute(text('SELECT '+columns+' FROM bill_occurrences')).all()
            command.upgrade(self.config, 'head')
            command.upgrade(self.config, 'head')
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text('SELECT '+columns+' FROM bill_occurrences')).all(), before)
                self.assertIsNone(conn.scalar(text('SELECT payment_account_id FROM bill_occurrences')))
                self.assertEqual(conn.scalar(text('SELECT count(*) FROM payment_accounts')), 0)
                self.assertEqual(conn.execute(text('PRAGMA foreign_key_check')).all(), [])
            command.downgrade(self.config, '0004_bill_subscription_kind')
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text('SELECT '+columns+' FROM bill_occurrences')).all(), before)
            command.upgrade(self.config, 'head')
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
