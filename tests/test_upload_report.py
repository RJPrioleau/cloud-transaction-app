import unittest
from datetime import datetime

from upload_report import build_transaction_report_rows


class UploadReportTests(unittest.TestCase):
    def test_builds_transaction_report_rows_with_added_then_duplicates(self):
        new_transactions = [
            {
                "date": datetime(2026, 9, 1),
                "amount": 42.1,
                "account": "SoFi Checking (2695)",
                "description": "SHELL SERVICE",
            },
        ]
        duplicate_transactions = [
            {
                "date": datetime(2026, 9, 2),
                "amount": 5.99,
                "account": "SoFi Checking (2695)",
                "description": "APPLE.COM/BILL",
            },
        ]

        self.assertEqual(
            build_transaction_report_rows(new_transactions, duplicate_transactions),
            [
                ["Status", "Date", "Amount", "Account", "Description"],
                [
                    "ADDED",
                    "09/01/2026",
                    "42.10",
                    "SoFi Checking (2695)",
                    "SHELL SERVICE",
                ],
                [
                    "DUPLICATE",
                    "09/02/2026",
                    "5.99",
                    "SoFi Checking (2695)",
                    "APPLE.COM/BILL",
                ],
            ],
        )


if __name__ == "__main__":
    unittest.main()
