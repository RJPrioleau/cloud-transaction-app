import unittest
from datetime import datetime

from budget_sheet import (
    build_transaction_batch_updates,
    find_first_empty_transaction_row,
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
