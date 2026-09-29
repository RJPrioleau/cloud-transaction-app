import csv
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from transaction_processor import process_transactions


class ProcessTransactionsTests(unittest.TestCase):
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
