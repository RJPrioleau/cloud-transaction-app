from datetime import date, datetime
from pathlib import Path
import tempfile
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from database import PROJECT_ROOT, create_database_engine, session_scope
from income_models import IncomeSource, OfficialPayDate
from income_repository import (
    create_income_source, create_official_pay_date,
    list_income_sources, list_official_pay_dates,
)


class IncomeRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.url = "sqlite:///" + str(Path(self.temporary_directory.name) / "income.sqlite3")
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        config.attributes["database_url"] = self.url
        command.upgrade(config, "head")
        self.engine = create_database_engine(self.url)
        self.addCleanup(self.engine.dispose)

    def test_records_survive_reopening_with_stable_ids_dates_and_timestamps(self):
        with session_scope(self.engine) as session:
            source = create_income_source(session, "  Example Employer  ")
            payday = create_official_pay_date(
                session, source.id, date(2027, 1, 8),
                date(2026, 12, 21), date(2027, 1, 3), "Synthetic calendar, page 1",
            )
        self.engine.dispose()
        reopened = create_database_engine(self.url)
        try:
            with session_scope(reopened) as session:
                sources = list_income_sources(session)
                dates = list_official_pay_dates(session, source.id)
                self.assertEqual([(row.id, row.name) for row in sources], [(source.id, "Example Employer")])
                self.assertEqual(len(dates), 1)
                saved = dates[0]
                self.assertEqual(saved.id, payday.id)
                self.assertEqual(saved.official_pay_date, date(2027, 1, 8))
                self.assertEqual(saved.pay_period_start, date(2026, 12, 21))
                self.assertEqual(saved.pay_period_end, date(2027, 1, 3))
                self.assertEqual(saved.source_reference, "Synthetic calendar, page 1")
                self.assertEqual(saved.review_status, "draft")
                self.assertEqual(saved.created_at, payday.created_at)
                self.assertEqual(sources[0].created_at, source.created_at)
        finally:
            reopened.dispose()

    def test_sources_are_isolated_and_pay_dates_are_returned_chronologically(self):
        with session_scope(self.engine) as session:
            first = create_income_source(session, "Example Employer")
            second = create_income_source(session, "Example Benefits")
            create_official_pay_date(session, first.id, date(2027, 1, 22))
            create_official_pay_date(session, second.id, date(2027, 1, 1))
            create_official_pay_date(session, first.id, date(2027, 1, 8))
        with session_scope(self.engine) as session:
            self.assertEqual(
                [row.official_pay_date for row in list_official_pay_dates(session, first.id)],
                [date(2027, 1, 8), date(2027, 1, 22)],
            )
            self.assertEqual(len(list_official_pay_dates(session, second.id)), 1)
            self.assertEqual(list_official_pay_dates(session, "unknown-source"), [])

    def test_source_names_are_validated_before_persistence(self):
        for name in (None, "", "   ", "\t\n", "x" * 201):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    with session_scope(self.engine) as session:
                        create_income_source(session, name)
        with session_scope(self.engine) as session:
            self.assertEqual(list_income_sources(session), [])

    def test_invalid_periods_and_non_date_inputs_are_rejected(self):
        with session_scope(self.engine) as session:
            source = create_income_source(session, "Example Employer")
        invalid = [
            {"official_pay_date": None},
            {"official_pay_date": "2027-01-08"},
            {"official_pay_date": datetime(2027, 1, 8)},
            {"official_pay_date": date(2027, 1, 8), "pay_period_start": "2027-01-01"},
            {"official_pay_date": date(2027, 1, 8), "pay_period_start": date(2027, 1, 2),
             "pay_period_end": date(2027, 1, 1)},
        ]
        for arguments in invalid:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    with session_scope(self.engine) as session:
                        create_official_pay_date(session, source.id, **arguments)
        with session_scope(self.engine) as session:
            self.assertEqual(list_official_pay_dates(session, source.id), [])

    def test_missing_source_is_rejected_by_foreign_key_constraint(self):
        with self.assertRaises(IntegrityError):
            with session_scope(self.engine) as session:
                create_official_pay_date(session, "nonexistent-source", date(2027, 1, 8))

    def test_failed_operation_rolls_back_already_flushed_records(self):
        with self.assertRaisesRegex(RuntimeError, "Synthetic failure"):
            with session_scope(self.engine) as session:
                source = create_income_source(session, "Example Employer")
                create_official_pay_date(session, source.id, date(2027, 1, 8))
                raise RuntimeError("Synthetic failure after both records were flushed")
        with session_scope(self.engine) as session:
            self.assertEqual(list_income_sources(session), [])
            self.assertEqual(list_official_pay_dates(session, source.id), [])

    def test_database_constraints_protect_draft_semantics_and_period_order(self):
        with session_scope(self.engine) as session:
            source = create_income_source(session, "Example Employer")
        for changes in (
            {"review_status": "confirmed"},
            {"pay_period_start": date(2027, 1, 2), "pay_period_end": date(2027, 1, 1)},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(IntegrityError):
                    with self.engine.begin() as connection:
                        connection.execute(insert(OfficialPayDate).values(
                            income_source_id=source.id, official_pay_date=date(2027, 1, 8), **changes
                        ))
        with self.assertRaises(IntegrityError):
            with self.engine.begin() as connection:
                connection.execute(insert(IncomeSource).values(name="   "))


if __name__ == "__main__":
    unittest.main()
