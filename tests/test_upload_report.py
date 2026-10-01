import unittest
from datetime import datetime

from upload_report import (
    UPLOAD_LOG_HEADER,
    build_transaction_report_rows,
    build_transaction_rows_html,
    build_upload_log_row,
)


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

        report_html = build_transaction_report_html(
            new_transactions,
            duplicate_transactions,
        )

        self.assertIn("<h3>Added Transactions</h3>", report_html)
        self.assertIn("<tr class='added-row'>", report_html)
        self.assertIn("<td>SHELL SERVICE</td>", report_html)
        self.assertIn("<h3>Skipped Duplicates</h3>", report_html)
        self.assertIn("<tr class='duplicate-row'>", report_html)
        self.assertIn("<td>APPLE.COM/BILL</td>", report_html)

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

    def test_builds_upload_log_row(self):
        self.assertEqual(
            UPLOAD_LOG_HEADER,
            [
                "Timestamp",
                "Month",
                "Files Uploaded",
                "Processed",
                "Added",
                "Duplicates",
                "Report File",
            ],
        )
        self.assertEqual(
            build_upload_log_row(
                datetime(2026, 9, 30, 14, 5, 6),
                "SEP",
                2,
                10,
                8,
                2,
                "transaction_report_SEP_20260930_140506.csv",
            ),
            [
                "2026-09-30 14:05:06",
                "SEP",
                2,
                10,
                8,
                2,
                "transaction_report_SEP_20260930_140506.csv",
            ],
        )

    def test_builds_transaction_rows_html(self):
        transactions = [
            {
                "date": datetime(2026, 9, 1),
                "amount": 42.1,
                "account": "SoFi Checking (2695)",
                "description": "SHELL SERVICE",
            },
        ]

        self.assertEqual(
            build_transaction_rows_html(transactions, "added-row"),
            (
                "<tr class='added-row'>"
                "<td>09/01/2026</td>"
                "<td>42.10</td>"
                "<td>SoFi Checking (2695)</td>"
                "<td>SHELL SERVICE</td>"
                "</tr>"
            ),
        )


if __name__ == "__main__":
    unittest.main()
