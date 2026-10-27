import csv
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from upload_report import (
    UPLOAD_LOG_HEADER,
    build_budget_summary,
    build_misc_review,
    append_upload_log_csv,
    build_transaction_report_rows,
    build_transaction_rows_html,
    build_upload_log_row,
    build_transaction_report_html,
    write_transaction_report_csv,
)


class UploadReportTests(unittest.TestCase):
    def test_misc_review_groups_exact_descriptions_and_excludes_other_categories(self):
        added = [
            {"budget_name": "MISC", "description": "Example Store", "amount": 0.1},
            {"budget_name": "MISC", "description": "Example Store", "amount": 0.2},
            {"budget_name": "MISC", "description": "example store", "amount": 2},
            {"budget_name": "Gas", "description": "Example Store", "amount": 42.1},
        ]
        duplicates = [
            {"budget_name": "MISC", "description": "Example Store", "amount": 5},
            {"budget_name": "MISC", "description": "Another Store", "amount": 7},
            {"budget_name": "Round up Transfer", "description": "Roundup Example", "amount": 0.57},
        ]

        self.assertEqual(build_misc_review(added, duplicates), [
            {"description": "Another Store", "added_count": 0, "added_total": Decimal("0"),
             "duplicate_count": 1, "duplicate_total": Decimal("7")},
            {"description": "Example Store", "added_count": 2, "added_total": Decimal("0.3"),
             "duplicate_count": 1, "duplicate_total": Decimal("5")},
            {"description": "example store", "added_count": 1, "added_total": Decimal("2"),
             "duplicate_count": 0, "duplicate_total": Decimal("0")},
        ])

    def test_misc_review_is_empty_when_no_misc_transactions_exist(self):
        self.assertEqual(build_misc_review([], []), [])
        self.assertEqual(build_misc_review([
            {"budget_name": "Gas", "description": "Example", "amount": 10}
        ], []), [])

    def test_budget_summary_groups_statuses_and_sums_decimal_amounts(self):
        added = [
            {"budget_name": "Round up Transfer", "amount": 0.1},
            {"budget_name": "MISC", "amount": 10},
            {"budget_name": "Round up Transfer", "amount": 0.2},
        ]
        duplicates = [
            {"budget_name": "Round up Transfer", "amount": 0.57},
            {"budget_name": "Gas", "amount": 42.1},
        ]

        self.assertEqual(build_budget_summary(added, duplicates), [
            {"budget_name": "Gas", "added_count": 0, "added_total": Decimal("0"),
             "duplicate_count": 1, "duplicate_total": Decimal("42.1")},
            {"budget_name": "MISC", "added_count": 1, "added_total": Decimal("10"),
             "duplicate_count": 0, "duplicate_total": Decimal("0")},
            {"budget_name": "Round up Transfer", "added_count": 2, "added_total": Decimal("0.3"),
             "duplicate_count": 1, "duplicate_total": Decimal("0.57")},
        ])

    def test_budget_summary_is_empty_without_transactions(self):
        self.assertEqual(build_budget_summary([], []), [])

    def test_appends_upload_log_entries_without_repeating_header(self):
        first_row = ["2026-09-01 12:00:00", "SEP", 1, 2, 1, 1, "first.csv"]
        second_row = ["2026-09-02 12:00:00", "SEP", 1, 1, 0, 1, 'café, "report".csv']

        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "upload_log.csv"

            append_upload_log_csv(log_path, first_row)
            append_upload_log_csv(log_path, second_row)

            with log_path.open(newline="", encoding="utf-8") as log_file:
                rows = list(csv.reader(log_file))

        self.assertEqual(rows, [
            UPLOAD_LOG_HEADER,
            [str(value) for value in first_row],
            [str(value) for value in second_row],
        ])

    def test_writes_utf8_csv_with_quoted_fields_and_replaces_previous_content(self):
        description = 'CAFÉ, "CORNER"\nSERVICE'
        transactions = [{
            "date": datetime(2026, 9, 1),
            "amount": 42.1,
            "account": "Example Checking",
            "description": description,
            "budget_name": "MISC",
        }]

        with tempfile.TemporaryDirectory() as temporary_directory:
            report_path = Path(temporary_directory) / "report.csv"
            report_path.write_text("previous report content", encoding="utf-8")

            write_transaction_report_csv(report_path, transactions, [])

            with report_path.open(newline="", encoding="utf-8") as report_file:
                rows = list(csv.reader(report_file))

        self.assertEqual(rows, [
            ["Status", "Date", "Amount", "Account", "Description", "Budget Name"],
            ["ADDED", "09/01/2026", "42.10", "Example Checking", description, "MISC"],
        ])

    def test_builds_transaction_report_rows_with_added_then_duplicates(self):
        new_transactions = [
            {
                "date": datetime(2026, 9, 1),
                "amount": 42.1,
                "account": "SoFi Checking (2695)",
                "description": "SHELL SERVICE",
                "budget_name": "Gas",
            },
        ]
        duplicate_transactions = [
            {
                "date": datetime(2026, 9, 2),
                "amount": 5.99,
                "account": "SoFi Checking (2695)",
                "description": "APPLE.COM/BILL",
                "budget_name": "Apple Music",
            },
        ]

        self.assertEqual(
            build_transaction_report_rows(new_transactions, duplicate_transactions),
            [
                ["Status", "Date", "Amount", "Account", "Description", "Budget Name"],
                [
                    "ADDED",
                    "09/01/2026",
                    "42.10",
                    "SoFi Checking (2695)",
                    "SHELL SERVICE",
                    "Gas",
                ],
                [
                    "DUPLICATE",
                    "09/02/2026",
                    "5.99",
                    "SoFi Checking (2695)",
                    "APPLE.COM/BILL",
                    "Apple Music",
                ],
            ],
        )

    def test_builds_html_report_with_added_and_duplicate_transactions(self):
        new_transactions = [
            {
                "date": datetime(2026, 9, 1),
                "amount": 42.1,
                "account": "SoFi Checking (2695)",
                "description": "SHELL SERVICE",
                "budget_name": "Gas",
            },
        ]
        duplicate_transactions = [
            {
                "date": datetime(2026, 9, 2),
                "amount": 5.99,
                "account": "SoFi Checking (2695)",
                "description": "APPLE.COM/BILL",
                "budget_name": "Apple Music",
            },
        ]

        report_html = build_transaction_report_html(
            new_transactions,
            duplicate_transactions,
        )

        self.assertIn("<h3>Added Transactions</h3>", report_html)
        self.assertEqual(report_html.count("<th>Budget Name</th>"), 2)
        self.assertIn("<td>Gas</td>", report_html)
        self.assertIn("<td>Apple Music</td>", report_html)
        self.assertIn("<tr class='added-row'>", report_html)
        self.assertIn("<td>SHELL SERVICE</td>", report_html)
        self.assertIn("<h3>Skipped Duplicates</h3>", report_html)
        self.assertIn("<tr class='duplicate-row'>", report_html)
        self.assertIn("<td>APPLE.COM/BILL</td>", report_html)

    def test_builds_html_report_without_transactions(self):
        report_html = build_transaction_report_html([], [])

        self.assertIn(
            "<h3>Added Transactions</h3>"
            "<p>No new transactions were added.</p>",
            report_html
        )
        self.assertIn("<h3>Skipped Duplicates</h3>", report_html)
        self.assertNotIn("<tr class='added-row'>", report_html)
        self.assertNotIn("<tr class='duplicate-row'>", report_html)

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
                "budget_name": "Gas",
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
                "<td>Gas</td>"
                "</tr>"
            ),
        )


if __name__ == "__main__":
    unittest.main()
