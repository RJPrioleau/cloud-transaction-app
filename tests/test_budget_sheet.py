import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from budget_sheet import (
    build_transaction_batch_updates,
    find_first_empty_transaction_row,
    import_transactions_to_worksheet,
    open_budget_worksheet,
)


class FakeCell:
    def __init__(self, value):
        self.value = value


class FakeWorksheet:
    def __init__(self, occupied_cells):
        self.occupied_cells = occupied_cells

    def acell(self, cell_name):
        return FakeCell(self.occupied_cells.get(cell_name))


class BudgetSheetTests(unittest.TestCase):
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
        worksheet.get_all_values.return_value = (
            [[] for _ in range(67)] + [matching_row_above_section] + [[""] * 16]
        )
        worksheet.acell.side_effect = [FakeCell("09/02/2026"), FakeCell("")]

        added, duplicates = import_transactions_to_worksheet(worksheet, [transaction])

        self.assertEqual(added, [transaction])
        self.assertEqual(duplicates, [])
        worksheet.batch_update.assert_called_once_with([
            {"range": "H70:H70", "values": [["09/01/2026"]]},
            {"range": "I70:I70", "values": [["Gas"]]},
            {"range": "K70:K70", "values": [[42.1]]},
            {"range": "O70:O70", "values": [["Example Checking"]]},
            {"range": "P70:P70", "values": [["SHELL SERVICE"]]},
        ])

    def test_finds_first_empty_transaction_row(self):
        worksheet = FakeWorksheet({
            "H69": "09/01/2026",
            "H70": "09/02/2026",
        })

        self.assertEqual(find_first_empty_transaction_row(worksheet), 71)

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
