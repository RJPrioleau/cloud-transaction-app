import gspread
from google.oauth2.service_account import Credentials

from transaction_processor import split_new_and_duplicate_transactions


def clear_test_imports(worksheet):
    """Clear constant import values in TEST rows 69–383, preserving formulas."""
    if worksheet.title != "TEST":
        raise ValueError("Reset is available only for the TEST worksheet.")

    rows = worksheet.get("H69:P383", value_render_option="FORMULA")
    ranges = []
    for column, offset in (("H", 0), ("I", 1), ("K", 3), ("O", 7), ("P", 8)):
        run_start = None
        for row_number in range(69, 385):
            row = rows[row_number - 69] if row_number <= 383 and row_number - 69 < len(rows) else []
            value = row[offset] if offset < len(row) else ""
            clearable = value not in ("", None) and not (
                isinstance(value, str) and value.startswith("=")
            )
            if clearable and run_start is None:
                run_start = row_number
            elif not clearable and run_start is not None:
                ranges.append(f"{column}{run_start}:{column}{row_number - 1}")
                run_start = None

    if ranges:
        worksheet.batch_clear(ranges)
    return len(ranges)


def open_budget_worksheet(credentials_path, spreadsheet_name, month):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    client = gspread.authorize(credentials)
    spreadsheet = client.open(spreadsheet_name)
    return spreadsheet.worksheet(month)


def import_transactions_to_worksheet(worksheet, transactions):
    existing_rows = worksheet.get_all_values()
    new_transactions, duplicate_transactions = split_new_and_duplicate_transactions(
        existing_rows[68:], transactions
    )
    if new_transactions:
        destination_row = find_first_empty_transaction_row(existing_rows)
        worksheet.batch_update(
            build_transaction_batch_updates(destination_row, new_transactions)
        )

    return new_transactions, duplicate_transactions


def find_first_empty_transaction_row(existing_rows, start_row=69):
    """Find the first blank date cell using the already-fetched worksheet rows."""
    for row_number, row in enumerate(existing_rows[start_row - 1:], start_row):
        if len(row) < 8 or not row[7]:
            return row_number
    return max(start_row, len(existing_rows) + 1)


def build_transaction_batch_updates(start_row, transactions):
    if not transactions:
        return []

    end_row = start_row + len(transactions) - 1

    return [
        {
            "range": f"H{start_row}:H{end_row}",
            "values": [[item["date"].strftime("%m/%d/%Y")] for item in transactions],
        },
        {
            "range": f"I{start_row}:I{end_row}",
            "values": [[item["budget_name"]] for item in transactions],
        },
        {
            "range": f"K{start_row}:K{end_row}",
            "values": [[item["amount"]] for item in transactions],
        },
        {
            "range": f"O{start_row}:O{end_row}",
            "values": [[item["account"]] for item in transactions],
        },
        {
            "range": f"P{start_row}:P{end_row}",
            "values": [[item["description"]] for item in transactions],
        },
    ]
