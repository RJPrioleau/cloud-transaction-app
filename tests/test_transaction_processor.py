import csv
import tempfile
import unittest
from pathlib import Path
from datetime import datetime

from openpyxl import Workbook

from transaction_processor import (
    build_existing_transaction_key,
    build_transaction_key,
    detect_account_from_filename,
    process_transactions,
    split_new_and_duplicate_transactions,
)


class ProcessTransactionsTests(unittest.TestCase):
    def test_detects_account_from_filename(self):
        self.assertEqual(
            detect_account_from_filename("SoFi Checking•2695.csv"),
            "SoFi Checking (2695)",
        )
        self.assertEqual(
            detect_account_from_filename("SoFi Savings•3475.csv"),
            "SoFi Savings (3475)",
        )
        self.assertEqual(
            detect_account_from_filename("unknown-account.csv"),
            None,
        )

    def test_builds_transaction_key_from_processed_item(self):
        item = {
            "date": datetime(2026, 9, 1),
            "amount": 42.1,
            "account": " SoFi Checking (2695) ",
            "description": " SHELL SERVICE ",
        }

        self.assertEqual(
            build_transaction_key(item),
            ("09/01/2026", "42.10", "sofi checking (2695)", "shell service"),
        )

    def test_builds_transaction_key_from_existing_sheet_row(self):
        row = [""] * 16
        row[7] = " 09/01/2026 "
        row[10] = "$42.10"
        row[14] = " SoFi Checking (2695) "
        row[15] = " SHELL SERVICE "

        self.assertEqual(
            build_existing_transaction_key(row),
            ("09/01/2026", "42.10", "sofi checking (2695)", "shell service"),
        )

    def test_splits_new_and_duplicate_transactions(self):
        existing_rows = [
            ["too short"],
            [""] * 16,
        ]
        existing_rows[1][7] = "09/01/2026"
        existing_rows[1][10] = "$42.10"
        existing_rows[1][14] = "SoFi Checking (2695)"
        existing_rows[1][15] = "SHELL SERVICE"

        transactions = [
            {
                "date": datetime(2026, 9, 1),
                "amount": 42.1,
                "account": "SoFi Checking (2695)",
                "description": "SHELL SERVICE",
            },
            {
                "date": datetime(2026, 9, 2),
                "amount": 5.99,
                "account": "SoFi Checking (2695)",
                "description": "APPLE.COM/BILL",
            },
        ]

        new_transactions, duplicate_transactions = split_new_and_duplicate_transactions(
            existing_rows,
            transactions,
        )

        self.assertEqual(new_transactions, [transactions[1]])
        self.assertEqual(duplicate_transactions, [transactions[0]])

    def test_processes_csv_transactions_with_categories_and_sorted_dates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "Checking-2695.csv"

            with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=["Date", "Description", "Amount"])
                writer.writeheader()
                writer.writerow({
                    "Date": "2026-09-02",
                    "Description": "SHELL SERVICE",
                    "Amount": "-42.10",
                })
                writer.writerow({
                    "Date": "2026-09-01",
                    "Description": "APPLE.COM/BILL",
                    "Amount": "-5.99",
                })

            rows = process_transactions(str(csv_path), "SoFi Checking (2695)", "SEP")

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["date"].strftime("%m/%d/%Y"), "09/01/2026")
        self.assertEqual(rows[0]["budget_name"], "Apple Music")
        self.assertEqual(rows[0]["amount"], 5.99)
        self.assertEqual(rows[0]["account"], "SoFi Checking (2695)")
        self.assertEqual(rows[1]["date"].strftime("%m/%d/%Y"), "09/02/2026")
        self.assertEqual(rows[1]["budget_name"], "Gas")
        self.assertEqual(rows[1]["amount"], 42.10)

    def test_processes_xlsx_transactions_with_alternate_headers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            xlsx_path = Path(temp_dir) / "Savings-3475.xlsx"
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.append(["Posted Date", "Memo", "Debit"])
            worksheet.append(["09/03/2026", "WAL-MART SUPERCENTER", 125.40])
            workbook.save(xlsx_path)

            rows = process_transactions(str(xlsx_path), "SoFi Savings (3475)", "SEP")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"].strftime("%m/%d/%Y"), "09/03/2026")
        self.assertEqual(rows[0]["budget_name"], "Groceries/household items")
        self.assertEqual(rows[0]["amount"], 125.40)
        self.assertEqual(rows[0]["description"], "WAL-MART SUPERCENTER")
        self.assertEqual(rows[0]["account"], "SoFi Savings (3475)")


if __name__ == "__main__":
    unittest.main()
