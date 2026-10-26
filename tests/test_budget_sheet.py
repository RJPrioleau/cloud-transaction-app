import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from budget_sheet import (
    clear_test_imports,
    build_transaction_batch_updates,
    find_first_empty_transaction_row,
    import_transactions_to_worksheet,
    open_budget_worksheet,
)


class BudgetSheetTests(unittest.TestCase):
    def test_reset_clears_only_import_constants_within_test_boundary(self):
        worksheet = Mock(title="TEST")
        rows = [[""] * 9 for _ in range(316)]
        rows[0] = ["09/01/2026", "Gas", "preserve J", 0, "preserve L", "", "preserve N", "Checking", "Example"]
        rows[1][0] = "=TODAY()"
        rows[2][0] = "09/03/2026"
        rows[314][0] = "09/30/2026"
        rows[315][0] = "outside reset boundary"
        worksheet.get.return_value = rows

        clear_test_imports(worksheet)

        worksheet.get.assert_called_once_with("H69:P383", value_render_option="FORMULA")
        worksheet.batch_clear.assert_called_once_with([
            "H69:H69", "H71:H71", "H383:H383", "I69:I69",
            "K69:K69", "O69:O69", "P69:P69",
        ])

    def test_reset_does_not_write_when_section_is_empty(self):
        worksheet = Mock(title="TEST")
        worksheet.get.return_value = []
        self.assertEqual(clear_test_imports(worksheet), 0)
        worksheet.batch_clear.assert_not_called()

    def test_reset_rejects_live_worksheet_before_reading_or_clearing(self):
        worksheet = Mock(title="SEP")
        with self.assertRaises(ValueError):
            clear_test_imports(worksheet)
        worksheet.get.assert_not_called()
        worksheet.batch_clear.assert_not_called()

    @patch("budget_sheet.gspread.authorize")
    @patch("budget_sheet.Credentials.from_service_account_file")
    def test_opens_configured_workbook_and_month_with_service_account(
        self, load_credentials, authorize
    ):
        worksheet = open_budget_worksheet("example-credentials.json", "Example Budget", "SEP")

        load_credentials.assert_called_once_with(
            "example-credentials.json",
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        authorize.assert_called_once_with(load_credentials.return_value)
        authorize.return_value.open.assert_called_once_with("Example Budget")
        authorize.return_value.open.return_value.worksheet.assert_called_once_with("SEP")
        self.assertIs(worksheet, authorize.return_value.open.return_value.worksheet.return_value)

    def test_import_ignores_rows_before_transaction_section_and_appends_after_occupied_row(self):
        transaction = {
            "date": datetime(2026, 9, 1),
            "budget_name": "Gas",
            "amount": 42.1,
            "account": "Example Checking",
            "description": "SHELL SERVICE",
        }
        matching_row_above_section = [""] * 16
        matching_row_above_section[7] = "09/01/2026"
        matching_row_above_section[10] = "42.10"
        matching_row_above_section[14] = "Example Checking"
        matching_row_above_section[15] = "SHELL SERVICE"
        worksheet = Mock()
        occupied_row = [""] * 16
        occupied_row[7] = "09/02/2026"
        worksheet.get_all_values.return_value = (
            [[] for _ in range(67)] + [matching_row_above_section, occupied_row]
        )

        added, duplicates = import_transactions_to_worksheet(worksheet, [transaction])

        self.assertEqual(added, [transaction])
        self.assertEqual(duplicates, [])
        worksheet.get_all_values.assert_called_once_with()
        worksheet.acell.assert_not_called()
        worksheet.batch_update.assert_called_once_with([
            {"range": "H70:H70", "values": [["09/01/2026"]]},
            {"range": "I70:I70", "values": [["Gas"]]},
            {"range": "K70:K70", "values": [[42.1]]},
            {"range": "O70:O70", "values": [["Example Checking"]]},
            {"range": "P70:P70", "values": [["SHELL SERVICE"]]},
        ])

    def test_finds_first_empty_transaction_row(self):
        occupied_row = [""] * 7 + ["09/01/2026"]
        for label, rows, start, expected in [
            ("empty sheet", [], 69, 69),
            ("occupied dates", [[]] * 68 + [occupied_row, occupied_row], 69, 71),
            ("gap before later content", [[]] * 68 + [occupied_row, [], occupied_row], 69, 70),
            ("short row", [[]] * 68 + [["other content"]], 69, 69),
            ("custom start", [[]] * 9 + [occupied_row], 10, 11),
        ]:
            with self.subTest(case=label):
                self.assertEqual(find_first_empty_transaction_row(rows, start), expected)

    def test_duplicate_only_295_row_upload_reads_values_once_and_never_scans_cells(self):
        transactions = []
        rows = [[] for _ in range(68)]
        for index in range(295):
            description = f"Synthetic transaction {index}"
            transactions.append({
                "date": datetime(2026, 9, 1), "amount": 1.0,
                "account": "Example Checking", "description": description,
            })
            row = [""] * 16
            row[7], row[10], row[14], row[15] = (
                "09/01/2026", "1.00", "Example Checking", description
            )
            rows.append(row)
        worksheet = Mock()
        worksheet.get_all_values.return_value = rows
        worksheet.acell.side_effect = AssertionError("Per-cell network reads are forbidden")

        added, duplicates = import_transactions_to_worksheet(worksheet, transactions)

        self.assertEqual(added, [])
        self.assertEqual(duplicates, transactions)
        worksheet.get_all_values.assert_called_once_with()
        worksheet.acell.assert_not_called()
        worksheet.batch_update.assert_not_called()

    def test_builds_transaction_batch_updates_for_writable_columns(self):
        transactions = [
            {
                "date": datetime(2026, 9, 1),
                "budget_name": "Gas",
                "amount": 42.1,
                "account": "SoFi Checking (2695)",
                "description": "SHELL SERVICE",
            },
            {
                "date": datetime(2026, 9, 2),
                "budget_name": "Apple Music",
                "amount": 5.99,
                "account": "SoFi Checking (2695)",
                "description": "APPLE.COM/BILL",
            },
        ]

        updates = build_transaction_batch_updates(69, transactions)

        self.assertEqual(
            [update["range"] for update in updates],
            ["H69:H70", "I69:I70", "K69:K70", "O69:O70", "P69:P70"],
        )
        self.assertEqual(updates[0]["values"], [["09/01/2026"], ["09/02/2026"]])
        self.assertEqual(updates[1]["values"], [["Gas"], ["Apple Music"]])
        self.assertEqual(updates[2]["values"], [[42.1], [5.99]])
        self.assertEqual(
            updates[3]["values"],
            [["SoFi Checking (2695)"], ["SoFi Checking (2695)"]],
        )
        self.assertEqual(updates[4]["values"], [["SHELL SERVICE"], ["APPLE.COM/BILL"]])

    def test_builds_no_updates_when_there_are_no_transactions(self):
        self.assertEqual(build_transaction_batch_updates(69, []), [])


if __name__ == "__main__":
    unittest.main()
